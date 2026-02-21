"""
Unit tests for src.network.ebpf.telemetry.perf_reader.PerfBufferReader.

Covers: construction, register_handler, start_reading (BCC unavailable path),
stop_reading, get_stats, and _process_events.
BCC is mocked / unavailable in this environment.
"""
import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from collections import deque
from unittest.mock import MagicMock, patch

import pytest

from src.network.ebpf.telemetry.models import (
    EventSeverity,
    TelemetryConfig,
    TelemetryEvent,
)
from src.network.ebpf.telemetry.perf_reader import BCC_AVAILABLE, PerfBufferReader
from src.network.ebpf.telemetry.security import SecurityManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def config():
    return TelemetryConfig(max_queue_size=50, poll_timeout=10)


@pytest.fixture
def security(config):
    return SecurityManager(config)


@pytest.fixture
def reader(config, security):
    return PerfBufferReader(config=config, security=security)


@pytest.fixture
def mock_security():
    """A MagicMock acting as SecurityManager so validate_event can be controlled."""
    m = MagicMock(spec=SecurityManager)
    m.validate_event.return_value = (True, None)
    return m


@pytest.fixture
def reader_mock_sec(config, mock_security):
    return PerfBufferReader(config=config, security=mock_security)


def _make_event(event_type="net_packet", ts=1_000_000_000, cpu=0):
    return TelemetryEvent(event_type=event_type, timestamp_ns=ts, cpu_id=cpu)


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestPerfBufferReaderInit:
    def test_running_flag_is_false_initially(self, reader):
        assert reader.running is False

    def test_config_stored(self, reader, config):
        assert reader.config is config

    def test_security_stored(self, reader, security):
        assert reader.security is security

    def test_event_queue_is_deque(self, reader):
        assert isinstance(reader.event_queue, deque)

    def test_event_queue_maxlen_matches_config(self, reader, config):
        assert reader.event_queue.maxlen == config.max_queue_size

    def test_event_handlers_dict_starts_empty(self, reader):
        # defaultdict(list) — iterating keys should yield nothing
        assert len(reader.event_handlers) == 0

    def test_initial_stats_all_zero(self, reader):
        stats = reader.get_stats()
        assert stats["events_received"] == 0
        assert stats["events_processed"] == 0
        assert stats["events_dropped"] == 0
        assert stats["parse_errors"] == 0


# ---------------------------------------------------------------------------
# register_handler
# ---------------------------------------------------------------------------


class TestRegisterHandler:
    def test_handler_added_to_event_handlers(self, reader):
        handler = MagicMock()
        reader.register_handler("net_packet", handler)
        assert handler in reader.event_handlers["net_packet"]

    def test_multiple_handlers_for_same_event_type(self, reader):
        h1, h2 = MagicMock(), MagicMock()
        reader.register_handler("net_packet", h1)
        reader.register_handler("net_packet", h2)
        assert len(reader.event_handlers["net_packet"]) == 2

    def test_different_event_types_stored_separately(self, reader):
        h1, h2 = MagicMock(), MagicMock()
        reader.register_handler("net_packet", h1)
        reader.register_handler("sys_call", h2)
        assert "net_packet" in reader.event_handlers
        assert "sys_call" in reader.event_handlers

    def test_handler_list_is_ordered_by_registration(self, reader):
        h1, h2, h3 = MagicMock(), MagicMock(), MagicMock()
        for h in (h1, h2, h3):
            reader.register_handler("evt", h)
        assert reader.event_handlers["evt"] == [h1, h2, h3]


# ---------------------------------------------------------------------------
# start_reading — BCC unavailable path
# ---------------------------------------------------------------------------


class TestStartReadingNoBCC:
    def test_start_reading_does_not_set_running_when_bcc_unavailable(self, reader):
        """When BCC is not available, start_reading returns immediately without
        setting self.running = True."""
        with patch(
            "src.network.ebpf.telemetry.perf_reader.BCC_AVAILABLE", False
        ):
            bpf_mock = MagicMock()
            reader.start_reading(bpf_mock, "events")
        # running should still be False because we returned early
        assert reader.running is False

    def test_start_reading_bcc_unavailable_does_not_call_bpf(self, reader):
        bpf_mock = MagicMock()
        with patch(
            "src.network.ebpf.telemetry.perf_reader.BCC_AVAILABLE", False
        ):
            reader.start_reading(bpf_mock, "events")
        bpf_mock.__getitem__.assert_not_called()


# ---------------------------------------------------------------------------
# stop_reading
# ---------------------------------------------------------------------------


class TestStopReading:
    def test_stop_reading_sets_running_false(self, reader):
        reader.running = True
        reader.stop_reading()
        assert reader.running is False

    def test_stop_reading_when_already_false_is_idempotent(self, reader):
        reader.running = False
        reader.stop_reading()
        assert reader.running is False


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------


class TestGetStats:
    def test_get_stats_returns_dict(self, reader):
        assert isinstance(reader.get_stats(), dict)

    def test_get_stats_has_required_keys(self, reader):
        stats = reader.get_stats()
        assert "events_received" in stats
        assert "events_processed" in stats
        assert "events_dropped" in stats
        assert "parse_errors" in stats

    def test_get_stats_is_copy_not_same_reference(self, reader):
        s1 = reader.get_stats()
        s2 = reader.get_stats()
        assert s1 is not s2

    def test_get_stats_reflects_manual_stat_updates(self, reader):
        reader.stats["events_received"] = 7
        assert reader.get_stats()["events_received"] == 7


# ---------------------------------------------------------------------------
# _process_events — internal logic
# ---------------------------------------------------------------------------


class TestProcessEvents:
    def test_handlers_called_for_matching_event_type(self, reader_mock_sec):
        handler = MagicMock()
        reader_mock_sec.register_handler("net_packet", handler)
        event = _make_event("net_packet")
        reader_mock_sec.event_queue.append(event)
        reader_mock_sec._process_events()
        handler.assert_called_once_with(event)

    def test_events_processed_counter_incremented(self, reader_mock_sec):
        handler = MagicMock()
        reader_mock_sec.register_handler("net_packet", handler)
        reader_mock_sec.event_queue.append(_make_event("net_packet"))
        reader_mock_sec.event_queue.append(_make_event("net_packet"))
        reader_mock_sec._process_events()
        assert reader_mock_sec.stats["events_processed"] == 2

    def test_no_handler_for_event_type_does_not_crash(self, reader_mock_sec):
        reader_mock_sec.event_queue.append(_make_event("unknown_type"))
        # Should not raise
        reader_mock_sec._process_events()

    def test_handler_exception_does_not_stop_processing(self, reader_mock_sec):
        bad_handler = MagicMock(side_effect=RuntimeError("handler boom"))
        good_handler = MagicMock()
        reader_mock_sec.register_handler("net_packet", bad_handler)
        reader_mock_sec.register_handler("net_packet", good_handler)
        reader_mock_sec.event_queue.append(_make_event("net_packet"))
        reader_mock_sec._process_events()
        good_handler.assert_called_once()

    def test_queue_is_empty_after_processing(self, reader_mock_sec):
        reader_mock_sec.event_queue.append(_make_event("net_packet"))
        reader_mock_sec._process_events()
        assert len(reader_mock_sec.event_queue) == 0


# ---------------------------------------------------------------------------
# BCC_AVAILABLE module flag
# ---------------------------------------------------------------------------


class TestBCCAvailableFlag:
    def test_bcc_available_is_bool(self):
        assert isinstance(BCC_AVAILABLE, bool)
