#!/usr/bin/env python3
"""
x0tta6bl4 Thread-Safe Statistics
============================================

Thread-safe statistics collection for concurrent operations.
Eliminates race conditions in metrics updates across mesh components.

Features:
- Atomic counters
- Thread-safe metrics collection
- Lock-free data structures where possible
- Performance optimized for high-frequency updates
"""

import threading
import time
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import logging

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

@dataclass
class AtomicCounter:
    """Thread-safe atomic counter."""
    _value: int = 0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def increment(self, delta: int = 1) -> int:
        """Increment counter and return new value."""
        with self._lock:
            self._value += delta
            return self._value
    
    def get(self) -> int:
        """Get current value."""
        with self._lock:
            return self._value
    
    def set(self, value: int) -> None:
        """Set counter value."""
        with self._lock:
            self._value = value
    
    def reset(self) -> int:
        """Reset counter and return old value."""
        with self._lock:
            old = self._value
            self._value = 0
            return old

@dataclass
class AtomicFloat:
    """Thread-safe atomic float."""
    _value: float = 0.0
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def update(self, value: float) -> float:
        """Update value and return new value."""
        with self._lock:
            self._value = value
            return self._value
    
    def add(self, delta: float) -> float:
        """Add delta and return new value."""
        with self._lock:
            self._value += delta
            return self._value
    
    def get(self) -> float:
        """Get current value."""
        with self._lock:
            return self._value

