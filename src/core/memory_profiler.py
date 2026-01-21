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

    def __init__(self, enable_tracemalloc: bool = True):
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

    def get_current_stats(self) -> MemoryStats:
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

    def log_memory_usage(self, prefix: str = "Memory usage"):
        """Log current memory usage."""
        stats = self.get_current_stats()
        logger.info(
            f"{prefix}: RSS={stats.rss_mb:.1f}MB, "
            f"VMS={stats.vms_mb:.1f}MB, "
            f"CPU={stats.cpu_percent:.1f}%, "
            f"Tracemalloc={stats.tracemalloc_mb:.1f}MB "
            f"(peak: {stats.peak_tracemalloc_mb:.1f}MB)"
        )

    def start_monitoring(self, interval_seconds: float = 300):
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

    def stop_monitoring(self):
        """Stop background memory monitoring."""
        if not self._monitoring:
            return

        self._monitoring = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=1.0)
        logger.info("Stopped memory monitoring")

    def _monitor_loop(self, interval: float):
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

    def get_stats_history(self) -> list[MemoryStats]:
        """Get historical memory statistics."""
        return self._stats_history.copy()

    def get_memory_report(self) -> Dict[str, Any]:
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

# Global profiler instance
_memory_profiler = MemoryProfiler()

def get_memory_profiler() -> MemoryProfiler:
    """Get global memory profiler instance."""
    return _memory_profiler

def log_memory_usage(prefix: str = "Memory usage"):
    """Convenience function to log current memory usage."""
    _memory_profiler.log_memory_usage(prefix)