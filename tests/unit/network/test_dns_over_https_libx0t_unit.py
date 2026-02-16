"""Unit tests for DNS-over-HTTPS (DoH) resolver.

Tests cover DoHResolver initialization, server rotation, domain classification,
system DNS fallback, DoH resolution, convenience methods, reverse lookup,
session management, and stats reporting.
"""

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

try:
    from libx0t.network.dns_over_https import (DOH_SERVERS, DoHResolver,
                                            get_doh_resolver)
except ImportError:
    pytest.skip("dns_over_https module not available", allow_module_level=True)


# ---------------------------------------------------------------------------
# Helper: build a mock aiohttp session + response for DoH HTTP tests
# ---------------------------------------------------------------------------


def _make_mock_session(status=200, json_data=None, json_side_effect=None):
    """Create a mock aiohttp ClientSession whose .get returns a context manager.

    Args:
        status: HTTP status code of the response.
        json_data: dict returned by response.json().
        json_side_effect: exception raised by response.json() (overrides json_data).

    Returns:
        (mock_session, mock_response) tuple.
    """
    mock_response = AsyncMock()
    mock_response.status = status
    if json_side_effect is not None:
        mock_response.json = AsyncMock(side_effect=json_side_effect)
        mock_response.text = AsyncMock(return_value="bad data")
    else:
        mock_response.json = AsyncMock(return_value=json_data or {})
    mock_response.text = (
        mock_response.text
        if hasattr(mock_response, "text") and mock_response.text._mock_name != "text"
        else AsyncMock(return_value="")
    )

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=mock_response)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=mock_cm)
    mock_session.closed = False
    mock_session.close = AsyncMock()

    return mock_session, mock_response


# ===========================================================================
# TestDoHResolverInit
# ===========================================================================


class TestDoHResolverInit:
    """Tests for DoHResolver.__init__."""

    def test_default_servers(self):
        """Default servers should be DOH_SERVERS (5 entries)."""
        resolver = DoHResolver()
        assert resolver.servers is DOH_SERVERS
        assert len(resolver.servers) == 5

    def test_custom_servers(self):
        """Passing a custom list should override default servers."""
        custom = [{"name": "Custom", "url": "https://custom.dns/query", "params": {}}]
        resolver = DoHResolver(servers=custom)
        assert resolver.servers is custom
        assert len(resolver.servers) == 1
        assert resolver.servers[0]["name"] == "Custom"

    def test_initial_state(self):
        """Index starts at 0 and session is None."""
        resolver = DoHResolver()
        assert resolver.current_server_index == 0
        assert resolver.session is None


# ===========================================================================
# TestRotateServer
# ===========================================================================


class TestRotateServer:
    """Tests for DoHResolver._rotate_server."""

    def test_increments_index(self):
        """Rotation should advance the index by 1."""
        resolver = DoHResolver()
        assert resolver.current_server_index == 0
        resolver._rotate_server()
        assert resolver.current_server_index == 1

    def test_wraps_around(self):
        """Index should wrap to 0 after reaching the last server."""
        resolver = DoHResolver()
        resolver.current_server_index = len(resolver.servers) - 1
        resolver._rotate_server()
        assert resolver.current_server_index == 0

    def test_multiple_rotations(self):
        """Rotating through all servers should cycle back to the start."""
        resolver = DoHResolver()
        total = len(resolver.servers)
        for _ in range(total):
            resolver._rotate_server()
        assert resolver.current_server_index == 0


# ===========================================================================
# TestShouldUseSystemDns
# ===========================================================================


class TestShouldUseSystemDns:
    """Tests for DoHResolver._should_use_system_dns."""

    def test_googleapis(self):
        resolver = DoHResolver()
        assert resolver._should_use_system_dns("apis.googleapis.com") is True

    def test_youtube(self):
        resolver = DoHResolver()
        assert resolver._should_use_system_dns("youtube.com") is True

    def test_spotify(self):
        resolver = DoHResolver()
        assert resolver._should_use_system_dns("spotify.com") is True

    def test_non_google_domain(self):
        resolver = DoHResolver()
        assert resolver._should_use_system_dns("example.com") is False

    def test_similar_but_not_matching(self):
        """A domain that contains 'google' but does not end with a listed suffix."""
        resolver = DoHResolver()
        assert resolver._should_use_system_dns("notgoogle.org") is False


