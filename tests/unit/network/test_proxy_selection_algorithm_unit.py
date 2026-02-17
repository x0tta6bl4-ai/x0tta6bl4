import os
import builtins
from collections import deque

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import src.network.proxy_selection_algorithm as mod
from src.network.residential_proxy_manager import ProxyEndpoint, ProxyStatus


def _proxy(
    proxy_id: str,
    *,
    region: str = "us-east",
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


def test_proxy_metrics_defaults_and_statistics():
    metrics = mod.ProxyMetrics(proxy_id="p1")
    assert metrics.get_success_rate() == 0.5
    assert metrics.get_avg_latency() == 1000.0
    assert metrics.get_latency_trend() == 0.0
    assert metrics.get_stability_score() == 0.5

    for i in range(20):
        metrics.add_sample(latency_ms=100 + i, success=(i % 2 == 0))
    assert 0.0 <= metrics.get_success_rate() <= 1.0
    assert metrics.get_avg_latency() > 0
    assert isinstance(metrics.get_latency_trend(), float)
    assert 0.0 <= metrics.get_stability_score() <= 1.0


def test_proxy_metrics_latency_trend_with_no_older_window():
    metrics = mod.ProxyMetrics(proxy_id="p1")
    metrics.latency_history = deque([100.0] * 10, maxlen=100)
    # len >= 10, but older window (-20:-10) is empty
    assert metrics.get_latency_trend() == 0.0


def test_proxy_metrics_stability_statistics_error(monkeypatch):
    metrics = mod.ProxyMetrics(proxy_id="p1")
    metrics.latency_history = deque([100.0] * 6, maxlen=100)
    monkeypatch.setattr(
        mod.statistics, "variance", lambda _values: (_ for _ in ()).throw(mod.statistics.StatisticsError("boom"))
    )
    assert metrics.get_stability_score() == 0.5


def test_proxy_metrics_stability_recent_short_edge():
    class _OddHistory:
        def __len__(self):
            return 6

        def __iter__(self):
            return iter([123.0])

    metrics = mod.ProxyMetrics(proxy_id="p1")
    metrics.latency_history = _OddHistory()  # exercise len(recent) < 2 branch
    assert metrics.get_stability_score() == 0.5


def test_domain_profile_post_init_and_blocking_logic():
    profile = mod.DomainProfile(
        domain="example.com",
        preferred_regions=("us",),
        blocked_proxies=["p1"],
        optimal_proxy_scores=[("p1", 0.7)],
    )
    assert isinstance(profile.preferred_regions, list)
    assert isinstance(profile.blocked_proxies, set)
    assert isinstance(profile.optimal_proxy_scores, dict)

    profile.update_score("p2", 0.9)
    assert profile.optimal_proxy_scores["p2"] == 0.9
    profile.mark_blocked("p2")
    assert "p2" in profile.blocked_proxies
    assert "p2" not in profile.optimal_proxy_scores


def test_calculate_proxy_score_domain_status_and_rate_limit_penalties(monkeypatch):
    alg = mod.ProxySelectionAlgorithm()
    proxy = _proxy("p1", region="us-east", cc="US", status=ProxyStatus.HEALTHY)
    metrics = alg._get_metrics(proxy)
    metrics.success_history = deque([1.0] * 20, maxlen=100)
    metrics.latency_history = deque([100.0] * 20, maxlen=100)

    profile = alg._get_domain_profile("a.com")
    profile.update_score(proxy.id, 0.5)
    score = alg.calculate_proxy_score(proxy, domain="a.com", preferred_region="us-east")
    assert score > 0.0

    # Country code fallback branch for geo score
    proxy.region = "eu-west"
    proxy.country_code = "DE"
    cc_score = alg.calculate_proxy_score(proxy, preferred_region="de")
    assert cc_score > 0.0

    profile.mark_blocked(proxy.id)
    assert alg.calculate_proxy_score(proxy, domain="a.com", preferred_region="us-east") == 0.0

    proxy.status = ProxyStatus.DEGRADED
    degraded_score = alg.calculate_proxy_score(proxy, preferred_region="us-east")
    proxy.status = ProxyStatus.UNHEALTHY
    unhealthy_score = alg.calculate_proxy_score(proxy, preferred_region="us-east")
    assert degraded_score > unhealthy_score

    proxy.status = ProxyStatus.BANNED
    assert alg.calculate_proxy_score(proxy, preferred_region="us-east") == 0.0

    proxy.status = ProxyStatus.HEALTHY
    monkeypatch.setattr(proxy, "is_rate_limited", lambda: True)
    limited_score = alg.calculate_proxy_score(proxy, preferred_region="us-east")
    monkeypatch.setattr(proxy, "is_rate_limited", lambda: False)
    normal_score = alg.calculate_proxy_score(proxy, preferred_region="us-east")
    assert limited_score < normal_score


@pytest.mark.asyncio
async def test_select_proxy_guard_clauses_and_strategy_fallback(caplog):
    alg = mod.ProxySelectionAlgorithm(default_strategy=mod.SelectionStrategy.WEIGHTED_SCORE)
    p1 = _proxy("p1", status=ProxyStatus.DEGRADED)
    p2 = _proxy("p2", status=ProxyStatus.BANNED)

    assert await alg.select_proxy([]) is None

    with caplog.at_level("WARNING"):
        no_healthy = await alg.select_proxy([p1, p2], require_healthy=True)
    assert no_healthy is None
    assert "No healthy proxies available" in caplog.text

    p3 = _proxy("p3", status=ProxyStatus.HEALTHY)
    p4 = _proxy("p4", status=ProxyStatus.HEALTHY)
    p3.is_rate_limited = lambda: True
    p4.is_rate_limited = lambda: True
    with caplog.at_level("WARNING"):
        all_limited = await alg.select_proxy([p3, p4], require_healthy=False)
    assert all_limited is None
    assert "All proxies rate limited" in caplog.text

    # Unknown strategy should fallback to weighted path
    chosen = await alg.select_proxy(
        [_proxy("px")], strategy="unknown", require_healthy=False
    )
    assert chosen is not None


@pytest.mark.asyncio
async def test_select_proxy_dispatch_all_strategies(monkeypatch):
    alg = mod.ProxySelectionAlgorithm()
    p = _proxy("p1")

    async def _weighted(_c, _d, _r):
        return _proxy("weighted")

    async def _lowest(_c):
        return _proxy("lowest")

    async def _rr(_c):
        return _proxy("rr")

    async def _random(_c):
        return _proxy("random")

    async def _predictive(_c, _d, _r):
        return _proxy("predictive")

    async def _geo(_c, _r):
        return _proxy("geo")

    monkeypatch.setattr(alg, "_select_weighted", _weighted)
    monkeypatch.setattr(alg, "_select_lowest_latency", _lowest)
    monkeypatch.setattr(alg, "_select_round_robin", _rr)
    monkeypatch.setattr(alg, "_select_random", _random)
    monkeypatch.setattr(alg, "_select_predictive", _predictive)
    monkeypatch.setattr(alg, "_select_geographic", _geo)

    assert (await alg.select_proxy([p], strategy=mod.SelectionStrategy.WEIGHTED_SCORE, require_healthy=False)).id == "weighted"
    assert (await alg.select_proxy([p], strategy=mod.SelectionStrategy.LOWEST_LATENCY, require_healthy=False)).id == "lowest"
    assert (await alg.select_proxy([p], strategy=mod.SelectionStrategy.ROUND_ROBIN, require_healthy=False)).id == "rr"
    assert (await alg.select_proxy([p], strategy=mod.SelectionStrategy.RANDOM, require_healthy=False)).id == "random"
    assert (await alg.select_proxy([p], strategy=mod.SelectionStrategy.PREDICTIVE, require_healthy=False)).id == "predictive"
    assert (await alg.select_proxy([p], strategy=mod.SelectionStrategy.GEOGRAPHIC, require_healthy=False)).id == "geo"


@pytest.mark.asyncio
async def test_weighted_lowest_latency_round_robin_random_and_predictive(monkeypatch):
    alg = mod.ProxySelectionAlgorithm()
    p1 = _proxy("p1")
    p2 = _proxy("p2")
    original_sum = builtins.sum

    # weighted path
    monkeypatch.setattr(mod.random, "uniform", lambda a, b: 0.0)
    chosen_weighted = await alg._select_weighted([p1, p2], domain=None, preferred_region=None)
    assert chosen_weighted.id in {"p1", "p2"}

    # total_score == 0 fallback branch
    monkeypatch.setattr(alg, "calculate_proxy_score", lambda *args, **kwargs: 0.1)
    monkeypatch.setattr(builtins, "sum", lambda _iterable: 0)
    monkeypatch.setattr(mod.random, "choice", lambda seq: seq[0])
    weighted_zero_sum = await alg._select_weighted([p1, p2], domain=None, preferred_region=None)
    assert weighted_zero_sum.id == "p1"

    # loop fallthrough branch returns last item when pick > total_score
    monkeypatch.setattr(builtins, "sum", original_sum)
    monkeypatch.setattr(alg, "calculate_proxy_score", lambda *args, **kwargs: 0.2)
    monkeypatch.setattr(mod.random, "uniform", lambda a, b: b + 1.0)
    weighted_fallthrough = await alg._select_weighted([p1, p2], domain=None, preferred_region=None)
    assert weighted_fallthrough.id == "p2"

    # zero-score weighted -> None
    monkeypatch.setattr(alg, "calculate_proxy_score", lambda *args, **kwargs: 0.0)
    assert await alg._select_weighted([p1], None, None) is None

    # lowest latency path
    m1 = alg._get_metrics(p1)
    m2 = alg._get_metrics(p2)
    m1.latency_history = deque([50.0] * 10, maxlen=100)
    m2.latency_history = deque([150.0] * 10, maxlen=100)
    lowest = await alg._select_lowest_latency([p1, p2])
    assert lowest.id == "p1"

    # round robin path
    rr1 = await alg._select_round_robin([p1, p2])
    rr2 = await alg._select_round_robin([p1, p2])
    assert [rr1.id, rr2.id] == ["p1", "p2"]

    # random path
    monkeypatch.setattr(mod.random, "choice", lambda seq: seq[-1])
    rnd = await alg._select_random([p1, p2])
    assert rnd.id == "p2"

    # predictive path (trend bonus)
    monkeypatch.setattr(alg, "calculate_proxy_score", lambda *args, **kwargs: 0.5)
    m1.latency_history = deque([200.0] * 10 + [100.0] * 10, maxlen=100)  # improving
    m2.latency_history = deque([100.0] * 10 + [200.0] * 10, maxlen=100)  # worsening
    pred = await alg._select_predictive([p1, p2], None, None)
    assert pred.id == "p1"


@pytest.mark.asyncio
async def test_geographic_selection_exact_country_and_fallback(monkeypatch):
    alg = mod.ProxySelectionAlgorithm()
    p_us = _proxy("us", region="us-east", cc="US")
    p_de = _proxy("de", region="eu-west", cc="DE")
    calls = []

    async def _weighted(proxies, domain, preferred_region):
        calls.append(preferred_region)
        return proxies[0]

    monkeypatch.setattr(alg, "_select_weighted", _weighted)

    exact = await alg._select_geographic([p_us, p_de], preferred_region="us-east")
    assert exact.id == "us"

    country = await alg._select_geographic([p_us, p_de], preferred_region="de")
    assert country.id == "de"

    fallback = await alg._select_geographic([p_us, p_de], preferred_region="fr")
    assert fallback.id == "us"

    no_pref = await alg._select_geographic([p_us, p_de], preferred_region=None)
    assert no_pref.id == "us"
    assert calls == ["us-east", "de", "fr", None]


def test_record_result_detect_patterns_and_recommendations():
    alg = mod.ProxySelectionAlgorithm()
    p1 = _proxy("p-low")
    p2 = _proxy("p-good")

    # Build enough history for pattern analysis.
    for _ in range(100):
        alg.record_result(p1, "blocked.example", latency_ms=600.0, success=False)
    for _ in range(20):
        alg.record_result(p2, "ok.example", latency_ms=100.0, success=True)
    alg._selection_history.append(
        {
            "proxy_id": "p-none",
            "domain": None,
            "success": False,
            "latency_ms": 999.0,
            "timestamp": 1.0,
        }
    )

    patterns = alg.detect_patterns()
    assert "domain_preferences" in patterns
    assert "blocked.example" in patterns["domain_preferences"]

    # Trigger domain blocking recommendation.
    profile = alg.domain_profiles["blocked.example"]
    profile.blocked_proxies.update({"a", "b", "c", "d"})

    recs = alg.get_recommendations()
    assert any(r["type"] == "proxy_health" for r in recs)
    assert any(r["type"] == "domain_blocking" for r in recs)


def test_detect_patterns_insufficient_data_and_get_recommendations_empty():
    alg = mod.ProxySelectionAlgorithm()
    assert alg.detect_patterns()["status"] == "insufficient_data"
    assert alg.get_recommendations() == []


@pytest.mark.asyncio
async def test_adaptive_load_balancer_acquire_release_and_empty_error(monkeypatch):
    alg = mod.ProxySelectionAlgorithm()
    lb = mod.AdaptiveLoadBalancer(alg)
    p1 = _proxy("p1")
    p2 = _proxy("p2")

    # Make choice deterministic by forcing scores.
    monkeypatch.setattr(alg, "calculate_proxy_score", lambda proxy, domain=None: 1.0 if proxy.id == "p1" else 0.5)

    selected, token = await lb.acquire_proxy([p1, p2], domain="x.com")
    assert selected.id == "p1"
    assert token.startswith("p1_")
    assert lb.get_load_distribution()["p1"] == 1

    await lb.release_proxy(token)
    assert lb.get_load_distribution()["p1"] == 0

    await lb.release_proxy("missing_proxy_token")
    assert lb.get_load_distribution()["p1"] == 0

    with pytest.raises(RuntimeError, match="No available proxies"):
        await lb.acquire_proxy([], domain="x.com")
