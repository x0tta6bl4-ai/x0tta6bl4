from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/run_income_watch_cycle.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("run_income_watch_cycle", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_x402_directory_timeout_is_soft_when_public_endpoint_is_ready() -> None:
    mod = _load_module()

    summary = mod._summarise_results(
        [
            {"name": "x402_public_ready", "ok": True},
            {"name": "x402_directory_watch", "ok": False, "timed_out": True},
            {"name": "agentjob_paid_chat", "ok": True},
        ]
    )

    assert summary["commands_failed"] == []
    assert summary["commands_soft_failed"] == ["x402_directory_watch"]


def test_ontario_readiness_failure_is_soft_when_public_endpoint_is_ready() -> None:
    mod = _load_module()

    summary = mod._summarise_results(
        [
            {"name": "x402_public_ready", "ok": True},
            {"name": "ontario_x402_readiness", "ok": False, "timed_out": True},
            {"name": "agentjob_paid_chat", "ok": True},
        ]
    )

    assert summary["commands_failed"] == []
    assert summary["commands_soft_failed"] == ["ontario_x402_readiness"]


def test_external_marketplace_tls_eof_is_soft_when_public_endpoint_is_ready() -> None:
    mod = _load_module()

    summary = mod._summarise_results(
        [
            {"name": "x402_public_ready", "ok": True},
            {
                "name": "bothire_work_loop",
                "ok": False,
                "stderr_tail": "urllib.error.URLError: <urlopen error [SSL: UNEXPECTED_EOF_WHILE_READING]>",
            },
            {
                "name": "opentask_status",
                "ok": False,
                "stderr_tail": "curl: (35) OpenSSL SSL_connect: SSL_ERROR_SYSCALL",
            },
            {"name": "payanagent_job_watch", "ok": False, "stderr_tail": "other error"},
        ]
    )

    assert summary["commands_failed"] == ["payanagent_job_watch"]
    assert summary["commands_soft_failed"] == ["bothire_work_loop", "opentask_status"]


def test_x402_directory_failure_is_hard_when_public_endpoint_is_not_ready() -> None:
    mod = _load_module()

    summary = mod._summarise_results(
        [
            {"name": "x402_public_ready", "ok": False},
            {"name": "x402_directory_watch", "ok": False, "timed_out": True},
        ]
    )

    assert summary["commands_failed"] == ["x402_public_ready", "x402_directory_watch"]
    assert summary["commands_soft_failed"] == []


def test_income_watch_cycle_includes_agentpact_alert_subscription() -> None:
    mod = _load_module()

    names = [name for name, _argv, _timeout in mod._commands(agentjob_wait_seconds=5)]

    assert "agentpact_wallet_watch" in names
    assert "agentpact_wallet_targeted_offers" in names
    assert "agentpact_alerts_subscribe" in names
    assert "agentpact_webhook_register" in names
    assert "jaypay_402directory_submit_all" in names
    assert "github_bounty_claim_watch" in names
    assert "mergework_mrwk_claim_watch" in names


def test_offline_income_watch_cycle_skips_external_commands(tmp_path: Path) -> None:
    mod = _load_module()
    output = tmp_path / "income-watch-cycle.json"

    snapshot = mod.run_cycle(
        wallet=mod.TARGET_WALLET,
        output=output,
        agentjob_wait_seconds=5,
        cycle=1,
        offline=True,
    )

    assert output.exists()
    persisted = json.loads(output.read_text(encoding="utf-8"))
    assert persisted == snapshot
    assert snapshot["offline_mode"] is True
    assert snapshot["funds_received_claim_allowed"] is False
    assert snapshot["wallet_before"]["skipped"] is True
    assert snapshot["wallet_after"]["skipped"] is True
    assert snapshot["commands_failed"] == []
    assert snapshot["commands_total"] == len(snapshot["results"])
    assert all(item["skipped"] is True for item in snapshot["results"])
    assert snapshot["next_action"] == "run_online_watch_with_operator_approval"
