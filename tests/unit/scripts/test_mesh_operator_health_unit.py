from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "ops" / "mesh_operator_health.py"
    spec = importlib.util.spec_from_file_location("mesh_operator_health", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load mesh_operator_health module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_run_preflight_success_with_cluster_check():
    mod = _load_module()

    def fake_run(command, timeout=30):  # noqa: ARG001
        mapping = {
            ("kubectl", "config", "current-context"): mod.CommandResult(0, "kind-x0tta", ""),
            ("kubectl", "cluster-info"): mod.CommandResult(0, "Kubernetes control plane", ""),
        }
        return mapping.get(tuple(command), mod.CommandResult(1, "", "unexpected command"))

    checks = mod.run_preflight(
        require_cluster=True,
        run=fake_run,
        which=lambda tool: "/usr/bin/kubectl" if tool == "kubectl" else None,
    )

    assert len(checks) == 3
    assert all(check.ok for check in checks)
    assert checks[1].details == "kind-x0tta"


def test_run_preflight_fails_when_kubectl_missing():
    mod = _load_module()

    def fake_run(command, timeout=30):  # noqa: ARG001
        return mod.CommandResult(127, "", "command not found: kubectl")

    checks = mod.run_preflight(
        require_cluster=False,
        run=fake_run,
        which=lambda _tool: None,
    )

    assert checks[0].ok is False
    assert "not found" in checks[0].details
    assert checks[1].ok is False


def test_run_smoke_success_for_expected_resources():
    mod = _load_module()
    namespace = "x0tta-mesh-system"
    release = "x0tta-mesh"
    deployment = f"{release}-x0tta-mesh-operator"
    service = f"{release}-x0tta-mesh-operator-metrics"

    def fake_run(command, timeout=30):  # noqa: ARG001
        mapping = {
            ("kubectl", "get", "namespace", namespace, "-o", "name"): mod.CommandResult(
                0, f"namespace/{namespace}", ""
            ),
            ("kubectl", "get", "crd", mod.MESH_CRD, "-o", "name"): mod.CommandResult(
                0, f"customresourcedefinition.apiextensions.k8s.io/{mod.MESH_CRD}", ""
            ),
            (
                "kubectl",
                "rollout",
                "status",
                f"deployment/{deployment}",
                "-n",
                namespace,
                "--timeout=120s",
            ): mod.CommandResult(0, f"deployment/{deployment} successfully rolled out", ""),
            ("kubectl", "get", "svc", service, "-n", namespace, "-o", "name"): mod.CommandResult(
                0, f"service/{service}", ""
            ),
            (
                "kubectl",
                "get",
                "deployment",
                deployment,
                "-n",
                namespace,
                "-o",
                "jsonpath={.status.readyReplicas}",
            ): mod.CommandResult(0, "2", ""),
        }
        return mapping.get(tuple(command), mod.CommandResult(1, "", "unexpected command"))

    checks = mod.run_smoke(
        namespace=namespace,
        release=release,
        wait_seconds=120,
        run=fake_run,
    )

    assert len(checks) == 5
    assert all(check.ok for check in checks)
    assert checks[-1].details == "readyReplicas=2"


def test_run_smoke_fails_when_ready_replicas_missing():
    mod = _load_module()

    def fake_run(command, timeout=30):  # noqa: ARG001
        if command[-1] == "jsonpath={.status.readyReplicas}":
            return mod.CommandResult(0, "", "")
        return mod.CommandResult(0, "ok", "")

    checks = mod.run_smoke(
        namespace="x0tta-mesh-system",
        release="x0tta-mesh",
        wait_seconds=60,
        run=fake_run,
    )

    assert checks[-1].ok is False
    assert "readyReplicas is empty" in checks[-1].details


def test_main_json_output_for_preflight(monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.setattr(
        mod,
        "run_preflight",
        lambda require_cluster, kubectl: [
            mod.CheckResult(name="tool:kubectl", ok=True, details="/usr/bin/kubectl")
        ],
    )
    rc = mod.main(["preflight", "--output", "json"])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["checks"][0]["name"] == "tool:kubectl"


def test_main_smoke_returns_nonzero_for_failures(monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.setattr(
        mod,
        "run_smoke",
        lambda namespace, release, wait_seconds, kubectl: [
            mod.CheckResult(name="rollout", ok=False, details="deployment failed")
        ],
    )
    rc = mod.main(["smoke", "--output", "text"])
    assert rc == 1
    assert "[FAIL] rollout: deployment failed" in capsys.readouterr().out


def test_main_rejects_negative_wait_seconds():
    mod = _load_module()
    with pytest.raises(SystemExit):
        mod.main(["smoke", "--wait-seconds", "-1"])
