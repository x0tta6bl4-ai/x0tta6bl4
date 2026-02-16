"""
Unit tests for SecurityManager component.

Tests cover:
- Metric name validation
- Metric value validation
- String sanitization
- Path sanitization
- Event validation
- Security statistics
"""

import pytest
from telemetry_module import (EventSeverity, MetricValidationStatus,
                              SecurityManager, TelemetryConfig, TelemetryEvent)


class TestSecurityManagerInitialization:
    """Test SecurityManager initialization."""

    def test_initialization_with_default_config(self):
        """Test initialization with default configuration."""
        config = TelemetryConfig()
        security = SecurityManager(config)

        assert security.config == config
        assert security.validation_errors == []
        assert security.sanitized_count == 0
        assert len(security.blocked_patterns) > 0
        assert len(security.allowed_metric_chars) > 0

    def test_initialization_with_custom_config(self):
        """Test initialization with custom configuration."""
        config = TelemetryConfig(
            enable_validation=False, enable_sanitization=False, max_metric_value=1e10
        )
        security = SecurityManager(config)

        assert security.config.enable_validation == False
        assert security.config.enable_sanitization == False
        assert security.config.max_metric_value == 1e10

    def test_blocked_patterns_initialization(self):
        """Test that blocked patterns are properly initialized."""
        config = TelemetryConfig()
        security = SecurityManager(config)

        assert "../" in security.blocked_patterns
        assert "..\\" in security.blocked_patterns
        assert "/proc/" in security.blocked_patterns
        assert "\x00" in security.blocked_patterns

    def test_allowed_metric_chars_initialization(self):
        """Test that allowed metric characters are properly initialized."""
        config = TelemetryConfig()
        security = SecurityManager(config)

        assert "a" in security.allowed_metric_chars
        assert "Z" in security.allowed_metric_chars
        assert "0" in security.allowed_metric_chars
        assert "_" in security.allowed_metric_chars
        assert ":" in security.allowed_metric_chars


