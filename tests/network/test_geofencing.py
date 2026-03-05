"""Smoke tests for GeoFencer."""
from src.network.geofencing import GeoFencer


class TestGeoFencer:
    def test_no_restrictions_allows_all(self):
        gf = GeoFencer()
        assert gf.validate_node("8.8.8.8") is True
        assert gf.is_transit_allowed("8.8.8.8", "1.1.1.1") is True

    def test_restricted_country_blocks_node(self):
        gf = GeoFencer(restricted_countries={"RU"})
        # 95.161.224.1 resolves to RU in mock cache
        assert gf.validate_node("95.161.224.1") is False

    def test_restricted_country_allows_other(self):
        gf = GeoFencer(restricted_countries={"RU"})
        assert gf.validate_node("8.8.8.8") is True  # US — not restricted

    def test_transit_blocked_when_endpoint_restricted(self):
        gf = GeoFencer(restricted_countries={"RU"})
        assert gf.is_transit_allowed("8.8.8.8", "95.161.224.1") is False

    def test_transit_allowed_between_unrestricted(self):
        gf = GeoFencer(restricted_countries={"RU"})
        assert gf.is_transit_allowed("8.8.8.8", "1.1.1.1") is True

    def test_set_restrictions_updates_state(self):
        gf = GeoFencer()
        gf.set_restrictions(["UA"])
        assert gf.validate_node("89.125.1.107") is False  # UA

    def test_unknown_ip_not_blocked_by_default(self):
        gf = GeoFencer(restricted_countries={"RU"})
        assert gf.validate_node("10.0.0.1") is True  # UNKNOWN — not in restricted

    def test_get_country_returns_known(self):
        gf = GeoFencer()
        assert gf.get_country("8.8.8.8") == "US"
        assert gf.get_country("99.99.99.99") == "UNKNOWN"
