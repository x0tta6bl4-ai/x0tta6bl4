"""
Memory profiling utilities for x0tta6bl4
"""
import tracemalloc
import psutil
import logging
import threading
import time
from typing import Dict, Any, Optional
from dataclasses import dataclass

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
class MemoryStats:
    """Memory usage statistics."""
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    tracemalloc_mb: float  # Tracemalloc current memory
    peak_tracemalloc_mb: float  # Tracemalloc peak memory
    cpu_percent: float  # CPU usage percentage
    timestamp: float

class MemoryProfiler:
    """
    Memory and performance profiler for x0tta6bl4 components.

    Tracks memory usage, CPU usage, and provides profiling capabilities.
    """

    def xǁMemoryProfilerǁ__init____mutmut_orig(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_1(self, enable_tracemalloc: bool = False):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_2(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = None
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_3(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = None
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_4(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = None
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_5(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = True
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_6(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = ""
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_7(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = None

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("Memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_8(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info(None)

    def xǁMemoryProfilerǁ__init____mutmut_9(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("XXMemory profiler initialized with tracemallocXX")

    def xǁMemoryProfilerǁ__init____mutmut_10(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("memory profiler initialized with tracemalloc")

    def xǁMemoryProfilerǁ__init____mutmut_11(self, enable_tracemalloc: bool = True):
        """
        Initialize memory profiler.

        Args:
            enable_tracemalloc: Whether to enable detailed memory tracing
        """
        self.process = psutil.Process()
        self.enable_tracemalloc = enable_tracemalloc
        self._monitoring = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._stats_history: list[MemoryStats] = []

        if enable_tracemalloc:
            tracemalloc.start()
            logger.info("MEMORY PROFILER INITIALIZED WITH TRACEMALLOC")
    
    xǁMemoryProfilerǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁ__init____mutmut_1': xǁMemoryProfilerǁ__init____mutmut_1, 
        'xǁMemoryProfilerǁ__init____mutmut_2': xǁMemoryProfilerǁ__init____mutmut_2, 
        'xǁMemoryProfilerǁ__init____mutmut_3': xǁMemoryProfilerǁ__init____mutmut_3, 
        'xǁMemoryProfilerǁ__init____mutmut_4': xǁMemoryProfilerǁ__init____mutmut_4, 
        'xǁMemoryProfilerǁ__init____mutmut_5': xǁMemoryProfilerǁ__init____mutmut_5, 
        'xǁMemoryProfilerǁ__init____mutmut_6': xǁMemoryProfilerǁ__init____mutmut_6, 
        'xǁMemoryProfilerǁ__init____mutmut_7': xǁMemoryProfilerǁ__init____mutmut_7, 
        'xǁMemoryProfilerǁ__init____mutmut_8': xǁMemoryProfilerǁ__init____mutmut_8, 
        'xǁMemoryProfilerǁ__init____mutmut_9': xǁMemoryProfilerǁ__init____mutmut_9, 
        'xǁMemoryProfilerǁ__init____mutmut_10': xǁMemoryProfilerǁ__init____mutmut_10, 
        'xǁMemoryProfilerǁ__init____mutmut_11': xǁMemoryProfilerǁ__init____mutmut_11
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMemoryProfilerǁ__init____mutmut_orig)
    xǁMemoryProfilerǁ__init____mutmut_orig.__name__ = 'xǁMemoryProfilerǁ__init__'

    def xǁMemoryProfilerǁget_current_stats__mutmut_orig(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_1(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = None
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_2(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = None

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_3(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=None)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_4(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=1.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_5(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = None
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_6(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 1
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_7(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = None

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_8(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 1

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_9(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = None
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_10(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = None  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_11(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 * 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_12(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current * 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_13(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1025 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_14(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1025  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_15(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = None  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_16(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 * 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_17(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak * 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_18(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1025 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_19(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1025  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_20(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(None)

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_21(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=None,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_22(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=None,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_23(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=None,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_24(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=None,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_25(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=None,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_26(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=None
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_27(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_28(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_29(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_30(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_31(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_32(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            )

    def xǁMemoryProfilerǁget_current_stats__mutmut_33(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 * 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_34(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss * 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_35(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1025 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_36(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1025,
            vms_mb=memory_info.vms / 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_37(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 * 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_38(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms * 1024 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_39(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1025 / 1024,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )

    def xǁMemoryProfilerǁget_current_stats__mutmut_40(self) -> MemoryStats:
        """Get current memory and CPU statistics."""
        memory_info = self.process.memory_info()
        cpu_percent = self.process.cpu_percent(interval=0.1)

        tracemalloc_current = 0
        tracemalloc_peak = 0

        if self.enable_tracemalloc:
            try:
                current, peak = tracemalloc.get_traced_memory()
                tracemalloc_current = current / 1024 / 1024  # MB
                tracemalloc_peak = peak / 1024 / 1024  # MB
            except Exception as e:
                logger.warning(f"Failed to get tracemalloc stats: {e}")

        return MemoryStats(
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1025,
            tracemalloc_mb=tracemalloc_current,
            peak_tracemalloc_mb=tracemalloc_peak,
            cpu_percent=cpu_percent,
            timestamp=time.time()
        )
    
    xǁMemoryProfilerǁget_current_stats__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁget_current_stats__mutmut_1': xǁMemoryProfilerǁget_current_stats__mutmut_1, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_2': xǁMemoryProfilerǁget_current_stats__mutmut_2, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_3': xǁMemoryProfilerǁget_current_stats__mutmut_3, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_4': xǁMemoryProfilerǁget_current_stats__mutmut_4, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_5': xǁMemoryProfilerǁget_current_stats__mutmut_5, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_6': xǁMemoryProfilerǁget_current_stats__mutmut_6, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_7': xǁMemoryProfilerǁget_current_stats__mutmut_7, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_8': xǁMemoryProfilerǁget_current_stats__mutmut_8, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_9': xǁMemoryProfilerǁget_current_stats__mutmut_9, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_10': xǁMemoryProfilerǁget_current_stats__mutmut_10, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_11': xǁMemoryProfilerǁget_current_stats__mutmut_11, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_12': xǁMemoryProfilerǁget_current_stats__mutmut_12, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_13': xǁMemoryProfilerǁget_current_stats__mutmut_13, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_14': xǁMemoryProfilerǁget_current_stats__mutmut_14, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_15': xǁMemoryProfilerǁget_current_stats__mutmut_15, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_16': xǁMemoryProfilerǁget_current_stats__mutmut_16, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_17': xǁMemoryProfilerǁget_current_stats__mutmut_17, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_18': xǁMemoryProfilerǁget_current_stats__mutmut_18, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_19': xǁMemoryProfilerǁget_current_stats__mutmut_19, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_20': xǁMemoryProfilerǁget_current_stats__mutmut_20, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_21': xǁMemoryProfilerǁget_current_stats__mutmut_21, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_22': xǁMemoryProfilerǁget_current_stats__mutmut_22, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_23': xǁMemoryProfilerǁget_current_stats__mutmut_23, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_24': xǁMemoryProfilerǁget_current_stats__mutmut_24, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_25': xǁMemoryProfilerǁget_current_stats__mutmut_25, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_26': xǁMemoryProfilerǁget_current_stats__mutmut_26, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_27': xǁMemoryProfilerǁget_current_stats__mutmut_27, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_28': xǁMemoryProfilerǁget_current_stats__mutmut_28, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_29': xǁMemoryProfilerǁget_current_stats__mutmut_29, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_30': xǁMemoryProfilerǁget_current_stats__mutmut_30, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_31': xǁMemoryProfilerǁget_current_stats__mutmut_31, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_32': xǁMemoryProfilerǁget_current_stats__mutmut_32, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_33': xǁMemoryProfilerǁget_current_stats__mutmut_33, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_34': xǁMemoryProfilerǁget_current_stats__mutmut_34, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_35': xǁMemoryProfilerǁget_current_stats__mutmut_35, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_36': xǁMemoryProfilerǁget_current_stats__mutmut_36, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_37': xǁMemoryProfilerǁget_current_stats__mutmut_37, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_38': xǁMemoryProfilerǁget_current_stats__mutmut_38, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_39': xǁMemoryProfilerǁget_current_stats__mutmut_39, 
        'xǁMemoryProfilerǁget_current_stats__mutmut_40': xǁMemoryProfilerǁget_current_stats__mutmut_40
    }
    
    def get_current_stats(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁget_current_stats__mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁget_current_stats__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_current_stats.__signature__ = _mutmut_signature(xǁMemoryProfilerǁget_current_stats__mutmut_orig)
    xǁMemoryProfilerǁget_current_stats__mutmut_orig.__name__ = 'xǁMemoryProfilerǁget_current_stats'

    def xǁMemoryProfilerǁlog_memory_usage__mutmut_orig(self, prefix: str = "Memory usage"):
        """Log current memory usage."""
        stats = self.get_current_stats()
        logger.info(
            f"{prefix}: RSS={stats.rss_mb:.1f}MB, "
            f"VMS={stats.vms_mb:.1f}MB, "
            f"CPU={stats.cpu_percent:.1f}%, "
            f"Tracemalloc={stats.tracemalloc_mb:.1f}MB "
            f"(peak: {stats.peak_tracemalloc_mb:.1f}MB)"
        )

    def xǁMemoryProfilerǁlog_memory_usage__mutmut_1(self, prefix: str = "XXMemory usageXX"):
        """Log current memory usage."""
        stats = self.get_current_stats()
        logger.info(
            f"{prefix}: RSS={stats.rss_mb:.1f}MB, "
            f"VMS={stats.vms_mb:.1f}MB, "
            f"CPU={stats.cpu_percent:.1f}%, "
            f"Tracemalloc={stats.tracemalloc_mb:.1f}MB "
            f"(peak: {stats.peak_tracemalloc_mb:.1f}MB)"
        )

    def xǁMemoryProfilerǁlog_memory_usage__mutmut_2(self, prefix: str = "memory usage"):
        """Log current memory usage."""
        stats = self.get_current_stats()
        logger.info(
            f"{prefix}: RSS={stats.rss_mb:.1f}MB, "
            f"VMS={stats.vms_mb:.1f}MB, "
            f"CPU={stats.cpu_percent:.1f}%, "
            f"Tracemalloc={stats.tracemalloc_mb:.1f}MB "
            f"(peak: {stats.peak_tracemalloc_mb:.1f}MB)"
        )

    def xǁMemoryProfilerǁlog_memory_usage__mutmut_3(self, prefix: str = "MEMORY USAGE"):
        """Log current memory usage."""
        stats = self.get_current_stats()
        logger.info(
            f"{prefix}: RSS={stats.rss_mb:.1f}MB, "
            f"VMS={stats.vms_mb:.1f}MB, "
            f"CPU={stats.cpu_percent:.1f}%, "
            f"Tracemalloc={stats.tracemalloc_mb:.1f}MB "
            f"(peak: {stats.peak_tracemalloc_mb:.1f}MB)"
        )

    def xǁMemoryProfilerǁlog_memory_usage__mutmut_4(self, prefix: str = "Memory usage"):
        """Log current memory usage."""
        stats = None
        logger.info(
            f"{prefix}: RSS={stats.rss_mb:.1f}MB, "
            f"VMS={stats.vms_mb:.1f}MB, "
            f"CPU={stats.cpu_percent:.1f}%, "
            f"Tracemalloc={stats.tracemalloc_mb:.1f}MB "
            f"(peak: {stats.peak_tracemalloc_mb:.1f}MB)"
        )

    def xǁMemoryProfilerǁlog_memory_usage__mutmut_5(self, prefix: str = "Memory usage"):
        """Log current memory usage."""
        stats = self.get_current_stats()
        logger.info(
            None
        )
    
    xǁMemoryProfilerǁlog_memory_usage__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁlog_memory_usage__mutmut_1': xǁMemoryProfilerǁlog_memory_usage__mutmut_1, 
        'xǁMemoryProfilerǁlog_memory_usage__mutmut_2': xǁMemoryProfilerǁlog_memory_usage__mutmut_2, 
        'xǁMemoryProfilerǁlog_memory_usage__mutmut_3': xǁMemoryProfilerǁlog_memory_usage__mutmut_3, 
        'xǁMemoryProfilerǁlog_memory_usage__mutmut_4': xǁMemoryProfilerǁlog_memory_usage__mutmut_4, 
        'xǁMemoryProfilerǁlog_memory_usage__mutmut_5': xǁMemoryProfilerǁlog_memory_usage__mutmut_5
    }
    
    def log_memory_usage(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁlog_memory_usage__mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁlog_memory_usage__mutmut_mutants"), args, kwargs, self)
        return result 
    
    log_memory_usage.__signature__ = _mutmut_signature(xǁMemoryProfilerǁlog_memory_usage__mutmut_orig)
    xǁMemoryProfilerǁlog_memory_usage__mutmut_orig.__name__ = 'xǁMemoryProfilerǁlog_memory_usage'

    def xǁMemoryProfilerǁstart_monitoring__mutmut_orig(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_1(self, interval_seconds: float = 301):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_2(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning(None)
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_3(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("XXMemory monitoring already runningXX")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_4(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_5(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("MEMORY MONITORING ALREADY RUNNING")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_6(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = None
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_7(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = False
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_8(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = None
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_9(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=None,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_10(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=None,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_11(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=None
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_12(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_13(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_14(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_15(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=False
        )
        self._monitor_thread.start()
        logger.info(f"Started memory monitoring (interval: {interval_seconds}s)")

    def xǁMemoryProfilerǁstart_monitoring__mutmut_16(self, interval_seconds: float = 300):
        """
        Start background monitoring of memory usage.

        Args:
            interval_seconds: How often to log memory stats
        """
        if self._monitoring:
            logger.warning("Memory monitoring already running")
            return

        self._monitoring = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True
        )
        self._monitor_thread.start()
        logger.info(None)
    
    xǁMemoryProfilerǁstart_monitoring__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁstart_monitoring__mutmut_1': xǁMemoryProfilerǁstart_monitoring__mutmut_1, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_2': xǁMemoryProfilerǁstart_monitoring__mutmut_2, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_3': xǁMemoryProfilerǁstart_monitoring__mutmut_3, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_4': xǁMemoryProfilerǁstart_monitoring__mutmut_4, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_5': xǁMemoryProfilerǁstart_monitoring__mutmut_5, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_6': xǁMemoryProfilerǁstart_monitoring__mutmut_6, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_7': xǁMemoryProfilerǁstart_monitoring__mutmut_7, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_8': xǁMemoryProfilerǁstart_monitoring__mutmut_8, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_9': xǁMemoryProfilerǁstart_monitoring__mutmut_9, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_10': xǁMemoryProfilerǁstart_monitoring__mutmut_10, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_11': xǁMemoryProfilerǁstart_monitoring__mutmut_11, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_12': xǁMemoryProfilerǁstart_monitoring__mutmut_12, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_13': xǁMemoryProfilerǁstart_monitoring__mutmut_13, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_14': xǁMemoryProfilerǁstart_monitoring__mutmut_14, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_15': xǁMemoryProfilerǁstart_monitoring__mutmut_15, 
        'xǁMemoryProfilerǁstart_monitoring__mutmut_16': xǁMemoryProfilerǁstart_monitoring__mutmut_16
    }
    
    def start_monitoring(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁstart_monitoring__mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁstart_monitoring__mutmut_mutants"), args, kwargs, self)
        return result 
    
    start_monitoring.__signature__ = _mutmut_signature(xǁMemoryProfilerǁstart_monitoring__mutmut_orig)
    xǁMemoryProfilerǁstart_monitoring__mutmut_orig.__name__ = 'xǁMemoryProfilerǁstart_monitoring'

    def xǁMemoryProfilerǁstop_monitoring__mutmut_orig(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_1(self):
        """Stop background memory monitoring."""
        if self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_2(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = None
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_3(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = True
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_4(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=None)
        logger.info("Stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_5(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        logger.info("Stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_6(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info(None)

    def xǁMemoryProfilerǁstop_monitoring__mutmut_7(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("XXStopped memory monitoringXX")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_8(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("stopped memory monitoring")

    def xǁMemoryProfilerǁstop_monitoring__mutmut_9(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("STOPPED MEMORY MONITORING")
    
    xǁMemoryProfilerǁstop_monitoring__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁstop_monitoring__mutmut_1': xǁMemoryProfilerǁstop_monitoring__mutmut_1, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_2': xǁMemoryProfilerǁstop_monitoring__mutmut_2, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_3': xǁMemoryProfilerǁstop_monitoring__mutmut_3, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_4': xǁMemoryProfilerǁstop_monitoring__mutmut_4, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_5': xǁMemoryProfilerǁstop_monitoring__mutmut_5, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_6': xǁMemoryProfilerǁstop_monitoring__mutmut_6, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_7': xǁMemoryProfilerǁstop_monitoring__mutmut_7, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_8': xǁMemoryProfilerǁstop_monitoring__mutmut_8, 
        'xǁMemoryProfilerǁstop_monitoring__mutmut_9': xǁMemoryProfilerǁstop_monitoring__mutmut_9
    }
    
    def stop_monitoring(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁstop_monitoring__mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁstop_monitoring__mutmut_mutants"), args, kwargs, self)
        return result 
    
    stop_monitoring.__signature__ = _mutmut_signature(xǁMemoryProfilerǁstop_monitoring__mutmut_orig)
    xǁMemoryProfilerǁstop_monitoring__mutmut_orig.__name__ = 'xǁMemoryProfilerǁstop_monitoring'

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_orig(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_1(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = None
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_2(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(None)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_3(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) >= 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_4(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1001:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_5(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = None

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_6(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[+1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_7(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1001:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_8(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb >= 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_9(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 801:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_10(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        None
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_11(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(None)

            time.sleep(interval)

    def xǁMemoryProfilerǁ_monitor_loop__mutmut_12(self, interval: float):
        """Background monitoring loop."""
        while self._monitoring:
            try:
                stats = self.get_current_stats()
                self._stats_history.append(stats)

                # Keep only last 1000 entries to prevent memory bloat
                if len(self._stats_history) > 1000:
                    self._stats_history = self._stats_history[-1000:]

                # Log if memory usage is high
                if stats.rss_mb > 800:  # 800MB threshold
                    logger.warning(
                        f"High memory usage detected: {stats.rss_mb:.1f}MB RSS"
                    )

            except Exception as e:
                logger.error(f"Error in memory monitoring: {e}")

            time.sleep(None)
    
    xǁMemoryProfilerǁ_monitor_loop__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁ_monitor_loop__mutmut_1': xǁMemoryProfilerǁ_monitor_loop__mutmut_1, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_2': xǁMemoryProfilerǁ_monitor_loop__mutmut_2, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_3': xǁMemoryProfilerǁ_monitor_loop__mutmut_3, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_4': xǁMemoryProfilerǁ_monitor_loop__mutmut_4, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_5': xǁMemoryProfilerǁ_monitor_loop__mutmut_5, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_6': xǁMemoryProfilerǁ_monitor_loop__mutmut_6, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_7': xǁMemoryProfilerǁ_monitor_loop__mutmut_7, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_8': xǁMemoryProfilerǁ_monitor_loop__mutmut_8, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_9': xǁMemoryProfilerǁ_monitor_loop__mutmut_9, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_10': xǁMemoryProfilerǁ_monitor_loop__mutmut_10, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_11': xǁMemoryProfilerǁ_monitor_loop__mutmut_11, 
        'xǁMemoryProfilerǁ_monitor_loop__mutmut_12': xǁMemoryProfilerǁ_monitor_loop__mutmut_12
    }
    
    def _monitor_loop(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁ_monitor_loop__mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁ_monitor_loop__mutmut_mutants"), args, kwargs, self)
        return result 
    
    _monitor_loop.__signature__ = _mutmut_signature(xǁMemoryProfilerǁ_monitor_loop__mutmut_orig)
    xǁMemoryProfilerǁ_monitor_loop__mutmut_orig.__name__ = 'xǁMemoryProfilerǁ_monitor_loop'

    def get_stats_history(self) -> list[MemoryStats]:
        """Get historical memory statistics."""
        return self._stats_history.copy()

    def xǁMemoryProfilerǁget_memory_report__mutmut_orig(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_1(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_2(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"XXerrorXX": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_3(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"ERROR": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_4(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "XXTracemalloc not enabledXX"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_5(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_6(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "TRACEMALLOC NOT ENABLED"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_7(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = None
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_8(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = None

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_9(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics(None)

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_10(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('XXlinenoXX')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_11(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('LINENO')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_12(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = None

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_13(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "XXcurrent_statsXX": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_14(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "CURRENT_STATS": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_15(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "XXtop_allocationsXX": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_16(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "TOP_ALLOCATIONS": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_17(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "XXsize_mbXX": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_18(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "SIZE_MB": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_19(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 * 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_20(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size * 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_21(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1025 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_22(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1025,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_23(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "XXcountXX": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_24(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "COUNT": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_25(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "XXfileXX": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_26(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "FILE": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_27(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[1].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_28(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "XXunknownXX",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_29(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "UNKNOWN",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_30(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "XXlineXX": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_31(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "LINE": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_32(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[1].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_33(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 1,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_34(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:11]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_35(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "XXtotal_trackedXX": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_36(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "TOTAL_TRACKED": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_37(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(None)
            return {"error": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_38(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"XXerrorXX": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_39(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"ERROR": str(e)}

    def xǁMemoryProfilerǁget_memory_report__mutmut_40(self) -> Dict[str, Any]:
        """Generate comprehensive memory report."""
        if not self.enable_tracemalloc:
            return {"error": "Tracemalloc not enabled"}

        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')

            report = {
                "current_stats": self.get_current_stats(),
                "top_allocations": [
                    {
                        "size_mb": stat.size / 1024 / 1024,
                        "count": stat.count,
                        "file": stat.traceback[0].filename if stat.traceback else "unknown",
                        "line": stat.traceback[0].lineno if stat.traceback else 0,
                    }
                    for stat in top_stats[:10]  # Top 10 allocations
                ],
                "total_tracked": len(top_stats),
            }

            return report

        except Exception as e:
            logger.error(f"Failed to generate memory report: {e}")
            return {"error": str(None)}
    
    xǁMemoryProfilerǁget_memory_report__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMemoryProfilerǁget_memory_report__mutmut_1': xǁMemoryProfilerǁget_memory_report__mutmut_1, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_2': xǁMemoryProfilerǁget_memory_report__mutmut_2, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_3': xǁMemoryProfilerǁget_memory_report__mutmut_3, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_4': xǁMemoryProfilerǁget_memory_report__mutmut_4, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_5': xǁMemoryProfilerǁget_memory_report__mutmut_5, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_6': xǁMemoryProfilerǁget_memory_report__mutmut_6, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_7': xǁMemoryProfilerǁget_memory_report__mutmut_7, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_8': xǁMemoryProfilerǁget_memory_report__mutmut_8, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_9': xǁMemoryProfilerǁget_memory_report__mutmut_9, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_10': xǁMemoryProfilerǁget_memory_report__mutmut_10, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_11': xǁMemoryProfilerǁget_memory_report__mutmut_11, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_12': xǁMemoryProfilerǁget_memory_report__mutmut_12, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_13': xǁMemoryProfilerǁget_memory_report__mutmut_13, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_14': xǁMemoryProfilerǁget_memory_report__mutmut_14, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_15': xǁMemoryProfilerǁget_memory_report__mutmut_15, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_16': xǁMemoryProfilerǁget_memory_report__mutmut_16, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_17': xǁMemoryProfilerǁget_memory_report__mutmut_17, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_18': xǁMemoryProfilerǁget_memory_report__mutmut_18, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_19': xǁMemoryProfilerǁget_memory_report__mutmut_19, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_20': xǁMemoryProfilerǁget_memory_report__mutmut_20, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_21': xǁMemoryProfilerǁget_memory_report__mutmut_21, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_22': xǁMemoryProfilerǁget_memory_report__mutmut_22, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_23': xǁMemoryProfilerǁget_memory_report__mutmut_23, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_24': xǁMemoryProfilerǁget_memory_report__mutmut_24, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_25': xǁMemoryProfilerǁget_memory_report__mutmut_25, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_26': xǁMemoryProfilerǁget_memory_report__mutmut_26, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_27': xǁMemoryProfilerǁget_memory_report__mutmut_27, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_28': xǁMemoryProfilerǁget_memory_report__mutmut_28, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_29': xǁMemoryProfilerǁget_memory_report__mutmut_29, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_30': xǁMemoryProfilerǁget_memory_report__mutmut_30, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_31': xǁMemoryProfilerǁget_memory_report__mutmut_31, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_32': xǁMemoryProfilerǁget_memory_report__mutmut_32, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_33': xǁMemoryProfilerǁget_memory_report__mutmut_33, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_34': xǁMemoryProfilerǁget_memory_report__mutmut_34, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_35': xǁMemoryProfilerǁget_memory_report__mutmut_35, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_36': xǁMemoryProfilerǁget_memory_report__mutmut_36, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_37': xǁMemoryProfilerǁget_memory_report__mutmut_37, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_38': xǁMemoryProfilerǁget_memory_report__mutmut_38, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_39': xǁMemoryProfilerǁget_memory_report__mutmut_39, 
        'xǁMemoryProfilerǁget_memory_report__mutmut_40': xǁMemoryProfilerǁget_memory_report__mutmut_40
    }
    
    def get_memory_report(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMemoryProfilerǁget_memory_report__mutmut_orig"), object.__getattribute__(self, "xǁMemoryProfilerǁget_memory_report__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_memory_report.__signature__ = _mutmut_signature(xǁMemoryProfilerǁget_memory_report__mutmut_orig)
    xǁMemoryProfilerǁget_memory_report__mutmut_orig.__name__ = 'xǁMemoryProfilerǁget_memory_report'

# Global profiler instance
_memory_profiler = MemoryProfiler()

def get_memory_profiler() -> MemoryProfiler:
    """Get global memory profiler instance."""
    return _memory_profiler

def x_log_memory_usage__mutmut_orig(prefix: str = "Memory usage"):
    """Convenience function to log current memory usage."""
    _memory_profiler.log_memory_usage(prefix)

def x_log_memory_usage__mutmut_1(prefix: str = "XXMemory usageXX"):
    """Convenience function to log current memory usage."""
    _memory_profiler.log_memory_usage(prefix)

def x_log_memory_usage__mutmut_2(prefix: str = "memory usage"):
    """Convenience function to log current memory usage."""
    _memory_profiler.log_memory_usage(prefix)

def x_log_memory_usage__mutmut_3(prefix: str = "MEMORY USAGE"):
    """Convenience function to log current memory usage."""
    _memory_profiler.log_memory_usage(prefix)

def x_log_memory_usage__mutmut_4(prefix: str = "Memory usage"):
    """Convenience function to log current memory usage."""
    _memory_profiler.log_memory_usage(None)

x_log_memory_usage__mutmut_mutants : ClassVar[MutantDict] = {
'x_log_memory_usage__mutmut_1': x_log_memory_usage__mutmut_1, 
    'x_log_memory_usage__mutmut_2': x_log_memory_usage__mutmut_2, 
    'x_log_memory_usage__mutmut_3': x_log_memory_usage__mutmut_3, 
    'x_log_memory_usage__mutmut_4': x_log_memory_usage__mutmut_4
}

def log_memory_usage(*args, **kwargs):
    result = _mutmut_trampoline(x_log_memory_usage__mutmut_orig, x_log_memory_usage__mutmut_mutants, args, kwargs)
    return result 

log_memory_usage.__signature__ = _mutmut_signature(x_log_memory_usage__mutmut_orig)
x_log_memory_usage__mutmut_orig.__name__ = 'x_log_memory_usage'