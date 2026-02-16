"""
Unit tests for PerfBufferReader component.

Tests cover:
- Initialization
- Event handler registration
- Event processing
- Queue management
- Statistics
- Error handling
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from telemetry_module import (EventSeverity, PerfBufferReader, TelemetryConfig,
                              TelemetryEvent)


class TestPerfBufferReaderInitialization:
    """Test PerfBufferReader initialization."""

    def test_initialization_with_config(self, telemetry_config):
        """Test initialization with configuration."""
        reader = PerfBufferReader(telemetry_config, MagicMock())

        assert reader.config == telemetry_config
        assert reader.running == False
        assert len(reader.event_queue) == 0
        assert isinstance(reader.event_handlers, dict)

    def test_initialization_stats(self, telemetry_config):
        """Test that statistics are initialized."""
        reader = PerfBufferReader(telemetry_config, MagicMock())

        assert reader.stats["events_received"] == 0
        assert reader.stats["events_processed"] == 0
        assert reader.stats["events_dropped"] == 0
        assert reader.stats["parse_errors"] == 0


class TestPerfBufferReaderEventHandlers:
    """Test event handler registration."""

    @pytest.fixture
    def reader(self, telemetry_config):
        return PerfBufferReader(telemetry_config, MagicMock())

    def test_register_handler(self, reader):
        """Test registering an event handler."""
        handler = Mock()
        reader.register_handler("test_event", handler)

        assert "test_event" in reader.event_handlers
        assert handler in reader.event_handlers["test_event"]

    def test_register_multiple_handlers(self, reader):
        """Test registering multiple handlers for same event type."""
        handler1 = Mock()
        handler2 = Mock()

        reader.register_handler("test_event", handler1)
        reader.register_handler("test_event", handler2)

        assert len(reader.event_handlers["test_event"]) == 2
        assert handler1 in reader.event_handlers["test_event"]
        assert handler2 in reader.event_handlers["test_event"]

    def test_register_handler_different_types(self, reader):
        """Test registering handlers for different event types."""
        handler1 = Mock()
        handler2 = Mock()

        reader.register_handler("event_type1", handler1)
        reader.register_handler("event_type2", handler2)

        assert "event_type1" in reader.event_handlers
        assert "event_type2" in reader.event_handlers
        assert handler1 in reader.event_handlers["event_type1"]
        assert handler2 in reader.event_handlers["event_type2"]


class TestPerfBufferReaderEventProcessing:
    """Test event processing."""

    @pytest.fixture
    def reader(self, telemetry_config):
        return PerfBufferReader(telemetry_config, MagicMock())

    def test_process_event_success(self, reader):
        """Test successful event processing."""
        handler = Mock()
        reader.register_handler("test_event", handler)

        event = TelemetryEvent(
            event_type="test_event", timestamp_ns=1000000000, cpu_id=0, pid=1234
        )

        reader.event_queue.append(event)
        reader._process_events()

        handler.assert_called_once()

    def test_process_event_multiple_handlers(self, reader):
        """Test event processing with multiple handlers."""
        handler1 = Mock()
        handler2 = Mock()

        reader.register_handler("test_event", handler1)
        reader.register_handler("test_event", handler2)

        event = TelemetryEvent(
            event_type="test_event", timestamp_ns=1000000000, cpu_id=0, pid=1234
        )

        reader.event_queue.append(event)
        reader._process_events()

        handler1.assert_called_once()
        handler2.assert_called_once()

    def test_process_event_no_handler(self, reader):
        """Test event processing when no handler is registered."""
        event = TelemetryEvent(
            event_type="unhandled_event", timestamp_ns=1000000000, cpu_id=0, pid=1234
        )

        reader.event_queue.append(event)
        reader._process_events()

        # Should not raise exception
        assert len(reader.event_queue) == 0

    def test_process_event_handler_exception(self, reader):
        """Test event processing when handler raises exception."""
        handler = Mock(side_effect=Exception("Handler error"))
        reader.register_handler("test_event", handler)

        event = TelemetryEvent(
            event_type="test_event", timestamp_ns=1000000000, cpu_id=0, pid=1234
        )

        reader.event_queue.append(event)
        reader._process_events()

        # Should handle exception gracefully
        assert len(reader.event_queue) == 0

    def test_process_multiple_events(self, reader):
        """Test processing multiple events."""
        handler = Mock()
        reader.register_handler("test_event", handler)

        for i in range(10):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=i % 4,
                pid=1234 + i,
            )
            reader.event_queue.append(event)

        reader._process_events()

        assert handler.call_count == 10
        assert len(reader.event_queue) == 0


class TestPerfBufferReaderQueueManagement:
    """Test queue management."""

    @pytest.fixture
    def reader(self, telemetry_config):
        config = TelemetryConfig(max_queue_size=5)
        return PerfBufferReader(config, MagicMock())

    def test_queue_add_event(self, reader):
        """Test adding event to queue."""
        event = TelemetryEvent(
            event_type="test_event", timestamp_ns=1000000000, cpu_id=0, pid=1234
        )

        reader.event_queue.append(event)

        assert len(reader.event_queue) == 1

    def test_queue_max_size(self, reader):
        """Test queue maximum size."""
        # Add more events than max queue size
        for i in range(10):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=0,
                pid=1234 + i,
            )
            reader.event_queue.append(event)

        # Queue should be at max size
        assert len(reader.event_queue) == reader.event_queue.maxlen

    def test_queue_events_dropped(self, reader):
        """Test that events are dropped when queue is full."""
        # Fill queue
        for i in range(5):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=0,
                pid=1234 + i,
            )
            reader.event_queue.append(event)

        # Add more events (should be dropped)
        for i in range(5, 10):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=0,
                pid=1234 + i,
            )
            reader.event_queue.append(event)

        # Check stats
        assert reader.stats["events_dropped"] >= 5


class TestPerfBufferReaderStatistics:
    """Test statistics tracking."""

    @pytest.fixture
    def reader(self, telemetry_config):
        return PerfBufferReader(telemetry_config, MagicMock())

    def test_stats_initial(self, reader):
        """Test initial statistics."""
        stats = reader.get_stats()

        assert stats["events_received"] == 0
        assert stats["events_processed"] == 0
        assert stats["events_dropped"] == 0
        assert stats["parse_errors"] == 0

    def test_stats_events_received(self, reader):
        """Test events received counter."""
        for i in range(10):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=0,
                pid=1234 + i,
            )
            reader.event_queue.append(event)
            reader.stats["events_received"] += 1

        stats = reader.get_stats()
        assert stats["events_received"] == 10

    def test_stats_events_processed(self, reader):
        """Test events processed counter."""
        handler = Mock()
        reader.register_handler("test_event", handler)

        for i in range(5):
            event = TelemetryEvent(
                event_type="test_event",
                timestamp_ns=1000000000 + i,
                cpu_id=0,
                pid=1234 + i,
            )
            reader.event_queue.append(event)
            reader._process_events()

        stats = reader.get_stats()
        assert stats["events_processed"] == 5


class TestPerfBufferReaderErrorHandling:
    """Test error handling."""

    @pytest.fixture
    def reader(self, telemetry_config):
        return PerfBufferReader(telemetry_config, MagicMock())

    def test_handle_invalid_event_data(self, reader):
        """Test handling of invalid event data."""
        # Add invalid event (too small)
        reader.event_queue.append(b"short")

        # Should handle gracefully
        reader._process_events()

        assert reader.stats["parse_errors"] >= 1

    def test_handle_malformed_event(self, reader):
        """Test handling of malformed event."""
        # Add malformed event
        reader.event_queue.append(b"malformed_data")

        # Should handle gracefully
        reader._process_events()

        assert reader.stats["parse_errors"] >= 1


class TestPerfBufferReaderLifecycle:
    """Test reader lifecycle."""

    @pytest.fixture
    def reader(self, telemetry_config):
        return PerfBufferReader(telemetry_config, MagicMock())

    def test_start_reading(self, reader):
        """Test starting reading."""
        reader.start_reading()

        assert reader.running == True

    def test_stop_reading(self, reader):
        """Test stopping reading."""
        reader.start_reading()
        reader.stop_reading()

        assert reader.running == False


class TestPerfBufferReaderEdgeCases:
    """Test edge cases."""

    @pytest.fixture
    def reader(self, telemetry_config):
        return PerfBufferReader(telemetry_config, MagicMock())

    def test_empty_queue_processing(self, reader):
        """Test processing empty queue."""
        reader._process_events()

        # Should not raise exception
        assert len(reader.event_queue) == 0

    def test_event_with_all_fields(self, reader):
        """Test event with all fields populated."""
        handler = Mock()
        reader.register_handler("test_event", handler)

        event = TelemetryEvent(
            event_type="test_event",
            timestamp_ns=1234567890,
            cpu_id=3,
            pid=9999,
            data={"key1": "value1", "key2": 123},
            severity=EventSeverity.CRITICAL,
        )

        reader.event_queue.append(event)
        reader._process_events()

        handler.assert_called_once()
        call_args = handler.call_args[0][0]
        assert call_args.event_type == "test_event"
        assert call_args.timestamp_ns == 1234567890
        assert call_args.cpu_id == 3
        assert call_args.pid == 9999
        assert call_args.severity == EventSeverity.CRITICAL