# ===========================================================================
# TestSystemDnsResolve
# ===========================================================================


class TestSystemDnsResolve:
    """Tests for DoHResolver._system_dns_resolve (mocks socket.getaddrinfo)."""

    @pytest.mark.asyncio
    async def test_a_record(self):
        """A record resolution should return IPv4 addresses."""
        resolver = DoHResolver()
        fake_addrinfo = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
            (socket.AF_INET, socket.SOCK_DGRAM, 17, "", ("93.184.216.34", 0)),
        ]
        with patch("socket.getaddrinfo", return_value=fake_addrinfo):
            result = await resolver._system_dns_resolve("example.com", "A")
        assert result == ["93.184.216.34"]

    @pytest.mark.asyncio
    async def test_aaaa_record(self):
        """AAAA record resolution should return IPv6 addresses."""
        resolver = DoHResolver()
        fake_addrinfo = [
            (
                socket.AF_INET6,
                socket.SOCK_STREAM,
                6,
                "",
                ("2606:2800:220:1:248:1893:25c8:1946", 0, 0, 0),
            ),
        ]
        with patch("socket.getaddrinfo", return_value=fake_addrinfo):
            result = await resolver._system_dns_resolve("example.com", "AAAA")
        assert result == ["2606:2800:220:1:248:1893:25c8:1946"]

    @pytest.mark.asyncio
    async def test_exception_returns_empty(self):
        """When getaddrinfo raises, an empty list should be returned."""
        resolver = DoHResolver()
        with patch("socket.getaddrinfo", side_effect=socket.gaierror("DNS failed")):
            result = await resolver._system_dns_resolve("nonexistent.example.com", "A")
        assert result == []


# ===========================================================================
# TestResolve
# ===========================================================================