class ThreadSafeMetrics:
    """
    Thread-safe metrics collection for mesh components.
    
    Provides atomic operations for common metrics patterns:
    - Counters (packets, connections, errors)
    - Gauges (latency, throughput, active connections)
    - Histograms (latency distributions)
    - Sets (unique items)
    """
    
    def xǁThreadSafeMetricsǁ__init____mutmut_orig(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_1(self, component_name: str):
        self.component_name = None
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_2(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = None
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_3(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(None)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_4(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = None
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_5(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(None)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_6(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = None
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_7(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(None)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_8(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = None
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_9(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(None)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_10(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = None
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_11(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(None)
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_12(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: None)
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_13(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=None))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_14(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1001))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_15(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = None
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_16(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(None)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_17(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = None
        
        logger.debug(f"ThreadSafeMetrics initialized for {component_name}")
    
    def xǁThreadSafeMetricsǁ__init____mutmut_18(self, component_name: str):
        self.component_name = component_name
        
        # Atomic counters
        self._counters: Dict[str, AtomicCounter] = defaultdict(AtomicCounter)
        
        # Atomic gauges
        self._gauges: Dict[str, AtomicFloat] = defaultdict(AtomicFloat)
        
        # Thread-safe sets for unique items
        self._sets: Dict[str, set] = defaultdict(set)
        self._set_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Thread-safe deques for recent values
        self._recent: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self._recent_locks: Dict[str, threading.Lock] = defaultdict(threading.Lock)
        
        # Last update timestamp
        self._last_update = AtomicFloat()
        
        logger.debug(None)
    
    xǁThreadSafeMetricsǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁ__init____mutmut_1': xǁThreadSafeMetricsǁ__init____mutmut_1, 
        'xǁThreadSafeMetricsǁ__init____mutmut_2': xǁThreadSafeMetricsǁ__init____mutmut_2, 
        'xǁThreadSafeMetricsǁ__init____mutmut_3': xǁThreadSafeMetricsǁ__init____mutmut_3, 
        'xǁThreadSafeMetricsǁ__init____mutmut_4': xǁThreadSafeMetricsǁ__init____mutmut_4, 
        'xǁThreadSafeMetricsǁ__init____mutmut_5': xǁThreadSafeMetricsǁ__init____mutmut_5, 
        'xǁThreadSafeMetricsǁ__init____mutmut_6': xǁThreadSafeMetricsǁ__init____mutmut_6, 
        'xǁThreadSafeMetricsǁ__init____mutmut_7': xǁThreadSafeMetricsǁ__init____mutmut_7, 
        'xǁThreadSafeMetricsǁ__init____mutmut_8': xǁThreadSafeMetricsǁ__init____mutmut_8, 
        'xǁThreadSafeMetricsǁ__init____mutmut_9': xǁThreadSafeMetricsǁ__init____mutmut_9, 
        'xǁThreadSafeMetricsǁ__init____mutmut_10': xǁThreadSafeMetricsǁ__init____mutmut_10, 
        'xǁThreadSafeMetricsǁ__init____mutmut_11': xǁThreadSafeMetricsǁ__init____mutmut_11, 
        'xǁThreadSafeMetricsǁ__init____mutmut_12': xǁThreadSafeMetricsǁ__init____mutmut_12, 
        'xǁThreadSafeMetricsǁ__init____mutmut_13': xǁThreadSafeMetricsǁ__init____mutmut_13, 
        'xǁThreadSafeMetricsǁ__init____mutmut_14': xǁThreadSafeMetricsǁ__init____mutmut_14, 
        'xǁThreadSafeMetricsǁ__init____mutmut_15': xǁThreadSafeMetricsǁ__init____mutmut_15, 
        'xǁThreadSafeMetricsǁ__init____mutmut_16': xǁThreadSafeMetricsǁ__init____mutmut_16, 
        'xǁThreadSafeMetricsǁ__init____mutmut_17': xǁThreadSafeMetricsǁ__init____mutmut_17, 
        'xǁThreadSafeMetricsǁ__init____mutmut_18': xǁThreadSafeMetricsǁ__init____mutmut_18
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁ__init____mutmut_orig)
    xǁThreadSafeMetricsǁ__init____mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁ__init__'
    
    def xǁThreadSafeMetricsǁincrement_counter__mutmut_orig(self, name: str, delta: int = 1) -> int:
        """Increment a counter atomically."""
        result = self._counters[name].increment(delta)
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁincrement_counter__mutmut_1(self, name: str, delta: int = 2) -> int:
        """Increment a counter atomically."""
        result = self._counters[name].increment(delta)
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁincrement_counter__mutmut_2(self, name: str, delta: int = 1) -> int:
        """Increment a counter atomically."""
        result = None
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁincrement_counter__mutmut_3(self, name: str, delta: int = 1) -> int:
        """Increment a counter atomically."""
        result = self._counters[name].increment(None)
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁincrement_counter__mutmut_4(self, name: str, delta: int = 1) -> int:
        """Increment a counter atomically."""
        result = self._counters[name].increment(delta)
        self._last_update.update(None)
        return result
    
    xǁThreadSafeMetricsǁincrement_counter__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁincrement_counter__mutmut_1': xǁThreadSafeMetricsǁincrement_counter__mutmut_1, 
        'xǁThreadSafeMetricsǁincrement_counter__mutmut_2': xǁThreadSafeMetricsǁincrement_counter__mutmut_2, 
        'xǁThreadSafeMetricsǁincrement_counter__mutmut_3': xǁThreadSafeMetricsǁincrement_counter__mutmut_3, 
        'xǁThreadSafeMetricsǁincrement_counter__mutmut_4': xǁThreadSafeMetricsǁincrement_counter__mutmut_4
    }
    
    def increment_counter(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁincrement_counter__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁincrement_counter__mutmut_mutants"), args, kwargs, self)
        return result 
    
    increment_counter.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁincrement_counter__mutmut_orig)
    xǁThreadSafeMetricsǁincrement_counter__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁincrement_counter'
    
    def get_counter(self, name: str) -> int:
        """Get counter value."""
        return self._counters[name].get()
    
    def xǁThreadSafeMetricsǁset_gauge__mutmut_orig(self, name: str, value: float) -> float:
        """Set gauge value atomically."""
        result = self._gauges[name].update(value)
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁset_gauge__mutmut_1(self, name: str, value: float) -> float:
        """Set gauge value atomically."""
        result = None
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁset_gauge__mutmut_2(self, name: str, value: float) -> float:
        """Set gauge value atomically."""
        result = self._gauges[name].update(None)
        self._last_update.update(time.time())
        return result
    
    def xǁThreadSafeMetricsǁset_gauge__mutmut_3(self, name: str, value: float) -> float:
        """Set gauge value atomically."""
        result = self._gauges[name].update(value)
        self._last_update.update(None)
        return result
    
    xǁThreadSafeMetricsǁset_gauge__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁset_gauge__mutmut_1': xǁThreadSafeMetricsǁset_gauge__mutmut_1, 
        'xǁThreadSafeMetricsǁset_gauge__mutmut_2': xǁThreadSafeMetricsǁset_gauge__mutmut_2, 
        'xǁThreadSafeMetricsǁset_gauge__mutmut_3': xǁThreadSafeMetricsǁset_gauge__mutmut_3
    }
    
    def set_gauge(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁset_gauge__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁset_gauge__mutmut_mutants"), args, kwargs, self)
        return result 
    
    set_gauge.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁset_gauge__mutmut_orig)
    xǁThreadSafeMetricsǁset_gauge__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁset_gauge'
    
    def get_gauge(self, name: str) -> float:
        """Get gauge value."""
        return self._gauges[name].get()
    
    def xǁThreadSafeMetricsǁadd_to_set__mutmut_orig(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return False
            self._sets[set_name].add(item)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁadd_to_set__mutmut_1(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return False
            self._sets[set_name].add(item)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁadd_to_set__mutmut_2(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return True
            self._sets[set_name].add(item)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁadd_to_set__mutmut_3(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return False
            self._sets[set_name].add(None)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁadd_to_set__mutmut_4(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return False
            self._sets[set_name].add(item)
            self._last_update.update(None)
            return True
    
    def xǁThreadSafeMetricsǁadd_to_set__mutmut_5(self, set_name: str, item: Any) -> bool:
        """Add item to set thread-safely. Returns True if item was new."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return False
            self._sets[set_name].add(item)
            self._last_update.update(time.time())
            return False
    
    xǁThreadSafeMetricsǁadd_to_set__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁadd_to_set__mutmut_1': xǁThreadSafeMetricsǁadd_to_set__mutmut_1, 
        'xǁThreadSafeMetricsǁadd_to_set__mutmut_2': xǁThreadSafeMetricsǁadd_to_set__mutmut_2, 
        'xǁThreadSafeMetricsǁadd_to_set__mutmut_3': xǁThreadSafeMetricsǁadd_to_set__mutmut_3, 
        'xǁThreadSafeMetricsǁadd_to_set__mutmut_4': xǁThreadSafeMetricsǁadd_to_set__mutmut_4, 
        'xǁThreadSafeMetricsǁadd_to_set__mutmut_5': xǁThreadSafeMetricsǁadd_to_set__mutmut_5
    }
    
    def add_to_set(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁadd_to_set__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁadd_to_set__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_to_set.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁadd_to_set__mutmut_orig)
    xǁThreadSafeMetricsǁadd_to_set__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁadd_to_set'
    
    def xǁThreadSafeMetricsǁremove_from_set__mutmut_orig(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return False
            self._sets[set_name].remove(item)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁremove_from_set__mutmut_1(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item in self._sets[set_name]:
                return False
            self._sets[set_name].remove(item)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁremove_from_set__mutmut_2(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return True
            self._sets[set_name].remove(item)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁremove_from_set__mutmut_3(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return False
            self._sets[set_name].remove(None)
            self._last_update.update(time.time())
            return True
    
    def xǁThreadSafeMetricsǁremove_from_set__mutmut_4(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return False
            self._sets[set_name].remove(item)
            self._last_update.update(None)
            return True
    
    def xǁThreadSafeMetricsǁremove_from_set__mutmut_5(self, set_name: str, item: Any) -> bool:
        """Remove item from set thread-safely. Returns True if item was present."""
        with self._set_locks[set_name]:
            if item not in self._sets[set_name]:
                return False
            self._sets[set_name].remove(item)
            self._last_update.update(time.time())
            return False
    
    xǁThreadSafeMetricsǁremove_from_set__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁremove_from_set__mutmut_1': xǁThreadSafeMetricsǁremove_from_set__mutmut_1, 
        'xǁThreadSafeMetricsǁremove_from_set__mutmut_2': xǁThreadSafeMetricsǁremove_from_set__mutmut_2, 
        'xǁThreadSafeMetricsǁremove_from_set__mutmut_3': xǁThreadSafeMetricsǁremove_from_set__mutmut_3, 
        'xǁThreadSafeMetricsǁremove_from_set__mutmut_4': xǁThreadSafeMetricsǁremove_from_set__mutmut_4, 
        'xǁThreadSafeMetricsǁremove_from_set__mutmut_5': xǁThreadSafeMetricsǁremove_from_set__mutmut_5
    }
    
    def remove_from_set(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁremove_from_set__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁremove_from_set__mutmut_mutants"), args, kwargs, self)
        return result 
    
    remove_from_set.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁremove_from_set__mutmut_orig)
    xǁThreadSafeMetricsǁremove_from_set__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁremove_from_set'
    
    def get_set_size(self, set_name: str) -> int:
        """Get set size."""
        with self._set_locks[set_name]:
            return len(self._sets[set_name])
    
    def xǁThreadSafeMetricsǁget_set_items__mutmut_orig(self, set_name: str) -> set:
        """Get copy of set items."""
        with self._set_locks[set_name]:
            return set(self._sets[set_name])
    
    def xǁThreadSafeMetricsǁget_set_items__mutmut_1(self, set_name: str) -> set:
        """Get copy of set items."""
        with self._set_locks[set_name]:
            return set(None)
    
    xǁThreadSafeMetricsǁget_set_items__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁget_set_items__mutmut_1': xǁThreadSafeMetricsǁget_set_items__mutmut_1
    }
    
    def get_set_items(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁget_set_items__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁget_set_items__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_set_items.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁget_set_items__mutmut_orig)
    xǁThreadSafeMetricsǁget_set_items__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁget_set_items'
    
    def xǁThreadSafeMetricsǁadd_recent__mutmut_orig(self, series_name: str, value: Any) -> None:
        """Add value to recent series thread-safely."""
        with self._recent_locks[series_name]:
            self._recent[series_name].append((time.time(), value))
            self._last_update.update(time.time())
    
    def xǁThreadSafeMetricsǁadd_recent__mutmut_1(self, series_name: str, value: Any) -> None:
        """Add value to recent series thread-safely."""
        with self._recent_locks[series_name]:
            self._recent[series_name].append(None)
            self._last_update.update(time.time())
    
    def xǁThreadSafeMetricsǁadd_recent__mutmut_2(self, series_name: str, value: Any) -> None:
        """Add value to recent series thread-safely."""
        with self._recent_locks[series_name]:
            self._recent[series_name].append((time.time(), value))
            self._last_update.update(None)
    
    xǁThreadSafeMetricsǁadd_recent__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁadd_recent__mutmut_1': xǁThreadSafeMetricsǁadd_recent__mutmut_1, 
        'xǁThreadSafeMetricsǁadd_recent__mutmut_2': xǁThreadSafeMetricsǁadd_recent__mutmut_2
    }
    
    def add_recent(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁadd_recent__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁadd_recent__mutmut_mutants"), args, kwargs, self)
        return result 
    
    add_recent.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁadd_recent__mutmut_orig)
    xǁThreadSafeMetricsǁadd_recent__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁadd_recent'
    
    def xǁThreadSafeMetricsǁget_recent__mutmut_orig(self, series_name: str, limit: Optional[int] = None) -> List[tuple]:
        """Get recent values from series."""
        with self._recent_locks[series_name]:
            recent = list(self._recent[series_name])
            if limit:
                return recent[-limit:]
            return recent
    
    def xǁThreadSafeMetricsǁget_recent__mutmut_1(self, series_name: str, limit: Optional[int] = None) -> List[tuple]:
        """Get recent values from series."""
        with self._recent_locks[series_name]:
            recent = None
            if limit:
                return recent[-limit:]
            return recent
    
    def xǁThreadSafeMetricsǁget_recent__mutmut_2(self, series_name: str, limit: Optional[int] = None) -> List[tuple]:
        """Get recent values from series."""
        with self._recent_locks[series_name]:
            recent = list(None)
            if limit:
                return recent[-limit:]
            return recent
    
    def xǁThreadSafeMetricsǁget_recent__mutmut_3(self, series_name: str, limit: Optional[int] = None) -> List[tuple]:
        """Get recent values from series."""
        with self._recent_locks[series_name]:
            recent = list(self._recent[series_name])
            if limit:
                return recent[+limit:]
            return recent
    
    xǁThreadSafeMetricsǁget_recent__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁget_recent__mutmut_1': xǁThreadSafeMetricsǁget_recent__mutmut_1, 
        'xǁThreadSafeMetricsǁget_recent__mutmut_2': xǁThreadSafeMetricsǁget_recent__mutmut_2, 
        'xǁThreadSafeMetricsǁget_recent__mutmut_3': xǁThreadSafeMetricsǁget_recent__mutmut_3
    }
    
    def get_recent(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁget_recent__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁget_recent__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_recent.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁget_recent__mutmut_orig)
    xǁThreadSafeMetricsǁget_recent__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁget_recent'
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_orig(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_1(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = None
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_2(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'XXcomponentXX': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_3(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'COMPONENT': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_4(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'XXlast_updateXX': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_5(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'LAST_UPDATE': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_6(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'XXcountersXX': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_7(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'COUNTERS': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_8(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'XXgaugesXX': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_9(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'GAUGES': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_10(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'XXsetsXX': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_11(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'SETS': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_12(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'XXrecent_seriesXX': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_13(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'RECENT_SERIES': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_14(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = None
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_15(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['XXcountersXX'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_16(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['COUNTERS'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_17(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = None
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_18(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['XXgaugesXX'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_19(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['GAUGES'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_20(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = None
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_21(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['XXsetsXX'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_22(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['SETS'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_23(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['recent_series'][name] = None
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_24(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['XXrecent_seriesXX'][name] = len(self._recent[name])
        
        return snapshot
    
    def xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_25(self) -> Dict[str, Any]:
        """Get thread-safe snapshot of all metrics."""
        snapshot = {
            'component': self.component_name,
            'last_update': self._last_update.get(),
            'counters': {},
            'gauges': {},
            'sets': {},
            'recent_series': {}
        }
        
        # Get counters
        for name, counter in self._counters.items():
            snapshot['counters'][name] = counter.get()
        
        # Get gauges
        for name, gauge in self._gauges.items():
            snapshot['gauges'][name] = gauge.get()
        
        # Get sets
        for name in self._sets:
            with self._set_locks[name]:
                snapshot['sets'][name] = len(self._sets[name])
        
        # Get recent series counts
        for name in self._recent:
            with self._recent_locks[name]:
                snapshot['RECENT_SERIES'][name] = len(self._recent[name])
        
        return snapshot
    
    xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_1': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_1, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_2': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_2, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_3': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_3, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_4': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_4, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_5': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_5, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_6': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_6, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_7': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_7, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_8': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_8, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_9': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_9, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_10': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_10, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_11': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_11, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_12': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_12, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_13': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_13, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_14': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_14, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_15': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_15, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_16': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_16, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_17': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_17, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_18': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_18, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_19': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_19, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_20': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_20, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_21': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_21, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_22': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_22, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_23': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_23, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_24': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_24, 
        'xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_25': xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_25
    }
    
    def get_stats_snapshot(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_stats_snapshot.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_orig)
    xǁThreadSafeMetricsǁget_stats_snapshot__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁget_stats_snapshot'
    
    def xǁThreadSafeMetricsǁreset_all__mutmut_orig(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()
        
        for gauge in self._gauges.values():
            gauge.update(0.0)
        
        for set_name in self._sets:
            with self._set_locks[set_name]:
                self._sets[set_name].clear()
        
        for series_name in self._recent:
            with self._recent_locks[series_name]:
                self._recent[series_name].clear()
        
        self._last_update.update(time.time())
        logger.info(f"Reset all metrics for {self.component_name}")
    
    def xǁThreadSafeMetricsǁreset_all__mutmut_1(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()
        
        for gauge in self._gauges.values():
            gauge.update(None)
        
        for set_name in self._sets:
            with self._set_locks[set_name]:
                self._sets[set_name].clear()
        
        for series_name in self._recent:
            with self._recent_locks[series_name]:
                self._recent[series_name].clear()
        
        self._last_update.update(time.time())
        logger.info(f"Reset all metrics for {self.component_name}")
    
    def xǁThreadSafeMetricsǁreset_all__mutmut_2(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()
        
        for gauge in self._gauges.values():
            gauge.update(1.0)
        
        for set_name in self._sets:
            with self._set_locks[set_name]:
                self._sets[set_name].clear()
        
        for series_name in self._recent:
            with self._recent_locks[series_name]:
                self._recent[series_name].clear()
        
        self._last_update.update(time.time())
        logger.info(f"Reset all metrics for {self.component_name}")
    
    def xǁThreadSafeMetricsǁreset_all__mutmut_3(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()
        
        for gauge in self._gauges.values():
            gauge.update(0.0)
        
        for set_name in self._sets:
            with self._set_locks[set_name]:
                self._sets[set_name].clear()
        
        for series_name in self._recent:
            with self._recent_locks[series_name]:
                self._recent[series_name].clear()
        
        self._last_update.update(None)
        logger.info(f"Reset all metrics for {self.component_name}")
    
    def xǁThreadSafeMetricsǁreset_all__mutmut_4(self) -> None:
        """Reset all metrics."""
        for counter in self._counters.values():
            counter.reset()
        
        for gauge in self._gauges.values():
            gauge.update(0.0)
        
        for set_name in self._sets:
            with self._set_locks[set_name]:
                self._sets[set_name].clear()
        
        for series_name in self._recent:
            with self._recent_locks[series_name]:
                self._recent[series_name].clear()
        
        self._last_update.update(time.time())
        logger.info(None)
    
    xǁThreadSafeMetricsǁreset_all__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁThreadSafeMetricsǁreset_all__mutmut_1': xǁThreadSafeMetricsǁreset_all__mutmut_1, 
        'xǁThreadSafeMetricsǁreset_all__mutmut_2': xǁThreadSafeMetricsǁreset_all__mutmut_2, 
        'xǁThreadSafeMetricsǁreset_all__mutmut_3': xǁThreadSafeMetricsǁreset_all__mutmut_3, 
        'xǁThreadSafeMetricsǁreset_all__mutmut_4': xǁThreadSafeMetricsǁreset_all__mutmut_4
    }
    
    def reset_all(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁThreadSafeMetricsǁreset_all__mutmut_orig"), object.__getattribute__(self, "xǁThreadSafeMetricsǁreset_all__mutmut_mutants"), args, kwargs, self)
        return result 
    
    reset_all.__signature__ = _mutmut_signature(xǁThreadSafeMetricsǁreset_all__mutmut_orig)
    xǁThreadSafeMetricsǁreset_all__mutmut_orig.__name__ = 'xǁThreadSafeMetricsǁreset_all'

class MeshRouterStats:
    """Thread-safe statistics for MeshRouter."""
    
    def xǁMeshRouterStatsǁ__init____mutmut_orig(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_1(self, node_id: str):
        self.node_id = None
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_2(self, node_id: str):
        self.node_id = node_id
        self.metrics = None
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_3(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(None)
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_4(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter(None, 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_5(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", None)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_6(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter(0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_7(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", )  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_8(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("XXtotal_peersXX", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_9(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("TOTAL_PEERS", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_10(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 1)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_11(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge(None, 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_12(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", None)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_13(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge(0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_14(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", )
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_15(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("XXalive_peersXX", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_16(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("ALIVE_PEERS", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_17(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 1.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_18(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge(None, 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_19(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", None)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_20(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge(0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_21(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", )
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_22(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("XXroutes_cachedXX", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_23(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("ROUTES_CACHED", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_24(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 1.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_25(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter(None, 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_26(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", None)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_27(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter(0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_28(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", )
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_29(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("XXconnections_establishedXX", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_30(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("CONNECTIONS_ESTABLISHED", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_31(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 1)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_32(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter(None, 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_33(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", None)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_34(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter(0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_35(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", )
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_36(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("XXconnections_failedXX", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_37(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("CONNECTIONS_FAILED", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_38(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 1)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_39(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter(None, 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_40(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", None)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_41(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter(0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_42(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", )
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_43(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("XXpackets_routedXX", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_44(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("PACKETS_ROUTED", 0)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_45(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 1)
        self.metrics.increment_counter("packets_dropped", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_46(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter(None, 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_47(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", None)
    
    def xǁMeshRouterStatsǁ__init____mutmut_48(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter(0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_49(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", )
    
    def xǁMeshRouterStatsǁ__init____mutmut_50(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("XXpackets_droppedXX", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_51(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("PACKETS_DROPPED", 0)
    
    def xǁMeshRouterStatsǁ__init____mutmut_52(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_router_{node_id}")
        
        # Initialize specific counters
        self.metrics.increment_counter("total_peers", 0)  # Will be updated properly
        self.metrics.set_gauge("alive_peers", 0.0)
        self.metrics.set_gauge("routes_cached", 0.0)
        self.metrics.increment_counter("connections_established", 0)
        self.metrics.increment_counter("connections_failed", 0)
        self.metrics.increment_counter("packets_routed", 0)
        self.metrics.increment_counter("packets_dropped", 1)
    
    xǁMeshRouterStatsǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁ__init____mutmut_1': xǁMeshRouterStatsǁ__init____mutmut_1, 
        'xǁMeshRouterStatsǁ__init____mutmut_2': xǁMeshRouterStatsǁ__init____mutmut_2, 
        'xǁMeshRouterStatsǁ__init____mutmut_3': xǁMeshRouterStatsǁ__init____mutmut_3, 
        'xǁMeshRouterStatsǁ__init____mutmut_4': xǁMeshRouterStatsǁ__init____mutmut_4, 
        'xǁMeshRouterStatsǁ__init____mutmut_5': xǁMeshRouterStatsǁ__init____mutmut_5, 
        'xǁMeshRouterStatsǁ__init____mutmut_6': xǁMeshRouterStatsǁ__init____mutmut_6, 
        'xǁMeshRouterStatsǁ__init____mutmut_7': xǁMeshRouterStatsǁ__init____mutmut_7, 
        'xǁMeshRouterStatsǁ__init____mutmut_8': xǁMeshRouterStatsǁ__init____mutmut_8, 
        'xǁMeshRouterStatsǁ__init____mutmut_9': xǁMeshRouterStatsǁ__init____mutmut_9, 
        'xǁMeshRouterStatsǁ__init____mutmut_10': xǁMeshRouterStatsǁ__init____mutmut_10, 
        'xǁMeshRouterStatsǁ__init____mutmut_11': xǁMeshRouterStatsǁ__init____mutmut_11, 
        'xǁMeshRouterStatsǁ__init____mutmut_12': xǁMeshRouterStatsǁ__init____mutmut_12, 
        'xǁMeshRouterStatsǁ__init____mutmut_13': xǁMeshRouterStatsǁ__init____mutmut_13, 
        'xǁMeshRouterStatsǁ__init____mutmut_14': xǁMeshRouterStatsǁ__init____mutmut_14, 
        'xǁMeshRouterStatsǁ__init____mutmut_15': xǁMeshRouterStatsǁ__init____mutmut_15, 
        'xǁMeshRouterStatsǁ__init____mutmut_16': xǁMeshRouterStatsǁ__init____mutmut_16, 
        'xǁMeshRouterStatsǁ__init____mutmut_17': xǁMeshRouterStatsǁ__init____mutmut_17, 
        'xǁMeshRouterStatsǁ__init____mutmut_18': xǁMeshRouterStatsǁ__init____mutmut_18, 
        'xǁMeshRouterStatsǁ__init____mutmut_19': xǁMeshRouterStatsǁ__init____mutmut_19, 
        'xǁMeshRouterStatsǁ__init____mutmut_20': xǁMeshRouterStatsǁ__init____mutmut_20, 
        'xǁMeshRouterStatsǁ__init____mutmut_21': xǁMeshRouterStatsǁ__init____mutmut_21, 
        'xǁMeshRouterStatsǁ__init____mutmut_22': xǁMeshRouterStatsǁ__init____mutmut_22, 
        'xǁMeshRouterStatsǁ__init____mutmut_23': xǁMeshRouterStatsǁ__init____mutmut_23, 
        'xǁMeshRouterStatsǁ__init____mutmut_24': xǁMeshRouterStatsǁ__init____mutmut_24, 
        'xǁMeshRouterStatsǁ__init____mutmut_25': xǁMeshRouterStatsǁ__init____mutmut_25, 
        'xǁMeshRouterStatsǁ__init____mutmut_26': xǁMeshRouterStatsǁ__init____mutmut_26, 
        'xǁMeshRouterStatsǁ__init____mutmut_27': xǁMeshRouterStatsǁ__init____mutmut_27, 
        'xǁMeshRouterStatsǁ__init____mutmut_28': xǁMeshRouterStatsǁ__init____mutmut_28, 
        'xǁMeshRouterStatsǁ__init____mutmut_29': xǁMeshRouterStatsǁ__init____mutmut_29, 
        'xǁMeshRouterStatsǁ__init____mutmut_30': xǁMeshRouterStatsǁ__init____mutmut_30, 
        'xǁMeshRouterStatsǁ__init____mutmut_31': xǁMeshRouterStatsǁ__init____mutmut_31, 
        'xǁMeshRouterStatsǁ__init____mutmut_32': xǁMeshRouterStatsǁ__init____mutmut_32, 
        'xǁMeshRouterStatsǁ__init____mutmut_33': xǁMeshRouterStatsǁ__init____mutmut_33, 
        'xǁMeshRouterStatsǁ__init____mutmut_34': xǁMeshRouterStatsǁ__init____mutmut_34, 
        'xǁMeshRouterStatsǁ__init____mutmut_35': xǁMeshRouterStatsǁ__init____mutmut_35, 
        'xǁMeshRouterStatsǁ__init____mutmut_36': xǁMeshRouterStatsǁ__init____mutmut_36, 
        'xǁMeshRouterStatsǁ__init____mutmut_37': xǁMeshRouterStatsǁ__init____mutmut_37, 
        'xǁMeshRouterStatsǁ__init____mutmut_38': xǁMeshRouterStatsǁ__init____mutmut_38, 
        'xǁMeshRouterStatsǁ__init____mutmut_39': xǁMeshRouterStatsǁ__init____mutmut_39, 
        'xǁMeshRouterStatsǁ__init____mutmut_40': xǁMeshRouterStatsǁ__init____mutmut_40, 
        'xǁMeshRouterStatsǁ__init____mutmut_41': xǁMeshRouterStatsǁ__init____mutmut_41, 
        'xǁMeshRouterStatsǁ__init____mutmut_42': xǁMeshRouterStatsǁ__init____mutmut_42, 
        'xǁMeshRouterStatsǁ__init____mutmut_43': xǁMeshRouterStatsǁ__init____mutmut_43, 
        'xǁMeshRouterStatsǁ__init____mutmut_44': xǁMeshRouterStatsǁ__init____mutmut_44, 
        'xǁMeshRouterStatsǁ__init____mutmut_45': xǁMeshRouterStatsǁ__init____mutmut_45, 
        'xǁMeshRouterStatsǁ__init____mutmut_46': xǁMeshRouterStatsǁ__init____mutmut_46, 
        'xǁMeshRouterStatsǁ__init____mutmut_47': xǁMeshRouterStatsǁ__init____mutmut_47, 
        'xǁMeshRouterStatsǁ__init____mutmut_48': xǁMeshRouterStatsǁ__init____mutmut_48, 
        'xǁMeshRouterStatsǁ__init____mutmut_49': xǁMeshRouterStatsǁ__init____mutmut_49, 
        'xǁMeshRouterStatsǁ__init____mutmut_50': xǁMeshRouterStatsǁ__init____mutmut_50, 
        'xǁMeshRouterStatsǁ__init____mutmut_51': xǁMeshRouterStatsǁ__init____mutmut_51, 
        'xǁMeshRouterStatsǁ__init____mutmut_52': xǁMeshRouterStatsǁ__init____mutmut_52
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁ__init____mutmut_orig)
    xǁMeshRouterStatsǁ__init____mutmut_orig.__name__ = 'xǁMeshRouterStatsǁ__init__'
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_orig(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_1(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge(None, float(total))
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_2(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", None)
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_3(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge(float(total))
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_4(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", )
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_5(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("XXtotal_peersXX", float(total))
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_6(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("TOTAL_PEERS", float(total))
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_7(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(None))
        self.metrics.set_gauge("alive_peers", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_8(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge(None, float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_9(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("alive_peers", None)
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_10(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge(float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_11(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("alive_peers", )
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_12(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("XXalive_peersXX", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_13(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("ALIVE_PEERS", float(alive))
    
    def xǁMeshRouterStatsǁupdate_peer_count__mutmut_14(self, total: int, alive: int) -> None:
        """Update peer counts."""
        self.metrics.set_gauge("total_peers", float(total))
        self.metrics.set_gauge("alive_peers", float(None))
    
    xǁMeshRouterStatsǁupdate_peer_count__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁupdate_peer_count__mutmut_1': xǁMeshRouterStatsǁupdate_peer_count__mutmut_1, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_2': xǁMeshRouterStatsǁupdate_peer_count__mutmut_2, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_3': xǁMeshRouterStatsǁupdate_peer_count__mutmut_3, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_4': xǁMeshRouterStatsǁupdate_peer_count__mutmut_4, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_5': xǁMeshRouterStatsǁupdate_peer_count__mutmut_5, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_6': xǁMeshRouterStatsǁupdate_peer_count__mutmut_6, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_7': xǁMeshRouterStatsǁupdate_peer_count__mutmut_7, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_8': xǁMeshRouterStatsǁupdate_peer_count__mutmut_8, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_9': xǁMeshRouterStatsǁupdate_peer_count__mutmut_9, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_10': xǁMeshRouterStatsǁupdate_peer_count__mutmut_10, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_11': xǁMeshRouterStatsǁupdate_peer_count__mutmut_11, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_12': xǁMeshRouterStatsǁupdate_peer_count__mutmut_12, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_13': xǁMeshRouterStatsǁupdate_peer_count__mutmut_13, 
        'xǁMeshRouterStatsǁupdate_peer_count__mutmut_14': xǁMeshRouterStatsǁupdate_peer_count__mutmut_14
    }
    
    def update_peer_count(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁupdate_peer_count__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁupdate_peer_count__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_peer_count.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁupdate_peer_count__mutmut_orig)
    xǁMeshRouterStatsǁupdate_peer_count__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁupdate_peer_count'
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_orig(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("routes_cached", float(cached_routes))
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_1(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge(None, float(cached_routes))
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_2(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("routes_cached", None)
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_3(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge(float(cached_routes))
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_4(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("routes_cached", )
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_5(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("XXroutes_cachedXX", float(cached_routes))
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_6(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("ROUTES_CACHED", float(cached_routes))
    
    def xǁMeshRouterStatsǁupdate_route_cache__mutmut_7(self, cached_routes: int) -> None:
        """Update route cache size."""
        self.metrics.set_gauge("routes_cached", float(None))
    
    xǁMeshRouterStatsǁupdate_route_cache__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁupdate_route_cache__mutmut_1': xǁMeshRouterStatsǁupdate_route_cache__mutmut_1, 
        'xǁMeshRouterStatsǁupdate_route_cache__mutmut_2': xǁMeshRouterStatsǁupdate_route_cache__mutmut_2, 
        'xǁMeshRouterStatsǁupdate_route_cache__mutmut_3': xǁMeshRouterStatsǁupdate_route_cache__mutmut_3, 
        'xǁMeshRouterStatsǁupdate_route_cache__mutmut_4': xǁMeshRouterStatsǁupdate_route_cache__mutmut_4, 
        'xǁMeshRouterStatsǁupdate_route_cache__mutmut_5': xǁMeshRouterStatsǁupdate_route_cache__mutmut_5, 
        'xǁMeshRouterStatsǁupdate_route_cache__mutmut_6': xǁMeshRouterStatsǁupdate_route_cache__mutmut_6, 
        'xǁMeshRouterStatsǁupdate_route_cache__mutmut_7': xǁMeshRouterStatsǁupdate_route_cache__mutmut_7
    }
    
    def update_route_cache(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁupdate_route_cache__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁupdate_route_cache__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_route_cache.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁupdate_route_cache__mutmut_orig)
    xǁMeshRouterStatsǁupdate_route_cache__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁupdate_route_cache'
    
    def xǁMeshRouterStatsǁrecord_connection_established__mutmut_orig(self) -> None:
        """Record successful connection."""
        self.metrics.increment_counter("connections_established")
    
    def xǁMeshRouterStatsǁrecord_connection_established__mutmut_1(self) -> None:
        """Record successful connection."""
        self.metrics.increment_counter(None)
    
    def xǁMeshRouterStatsǁrecord_connection_established__mutmut_2(self) -> None:
        """Record successful connection."""
        self.metrics.increment_counter("XXconnections_establishedXX")
    
    def xǁMeshRouterStatsǁrecord_connection_established__mutmut_3(self) -> None:
        """Record successful connection."""
        self.metrics.increment_counter("CONNECTIONS_ESTABLISHED")
    
    xǁMeshRouterStatsǁrecord_connection_established__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁrecord_connection_established__mutmut_1': xǁMeshRouterStatsǁrecord_connection_established__mutmut_1, 
        'xǁMeshRouterStatsǁrecord_connection_established__mutmut_2': xǁMeshRouterStatsǁrecord_connection_established__mutmut_2, 
        'xǁMeshRouterStatsǁrecord_connection_established__mutmut_3': xǁMeshRouterStatsǁrecord_connection_established__mutmut_3
    }
    
    def record_connection_established(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_connection_established__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_connection_established__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_connection_established.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁrecord_connection_established__mutmut_orig)
    xǁMeshRouterStatsǁrecord_connection_established__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁrecord_connection_established'
    
    def xǁMeshRouterStatsǁrecord_connection_failed__mutmut_orig(self) -> None:
        """Record failed connection."""
        self.metrics.increment_counter("connections_failed")
    
    def xǁMeshRouterStatsǁrecord_connection_failed__mutmut_1(self) -> None:
        """Record failed connection."""
        self.metrics.increment_counter(None)
    
    def xǁMeshRouterStatsǁrecord_connection_failed__mutmut_2(self) -> None:
        """Record failed connection."""
        self.metrics.increment_counter("XXconnections_failedXX")
    
    def xǁMeshRouterStatsǁrecord_connection_failed__mutmut_3(self) -> None:
        """Record failed connection."""
        self.metrics.increment_counter("CONNECTIONS_FAILED")
    
    xǁMeshRouterStatsǁrecord_connection_failed__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁrecord_connection_failed__mutmut_1': xǁMeshRouterStatsǁrecord_connection_failed__mutmut_1, 
        'xǁMeshRouterStatsǁrecord_connection_failed__mutmut_2': xǁMeshRouterStatsǁrecord_connection_failed__mutmut_2, 
        'xǁMeshRouterStatsǁrecord_connection_failed__mutmut_3': xǁMeshRouterStatsǁrecord_connection_failed__mutmut_3
    }
    
    def record_connection_failed(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_connection_failed__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_connection_failed__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_connection_failed.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁrecord_connection_failed__mutmut_orig)
    xǁMeshRouterStatsǁrecord_connection_failed__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁrecord_connection_failed'
    
    def xǁMeshRouterStatsǁrecord_packet_routed__mutmut_orig(self) -> None:
        """Record packet routed successfully."""
        self.metrics.increment_counter("packets_routed")
    
    def xǁMeshRouterStatsǁrecord_packet_routed__mutmut_1(self) -> None:
        """Record packet routed successfully."""
        self.metrics.increment_counter(None)
    
    def xǁMeshRouterStatsǁrecord_packet_routed__mutmut_2(self) -> None:
        """Record packet routed successfully."""
        self.metrics.increment_counter("XXpackets_routedXX")
    
    def xǁMeshRouterStatsǁrecord_packet_routed__mutmut_3(self) -> None:
        """Record packet routed successfully."""
        self.metrics.increment_counter("PACKETS_ROUTED")
    
    xǁMeshRouterStatsǁrecord_packet_routed__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁrecord_packet_routed__mutmut_1': xǁMeshRouterStatsǁrecord_packet_routed__mutmut_1, 
        'xǁMeshRouterStatsǁrecord_packet_routed__mutmut_2': xǁMeshRouterStatsǁrecord_packet_routed__mutmut_2, 
        'xǁMeshRouterStatsǁrecord_packet_routed__mutmut_3': xǁMeshRouterStatsǁrecord_packet_routed__mutmut_3
    }
    
    def record_packet_routed(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_packet_routed__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_packet_routed__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_packet_routed.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁrecord_packet_routed__mutmut_orig)
    xǁMeshRouterStatsǁrecord_packet_routed__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁrecord_packet_routed'
    
    def xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_orig(self) -> None:
        """Record packet dropped."""
        self.metrics.increment_counter("packets_dropped")
    
    def xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_1(self) -> None:
        """Record packet dropped."""
        self.metrics.increment_counter(None)
    
    def xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_2(self) -> None:
        """Record packet dropped."""
        self.metrics.increment_counter("XXpackets_droppedXX")
    
    def xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_3(self) -> None:
        """Record packet dropped."""
        self.metrics.increment_counter("PACKETS_DROPPED")
    
    xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_1': xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_1, 
        'xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_2': xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_2, 
        'xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_3': xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_3
    }
    
    def record_packet_dropped(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_packet_dropped.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_orig)
    xǁMeshRouterStatsǁrecord_packet_dropped__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁrecord_packet_dropped'
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_orig(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent("peer_latencies", (peer_id, latency_ms))
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_1(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent(None, (peer_id, latency_ms))
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_2(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent("peer_latencies", None)
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_3(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent((peer_id, latency_ms))
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_4(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent("peer_latencies", )
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_5(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent("XXpeer_latenciesXX", (peer_id, latency_ms))
    
    def xǁMeshRouterStatsǁupdate_peer_latency__mutmut_6(self, peer_id: str, latency_ms: float) -> None:
        """Update peer latency measurement."""
        self.metrics.add_recent("PEER_LATENCIES", (peer_id, latency_ms))
    
    xǁMeshRouterStatsǁupdate_peer_latency__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁupdate_peer_latency__mutmut_1': xǁMeshRouterStatsǁupdate_peer_latency__mutmut_1, 
        'xǁMeshRouterStatsǁupdate_peer_latency__mutmut_2': xǁMeshRouterStatsǁupdate_peer_latency__mutmut_2, 
        'xǁMeshRouterStatsǁupdate_peer_latency__mutmut_3': xǁMeshRouterStatsǁupdate_peer_latency__mutmut_3, 
        'xǁMeshRouterStatsǁupdate_peer_latency__mutmut_4': xǁMeshRouterStatsǁupdate_peer_latency__mutmut_4, 
        'xǁMeshRouterStatsǁupdate_peer_latency__mutmut_5': xǁMeshRouterStatsǁupdate_peer_latency__mutmut_5, 
        'xǁMeshRouterStatsǁupdate_peer_latency__mutmut_6': xǁMeshRouterStatsǁupdate_peer_latency__mutmut_6
    }
    
    def update_peer_latency(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁupdate_peer_latency__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁupdate_peer_latency__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_peer_latency.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁupdate_peer_latency__mutmut_orig)
    xǁMeshRouterStatsǁupdate_peer_latency__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁupdate_peer_latency'
    
    def xǁMeshRouterStatsǁget_stats__mutmut_orig(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_1(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = None
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_2(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = None
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_3(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['XXsuccess_rateXX'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_4(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['SUCCESS_RATE'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_5(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 1.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_6(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = None
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_7(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) - stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_8(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get(None, 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_9(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', None) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_10(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get(0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_11(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', ) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_12(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['XXcountersXX'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_13(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['COUNTERS'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_14(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('XXconnections_establishedXX', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_15(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('CONNECTIONS_ESTABLISHED', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_16(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 1) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_17(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get(None, 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_18(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', None))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_19(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get(0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_20(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', ))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_21(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['XXcountersXX'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_22(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['COUNTERS'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_23(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('XXconnections_failedXX', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_24(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('CONNECTIONS_FAILED', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_25(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 1))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_26(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts >= 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_27(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 1:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_28(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = None
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_29(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['XXsuccess_rateXX'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_30(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['SUCCESS_RATE'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_31(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) * total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_32(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get(None, 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_33(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', None) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_34(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get(0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_35(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', ) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_36(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['XXcountersXX'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_37(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['COUNTERS'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_38(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('XXconnections_establishedXX', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_39(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('CONNECTIONS_ESTABLISHED', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_40(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 1) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_41(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = None
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_42(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent(None, 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_43(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", None)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_44(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent(100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_45(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", )
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_46(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("XXpeer_latenciesXX", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_47(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("PEER_LATENCIES", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_48(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 101)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_49(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = None
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_50(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = None
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_51(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['XXavg_latencyXX'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_52(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['AVG_LATENCY'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_53(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) * len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_54(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(None) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_55(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = None
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_56(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['XXmin_latencyXX'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_57(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['MIN_LATENCY'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_58(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(None)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_59(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = None
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_60(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['XXmax_latencyXX'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_61(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['MAX_LATENCY'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_62(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(None)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_63(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = None
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_64(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['XXavg_latencyXX'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_65(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['AVG_LATENCY'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_66(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 1.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_67(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = None
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_68(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['XXmin_latencyXX'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_69(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['MIN_LATENCY'] = 0.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_70(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 1.0
            stats['max_latency'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_71(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = None
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_72(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['XXmax_latencyXX'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_73(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['MAX_LATENCY'] = 0.0
        
        return stats
    
    def xǁMeshRouterStatsǁget_stats__mutmut_74(self) -> Dict[str, Any]:
        """Get router statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        stats['success_rate'] = 0.0
        total_attempts = (stats['counters'].get('connections_established', 0) + 
                         stats['counters'].get('connections_failed', 0))
        if total_attempts > 0:
            stats['success_rate'] = stats['counters'].get('connections_established', 0) / total_attempts
        
        # Add recent latency stats
        recent_latencies = self.metrics.get_recent("peer_latencies", 100)
        if recent_latencies:
            latencies = [lat for _, lat in recent_latencies]
            stats['avg_latency'] = sum(latencies) / len(latencies)
            stats['min_latency'] = min(latencies)
            stats['max_latency'] = max(latencies)
        else:
            stats['avg_latency'] = 0.0
            stats['min_latency'] = 0.0
            stats['max_latency'] = 1.0
        
        return stats
    
    xǁMeshRouterStatsǁget_stats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshRouterStatsǁget_stats__mutmut_1': xǁMeshRouterStatsǁget_stats__mutmut_1, 
        'xǁMeshRouterStatsǁget_stats__mutmut_2': xǁMeshRouterStatsǁget_stats__mutmut_2, 
        'xǁMeshRouterStatsǁget_stats__mutmut_3': xǁMeshRouterStatsǁget_stats__mutmut_3, 
        'xǁMeshRouterStatsǁget_stats__mutmut_4': xǁMeshRouterStatsǁget_stats__mutmut_4, 
        'xǁMeshRouterStatsǁget_stats__mutmut_5': xǁMeshRouterStatsǁget_stats__mutmut_5, 
        'xǁMeshRouterStatsǁget_stats__mutmut_6': xǁMeshRouterStatsǁget_stats__mutmut_6, 
        'xǁMeshRouterStatsǁget_stats__mutmut_7': xǁMeshRouterStatsǁget_stats__mutmut_7, 
        'xǁMeshRouterStatsǁget_stats__mutmut_8': xǁMeshRouterStatsǁget_stats__mutmut_8, 
        'xǁMeshRouterStatsǁget_stats__mutmut_9': xǁMeshRouterStatsǁget_stats__mutmut_9, 
        'xǁMeshRouterStatsǁget_stats__mutmut_10': xǁMeshRouterStatsǁget_stats__mutmut_10, 
        'xǁMeshRouterStatsǁget_stats__mutmut_11': xǁMeshRouterStatsǁget_stats__mutmut_11, 
        'xǁMeshRouterStatsǁget_stats__mutmut_12': xǁMeshRouterStatsǁget_stats__mutmut_12, 
        'xǁMeshRouterStatsǁget_stats__mutmut_13': xǁMeshRouterStatsǁget_stats__mutmut_13, 
        'xǁMeshRouterStatsǁget_stats__mutmut_14': xǁMeshRouterStatsǁget_stats__mutmut_14, 
        'xǁMeshRouterStatsǁget_stats__mutmut_15': xǁMeshRouterStatsǁget_stats__mutmut_15, 
        'xǁMeshRouterStatsǁget_stats__mutmut_16': xǁMeshRouterStatsǁget_stats__mutmut_16, 
        'xǁMeshRouterStatsǁget_stats__mutmut_17': xǁMeshRouterStatsǁget_stats__mutmut_17, 
        'xǁMeshRouterStatsǁget_stats__mutmut_18': xǁMeshRouterStatsǁget_stats__mutmut_18, 
        'xǁMeshRouterStatsǁget_stats__mutmut_19': xǁMeshRouterStatsǁget_stats__mutmut_19, 
        'xǁMeshRouterStatsǁget_stats__mutmut_20': xǁMeshRouterStatsǁget_stats__mutmut_20, 
        'xǁMeshRouterStatsǁget_stats__mutmut_21': xǁMeshRouterStatsǁget_stats__mutmut_21, 
        'xǁMeshRouterStatsǁget_stats__mutmut_22': xǁMeshRouterStatsǁget_stats__mutmut_22, 
        'xǁMeshRouterStatsǁget_stats__mutmut_23': xǁMeshRouterStatsǁget_stats__mutmut_23, 
        'xǁMeshRouterStatsǁget_stats__mutmut_24': xǁMeshRouterStatsǁget_stats__mutmut_24, 
        'xǁMeshRouterStatsǁget_stats__mutmut_25': xǁMeshRouterStatsǁget_stats__mutmut_25, 
        'xǁMeshRouterStatsǁget_stats__mutmut_26': xǁMeshRouterStatsǁget_stats__mutmut_26, 
        'xǁMeshRouterStatsǁget_stats__mutmut_27': xǁMeshRouterStatsǁget_stats__mutmut_27, 
        'xǁMeshRouterStatsǁget_stats__mutmut_28': xǁMeshRouterStatsǁget_stats__mutmut_28, 
        'xǁMeshRouterStatsǁget_stats__mutmut_29': xǁMeshRouterStatsǁget_stats__mutmut_29, 
        'xǁMeshRouterStatsǁget_stats__mutmut_30': xǁMeshRouterStatsǁget_stats__mutmut_30, 
        'xǁMeshRouterStatsǁget_stats__mutmut_31': xǁMeshRouterStatsǁget_stats__mutmut_31, 
        'xǁMeshRouterStatsǁget_stats__mutmut_32': xǁMeshRouterStatsǁget_stats__mutmut_32, 
        'xǁMeshRouterStatsǁget_stats__mutmut_33': xǁMeshRouterStatsǁget_stats__mutmut_33, 
        'xǁMeshRouterStatsǁget_stats__mutmut_34': xǁMeshRouterStatsǁget_stats__mutmut_34, 
        'xǁMeshRouterStatsǁget_stats__mutmut_35': xǁMeshRouterStatsǁget_stats__mutmut_35, 
        'xǁMeshRouterStatsǁget_stats__mutmut_36': xǁMeshRouterStatsǁget_stats__mutmut_36, 
        'xǁMeshRouterStatsǁget_stats__mutmut_37': xǁMeshRouterStatsǁget_stats__mutmut_37, 
        'xǁMeshRouterStatsǁget_stats__mutmut_38': xǁMeshRouterStatsǁget_stats__mutmut_38, 
        'xǁMeshRouterStatsǁget_stats__mutmut_39': xǁMeshRouterStatsǁget_stats__mutmut_39, 
        'xǁMeshRouterStatsǁget_stats__mutmut_40': xǁMeshRouterStatsǁget_stats__mutmut_40, 
        'xǁMeshRouterStatsǁget_stats__mutmut_41': xǁMeshRouterStatsǁget_stats__mutmut_41, 
        'xǁMeshRouterStatsǁget_stats__mutmut_42': xǁMeshRouterStatsǁget_stats__mutmut_42, 
        'xǁMeshRouterStatsǁget_stats__mutmut_43': xǁMeshRouterStatsǁget_stats__mutmut_43, 
        'xǁMeshRouterStatsǁget_stats__mutmut_44': xǁMeshRouterStatsǁget_stats__mutmut_44, 
        'xǁMeshRouterStatsǁget_stats__mutmut_45': xǁMeshRouterStatsǁget_stats__mutmut_45, 
        'xǁMeshRouterStatsǁget_stats__mutmut_46': xǁMeshRouterStatsǁget_stats__mutmut_46, 
        'xǁMeshRouterStatsǁget_stats__mutmut_47': xǁMeshRouterStatsǁget_stats__mutmut_47, 
        'xǁMeshRouterStatsǁget_stats__mutmut_48': xǁMeshRouterStatsǁget_stats__mutmut_48, 
        'xǁMeshRouterStatsǁget_stats__mutmut_49': xǁMeshRouterStatsǁget_stats__mutmut_49, 
        'xǁMeshRouterStatsǁget_stats__mutmut_50': xǁMeshRouterStatsǁget_stats__mutmut_50, 
        'xǁMeshRouterStatsǁget_stats__mutmut_51': xǁMeshRouterStatsǁget_stats__mutmut_51, 
        'xǁMeshRouterStatsǁget_stats__mutmut_52': xǁMeshRouterStatsǁget_stats__mutmut_52, 
        'xǁMeshRouterStatsǁget_stats__mutmut_53': xǁMeshRouterStatsǁget_stats__mutmut_53, 
        'xǁMeshRouterStatsǁget_stats__mutmut_54': xǁMeshRouterStatsǁget_stats__mutmut_54, 
        'xǁMeshRouterStatsǁget_stats__mutmut_55': xǁMeshRouterStatsǁget_stats__mutmut_55, 
        'xǁMeshRouterStatsǁget_stats__mutmut_56': xǁMeshRouterStatsǁget_stats__mutmut_56, 
        'xǁMeshRouterStatsǁget_stats__mutmut_57': xǁMeshRouterStatsǁget_stats__mutmut_57, 
        'xǁMeshRouterStatsǁget_stats__mutmut_58': xǁMeshRouterStatsǁget_stats__mutmut_58, 
        'xǁMeshRouterStatsǁget_stats__mutmut_59': xǁMeshRouterStatsǁget_stats__mutmut_59, 
        'xǁMeshRouterStatsǁget_stats__mutmut_60': xǁMeshRouterStatsǁget_stats__mutmut_60, 
        'xǁMeshRouterStatsǁget_stats__mutmut_61': xǁMeshRouterStatsǁget_stats__mutmut_61, 
        'xǁMeshRouterStatsǁget_stats__mutmut_62': xǁMeshRouterStatsǁget_stats__mutmut_62, 
        'xǁMeshRouterStatsǁget_stats__mutmut_63': xǁMeshRouterStatsǁget_stats__mutmut_63, 
        'xǁMeshRouterStatsǁget_stats__mutmut_64': xǁMeshRouterStatsǁget_stats__mutmut_64, 
        'xǁMeshRouterStatsǁget_stats__mutmut_65': xǁMeshRouterStatsǁget_stats__mutmut_65, 
        'xǁMeshRouterStatsǁget_stats__mutmut_66': xǁMeshRouterStatsǁget_stats__mutmut_66, 
        'xǁMeshRouterStatsǁget_stats__mutmut_67': xǁMeshRouterStatsǁget_stats__mutmut_67, 
        'xǁMeshRouterStatsǁget_stats__mutmut_68': xǁMeshRouterStatsǁget_stats__mutmut_68, 
        'xǁMeshRouterStatsǁget_stats__mutmut_69': xǁMeshRouterStatsǁget_stats__mutmut_69, 
        'xǁMeshRouterStatsǁget_stats__mutmut_70': xǁMeshRouterStatsǁget_stats__mutmut_70, 
        'xǁMeshRouterStatsǁget_stats__mutmut_71': xǁMeshRouterStatsǁget_stats__mutmut_71, 
        'xǁMeshRouterStatsǁget_stats__mutmut_72': xǁMeshRouterStatsǁget_stats__mutmut_72, 
        'xǁMeshRouterStatsǁget_stats__mutmut_73': xǁMeshRouterStatsǁget_stats__mutmut_73, 
        'xǁMeshRouterStatsǁget_stats__mutmut_74': xǁMeshRouterStatsǁget_stats__mutmut_74
    }
    
    def get_stats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshRouterStatsǁget_stats__mutmut_orig"), object.__getattribute__(self, "xǁMeshRouterStatsǁget_stats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_stats.__signature__ = _mutmut_signature(xǁMeshRouterStatsǁget_stats__mutmut_orig)
    xǁMeshRouterStatsǁget_stats__mutmut_orig.__name__ = 'xǁMeshRouterStatsǁget_stats'

class MeshTopologyStats:
    """Thread-safe statistics for MeshTopology."""
    
    def xǁMeshTopologyStatsǁ__init____mutmut_orig(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_1(self, node_id: str):
        self.node_id = None
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_2(self, node_id: str):
        self.node_id = node_id
        self.metrics = None
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_3(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(None)
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_4(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge(None, 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_5(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", None)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_6(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge(0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_7(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", )
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_8(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("XXtotal_nodesXX", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_9(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("TOTAL_NODES", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_10(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 1.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_11(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge(None, 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_12(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", None)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_13(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge(0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_14(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", )
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_15(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("XXtotal_linksXX", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_16(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("TOTAL_LINKS", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_17(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 1.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_18(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge(None, 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_19(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", None)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_20(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge(0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_21(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", )
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_22(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("XXcache_sizeXX", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_23(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("CACHE_SIZE", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_24(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 1.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_25(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter(None, 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_26(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", None)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_27(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter(0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_28(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", )
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_29(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("XXpath_computationsXX", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_30(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("PATH_COMPUTATIONS", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_31(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 1)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_32(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter(None, 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_33(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", None)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_34(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter(0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_35(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", )
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_36(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("XXcache_hitsXX", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_37(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("CACHE_HITS", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_38(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 1)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_39(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter(None, 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_40(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", None)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_41(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter(0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_42(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", )
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_43(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("XXcache_missesXX", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_44(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("CACHE_MISSES", 0)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_45(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 1)
        self.metrics.increment_counter("failover_events", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_46(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter(None, 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_47(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", None)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_48(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter(0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_49(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", )
    
    def xǁMeshTopologyStatsǁ__init____mutmut_50(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("XXfailover_eventsXX", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_51(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("FAILOVER_EVENTS", 0)
    
    def xǁMeshTopologyStatsǁ__init____mutmut_52(self, node_id: str):
        self.node_id = node_id
        self.metrics = ThreadSafeMetrics(f"mesh_topology_{node_id}")
        
        # Initialize specific counters
        self.metrics.set_gauge("total_nodes", 0.0)
        self.metrics.set_gauge("total_links", 0.0)
        self.metrics.set_gauge("cache_size", 0.0)
        self.metrics.increment_counter("path_computations", 0)
        self.metrics.increment_counter("cache_hits", 0)
        self.metrics.increment_counter("cache_misses", 0)
        self.metrics.increment_counter("failover_events", 1)
    
    xǁMeshTopologyStatsǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁ__init____mutmut_1': xǁMeshTopologyStatsǁ__init____mutmut_1, 
        'xǁMeshTopologyStatsǁ__init____mutmut_2': xǁMeshTopologyStatsǁ__init____mutmut_2, 
        'xǁMeshTopologyStatsǁ__init____mutmut_3': xǁMeshTopologyStatsǁ__init____mutmut_3, 
        'xǁMeshTopologyStatsǁ__init____mutmut_4': xǁMeshTopologyStatsǁ__init____mutmut_4, 
        'xǁMeshTopologyStatsǁ__init____mutmut_5': xǁMeshTopologyStatsǁ__init____mutmut_5, 
        'xǁMeshTopologyStatsǁ__init____mutmut_6': xǁMeshTopologyStatsǁ__init____mutmut_6, 
        'xǁMeshTopologyStatsǁ__init____mutmut_7': xǁMeshTopologyStatsǁ__init____mutmut_7, 
        'xǁMeshTopologyStatsǁ__init____mutmut_8': xǁMeshTopologyStatsǁ__init____mutmut_8, 
        'xǁMeshTopologyStatsǁ__init____mutmut_9': xǁMeshTopologyStatsǁ__init____mutmut_9, 
        'xǁMeshTopologyStatsǁ__init____mutmut_10': xǁMeshTopologyStatsǁ__init____mutmut_10, 
        'xǁMeshTopologyStatsǁ__init____mutmut_11': xǁMeshTopologyStatsǁ__init____mutmut_11, 
        'xǁMeshTopologyStatsǁ__init____mutmut_12': xǁMeshTopologyStatsǁ__init____mutmut_12, 
        'xǁMeshTopologyStatsǁ__init____mutmut_13': xǁMeshTopologyStatsǁ__init____mutmut_13, 
        'xǁMeshTopologyStatsǁ__init____mutmut_14': xǁMeshTopologyStatsǁ__init____mutmut_14, 
        'xǁMeshTopologyStatsǁ__init____mutmut_15': xǁMeshTopologyStatsǁ__init____mutmut_15, 
        'xǁMeshTopologyStatsǁ__init____mutmut_16': xǁMeshTopologyStatsǁ__init____mutmut_16, 
        'xǁMeshTopologyStatsǁ__init____mutmut_17': xǁMeshTopologyStatsǁ__init____mutmut_17, 
        'xǁMeshTopologyStatsǁ__init____mutmut_18': xǁMeshTopologyStatsǁ__init____mutmut_18, 
        'xǁMeshTopologyStatsǁ__init____mutmut_19': xǁMeshTopologyStatsǁ__init____mutmut_19, 
        'xǁMeshTopologyStatsǁ__init____mutmut_20': xǁMeshTopologyStatsǁ__init____mutmut_20, 
        'xǁMeshTopologyStatsǁ__init____mutmut_21': xǁMeshTopologyStatsǁ__init____mutmut_21, 
        'xǁMeshTopologyStatsǁ__init____mutmut_22': xǁMeshTopologyStatsǁ__init____mutmut_22, 
        'xǁMeshTopologyStatsǁ__init____mutmut_23': xǁMeshTopologyStatsǁ__init____mutmut_23, 
        'xǁMeshTopologyStatsǁ__init____mutmut_24': xǁMeshTopologyStatsǁ__init____mutmut_24, 
        'xǁMeshTopologyStatsǁ__init____mutmut_25': xǁMeshTopologyStatsǁ__init____mutmut_25, 
        'xǁMeshTopologyStatsǁ__init____mutmut_26': xǁMeshTopologyStatsǁ__init____mutmut_26, 
        'xǁMeshTopologyStatsǁ__init____mutmut_27': xǁMeshTopologyStatsǁ__init____mutmut_27, 
        'xǁMeshTopologyStatsǁ__init____mutmut_28': xǁMeshTopologyStatsǁ__init____mutmut_28, 
        'xǁMeshTopologyStatsǁ__init____mutmut_29': xǁMeshTopologyStatsǁ__init____mutmut_29, 
        'xǁMeshTopologyStatsǁ__init____mutmut_30': xǁMeshTopologyStatsǁ__init____mutmut_30, 
        'xǁMeshTopologyStatsǁ__init____mutmut_31': xǁMeshTopologyStatsǁ__init____mutmut_31, 
        'xǁMeshTopologyStatsǁ__init____mutmut_32': xǁMeshTopologyStatsǁ__init____mutmut_32, 
        'xǁMeshTopologyStatsǁ__init____mutmut_33': xǁMeshTopologyStatsǁ__init____mutmut_33, 
        'xǁMeshTopologyStatsǁ__init____mutmut_34': xǁMeshTopologyStatsǁ__init____mutmut_34, 
        'xǁMeshTopologyStatsǁ__init____mutmut_35': xǁMeshTopologyStatsǁ__init____mutmut_35, 
        'xǁMeshTopologyStatsǁ__init____mutmut_36': xǁMeshTopologyStatsǁ__init____mutmut_36, 
        'xǁMeshTopologyStatsǁ__init____mutmut_37': xǁMeshTopologyStatsǁ__init____mutmut_37, 
        'xǁMeshTopologyStatsǁ__init____mutmut_38': xǁMeshTopologyStatsǁ__init____mutmut_38, 
        'xǁMeshTopologyStatsǁ__init____mutmut_39': xǁMeshTopologyStatsǁ__init____mutmut_39, 
        'xǁMeshTopologyStatsǁ__init____mutmut_40': xǁMeshTopologyStatsǁ__init____mutmut_40, 
        'xǁMeshTopologyStatsǁ__init____mutmut_41': xǁMeshTopologyStatsǁ__init____mutmut_41, 
        'xǁMeshTopologyStatsǁ__init____mutmut_42': xǁMeshTopologyStatsǁ__init____mutmut_42, 
        'xǁMeshTopologyStatsǁ__init____mutmut_43': xǁMeshTopologyStatsǁ__init____mutmut_43, 
        'xǁMeshTopologyStatsǁ__init____mutmut_44': xǁMeshTopologyStatsǁ__init____mutmut_44, 
        'xǁMeshTopologyStatsǁ__init____mutmut_45': xǁMeshTopologyStatsǁ__init____mutmut_45, 
        'xǁMeshTopologyStatsǁ__init____mutmut_46': xǁMeshTopologyStatsǁ__init____mutmut_46, 
        'xǁMeshTopologyStatsǁ__init____mutmut_47': xǁMeshTopologyStatsǁ__init____mutmut_47, 
        'xǁMeshTopologyStatsǁ__init____mutmut_48': xǁMeshTopologyStatsǁ__init____mutmut_48, 
        'xǁMeshTopologyStatsǁ__init____mutmut_49': xǁMeshTopologyStatsǁ__init____mutmut_49, 
        'xǁMeshTopologyStatsǁ__init____mutmut_50': xǁMeshTopologyStatsǁ__init____mutmut_50, 
        'xǁMeshTopologyStatsǁ__init____mutmut_51': xǁMeshTopologyStatsǁ__init____mutmut_51, 
        'xǁMeshTopologyStatsǁ__init____mutmut_52': xǁMeshTopologyStatsǁ__init____mutmut_52
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁ__init____mutmut_orig)
    xǁMeshTopologyStatsǁ__init____mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁ__init__'
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_orig(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_1(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge(None, float(nodes))
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_2(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", None)
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_3(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge(float(nodes))
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_4(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", )
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_5(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("XXtotal_nodesXX", float(nodes))
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_6(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("TOTAL_NODES", float(nodes))
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_7(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(None))
        self.metrics.set_gauge("total_links", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_8(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge(None, float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_9(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("total_links", None)
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_10(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge(float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_11(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("total_links", )
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_12(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("XXtotal_linksXX", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_13(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("TOTAL_LINKS", float(links))
    
    def xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_14(self, nodes: int, links: int) -> None:
        """Update topology node and link counts."""
        self.metrics.set_gauge("total_nodes", float(nodes))
        self.metrics.set_gauge("total_links", float(None))
    
    xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_1': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_1, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_2': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_2, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_3': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_3, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_4': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_4, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_5': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_5, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_6': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_6, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_7': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_7, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_8': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_8, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_9': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_9, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_10': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_10, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_11': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_11, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_12': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_12, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_13': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_13, 
        'xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_14': xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_14
    }
    
    def update_topology_counts(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_topology_counts.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_orig)
    xǁMeshTopologyStatsǁupdate_topology_counts__mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁupdate_topology_counts'
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_orig(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("cache_size", float(size))
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_1(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge(None, float(size))
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_2(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("cache_size", None)
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_3(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge(float(size))
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_4(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("cache_size", )
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_5(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("XXcache_sizeXX", float(size))
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_6(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("CACHE_SIZE", float(size))
    
    def xǁMeshTopologyStatsǁupdate_cache_size__mutmut_7(self, size: int) -> None:
        """Update path cache size."""
        self.metrics.set_gauge("cache_size", float(None))
    
    xǁMeshTopologyStatsǁupdate_cache_size__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_1': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_1, 
        'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_2': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_2, 
        'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_3': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_3, 
        'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_4': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_4, 
        'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_5': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_5, 
        'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_6': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_6, 
        'xǁMeshTopologyStatsǁupdate_cache_size__mutmut_7': xǁMeshTopologyStatsǁupdate_cache_size__mutmut_7
    }
    
    def update_cache_size(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁupdate_cache_size__mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁupdate_cache_size__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_cache_size.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁupdate_cache_size__mutmut_orig)
    xǁMeshTopologyStatsǁupdate_cache_size__mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁupdate_cache_size'
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_orig(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("path_computations")
        self.metrics.increment_counter("cache_misses")
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_1(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter(None)
        self.metrics.increment_counter("cache_misses")
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_2(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("XXpath_computationsXX")
        self.metrics.increment_counter("cache_misses")
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_3(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("PATH_COMPUTATIONS")
        self.metrics.increment_counter("cache_misses")
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_4(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("path_computations")
        self.metrics.increment_counter(None)
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_5(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("path_computations")
        self.metrics.increment_counter("XXcache_missesXX")
    
    def xǁMeshTopologyStatsǁrecord_path_computation__mutmut_6(self) -> None:
        """Record path computation."""
        self.metrics.increment_counter("path_computations")
        self.metrics.increment_counter("CACHE_MISSES")
    
    xǁMeshTopologyStatsǁrecord_path_computation__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁrecord_path_computation__mutmut_1': xǁMeshTopologyStatsǁrecord_path_computation__mutmut_1, 
        'xǁMeshTopologyStatsǁrecord_path_computation__mutmut_2': xǁMeshTopologyStatsǁrecord_path_computation__mutmut_2, 
        'xǁMeshTopologyStatsǁrecord_path_computation__mutmut_3': xǁMeshTopologyStatsǁrecord_path_computation__mutmut_3, 
        'xǁMeshTopologyStatsǁrecord_path_computation__mutmut_4': xǁMeshTopologyStatsǁrecord_path_computation__mutmut_4, 
        'xǁMeshTopologyStatsǁrecord_path_computation__mutmut_5': xǁMeshTopologyStatsǁrecord_path_computation__mutmut_5, 
        'xǁMeshTopologyStatsǁrecord_path_computation__mutmut_6': xǁMeshTopologyStatsǁrecord_path_computation__mutmut_6
    }
    
    def record_path_computation(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁrecord_path_computation__mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁrecord_path_computation__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_path_computation.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁrecord_path_computation__mutmut_orig)
    xǁMeshTopologyStatsǁrecord_path_computation__mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁrecord_path_computation'
    
    def xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_orig(self) -> None:
        """Record cache hit."""
        self.metrics.increment_counter("cache_hits")
    
    def xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_1(self) -> None:
        """Record cache hit."""
        self.metrics.increment_counter(None)
    
    def xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_2(self) -> None:
        """Record cache hit."""
        self.metrics.increment_counter("XXcache_hitsXX")
    
    def xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_3(self) -> None:
        """Record cache hit."""
        self.metrics.increment_counter("CACHE_HITS")
    
    xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_1': xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_1, 
        'xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_2': xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_2, 
        'xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_3': xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_3
    }
    
    def record_cache_hit(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_cache_hit.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_orig)
    xǁMeshTopologyStatsǁrecord_cache_hit__mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁrecord_cache_hit'
    
    def xǁMeshTopologyStatsǁrecord_failover__mutmut_orig(self) -> None:
        """Record failover event."""
        self.metrics.increment_counter("failover_events")
    
    def xǁMeshTopologyStatsǁrecord_failover__mutmut_1(self) -> None:
        """Record failover event."""
        self.metrics.increment_counter(None)
    
    def xǁMeshTopologyStatsǁrecord_failover__mutmut_2(self) -> None:
        """Record failover event."""
        self.metrics.increment_counter("XXfailover_eventsXX")
    
    def xǁMeshTopologyStatsǁrecord_failover__mutmut_3(self) -> None:
        """Record failover event."""
        self.metrics.increment_counter("FAILOVER_EVENTS")
    
    xǁMeshTopologyStatsǁrecord_failover__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁrecord_failover__mutmut_1': xǁMeshTopologyStatsǁrecord_failover__mutmut_1, 
        'xǁMeshTopologyStatsǁrecord_failover__mutmut_2': xǁMeshTopologyStatsǁrecord_failover__mutmut_2, 
        'xǁMeshTopologyStatsǁrecord_failover__mutmut_3': xǁMeshTopologyStatsǁrecord_failover__mutmut_3
    }
    
    def record_failover(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁrecord_failover__mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁrecord_failover__mutmut_mutants"), args, kwargs, self)
        return result 
    
    record_failover.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁrecord_failover__mutmut_orig)
    xǁMeshTopologyStatsǁrecord_failover__mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁrecord_failover'
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_orig(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_1(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = None
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_2(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = None
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_3(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) - stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_4(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get(None, 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_5(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', None) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_6(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get(0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_7(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', ) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_8(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['XXcountersXX'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_9(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['COUNTERS'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_10(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('XXcache_hitsXX', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_11(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('CACHE_HITS', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_12(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 1) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_13(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get(None, 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_14(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', None))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_15(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get(0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_16(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', ))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_17(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['XXcountersXX'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_18(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['COUNTERS'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_19(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('XXcache_missesXX', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_20(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('CACHE_MISSES', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_21(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 1))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_22(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests >= 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_23(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 1:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_24(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = None
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_25(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['XXcache_hit_rateXX'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_26(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['CACHE_HIT_RATE'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_27(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) * total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_28(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get(None, 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_29(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', None) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_30(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get(0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_31(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', ) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_32(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['XXcountersXX'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_33(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['COUNTERS'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_34(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('XXcache_hitsXX', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_35(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('CACHE_HITS', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_36(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 1) / total_requests
        else:
            stats['cache_hit_rate'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_37(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = None
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_38(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['XXcache_hit_rateXX'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_39(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['CACHE_HIT_RATE'] = 0.0
        
        return stats
    
    def xǁMeshTopologyStatsǁget_stats__mutmut_40(self) -> Dict[str, Any]:
        """Get topology statistics snapshot."""
        stats = self.metrics.get_stats_snapshot()
        
        # Add computed metrics
        total_requests = (stats['counters'].get('cache_hits', 0) + 
                         stats['counters'].get('cache_misses', 0))
        if total_requests > 0:
            stats['cache_hit_rate'] = stats['counters'].get('cache_hits', 0) / total_requests
        else:
            stats['cache_hit_rate'] = 1.0
        
        return stats
    
    xǁMeshTopologyStatsǁget_stats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshTopologyStatsǁget_stats__mutmut_1': xǁMeshTopologyStatsǁget_stats__mutmut_1, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_2': xǁMeshTopologyStatsǁget_stats__mutmut_2, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_3': xǁMeshTopologyStatsǁget_stats__mutmut_3, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_4': xǁMeshTopologyStatsǁget_stats__mutmut_4, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_5': xǁMeshTopologyStatsǁget_stats__mutmut_5, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_6': xǁMeshTopologyStatsǁget_stats__mutmut_6, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_7': xǁMeshTopologyStatsǁget_stats__mutmut_7, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_8': xǁMeshTopologyStatsǁget_stats__mutmut_8, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_9': xǁMeshTopologyStatsǁget_stats__mutmut_9, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_10': xǁMeshTopologyStatsǁget_stats__mutmut_10, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_11': xǁMeshTopologyStatsǁget_stats__mutmut_11, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_12': xǁMeshTopologyStatsǁget_stats__mutmut_12, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_13': xǁMeshTopologyStatsǁget_stats__mutmut_13, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_14': xǁMeshTopologyStatsǁget_stats__mutmut_14, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_15': xǁMeshTopologyStatsǁget_stats__mutmut_15, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_16': xǁMeshTopologyStatsǁget_stats__mutmut_16, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_17': xǁMeshTopologyStatsǁget_stats__mutmut_17, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_18': xǁMeshTopologyStatsǁget_stats__mutmut_18, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_19': xǁMeshTopologyStatsǁget_stats__mutmut_19, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_20': xǁMeshTopologyStatsǁget_stats__mutmut_20, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_21': xǁMeshTopologyStatsǁget_stats__mutmut_21, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_22': xǁMeshTopologyStatsǁget_stats__mutmut_22, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_23': xǁMeshTopologyStatsǁget_stats__mutmut_23, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_24': xǁMeshTopologyStatsǁget_stats__mutmut_24, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_25': xǁMeshTopologyStatsǁget_stats__mutmut_25, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_26': xǁMeshTopologyStatsǁget_stats__mutmut_26, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_27': xǁMeshTopologyStatsǁget_stats__mutmut_27, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_28': xǁMeshTopologyStatsǁget_stats__mutmut_28, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_29': xǁMeshTopologyStatsǁget_stats__mutmut_29, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_30': xǁMeshTopologyStatsǁget_stats__mutmut_30, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_31': xǁMeshTopologyStatsǁget_stats__mutmut_31, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_32': xǁMeshTopologyStatsǁget_stats__mutmut_32, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_33': xǁMeshTopologyStatsǁget_stats__mutmut_33, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_34': xǁMeshTopologyStatsǁget_stats__mutmut_34, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_35': xǁMeshTopologyStatsǁget_stats__mutmut_35, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_36': xǁMeshTopologyStatsǁget_stats__mutmut_36, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_37': xǁMeshTopologyStatsǁget_stats__mutmut_37, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_38': xǁMeshTopologyStatsǁget_stats__mutmut_38, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_39': xǁMeshTopologyStatsǁget_stats__mutmut_39, 
        'xǁMeshTopologyStatsǁget_stats__mutmut_40': xǁMeshTopologyStatsǁget_stats__mutmut_40
    }
    
    def get_stats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshTopologyStatsǁget_stats__mutmut_orig"), object.__getattribute__(self, "xǁMeshTopologyStatsǁget_stats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_stats.__signature__ = _mutmut_signature(xǁMeshTopologyStatsǁget_stats__mutmut_orig)
    xǁMeshTopologyStatsǁget_stats__mutmut_orig.__name__ = 'xǁMeshTopologyStatsǁget_stats'

# Global registry for component stats
_component_stats: Dict[str, Any] = {}
_registry_lock = threading.Lock()

def x_get_component_stats__mutmut_orig(component_id: str) -> Optional[ThreadSafeMetrics]:
    """Get component statistics from registry."""
    with _registry_lock:
        return _component_stats.get(component_id)

def x_get_component_stats__mutmut_1(component_id: str) -> Optional[ThreadSafeMetrics]:
    """Get component statistics from registry."""
    with _registry_lock:
        return _component_stats.get(None)

x_get_component_stats__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_component_stats__mutmut_1': x_get_component_stats__mutmut_1
}

def get_component_stats(*args, **kwargs):
    result = _mutmut_trampoline(x_get_component_stats__mutmut_orig, x_get_component_stats__mutmut_mutants, args, kwargs)
    return result 

get_component_stats.__signature__ = _mutmut_signature(x_get_component_stats__mutmut_orig)
x_get_component_stats__mutmut_orig.__name__ = 'x_get_component_stats'

def x_register_component_stats__mutmut_orig(component_id: str, stats: ThreadSafeMetrics) -> None:
    """Register component statistics in registry."""
    with _registry_lock:
        _component_stats[component_id] = stats

def x_register_component_stats__mutmut_1(component_id: str, stats: ThreadSafeMetrics) -> None:
    """Register component statistics in registry."""
    with _registry_lock:
        _component_stats[component_id] = None

x_register_component_stats__mutmut_mutants : ClassVar[MutantDict] = {
'x_register_component_stats__mutmut_1': x_register_component_stats__mutmut_1
}

def register_component_stats(*args, **kwargs):
    result = _mutmut_trampoline(x_register_component_stats__mutmut_orig, x_register_component_stats__mutmut_mutants, args, kwargs)
    return result 

register_component_stats.__signature__ = _mutmut_signature(x_register_component_stats__mutmut_orig)
x_register_component_stats__mutmut_orig.__name__ = 'x_register_component_stats'

def get_all_stats() -> Dict[str, Dict[str, Any]]:
    """Get all registered component statistics."""
    with _registry_lock:
        return {
            component_id: stats.get_stats_snapshot()
            for component_id, stats in _component_stats.items()
        }
