"""Unit tests for NodeManager traffic shaping integration."""

from unittest.mock import MagicMock, patch

import pytest

from src.network.batman.node_manager import NodeManager


class TestNodeManagerTrafficShaping:
    """Tests for NodeManager traffic shaping integration."""

    def test_traffic_shaping_disabled_by_default(self):
        """Traffic shaping should be disabled with 'none' profile."""
        nm = NodeManager("mesh", "node1", traffic_profile="none")
        assert nm.traffic_shaper is None

    def test_traffic_shaping_enabled_with_profile(self):
        """Traffic shaping should be enabled with valid profile."""
        nm = NodeManager("mesh", "node1", traffic_profile="video_streaming")
        assert nm.traffic_shaper is not None
        assert nm.traffic_shaper.profile.value == "video_streaming"

    def test_traffic_shaping_voice_call_profile(self):
        """Test voice call profile activation."""
        nm = NodeManager("mesh", "node1", traffic_profile="voice_call")
        assert nm.traffic_shaper is not None
        info = nm.traffic_shaper.get_profile_info()
        assert info["profile"] == "voice_call"
        assert info["name"] == "Voice Call (WhatsApp/Signal)"

    def test_traffic_shaping_gaming_profile(self):
        """Test gaming profile activation."""
        nm = NodeManager("mesh", "node1", traffic_profile="gaming")
        assert nm.traffic_shaper is not None
        info = nm.traffic_shaper.get_profile_info()
        assert info["profile"] == "gaming"

    def test_invalid_profile_logs_warning(self):
        """Invalid profile should log warning and disable shaping."""
        with patch("src.network.batman.node_manager.logger") as mock_logger:
            nm = NodeManager("mesh", "node1", traffic_profile="invalid_profile")
            assert nm.traffic_shaper is None
            mock_logger.warning.assert_called()

    def test_heartbeat_with_traffic_shaping(self):
        """Heartbeat should apply traffic shaping."""
        nm = NodeManager("mesh", "node1", traffic_profile="file_download")

        # Should succeed and use shaping
        result = nm.send_heartbeat("target_node")
        assert result is True

    def test_topology_update_with_traffic_shaping(self):
        """Topology update should apply traffic shaping."""
        nm = NodeManager("mesh", "node1", traffic_profile="web_browsing")

        result = nm.send_topology_update("target", {"key": "value"})
        assert result is True

    def test_combined_obfuscation_and_shaping(self):
        """Both obfuscation and traffic shaping should work together."""
        from src.network.obfuscation import TransportManager

        transport = TransportManager.create("xor", key="testkey")
        nm = NodeManager(
            "mesh",
            "node1",
            obfuscation_transport=transport,
            traffic_profile="video_streaming",
        )

        assert nm.obfuscation_transport is not None
        assert nm.traffic_shaper is not None

        # Both should be applied in heartbeat
        result = nm.send_heartbeat("peer")
        assert result is True
