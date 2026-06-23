import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.coordination.events import EventBus, EventType
import src.network.reputation_scoring as mod


def _clear_reputation_scoring_identity(monkeypatch):
    for name in (
        "REPUTATION_SCORING_SYSTEM_SPIFFE_ID",
        "REPUTATION_SCORING_SYSTEM_DID",
        "REPUTATION_SCORING_SYSTEM_WALLET_ADDRESS",
        "X0TTA6BL4_SERVICE_SPIFFE_ID",
        "X0TTA6BL4_SERVICE_DID",
        "X0TTA6BL4_SERVICE_WALLET_ADDRESS",
        "SERVICE_SPIFFE_ID",
        "SERVICE_DID",
        "SERVICE_WALLET_ADDRESS",
        "SPIFFE_ID",
        "DID",
        "GHOST_WALLET_ADDRESS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_reputation_level_from_score_boundaries():
    assert mod.ReputationLevel.from_score(0.95) == mod.ReputationLevel.EXCELLENT
    assert mod.ReputationLevel.from_score(0.75) == mod.ReputationLevel.GOOD
    assert mod.ReputationLevel.from_score(0.55) == mod.ReputationLevel.FAIR
    assert mod.ReputationLevel.from_score(0.35) == mod.ReputationLevel.POOR
    assert mod.ReputationLevel.from_score(0.10) == mod.ReputationLevel.BAD
    assert mod.ReputationLevel.from_score(1.5) == mod.ReputationLevel.UNKNOWN


def test_domain_reputation_success_failure_risk_and_dict():
    rep = mod.DomainReputation(domain="example.com", score=0.5)
    rep.record_event(mod.ReputationEvent(timestamp=1000.0, success=True, latency_ms=100.0))
    rep.record_event(
        mod.ReputationEvent(
            timestamp=1001.0,
            success=False,
            latency_ms=900.0,
            error_type="blocked",
        )
    )

    assert rep.block_events == 1
    assert rep.failure_streak == 1
    assert rep.success_streak == 0
    assert 0.0 <= rep.get_risk_score() <= 1.0
    assert rep.get_level() in mod.ReputationLevel
    assert isinstance(rep.is_trusted(), bool)
    assert 0.0 <= rep.get_success_rate() <= 1.0
    assert rep.get_avg_latency() > 0

    payload = rep.to_dict()
    assert payload["domain"] == "example.com"
    assert "risk_score" in payload
    assert payload["total_events"] == 2


def test_domain_reputation_edge_defaults_and_event_trimming():
    rep = mod.DomainReputation(domain="trim.example")
    assert rep.get_success_rate() == 0.5
    assert rep.get_avg_latency() == 0.0
    assert rep.get_risk_score() >= 0.0

    for i in range(120):
        rep.record_event(
            mod.ReputationEvent(
                timestamp=2000.0 + i,
                success=(i % 3 != 0),
                latency_ms=50.0 + i,
                error_type="captcha" if i % 10 == 0 else None,
            )
        )
    assert len(rep.events) == 100


def test_proxy_trust_score_updates_and_to_dict():
    trust = mod.ProxyTrustScore(proxy_id="p1")
    for i in range(12):
        trust.record_result(success=(i % 4 != 0), latency_ms=100 + i * 10, error_type="blocked" if i % 6 == 0 else None)

    assert trust.total_requests == 12
    assert trust.failed_requests > 0
    assert trust.successful_requests > 0
    assert trust.blocked_requests >= 1
    assert 0.0 <= trust.reliability_score <= 1.0
    assert 0.0 <= trust.performance_score <= 1.0
    assert 0.0 <= trust.trust_score <= 1.0
    assert isinstance(trust.get_error_breakdown(), dict)

    payload = trust.to_dict()
    assert payload["proxy_id"] == "p1"
    assert payload["total_requests"] == 12
    assert "error_breakdown" in payload


def test_proxy_trust_score_latency_tiers():
    trust = mod.ProxyTrustScore(proxy_id="tier")
    trust.record_result(success=True, latency_ms=50.0)
    assert trust.performance_score == 1.0
    trust.record_result(success=True, latency_ms=250.0)
    assert trust.performance_score >= 0.9
    trust.record_result(success=True, latency_ms=450.0)
    assert trust.performance_score >= 0.7
    trust.record_result(success=True, latency_ms=900.0)
    assert trust.performance_score >= 0.5
    trust.record_result(success=True, latency_ms=2000.0)
    assert 0.0 <= trust.performance_score <= 1.0


def test_proxy_trust_score_trims_latency_history_to_100():
    trust = mod.ProxyTrustScore(proxy_id="trim")
    for i in range(130):
        trust.record_result(success=True, latency_ms=100.0 + i)
    assert len(trust.latency_history) == 100


def test_proxy_trust_score_update_performance_no_history_returns():
    trust = mod.ProxyTrustScore(proxy_id="nohist")
    trust.latency_history = []
    trust.performance_score = 0.42
    trust._update_performance()
    assert trust.performance_score == 0.42


@pytest.mark.asyncio
async def test_reputation_system_record_and_queries():
    system = mod.ReputationScoringSystem()

    await system.record_domain_event("d1.com", success=False, latency_ms=500.0, proxy_id="p1", error_type="blocked")
    await system.record_domain_event("d1.com", success=False, latency_ms=700.0, proxy_id="p2", error_type="captcha")
    await system.record_proxy_result("p1", success=False, latency_ms=700.0, error_type="blocked")
    await system.record_proxy_result("p1", success=True, latency_ms=120.0)

    d1 = system.get_domain_reputation("d1.com")
    p1 = system.get_proxy_trust("p1")
    assert d1 is not None
    assert p1 is not None

    high_risk = system.get_high_risk_domains(threshold=0.0)
    assert any(r.domain == "d1.com" for r in high_risk)

    trusted = system.get_trusted_proxies(min_trust=0.0)
    assert any(t.proxy_id == "p1" for t in trusted)


@pytest.mark.asyncio
async def test_record_domain_event_publishes_redacted_evidence(
    tmp_path, monkeypatch
):
    _clear_reputation_scoring_identity(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    system = mod.ReputationScoringSystem(event_bus=bus)

    await system.record_domain_event(
        "secret.example",
        success=False,
        latency_ms=555.5,
        proxy_id="proxy-secret-1",
        error_type="blocked-secret",
    )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="reputation-scoring-system",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["component"] == "network.reputation_scoring"
    assert payload["operation"] == "record_domain_event"
    assert payload["service_name"] == "reputation-scoring-system"
    assert payload["layer"] == "network_reputation_scoring_observed_state"
    assert payload["status"] == "domain_reputation_recorded"
    assert payload["success"] is True
    assert payload["domain_hash"].startswith("sha256:")
    assert payload["proxy_id_hash"].startswith("sha256:")
    assert payload["event_success"] is False
    assert payload["latency_ms"] == 555.5
    assert payload["error_type_present"] is True
    assert payload["error_type_hash"].startswith("sha256:")
    assert payload["domain_created"] is True
    assert payload["score_after"] <= payload["score_before"]
    assert payload["block_events_after"] == 0
    assert payload["service_identity_present"] == {
        "spiffe_id": False,
        "did": False,
        "wallet_address": False,
    }
    assert "customer traffic delivery" in payload["claim_boundary"]
    text = str(payload)
    assert "secret.example" not in text
    assert "proxy-secret-1" not in text
    assert "blocked-secret" not in text


@pytest.mark.asyncio
async def test_record_proxy_result_publishes_redacted_evidence(
    tmp_path, monkeypatch
):
    _clear_reputation_scoring_identity(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    system = mod.ReputationScoringSystem(event_bus=bus)

    await system.record_proxy_result(
        "proxy-secret-2",
        success=False,
        latency_ms=1500.25,
        error_type="banned",
    )

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="reputation-scoring-system",
    )
    assert len(events) == 1
    payload = events[0].data
    assert payload["operation"] == "record_proxy_result"
    assert payload["status"] == "proxy_trust_recorded"
    assert payload["proxy_id_hash"].startswith("sha256:")
    assert payload["proxy_created"] is True
    assert payload["result_success"] is False
    assert payload["latency_ms"] == 1500.25
    assert payload["error_type_hash"].startswith("sha256:")
    assert payload["scores_before"]["trust"] == 0.5
    assert 0.0 <= payload["scores_after"]["trust"] <= 1.0
    assert payload["request_counts_after"] == {
        "total": 1,
        "successful": 0,
        "failed": 1,
        "blocked": 1,
    }
    text = str(payload)
    assert "proxy-secret-2" not in text
    assert '"banned"' not in text


@pytest.mark.asyncio
async def test_export_stats_publishes_redacted_aggregate_evidence(
    tmp_path, monkeypatch
):
    _clear_reputation_scoring_identity(monkeypatch)
    bus = EventBus(project_root=str(tmp_path))
    system = mod.ReputationScoringSystem(event_bus=bus)

    for _ in range(5):
        await system.record_domain_event(
            "risk-secret.example",
            success=False,
            latency_ms=1000.0,
            proxy_id="proxy-secret-3",
            error_type="blocked-secret",
        )
    for _ in range(12):
        await system.record_proxy_result(
            "bad-proxy-secret",
            success=False,
            latency_ms=1500.0,
            error_type="blocked-secret",
        )

    stats = system.export_stats()

    events = bus.get_event_history(
        event_type=EventType.PIPELINE_STAGE_END,
        source_agent="reputation-scoring-system",
    )
    payload = events[-1].data
    assert stats["domains"]["total"] == 1
    assert payload["operation"] == "export_stats"
    assert payload["status"] == "reputation_stats_exported"
    assert payload["domains_total"] == 1
    assert payload["proxies_total"] == 1
    assert payload["recommendations"]["total"] >= 1
    assert payload["recommendations"]["selector_hashes"][0]["domain_hash"].startswith(
        "sha256:"
    )
    text = str(payload)
    assert "risk-secret.example" not in text
    assert "bad-proxy-secret" not in text
    assert "proxy-secret-3" not in text
    assert "blocked-secret" not in text


@pytest.mark.asyncio
async def test_reputation_system_recommendations_and_export_stats():
    system = mod.ReputationScoringSystem()

    # High risk domain
    for _ in range(5):
        await system.record_domain_event(
            "risk.example", success=False, latency_ms=1000.0, proxy_id="px", error_type="blocked"
        )

    # Untrusted proxy with enough requests
    for _ in range(12):
        await system.record_proxy_result(
            "bad-proxy", success=False, latency_ms=1500.0, error_type="blocked"
        )

    recs = system.get_recommendations()
    assert any(r["type"] == "high_risk_domain" for r in recs)
    assert any(r["type"] == "untrusted_proxy" for r in recs)

    stats = system.export_stats()
    assert stats["domains"]["total"] >= 1
    assert stats["proxies"]["total"] >= 1
    assert "recommendations" in stats