class TestResolve:
    """Tests for DoHResolver.resolve (the main async resolution method)."""

    @pytest.mark.asyncio
    async def test_google_domain_delegates_to_system_dns(self):
        """Google Cloud domains should be resolved via _system_dns_resolve."""
        resolver = DoHResolver()
        with patch.object(
            resolver,
            "_system_dns_resolve",
            new_callable=AsyncMock,
            return_value=["142.250.80.46"],
        ) as mock_sys:
            result = await resolver.resolve("apis.googleapis.com", "A")
        mock_sys.assert_awaited_once_with("apis.googleapis.com", "A")
        assert result == ["142.250.80.46"]

    @pytest.mark.asyncio
    async def test_successful_a_record(self):
        """Successful A record resolution via DoH."""
        resolver = DoHResolver()
        json_data = {
            "Status": 0,
            "Answer": [
                {"name": "example.com", "type": 1, "data": "93.184.216.34"},
            ],
        }
        mock_session, _ = _make_mock_session(status=200, json_data=json_data)
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("example.com", "A")

        assert result == ["93.184.216.34"]

    @pytest.mark.asyncio
    async def test_successful_aaaa_record(self):
        """Successful AAAA record resolution via DoH."""
        resolver = DoHResolver()
        json_data = {
            "Status": 0,
            "Answer": [
                {
                    "name": "example.com",
                    "type": 28,
                    "data": "2606:2800:220:1:248:1893:25c8:1946",
                },
            ],
        }
        mock_session, _ = _make_mock_session(status=200, json_data=json_data)
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("example.com", "AAAA")

        assert result == ["2606:2800:220:1:248:1893:25c8:1946"]

    @pytest.mark.asyncio
    async def test_dns_error_status_returns_empty(self):
        """Non-zero DNS Status (e.g., NXDOMAIN) should yield an empty list."""
        resolver = DoHResolver(
            servers=[
                {"name": "Only", "url": "https://only.dns/query", "params": {}},
            ]
        )
        json_data = {"Status": 3}  # NXDOMAIN
        mock_session, _ = _make_mock_session(status=200, json_data=json_data)
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("nonexistent.example.com", "A")

        assert result == []

    @pytest.mark.asyncio
    async def test_http_error_rotates_and_returns_empty(self):
        """HTTP non-200 should trigger rotation; if all fail, return empty."""
        single_server = [
            {"name": "Fail", "url": "https://fail.dns/query", "params": {}}
        ]
        resolver = DoHResolver(servers=single_server)
        mock_session, _ = _make_mock_session(status=503)
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("example.com", "A")

        assert result == []
        # Server should have been rotated (wraps around on single server)
        assert resolver.current_server_index == 0

    @pytest.mark.asyncio
    async def test_json_parse_error_rotates(self):
        """JSON decode failure should rotate to next server."""
        two_servers = [
            {"name": "Bad", "url": "https://bad.dns/query", "params": {}},
            {"name": "Good", "url": "https://good.dns/query", "params": {}},
        ]
        resolver = DoHResolver(servers=two_servers)

        # First call: JSON parse error; second call: success
        bad_response = AsyncMock()
        bad_response.status = 200
        bad_response.json = AsyncMock(side_effect=ValueError("bad json"))
        bad_response.text = AsyncMock(return_value="not json")

        good_json = {
            "Status": 0,
            "Answer": [{"name": "example.com", "type": 1, "data": "1.2.3.4"}],
        }
        good_response = AsyncMock()
        good_response.status = 200
        good_response.json = AsyncMock(return_value=good_json)

        bad_cm = AsyncMock()
        bad_cm.__aenter__ = AsyncMock(return_value=bad_response)
        bad_cm.__aexit__ = AsyncMock(return_value=False)

        good_cm = AsyncMock()
        good_cm.__aenter__ = AsyncMock(return_value=good_response)
        good_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=[bad_cm, good_cm])
        mock_session.closed = False
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("example.com", "A")

        assert result == ["1.2.3.4"]

    @pytest.mark.asyncio
    async def test_timeout_rotates(self):
        """asyncio.TimeoutError should rotate to the next server."""
        two_servers = [
            {"name": "Slow", "url": "https://slow.dns/query", "params": {}},
            {"name": "Fast", "url": "https://fast.dns/query", "params": {}},
        ]
        resolver = DoHResolver(servers=two_servers)

        # First call times out, second succeeds
        good_json = {
            "Status": 0,
            "Answer": [{"name": "example.com", "type": 1, "data": "5.6.7.8"}],
        }
        good_response = AsyncMock()
        good_response.status = 200
        good_response.json = AsyncMock(return_value=good_json)

        timeout_cm = MagicMock()
        timeout_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        timeout_cm.__aexit__ = AsyncMock(return_value=False)

        good_cm = AsyncMock()
        good_cm.__aenter__ = AsyncMock(return_value=good_response)
        good_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        mock_session.get = MagicMock(side_effect=[timeout_cm, good_cm])
        mock_session.closed = False
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("example.com", "A")

        assert result == ["5.6.7.8"]

    @pytest.mark.asyncio
    async def test_all_servers_fail_returns_empty(self):
        """When every server fails, resolve should return an empty list."""
        servers = [
            {"name": "S1", "url": "https://s1.dns/q", "params": {}},
            {"name": "S2", "url": "https://s2.dns/q", "params": {}},
        ]
        resolver = DoHResolver(servers=servers)

        timeout_cm = MagicMock()
        timeout_cm.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError())
        timeout_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = AsyncMock()
        # Both attempts time out
        mock_session.get = MagicMock(return_value=timeout_cm)
        mock_session.closed = False
        resolver.session = mock_session

        with patch.object(resolver, "_init_session", new_callable=AsyncMock):
            result = await resolver.resolve("example.com", "A")

        assert result == []


# ===========================================================================
# TestConvenienceMethods
# ===========================================================================


class TestConvenienceMethods:
    """Tests for resolve_a, resolve_aaaa, resolve_mx, resolve_txt."""

    @pytest.mark.asyncio
    async def test_resolve_a(self):
        """resolve_a should delegate to resolve with record_type='A'."""
        resolver = DoHResolver()
        with patch.object(
            resolver, "resolve", new_callable=AsyncMock, return_value=["1.1.1.1"]
        ) as mock_resolve:
            result = await resolver.resolve_a("example.com")
        mock_resolve.assert_awaited_once_with("example.com", "A")
        assert result == ["1.1.1.1"]

    @pytest.mark.asyncio
    async def test_resolve_aaaa(self):
        """resolve_aaaa should delegate to resolve with record_type='AAAA'."""
        resolver = DoHResolver()
        with patch.object(
            resolver, "resolve", new_callable=AsyncMock, return_value=["::1"]
        ) as mock_resolve:
            result = await resolver.resolve_aaaa("example.com")
        mock_resolve.assert_awaited_once_with("example.com", "AAAA")
        assert result == ["::1"]


