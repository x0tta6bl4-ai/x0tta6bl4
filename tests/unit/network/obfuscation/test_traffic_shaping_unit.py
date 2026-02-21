"""Unit tests for src.network.obfuscation.traffic_shaping module."""

import random
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.network.obfuscation.traffic_shaping import (TRAFFIC_PROFILES,
                                                     ProfileParameters,
                                                     TrafficAnalyzer,
                                                     TrafficProfile,
                                                     TrafficShaper)

# ---------------------------------------------------------------------------
# TrafficProfile enum
# ---------------------------------------------------------------------------


class TestTrafficProfile:
    """Tests for the TrafficProfile enum."""

    def test_all_six_values_exist(self):
        expected = {
            "NONE",
            "VIDEO_STREAMING",
            "VOICE_CALL",
            "WEB_BROWSING",
            "FILE_DOWNLOAD",
            "GAMING",
        }
        actual = {member.name for member in TrafficProfile}
        assert actual == expected

    def test_enum_string_values(self):
        assert TrafficProfile.NONE.value == "none"
        assert TrafficProfile.VIDEO_STREAMING.value == "video_streaming"
        assert TrafficProfile.VOICE_CALL.value == "voice_call"
        assert TrafficProfile.WEB_BROWSING.value == "web_browsing"
        assert TrafficProfile.FILE_DOWNLOAD.value == "file_download"
        assert TrafficProfile.GAMING.value == "gaming"


# ---------------------------------------------------------------------------
# TRAFFIC_PROFILES dict
# ---------------------------------------------------------------------------


class TestTrafficProfiles:
    """Tests for the TRAFFIC_PROFILES constant."""

    def test_has_entries_for_all_non_none_profiles(self):
        non_none = [p for p in TrafficProfile if p != TrafficProfile.NONE]
        for profile in non_none:
            assert profile in TRAFFIC_PROFILES, f"Missing profile: {profile}"

    def test_none_profile_not_in_dict(self):
        assert TrafficProfile.NONE not in TRAFFIC_PROFILES

    def test_all_entries_are_profile_parameters(self):
        for profile, params in TRAFFIC_PROFILES.items():
            assert isinstance(params, ProfileParameters)

    def test_video_streaming_pad_to_size(self):
        params = TRAFFIC_PROFILES[TrafficProfile.VIDEO_STREAMING]
        assert params.pad_to_size == 1460

    def test_voice_call_regular_timing(self):
        params = TRAFFIC_PROFILES[TrafficProfile.VOICE_CALL]
        assert params.min_interval_ms == params.max_interval_ms == 20

    def test_web_browsing_variable_padding(self):
        params = TRAFFIC_PROFILES[TrafficProfile.WEB_BROWSING]
        assert params.pad_to_size is None

    def test_gaming_low_burst_probability(self):
        params = TRAFFIC_PROFILES[TrafficProfile.GAMING]
        assert params.burst_probability == 0.1


# ---------------------------------------------------------------------------
# TrafficShaper -- NONE profile
# ---------------------------------------------------------------------------


class TestTrafficShaperNone:
    """Tests for TrafficShaper with NONE profile (passthrough mode)."""

    def setup_method(self):
        self.shaper = TrafficShaper(profile=TrafficProfile.NONE)

    def test_shape_packet_returns_data_unchanged(self):
        data = b"hello world"
        assert self.shaper.shape_packet(data) == data

    def test_unshape_packet_returns_data_unchanged(self):
        data = b"raw bytes here"
        assert self.shaper.unshape_packet(data) == data

    def test_get_send_delay_returns_zero(self):
        assert self.shaper.get_send_delay() == 0.0

    def test_get_profile_info_returns_none_dict(self):
        info = self.shaper.get_profile_info()
        assert info == {"profile": "none"}


# ---------------------------------------------------------------------------
# TrafficShaper -- VIDEO_STREAMING profile
# ---------------------------------------------------------------------------


