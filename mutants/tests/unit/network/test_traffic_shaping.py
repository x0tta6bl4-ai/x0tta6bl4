"""Unit tests for Traffic Shaping module."""
import pytest
import asyncio
import time
from src.network.obfuscation.traffic_shaping import (
    TrafficShaper,
    TrafficProfile,
    TrafficAnalyzer,
    TRAFFIC_PROFILES,
    ProfileParameters
)


class TestTrafficShaper:
    """Tests for TrafficShaper class."""
    
    def test_shape_packet_adds_padding(self):
        """Test that small packets are padded to profile size."""
        shaper = TrafficShaper(TrafficProfile.VIDEO_STREAMING)
        data = b"hello world"  # 11 bytes
        shaped = shaper.shape_packet(data)
        
        # Should be padded to 1460 (video streaming pad_to_size) + 2 (length prefix)
        assert len(shaped) == 1462
        # First 2 bytes are length
        assert int.from_bytes(shaped[:2], 'big') == 11
    
    def test_unshape_packet_removes_padding(self):
        """Test that padding is correctly removed."""
        shaper = TrafficShaper(TrafficProfile.VIDEO_STREAMING)
        original = b"test data for shaping"
        shaped = shaper.shape_packet(original)
        unshaped = shaper.unshape_packet(shaped)
        
        assert unshaped == original
    
    def test_shape_unshape_roundtrip_all_profiles(self):
        """Test shape/unshape roundtrip for all profiles."""
        data = b"roundtrip test data"
        
        for profile in TrafficProfile:
            shaper = TrafficShaper(profile)
            shaped = shaper.shape_packet(data)
            unshaped = shaper.unshape_packet(shaped)
            assert unshaped == data, f"Roundtrip failed for profile {profile}"
    
    def test_none_profile_no_shaping(self):
        """Test that NONE profile doesn't modify data."""
        shaper = TrafficShaper(TrafficProfile.NONE)
        data = b"unchanged data"
        shaped = shaper.shape_packet(data)
        
        # With NONE profile, data should be unchanged
        assert shaped == data
    
    def test_get_send_delay_returns_positive(self):
        """Test that send delay is within profile range."""
        shaper = TrafficShaper(TrafficProfile.VOICE_CALL)
        params = TRAFFIC_PROFILES[TrafficProfile.VOICE_CALL]
        
        delays = [shaper.get_send_delay() for _ in range(100)]
        
        for delay in delays:
            assert delay >= params.min_interval_ms / 1000.0
            # Allow some tolerance for burst mode
            assert delay <= params.max_interval_ms / 1000.0 + 0.001
    
    def test_get_profile_info(self):
        """Test profile info retrieval."""
        shaper = TrafficShaper(TrafficProfile.GAMING)
        info = shaper.get_profile_info()
        
        assert info["profile"] == "gaming"
        assert info["name"] == "Gaming (Low Latency)"
        assert info["packet_sizes"] == [64, 128, 256]
        assert info["burst_enabled"] is True
    
    def test_voice_call_regular_timing(self):
        """Voice calls have very regular timing (min == max interval)."""
        params = TRAFFIC_PROFILES[TrafficProfile.VOICE_CALL]
        assert params.min_interval_ms == params.max_interval_ms
        assert params.burst_probability == 0.0
    
    def test_file_download_high_burst(self):
        """File downloads have high burst probability."""
        params = TRAFFIC_PROFILES[TrafficProfile.FILE_DOWNLOAD]
        assert params.burst_probability == 0.9
        assert params.burst_size == 20


class TestTrafficAnalyzer:
    """Tests for TrafficAnalyzer class."""
    
    def test_record_packet_tracks_size(self):
        """Test that packet sizes are tracked."""
        analyzer = TrafficAnalyzer()
        analyzer.record_packet(100)
        analyzer.record_packet(200)
        analyzer.record_packet(300)
        
        stats = analyzer.get_statistics()
        assert stats["packets"] == 3
        assert stats["avg_size"] == 200
        assert stats["min_size"] == 100
        assert stats["max_size"] == 300
    
    def test_inter_arrival_time(self):
        """Test inter-arrival time tracking."""
        analyzer = TrafficAnalyzer()
        
        analyzer.record_packet(100)
        time.sleep(0.05)  # 50ms
        analyzer.record_packet(100)
        time.sleep(0.05)
        analyzer.record_packet(100)
        
        stats = analyzer.get_statistics()
        # Should have ~50ms average interval
        assert 30 < stats["avg_interval_ms"] < 70
    
    def test_reset_clears_stats(self):
        """Test that reset clears all statistics."""
        analyzer = TrafficAnalyzer()
        analyzer.record_packet(100)
        analyzer.record_packet(200)
        
        analyzer.reset()
        stats = analyzer.get_statistics()
        
        assert stats["packets"] == 0
    
    def test_empty_stats(self):
        """Test statistics with no packets."""
        analyzer = TrafficAnalyzer()
        stats = analyzer.get_statistics()
        
        assert stats["packets"] == 0


class TestProfileParameters:
    """Tests for profile parameter validity."""
    
    def test_all_profiles_have_valid_params(self):
        """Ensure all profiles have sensible parameters."""
        for profile, params in TRAFFIC_PROFILES.items():
            assert params.min_packet_size > 0
            assert params.max_packet_size >= params.min_packet_size
            assert params.min_interval_ms >= 0
            assert params.max_interval_ms >= params.min_interval_ms
            assert 0 <= params.burst_probability <= 1
            assert params.burst_size >= 1
    
    def test_typical_sizes_within_range(self):
        """Ensure typical sizes are within min/max range."""
        for profile, params in TRAFFIC_PROFILES.items():
            for size in params.typical_packet_sizes:
                assert params.min_packet_size <= size <= params.max_packet_size


@pytest.mark.asyncio
async def test_async_send_shaped():
    """Test async send with shaping."""
    shaper = TrafficShaper(TrafficProfile.GAMING)
    sent_data = []
    
    def capture_send(data: bytes):
        sent_data.append(data)
    
    original = b"game update packet"
    await shaper.send_shaped(original, capture_send)
    
    assert len(sent_data) == 1
    # Verify we can unshape
    unshaped = shaper.unshape_packet(sent_data[0])
    assert unshaped == original
