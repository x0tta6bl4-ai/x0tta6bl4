"""
Pytest configuration and fixtures for eBPF telemetry module tests.

This module provides:
- Shared fixtures for all tests
- Mock objects for kernel interaction
- Test configuration
- Utility functions
"""

import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, Mock, PropertyMock, patch

import pytest

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


# ============================================================================
# Configuration
# ============================================================================


def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: marks tests as unit tests")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line(
        "markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')"
    )
    config.addinivalue_line(
        "markers", "requires_root: marks tests that require root privileges"
    )


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def telemetry_config():
    """Provide a default telemetry configuration for testing."""
    from telemetry_module import TelemetryConfig

    return TelemetryConfig(
        collection_interval=0.1,  # Fast for tests
        batch_size=10,
        max_queue_size=100,
        max_workers=2,
        read_timeout=1.0,
        poll_timeout=10,
        prometheus_port=19090,  # Different port for tests
        prometheus_host="127.0.0.1",
        enable_validation=True,
        enable_sanitization=True,
        max_metric_value=1e12,
        sanitize_paths=True,
        max_retries=2,
        retry_delay=0.1,
        enable_fallback=True,
        log_level="DEBUG",
        log_events=False,
    )


@pytest.fixture
def mock_bpf_program():
    """Provide a mock BPF program for testing."""
    mock_bpf = MagicMock()

    # Mock map access
    mock_map = MagicMock()
    mock_map.items.return_value = [
        (b"key1", {"value": 42}),
        (b"key2", {"value": 100}),
    ]

    # Mock __getitem__ for map access
    mock_bpf.__getitem__ = Mock(return_value=mock_map)

    # Mock dir() for map discovery
    mock_bpf.__dir__ = Mock(
        return_value=["[process_map]", "[system_metrics_map]", "[perf_events]"]
    )

    return mock_bpf_program


@pytest.fixture
def mock_bpf_program_with_maps():
    """Provide a mock BPF program with multiple maps."""
    mock_bpf = MagicMock()

    # Create mock maps
    process_map = MagicMock()
    process_map.items.return_value = [
        (123, {"cpu_time_ns": 1000000, "context_switches": 10}),
        (456, {"cpu_time_ns": 2000000, "context_switches": 20}),
    ]

    system_map = MagicMock()
    system_map.__getitem__ = Mock(
        return_value={
            "total_context_switches": 1000,
            "total_syscalls": 5000,
            "total_memory_allocs": 10000,
            "total_io_ops": 500,
        }
    )

    # Mock __getitem__ to return appropriate map
    def getitem_side_effect(key):
        if "process" in key.lower():
            return process_map
        elif "system" in key.lower():
            return system_map
        return MagicMock()

    mock_bpf.__getitem__ = Mock(side_effect=getitem_side_effect)

    return mock_bpf_program


@pytest.fixture
def mock_prometheus_registry():
    """Provide a mock Prometheus registry for testing."""
    from prometheus_client import CollectorRegistry

    registry = CollectorRegistry()
    return registry


@pytest.fixture
def mock_subprocess():
    """Provide a mock subprocess module for testing."""
    with patch("subprocess.run") as mock_run:
        yield mock_run


@pytest.fixture
def mock_time():
    """Provide a mock time module for testing."""
    with patch("time.time") as mock_time_func:
        mock_time_func.return_value = 1000.0
        yield mock_time_func


@pytest.fixture
def mock_threading():
    """Provide a mock threading module for testing."""
    with patch("threading.Thread") as mock_thread:
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance
        yield mock_thread


# ============================================================================
# Mock BCC Module
# ============================================================================


class MockBCC:
    """Mock BCC module for testing without root privileges."""

    def __init__(self, *args, **kwargs):
        self.maps = {}
        self.programs = {}
        self.loaded = False

    def __getitem__(self, key):
        """Mock map access."""
        return self.maps.get(key, MagicMock())

    def __setitem__(self, key, value):
        """Mock map creation."""
        self.maps[key] = value

    def get_table(self, name):
        """Mock table access."""
        return self.maps.get(name, MagicMock())

    def load_func(self, name, func_type):
        """Mock function loading."""
        return MagicMock()

    def attach(self, *args, **kwargs):
        """Mock attachment."""
        return True

    def cleanup(self):
        """Mock cleanup."""
        self.maps.clear()
        self.loaded = False