class TestTrafficShaperVideoStreaming:
    """Tests for TrafficShaper with VIDEO_STREAMING profile."""

    def setup_method(self):
        random.seed(42)
        self.shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)

    def test_shape_packet_small_data_padded_to_pad_to_size(self):
        data = b"small"
        shaped = self.shaper.shape_packet(data)
        # 2-byte length prefix + pad_to_size (1460) bytes of payload+padding
        assert len(shaped) == 2 + 1460

    def test_shape_packet_has_correct_length_prefix(self):
        data = b"test data"
        shaped = self.shaper.shape_packet(data)
        length_prefix = int.from_bytes(shaped[:2], "big")
        assert length_prefix == len(data)

    def test_shape_packet_contains_original_data(self):
        data = b"original content"
        shaped = self.shaper.shape_packet(data)
        # After the 2-byte prefix, original data should be present
        assert shaped[2 : 2 + len(data)] == data

    def test_unshape_packet_roundtrip_preserves_data(self):
        data = b"important mesh traffic"
        shaped = self.shaper.shape_packet(data)
        unshaped = self.shaper.unshape_packet(shaped)
        assert unshaped == data

    def test_get_send_delay_returns_positive_float(self):
        delay = self.shaper.get_send_delay()
        assert isinstance(delay, float)
        assert delay > 0.0

    def test_get_send_delay_within_profile_range(self):
        random.seed(99)
        params = TRAFFIC_PROFILES[TrafficProfile.VIDEO_STREAMING]
        min_delay = params.min_interval_ms / 1000.0
        max_delay = params.max_interval_ms / 1000.0
        for _ in range(50):
            delay = self.shaper.get_send_delay()
            assert min_delay <= delay <= max_delay


# ---------------------------------------------------------------------------
# TrafficShaper -- round-trip for each profile
# ---------------------------------------------------------------------------


class TestTrafficShaperRoundTrip:
    """Shape/unshape round-trip for every non-NONE profile."""

    @pytest.mark.parametrize(
        "profile",
        [
            TrafficProfile.VIDEO_STREAMING,
            TrafficProfile.VOICE_CALL,
            TrafficProfile.WEB_BROWSING,
            TrafficProfile.FILE_DOWNLOAD,
            TrafficProfile.GAMING,
        ],
    )
    def test_roundtrip_preserves_data(self, profile):
        random.seed(12345)
        shaper = TrafficShaper(profile=profile)
        data = b"mesh round-trip payload"
        shaped = shaper.shape_packet(data)
        unshaped = shaper.unshape_packet(shaped)
        assert unshaped == data

    @pytest.mark.parametrize(
        "profile",
        [
            TrafficProfile.VIDEO_STREAMING,
            TrafficProfile.VOICE_CALL,
            TrafficProfile.WEB_BROWSING,
            TrafficProfile.FILE_DOWNLOAD,
            TrafficProfile.GAMING,
        ],
    )
    def test_shaped_packet_has_length_prefix(self, profile):
        random.seed(12345)
        shaper = TrafficShaper(profile=profile)
        data = b"prefix check"
        shaped = shaper.shape_packet(data)
        length_prefix = int.from_bytes(shaped[:2], "big")
        assert length_prefix == len(data)

    def test_roundtrip_empty_data(self):
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        data = b""
        shaped = shaper.shape_packet(data)
        unshaped = shaper.unshape_packet(shaped)
        assert unshaped == data

    def test_roundtrip_large_data(self):
        """Data larger than pad_to_size should still round-trip correctly."""
        random.seed(0)
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        data = b"X" * 2000
        shaped = shaper.shape_packet(data)
        unshaped = shaper.unshape_packet(shaped)
        assert unshaped == data

    def test_unshape_short_packet_returns_unchanged(self):
        shaper = TrafficShaper(profile=TrafficProfile.GAMING)
        assert shaper.unshape_packet(b"\x01") == b"\x01"


