"""
Unit tests for src.network.ebpf.metrics.sanitizer.MetricSanitizer.

Covers: default rules, validate(), sanitize(), type mismatch, out-of-range,
unknown metrics, and custom validation rules.
"""
import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import pytest

from src.network.ebpf.metrics.models import MetricValidationStatus
from src.network.ebpf.metrics.sanitizer import MetricSanitizer


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def sanitizer():
    """Default MetricSanitizer with built-in rules."""
    return MetricSanitizer()


# ---------------------------------------------------------------------------
# Construction
# ---------------------------------------------------------------------------


class TestMetricSanitizerInit:
    def test_default_rules_present(self, sanitizer):
        rules = sanitizer.validation_rules
        assert "packet_counters" in rules
        assert "latency_ms" in rules
        assert "bytes_transferred" in rules
        assert "interface_count" in rules

    def test_custom_rules_override_defaults(self):
        custom = {"my_metric": {"min": 0, "max": 10, "type": int}}
        s = MetricSanitizer(validation_rules=custom)
        assert "my_metric" in s.validation_rules
        # Default rules should NOT be present when custom rules provided
        assert "packet_counters" not in s.validation_rules

    def test_none_rules_uses_defaults(self):
        s = MetricSanitizer(validation_rules=None)
        assert "packet_counters" in s.validation_rules


# ---------------------------------------------------------------------------
# validate() — VALID cases
# ---------------------------------------------------------------------------


class TestMetricSanitizerValidateValid:
    def test_packet_counters_valid_int(self, sanitizer):
        result = sanitizer.validate("packet_counters", 1000)
        assert result.status == MetricValidationStatus.VALID

    def test_packet_counters_boundary_zero(self, sanitizer):
        result = sanitizer.validate("packet_counters", 0)
        assert result.status == MetricValidationStatus.VALID

    def test_packet_counters_boundary_max(self, sanitizer):
        result = sanitizer.validate("packet_counters", 10**12)
        assert result.status == MetricValidationStatus.VALID

    def test_latency_ms_valid_int(self, sanitizer):
        result = sanitizer.validate("latency_ms", 500)
        assert result.status == MetricValidationStatus.VALID

    def test_latency_ms_valid_float(self, sanitizer):
        result = sanitizer.validate("latency_ms", 12.5)
        assert result.status == MetricValidationStatus.VALID

    def test_bytes_transferred_valid(self, sanitizer):
        result = sanitizer.validate("bytes_transferred", 1024 * 1024)
        assert result.status == MetricValidationStatus.VALID

    def test_interface_count_valid(self, sanitizer):
        result = sanitizer.validate("interface_count", 4)
        assert result.status == MetricValidationStatus.VALID

    def test_result_name_preserved(self, sanitizer):
        result = sanitizer.validate("packet_counters", 100)
        assert result.name == "packet_counters"

    def test_result_value_preserved(self, sanitizer):
        result = sanitizer.validate("packet_counters", 42)
        assert result.value == 42


# ---------------------------------------------------------------------------
# validate() — TYPE_MISMATCH cases
# ---------------------------------------------------------------------------


class TestMetricSanitizerTypeMismatch:
    def test_packet_counters_string_is_type_mismatch(self, sanitizer):
        result = sanitizer.validate("packet_counters", "bad")
        assert result.status == MetricValidationStatus.TYPE_MISMATCH

    def test_packet_counters_float_is_type_mismatch(self, sanitizer):
        # packet_counters rule requires int, not float
        result = sanitizer.validate("packet_counters", 1.5)
        assert result.status == MetricValidationStatus.TYPE_MISMATCH

    def test_interface_count_float_is_type_mismatch(self, sanitizer):
        result = sanitizer.validate("interface_count", 2.0)
        assert result.status == MetricValidationStatus.TYPE_MISMATCH

    def test_type_mismatch_message_not_none(self, sanitizer):
        result = sanitizer.validate("packet_counters", "x")
        assert result.message is not None


