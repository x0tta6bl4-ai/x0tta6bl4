import os
import time

import pytest

from src.network.proxy_selection_algorithm import (AdaptiveLoadBalancer,
                                                   DomainProfile,
                                                   ProxySelectionAlgorithm,
                                                   SelectionStrategy)
from src.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")


def _proxy(
    proxy_id: str,
    region: str = "us",
    cc: str = "US",
    status: ProxyStatus = ProxyStatus.HEALTHY,
):
    return ProxyEndpoint(
        id=proxy_id,
        host="127.0.0.1",
        port=8080,
        region=region,
        country_code=cc,
        status=status,
    )


def test_domain_profile_post_init_and_updates():
    p = DomainProfile(
        domain="example.com",
        preferred_regions=("us",),
        blocked_proxies=["a"],
        optimal_proxy_scores=[("a", 0.5)],
    )
    assert isinstance(p.preferred_regions, list)
    assert isinstance(p.blocked_proxies, set)
    assert isinstance(p.optimal_proxy_scores, dict)
    p.update_score("x", 0.8)
    assert p.optimal_proxy_scores["x"] == 0.8
    p.mark_blocked("x")
    assert "x" in p.blocked_proxies
    assert "x" not in p.optimal_proxy_scores


@pytest.mark.asyncio
async def test_select_proxy_strategy_paths():
    alg = ProxySelectionAlgorithm(default_strategy=SelectionStrategy.RANDOM)
    p1 = _proxy("p1", "us-east")
    p2 = _proxy("p2", "eu-west", "DE")
    out = await alg.select_proxy(
        [p1, p2], strategy=SelectionStrategy.GEOGRAPHIC, preferred_region="US"
    )
    assert out is not None
    assert out.id in {"p1", "p2"}
    out2 = await alg.select_proxy([p1], strategy=SelectionStrategy.ROUND_ROBIN)
    assert out2.id == "p1"


def test_record_result_detect_patterns_and_recommendations():
    alg = ProxySelectionAlgorithm()
    p = _proxy("p-low")
    for _ in range(120):
        alg.record_result(p, "blocked.example", latency_ms=500, success=False)
    patterns = alg.detect_patterns()
    assert "domain_preferences" in patterns
    # Trigger domain-blocking recommendation (threshold > 3 blocked proxies per domain)
    profile = alg.domain_profiles["blocked.example"]
    profile.blocked_proxies.update({"p1", "p2", "p3", "p4"})
    recs = alg.get_recommendations()
    assert any(r["type"] == "proxy_health" for r in recs)
    assert any(r["type"] == "domain_blocking" for r in recs)


def test_detect_patterns_insufficient_data():
    alg = ProxySelectionAlgorithm()
    assert alg.detect_patterns()["status"] == "insufficient_data"


@pytest.mark.asyncio
async def test_adaptive_load_balancer_acquire_release():
    alg = ProxySelectionAlgorithm()
    lb = AdaptiveLoadBalancer(alg)
    p1 = _proxy("p1")
    p2 = _proxy("p2")
    selected, token = await lb.acquire_proxy([p1, p2], domain="x.com")
    assert token.startswith(f"{selected.id}_")
    before = lb.get_load_distribution()[selected.id]
    await lb.release_proxy(token)
    after = lb.get_load_distribution()[selected.id]
    assert after == max(0, before - 1)