class TestMetricNameValidation:
    """Test metric name validation."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_valid_metric_name(self, security_manager):
        """Test validation of valid metric names."""
        valid_names = [
            "cpu_usage_percent",
            "memory_usage_bytes",
            "network_packets_total",
            "security_events_total",
            "custom_metric_123",
            "metric_with_underscores",
        ]

        for name in valid_names:
            is_valid, error = security_manager.validate_metric_name(name)
            assert is_valid, f"Valid metric name '{name}' was rejected: {error}"
            assert error is None

    def test_empty_metric_name(self, security_manager):
        """Test validation of empty metric name."""
        is_valid, error = security_manager.validate_metric_name("")

        assert not is_valid
        assert error is not None
        assert "cannot be empty" in error.lower()

    def test_metric_name_too_long(self, security_manager):
        """Test validation of metric name that is too long."""
        long_name = "a" * 201
        is_valid, error = security_manager.validate_metric_name(long_name)

        assert not is_valid
        assert error is not None
        assert "too long" in error.lower()

    def test_metric_name_with_invalid_characters(self, security_manager):
        """Test validation of metric name with invalid characters."""
        invalid_names = [
            "metric with spaces",
            "metric-with-dashes",
            "metric/with/slashes",
            "metric.with.dots",
            "metric@with@special",
            "metric#with#hash",
        ]

        for name in invalid_names:
            is_valid, error = security_manager.validate_metric_name(name)
            assert not is_valid, f"Invalid metric name '{name}' was accepted"
            assert error is not None

    def test_metric_name_starting_with_double_underscore(self, security_manager):
        """Test validation of metric name starting with __."""
        is_valid, error = security_manager.validate_metric_name("__private_metric")

        assert not is_valid
        assert error is not None
        assert "cannot start with '__'" in error.lower()

    def test_metric_name_exactly_200_characters(self, security_manager):
        """Test validation of metric name with exactly 200 characters."""
        name = "a" * 200
        is_valid, error = security_manager.validate_metric_name(name)

        assert is_valid, f"Valid metric name (200 chars) was rejected: {error}"
        assert error is None


class TestMetricValueValidation:
    """Test metric value validation."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_valid_integer_value(self, security_manager):
        """Test validation of valid integer values."""
        valid_values = [0, 1, 100, 1000, 1000000]

        for value in valid_values:
            is_valid, error = security_manager.validate_metric_value(value)
            assert is_valid, f"Valid integer value {value} was rejected: {error}"
            assert error is None

    def test_valid_float_value(self, security_manager):
        """Test validation of valid float values."""
        valid_values = [0.0, 1.5, 100.123, 1000.999]

        for value in valid_values:
            is_valid, error = security_manager.validate_metric_value(value)
            assert is_valid, f"Valid float value {value} was rejected: {error}"
            assert error is None

    def test_none_value(self, security_manager):
        """Test validation of None value."""
        is_valid, error = security_manager.validate_metric_value(None)

        assert not is_valid
        assert error is not None
        assert "cannot be None" in error.lower()

    def test_string_value(self, security_manager):
        """Test validation of string value."""
        is_valid, error = security_manager.validate_metric_value("invalid")

        assert not is_valid
        assert error is not None
        assert "invalid metric type" in error.lower()

    def test_nan_value(self, security_manager):
        """Test validation of NaN value."""
        import math

        is_valid, error = security_manager.validate_metric_value(float("nan"))

        assert not is_valid
        assert error is not None
        assert "cannot be NaN" in error.lower()

    def test_infinite_value(self, security_manager):
        """Test validation of infinite value."""
        is_valid, error = security_manager.validate_metric_value(float("inf"))

        assert not is_valid
        assert error is not None
        assert "cannot be infinite" in error.lower()

    def test_negative_infinite_value(self, security_manager):
        """Test validation of negative infinite value."""
        is_valid, error = security_manager.validate_metric_value(float("-inf"))

        assert not is_valid
        assert error is not None
        assert "cannot be infinite" in error.lower()

    def test_value_exceeds_maximum(self, security_manager):
        """Test validation of value that exceeds maximum."""
        config = TelemetryConfig(max_metric_value=1000)
        security = SecurityManager(config)

        is_valid, error = security_manager.validate_metric_value(1001)

        assert not is_valid
        assert error is not None
        assert "exceeds maximum" in error.lower()

    def test_negative_value(self, security_manager):
        """Test validation of negative value."""
        is_valid, error = security_manager.validate_metric_value(-100)

        # Negative values should be valid (gauges can be negative)
        assert is_valid, f"Valid negative value was rejected: {error}"
        assert error is None