# ---------------------------------------------------------------------------
# TrafficShaper -- variable padding (WEB_BROWSING, GAMING)
# ---------------------------------------------------------------------------


class TestTrafficShaperVariablePadding:
    """Profiles with pad_to_size=None should choose a suitable typical size."""

    def test_web_browsing_selects_suitable_typical_size(self):
        random.seed(7)
        shaper = TrafficShaper(profile=TrafficProfile.WEB_BROWSING)
        data = b"A" * 100  # Small data, several typical sizes are >= 100
        shaped = shaper.shape_packet(data)
        # Should be 2 + one of [512, 1024, 1460]
        body_len = len(shaped) - 2
        params = TRAFFIC_PROFILES[TrafficProfile.WEB_BROWSING]
        valid_targets = params.typical_packet_sizes + [params.max_packet_size]
        assert body_len in valid_targets

    def test_gaming_data_larger_than_all_typical_uses_max(self):
        random.seed(0)
        shaper = TrafficShaper(profile=TrafficProfile.GAMING)
        # Data larger than all typical sizes [64, 128, 256] but < max (300)
        data = b"B" * 270
        shaped = shaper.shape_packet(data)
        params = TRAFFIC_PROFILES[TrafficProfile.GAMING]
        body_len = len(shaped) - 2
        assert body_len == params.max_packet_size


# ---------------------------------------------------------------------------
# TrafficShaper -- burst mode
# ---------------------------------------------------------------------------


class TestTrafficShaperBurstMode:
    """Test burst mode behaviour in get_send_delay."""

    def test_burst_triggers_with_high_probability_profile(self):
        """FILE_DOWNLOAD has burst_probability=0.9, so bursts trigger easily."""
        random.seed(1)
        shaper = TrafficShaper(profile=TrafficProfile.FILE_DOWNLOAD)
        params = TRAFFIC_PROFILES[TrafficProfile.FILE_DOWNLOAD]
        min_delay = params.min_interval_ms / 1000.0

        # Collect many delays; at least some should equal min_interval (burst)
        delays = [shaper.get_send_delay() for _ in range(30)]
        burst_delays = [d for d in delays if d == min_delay]
        assert len(burst_delays) > 0, "Expected at least one burst delay"

    def test_burst_counter_decrements(self):
        """Manually trigger burst and verify counter decrements."""
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        shaper._in_burst = True
        shaper._burst_counter = 3

        shaper.get_send_delay()
        assert shaper._burst_counter == 2

        shaper.get_send_delay()
        assert shaper._burst_counter == 1

        shaper.get_send_delay()
        assert shaper._burst_counter == 0
        assert shaper._in_burst is False

    def test_burst_ends_after_counter_reaches_zero(self):
        shaper = TrafficShaper(profile=TrafficProfile.VOICE_CALL)
        shaper._in_burst = True
        shaper._burst_counter = 1

        shaper.get_send_delay()
        assert shaper._in_burst is False
        assert shaper._burst_counter == 0

    def test_no_burst_with_zero_probability(self):
        """VOICE_CALL has burst_probability=0.0 so _in_burst should never start."""
        random.seed(42)
        shaper = TrafficShaper(profile=TrafficProfile.VOICE_CALL)
        for _ in range(50):
            shaper.get_send_delay()
        assert shaper._in_burst is False


# ---------------------------------------------------------------------------
# TrafficShaper -- get_profile_info
# ---------------------------------------------------------------------------


