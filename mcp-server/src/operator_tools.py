"""
x0tta6bl4 MCP Operator Server — local tools for mesh diagnostics,
MAPE-K status, verification, SBOM, and agent coordination.

Transport: stdio
Protocol:  Model Context Protocol v1

Run:
    python3 mcp-server/src/operator_tools.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import Resource, ResourceTemplate, TextContent, Tool

ROOT_DIR = Path(__file__).resolve().parent.parent.parent

# ── Helpers ───────────────────────────────────────────────────────────────────

def _run(cmd: list[str], timeout: int = 120, cwd: str | None = None) -> dict[str, Any]:
    """Run a subprocess and return structured result."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=cwd or str(ROOT_DIR),
            env={**os.environ, "NO_COLOR": "1"},
        )
        return {
            "exit_code": result.returncode,
            "stdout": result.stdout[-8000:] if len(result.stdout) > 8000 else result.stdout,
            "stderr": result.stderr[-4000:] if len(result.stderr) > 4000 else result.stderr,
        }
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": f"Command timed out after {timeout}s"}
    except FileNotFoundError as e:
        return {"exit_code": -1, "stdout": "", "stderr": str(e)}


def _read_json(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return None


@contextmanager
def _suppress_import_stdio():
    """Keep stdio MCP framing clean when third-party imports print banners."""
    with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
        yield


def _file_entry(path: str) -> dict[str, Any]:
    full_path = ROOT_DIR / path
    return {
        "path": path,
        "exists": full_path.exists(),
        "size": full_path.stat().st_size if full_path.exists() else None,
    }


def _read_text_resource(path: str) -> list[ReadResourceContents]:
    full_path = ROOT_DIR / path
    if not full_path.exists():
        payload = {"error": "resource_missing", "path": path}
        return [ReadResourceContents(json.dumps(payload, indent=2), "application/json")]
    return [ReadResourceContents(full_path.read_text(encoding="utf-8", errors="replace"), "text/markdown")]


VPN_DOC_RESOURCES = {
    "status-reality": "STATUS_REALITY.md",
    "prod-source-of-truth": ".claude/rules/50-prod-source-of-truth.md",
    "ghost-access-readme": "docs/ghost-access/README.md",
    "ghost-access-self-test": "docs/ghost-access/SELF_TEST_CHECKLIST.md",
    "ghost-access-execution-plan": "docs/ghost-access/EXECUTION_PLAN.md",
    "spb-beta-rollout": "docs/ghost-access/spb-beta-rollout.md",
    "ghost-canary-runtime": "docs/ghost-access/ghost-canary-runtime.md",
    "vpn-production-summary": "docs/vpn/VPN_PRODUCTION_SUMMARY.md",
}


# ── Tool implementations ─────────────────────────────────────────────────────

async def verify_status(args: dict) -> dict:
    """Run scripts/verify-v1.1.sh --fast and return structured results."""
    timeout = args.get("timeout_seconds", 180)
    extra_env = {}
    if args.get("include_open5gs"):
        extra_env["VERIFY_OPEN5GS_LOCAL_SIGNALING"] = "1"
    if args.get("ebpf_build_timeout"):
        extra_env["VERIFY_EBPF_BUILD_TIMEOUT_SEC"] = str(args["ebpf_build_timeout"])

    env = {**os.environ, **extra_env, "NO_COLOR": "1"}
    try:
        result = subprocess.run(
            ["bash", "scripts/verify-v1.1.sh", "--fast"],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(ROOT_DIR), env=env,
        )
    except subprocess.TimeoutExpired:
        return {"error": f"Verification timed out after {timeout}s"}

    output = result.stdout
    # Parse summary counts
    counts = {}
    for label in ("VERIFIED HERE", "VERIFIED VIA SCRIPT/CI", "NOT VERIFIED YET", "FAILED"):
        import re
        m = re.search(rf"{re.escape(label)}.*?(\d+)", output)
        if m:
            counts[label.lower().replace(" ", "_").replace("/", "_")] = int(m.group(1))

    return {
        "counts": counts,
        "summary": output[output.find("SUMMARY"):] if "SUMMARY" in output else output[-3000:],
        "exit_code": result.returncode,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def mape_k_status(args: dict) -> dict:
    """Get MAPE-K self-healing loop status from Python runtime."""
    try:
        sys.path.insert(0, str(ROOT_DIR))
        with _suppress_import_stdio():
            from src.self_healing.mape_k import (
                MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, MAPEKExecutor, MAPEKKnowledge,
            )
        info = {
            "module": "src.self_healing.mape_k",
            "importable": True,
            "components": ["MAPEKMonitor", "MAPEKAnalyzer", "MAPEKPlanner", "MAPEKExecutor", "MAPEKKnowledge"],
        }
    except ImportError as e:
        info = {"module": "src.self_healing.mape_k", "importable": False, "error": str(e)}

    # Check recovery actions
    try:
        with _suppress_import_stdio():
            from src.self_healing.recovery_actions import RecoveryActionExecutor
        info["recovery_executor"] = "available"
    except ImportError:
        info["recovery_executor"] = "unavailable"

    # Check PQC status (Real liboqs check)
    try:
        with _suppress_import_stdio():
            from src.security.pqc.adapter import is_liboqs_available
            pqc_enabled = is_liboqs_available()
        info["pqc_status"] = "enabled (real)" if pqc_enabled else "disabled (fallback)"
    except ImportError:
        info["pqc_status"] = "unknown (module missing)"

    # Version
    try:
        with _suppress_import_stdio():
            from src.version import __version__
        info["version"] = __version__
    except ImportError:
        info["version"] = "unknown"

    return info


async def mesh_topology(args: dict) -> dict:
    """Get mesh network topology snapshot."""
    # Check for local mesh state files
    state_file = ROOT_DIR / ".agent-coord" / "state.json"
    state = _read_json(state_file)

    # Check running services
    result = _run(["bash", "-c", "ss -tlnp 2>/dev/null | head -30"])
    listening_ports = result["stdout"] if result["exit_code"] == 0 else "unavailable"

    # Docker containers
    docker_result = _run(["docker", "ps", "--format", "{{.Names}}\t{{.Status}}\t{{.Ports}}"], timeout=10)
    containers = docker_result["stdout"] if docker_result["exit_code"] == 0 else "docker unavailable"

    # Interface info
    iface_result = _run(["ip", "-brief", "addr", "show"], timeout=5)
    interfaces = iface_result["stdout"] if iface_result["exit_code"] == 0 else "unavailable"

    return {
        "coordination_state": state,
        "listening_ports": listening_ports,
        "docker_containers": containers,
        "network_interfaces": interfaces,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def agent_coordination(args: dict) -> dict:
    """Get agent coordination status and inbox."""
    action = args.get("action", "status")

    if action == "status":
        result = _run(["bash", "scripts/agent-coord.sh", "status"])
    elif action == "inbox":
        agent = args.get("agent", "claude")
        result = _run(["bash", "scripts/agent-coord.sh", "inbox", agent])
    elif action == "send":
        result = _run([
            "bash", "scripts/agent-coord.sh", "send",
            args.get("from_agent", "claude"),
            args.get("to_agent", ""),
            args.get("subject", "mcp"),
            args.get("message", ""),
        ])
    else:
        return {"error": f"Unknown action: {action}. Use: status, inbox, send"}

    return {
        "action": action,
        "output": result["stdout"],
        "exit_code": result["exit_code"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def sbom_check(args: dict) -> dict:
    """Run SBOM generation and vulnerability scan."""
    mode = args.get("mode", "quick")

    if mode == "quick":
        # Check existing SBOM artifacts
        sbom_dir = ROOT_DIR / "security" / "sbom"
        artifacts = []
        if sbom_dir.exists():
            for f in sbom_dir.glob("*.json"):
                artifacts.append({"name": f.name, "size": f.stat().st_size})
            for f in sbom_dir.glob("*.grype.json"):
                artifacts.append({"name": f.name, "size": f.stat().st_size})
        return {"mode": "quick", "artifacts": artifacts}

    elif mode == "full":
        result = _run(
            ["bash", "security/sbom/run-local-sbom-check.sh", "full", "--tool-mode", "docker"],
            timeout=300,
        )
        return {
            "mode": "full",
            "output": result["stdout"][-4000:],
            "exit_code": result["exit_code"],
        }

    elif mode == "cosign":
        result = _run(
            ["bash", "security/sbom/verify-cosign-rekor.sh", "--mode", "mock", "--tool-mode", "docker"],
            timeout=300,
        )
        return {
            "mode": "cosign",
            "output": result["stdout"][-4000:],
            "exit_code": result["exit_code"],
        }

    return {"error": f"Unknown mode: {mode}. Use: quick, full, cosign"}


async def run_tests(args: dict) -> dict:
    """Run project test suites."""
    suite = args.get("suite", "fast")
    extra_args = args.get("extra_args", "")

    # Allowlist безопасных pytest-флагов (защита от argument injection)
    _SAFE_PYTEST_FLAGS = {"-v", "-s", "-x", "-q", "--tb=short", "--tb=long", "--tb=no",
                          "--tb=line", "--no-header", "--timeout=30", "--timeout=60"}

    if suite == "fast":
        cmd = ["python3", "-m", "pytest", "-x", "-q", "--tb=short", "--timeout=30"]
        if extra_args:
            for flag in extra_args.split():
                if flag in _SAFE_PYTEST_FLAGS:
                    cmd.append(flag)
        result = _run(cmd, timeout=180)

    elif suite == "go":
        result = _run(
            ["bash", "-c",
             "env -u GOSUMDB GOCACHE=/mnt/projects/.tmp/go-build go test ./edge/5g/... -v"],
            timeout=120,
        )

    elif suite == "specific":
        path = args.get("path", "test/")
        cmd = ["python3", "-m", "pytest", "-x", "-q", "--tb=short", path]
        result = _run(cmd, timeout=180)

    else:
        return {"error": f"Unknown suite: {suite}. Use: fast, go, specific"}

    return {
        "suite": suite,
        "output": result["stdout"][-6000:],
        "stderr": result["stderr"][-2000:],
        "exit_code": result["exit_code"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def ghost_vpn_status(args: dict) -> dict:
    """Check Ghost VPN components status."""
    status = {}

    # Check key module files exist (avoid importing — some have blocking side-effects)
    module_files = {
        "ghost_vpn_server": ROOT_DIR / "src" / "network" / "ghost_vpn_server.py",
        "ghost_vpn_client": ROOT_DIR / "src" / "network" / "ghost_vpn_client.py",
        "ghost_proto": ROOT_DIR / "src" / "network" / "transport" / "ghost_proto.py",
        "evolution_agent": ROOT_DIR / "src" / "anti_censorship" / "evolution_agent.py",
        "ghost_vpn_adapter": ROOT_DIR / "src" / "anti_censorship" / "ghost_vpn_adapter.py",
    }
    for name, path in module_files.items():
        if path.exists():
            status[name] = f"present ({path.stat().st_size} bytes)"
        else:
            status[name] = "missing"

    # Docker compose files (check known locations, avoid recursive glob on large repo)
    compose_candidates = [
        ROOT_DIR / "docker-compose.ghost-vpn.yml",
        ROOT_DIR / "deploy" / "compose" / "docker-compose.ghost-vpn.yml",
    ]
    status["compose_files"] = [
        str(f.relative_to(ROOT_DIR)) for f in compose_candidates if f.exists()
    ]

    # Check Dockerfile
    dockerfile = ROOT_DIR / "Dockerfile.ghost-vpn"
    status["dockerfile_exists"] = dockerfile.exists()

    return {
        "modules": status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def ghost_access_status(args: dict) -> dict:
    """Return a local, read-only Ghost Access/VPN development inventory."""
    product_runtime_files = [
        "telegram_bot_simple.py",
        "database.py",
        "scripts/xui_client_manager.py",
        "scripts/xray_runtime_user_manager.py",
        "scripts/sync_xray_device_activity.py",
        "deploy/env.bot.example",
    ]
    observability_files = [
        "scripts/run_vpn_service_access_agent.py",
        "scripts/show_vpn_service_access_status.py",
        "scripts/run_vpn_delivery_canary.py",
        "scripts/ghost_vpn_operator_gate.py",
        "docs/operations/vpn-profile-health-runbook.md",
    ]
    client_compat_files = [
        "scripts/build_v2rayn_canary_bundle.py",
        "scripts/validate_client_compatibility.py",
        "docs/vpn/VPN_USER_GUIDE.md",
        "docs/ghost-access/SELF_TEST_CHECKLIST.md",
    ]
    ghostvpn_research_files = [
        "src/network/ghost_vpn_server.py",
        "src/network/transport/ghost_proto.py",
        "src/network/vpn_runtime_state.py",
        "Dockerfile.ghost-vpn",
        "docker-compose.vpn-fallback.yml",
    ]

    return {
        "status": "local_inventory_only",
        "source_of_truth": [
            "STATUS_REALITY.md",
            ".claude/rules/50-prod-source-of-truth.md",
            "docs/ghost-access/README.md",
            "docs/ghost-access/SELF_TEST_CHECKLIST.md",
        ],
        "guardrails": [
            "No live NL/SPB SSH, service restart, xray/x-ui config edit, or DB write from this tool.",
            "Codex lane must not patch Ghost Access runtime paths directly; runtime fixes go through claude or vpn-runtime-ops.",
            "VPN_IMPLEMENTATION_ROADMAP.md and older docs/vpn roadmap files are aspirational unless backed by fresh evidence.",
        ],
        "known_open_issues_from_truth_surface": [
            "SPB entry-443 has 17-18 orphan UUIDs relative to the bot database; cleanup needs claude/vpn-runtime-ops and user-approved restart.",
            "SPB is not full production; STATUS_REALITY marks it staging/light-mode with remaining simulation gaps.",
            "Client import/live connectivity still needs real-device evidence for CLIENTQA-RDM-001.",
            "GhostVPN canary/sidecar evidence must not be promoted to field-validated end-user VPN data path.",
        ],
        "development_surfaces": {
            "ghost_access_product_runtime": [_file_entry(path) for path in product_runtime_files],
            "vpn_observability": [_file_entry(path) for path in observability_files],
            "client_compatibility": [_file_entry(path) for path in client_compat_files],
            "ghostvpn_research_stack": [_file_entry(path) for path in ghostvpn_research_files],
        },
        "docs_exposed_as_mcp_resources": sorted(VPN_DOC_RESOURCES),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def healing_trigger(args: dict) -> dict:
    """Trigger or simulate a MAPE-K healing action."""
    action = args.get("action", "diagnose")
    dry_run = args.get("dry_run", True)

    if action == "diagnose":
        # Run diagnostic checks
        checks = {}
        # Disk
        disk = _run(["df", "-h", "/"], timeout=5)
        checks["disk"] = disk["stdout"].strip()
        # Memory
        mem = _run(["free", "-h"], timeout=5)
        checks["memory"] = mem["stdout"].strip()
        # Load
        load = _run(["uptime"], timeout=5)
        checks["load"] = load["stdout"].strip()
        # Docker health
        docker = _run(["docker", "ps", "-a", "--format", "{{.Names}}: {{.Status}}"], timeout=10)
        checks["docker"] = docker["stdout"].strip() if docker["exit_code"] == 0 else "unavailable"

        return {"action": "diagnose", "checks": checks}

    elif action == "restart_service":
        service = args.get("service", "")
        if not service:
            return {"error": "service name required"}
        if dry_run:
            return {"action": "restart_service", "service": service, "dry_run": True,
                    "message": f"Would restart {service}. Set dry_run=false to execute."}
        result = _run(["docker", "restart", service], timeout=30)
        return {"action": "restart_service", "service": service, "result": result}

    elif action == "reroute":
        if dry_run:
            return {"action": "reroute", "dry_run": True,
                    "message": "Would trigger AODV re-routing. Set dry_run=false to execute."}
        return {"action": "reroute", "status": "not_implemented_in_local_mode"}

    return {"error": f"Unknown action: {action}. Use: diagnose, restart_service, reroute"}


# ── Tool definitions ─────────────────────────────────────────────────────────

TOOLS = [
    Tool(
        name="verify_status",
        description="Run the x0tta6bl4 verification suite (verify-v1.1.sh --fast) and return structured pass/fail/skip counts with full summary.",
        inputSchema={
            "type": "object",
            "properties": {
                "timeout_seconds": {"type": "integer", "default": 180, "description": "Max seconds to wait"},
                "include_open5gs": {"type": "boolean", "default": False, "description": "Include Open5GS local signaling validation"},
                "ebpf_build_timeout": {"type": "integer", "description": "Override eBPF build timeout (seconds)"},
            },
        },
    ),
    Tool(
        name="mape_k_status",
        description="Check MAPE-K self-healing loop importability, PQC status, recovery executor availability, and project version.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="mesh_topology",
        description="Get mesh topology snapshot: coordination state, listening ports, Docker containers, and network interfaces.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="agent_coordination",
        description="Interact with the multi-agent coordination system. Actions: status (overview), inbox (per-agent messages), send (post a message).",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["status", "inbox", "send"], "default": "status"},
                "agent": {"type": "string", "description": "Agent name for inbox action"},
                "from_agent": {"type": "string", "description": "Sender for send action"},
                "to_agent": {"type": "string", "description": "Recipient for send action"},
                "subject": {"type": "string", "description": "Message subject"},
                "message": {"type": "string", "description": "Message body"},
            },
        },
    ),
    Tool(
        name="sbom_check",
        description="Run SBOM generation and vulnerability scanning. Modes: quick (check existing artifacts), full (generate + scan via Docker), cosign (mock cosign/Rekor verification).",
        inputSchema={
            "type": "object",
            "properties": {
                "mode": {"type": "string", "enum": ["quick", "full", "cosign"], "default": "quick"},
            },
        },
    ),
    Tool(
        name="run_tests",
        description="Run project test suites. Suites: fast (Python pytest quick), go (edge/5g Go tests), specific (target path).",
        inputSchema={
            "type": "object",
            "properties": {
                "suite": {"type": "string", "enum": ["fast", "go", "specific"], "default": "fast"},
                "path": {"type": "string", "description": "Test path for 'specific' suite"},
                "extra_args": {"type": "string", "description": "Additional pytest args"},
            },
        },
    ),
    Tool(
        name="ghost_vpn_status",
        description="Check Ghost VPN component health: module importability, Docker compose files, Dockerfile presence.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="ghost_access_status",
        description="Read-only local inventory for Ghost Access/VPN development surfaces, truth docs, guardrails, and open issues.",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="healing_trigger",
        description="Trigger or simulate MAPE-K healing actions. Actions: diagnose (system health), restart_service (Docker), reroute (mesh path). Default is dry_run=true.",
        inputSchema={
            "type": "object",
            "properties": {
                "action": {"type": "string", "enum": ["diagnose", "restart_service", "reroute"], "default": "diagnose"},
                "service": {"type": "string", "description": "Docker service name (for restart_service)"},
                "dry_run": {"type": "boolean", "default": True, "description": "Simulate without executing"},
            },
        },
    ),
]

TOOL_HANDLERS = {
    "verify_status": verify_status,
    "mape_k_status": mape_k_status,
    "mesh_topology": mesh_topology,
    "agent_coordination": agent_coordination,
    "sbom_check": sbom_check,
    "run_tests": run_tests,
    "ghost_vpn_status": ghost_vpn_status,
    "ghost_access_status": ghost_access_status,
    "healing_trigger": healing_trigger,
}

# ── MCP server bootstrap ────────────────────────────────────────────────────

app = Server("x0tta-operator-mcp")


@app.list_resources()
async def list_resources() -> list[Resource]:
    return [
        Resource(
            uri="x0tta://operator/heartbeat",
            name="operator_heartbeat",
            description="MCP server heartbeat and local repo/source-of-truth availability.",
            mimeType="application/json",
        ),
        Resource(
            uri="x0tta://vpn/developments",
            name="vpn_developments",
            description="Read-only Ghost Access/VPN local development inventory and current evidence boundaries.",
            mimeType="application/json",
        ),
        Resource(
            uri="x0tta://coord/tooling-registry",
            name="coord_tooling_registry",
            description="Generated coordination tooling registry JSON.",
            mimeType="application/json",
        ),
        *[
            Resource(
                uri=f"x0tta://vpn/doc/{name}",
                name=f"vpn_doc_{name.replace('-', '_')}",
                description=f"Whitelisted VPN/Ghost Access source document: {path}",
                mimeType="text/markdown",
            )
            for name, path in sorted(VPN_DOC_RESOURCES.items())
        ],
    ]


@app.list_resource_templates()
async def list_resource_templates() -> list[ResourceTemplate]:
    return [
        ResourceTemplate(
            uriTemplate="x0tta://vpn/doc/{name}",
            name="vpn_doc_by_name",
            description="Read a whitelisted VPN/Ghost Access truth document by symbolic name.",
            mimeType="text/markdown",
        )
    ]


@app.read_resource()
async def read_resource(uri) -> list[ReadResourceContents]:
    uri_str = str(uri).rstrip("/")
    if uri_str == "x0tta://operator/heartbeat":
        payload = {
            "server": "x0tta-operator-mcp",
            "root": str(ROOT_DIR),
            "status": "ok",
            "tools": sorted(TOOL_HANDLERS),
            "resources": [str(resource.uri) for resource in await list_resources()],
            "source_files": [
                _file_entry("STATUS_REALITY.md"),
                _file_entry(".agent-coord/tooling_registry.json"),
                _file_entry(".mcp.json"),
                _file_entry("docs/ghost-access/README.md"),
            ],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        return [ReadResourceContents(json.dumps(payload, indent=2), "application/json")]

    if uri_str == "x0tta://vpn/developments":
        payload = await ghost_access_status({})
        return [ReadResourceContents(json.dumps(payload, indent=2), "application/json")]

    if uri_str == "x0tta://coord/tooling-registry":
        path = ROOT_DIR / ".agent-coord" / "tooling_registry.json"
        if not path.exists():
            payload = {"error": "tooling_registry_missing", "path": str(path)}
            return [ReadResourceContents(json.dumps(payload, indent=2), "application/json")]
        return [ReadResourceContents(path.read_text(encoding="utf-8", errors="replace"), "application/json")]

    doc_prefix = "x0tta://vpn/doc/"
    if uri_str.startswith(doc_prefix):
        name = uri_str[len(doc_prefix):]
        path = VPN_DOC_RESOURCES.get(name)
        if path:
            return _read_text_resource(path)
        payload = {"error": "unknown_vpn_doc", "allowed": sorted(VPN_DOC_RESOURCES)}
        return [ReadResourceContents(json.dumps(payload, indent=2), "application/json")]

    payload = {
        "error": "unknown_resource",
        "uri": uri_str,
        "allowed": [str(resource.uri) for resource in await list_resources()],
    }
    return [ReadResourceContents(json.dumps(payload, indent=2), "application/json")]


@app.list_tools()
async def list_tools() -> list[Tool]:
    return TOOLS


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    handler = TOOL_HANDLERS.get(name)
    if not handler:
        return [TextContent(type="text", text=json.dumps({"error": f"Unknown tool: {name}"}))]
    try:
        result = await handler(arguments or {})
        return [TextContent(type="text", text=json.dumps(result, indent=2, default=str))]
    except Exception as e:
        return [TextContent(type="text", text=json.dumps({"error": f"{name} failed: {e}"}))]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
