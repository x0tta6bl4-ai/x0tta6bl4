from __future__ import annotations

import sys


def test_network_package_lazily_exports_firstparty_vpn() -> None:
    sys.modules.pop("src.network.firstparty_vpn", None)

    import src.network as network

    network.__dict__.pop("firstparty_vpn", None)

    assert "firstparty_vpn" in network.__all__
    assert "firstparty_vpn" in dir(network)
    assert "src.network.firstparty_vpn" not in sys.modules

    firstparty_vpn = network.firstparty_vpn

    assert firstparty_vpn.__name__ == "src.network.firstparty_vpn"
    assert sys.modules["src.network.firstparty_vpn"] is firstparty_vpn
