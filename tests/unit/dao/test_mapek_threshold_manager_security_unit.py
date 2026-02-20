import json

from src.dao.governance import GovernanceEngine
from src.dao.mapek_threshold_manager import DEFAULT_THRESHOLDS, MAPEKThresholdManager


def _make_manager(tmp_path, monkeypatch, hmac_key: str | None = None) -> MAPEKThresholdManager:
    if hmac_key is None:
        monkeypatch.delenv("X0TTA6BL4_THRESHOLDS_HMAC_KEY", raising=False)
    else:
        monkeypatch.setenv("X0TTA6BL4_THRESHOLDS_HMAC_KEY", hmac_key)

    return MAPEKThresholdManager(
        governance_engine=GovernanceEngine("node-1"),
        storage_path=tmp_path,
    )


def test_apply_threshold_changes_writes_hmac_and_audit(tmp_path, monkeypatch):
    manager = _make_manager(tmp_path, monkeypatch, hmac_key="local-integrity-key")

    applied = manager.apply_threshold_changes({"cpu_threshold": 74.0}, source="dao")

    assert applied is True
    assert manager.threshold_file.exists()
    assert manager.threshold_hmac_file.exists()
    assert manager.threshold_audit_file.exists()

    records = manager.threshold_audit_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(records) == 1
    event = json.loads(records[0])
    assert event["source"] == "dao"
    assert event["changes"]["cpu_threshold"] == 74.0
    assert event["previous_values"]["cpu_threshold"] == DEFAULT_THRESHOLDS["cpu_threshold"]
    assert len(event["thresholds_sha256"]) == 64


def test_rejects_unknown_or_out_of_bounds_values(tmp_path, monkeypatch):
    manager = _make_manager(tmp_path, monkeypatch)

    assert manager.apply_threshold_changes(
        {"rogue_threshold": 10.0}, source="manual"
    ) is False
    assert manager.apply_threshold_changes(
        {"cpu_threshold": 0.0}, source="manual"
    ) is False
    assert manager.apply_threshold_changes(
        {"latency_threshold": 90000.0}, source="manual"
    ) is False

    assert manager.get_threshold("cpu_threshold") == DEFAULT_THRESHOLDS["cpu_threshold"]
    assert manager.get_threshold("latency_threshold") == DEFAULT_THRESHOLDS["latency_threshold"]


def test_fallback_to_defaults_on_hmac_mismatch(tmp_path, monkeypatch):
    manager = _make_manager(tmp_path, monkeypatch, hmac_key="mesh-hmac-key")
    assert manager.apply_threshold_changes({"cpu_threshold": 72.0}, source="dao") is True

    tampered = json.loads(manager.threshold_file.read_text(encoding="utf-8"))
    tampered["cpu_threshold"] = 40.0
    manager.threshold_file.write_text(json.dumps(tampered, indent=2), encoding="utf-8")

    reloaded = _make_manager(tmp_path, monkeypatch, hmac_key="mesh-hmac-key")
    assert reloaded.get_threshold("cpu_threshold") == DEFAULT_THRESHOLDS["cpu_threshold"]


def test_fallback_to_defaults_when_hmac_missing(tmp_path, monkeypatch):
    manager = _make_manager(tmp_path, monkeypatch, hmac_key="mesh-hmac-key")
    assert manager.apply_threshold_changes({"cpu_threshold": 70.0}, source="dao") is True
    manager.threshold_hmac_file.unlink()

    reloaded = _make_manager(tmp_path, monkeypatch, hmac_key="mesh-hmac-key")
    assert reloaded.get_threshold("cpu_threshold") == DEFAULT_THRESHOLDS["cpu_threshold"]


def test_invalid_dao_proposal_is_not_applied(tmp_path, monkeypatch):
    manager = _make_manager(tmp_path, monkeypatch)
    governance = manager.governance

    proposal = governance.create_proposal(
        title="Inject invalid threshold",
        description="Should be rejected by manager validation",
        actions=[
            {
                "type": "update_mapek_threshold",
                "parameter": "unknown_threshold",
                "value": 0.0,
            }
        ],
    )

    governance.cast_vote(proposal.id, "node-1", governance.VoteType.YES, tokens=100.0)
    governance.cast_vote(proposal.id, "node-2", governance.VoteType.YES, tokens=100.0)
    governance._tally_votes(proposal)

    applied = manager.check_and_apply_dao_proposals()
    assert applied == 0
    assert proposal.state == governance.ProposalState.PASSED
