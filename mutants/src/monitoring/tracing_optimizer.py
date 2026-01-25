"""
Distributed Tracing Optimizer

Advanced tracing optimization with:
- Span sampling strategies
- Trace correlation
- Performance analysis
- Root cause analysis
- Distributed latency tracking
"""

import logging
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from enum import Enum
from collections import defaultdict, deque
import numpy as np

logger = logging.getLogger(__name__)


class SamplingStrategy(Enum):
    """Span sampling strategies"""
    ALL = "all"
    NONE = "none"
    RANDOM = "random"
    ADAPTIVE = "adaptive"
    ERROR_BASED = "error_based"


@dataclass
class Span:
    """Distributed trace span"""
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    operation_name: str
    service_name: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "ok"
    error_message: Optional[str] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    logs: List[Dict[str, Any]] = field(default_factory=list)
    
    @property
    def duration_ms(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds() * 1000
        return 0.0


@dataclass
class Trace:
    """Complete trace with all spans"""
    trace_id: str
    spans: List[Span] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def total_duration_ms(self) -> float:
        if not self.spans:
            return 0.0
        start = min(s.start_time for s in self.spans)
        end = max(s.end_time or s.start_time for s in self.spans)
        return (end - start).total_seconds() * 1000
    
    @property
    def span_count(self) -> int:
        return len(self.spans)
    
    @property
    def service_count(self) -> int:
        return len(set(s.service_name for s in self.spans))
    
    @property
    def has_errors(self) -> bool:
        return any(s.status == "error" for s in self.spans)


class SamplingCalculator:
    """Calculates trace sampling decisions"""
    
    def __init__(self, default_rate: float = 0.1):
        self.default_rate = default_rate
        self.latency_buckets = defaultdict(lambda: deque(maxlen=1000))
        self.error_rates = defaultdict(lambda: {"errors": 0, "total": 0})
    
    def should_sample(self, trace_id: str, service_name: str,
                     duration_ms: float, has_error: bool,
                     strategy: SamplingStrategy = SamplingStrategy.ADAPTIVE) -> bool:
        """Determine if trace should be sampled"""
        
        if strategy == SamplingStrategy.ALL:
            return True
        elif strategy == SamplingStrategy.NONE:
            return False
        elif strategy == SamplingStrategy.RANDOM:
            hash_val = int(hashlib.md5(trace_id.encode()).hexdigest(), 16)
            return (hash_val % 100) < (self.default_rate * 100)
        elif strategy == SamplingStrategy.ERROR_BASED:
            return has_error
        elif strategy == SamplingStrategy.ADAPTIVE:
            return self._adaptive_sample(service_name, duration_ms, has_error)
        
        return False
    
    def _adaptive_sample(self, service_name: str, duration_ms: float,
                        has_error: bool) -> bool:
        """Adaptive sampling based on latency and errors"""
        
        self.latency_buckets[service_name].append(duration_ms)
        
        if has_error:
            return True
        
        latencies = list(self.latency_buckets[service_name])
        if len(latencies) < 100:
            return np.random.random() < 0.1
        
        p95 = np.percentile(latencies, 95)
        
        if duration_ms > p95 * 1.5:
            return True
        
        return np.random.random() < 0.05


class LatencyAnalyzer:
    """Analyzes latency patterns in traces"""
    
    def __init__(self):
        self.operation_latencies = defaultdict(lambda: deque(maxlen=5000))
        self.service_latencies = defaultdict(lambda: deque(maxlen=5000))
    
    def record_span_latency(self, operation: str, service: str,
                           duration_ms: float) -> None:
        """Record span latency"""
        self.operation_latencies[operation].append(duration_ms)
        self.service_latencies[service].append(duration_ms)
    
    def get_operation_stats(self, operation: str) -> Dict[str, float]:
        """Get latency stats for operation"""
        latencies = list(self.operation_latencies.get(operation, []))
        if not latencies:
            return {}
        
        arr = np.array(latencies)
        return {
            "count": len(latencies),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99))
        }
    
    def get_service_stats(self, service: str) -> Dict[str, float]:
        """Get latency stats for service"""
        latencies = list(self.service_latencies.get(service, []))
        if not latencies:
            return {}
        
        arr = np.array(latencies)
        return {
            "count": len(latencies),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
            "mean": float(np.mean(arr)),
            "p50": float(np.percentile(arr, 50)),
            "p95": float(np.percentile(arr, 95)),
            "p99": float(np.percentile(arr, 99))
        }


