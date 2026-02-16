import os

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import libx0t.network.reputation_scoring as mod


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
