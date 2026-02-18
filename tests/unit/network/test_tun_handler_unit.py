"""Unit tests for TUN Handler — IPPacketParser and constants."""
import os
import socket
import struct
import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.tun_handler import (
    IPPacketParser,
    IPPROTO_TCP,
    IPPROTO_UDP,
    IPPROTO_ICMP,
    IPPROTO_ICMPV6,
    IFF_TUN,
    IFF_TAP,
    IFF_NO_PI,
    TUNSETIFF,
    TUNInterface,
)


def _build_ip_packet(
    src="10.0.0.1", dst="10.0.0.2", protocol=6, ttl=64, payload=b""
):
    """Build a minimal IPv4 packet for testing."""
    version_ihl = (4 << 4) | 5  # IPv4, 20-byte header
    total_len = 20 + len(payload)
    header = bytearray(20)
    header[0] = version_ihl
    header[2] = (total_len >> 8) & 0xFF
    header[3] = total_len & 0xFF
    header[8] = ttl
    header[9] = protocol
    header[12:16] = socket.inet_aton(src)
    header[16:20] = socket.inet_aton(dst)
    return bytes(header) + payload


def _build_tcp_payload(
    src_port=12345, dst_port=80, seq=1000, ack=0, flags=0x02
):
    """Build a minimal TCP header."""
    hdr = bytearray(20)
    hdr[0] = (src_port >> 8) & 0xFF
    hdr[1] = src_port & 0xFF
    hdr[2] = (dst_port >> 8) & 0xFF
    hdr[3] = dst_port & 0xFF
    hdr[4:8] = seq.to_bytes(4, "big")
    hdr[8:12] = ack.to_bytes(4, "big")
    hdr[12] = 0x50  # data offset = 5 words
    hdr[13] = flags
    return bytes(hdr)


def _build_udp_payload(src_port=5000, dst_port=53, data=b""):
    """Build a minimal UDP header."""
    length = 8 + len(data)
    hdr = bytearray(8)
    hdr[0] = (src_port >> 8) & 0xFF
    hdr[1] = src_port & 0xFF
    hdr[2] = (dst_port >> 8) & 0xFF
    hdr[3] = dst_port & 0xFF
    hdr[4] = (length >> 8) & 0xFF
    hdr[5] = length & 0xFF
    return bytes(hdr) + data


class TestProtocolConstants:
    def test_tcp(self):
        assert IPPROTO_TCP == 6

    def test_udp(self):
        assert IPPROTO_UDP == 17

    def test_icmp(self):
        assert IPPROTO_ICMP == 1

    def test_icmpv6(self):
        assert IPPROTO_ICMPV6 == 58

    def test_tun_flags(self):
        assert IFF_TUN == 0x0001
        assert IFF_TAP == 0x0002
        assert IFF_NO_PI == 0x1000


class TestIPPacketParser:
    def test_parse_valid_packet(self):
        pkt = _build_ip_packet("192.168.1.1", "10.0.0.1", protocol=6, ttl=128)
        result = IPPacketParser.parse(pkt)
        assert result is not None
        assert result["version"] == 4
        assert result["header_len"] == 20
        assert result["protocol"] == 6
        assert result["ttl"] == 128
        assert result["src_ip"] == "192.168.1.1"
        assert result["dst_ip"] == "10.0.0.1"
        assert result["total_len"] == 20

    def test_parse_with_payload(self):
        payload = b"\x00" * 100
        pkt = _build_ip_packet(payload=payload)
        result = IPPacketParser.parse(pkt)
        assert result is not None
        assert len(result["payload"]) == 100
        assert result["total_len"] == 120

    def test_parse_too_short(self):
        assert IPPacketParser.parse(b"\x45\x00") is None

    def test_parse_empty(self):
        assert IPPacketParser.parse(b"") is None

    def test_parse_raw_preserved(self):
        pkt = _build_ip_packet()
        result = IPPacketParser.parse(pkt)
        assert result["raw"] == pkt


class TestTCPParsing:
    def test_parse_syn(self):
        tcp = _build_tcp_payload(src_port=54321, dst_port=443, seq=999, flags=0x02)
        result = IPPacketParser.get_tcp_info(tcp)
        assert result is not None
        assert result["src_port"] == 54321
        assert result["dst_port"] == 443
        assert result["seq_num"] == 999
        assert result["flags"]["syn"] is True
        assert result["flags"]["ack"] is False

    def test_parse_syn_ack(self):
        tcp = _build_tcp_payload(flags=0x12)  # SYN+ACK
        result = IPPacketParser.get_tcp_info(tcp)
        assert result["flags"]["syn"] is True
        assert result["flags"]["ack"] is True

    def test_parse_fin(self):
        tcp = _build_tcp_payload(flags=0x01)
        result = IPPacketParser.get_tcp_info(tcp)
        assert result["flags"]["fin"] is True

    def test_parse_rst(self):
        tcp = _build_tcp_payload(flags=0x04)
        result = IPPacketParser.get_tcp_info(tcp)
        assert result["flags"]["rst"] is True

    def test_too_short(self):
        assert IPPacketParser.get_tcp_info(b"\x00" * 10) is None


class TestUDPParsing:
    def test_parse_udp(self):
        udp = _build_udp_payload(src_port=5353, dst_port=53, data=b"dns-query")
        result = IPPacketParser.get_udp_info(udp)
        assert result is not None
        assert result["src_port"] == 5353
        assert result["dst_port"] == 53
        assert result["length"] == 17  # 8 + len("dns-query")
        assert result["payload"] == b"dns-query"

    def test_too_short(self):
        assert IPPacketParser.get_udp_info(b"\x00" * 4) is None


class TestTUNInterface:
    def test_init_defaults(self):
        tun = TUNInterface()
        assert tun.name == "tun0"
        assert tun.mtu == 1500

    def test_init_custom(self):
        tun = TUNInterface(name="tun1", mtu=9000, persist=True)
        assert tun.name == "tun1"
        assert tun.mtu == 9000

    def test_context_manager(self):
        tun = TUNInterface()
        # __enter__ returns self
        assert tun.__enter__() is tun
        # __exit__ should not raise
        tun.__exit__(None, None, None)