@pytest.fixture
def mock_bcc():
    """Provide a mock BCC module."""
    with patch("telemetry_module.BCC", MockBCC):
        yield MockBCC


# ============================================================================
# Mock bpftool
# ============================================================================


class MockBpftool:
    """Mock bpftool for testing."""

    def __init__(self, available=True):
        self.available = available
        self.maps = {}
        self.call_count = 0

    def list_maps(self):
        """Mock list maps."""
        self.call_count += 1
        return [
            {"id": 1, "name": "process_map", "type": "hash", "max_entries": 1024},
            {"id": 2, "name": "system_metrics_map", "type": "array", "max_entries": 1},
        ]

    def read_map(self, map_name):
        """Mock read map."""
        self.call_count += 1
        if map_name == "process_map":
            return {
                "data": [
                    {"key": [123], "value": {"cpu_time_ns": 1000000}},
                    {"key": [456], "value": {"cpu_time_ns": 2000000}},
                ]
            }
        elif map_name == "system_metrics_map":
            return {"data": [{"key": [0], "value": {"total_context_switches": 1000}}]}
        return {"data": []}


@pytest.fixture
def mock_bpftool():
    """Provide a mock bpftool."""
    return MockBpftool(available=True)


# ============================================================================
# Mock Perf Buffer
# ============================================================================


class MockPerfBuffer:
    """Mock perf buffer for testing."""

    def __init__(self):
        self.events = []
        self.running = False
        self.handlers = []

    def open_perf_buffer(self, callback):
        """Mock open perf buffer."""
        self.handlers.append(callback)

    def poll(self, timeout=100):
        """Mock poll."""
        if self.running and self.events:
            event = self.events.pop(0)
            for handler in self.handlers:
                handler(0, event, len(event))

    def add_event(self, event):
        """Add event for testing."""
        self.events.append(event)

    def start(self):
        """Start mock perf buffer."""
        self.running = True

    def stop(self):
        """Stop mock perf buffer."""
        self.running = False


@pytest.fixture
def mock_perf_buffer():
    """Provide a mock perf buffer."""
    return MockPerfBuffer()


# ============================================================================
# Test Data
# ============================================================================


@pytest.fixture
def sample_metrics():
    """Provide sample metrics for testing."""
    return {
        "performance_monitor": {
            "process_map_123_cpu_time_ns": 1000000,
            "process_map_123_context_switches": 10,
            "system_metrics_map_0_total_context_switches": 1000,
            "system_metrics_map_0_total_syscalls": 5000,
        },
        "network_monitor": {
            "system_network_map_0_total_packets_ingress": 10000,
            "system_network_map_0_total_packets_egress": 5000,
            "system_network_map_0_active_connections": 50,
        },
        "security_monitor": {
            "system_security_map_0_total_connection_attempts": 100,
            "system_security_map_0_failed_auth_attempts": 5,
        },
    }


@pytest.fixture
def sample_events():
    """Provide sample events for testing."""
    from telemetry_module import EventSeverity, TelemetryEvent

    return [
        TelemetryEvent(
            event_type="security_event",
            timestamp_ns=1000000000,
            cpu_id=0,
            pid=1234,
            data={"type": "file_access", "filename": "/etc/passwd"},
            severity=EventSeverity.HIGH,
        ),
        TelemetryEvent(
            event_type="performance_event",
            timestamp_ns=1000001000,
            cpu_id=1,
            pid=5678,
            data={"type": "context_switch"},
            severity=EventSeverity.INFO,
        ),
    ]


# ============================================================================
# Utility Functions
# ============================================================================


def assert_metric_exists(metrics, metric_name):
    """Assert that a metric exists in the metrics dictionary."""
    assert metric_name in metrics, f"Metric {metric_name} not found in metrics"