class RootCauseAnalyzer:
    """Analyzes traces to identify root causes"""
    
    def __init__(self):
        self.error_traces: List[Trace] = []
    
    def analyze_error_trace(self, trace: Trace) -> Dict[str, Any]:
        """Analyze error trace for root cause"""
        if not trace.has_errors:
            return {"error": "Trace has no errors"}
        
        error_spans = [s for s in trace.spans if s.status == "error"]
        
        if not error_spans:
            return {"error": "No error spans found"}
        
        root_error = error_spans[0]
        
        affected_downstream = [
            s for s in trace.spans
            if any(s.parent_span_id == es.span_id for es in error_spans)
        ]
        
        return {
            "trace_id": trace.trace_id,
            "root_cause_service": root_error.service_name,
            "root_cause_operation": root_error.operation_name,
            "error_message": root_error.error_message,
            "affected_services": list(set(s.service_name for s in affected_downstream)),
            "error_span_count": len(error_spans),
            "propagation_depth": self._calculate_propagation_depth(trace, root_error),
            "timestamp": datetime.utcnow().isoformat()
        }
    
    def _calculate_propagation_depth(self, trace: Trace, root_span: Span) -> int:
        """Calculate how deep error propagated"""
        depth = 0
        current_parents = {root_span.span_id}
        
        while current_parents:
            next_parents = set()
            for span in trace.spans:
                if span.parent_span_id in current_parents:
                    next_parents.add(span.span_id)
            
            if next_parents:
                depth += 1
                current_parents = next_parents
            else:
                break
        
        return depth
    
    def find_slow_spans(self, trace: Trace, percentile: float = 95) -> List[Span]:
        """Find slow spans in trace"""
        if not trace.spans:
            return []
        
        durations = [s.duration_ms for s in trace.spans if s.duration_ms > 0]
        if not durations:
            return []
        
        threshold = np.percentile(durations, percentile)
        return [s for s in trace.spans if s.duration_ms > threshold]


class TracingOptimizer:
    """Distributed tracing optimizer"""
    
    def __init__(self):
        self.traces: Dict[str, Trace] = {}
        self.sampling_calc = SamplingCalculator()
        self.latency_analyzer = LatencyAnalyzer()
        self.rca = RootCauseAnalyzer()
        self.span_buffer: List[Span] = []
        self.lock = __import__('threading').Lock()
    
    def create_span(self, trace_id: str, span_id: str, operation_name: str,
                   service_name: str, parent_span_id: Optional[str] = None) -> Span:
        """Create new span"""
        span = Span(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            operation_name=operation_name,
            service_name=service_name,
            start_time=datetime.utcnow()
        )
        return span
    
    def end_span(self, span: Span, status: str = "ok",
                error_message: Optional[str] = None) -> None:
        """End span"""
        with self.lock:
            span.end_time = datetime.utcnow()
            span.status = status
            span.error_message = error_message
            
            self.span_buffer.append(span)
            
            self.latency_analyzer.record_span_latency(
                span.operation_name,
                span.service_name,
                span.duration_ms
            )
            
            if len(self.span_buffer) >= 10:
                self._flush_spans()
    
    def _flush_spans(self) -> None:
        """Flush buffered spans to traces"""
        for span in self.span_buffer:
            if span.trace_id not in self.traces:
                self.traces[span.trace_id] = Trace(trace_id=span.trace_id)
            
            self.traces[span.trace_id].spans.append(span)
        
        self.span_buffer.clear()
        
        if len(self.traces) > 100000:
            old_traces = sorted(
                self.traces.items(),
                key=lambda x: x[1].created_at
            )[:50000]
            self.traces = dict(old_traces)
    
    def should_sample_trace(self, trace_id: str, duration_ms: float,
                           has_error: bool, service_name: str = "") -> bool:
        """Determine if trace should be sampled"""
        return self.sampling_calc.should_sample(
            trace_id, service_name, duration_ms, has_error,
            SamplingStrategy.ADAPTIVE
        )
    
    def analyze_trace(self, trace_id: str) -> Dict[str, Any]:
        """Analyze complete trace"""
        with self.lock:
            trace = self.traces.get(trace_id)
            if not trace:
                return {"error": "Trace not found"}
            
            result = {
                "trace_id": trace_id,
                "span_count": trace.span_count,
                "service_count": trace.service_count,
                "total_duration_ms": trace.total_duration_ms,
                "has_errors": trace.has_errors,
                "services": list(set(s.service_name for s in trace.spans))
            }
            
            if trace.has_errors:
                result["root_cause"] = self.rca.analyze_error_trace(trace)
            
            slow_spans = self.rca.find_slow_spans(trace)
            result["slow_spans"] = [
                {
                    "operation": s.operation_name,
                    "service": s.service_name,
                    "duration_ms": s.duration_ms
                }
                for s in slow_spans
            ]
            
            return result
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Get performance report"""
        with self.lock:
            self._flush_spans()
            
            operations = list(self.latency_analyzer.operation_latencies.keys())
            services = list(self.latency_analyzer.service_latencies.keys())
            
            operation_stats = {op: self.latency_analyzer.get_operation_stats(op) for op in operations}
            service_stats = {svc: self.latency_analyzer.get_service_stats(svc) for svc in services}
            
            return {
                "total_traces": len(self.traces),
                "operations": operation_stats,
                "services": service_stats,
                "timestamp": datetime.utcnow().isoformat()
            }


_optimizer = None

def get_tracing_optimizer() -> TracingOptimizer:
    """Get or create singleton optimizer"""
    global _optimizer
    if _optimizer is None:
        _optimizer = TracingOptimizer()
    return _optimizer


__all__ = [
    "SamplingStrategy",
    "Span",
    "Trace",
    "SamplingCalculator",
    "LatencyAnalyzer",
    "RootCauseAnalyzer",
    "TracingOptimizer",
    "get_tracing_optimizer",
]
