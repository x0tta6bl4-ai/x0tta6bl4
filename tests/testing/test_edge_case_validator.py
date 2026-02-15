from datetime import datetime, timedelta

import pytest

from src.testing.edge_case_validator import (BoundaryValidator,
                                             ConcurrencyValidator,
                                             EdgeCaseType, EdgeCaseValidator,
                                             ResourceLimitValidator,
                                             StateTransitionValidator,
                                             TimingValidator)


class TestBoundaryValidator:
    def test_numeric_bounds_valid(self):
        validator = BoundaryValidator()
        violations = validator.check_numeric_bounds(50, min_val=0, max_val=100)
        assert len(violations) == 0

    def test_numeric_bounds_below_min(self):
        validator = BoundaryValidator()
        violations = validator.check_numeric_bounds(-10, min_val=0, max_val=100)
        assert len(violations) > 0
        assert violations[0].case_type == EdgeCaseType.BOUNDARY

    def test_numeric_bounds_above_max(self):
        validator = BoundaryValidator()
        violations = validator.check_numeric_bounds(150, min_val=0, max_val=100)
        assert len(violations) > 0

    def test_zero_value_detection(self):
        validator = BoundaryValidator()
        violations = validator.check_numeric_bounds(0, min_val=0, max_val=100)
        assert any(
            v.description == "Zero value - potential division by zero"
            for v in violations
        )

    def test_string_bounds_valid(self):
        validator = BoundaryValidator()
        violations = validator.check_string_bounds("hello", min_len=0, max_len=10)
        assert len(violations) == 0

    def test_string_bounds_too_short(self):
        validator = BoundaryValidator()
        violations = validator.check_string_bounds("hi", min_len=5)
        assert len(violations) > 0

    def test_string_bounds_too_long(self):
        validator = BoundaryValidator()
        violations = validator.check_string_bounds("hello world", min_len=0, max_len=5)
        assert len(violations) > 0

    def test_empty_string_detection(self):
        validator = BoundaryValidator()
        violations = validator.check_string_bounds("", min_len=0)
        assert any(v.description == "Empty string" for v in violations)


class TestStateTransitionValidator:
    def test_valid_transition(self):
        validator = StateTransitionValidator()
        validator.define_transitions("started", ["running", "stopped"])

        violation = validator.validate_transition("started", "running")
        assert violation is None

    def test_invalid_transition(self):
        validator = StateTransitionValidator()
        validator.define_transitions("started", ["running"])

        violation = validator.validate_transition("started", "paused")
        assert violation is not None
        assert violation.case_type == EdgeCaseType.STATE


class TestResourceLimitValidator:
    def test_set_limit(self):
        validator = ResourceLimitValidator()
        validator.set_limit("memory", "max", 1024)
        assert "memory" in validator.limits

    def test_usage_within_limit(self):
        validator = ResourceLimitValidator()
        validator.set_limit("memory", "max", 1024)

        violations = validator.record_usage("memory", 512)
        assert len(violations) == 0

    def test_usage_exceeds_max(self):
        validator = ResourceLimitValidator()
        validator.set_limit("memory", "max", 1024)

        violations = validator.record_usage("memory", 2048)
        assert len(violations) > 0
        assert violations[0].case_type == EdgeCaseType.RESOURCE


class TestTimingValidator:
    def test_operation_within_timeout(self):
        validator = TimingValidator()
        start = datetime.utcnow()
        violation = validator.check_timeout(start, 5.0)
        assert violation is None

    def test_operation_timeout(self):
        validator = TimingValidator()
        start = datetime.utcnow() - timedelta(seconds=10)
        violation = validator.check_timeout(start, 5.0)
        assert violation is not None
        assert violation.case_type == EdgeCaseType.TIMING


class TestEdgeCaseValidator:
    def test_validate_integer_input(self):
        validator = EdgeCaseValidator()
        violations = validator.validate_input(50, {"type": int, "min": 0, "max": 100})
        assert len(violations) == 0

    def test_validate_numeric_constraints(self):
        validator = EdgeCaseValidator()
        violations = validator.validate_input(150, {"type": int, "min": 0, "max": 100})
        assert len(violations) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
