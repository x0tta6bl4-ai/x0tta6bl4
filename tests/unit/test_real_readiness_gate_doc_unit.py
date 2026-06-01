from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "docs/05-operations/REAL_READINESS_GATE.md"


def _doc_text() -> str:
    return DOC.read_text(encoding="utf-8")


def test_real_readiness_gate_safe_actuator_counts_match_verifiers():
    text = _doc_text()

    assert "parse-error-free" in text
    assert "`20/20`" in text
    assert "`63/63`" in text
    assert "`18 EventBus + 4 ops" in text
    assert "result-metadata` local cases" in text

    stale_markers = (
        "`14/14`",
        "`13/13`",
        "still incremental",
    )
    for marker in stale_markers:
        assert marker not in text


def test_real_readiness_gate_names_current_runtime_retention_surfaces():
    text = _doc_text()
    compact_text = " ".join(text.split())

    required_surfaces = (
        "SPIRE",
        "TokenBridge",
        "DAO executor release-script",
        "DAO proposal Helm upgrade",
        "DAO governance dispatch",
        "GovernanceContract chain-write",
        "Ghost L3",
        "eBPF",
        "MaaS governance",
        "PQC rotator",
        "MPTCP",
        "MeshActionEnforcer",
        "self-healing MAPE-K",
        "PBFT",
        "Swarm MAPE-K",
        "canary deployment",
        "multi-cloud deployment",
    )
    for surface in required_surfaces:
        assert surface in compact_text


def test_real_readiness_gate_followup_lists_maas_heal_api_probe_verifier():
    text = _doc_text()

    assert "verify_maas_heal_api_post_action_dataplane_probe.py" in text
    assert "--require-ready" in text
    assert "traffic/customer/external/SLO/production claims false" in text
