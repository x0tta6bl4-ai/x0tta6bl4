import pytest

from src.network.proxy_selection_algorithm import (AdaptiveLoadBalancer,
                                                   ProxySelectionAlgorithm)
from src.network.residential_proxy_manager import ProxyEndpoint


@pytest.mark.asyncio
async def test_acquire_proxy_uses_hex_token_suffix():
    algorithm = ProxySelectionAlgorithm()
    balancer = AdaptiveLoadBalancer(algorithm)
    proxy = ProxyEndpoint(id="proxy-1", host="127.0.0.1", port=8080)

    selected, token = await balancer.acquire_proxy([proxy])

    assert selected.id == "proxy-1"
    assert token.startswith("proxy-1_")
    suffix = token.split("_", 1)[1]
    assert len(suffix) == 16
    int(suffix, 16)


@pytest.mark.asyncio
async def test_acquire_proxy_tokens_are_unique():
    algorithm = ProxySelectionAlgorithm()
    balancer = AdaptiveLoadBalancer(algorithm)
    proxy = ProxyEndpoint(id="proxy-1", host="127.0.0.1", port=8080)

    _, token1 = await balancer.acquire_proxy([proxy])
    _, token2 = await balancer.acquire_proxy([proxy])

    assert token1 != token2