class TestStringSanitization:
    """Test string sanitization."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_sanitize_normal_string(self, security_manager):
        """Test sanitization of normal string."""
        input_str = "normal_string_123"
        result = security_manager.sanitize_string(input_str)

        assert result == input_str
        assert security_manager.sanitized_count == 1

    def test_sanitize_null_bytes(self, security_manager):
        """Test sanitization of null bytes."""
        input_str = "test\x00string\x00with\x00nulls"
        result = security_manager.sanitize_string(input_str)

        assert "\x00" not in result
        assert result == "teststringwithnulls"

    def test_sanitize_path_traversal(self, security_manager):
        """Test sanitization of path traversal attempts."""
        input_str = "../../../etc/passwd"
        result = security_manager.sanitize_string(input_str)

        assert "../" not in result
        assert "..\\" not in result

    def test_sanitize_sensitive_paths(self, security_manager):
        """Test sanitization of sensitive paths."""
        input_str = "/proc/self/status"
        result = security_manager.sanitize_string(input_str)

        assert "/proc/" not in result

    def test_sanitize_long_string(self, security_manager):
        """Test sanitization of long string."""
        input_str = "a" * 2000
        result = security_manager.sanitize_string(input_str)

        assert len(result) == 1000  # Max length
        assert result == "a" * 1000

    def test_sanitize_non_string_input(self, security_manager):
        """Test sanitization of non-string input."""
        result = security_manager.sanitize_string(123)

        assert result == ""

    def test_sanitize_empty_string(self, security_manager):
        """Test sanitization of empty string."""
        result = security_manager.sanitize_string("")

        assert result == ""

    def test_sanitize_count_increments(self, security_manager):
        """Test that sanitized count increments."""
        security_manager.sanitize_string("test1")
        count1 = security_manager.sanitized_count

        security_manager.sanitize_string("test2")
        count2 = security_manager.sanitized_count

        assert count2 == count1 + 1


class TestPathSanitization:
    """Test path sanitization."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_sanitize_normal_path(self, security_manager):
        """Test sanitization of normal path."""
        input_path = "/home/user/file.txt"
        result = security_manager.sanitize_path(input_path)

        assert result == "file.txt"

    def test_sanitize_path_with_traversal(self, security_manager):
        """Test sanitization of path with traversal."""
        input_path = "../../../etc/passwd"
        result = security_manager.sanitize_path(input_path)

        assert "../" not in result
        assert "..\\" not in result

    def test_sanitize_absolute_path(self, security_manager):
        """Test sanitization of absolute path."""
        input_path = "/etc/passwd"
        result = security_manager.sanitize_path(input_path)

        assert not result.startswith("/")
        assert result == "passwd"

    def test_sanitize_path_with_subdirectories(self, security_manager):
        """Test sanitization of path with subdirectories."""
        input_path = "/home/user/documents/file.txt"
        result = security_manager.sanitize_path(input_path)

        assert result == "file.txt"

    def test_sanitize_path_disabled(self, telemetry_config):
        """Test path sanitization when disabled."""
        config = TelemetryConfig(sanitize_paths=False)
        security = SecurityManager(config)

        input_path = "/etc/passwd"
        result = security_manager.sanitize_path(input_path)

        assert result == input_path  # No sanitization


class TestEventValidation:
    """Test event validation."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_valid_event(self, security_manager):
        """Test validation of valid event."""
        event = TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=0,
            pid=1234,
            data={"type": "file_access"},
            severity=EventSeverity.HIGH,
        )

        is_valid, error = security_manager.validate_event(event)

        assert is_valid, f"Valid event was rejected: {error}"
        assert error is None

    def test_event_with_invalid_type(self, security_manager):
        """Test validation of event with invalid type."""
        event = TelemetryEvent(
            event_type="", timestamp_ns=1000000000, cpu_id=0, pid=1234  # Empty type
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None
        assert "invalid event type" in error.lower()

    def test_event_with_invalid_timestamp(self, security_manager):
        """Test validation of event with invalid timestamp."""
        event = TelemetryEvent(
            event_type="security_event", timestamp_ns=0, cpu_id=0, pid=1234  # Invalid
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None
        assert "invalid timestamp" in error.lower()

    def test_event_with_invalid_cpu_id(self, security_manager):
        """Test validation of event with invalid CPU ID."""
        event = TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=256,  # Invalid (> 255)
            pid=1234,
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None
        assert "invalid cpu id" in error.lower()

    def test_event_with_invalid_pid(self, security_manager):
        """Test validation of event with invalid PID."""
        event = TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=0,
            pid=5000000,  # Invalid (> 4194304)
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None
        assert "invalid pid" in error.lower()

    def test_event_with_invalid_severity(self, security_manager):
        """Test validation of event with invalid severity."""
        event = TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=0,
            pid=1234,
            severity="invalid",  # Not EventSeverity enum
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None
        assert "invalid severity" in error.lower()

    def test_event_with_negative_cpu_id(self, security_manager):
        """Test validation of event with negative CPU ID."""
        event = TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=-1,  # Invalid
            pid=1234,
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None

    def test_event_with_negative_pid(self, security_manager):
        """Test validation of event with negative PID."""
        event = TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=0,
            pid=-1,  # Invalid
        )

        is_valid, error = security_manager.validate_event(event)

        assert not is_valid
        assert error is not None


class TestSecurityStatistics:
    """Test security statistics."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_get_stats_initial(self, security_manager):
        """Test getting initial statistics."""
        stats = security_manager.get_stats()

        assert "validation_errors" in stats
        assert "sanitized_count" in stats
        assert "config" in stats

        assert stats["validation_errors"] == 0
        assert stats["sanitized_count"] == 0

    def test_get_stats_after_validation_errors(self, security_manager):
        """Test getting statistics after validation errors."""
        # Generate some validation errors
        security_manager.validate_metric_name("")
        security_manager.validate_metric_name("invalid name")

        stats = security_manager.get_stats()

        assert stats["validation_errors"] >= 2

    def test_get_stats_after_sanitization(self, security_manager):
        """Test getting statistics after sanitization."""
        # Sanitize some strings
        security_manager.sanitize_string("test1")
        security_manager.sanitize_string("test2")
        security_manager.sanitize_string("test3")

        stats = security_manager.get_stats()

        assert stats["sanitized_count"] == 3

    def test_get_stats_config(self, security_manager):
        """Test that config is included in stats."""
        stats = security_manager.get_stats()

        assert "config" in stats
        assert "enable_validation" in stats["config"]
        assert "enable_sanitization" in stats["config"]
        assert "max_metric_value" in stats["config"]