# ===========================================================================
# TestReverseLookup
# ===========================================================================


class TestReverseLookup:
    """Tests for DoHResolver.reverse_lookup."""

    @pytest.mark.asyncio
    async def test_ipv4_reverse(self):
        """IPv4 address should be converted to in-addr.arpa and resolved as PTR."""
        resolver = DoHResolver()
        with patch.object(
            resolver, "resolve", new_callable=AsyncMock, return_value=["dns.google"]
        ) as mock_resolve:
            result = await resolver.reverse_lookup("1.2.3.4")
        mock_resolve.assert_awaited_once_with("4.3.2.1.in-addr.arpa", "PTR")
        assert result == ["dns.google"]

    @pytest.mark.asyncio
    async def test_ipv6_reverse(self):
        """IPv6 address should use ipaddress.IPv6Address.reverse_pointer."""
        import ipaddress

        resolver = DoHResolver()
        test_ip = "2001:db8::1"
        expected_arpa = ipaddress.IPv6Address(test_ip).reverse_pointer

        with patch.object(
            resolver,
            "resolve",
            new_callable=AsyncMock,
            return_value=["host.example.com"],
        ) as mock_resolve:
            result = await resolver.reverse_lookup(test_ip)
        mock_resolve.assert_awaited_once_with(expected_arpa, "PTR")
        assert result == ["host.example.com"]


# ===========================================================================
# TestClose
# ===========================================================================


class TestClose:
    """Tests for DoHResolver.close."""

    @pytest.mark.asyncio
    async def test_close_open_session(self):
        """Closing the resolver should close its aiohttp session."""
        resolver = DoHResolver()
        mock_session = AsyncMock()
        mock_session.closed = False
        mock_session.close = AsyncMock()
        resolver.session = mock_session

        await resolver.close()

        mock_session.close.assert_awaited_once()


# ===========================================================================
# TestGetStats
# ===========================================================================


class TestGetStats:
    """Tests for DoHResolver.get_stats."""

    def test_returns_server_info(self):
        """Stats should include server_count and current_server details."""
        resolver = DoHResolver()
        stats = resolver.get_stats()
        assert stats["server_count"] == 5
        assert stats["current_server"]["name"] == "Cloudflare"
        assert stats["current_server"]["url"] == "https://cloudflare-dns.com/dns-query"


# ===========================================================================
# TestAdditionalCoverage
# ===========================================================================


class TestAdditionalCoverage:
    """Extra direct libx0t coverage for helper paths and singleton."""

    @pytest.mark.asyncio
    async def test_init_session_creates_and_recreates_when_closed(self):
        resolver = DoHResolver()

        first = MagicMock()
        first.closed = False
        second = MagicMock()
        second.closed = False

        with patch(
            "libx0t.network.dns_over_https.aiohttp.ClientSession",
            side_effect=[first, second],
        ):
            await resolver._init_session()
            assert resolver.session is first

            resolver.session.closed = True
            await resolver._init_session()
            assert resolver.session is second

    @pytest.mark.asyncio
    async def test_resolve_mx_and_txt_delegate(self):
        resolver = DoHResolver()

        with patch.object(
            resolver, "resolve", new_callable=AsyncMock, return_value=["mx.example"]
        ) as mock_resolve_mx:
            result_mx = await resolver.resolve_mx("example.com")
        mock_resolve_mx.assert_awaited_once_with("example.com", "MX")
        assert result_mx == ["mx.example"]

        with patch.object(
            resolver, "resolve", new_callable=AsyncMock, return_value=["v=spf1"]
        ) as mock_resolve_txt:
            result_txt = await resolver.resolve_txt("example.com")
        mock_resolve_txt.assert_awaited_once_with("example.com", "TXT")
        assert result_txt == ["v=spf1"]

    @pytest.mark.asyncio
    async def test_get_doh_resolver_singleton(self):
        import importlib

        doh_module = importlib.import_module("libx0t.network.dns_over_https")
        doh_module._global_resolver = None
        first = await get_doh_resolver()
        second = await get_doh_resolver()
        assert first is second
