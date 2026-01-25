"""
Self-Learning MAPE-K Threshold Optimization

Automatically learns optimal thresholds from historical metrics data.
Provides anomaly detection, trend analysis, and dynamic threshold adaptation.
"""

import logging
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import OrderedDict, deque
from datetime import datetime, timedelta
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


class ThresholdStrategy(Enum):
    """Strategies for threshold calculation"""
    PERCENTILE = "percentile"
    SIGMA = "sigma"
    IQR = "iqr"
    ADAPTIVE = "adaptive"


@dataclass
class MetricPoint:
    """Single metric measurement"""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class ThresholdRecommendation:
    """Threshold recommendation with confidence"""
    parameter: str
    recommended_value: float
    confidence: float
    strategy: ThresholdStrategy
    reasoning: str
    supporting_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class MetricStatistics:
    """Statistics for a metric"""
    mean: float
    median: float
    std_dev: float
    min_value: float
    max_value: float
    p25: float
    p75: float
    p90: float
    p95: float
    p99: float
    data_points: int
    timestamp: float


class MetricsBuffer:
    """Circular buffer for metric time series"""
    
    def xǁMetricsBufferǁ__init____mutmut_orig(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_1(self, parameter: str, max_points: int = 10001):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_2(self, parameter: str, max_points: int = 10000):
        self.parameter = None
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_3(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = None
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_4(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = None
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_5(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=None)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_6(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = ""
        self.last_stats_update: float = 0
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_7(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = None
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_8(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 1
        self.stats_cache_interval = 60
    
    def xǁMetricsBufferǁ__init____mutmut_9(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = None
    
    def xǁMetricsBufferǁ__init____mutmut_10(self, parameter: str, max_points: int = 10000):
        self.parameter = parameter
        self.max_points = max_points
        self.buffer: deque = deque(maxlen=max_points)
        self.last_stats: Optional[MetricStatistics] = None
        self.last_stats_update: float = 0
        self.stats_cache_interval = 61
    
    xǁMetricsBufferǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMetricsBufferǁ__init____mutmut_1': xǁMetricsBufferǁ__init____mutmut_1, 
        'xǁMetricsBufferǁ__init____mutmut_2': xǁMetricsBufferǁ__init____mutmut_2, 
        'xǁMetricsBufferǁ__init____mutmut_3': xǁMetricsBufferǁ__init____mutmut_3, 
        'xǁMetricsBufferǁ__init____mutmut_4': xǁMetricsBufferǁ__init____mutmut_4, 
        'xǁMetricsBufferǁ__init____mutmut_5': xǁMetricsBufferǁ__init____mutmut_5, 
        'xǁMetricsBufferǁ__init____mutmut_6': xǁMetricsBufferǁ__init____mutmut_6, 
        'xǁMetricsBufferǁ__init____mutmut_7': xǁMetricsBufferǁ__init____mutmut_7, 
        'xǁMetricsBufferǁ__init____mutmut_8': xǁMetricsBufferǁ__init____mutmut_8, 
        'xǁMetricsBufferǁ__init____mutmut_9': xǁMetricsBufferǁ__init____mutmut_9, 
        'xǁMetricsBufferǁ__init____mutmut_10': xǁMetricsBufferǁ__init____mutmut_10
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMetricsBufferǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMetricsBufferǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMetricsBufferǁ__init____mutmut_orig)
    xǁMetricsBufferǁ__init____mutmut_orig.__name__ = 'xǁMetricsBufferǁ__init__'
    
    def xǁMetricsBufferǁadd_point__mutmut_orig(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_1(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is not None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_2(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = None
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_3(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = None
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_4(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=None,
            value=value,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_5(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=None,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_6(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=None
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_7(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            value=value,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_8(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            labels=labels or {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_9(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_10(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels and {}
        )
        self.buffer.append(point)
    
    def xǁMetricsBufferǁadd_point__mutmut_11(self, value: float, timestamp: Optional[float] = None, 
                  labels: Optional[Dict[str, str]] = None):
        if timestamp is None:
            timestamp = time.time()
        
        point = MetricPoint(
            timestamp=timestamp,
            value=value,
            labels=labels or {}
        )
        self.buffer.append(None)
    
    xǁMetricsBufferǁadd_point__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMetricsBufferǁadd_point__mutmut_1': xǁMetricsBufferǁadd_point__mutmut_1, 
        'xǁMetricsBufferǁadd_point__mutmut_2': xǁMetricsBufferǁadd_point__mutmut_2, 
        'xǁMetricsBufferǁadd_point__mutmut_3': xǁMetricsBufferǁadd_point__mutmut_3, 
        'xǁMetricsBufferǁadd_point__mutmut_4': xǁMetricsBufferǁadd_point__mutmut_4, 
        'xǁMetricsBufferǁadd_point__mutmut_5': xǁMetricsBufferǁadd_point__mutmut_5, 
        'xǁMetricsBufferǁadd_point__mutmut_6': xǁMetricsBufferǁadd_point__mutmut_6, 
        'xǁMetricsBufferǁadd_point__mutmut_7': xǁMetricsBufferǁadd_point__mutmut_7, 
        'xǁMetricsBufferǁadd_point__mutmut_8': xǁMetricsBufferǁadd_point__mutmut_8, 
        'xǁMetricsBufferǁadd_point__mutmut_9': xǁMetricsBufferǁadd_point__mutmut_9, 
        'xǁMetricsBufferǁadd_point__mutmut_10': xǁMetricsBufferǁadd_point__mutmut_10, 
        'xǁMetricsBufferǁadd_point__mutmut_11': xǁMetricsBufferǁadd_point__mutmut_11
    }
    
    def add_point(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMetricsBufferǁadd_point__mutmut_orig"), object.__getattribute__(self, "xǁMetricsBufferǁadd_point__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_point.__signature__ = _mutmut_signature(xǁMetricsBufferǁadd_point__mutmut_orig)
    xǁMetricsBufferǁadd_point__mutmut_orig.__name__ = 'xǁMetricsBufferǁadd_point'
    
    def xǁMetricsBufferǁadd_points__mutmut_orig(self, points: List[Tuple[float, float]]):
        for value, timestamp in points:
            self.add_point(value, timestamp)
    
    def xǁMetricsBufferǁadd_points__mutmut_1(self, points: List[Tuple[float, float]]):
        for value, timestamp in points:
            self.add_point(None, timestamp)
    
    def xǁMetricsBufferǁadd_points__mutmut_2(self, points: List[Tuple[float, float]]):
        for value, timestamp in points:
            self.add_point(value, None)
    
    def xǁMetricsBufferǁadd_points__mutmut_3(self, points: List[Tuple[float, float]]):
        for value, timestamp in points:
            self.add_point(timestamp)
    
    def xǁMetricsBufferǁadd_points__mutmut_4(self, points: List[Tuple[float, float]]):
        for value, timestamp in points:
            self.add_point(value, )
    
    xǁMetricsBufferǁadd_points__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMetricsBufferǁadd_points__mutmut_1': xǁMetricsBufferǁadd_points__mutmut_1, 
        'xǁMetricsBufferǁadd_points__mutmut_2': xǁMetricsBufferǁadd_points__mutmut_2, 
        'xǁMetricsBufferǁadd_points__mutmut_3': xǁMetricsBufferǁadd_points__mutmut_3, 
        'xǁMetricsBufferǁadd_points__mutmut_4': xǁMetricsBufferǁadd_points__mutmut_4
    }
    
    def add_points(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMetricsBufferǁadd_points__mutmut_orig"), object.__getattribute__(self, "xǁMetricsBufferǁadd_points__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_points.__signature__ = _mutmut_signature(xǁMetricsBufferǁadd_points__mutmut_orig)
    xǁMetricsBufferǁadd_points__mutmut_orig.__name__ = 'xǁMetricsBufferǁadd_points'
    
    def xǁMetricsBufferǁget_statistics__mutmut_orig(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_1(self, force_recalc: bool = True) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_2(self, force_recalc: bool = False) -> MetricStatistics:
        now = None
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_3(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats or (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_4(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc or self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_5(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_6(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now + self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_7(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) <= self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_8(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_9(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=None, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_10(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=None, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_11(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=None, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_12(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=None, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_13(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=None,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_14(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=None, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_15(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=None, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_16(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=None, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_17(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=None, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_18(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=None, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_19(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=None,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_20(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=None
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_21(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_22(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_23(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_24(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_25(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_26(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_27(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_28(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_29(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_30(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_31(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_32(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_33(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=1, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_34(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=1, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_35(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=1, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_36(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=1, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_37(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=1,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_38(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=1, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_39(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=1, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_40(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=1, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_41(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=1, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_42(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=1, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_43(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=1,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_44(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = None
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_45(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array(None)
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_46(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = None
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_47(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=None,
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_48(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=None,
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_49(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=None,
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_50(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=None,
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_51(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=None,
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_52(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=None,
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_53(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=None,
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_54(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=None,
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_55(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=None,
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_56(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=None,
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_57(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=None,
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_58(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=None
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_59(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_60(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_61(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_62(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_63(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_64(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_65(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_66(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_67(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_68(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_69(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_70(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_71(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(None),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_72(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(None)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_73(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(None),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_74(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(None)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_75(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(None),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_76(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(None)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_77(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(None),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_78(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(None)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_79(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(None),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_80(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(None)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_81(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(None),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_82(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(None, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_83(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, None)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_84(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_85(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, )),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_86(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 26)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_87(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(None),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_88(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(None, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_89(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, None)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_90(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_91(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, )),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_92(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 76)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_93(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(None),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_94(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(None, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_95(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, None)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_96(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_97(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, )),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_98(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 91)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_99(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(None),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_100(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(None, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_101(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, None)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_102(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_103(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, )),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_104(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 96)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_105(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(None),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_106(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(None, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_107(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, None)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_108(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_109(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, )),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_110(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 100)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_111(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = None
        self.last_stats_update = now
        return stats
    
    def xǁMetricsBufferǁget_statistics__mutmut_112(self, force_recalc: bool = False) -> MetricStatistics:
        now = time.time()
        
        if not force_recalc and self.last_stats and \
           (now - self.last_stats_update) < self.stats_cache_interval:
            return self.last_stats
        
        if not self.buffer:
            return MetricStatistics(
                mean=0, median=0, std_dev=0, min_value=0, max_value=0,
                p25=0, p75=0, p90=0, p95=0, p99=0, data_points=0,
                timestamp=now
            )
        
        values = np.array([p.value for p in self.buffer])
        
        stats = MetricStatistics(
            mean=float(np.mean(values)),
            median=float(np.median(values)),
            std_dev=float(np.std(values)),
            min_value=float(np.min(values)),
            max_value=float(np.max(values)),
            p25=float(np.percentile(values, 25)),
            p75=float(np.percentile(values, 75)),
            p90=float(np.percentile(values, 90)),
            p95=float(np.percentile(values, 95)),
            p99=float(np.percentile(values, 99)),
            data_points=len(values),
            timestamp=now
        )
        
        self.last_stats = stats
        self.last_stats_update = None
        return stats
    
    xǁMetricsBufferǁget_statistics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMetricsBufferǁget_statistics__mutmut_1': xǁMetricsBufferǁget_statistics__mutmut_1, 
        'xǁMetricsBufferǁget_statistics__mutmut_2': xǁMetricsBufferǁget_statistics__mutmut_2, 
        'xǁMetricsBufferǁget_statistics__mutmut_3': xǁMetricsBufferǁget_statistics__mutmut_3, 
        'xǁMetricsBufferǁget_statistics__mutmut_4': xǁMetricsBufferǁget_statistics__mutmut_4, 
        'xǁMetricsBufferǁget_statistics__mutmut_5': xǁMetricsBufferǁget_statistics__mutmut_5, 
        'xǁMetricsBufferǁget_statistics__mutmut_6': xǁMetricsBufferǁget_statistics__mutmut_6, 
        'xǁMetricsBufferǁget_statistics__mutmut_7': xǁMetricsBufferǁget_statistics__mutmut_7, 
        'xǁMetricsBufferǁget_statistics__mutmut_8': xǁMetricsBufferǁget_statistics__mutmut_8, 
        'xǁMetricsBufferǁget_statistics__mutmut_9': xǁMetricsBufferǁget_statistics__mutmut_9, 
        'xǁMetricsBufferǁget_statistics__mutmut_10': xǁMetricsBufferǁget_statistics__mutmut_10, 
        'xǁMetricsBufferǁget_statistics__mutmut_11': xǁMetricsBufferǁget_statistics__mutmut_11, 
        'xǁMetricsBufferǁget_statistics__mutmut_12': xǁMetricsBufferǁget_statistics__mutmut_12, 
        'xǁMetricsBufferǁget_statistics__mutmut_13': xǁMetricsBufferǁget_statistics__mutmut_13, 
        'xǁMetricsBufferǁget_statistics__mutmut_14': xǁMetricsBufferǁget_statistics__mutmut_14, 
        'xǁMetricsBufferǁget_statistics__mutmut_15': xǁMetricsBufferǁget_statistics__mutmut_15, 
        'xǁMetricsBufferǁget_statistics__mutmut_16': xǁMetricsBufferǁget_statistics__mutmut_16, 
        'xǁMetricsBufferǁget_statistics__mutmut_17': xǁMetricsBufferǁget_statistics__mutmut_17, 
        'xǁMetricsBufferǁget_statistics__mutmut_18': xǁMetricsBufferǁget_statistics__mutmut_18, 
        'xǁMetricsBufferǁget_statistics__mutmut_19': xǁMetricsBufferǁget_statistics__mutmut_19, 
        'xǁMetricsBufferǁget_statistics__mutmut_20': xǁMetricsBufferǁget_statistics__mutmut_20, 
        'xǁMetricsBufferǁget_statistics__mutmut_21': xǁMetricsBufferǁget_statistics__mutmut_21, 
        'xǁMetricsBufferǁget_statistics__mutmut_22': xǁMetricsBufferǁget_statistics__mutmut_22, 
        'xǁMetricsBufferǁget_statistics__mutmut_23': xǁMetricsBufferǁget_statistics__mutmut_23, 
        'xǁMetricsBufferǁget_statistics__mutmut_24': xǁMetricsBufferǁget_statistics__mutmut_24, 
        'xǁMetricsBufferǁget_statistics__mutmut_25': xǁMetricsBufferǁget_statistics__mutmut_25, 
        'xǁMetricsBufferǁget_statistics__mutmut_26': xǁMetricsBufferǁget_statistics__mutmut_26, 
        'xǁMetricsBufferǁget_statistics__mutmut_27': xǁMetricsBufferǁget_statistics__mutmut_27, 
        'xǁMetricsBufferǁget_statistics__mutmut_28': xǁMetricsBufferǁget_statistics__mutmut_28, 
        'xǁMetricsBufferǁget_statistics__mutmut_29': xǁMetricsBufferǁget_statistics__mutmut_29, 
        'xǁMetricsBufferǁget_statistics__mutmut_30': xǁMetricsBufferǁget_statistics__mutmut_30, 
        'xǁMetricsBufferǁget_statistics__mutmut_31': xǁMetricsBufferǁget_statistics__mutmut_31, 
        'xǁMetricsBufferǁget_statistics__mutmut_32': xǁMetricsBufferǁget_statistics__mutmut_32, 
        'xǁMetricsBufferǁget_statistics__mutmut_33': xǁMetricsBufferǁget_statistics__mutmut_33, 
        'xǁMetricsBufferǁget_statistics__mutmut_34': xǁMetricsBufferǁget_statistics__mutmut_34, 
        'xǁMetricsBufferǁget_statistics__mutmut_35': xǁMetricsBufferǁget_statistics__mutmut_35, 
        'xǁMetricsBufferǁget_statistics__mutmut_36': xǁMetricsBufferǁget_statistics__mutmut_36, 
        'xǁMetricsBufferǁget_statistics__mutmut_37': xǁMetricsBufferǁget_statistics__mutmut_37, 
        'xǁMetricsBufferǁget_statistics__mutmut_38': xǁMetricsBufferǁget_statistics__mutmut_38, 
        'xǁMetricsBufferǁget_statistics__mutmut_39': xǁMetricsBufferǁget_statistics__mutmut_39, 
        'xǁMetricsBufferǁget_statistics__mutmut_40': xǁMetricsBufferǁget_statistics__mutmut_40, 
        'xǁMetricsBufferǁget_statistics__mutmut_41': xǁMetricsBufferǁget_statistics__mutmut_41, 
        'xǁMetricsBufferǁget_statistics__mutmut_42': xǁMetricsBufferǁget_statistics__mutmut_42, 
        'xǁMetricsBufferǁget_statistics__mutmut_43': xǁMetricsBufferǁget_statistics__mutmut_43, 
        'xǁMetricsBufferǁget_statistics__mutmut_44': xǁMetricsBufferǁget_statistics__mutmut_44, 
        'xǁMetricsBufferǁget_statistics__mutmut_45': xǁMetricsBufferǁget_statistics__mutmut_45, 
        'xǁMetricsBufferǁget_statistics__mutmut_46': xǁMetricsBufferǁget_statistics__mutmut_46, 
        'xǁMetricsBufferǁget_statistics__mutmut_47': xǁMetricsBufferǁget_statistics__mutmut_47, 
        'xǁMetricsBufferǁget_statistics__mutmut_48': xǁMetricsBufferǁget_statistics__mutmut_48, 
        'xǁMetricsBufferǁget_statistics__mutmut_49': xǁMetricsBufferǁget_statistics__mutmut_49, 
        'xǁMetricsBufferǁget_statistics__mutmut_50': xǁMetricsBufferǁget_statistics__mutmut_50, 
        'xǁMetricsBufferǁget_statistics__mutmut_51': xǁMetricsBufferǁget_statistics__mutmut_51, 
        'xǁMetricsBufferǁget_statistics__mutmut_52': xǁMetricsBufferǁget_statistics__mutmut_52, 
        'xǁMetricsBufferǁget_statistics__mutmut_53': xǁMetricsBufferǁget_statistics__mutmut_53, 
        'xǁMetricsBufferǁget_statistics__mutmut_54': xǁMetricsBufferǁget_statistics__mutmut_54, 
        'xǁMetricsBufferǁget_statistics__mutmut_55': xǁMetricsBufferǁget_statistics__mutmut_55, 
        'xǁMetricsBufferǁget_statistics__mutmut_56': xǁMetricsBufferǁget_statistics__mutmut_56, 
        'xǁMetricsBufferǁget_statistics__mutmut_57': xǁMetricsBufferǁget_statistics__mutmut_57, 
        'xǁMetricsBufferǁget_statistics__mutmut_58': xǁMetricsBufferǁget_statistics__mutmut_58, 
        'xǁMetricsBufferǁget_statistics__mutmut_59': xǁMetricsBufferǁget_statistics__mutmut_59, 
        'xǁMetricsBufferǁget_statistics__mutmut_60': xǁMetricsBufferǁget_statistics__mutmut_60, 
        'xǁMetricsBufferǁget_statistics__mutmut_61': xǁMetricsBufferǁget_statistics__mutmut_61, 
        'xǁMetricsBufferǁget_statistics__mutmut_62': xǁMetricsBufferǁget_statistics__mutmut_62, 
        'xǁMetricsBufferǁget_statistics__mutmut_63': xǁMetricsBufferǁget_statistics__mutmut_63, 
        'xǁMetricsBufferǁget_statistics__mutmut_64': xǁMetricsBufferǁget_statistics__mutmut_64, 
        'xǁMetricsBufferǁget_statistics__mutmut_65': xǁMetricsBufferǁget_statistics__mutmut_65, 
        'xǁMetricsBufferǁget_statistics__mutmut_66': xǁMetricsBufferǁget_statistics__mutmut_66, 
        'xǁMetricsBufferǁget_statistics__mutmut_67': xǁMetricsBufferǁget_statistics__mutmut_67, 
        'xǁMetricsBufferǁget_statistics__mutmut_68': xǁMetricsBufferǁget_statistics__mutmut_68, 
        'xǁMetricsBufferǁget_statistics__mutmut_69': xǁMetricsBufferǁget_statistics__mutmut_69, 
        'xǁMetricsBufferǁget_statistics__mutmut_70': xǁMetricsBufferǁget_statistics__mutmut_70, 
        'xǁMetricsBufferǁget_statistics__mutmut_71': xǁMetricsBufferǁget_statistics__mutmut_71, 
        'xǁMetricsBufferǁget_statistics__mutmut_72': xǁMetricsBufferǁget_statistics__mutmut_72, 
        'xǁMetricsBufferǁget_statistics__mutmut_73': xǁMetricsBufferǁget_statistics__mutmut_73, 
        'xǁMetricsBufferǁget_statistics__mutmut_74': xǁMetricsBufferǁget_statistics__mutmut_74, 
        'xǁMetricsBufferǁget_statistics__mutmut_75': xǁMetricsBufferǁget_statistics__mutmut_75, 
        'xǁMetricsBufferǁget_statistics__mutmut_76': xǁMetricsBufferǁget_statistics__mutmut_76, 
        'xǁMetricsBufferǁget_statistics__mutmut_77': xǁMetricsBufferǁget_statistics__mutmut_77, 
        'xǁMetricsBufferǁget_statistics__mutmut_78': xǁMetricsBufferǁget_statistics__mutmut_78, 
        'xǁMetricsBufferǁget_statistics__mutmut_79': xǁMetricsBufferǁget_statistics__mutmut_79, 
        'xǁMetricsBufferǁget_statistics__mutmut_80': xǁMetricsBufferǁget_statistics__mutmut_80, 
        'xǁMetricsBufferǁget_statistics__mutmut_81': xǁMetricsBufferǁget_statistics__mutmut_81, 
        'xǁMetricsBufferǁget_statistics__mutmut_82': xǁMetricsBufferǁget_statistics__mutmut_82, 
        'xǁMetricsBufferǁget_statistics__mutmut_83': xǁMetricsBufferǁget_statistics__mutmut_83, 
        'xǁMetricsBufferǁget_statistics__mutmut_84': xǁMetricsBufferǁget_statistics__mutmut_84, 
        'xǁMetricsBufferǁget_statistics__mutmut_85': xǁMetricsBufferǁget_statistics__mutmut_85, 
        'xǁMetricsBufferǁget_statistics__mutmut_86': xǁMetricsBufferǁget_statistics__mutmut_86, 
        'xǁMetricsBufferǁget_statistics__mutmut_87': xǁMetricsBufferǁget_statistics__mutmut_87, 
        'xǁMetricsBufferǁget_statistics__mutmut_88': xǁMetricsBufferǁget_statistics__mutmut_88, 
        'xǁMetricsBufferǁget_statistics__mutmut_89': xǁMetricsBufferǁget_statistics__mutmut_89, 
        'xǁMetricsBufferǁget_statistics__mutmut_90': xǁMetricsBufferǁget_statistics__mutmut_90, 
        'xǁMetricsBufferǁget_statistics__mutmut_91': xǁMetricsBufferǁget_statistics__mutmut_91, 
        'xǁMetricsBufferǁget_statistics__mutmut_92': xǁMetricsBufferǁget_statistics__mutmut_92, 
        'xǁMetricsBufferǁget_statistics__mutmut_93': xǁMetricsBufferǁget_statistics__mutmut_93, 
        'xǁMetricsBufferǁget_statistics__mutmut_94': xǁMetricsBufferǁget_statistics__mutmut_94, 
        'xǁMetricsBufferǁget_statistics__mutmut_95': xǁMetricsBufferǁget_statistics__mutmut_95, 
        'xǁMetricsBufferǁget_statistics__mutmut_96': xǁMetricsBufferǁget_statistics__mutmut_96, 
        'xǁMetricsBufferǁget_statistics__mutmut_97': xǁMetricsBufferǁget_statistics__mutmut_97, 
        'xǁMetricsBufferǁget_statistics__mutmut_98': xǁMetricsBufferǁget_statistics__mutmut_98, 
        'xǁMetricsBufferǁget_statistics__mutmut_99': xǁMetricsBufferǁget_statistics__mutmut_99, 
        'xǁMetricsBufferǁget_statistics__mutmut_100': xǁMetricsBufferǁget_statistics__mutmut_100, 
        'xǁMetricsBufferǁget_statistics__mutmut_101': xǁMetricsBufferǁget_statistics__mutmut_101, 
        'xǁMetricsBufferǁget_statistics__mutmut_102': xǁMetricsBufferǁget_statistics__mutmut_102, 
        'xǁMetricsBufferǁget_statistics__mutmut_103': xǁMetricsBufferǁget_statistics__mutmut_103, 
        'xǁMetricsBufferǁget_statistics__mutmut_104': xǁMetricsBufferǁget_statistics__mutmut_104, 
        'xǁMetricsBufferǁget_statistics__mutmut_105': xǁMetricsBufferǁget_statistics__mutmut_105, 
        'xǁMetricsBufferǁget_statistics__mutmut_106': xǁMetricsBufferǁget_statistics__mutmut_106, 
        'xǁMetricsBufferǁget_statistics__mutmut_107': xǁMetricsBufferǁget_statistics__mutmut_107, 
        'xǁMetricsBufferǁget_statistics__mutmut_108': xǁMetricsBufferǁget_statistics__mutmut_108, 
        'xǁMetricsBufferǁget_statistics__mutmut_109': xǁMetricsBufferǁget_statistics__mutmut_109, 
        'xǁMetricsBufferǁget_statistics__mutmut_110': xǁMetricsBufferǁget_statistics__mutmut_110, 
        'xǁMetricsBufferǁget_statistics__mutmut_111': xǁMetricsBufferǁget_statistics__mutmut_111, 
        'xǁMetricsBufferǁget_statistics__mutmut_112': xǁMetricsBufferǁget_statistics__mutmut_112
    }
    
    def get_statistics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMetricsBufferǁget_statistics__mutmut_orig"), object.__getattribute__(self, "xǁMetricsBufferǁget_statistics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_statistics.__signature__ = _mutmut_signature(xǁMetricsBufferǁget_statistics__mutmut_orig)
    xǁMetricsBufferǁget_statistics__mutmut_orig.__name__ = 'xǁMetricsBufferǁget_statistics'
    
    def xǁMetricsBufferǁget_recent_points__mutmut_orig(self, seconds: int = 3600) -> List[MetricPoint]:
        cutoff = time.time() - seconds
        return [p for p in self.buffer if p.timestamp >= cutoff]
    
    def xǁMetricsBufferǁget_recent_points__mutmut_1(self, seconds: int = 3601) -> List[MetricPoint]:
        cutoff = time.time() - seconds
        return [p for p in self.buffer if p.timestamp >= cutoff]
    
    def xǁMetricsBufferǁget_recent_points__mutmut_2(self, seconds: int = 3600) -> List[MetricPoint]:
        cutoff = None
        return [p for p in self.buffer if p.timestamp >= cutoff]
    
    def xǁMetricsBufferǁget_recent_points__mutmut_3(self, seconds: int = 3600) -> List[MetricPoint]:
        cutoff = time.time() + seconds
        return [p for p in self.buffer if p.timestamp >= cutoff]
    
    def xǁMetricsBufferǁget_recent_points__mutmut_4(self, seconds: int = 3600) -> List[MetricPoint]:
        cutoff = time.time() - seconds
        return [p for p in self.buffer if p.timestamp > cutoff]
    
    xǁMetricsBufferǁget_recent_points__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMetricsBufferǁget_recent_points__mutmut_1': xǁMetricsBufferǁget_recent_points__mutmut_1, 
        'xǁMetricsBufferǁget_recent_points__mutmut_2': xǁMetricsBufferǁget_recent_points__mutmut_2, 
        'xǁMetricsBufferǁget_recent_points__mutmut_3': xǁMetricsBufferǁget_recent_points__mutmut_3, 
        'xǁMetricsBufferǁget_recent_points__mutmut_4': xǁMetricsBufferǁget_recent_points__mutmut_4
    }
    
    def get_recent_points(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMetricsBufferǁget_recent_points__mutmut_orig"), object.__getattribute__(self, "xǁMetricsBufferǁget_recent_points__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_recent_points.__signature__ = _mutmut_signature(xǁMetricsBufferǁget_recent_points__mutmut_orig)
    xǁMetricsBufferǁget_recent_points__mutmut_orig.__name__ = 'xǁMetricsBufferǁget_recent_points'
    
    def xǁMetricsBufferǁget_trend__mutmut_orig(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_1(self, seconds: int = 3601) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_2(self, seconds: int = 3600) -> Optional[str]:
        points = None
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_3(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(None)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_4(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) <= 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_5(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 4:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_6(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = None
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_7(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array(None)
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_8(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = None
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_9(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(None)
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_10(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = None
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_11(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(None, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_12(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, None, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_13(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, None)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_14(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_15(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_16(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, )
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_17(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 2)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_18(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = None
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_19(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[1]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_20(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope >= 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_21(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) * len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_22(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 / np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_23(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 1.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_24(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(None) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_25(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "XXincreasingXX"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_26(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "INCREASING"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_27(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope <= -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_28(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) * len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_29(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 / np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_30(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < +0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_31(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -1.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_32(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(None) / len(values):
            return "decreasing"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_33(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "XXdecreasingXX"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_34(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "DECREASING"
        else:
            return "stable"
    
    def xǁMetricsBufferǁget_trend__mutmut_35(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "XXstableXX"
    
    def xǁMetricsBufferǁget_trend__mutmut_36(self, seconds: int = 3600) -> Optional[str]:
        points = self.get_recent_points(seconds)
        if len(points) < 3:
            return None
        
        values = np.array([p.value for p in points])
        
        x = np.arange(len(values))
        z = np.polyfit(x, values, 1)
        slope = z[0]
        
        if slope > 0.1 * np.mean(values) / len(values):
            return "increasing"
        elif slope < -0.1 * np.mean(values) / len(values):
            return "decreasing"
        else:
            return "STABLE"
    
    xǁMetricsBufferǁget_trend__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMetricsBufferǁget_trend__mutmut_1': xǁMetricsBufferǁget_trend__mutmut_1, 
        'xǁMetricsBufferǁget_trend__mutmut_2': xǁMetricsBufferǁget_trend__mutmut_2, 
        'xǁMetricsBufferǁget_trend__mutmut_3': xǁMetricsBufferǁget_trend__mutmut_3, 
        'xǁMetricsBufferǁget_trend__mutmut_4': xǁMetricsBufferǁget_trend__mutmut_4, 
        'xǁMetricsBufferǁget_trend__mutmut_5': xǁMetricsBufferǁget_trend__mutmut_5, 
        'xǁMetricsBufferǁget_trend__mutmut_6': xǁMetricsBufferǁget_trend__mutmut_6, 
        'xǁMetricsBufferǁget_trend__mutmut_7': xǁMetricsBufferǁget_trend__mutmut_7, 
        'xǁMetricsBufferǁget_trend__mutmut_8': xǁMetricsBufferǁget_trend__mutmut_8, 
        'xǁMetricsBufferǁget_trend__mutmut_9': xǁMetricsBufferǁget_trend__mutmut_9, 
        'xǁMetricsBufferǁget_trend__mutmut_10': xǁMetricsBufferǁget_trend__mutmut_10, 
        'xǁMetricsBufferǁget_trend__mutmut_11': xǁMetricsBufferǁget_trend__mutmut_11, 
        'xǁMetricsBufferǁget_trend__mutmut_12': xǁMetricsBufferǁget_trend__mutmut_12, 
        'xǁMetricsBufferǁget_trend__mutmut_13': xǁMetricsBufferǁget_trend__mutmut_13, 
        'xǁMetricsBufferǁget_trend__mutmut_14': xǁMetricsBufferǁget_trend__mutmut_14, 
        'xǁMetricsBufferǁget_trend__mutmut_15': xǁMetricsBufferǁget_trend__mutmut_15, 
        'xǁMetricsBufferǁget_trend__mutmut_16': xǁMetricsBufferǁget_trend__mutmut_16, 
        'xǁMetricsBufferǁget_trend__mutmut_17': xǁMetricsBufferǁget_trend__mutmut_17, 
        'xǁMetricsBufferǁget_trend__mutmut_18': xǁMetricsBufferǁget_trend__mutmut_18, 
        'xǁMetricsBufferǁget_trend__mutmut_19': xǁMetricsBufferǁget_trend__mutmut_19, 
        'xǁMetricsBufferǁget_trend__mutmut_20': xǁMetricsBufferǁget_trend__mutmut_20, 
        'xǁMetricsBufferǁget_trend__mutmut_21': xǁMetricsBufferǁget_trend__mutmut_21, 
        'xǁMetricsBufferǁget_trend__mutmut_22': xǁMetricsBufferǁget_trend__mutmut_22, 
        'xǁMetricsBufferǁget_trend__mutmut_23': xǁMetricsBufferǁget_trend__mutmut_23, 
        'xǁMetricsBufferǁget_trend__mutmut_24': xǁMetricsBufferǁget_trend__mutmut_24, 
        'xǁMetricsBufferǁget_trend__mutmut_25': xǁMetricsBufferǁget_trend__mutmut_25, 
        'xǁMetricsBufferǁget_trend__mutmut_26': xǁMetricsBufferǁget_trend__mutmut_26, 
        'xǁMetricsBufferǁget_trend__mutmut_27': xǁMetricsBufferǁget_trend__mutmut_27, 
        'xǁMetricsBufferǁget_trend__mutmut_28': xǁMetricsBufferǁget_trend__mutmut_28, 
        'xǁMetricsBufferǁget_trend__mutmut_29': xǁMetricsBufferǁget_trend__mutmut_29, 
        'xǁMetricsBufferǁget_trend__mutmut_30': xǁMetricsBufferǁget_trend__mutmut_30, 
        'xǁMetricsBufferǁget_trend__mutmut_31': xǁMetricsBufferǁget_trend__mutmut_31, 
        'xǁMetricsBufferǁget_trend__mutmut_32': xǁMetricsBufferǁget_trend__mutmut_32, 
        'xǁMetricsBufferǁget_trend__mutmut_33': xǁMetricsBufferǁget_trend__mutmut_33, 
        'xǁMetricsBufferǁget_trend__mutmut_34': xǁMetricsBufferǁget_trend__mutmut_34, 
        'xǁMetricsBufferǁget_trend__mutmut_35': xǁMetricsBufferǁget_trend__mutmut_35, 
        'xǁMetricsBufferǁget_trend__mutmut_36': xǁMetricsBufferǁget_trend__mutmut_36
    }
    
    def get_trend(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMetricsBufferǁget_trend__mutmut_orig"), object.__getattribute__(self, "xǁMetricsBufferǁget_trend__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_trend.__signature__ = _mutmut_signature(xǁMetricsBufferǁget_trend__mutmut_orig)
    xǁMetricsBufferǁget_trend__mutmut_orig.__name__ = 'xǁMetricsBufferǁget_trend'


class SelfLearningThresholdOptimizer:
    """
    Self-learning system for MAPE-K threshold optimization.
    """
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_orig(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_1(self,
                 learning_window_seconds: int = 86401,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_2(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 101,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_3(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3601):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_4(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = None
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_5(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = None
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_6(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = None
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_7(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = None
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_8(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = None
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_9(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = None
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_10(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 1
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_11(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = None
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_12(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = None
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_13(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = None
        self.max_history = 100
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_14(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = None
    
    def xǁSelfLearningThresholdOptimizerǁ__init____mutmut_15(self,
                 learning_window_seconds: int = 86400,
                 min_data_points: int = 100,
                 optimization_interval: int = 3600):
        self.learning_window = learning_window_seconds
        self.min_data_points = min_data_points
        self.optimization_interval = optimization_interval
        
        self.buffers: Dict[str, MetricsBuffer] = {}
        self.recommendations: Dict[str, ThresholdRecommendation] = {}
        self.last_optimization: float = 0
        
        self.anomaly_counts: Dict[str, int] = {}
        self.normal_counts: Dict[str, int] = {}
        
        self.optimization_history: List[Dict[str, Any]] = []
        self.max_history = 101
    
    xǁSelfLearningThresholdOptimizerǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_1': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_2': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_3': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_4': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_5': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_6': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_7': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_8': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_9': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_9, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_10': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_10, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_11': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_11, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_12': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_12, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_13': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_13, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_14': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_14, 
        'xǁSelfLearningThresholdOptimizerǁ__init____mutmut_15': xǁSelfLearningThresholdOptimizerǁ__init____mutmut_15
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁ__init____mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁ__init____mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁ__init__'
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_orig(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, timestamp, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_1(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, timestamp, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_2(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = None
        
        self.buffers[parameter].add_point(value, timestamp, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_3(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(None)
        
        self.buffers[parameter].add_point(value, timestamp, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_4(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(None, timestamp, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_5(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, None, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_6(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, timestamp, None)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_7(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(timestamp, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_8(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, labels)
    
    def xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_9(self, parameter: str, value: float, 
                   timestamp: Optional[float] = None,
                   labels: Optional[Dict[str, str]] = None):
        if parameter not in self.buffers:
            self.buffers[parameter] = MetricsBuffer(parameter)
        
        self.buffers[parameter].add_point(value, timestamp, )
    
    xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_1': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_2': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_3': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_4': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_5': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_6': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_7': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_8': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_9': xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_9
    }
    
    def add_metric(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_metric.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁadd_metric__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁadd_metric'
    
    def xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_orig(self) -> bool:
        now = time.time()
        return (now - self.last_optimization) >= self.optimization_interval
    
    def xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_1(self) -> bool:
        now = None
        return (now - self.last_optimization) >= self.optimization_interval
    
    def xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_2(self) -> bool:
        now = time.time()
        return (now + self.last_optimization) >= self.optimization_interval
    
    def xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_3(self) -> bool:
        now = time.time()
        return (now - self.last_optimization) > self.optimization_interval
    
    xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_1': xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_2': xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_3': xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_3
    }
    
    def should_optimize(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_mutants"), args, kwargs, self)
        return result 
    
    should_optimize.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁshould_optimize__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁshould_optimize'
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_orig(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_1(self) -> Dict[str, ThresholdRecommendation]:
        now = None
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_2(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = None
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_3(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = None
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_4(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = None
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_5(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points <= self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_6(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(None)
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_7(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                break
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_8(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = None
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_9(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(None, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_10(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, None, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_11(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, None)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_12(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_13(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_14(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, )
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_15(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = None
                self.recommendations[parameter] = rec
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_16(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = None
        
        self._record_optimization(recommendations)
        
        return recommendations
    
    def xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_17(self) -> Dict[str, ThresholdRecommendation]:
        now = time.time()
        self.last_optimization = now
        recommendations = {}
        
        for parameter, buffer in self.buffers.items():
            stats = buffer.get_statistics()
            
            if stats.data_points < self.min_data_points:
                logger.debug(f"Skipping {parameter}: only {stats.data_points} points")
                continue
            
            rec = self._generate_recommendation(parameter, buffer, stats)
            if rec:
                recommendations[parameter] = rec
                self.recommendations[parameter] = rec
        
        self._record_optimization(None)
        
        return recommendations
    
    xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_1': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_2': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_3': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_4': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_5': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_6': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_7': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_8': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_9': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_9, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_10': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_10, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_11': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_11, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_12': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_12, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_13': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_13, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_14': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_14, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_15': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_15, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_16': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_16, 
        'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_17': xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_17
    }
    
    def optimize_thresholds(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_mutants"), args, kwargs, self)
        return result 
    
    optimize_thresholds.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁoptimize_thresholds__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁoptimize_thresholds'
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_orig(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_1(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = None
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_2(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = None
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_3(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = None
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_4(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['XXpercentileXX'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_5(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['PERCENTILE'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_6(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 1.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_7(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = None
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_8(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean - 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_9(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 / stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_10(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 3 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_11(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = None
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_12(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['XXsigmaXX'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_13(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['SIGMA'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_14(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 1.8, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_15(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = None
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_16(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 + stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_17(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = None
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_18(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 - 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_19(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 / iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_20(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 2.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_21(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = None
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_22(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['XXiqrXX'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_23(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['IQR'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_24(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 1.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_25(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = None
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_26(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(None, key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_27(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=None)
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_28(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_29(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), )
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_30(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: None)
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_31(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[2][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_32(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][2])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_33(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = None
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_34(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[2][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_35(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][1]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_36(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = None
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_37(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[2][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_38(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][2]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_39(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = None
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_40(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[2][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_41(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][3]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_42(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = None
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_43(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend != "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_44(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "XXincreasingXX":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_45(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "INCREASING":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_46(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence = 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_47(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence /= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_48(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 1.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_49(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend != "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_50(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "XXdecreasingXX":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_51(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "DECREASING":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_52(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence = 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_53(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence /= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_54(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 1.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_55(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence = 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_56(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence /= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_57(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 2.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_58(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = None
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_59(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(None, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_60(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, None)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_61(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_62(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, )
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_63(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean / 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_64(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 2.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_65(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = None
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_66(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(None, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_67(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, None)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_68(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_69(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, )
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_70(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value / 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_71(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 1.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_72(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = None
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_73(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].lower()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_74(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[1].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_75(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend and 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_76(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'XXunknownXX'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_77(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'UNKNOWN'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_78(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=None,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_79(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=None,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_80(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=None,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_81(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=None,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_82(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=None,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_83(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data=None
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_84(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_85(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_86(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_87(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_88(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_89(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_90(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'XXmeanXX': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_91(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'MEAN': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_92(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'XXstd_devXX': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_93(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'STD_DEV': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_94(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'XXp95XX': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_95(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'P95': stats.p95,
                'data_points': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_96(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'XXdata_pointsXX': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_97(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'DATA_POINTS': stats.data_points,
                'trend': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_98(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'XXtrendXX': trend
            }
        )
    
    def xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_99(self, 
                                parameter: str,
                                buffer: MetricsBuffer,
                                stats: MetricStatistics) -> Optional[ThresholdRecommendation]:
        
        strategies_scores = {}
        
        p95_threshold = stats.p95
        strategies_scores['percentile'] = (p95_threshold, 0.85, ThresholdStrategy.PERCENTILE)
        
        sigma_threshold = stats.mean + 2 * stats.std_dev
        strategies_scores['sigma'] = (sigma_threshold, 0.80, ThresholdStrategy.SIGMA)
        
        iqr = stats.p75 - stats.p25
        iqr_threshold = stats.p75 + 1.5 * iqr
        strategies_scores['iqr'] = (iqr_threshold, 0.75, ThresholdStrategy.IQR)
        
        best_strategy = max(strategies_scores.items(), key=lambda x: x[1][1])
        recommended_value = best_strategy[1][0]
        confidence = best_strategy[1][1]
        strategy = best_strategy[1][2]
        
        trend = buffer.get_trend()
        if trend == "increasing":
            confidence *= 0.9
        elif trend == "decreasing":
            confidence *= 0.95
        else:
            confidence *= 1.0
        
        recommended_value = max(stats.mean * 1.5, recommended_value)
        recommended_value = min(stats.max_value * 0.95, recommended_value)
        
        reasoning = (
            f"Strategy: {best_strategy[0].upper()} | "
            f"Mean={stats.mean:.2f}, StdDev={stats.std_dev:.2f}, "
            f"P95={stats.p95:.2f} | Trend: {trend or 'unknown'}"
        )
        
        return ThresholdRecommendation(
            parameter=parameter,
            recommended_value=recommended_value,
            confidence=confidence,
            strategy=strategy,
            reasoning=reasoning,
            supporting_data={
                'mean': stats.mean,
                'std_dev': stats.std_dev,
                'p95': stats.p95,
                'data_points': stats.data_points,
                'TREND': trend
            }
        )
    
    xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_1': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_2': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_3': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_4': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_5': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_6': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_7': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_8': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_9': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_9, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_10': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_10, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_11': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_11, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_12': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_12, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_13': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_13, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_14': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_14, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_15': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_15, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_16': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_16, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_17': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_17, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_18': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_18, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_19': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_19, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_20': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_20, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_21': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_21, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_22': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_22, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_23': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_23, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_24': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_24, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_25': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_25, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_26': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_26, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_27': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_27, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_28': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_28, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_29': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_29, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_30': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_30, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_31': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_31, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_32': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_32, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_33': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_33, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_34': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_34, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_35': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_35, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_36': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_36, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_37': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_37, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_38': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_38, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_39': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_39, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_40': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_40, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_41': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_41, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_42': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_42, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_43': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_43, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_44': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_44, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_45': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_45, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_46': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_46, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_47': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_47, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_48': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_48, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_49': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_49, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_50': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_50, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_51': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_51, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_52': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_52, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_53': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_53, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_54': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_54, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_55': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_55, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_56': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_56, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_57': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_57, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_58': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_58, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_59': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_59, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_60': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_60, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_61': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_61, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_62': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_62, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_63': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_63, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_64': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_64, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_65': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_65, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_66': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_66, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_67': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_67, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_68': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_68, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_69': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_69, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_70': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_70, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_71': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_71, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_72': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_72, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_73': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_73, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_74': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_74, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_75': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_75, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_76': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_76, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_77': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_77, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_78': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_78, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_79': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_79, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_80': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_80, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_81': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_81, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_82': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_82, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_83': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_83, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_84': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_84, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_85': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_85, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_86': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_86, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_87': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_87, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_88': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_88, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_89': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_89, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_90': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_90, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_91': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_91, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_92': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_92, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_93': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_93, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_94': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_94, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_95': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_95, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_96': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_96, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_97': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_97, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_98': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_98, 
        'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_99': xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_99
    }
    
    def _generate_recommendation(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _generate_recommendation.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁ_generate_recommendation__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁ_generate_recommendation'
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_orig(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_1(self, parameter: str, 
                        sensitivity: float = 3.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_2(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_3(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = None
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_4(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = None
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_5(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points <= 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_6(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 11:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_7(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = None
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_8(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean - sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_9(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity / stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_10(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = None
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_11(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value >= threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_12(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = None
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_13(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) - len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_14(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(None, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_15(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, None) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_16(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_17(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, ) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_18(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 1) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_19(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = None
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_20(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) - (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_21(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(None, 0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_22(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, None) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_23(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(0) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_24(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, ) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_25(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 1) + (
            stats.data_points - len(anomalies)
        )
        
        return anomalies
    
    def xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_26(self, parameter: str, 
                        sensitivity: float = 2.0) -> List[MetricPoint]:
        
        if parameter not in self.buffers:
            return []
        
        buffer = self.buffers[parameter]
        stats = buffer.get_statistics()
        
        if stats.data_points < 10:
            return []
        
        threshold = stats.mean + sensitivity * stats.std_dev
        anomalies = [p for p in buffer.buffer if p.value > threshold]
        
        self.anomaly_counts[parameter] = self.anomaly_counts.get(parameter, 0) + len(anomalies)
        self.normal_counts[parameter] = self.normal_counts.get(parameter, 0) + (
            stats.data_points + len(anomalies)
        )
        
        return anomalies
    
    xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_1': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_2': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_3': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_4': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_5': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_6': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_7': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_8': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_9': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_9, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_10': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_10, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_11': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_11, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_12': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_12, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_13': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_13, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_14': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_14, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_15': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_15, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_16': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_16, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_17': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_17, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_18': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_18, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_19': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_19, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_20': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_20, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_21': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_21, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_22': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_22, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_23': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_23, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_24': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_24, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_25': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_25, 
        'xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_26': xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_26
    }
    
    def detect_anomalies(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_mutants"), args, kwargs, self)
        return result 
    
    detect_anomalies.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁdetect_anomalies__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁdetect_anomalies'
    
    def xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_orig(self, parameter: str) -> Optional[MetricStatistics]:
        if parameter not in self.buffers:
            return None
        return self.buffers[parameter].get_statistics()
    
    def xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_1(self, parameter: str) -> Optional[MetricStatistics]:
        if parameter in self.buffers:
            return None
        return self.buffers[parameter].get_statistics()
    
    xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_1': xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_1
    }
    
    def get_statistics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_statistics.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁget_statistics__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁget_statistics'
    
    def xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_orig(self, parameter: str) -> Optional[ThresholdRecommendation]:
        return self.recommendations.get(parameter)
    
    def xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_1(self, parameter: str) -> Optional[ThresholdRecommendation]:
        return self.recommendations.get(None)
    
    xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_1': xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_1
    }
    
    def get_recommendation(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_recommendation.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁget_recommendation__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁget_recommendation'
    
    def get_all_recommendations(self) -> Dict[str, ThresholdRecommendation]:
        return self.recommendations.copy()
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_orig(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_1(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = None
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_2(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'XXtimestampXX': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_3(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'TIMESTAMP': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_4(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'XXrecommendationsXX': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_5(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'RECOMMENDATIONS': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_6(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'XXvalueXX': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_7(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'VALUE': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_8(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'XXconfidenceXX': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_9(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'CONFIDENCE': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_10(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'XXstrategyXX': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_11(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'STRATEGY': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_12(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(None)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_13(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) >= self.max_history:
            self.optimization_history.pop(0)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_14(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(None)
    
    def xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_15(self, recommendations: Dict[str, ThresholdRecommendation]):
        history_entry = {
            'timestamp': time.time(),
            'recommendations': {
                k: {
                    'value': v.recommended_value,
                    'confidence': v.confidence,
                    'strategy': v.strategy.value
                }
                for k, v in recommendations.items()
            }
        }
        
        self.optimization_history.append(history_entry)
        if len(self.optimization_history) > self.max_history:
            self.optimization_history.pop(1)
    
    xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_1': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_2': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_3': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_4': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_5': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_6': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_7': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_8': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_9': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_9, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_10': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_10, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_11': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_11, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_12': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_12, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_13': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_13, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_14': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_14, 
        'xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_15': xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_15
    }
    
    def _record_optimization(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _record_optimization.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁ_record_optimization__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁ_record_optimization'
    
    def get_optimization_history(self) -> List[Dict[str, Any]]:
        return self.optimization_history.copy()
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_orig(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_1(self) -> Dict[str, Any]:
        return {
            'XXtotal_parametersXX': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_2(self) -> Dict[str, Any]:
        return {
            'TOTAL_PARAMETERS': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_3(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'XXparameters_with_dataXX': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_4(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'PARAMETERS_WITH_DATA': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_5(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                None
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_6(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                2 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_7(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points > self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_8(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'XXtotal_data_pointsXX': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_9(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'TOTAL_DATA_POINTS': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_10(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                None
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_11(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'XXanomaly_detection_rateXX': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_12(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'ANOMALY_DETECTION_RATE': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_13(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) / 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_14(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) * max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_15(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(None, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_16(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, None) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_17(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_18(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, ) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_19(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 1) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_20(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    None, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_21(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, None
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_22(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_23(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_24(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    2, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_25(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) - self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_26(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(None, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_27(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, None) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_28(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_29(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, ) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_30(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 1) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_31(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(None, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_32(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, None)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_33(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_34(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, )
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_35(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 1)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_36(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 101
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_37(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'XXrecommendations_activeXX': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_38(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'RECOMMENDATIONS_ACTIVE': len(self.recommendations),
            'optimization_history_entries': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_39(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'XXoptimization_history_entriesXX': len(self.optimization_history)
        }
    
    def xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_40(self) -> Dict[str, Any]:
        return {
            'total_parameters': len(self.buffers),
            'parameters_with_data': sum(
                1 for b in self.buffers.values() 
                if b.get_statistics().data_points >= self.min_data_points
            ),
            'total_data_points': sum(
                b.get_statistics().data_points for b in self.buffers.values()
            ),
            'anomaly_detection_rate': {
                param: self.anomaly_counts.get(param, 0) / max(
                    1, self.anomaly_counts.get(param, 0) + self.normal_counts.get(param, 0)
                ) * 100
                for param in self.buffers.keys()
            },
            'recommendations_active': len(self.recommendations),
            'OPTIMIZATION_HISTORY_ENTRIES': len(self.optimization_history)
        }
    
    xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_1': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_2': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_3': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_4': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_4, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_5': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_5, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_6': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_6, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_7': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_7, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_8': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_8, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_9': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_9, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_10': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_10, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_11': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_11, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_12': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_12, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_13': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_13, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_14': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_14, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_15': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_15, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_16': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_16, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_17': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_17, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_18': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_18, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_19': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_19, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_20': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_20, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_21': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_21, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_22': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_22, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_23': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_23, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_24': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_24, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_25': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_25, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_26': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_26, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_27': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_27, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_28': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_28, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_29': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_29, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_30': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_30, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_31': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_31, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_32': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_32, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_33': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_33, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_34': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_34, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_35': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_35, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_36': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_36, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_37': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_37, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_38': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_38, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_39': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_39, 
        'xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_40': xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_40
    }
    
    def get_learning_stats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_learning_stats.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁget_learning_stats__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁget_learning_stats'
    
    def export_thresholds(self) -> Dict[str, float]:
        return {
            param: rec.recommended_value
            for param, rec in self.recommendations.items()
        }
    
    def xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_orig(self, metrics_dict: Dict[str, List[Tuple[float, float]]]):
        for parameter, points in metrics_dict.items():
            if parameter not in self.buffers:
                self.buffers[parameter] = MetricsBuffer(parameter)
            self.buffers[parameter].add_points(points)
    
    def xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_1(self, metrics_dict: Dict[str, List[Tuple[float, float]]]):
        for parameter, points in metrics_dict.items():
            if parameter in self.buffers:
                self.buffers[parameter] = MetricsBuffer(parameter)
            self.buffers[parameter].add_points(points)
    
    def xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_2(self, metrics_dict: Dict[str, List[Tuple[float, float]]]):
        for parameter, points in metrics_dict.items():
            if parameter not in self.buffers:
                self.buffers[parameter] = None
            self.buffers[parameter].add_points(points)
    
    def xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_3(self, metrics_dict: Dict[str, List[Tuple[float, float]]]):
        for parameter, points in metrics_dict.items():
            if parameter not in self.buffers:
                self.buffers[parameter] = MetricsBuffer(None)
            self.buffers[parameter].add_points(points)
    
    def xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_4(self, metrics_dict: Dict[str, List[Tuple[float, float]]]):
        for parameter, points in metrics_dict.items():
            if parameter not in self.buffers:
                self.buffers[parameter] = MetricsBuffer(parameter)
            self.buffers[parameter].add_points(None)
    
    xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_1': xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_1, 
        'xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_2': xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_2, 
        'xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_3': xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_3, 
        'xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_4': xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_4
    }
    
    def import_metrics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_orig"), object.__getattribute__(self, "xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    import_metrics.__signature__ = _mutmut_signature(xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_orig)
    xǁSelfLearningThresholdOptimizerǁimport_metrics__mutmut_orig.__name__ = 'xǁSelfLearningThresholdOptimizerǁimport_metrics'