class TestSecurityManagerEdgeCases:
    """Test edge cases for SecurityManager."""

    @pytest.fixture
    def security_manager(self, telemetry_config):
        return SecurityManager(telemetry_config)

    def test_metric_name_with_unicode(self, security_manager):
        """Test metric name with unicode characters."""
        is_valid, error = security_manager.validate_metric_name("metric_тест")

        # Unicode should be rejected
        assert not is_valid
        assert error is not None

    def test_metric_value_zero(self, security_manager):
        """Test metric value of zero."""
        is_valid, error = security_manager.validate_metric_value(0)

        assert is_valid, f"Valid zero value was rejected: {error}"
        assert error is None

    def test_metric_value_very_large(self, security_manager):
        """Test metric value that is very large but within limit."""
        config = TelemetryConfig(max_metric_value=1e15)
        security = SecurityManager(config)

        is_valid, error = security_manager.validate_metric_value(1e14)

        assert is_valid, f"Valid large value was rejected: {error}"
        assert error is None

    def test_string_with_special_characters(self, security_manager):
        """Test string with various special characters."""
        input_str = "test!@#$%^&*()_+-={}[]|\\:;\"'<>,.?/~`"
        result = security_manager.sanitize_string(input_str)

        # Should remove null bytes and path traversal
        assert "\x00" not in result
        assert "../" not in result

    def test_path_with_dots(self, security_manager):
        """Test path with multiple dots."""
        input_path = "....file.txt"
        result = security_manager.sanitize_path(input_path)

        assert result == "file.txt"

    def test_event_with_all_fields(self, security_manager):
        """Test event with all fields populated."""
        event = TelemetryEvent(
            event_type="test_event",
            timestamp_ns=1234567890,
            cpu_id=3,
            pid=9999,
            data={"key1": "value1", "key2": 123},
            severity=EventSeverity.CRITICAL,
        )

        is_valid, error = security_manager.validate_event(event)

        assert is_valid, f"Valid event was rejected: {error}"
        assert error is None

    def test_event_with_minimal_fields(self, security_manager):
        """Test event with minimal required fields."""
        event = TelemetryEvent(
            event_type="test_event", timestamp_ns=1000000000, cpu_id=0
        )

        is_valid, error = security_manager.validate_event(event)

        assert is_valid, f"Valid minimal event was rejected: {error}"
        assert error is None
