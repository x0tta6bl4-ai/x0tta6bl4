"""
Unit tests for src.network.ebpf.metrics.exceptions.

Tests exception classes: EBPFMetricsError, MapReadError, BpftoolError,
PrometheusExportError, MetricRegistrationError, ParseError, MetricsTimeoutError.
"""
import os
import time

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import pytest

from src.network.ebpf.metrics.exceptions import (
    BpftoolError,
    EBPFMetricsError,
    MapReadError,
    MetricRegistrationError,
    MetricsTimeoutError,
    ParseError,
    PrometheusExportError,
)


# ---------------------------------------------------------------------------
# EBPFMetricsError — base class
# ---------------------------------------------------------------------------


class TestEBPFMetricsError:
    def test_basic_creation_message(self):
        err = EBPFMetricsError("something went wrong")
        assert str(err) == "something went wrong"

    def test_context_defaults_to_empty_dict(self):
        err = EBPFMetricsError("no context")
        assert err.context == {}

    def test_context_preserved_when_provided(self):
        ctx = {"map_id": 42, "operation": "read"}
        err = EBPFMetricsError("read failed", context=ctx)
        assert err.context == {"map_id": 42, "operation": "read"}

    def test_timestamp_is_set_on_creation(self):
        before = time.time()
        err = EBPFMetricsError("ts test")
        after = time.time()
        assert before <= err.timestamp <= after

    def test_to_dict_keys(self):
        err = EBPFMetricsError("dict test", context={"k": "v"})
        d = err.to_dict()
        assert set(d.keys()) == {"error_type", "message", "context", "timestamp"}

    def test_to_dict_error_type_is_class_name(self):
        err = EBPFMetricsError("base")
        assert err.to_dict()["error_type"] == "EBPFMetricsError"

    def test_to_dict_message_matches_str(self):
        err = EBPFMetricsError("hello")
        assert err.to_dict()["message"] == "hello"

    def test_to_dict_context_matches(self):
        ctx = {"x": 1}
        err = EBPFMetricsError("ctx", context=ctx)
        assert err.to_dict()["context"] == ctx

    def test_to_dict_timestamp_matches_attr(self):
        err = EBPFMetricsError("ts")
        assert err.to_dict()["timestamp"] == err.timestamp

    def test_is_exception_subclass(self):
        err = EBPFMetricsError("ex")
        assert isinstance(err, Exception)

    def test_none_context_normalised_to_empty_dict(self):
        err = EBPFMetricsError("none ctx", context=None)
        assert err.context == {}


# ---------------------------------------------------------------------------
# MapReadError
# ---------------------------------------------------------------------------


class TestMapReadError:
    def test_is_ebpf_metrics_error_subclass(self):
        err = MapReadError("map error")
        assert isinstance(err, EBPFMetricsError)

    def test_message_preserved(self):
        err = MapReadError("map read failed")
        assert str(err) == "map read failed"

    def test_to_dict_error_type_is_map_read_error(self):
        err = MapReadError("map")
        assert err.to_dict()["error_type"] == "MapReadError"

    def test_context_preserved(self):
        err = MapReadError("ctx", context={"map_id": 7})
        assert err.context["map_id"] == 7


# ---------------------------------------------------------------------------
# BpftoolError
# ---------------------------------------------------------------------------


class TestBpftoolError:
    def _make(self, **kwargs):
        defaults = {
            "message": "bpftool failed",
            "command": ["bpftool", "map", "show"],
        }
        defaults.update(kwargs)
        return BpftoolError(**defaults)

    def test_is_ebpf_metrics_error_subclass(self):
        err = self._make()
        assert isinstance(err, EBPFMetricsError)

    def test_message_preserved(self):
        err = self._make(message="cmd failed")
        assert str(err) == "cmd failed"

    def test_command_attribute_stored(self):
        cmd = ["bpftool", "prog", "list"]
        err = self._make(command=cmd)
        assert err.command == cmd

    def test_stderr_default_empty_string(self):
        err = self._make()
        assert err.stderr == ""

    def test_stderr_custom_value(self):
        err = self._make(stderr="some error output")
        assert err.stderr == "some error output"

    def test_returncode_default_is_minus_one(self):
        err = self._make()
        assert err.returncode == -1

    def test_returncode_custom_value(self):
        err = self._make(returncode=2)
        assert err.returncode == 2

    def test_to_dict_error_type_is_bpftool_error(self):
        err = self._make()
        assert err.to_dict()["error_type"] == "BpftoolError"

    def test_context_contains_command_string(self):
        cmd = ["bpftool", "map", "show"]
        err = self._make(command=cmd)
        assert err.context["command"] == "bpftool map show"

    def test_context_contains_stderr(self):
        err = self._make(stderr="permission denied")
        assert err.context["stderr"] == "permission denied"

    def test_context_contains_returncode(self):
        err = self._make(returncode=127)
        assert err.context["returncode"] == 127


# ---------------------------------------------------------------------------
# Simple subclasses: PrometheusExportError, MetricRegistrationError,
# ParseError, MetricsTimeoutError
# ---------------------------------------------------------------------------


class TestSimpleSubclasses:
    @pytest.mark.parametrize(
        "cls",
        [
            PrometheusExportError,
            MetricRegistrationError,
            ParseError,
            MetricsTimeoutError,
        ],
    )
    def test_is_ebpf_metrics_error_subclass(self, cls):
        err = cls("test")
        assert isinstance(err, EBPFMetricsError)

    @pytest.mark.parametrize(
        "cls",
        [
            PrometheusExportError,
            MetricRegistrationError,
            ParseError,
            MetricsTimeoutError,
        ],
    )
    def test_message_preserved(self, cls):
        err = cls("specific message")
        assert str(err) == "specific message"

    @pytest.mark.parametrize(
        "cls",
        [
            PrometheusExportError,
            MetricRegistrationError,
            ParseError,
            MetricsTimeoutError,
        ],
    )
    def test_to_dict_error_type_matches_class_name(self, cls):
        err = cls("msg")
        assert err.to_dict()["error_type"] == cls.__name__

    @pytest.mark.parametrize(
        "cls",
        [
            PrometheusExportError,
            MetricRegistrationError,
            ParseError,
            MetricsTimeoutError,
        ],
    )
    def test_context_passed_through(self, cls):
        ctx = {"detail": "extra info"}
        err = cls("msg", context=ctx)
        assert err.context == ctx

    def test_can_be_raised_and_caught_as_base(self):
        with pytest.raises(EBPFMetricsError):
            raise PrometheusExportError("prometheus down")

    def test_parse_error_can_be_raised_and_caught(self):
        with pytest.raises(ParseError):
            raise ParseError("bad json")

    def test_timeout_error_can_be_raised_and_caught(self):
        with pytest.raises(MetricsTimeoutError):
            raise MetricsTimeoutError("timed out")
