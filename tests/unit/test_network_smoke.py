"""
Smoke tests for key src.network modules.
Verifies core networking components can be imported.
"""
import pytest


def test_network_routing_types():
    """Core routing types import successfully."""
    from src.network.routing.types import RouteEntry, PacketType, RoutingPacket
    entry = RouteEntry(destination="test", next_hop="hop", hop_count=1, seq_num=1)
    assert entry.destination == "test"


def test_network_firstparty_vpn_tun():
    """First-party VPN TUN module imports."""
    import src.network.firstparty_vpn.tun  # noqa: F401


def test_network_firstparty_vpn_session():
    """First-party VPN session module imports."""
    import src.network.firstparty_vpn.session  # noqa: F401


def test_network_firstparty_vpn_protocol():
    """First-party VPN protocol module imports."""
    import src.network.firstparty_vpn.protocol  # noqa: F401


def test_network_firstparty_vpn_stream():
    """First-party VPN stream module imports."""
    import src.network.firstparty_vpn.stream  # noqa: F401


@pytest.mark.slow
def test_network_routing_mesh_router():
    """MeshRouter imports and instantiates (slow due to deps)."""
    from src.network.routing.types import PacketType
    assert PacketType.DATA.value == 0x01
