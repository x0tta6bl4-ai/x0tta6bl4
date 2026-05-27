import json
from pathlib import Path

from src.integration import x0t_contract_build_verification as mod


def _write(path: Path, text: str = "") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _package_surface(root: Path) -> None:
    package_dir = root / mod.CONTRACT_PACKAGE_DIR
    _write(package_dir / "package.json", '{"scripts":{"compile":"hardhat compile","test":"hardhat test"}}')
    _write(package_dir / mod.HARDHAT_CLI, "hardhat")


def _result(name, command, returncode=0, stdout="", stderr=""):
    return mod.CommandResult(
        name=name,
        command=command,
        returncode=returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=1,
    )


def test_build_report_runs_node22_compile_and_test(monkeypatch, tmp_path):
    _package_surface(tmp_path)
    calls = []

    def fake_run(name, command, cwd, timeout):
        calls.append((name, command, cwd, timeout))
        stdout = "v22.10.0\n" if name == "node_version" else ""
        return _result(name, command, stdout=stdout)

    monkeypatch.setattr(mod, "_run_command", fake_run)

    report = mod.build_report(tmp_path, timeout=120)

    assert report["decision"] == "X0T_CONTRACT_BUILD_VERIFIED"
    assert report["contract_build_verified"] is True
    assert report["goal_can_be_marked_complete"] is False
    assert report["mutates_chain"] is False
    assert report["runs_live_rpc"] is False
    assert report["submits_transaction"] is False
    assert report["mutates_local_build_artifacts"] is True
    assert [call[0] for call in calls] == ["node_version", "hardhat_compile", "hardhat_test"]
    assert all(call[1][:5] == ["npx", "-y", "-p", mod.REQUIRED_NODE_PACKAGE, "node"] for call in calls)
    assert calls[2][1][-2:] == ["test", "--no-compile"]
    assert report["summary"]["required_node_runtime_ready"] is True
    assert report["summary"]["hardhat_compile_ready"] is True
    assert report["summary"]["hardhat_test_ready"] is True


def test_build_report_stops_after_compile_failure(monkeypatch, tmp_path):
    _package_surface(tmp_path)
    calls = []

    def fake_run(name, command, cwd, timeout):
        calls.append(name)
        if name == "node_version":
            return _result(name, command, stdout="v22.10.0\n")
        return _result(name, command, returncode=1, stderr="compile failed")

    monkeypatch.setattr(mod, "_run_command", fake_run)

    report = mod.build_report(tmp_path)

    assert report["decision"] == "X0T_CONTRACT_BUILD_BLOCKED"
    assert report["contract_build_verified"] is False
    assert calls == ["node_version", "hardhat_compile"]
    assert report["summary"]["hardhat_compile_ready"] is False
    assert report["summary"]["hardhat_test_ready"] is False


def test_cli_writes_artifact_and_require_verified_blocks(monkeypatch, tmp_path, capsys):
    _package_surface(tmp_path)

    def fake_run(name, command, cwd, timeout):
        if name == "node_version":
            return _result(name, command, stdout="v20.19.6\n")
        return _result(name, command)

    monkeypatch.setattr(mod, "_run_command", fake_run)
    output = tmp_path / "out.json"

    exit_code = mod.main([
        "--root",
        str(tmp_path),
        "--write-json",
        "--output-json",
        str(output),
        "--require-verified",
    ])

    assert exit_code == 2
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["schema_version"] == mod.SCHEMA_VERSION
    assert payload["contract_build_verified"] is False
    printed = json.loads(capsys.readouterr().out)
    assert printed["decision"] == "X0T_CONTRACT_BUILD_BLOCKED"
