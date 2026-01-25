"""
Edge Case Validator and Boundary Test Suite

Comprehensive edge case handling with:
- Boundary value validation
- State machine testing
- Resource limit checks
- Error condition handling
- Concurrency edge cases
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Any, Optional, Callable, Tuple
from datetime import datetime, timedelta
from enum import Enum
import threading

logger = logging.getLogger(__name__)


class EdgeCaseType(Enum):
    """Types of edge cases"""
    BOUNDARY = "boundary"
    STATE = "state"
    RESOURCE = "resource"
    CONCURRENCY = "concurrency"
    TIMING = "timing"
    ERROR = "error"


@dataclass
class EdgeCaseViolation:
    """Edge case violation found"""
    case_type: EdgeCaseType
    description: str
    value: Any
    limit: Any
    severity: str
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


class BoundaryValidator:
    """Validates boundary conditions"""
    
    def __init__(self):
        self.violations: List[EdgeCaseViolation] = []
    
    def check_numeric_bounds(self, value: Any, min_val: Any = None,
                            max_val: Any = None) -> List[EdgeCaseViolation]:
        """Check numeric boundary violations"""
        violations = []
        
        try:
            float_val = float(value)
        except (TypeError, ValueError):
            return violations
        
        if min_val is not None and float_val < float(min_val):
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description=f"Value below minimum",
                value=float_val,
                limit=float(min_val),
                severity="high"
            ))
        
        if max_val is not None and float_val > float(max_val):
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description=f"Value exceeds maximum",
                value=float_val,
                limit=float(max_val),
                severity="high"
            ))
        
        if float_val == 0:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="Zero value - potential division by zero",
                value=float_val,
                limit=0,
                severity="medium"
            ))
        
        self.violations.extend(violations)
        return violations
    
    def check_string_bounds(self, value: str, min_len: int = 0,
                           max_len: int = None) -> List[EdgeCaseViolation]:
        """Check string boundary violations"""
        violations = []
        
        if len(value) < min_len:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="String below minimum length",
                value=len(value),
                limit=min_len,
                severity="high"
            ))
        
        if max_len and len(value) > max_len:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="String exceeds maximum length",
                value=len(value),
                limit=max_len,
                severity="high"
            ))
        
        if value == "":
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="Empty string",
                value="",
                limit="non-empty",
                severity="medium"
            ))
        
        self.violations.extend(violations)
        return violations
    
    def check_collection_bounds(self, collection: Any, min_size: int = 0,
                               max_size: int = None) -> List[EdgeCaseViolation]:
        """Check collection boundary violations"""
        violations = []
        
        try:
            size = len(collection)
        except TypeError:
            return violations
        
        if size < min_size:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="Collection below minimum size",
                value=size,
                limit=min_size,
                severity="high"
            ))
        
        if max_size and size > max_size:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="Collection exceeds maximum size",
                value=size,
                limit=max_size,
                severity="high"
            ))
        
        if size == 0:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.BOUNDARY,
                description="Empty collection",
                value=size,
                limit="non-empty",
                severity="medium"
            ))
        
        self.violations.extend(violations)
        return violations


class StateTransitionValidator:
    """Validates state machine transitions"""
    
    def __init__(self):
        self.valid_transitions: Dict[str, List[str]] = {}
        self.violations: List[EdgeCaseViolation] = []
    
    def define_transitions(self, state: str, allowed_next: List[str]) -> None:
        """Define valid state transitions"""
        self.valid_transitions[state] = allowed_next
    
    def validate_transition(self, current_state: str,
                           next_state: str) -> Optional[EdgeCaseViolation]:
        """Validate state transition"""
        allowed = self.valid_transitions.get(current_state, [])
        
        if next_state not in allowed:
            violation = EdgeCaseViolation(
                case_type=EdgeCaseType.STATE,
                description=f"Invalid state transition",
                value=f"{current_state} -> {next_state}",
                limit=f"allowed: {allowed}",
                severity="critical"
            )
            self.violations.append(violation)
            return violation
        
        return None


class ResourceLimitValidator:
    """Validates resource usage limits"""
    
    def __init__(self):
        self.limits: Dict[str, Dict[str, float]] = {}
        self.current: Dict[str, float] = {}
        self.violations: List[EdgeCaseViolation] = []
    
    def set_limit(self, resource: str, limit_type: str, value: float) -> None:
        """Set resource limit"""
        if resource not in self.limits:
            self.limits[resource] = {}
        self.limits[resource][limit_type] = value
    
    def record_usage(self, resource: str, usage: float) -> List[EdgeCaseViolation]:
        """Record resource usage"""
        violations = []
        self.current[resource] = usage
        
        if resource not in self.limits:
            return violations
        
        limits = self.limits[resource]
        
        if "max" in limits and usage > limits["max"]:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.RESOURCE,
                description=f"Resource exceeds maximum",
                value=usage,
                limit=limits["max"],
                severity="critical"
            ))
        
        if "warning" in limits and usage > limits["warning"]:
            violations.append(EdgeCaseViolation(
                case_type=EdgeCaseType.RESOURCE,
                description=f"Resource exceeds warning threshold",
                value=usage,
                limit=limits["warning"],
                severity="high"
            ))
        
        self.violations.extend(violations)
        return violations


class ConcurrencyValidator:
    """Validates concurrency edge cases"""
    
    def __init__(self):
        self.lock = threading.Lock()
        self.active_threads: Dict[str, int] = {}
        self.violations: List[EdgeCaseViolation] = []
    
    def check_thread_safety(self, operation_name: str,
                           max_concurrent: int = 1) -> Optional[EdgeCaseViolation]:
        """Check for thread safety violations"""
        with self.lock:
            count = self.active_threads.get(operation_name, 0)
            
            if count > max_concurrent:
                violation = EdgeCaseViolation(
                    case_type=EdgeCaseType.CONCURRENCY,
                    description=f"Concurrent operation limit exceeded",
                    value=count,
                    limit=max_concurrent,
                    severity="critical"
                )
                self.violations.append(violation)
                return violation
        
        return None
    
    def start_operation(self, operation_name: str) -> None:
        """Mark operation start"""
        with self.lock:
            self.active_threads[operation_name] = self.active_threads.get(operation_name, 0) + 1
    
    def end_operation(self, operation_name: str) -> None:
        """Mark operation end"""
        with self.lock:
            self.active_threads[operation_name] = max(0, self.active_threads.get(operation_name, 0) - 1)


class TimingValidator:
    """Validates timing-related edge cases"""
    
    def __init__(self):
        self.violations: List[EdgeCaseViolation] = []
    
    def check_timeout(self, start_time: datetime, timeout_seconds: float) -> Optional[EdgeCaseViolation]:
        """Check if operation timed out"""
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        if elapsed > timeout_seconds:
            violation = EdgeCaseViolation(
                case_type=EdgeCaseType.TIMING,
                description="Operation timeout",
                value=elapsed,
                limit=timeout_seconds,
                severity="high"
            )
            self.violations.append(violation)
            return violation
        
        return None
    
    def check_deadline(self, deadline: datetime) -> Optional[EdgeCaseViolation]:
        """Check if deadline passed"""
        if datetime.utcnow() > deadline:
            violation = EdgeCaseViolation(
                case_type=EdgeCaseType.TIMING,
                description="Deadline exceeded",
                value=datetime.utcnow(),
                limit=deadline,
                severity="high"
            )
            self.violations.append(violation)
            return violation
        
        return None


class EdgeCaseValidator:
    """Comprehensive edge case validator"""
    
    def __init__(self):
        self.boundary = BoundaryValidator()
        self.state = StateTransitionValidator()
        self.resource = ResourceLimitValidator()
        self.concurrency = ConcurrencyValidator()
        self.timing = TimingValidator()
        self.all_violations: List[EdgeCaseViolation] = []
    
    def validate_input(self, value: Any, constraints: Dict[str, Any]) -> List[EdgeCaseViolation]:
        """Validate input against constraints"""
        violations = []
        
        if "type" in constraints:
            if not isinstance(value, constraints["type"]):
                violations.append(EdgeCaseViolation(
                    case_type=EdgeCaseType.ERROR,
                    description="Type constraint violated",
                    value=type(value),
                    limit=constraints["type"],
                    severity="high"
                ))
        
        if isinstance(value, (int, float)):
            violations.extend(self.boundary.check_numeric_bounds(
                value,
                constraints.get("min"),
                constraints.get("max")
            ))
        elif isinstance(value, str):
            violations.extend(self.boundary.check_string_bounds(
                value,
                constraints.get("min_len", 0),
                constraints.get("max_len")
            ))
        elif isinstance(value, (list, dict, set)):
            violations.extend(self.boundary.check_collection_bounds(
                value,
                constraints.get("min_size", 0),
                constraints.get("max_size")
            ))
        
        self.all_violations.extend(violations)
        return violations
    
    def get_violation_summary(self) -> Dict[str, Any]:
        """Get summary of all violations"""
        by_type = {}
        by_severity = {}
        
        for violation in self.all_violations:
            case_type = violation.case_type.value
            by_type[case_type] = by_type.get(case_type, 0) + 1
            
            by_severity[violation.severity] = by_severity.get(violation.severity, 0) + 1
        
        return {
            "total_violations": len(self.all_violations),
            "by_type": by_type,
            "by_severity": by_severity,
            "critical_count": by_severity.get("critical", 0),
            "high_count": by_severity.get("high", 0),
            "timestamp": datetime.utcnow().isoformat()
        }


__all__ = [
    "EdgeCaseType",
    "EdgeCaseViolation",
    "BoundaryValidator",
    "StateTransitionValidator",
    "ResourceLimitValidator",
    "ConcurrencyValidator",
    "TimingValidator",
    "EdgeCaseValidator",
]
