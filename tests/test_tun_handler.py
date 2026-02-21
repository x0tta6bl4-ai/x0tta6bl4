"""
Tests for TUN Interface Handler
"""

import asyncio
import os
import struct
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.network.tun_handler import (
    TUNInterface,
    IPPacketParser,
    IPPROTO_TCP,
    IPPROTO_UDP,
)


class TestIPPacketParser:
    """Tests for IP packet parser."""
    
    def test_parse_ipv4_packet(self):
        """Test parsing a valid IPv4 packet."""
        # Construct a minimal valid IPv4 header
        # Version 4, IHL 5 (20 bytes), Total length 40
        # Protocol 6 (TCP), TTL 64
        # Src IP: 192.168.1.1, Dst IP: 10.0.0.1
        packet = bytes([
            0x45,  # Version 4, IHL 5
            0x00,  # DSCP/ECN
            0x00, 0x28,  # Total length 40
            0x00, 0x00,  # Identification
            0x00, 0x00,  # Flags, Fragment offset
            0x40,  # TTL 64
            0x06,  # Protocol TCP
            0x00, 0x00,  # Checksum (placeholder)
            192, 168, 1, 1,  # Source IP
            10, 0, 0, 1,  # Destination IP
        ]) + b'\x00' * 20  # Payload (TCP header placeholder)
        
        result = IPPacketParser.parse(packet)
        
        assert result is not None
        assert result["version"] == 4
        assert result["header_len"] == 20
        assert result["total_len"] == 40
        assert result["protocol"] == IPPROTO_TCP
        assert result["ttl"] == 64
        assert result["src_ip"] == "192.168.1.1"
        assert result["dst_ip"] == "10.0.0.1"
    
    def test_parse_udp_packet(self):
        """Test parsing UDP packet."""
        # IPv4 header + UDP header
        ip_header = bytes([
            0x45, 0x00, 0x00, 0x1C,  # Version, IHL, Total length 28
            0x00, 0x00, 0x00, 0x00,  # ID, Flags, Frag offset
            0x40, 0x11,  # TTL, Protocol UDP
            0x00, 0x00,  # Checksum
            192, 168, 1, 1,  # Src IP
            8, 8, 8, 8,  # Dst IP (Google DNS)
        ])
        
        udp_header = bytes([
            0x00, 0x35,  # Src port 53
            0x00, 0x35,  # Dst port 53
            0x00, 0x08,  # Length
            0x00, 0x00,  # Checksum
        ])
        
        packet = ip_header + udp_header
        
        result = IPPacketParser.parse(packet)
        assert result is not None
        assert result["protocol"] == IPPROTO_UDP
        
        udp_info = IPPacketParser.get_udp_info(result["payload"])
        assert udp_info is not None
        assert udp_info["src_port"] == 53
        assert udp_info["dst_port"] == 53
    
    def test_parse_tcp_packet(self):
        """Test parsing TCP packet."""
        # IPv4 header
        ip_header = bytes([
            0x45, 0x00, 0x00, 0x28,  # Version, IHL, Total length 40
            0x00, 0x00, 0x00, 0x00,
            0x40, 0x06,  # TTL, Protocol TCP
            0x00, 0x00,
            192, 168, 1, 100,  # Src IP
            142, 250, 185, 46,  # Dst IP (google.com)
        ])
        
        # TCP header with SYN flag
        tcp_header = bytes([
            0xC0, 0x01,  # Src port 49153
            0x01, 0xBB,  # Dst port 443
            0x00, 0x00, 0x00, 0x01,  # Seq num
            0x00, 0x00, 0x00, 0x00,  # Ack num
            0x50, 0x02,  # Data offset 5, SYN flag
            0xFF, 0xFF,  # Window
            0x00, 0x00,  # Checksum
            0x00, 0x00,  # Urgent pointer
        ])
        
        packet = ip_header + tcp_header
        
        result = IPPacketParser.parse(packet)
        assert result is not None
        assert result["protocol"] == IPPROTO_TCP
        
        tcp_info = IPPacketParser.get_tcp_info(result["payload"])
        assert tcp_info is not None
        assert tcp_info["src_port"] == 49153
        assert tcp_info["dst_port"] == 443
        assert tcp_info["flags"]["syn"] is True
        assert tcp_info["flags"]["ack"] is False
    
    def test_parse_invalid_packet(self):
        """Test parsing invalid packets."""
        # Too short
        assert IPPacketParser.parse(b'\x45\x00') is None
        
        # Empty
        assert IPPacketParser.parse(b'') is None


class TestTUNInterface:
    """Tests for TUN interface handler."""
    
    @pytest.mark.asyncio
    async def test_create_tun_permission_check(self):
        """Test that TUN creation checks permissions."""
        tun = TUNInterface("tun0")
        
        # This will fail if not root, which is expected
        if os.geteuid() != 0:
            result = await tun.create()
            assert result is False
    
    @pytest.mark.asyncio
    async def test_close(self):
        """Test TUN interface close."""
        tun = TUNInterface("tun0")
        tun.fd = 123  # Mock fd
        tun._running = True
        
        with patch.object(os, 'close') as mock_close:
            tun.close()
            mock_close.assert_called_once_with(123)
        
        assert tun.fd is None
        assert not tun._running
    
    def test_context_manager(self):
        """Test context manager protocol."""
        with patch.object(TUNInterface, 'close') as mock_close:
            with TUNInterface("tun0") as tun:
                pass
            mock_close.assert_called_once()


class TestTUNSOCKSBridge:
    """Tests for TUN-SOCKS bridge."""
    
    @pytest.mark.asyncio
    async def test_socks5_connect(self):
        """Test SOCKS5 connection establishment."""
        from src.network.tun_socks_bridge import TUNSOCKSBridge
        
        bridge = TUNSOCKSBridge(
            tun_name="tun0",
            socks_host="127.0.0.1",
            socks_port=1080
        )
        
        # Mock the SOCKS5 connection
        mock_reader = AsyncMock()
        mock_writer = AsyncMock()
        
        with patch('asyncio.open_connection', new_callable=AsyncMock) as mock_open:
            mock_open.return_value = (mock_reader, mock_writer)
            
            # Mock SOCKS5 handshake responses
            mock_reader.read = AsyncMock(side_effect=[
                b'\x05\x00',  # Handshake response
                b'\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00',  # Connect response
            ])
            
            # This would normally work with a real SOCKS5 proxy
            # For now, we just verify the method exists
            assert hasattr(bridge, '_socks5_connect')
    
    def test_stats(self):
        """Test bridge statistics."""
        from src.network.tun_socks_bridge import TUNSOCKSBridge, BridgeStats
        
        bridge = TUNSOCKSBridge()
        
        # Check initial stats
        stats = bridge.get_stats()
        assert stats["packets_read"] == 0
        assert stats["connections_active"] == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])