from __future__ import annotations

import pytest

from libx0t.network.obfuscation.traffic_shaping import (
    TrafficAnalyzer,
    TrafficProfile,
    TrafficShaper,
)


def test_libx0t_traffic_shaper_thinking_redacts_payload():
    shaper = TrafficShaper(profile=TrafficProfile.VIDEO_STREAMING)
    shaped = shaper.shape_packet(b"raw-payload-secret")
    assert shaper.unshape_packet(shaped) == b"raw-payload-secret"

    status = shaper.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "security"
    assert "zero_trust_review" in status["thinking"]["techniques"]
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "libx0t_traffic_shaping_unshape_packet_done"
    )
    assert "raw-payload-secret" not in repr(status)


@pytest.mark.asyncio
async def test_libx0t_send_shaped_thinking_is_not_dataplane_proof(monkeypatch):
    shaper = TrafficShaper(profile=TrafficProfile.GAMING)
    sent = []

    async def _sleep(_delay):
        return None

    monkeypatch.setattr("libx0t.network.obfuscation.traffic_shaping.asyncio.sleep", _sleep)
    await shaper.send_shaped(b"raw-game-secret", sent.append)

    assert sent
    status = shaper.get_thinking_status()
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "libx0t_traffic_shaping_send_shaped_done"
    )
    rendered = repr(status)
    assert "raw-game-secret" not in rendered
    assert "dataplane_confirmed': True" not in rendered


def test_libx0t_traffic_analyzer_thinking_records_counts_only():
    analyzer = TrafficAnalyzer()
    analyzer.record_packet(256)
    stats = analyzer.get_statistics()
    assert stats["packets"] == 1

    status = analyzer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "monitoring"
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "libx0t_traffic_analyzer_get_statistics"
    )
