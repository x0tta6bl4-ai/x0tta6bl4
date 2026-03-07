from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import sys
from contextlib import redirect_stdout
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "ops" / "utrecht_6g_deploy.py"
    spec = importlib.util.spec_from_file_location("utrecht_6g_deploy", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load utrecht_6g_deploy module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_args_defaults():
    mod = _load_module()
    args = mod.parse_args([])
    assert args.nodes is None
    assert args.owner_id is None
    assert args.billing_plan is None
    assert args.output == "text"


def test_build_config_rejects_non_positive_nodes():
    mod = _load_module()
    args = mod.parse_args(["--nodes", "0"])
    with pytest.raises(ValueError, match="greater than 0"):
        mod.build_config(args)


def test_build_config_uses_defaults_when_no_cli_overrides():
    mod = _load_module()
    args = mod.parse_args([])
    cfg = mod.build_config(args)

    assert cfg.nodes == 50
    assert cfg.owner_id == "utrecht_enterprise_001"
    assert cfg.billing_plan == "enterprise"


def test_build_config_applies_values_file_overrides(tmp_path):
    mod = _load_module()
    values = tmp_path / "values.yaml"
    values.write_text(
        """
replicas: 11
billing:
  plan: pro
  region: eu-north-test
network:
  obfuscation: ws-tls
pqc:
  enabled: false
""".strip(),
        encoding="utf-8",
    )

    args = mod.parse_args(["--values-file", str(values)])
    cfg = mod.build_config(args)

    assert cfg.nodes == 11
    assert cfg.billing_plan == "pro"
    assert cfg.region == "eu-north-test"
    assert cfg.obfuscation == "ws-tls"
    assert cfg.pqc_enabled is False


def test_build_config_cli_overrides_values_file(tmp_path):
    mod = _load_module()
    values = tmp_path / "values.yaml"
    values.write_text(
        """
replicas: 11
billing:
  plan: pro
""".strip(),
        encoding="utf-8",
    )

    args = mod.parse_args(
        ["--values-file", str(values), "--nodes", "5", "--billing-plan", "enterprise"]
    )
    cfg = mod.build_config(args)

    assert cfg.nodes == 5
    assert cfg.billing_plan == "enterprise"


def test_deploy_utrecht_demo_dry_run_returns_request_payload():
    mod = _load_module()
    cfg = mod.DeploymentConfig(dry_run=True, nodes=12, owner_id="pilot-a")
    result = asyncio.run(mod.deploy_utrecht_demo(config=cfg))

    assert result["status"] == "dry-run"
    assert result["request"]["owner_id"] == "pilot-a"
    assert result["request"]["nodes"] == 12
    assert result["request"]["pqc_enabled"] is True


def test_deploy_utrecht_demo_success_with_stub_provisioner():
    mod = _load_module()

    class _Provisioner:
        async def provision_mesh(self, **kwargs):
            assert kwargs["nodes"] == 7
            return type("Mesh", (), {"mesh_id": "mesh-test", "join_token": "join-abc"})()

    cfg = mod.DeploymentConfig(nodes=7, owner_id="pilot-b", dry_run=False)
    result = asyncio.run(mod.deploy_utrecht_demo(config=cfg, provisioner=_Provisioner()))

    assert result["status"] == "ok"
    assert result["mesh"]["mesh_id"] == "mesh-test"
    assert result["mesh"]["join_token"] == "join-abc"
    assert result["mesh"]["dashboard_url"].endswith("/mesh-test")


def test_main_dry_run_json_output():
    mod = _load_module()
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        rc = mod.main(["--dry-run", "--output", "json", "--nodes", "3"])

    assert rc == 0
    payload = json.loads(stdout.getvalue())
    assert payload["status"] == "dry-run"
    assert payload["request"]["nodes"] == 3


def test_main_returns_error_for_invalid_nodes():
    mod = _load_module()
    stdout = io.StringIO()
    with redirect_stdout(stdout):
        rc = mod.main(["--nodes", "0"])

    assert rc == 1
    assert "ERROR" in stdout.getvalue()