class TestTrafficShaperProfileInfo:
    """Tests for get_profile_info."""

    def test_returns_correct_keys_for_active_profile(self):
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        info = shaper.get_profile_info()
        expected_keys = {
            "profile",
            "name",
            "packet_sizes",
            "timing_range_ms",
            "burst_enabled",
        }
        assert set(info.keys()) == expected_keys

    def test_profile_value_matches(self):
        shaper = TrafficShaper(profile=TrafficProfile.GAMING)
        info = shaper.get_profile_info()
        assert info["profile"] == "gaming"

    def test_name_matches_params(self):
        shaper = TrafficShaper(profile=TrafficProfile.FILE_DOWNLOAD)
        info = shaper.get_profile_info()
        params = TRAFFIC_PROFILES[TrafficProfile.FILE_DOWNLOAD]
        assert info["name"] == params.name

    def test_packet_sizes_matches_params(self):
        shaper = TrafficShaper(profile=TrafficProfile.WEB_BROWSING)
        info = shaper.get_profile_info()
        params = TRAFFIC_PROFILES[TrafficProfile.WEB_BROWSING]
        assert info["packet_sizes"] == params.typical_packet_sizes

    def test_timing_range(self):
        shaper = TrafficShaper(profile=TrafficProfile.VOICE_CALL)
        info = shaper.get_profile_info()
        assert info["timing_range_ms"] == [20, 20]

    def test_burst_enabled_true(self):
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        info = shaper.get_profile_info()
        assert info["burst_enabled"] is True

    def test_burst_enabled_false(self):
        shaper = TrafficShaper(profile=TrafficProfile.VOICE_CALL)
        info = shaper.get_profile_info()
        assert info["burst_enabled"] is False


# ---------------------------------------------------------------------------
# TrafficShaper -- send_shaped (async)
# ---------------------------------------------------------------------------