# ---------------------------------------------------------------------------
# validate() — OUT_OF_RANGE cases
# ---------------------------------------------------------------------------


class TestMetricSanitizerOutOfRange:
    def test_packet_counters_negative_is_out_of_range(self, sanitizer):
        result = sanitizer.validate("packet_counters", -1)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_packet_counters_exceeds_max_is_out_of_range(self, sanitizer):
        result = sanitizer.validate("packet_counters", 10**12 + 1)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_latency_ms_exceeds_60000_is_out_of_range(self, sanitizer):
        result = sanitizer.validate("latency_ms", 60001)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_interface_count_above_100_is_out_of_range(self, sanitizer):
        result = sanitizer.validate("interface_count", 101)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE

    def test_out_of_range_provides_range_min(self, sanitizer):
        result = sanitizer.validate("interface_count", 200)
        assert result.range_min == 0

    def test_out_of_range_provides_range_max(self, sanitizer):
        result = sanitizer.validate("interface_count", 200)
        assert result.range_max == 100


# ---------------------------------------------------------------------------
# validate() — unknown / pattern-matched metrics
# ---------------------------------------------------------------------------


class TestMetricSanitizerPatternMatch:
    def test_unknown_metric_with_no_rules_passes_with_valid_number(self, sanitizer):
        # Unknown metric with no matching pattern — uses default expected_types=(int, float)
        # and no range, so any numeric value is VALID
        result = sanitizer.validate("totally_unknown_metric", 999)
        assert result.status == MetricValidationStatus.VALID

    def test_name_containing_packet_uses_packet_counters_rules(self, sanitizer):
        # "my_packet_count" contains "packet" → uses packet_counters rule (int only)
        result = sanitizer.validate("my_packet_count", 1.5)
        assert result.status == MetricValidationStatus.TYPE_MISMATCH

    def test_name_containing_latency_uses_latency_rules(self, sanitizer):
        # "network_latency" contains "latency" → uses latency_ms rule (int|float, 0-60000)
        result = sanitizer.validate("network_latency", 70000)
        assert result.status == MetricValidationStatus.OUT_OF_RANGE


# ---------------------------------------------------------------------------
# sanitize()
# ---------------------------------------------------------------------------


class TestMetricSanitizerSanitize:
    def test_all_valid_metrics_returned(self, sanitizer):
        metrics = {"packet_counters": 100, "interface_count": 2}
        valid, results = sanitizer.sanitize(metrics)
        assert "packet_counters" in valid
        assert "interface_count" in valid

    def test_invalid_metrics_excluded_from_valid(self, sanitizer):
        metrics = {"packet_counters": -1, "interface_count": 2}
        valid, results = sanitizer.sanitize(metrics)
        assert "packet_counters" not in valid
        assert "interface_count" in valid

    def test_validation_results_length_matches_input(self, sanitizer):
        metrics = {"packet_counters": 100, "latency_ms": 5.0, "interface_count": 3}
        valid, results = sanitizer.sanitize(metrics)
        assert len(results) == 3

    def test_sanitize_empty_dict(self, sanitizer):
        valid, results = sanitizer.sanitize({})
        assert valid == {}
        assert results == []

    def test_all_invalid_returns_empty_valid(self, sanitizer):
        metrics = {"packet_counters": -1, "interface_count": 999}
        valid, results = sanitizer.sanitize(metrics)
        assert valid == {}
        assert len(results) == 2

    def test_sanitize_returns_tuple(self, sanitizer):
        result = sanitizer.sanitize({"packet_counters": 1})
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_custom_rules_applied_in_sanitize(self):
        custom = {"speed": {"min": 0, "max": 100, "type": int}}
        s = MetricSanitizer(validation_rules=custom)
        valid, results = s.sanitize({"speed": 50, "speed_too_high": 200})
        # "speed" is directly in rules → valid
        assert "speed" in valid
