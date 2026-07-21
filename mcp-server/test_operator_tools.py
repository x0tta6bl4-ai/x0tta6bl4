"""Tests for x0tta6bl4 MCP operator tools."""

import asyncio
import importlib.util
import json
import signal
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Load module without package import
spec = importlib.util.spec_from_file_location(
    "operator_tools", ROOT / "mcp-server" / "src" / "operator_tools.py"
)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


def run(coro, timeout=15):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(asyncio.wait_for(coro, timeout=timeout))
    finally:
        loop.close()


def test_tool_handler_coverage():
    tool_names = {t.name for t in mod.TOOLS}
    handler_names = set(mod.TOOL_HANDLERS.keys())
    assert tool_names == handler_names, f"Mismatch: {tool_names ^ handler_names}"


def test_mape_k_status():
    result = run(mod.mape_k_status({}))
    assert "module" in result
    assert "version" in result
    expected_version = (ROOT / "VERSION").read_text().strip()
    assert result["version"] == expected_version, f"Expected {expected_version}, got {result['version']}"


def test_healing_diagnose():
    result = run(mod.healing_trigger({"action": "diagnose"}))
    assert result["action"] == "diagnose"
    assert "checks" in result
    assert "disk" in result["checks"]


def test_healing_dry_run():
    result = run(mod.healing_trigger({"action": "restart_service", "service": "test", "dry_run": True}))
    assert result["dry_run"] is True
    assert "Would restart" in result["message"]


def test_sbom_quick():
    result = run(mod.sbom_check({"mode": "quick"}))
    assert result["mode"] == "quick"
    assert "artifacts" in result


def test_mesh_topology():
    result = run(mod.mesh_topology({}), timeout=20)
    assert "coordination_state" in result
    assert "timestamp" in result


def test_agent_coordination_status():
    result = run(mod.agent_coordination({"action": "status"}), timeout=30)
    assert result["action"] == "status"
    assert "output" in result


def test_ghost_vpn_status():
    result = run(mod.ghost_vpn_status({}), timeout=10)
    assert "modules" in result
    assert "timestamp" in result


def test_ghost_access_status():
    result = run(mod.ghost_access_status({}), timeout=10)
    assert result["status"] == "local_inventory_only"
    assert "development_surfaces" in result
    assert "STATUS_REALITY.md" in result["source_of_truth"]


def test_resources_expose_vpn_truth():
    resources = run(mod.list_resources(), timeout=10)
    uris = {str(resource.uri).rstrip("/") for resource in resources}
    assert "x0tta://operator/heartbeat" in uris
    assert "x0tta://vpn/developments" in uris
    assert "x0tta://coord/tooling-registry" in uris

    contents = run(mod.read_resource("x0tta://vpn/developments"), timeout=10)
    payload = json.loads(contents[0].content)
    assert payload["status"] == "local_inventory_only"


def test_mcp_proxy_mape_k_keeps_stdio_clean():
    result = subprocess.run(
        ["python3", "scripts/agents/mcp_client_proxy.py", "mape_k_status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    assert "Failed to parse JSONRPC message" not in result.stderr
    payload = json.loads(result.stdout)
    text = payload["content"][0]["text"]
    assert "liboqs-python faulthandler is disabled" not in result.stderr
    assert "pqc_status" in text


def test_unknown_action_errors():
    result = run(mod.healing_trigger({"action": "bogus"}))
    assert "error" in result

    result = run(mod.sbom_check({"mode": "bogus"}))
    assert "error" in result

    result = run(mod.agent_coordination({"action": "bogus"}))
    assert "error" in result


if __name__ == "__main__":
    passed = 0
    failed = 0
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for t in tests:
        print(f"  {t.__name__}...", end=" ", flush=True)
        try:
            t()
            print("PASS")
            passed += 1
        except asyncio.TimeoutError:
            print("TIMEOUT")
            failed += 1
        except Exception as e:
            print(f"FAIL: {e}")
            failed += 1
    print(f"\n  {passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