class TestTrafficShaperSendShaped:
    """Async tests for send_shaped."""

    @pytest.mark.asyncio
    async def test_send_shaped_calls_send_func_with_shaped_data(self):
        random.seed(0)
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        send_func = MagicMock()
        data = b"async payload"

        with patch(
            "src.network.obfuscation.traffic_shaping.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            await shaper.send_shaped(data, send_func)

        send_func.assert_called_once()
        sent_data = send_func.call_args[0][0]
        # Verify the sent data is shaped (has length prefix)
        length_prefix = int.from_bytes(sent_data[:2], "big")
        assert length_prefix == len(data)

    @pytest.mark.asyncio
    async def test_send_shaped_awaits_delay(self):
        random.seed(0)
        shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
        send_func = MagicMock()

        with patch(
            "src.network.obfuscation.traffic_shaping.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            await shaper.send_shaped(b"data", send_func)
            mock_sleep.assert_called_once()
            delay_arg = mock_sleep.call_args[0][0]
            assert delay_arg > 0

    @pytest.mark.asyncio
    async def test_send_shaped_updates_last_send_time(self):
        shaper = TrafficShaper(profile=TrafficProfile.VOICE_CALL)
        send_func = MagicMock()
        before = time.time()

        with patch(
            "src.network.obfuscation.traffic_shaping.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await shaper.send_shaped(b"ts", send_func)

        assert shaper._last_send_time >= before

    @pytest.mark.asyncio
    async def test_send_shaped_none_profile_no_delay(self):
        shaper = TrafficShaper(profile=TrafficProfile.NONE)
        send_func = MagicMock()

        with patch(
            "src.network.obfuscation.traffic_shaping.asyncio.sleep",
            new_callable=AsyncMock,
        ) as mock_sleep:
            await shaper.send_shaped(b"passthrough", send_func)

        # Delay is 0.0 for NONE, so asyncio.sleep should NOT be called
        mock_sleep.assert_not_called()
        send_func.assert_called_once_with(b"passthrough")

    @pytest.mark.asyncio
    async def test_send_shaped_roundtrip_via_send_func(self):
        """Verify the data sent via send_func can be unshaped back."""
        random.seed(55)
        shaper = TrafficShaper(profile=TrafficProfile.GAMING)
        captured = []
        send_func = MagicMock(side_effect=lambda d: captured.append(d))

        original = b"game packet data"
        with patch(
            "src.network.obfuscation.traffic_shaping.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            await shaper.send_shaped(original, send_func)

        assert len(captured) == 1
        unshaped = shaper.unshape_packet(captured[0])
        assert unshaped == original


# ---------------------------------------------------------------------------
# TrafficAnalyzer
# ---------------------------------------------------------------------------


class TestTrafficAnalyzer:
    """Tests for TrafficAnalyzer."""

    def test_initial_state_empty(self):
        analyzer = TrafficAnalyzer()
        assert analyzer.packet_sizes == []
        assert analyzer.inter_arrival_times == []

    def test_record_packet_stores_size(self):
        analyzer = TrafficAnalyzer()
        analyzer.record_packet(1460)
        analyzer.record_packet(200)
        assert analyzer.packet_sizes == [1460, 200]

    def test_record_packet_computes_inter_arrival_time(self):
        analyzer = TrafficAnalyzer()
        with patch(
            "src.network.obfuscation.traffic_shaping.time.time",
            side_effect=[1000.0, 1000.050],
        ):
            analyzer.record_packet(100)
            analyzer.record_packet(200)
        assert len(analyzer.inter_arrival_times) == 1
        assert abs(analyzer.inter_arrival_times[0] - 0.050) < 1e-6

    def test_get_statistics_no_packets(self):
        analyzer = TrafficAnalyzer()
        stats = analyzer.get_statistics()
        assert stats == {"packets": 0}

    def test_get_statistics_with_packets(self):
        analyzer = TrafficAnalyzer()
        with patch(
            "src.network.obfuscation.traffic_shaping.time.time",
            side_effect=[1.0, 1.1, 1.2],
        ):
            analyzer.record_packet(100)
            analyzer.record_packet(200)
            analyzer.record_packet(300)

        stats = analyzer.get_statistics()
        assert stats["packets"] == 3
        assert stats["avg_size"] == 200.0
        assert stats["min_size"] == 100
        assert stats["max_size"] == 300
        # inter-arrival times: [0.1, 0.1], average = 0.1s = 100ms
        assert abs(stats["avg_interval_ms"] - 100.0) < 1e-6
        # throughput: 1/0.1 = 10 pps
        assert abs(stats["throughput_pps"] - 10.0) < 1e-6

    def test_get_statistics_single_packet(self):
        analyzer = TrafficAnalyzer()
        analyzer.record_packet(500)
        stats = analyzer.get_statistics()
        assert stats["packets"] == 1
        assert stats["avg_size"] == 500.0
        assert stats["min_size"] == 500
        assert stats["max_size"] == 500
        # No inter-arrival times yet
        assert stats["avg_interval_ms"] == 0
        assert stats["throughput_pps"] == 0

    def test_reset_clears_all_data(self):
        analyzer = TrafficAnalyzer()
        analyzer.record_packet(100)
        analyzer.record_packet(200)
        analyzer.reset()

        assert analyzer.packet_sizes == []
        assert analyzer.inter_arrival_times == []
        assert analyzer._last_packet_time is None

    def test_reset_then_get_statistics_returns_empty(self):
        analyzer = TrafficAnalyzer()
        analyzer.record_packet(100)
        analyzer.reset()
        stats = analyzer.get_statistics()
        assert stats == {"packets": 0}


# ---------------------------------------------------------------------------
# TrafficShaper -- default profile
# ---------------------------------------------------------------------------


class TestTrafficShaperDefaults:
    """Test default constructor behaviour."""

    def test_default_profile_is_video_streaming(self):
        shaper = TrafficShaper()
        assert shaper.profile == TrafficProfile.VIDEO_STREAMING

    def test_initial_state(self):
        shaper = TrafficShaper()
        assert shaper._last_send_time == 0
        assert shaper._burst_counter == 0
        assert shaper._in_burst is False

    def test_params_set_from_profiles_dict(self):
        shaper = TrafficShaper()
        assert shaper.params is TRAFFIC_PROFILES[TrafficProfile.VIDEO_STREAMING]
