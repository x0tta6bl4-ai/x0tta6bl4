import ast
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.ops import automated_pilot_launcher as launcher


REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT = REPO_ROOT / "scripts" / "ops" / "automated_pilot_launcher.py"


def _launcher_source() -> str:
    return SCRIPT.read_text(encoding="utf-8")


def test_run_plan_defaults_to_dry_run_without_subprocess(tmp_path, monkeypatch):
    called = False

    def fake_run(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(launcher.subprocess, "Popen", fake_run)

    results = launcher.run_plan(root=tmp_path, hosts=("nl",), apply_live=False)

    assert called is False
    assert results
    assert all(item["status"] == "dry-run" for item in results)


def test_apply_live_requires_confirmation_token(tmp_path):
    with pytest.raises(ValueError, match="LIVE_PILOT_MUTATION"):
        launcher.run_plan(root=tmp_path, hosts=("nl",), apply_live=True, confirm="")


def test_build_plan_uses_list_form_commands(tmp_path):
    plan = launcher.build_plan(root=tmp_path, hosts=("sb",))

    assert [step.name for step in plan] == [
        "start_hardhat",
        "stop_existing_maas",
        "start_control_plane",
        "tunnel_sb",
        "prepare_remote_sb",
        "sync_sb",
        "start_agent_sb",
    ]
    assert all(isinstance(step.argv, tuple) for step in plan)
    assert plan[3].argv[:3] == ("ssh", "-f", "-N")
    assert plan[4].argv == ("ssh", "sb", "mkdir -p /tmp/x0t_pilot/src")
    assert plan[5].argv == ("rsync", "-avz", "src/", "sb:/tmp/x0t_pilot/src/")


def test_apply_live_uses_list_form_subprocess(tmp_path, monkeypatch):
    calls = []

    class FakeProcess:
        pass

    def fake_popen(command, **kwargs):
        calls.append(("Popen", command, kwargs))
        return FakeProcess()

    def fake_run(command, **kwargs):
        calls.append(("run", command, kwargs))
        return type("Result", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    monkeypatch.setattr(launcher.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(launcher.subprocess, "run", fake_run)

    results = launcher.run_plan(
        root=tmp_path,
        hosts=("nl",),
        apply_live=True,
        confirm=launcher.CONFIRM_TOKEN,
    )

    assert all(item["status"] in {"ok", "started"} for item in results)
    assert calls
    assert all(isinstance(command, list) for _, command, _ in calls)
    assert all("shell" not in kwargs for _, _, kwargs in calls)


def test_main_json_output_is_dry_run_without_subprocess(monkeypatch, capsys):
    called = False

    def fake_run(*_args, **_kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(launcher.subprocess, "run", fake_run)
    monkeypatch.setattr(launcher.subprocess, "Popen", fake_run)

    rc = launcher.main(["--host", "sb", "--output", "json"])

    assert rc == 0
    assert called is False
    payload = launcher.json.loads(capsys.readouterr().out)
    assert payload["mode"] == "dry-run"
    assert payload["hosts"] == ["sb"]
    assert all(item["status"] == "dry-run" for item in payload["results"])


def test_cli_json_dry_run_does_not_invoke_transport_commands(tmp_path):
    marker_dir = tmp_path / "markers"
    marker_dir.mkdir()
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()

    for command in ("npx", "pkill", "python3", "ssh", "rsync"):
        stub = bin_dir / command
        stub.write_text(
            "#!/bin/sh\n"
            f"touch {marker_dir / command}\n"
            "exit 99\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = str(bin_dir)

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--host", "sb", "--output", "json"],
        check=False,
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        timeout=5,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["hosts"] == ["sb"]
    assert all(item["status"] == "dry-run" for item in payload["results"])
    assert sorted(path.name for path in marker_dir.iterdir()) == []


def test_launcher_source_rejects_legacy_live_runner_patterns():
    source = _launcher_source()
    tree = ast.parse(source)

    assert "shell=True" not in source
    assert "Sovereign Mesh Pilot Stabilized" not in source
    assert "v1.0 REALITY" not in source

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            assert not (
                keyword.arg == "shell"
                and isinstance(keyword.value, ast.Constant)
                and keyword.value.value is True
            )

    main_guard = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    assert len(main_guard) == 1
    guard_source = ast.unparse(main_guard[0])
    assert "main()" in guard_source
    assert "start_hardhat()" not in guard_source
    assert "start_control_plane()" not in guard_source
    assert "setup_tunnels_and_agents()" not in guard_source