def assert_metric_value(metrics, metric_name, expected_value, tolerance=0.01):
    """Assert that a metric has the expected value."""
    assert metric_name in metrics, f"Metric {metric_name} not found"
    actual_value = metrics[metric_name]
    if isinstance(expected_value, float):
        assert (
            abs(actual_value - expected_value) <= tolerance
        ), f"Metric {metric_name}: expected {expected_value}, got {actual_value}"
    else:
        assert (
            actual_value == expected_value
        ), f"Metric {metric_name}: expected {expected_value}, got {actual_value}"


def wait_for_condition(condition, timeout=5.0, interval=0.1):
    """Wait for a condition to become true."""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition():
            return True
        time.sleep(interval)
    return False


# ============================================================================
# Test Scenarios
# ============================================================================


class TestScenarios:
    """Common test scenarios for eBPF telemetry module."""

    @staticmethod
    def normal_operation():
        """Normal operation scenario."""
        return {
            "description": "Normal operation with all components working",
            "expected": "success",
        }

    @staticmethod
    def bcc_unavailable():
        """BCC unavailable scenario."""
        return {
            "description": "BCC not available, fallback to bpftool",
            "expected": "degraded",
        }

    @staticmethod
    def bpftool_unavailable():
        """bpftool unavailable scenario."""
        return {"description": "Both BCC and bpftool unavailable", "expected": "error"}

    @staticmethod
    def high_load():
        """High load scenario."""
        return {
            "description": "High load with many events",
            "expected": "success_with_delay",
        }

    @staticmethod
    def invalid_data():
        """Invalid data scenario."""
        return {"description": "Invalid metric data", "expected": "validation_error"}

    @staticmethod
    def security_event():
        """Security event scenario."""
        return {"description": "High severity security event", "expected": "alert"}


# ============================================================================
# Performance Test Helpers
# ============================================================================


class PerformanceTestHelper:
    """Helper for performance testing."""

    @staticmethod
    def measure_execution_time(func, *args, **kwargs):
        """Measure execution time of a function."""
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        return result, end_time - start_time

    @staticmethod
    def assert_performance(execution_time, max_expected_time):
        """Assert that execution time is within expected bounds."""
        assert (
            execution_time <= max_expected_time
        ), f"Execution time {execution_time}s exceeds maximum {max_expected_time}s"

    @staticmethod
    def benchmark_function(func, iterations=100, *args, **kwargs):
        """Benchmark a function over multiple iterations."""
        times = []
        for _ in range(iterations):
            _, duration = PerformanceTestHelper.measure_execution_time(
                func, *args, **kwargs
            )
            times.append(duration)

        return {
            "min": min(times),
            "max": max(times),
            "avg": sum(times) / len(times),
            "p50": sorted(times)[len(times) // 2],
            "p95": sorted(times)[int(len(times) * 0.95)],
            "p99": sorted(times)[int(len(times) * 0.99)],
        }


# ============================================================================
# Error Test Helpers
# ============================================================================


class ErrorTestHelper:
    """Helper for error testing."""

    @staticmethod
    def assert_raises(exception_type, func, *args, **kwargs):
        """Assert that a function raises a specific exception."""
        with pytest.raises(exception_type):
            func(*args, **kwargs)

    @staticmethod
    def assert_no_exception(func, *args, **kwargs):
        """Assert that a function does not raise an exception."""
        try:
            func(*args, **kwargs)
        except Exception as e:
            pytest.fail(f"Unexpected exception: {e}")

    @staticmethod
    def assert_logs_error(caplog, error_message):
        """Assert that an error message was logged."""
        assert any(
            error_message in record.message
            for record in caplog.records
            if record.levelname == "ERROR"
        ), f"Error message '{error_message}' not found in logs"

    @staticmethod
    def assert_logs_warning(caplog, warning_message):
        """Assert that a warning message was logged."""
        assert any(
            warning_message in record.message
            for record in caplog.records
            if record.levelname == "WARNING"
        ), f"Warning message '{warning_message}' not found in logs"
