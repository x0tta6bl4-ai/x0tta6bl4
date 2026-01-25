"""
Ongoing Performance Optimization Framework

Provides framework for continuous performance optimization:
- Performance profiling
- Hot path identification
- Optimization suggestions
- Performance regression detection
"""

import logging
import time
import cProfile
import pstats
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import functools

logger = logging.getLogger(__name__)


@dataclass
class PerformanceProfile:
    """Performance profile data"""
    function_name: str
    total_time: float
    cumulative_time: float
    call_count: int
    average_time: float


@dataclass
class OptimizationSuggestion:
    """Performance optimization suggestion"""
    function_name: str
    current_time: float
    suggested_improvement: str
    estimated_gain: float  # percentage
    priority: str  # 'high', 'medium', 'low'


class PerformanceOptimizer:
    """
    Ongoing performance optimization framework.
    
    Features:
    - Performance profiling
    - Hot path identification
    - Optimization suggestions
    - Regression detection
    """
    
    def __init__(self):
        self.profiles: List[Dict[str, Any]] = []
        self.baseline_metrics: Dict[str, float] = {}
        self.optimization_history: List[Dict[str, Any]] = []
        
        logger.info("Performance Optimizer initialized")
    
    def profile_function(self, func: Callable) -> Callable:
        """
        Decorator to profile a function.
        
        Usage:
            @optimizer.profile_function
            def my_function():
                ...
        """
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                self._record_profile(func.__name__, elapsed)
        
        return wrapper
    
    def profile_async_function(self, func: Callable) -> Callable:
        """
        Decorator to profile an async function.
        
        Usage:
            @optimizer.profile_async_function
            async def my_async_function():
                ...
        """
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                elapsed = time.perf_counter() - start
                self._record_profile(func.__name__, elapsed)
        
        return wrapper
    
    def _record_profile(self, function_name: str, elapsed: float):
        """Record function execution time."""
        if function_name not in self.baseline_metrics:
            self.baseline_metrics[function_name] = elapsed
        
        self.profiles.append({
            "function_name": function_name,
            "elapsed": elapsed,
            "timestamp": datetime.now().isoformat()
        })
    
    def run_profiler(self, func: Callable, *args, **kwargs) -> Dict[str, Any]:
        """
        Run cProfile on a function.
        
        Args:
            func: Function to profile
            *args, **kwargs: Arguments to pass to function
            
        Returns:
            Profile statistics
        """
        profiler = cProfile.Profile()
        profiler.enable()
        
        try:
            result = func(*args, **kwargs)
        finally:
            profiler.disable()
        
        stats = pstats.Stats(profiler)
        stats.sort_stats('cumulative')
        
        # Extract top functions
        top_functions = []
        for func_name, (cc, nc, tt, ct, callers) in stats.stats.items():
            if ct > 0.001:  # Only significant functions
                top_functions.append({
                    "function": f"{func_name[0]}:{func_name[1]}:{func_name[2]}",
                    "total_time": tt,
                    "cumulative_time": ct,
                    "call_count": cc
                })
        
        return {
            "result": result,
            "top_functions": sorted(top_functions, key=lambda x: x["cumulative_time"], reverse=True)[:10]
        }
    
    def identify_hot_paths(self, limit: int = 10) -> List[PerformanceProfile]:
        """
        Identify hot paths (most time-consuming functions).
        
        Args:
            limit: Maximum number of hot paths to return
            
        Returns:
            List of performance profiles
        """
        # Aggregate profiles by function name
        function_stats: Dict[str, Dict[str, Any]] = {}
        
        for profile in self.profiles:
            func_name = profile["function_name"]
            elapsed = profile["elapsed"]
            
            if func_name not in function_stats:
                function_stats[func_name] = {
                    "total_time": 0.0,
                    "call_count": 0,
                    "times": []
                }
            
            function_stats[func_name]["total_time"] += elapsed
            function_stats[func_name]["call_count"] += 1
            function_stats[func_name]["times"].append(elapsed)
        
        # Calculate averages and create profiles
        hot_paths = []
        for func_name, stats in function_stats.items():
            avg_time = stats["total_time"] / stats["call_count"]
            hot_paths.append(PerformanceProfile(
                function_name=func_name,
                total_time=stats["total_time"],
                cumulative_time=stats["total_time"],
                call_count=stats["call_count"],
                average_time=avg_time
            ))
        
        # Sort by total time
        hot_paths.sort(key=lambda x: x.total_time, reverse=True)
        
        return hot_paths[:limit]
    
    def generate_optimization_suggestions(self) -> List[OptimizationSuggestion]:
        """
        Generate optimization suggestions based on profiling data.
        
        Returns:
            List of optimization suggestions
        """
        hot_paths = self.identify_hot_paths(limit=20)
        suggestions = []
        
        for path in hot_paths:
            # Check if function is slow
            if path.average_time > 0.1:  # > 100ms
                suggestion = OptimizationSuggestion(
                    function_name=path.function_name,
                    current_time=path.average_time,
                    suggested_improvement="Consider async/await or caching",
                    estimated_gain=30.0,  # 30% improvement estimate
                    priority="high"
                )
                suggestions.append(suggestion)
            
            # Check if function is called frequently
            elif path.call_count > 1000 and path.average_time > 0.01:  # > 10ms, called 1000+ times
                suggestion = OptimizationSuggestion(
                    function_name=path.function_name,
                    current_time=path.average_time,
                    suggested_improvement="Consider memoization or batch processing",
                    estimated_gain=20.0,
                    priority="medium"
                )
                suggestions.append(suggestion)
        
        return suggestions
    
    def detect_regression(self, function_name: str, current_time: float) -> bool:
        """
        Detect performance regression.
        
        Args:
            function_name: Name of function
            current_time: Current execution time
            
        Returns:
            True if regression detected
        """
        if function_name not in self.baseline_metrics:
            self.baseline_metrics[function_name] = current_time
            return False
        
        baseline = self.baseline_metrics[function_name]
        regression_threshold = baseline * 1.2  # 20% slower
        
        if current_time > regression_threshold:
            logger.warning(
                f"⚠️ Performance regression detected in {function_name}: "
                f"{current_time:.3f}s (baseline: {baseline:.3f}s)"
            )
            return True
        
        return False
    
    def get_performance_report(self) -> Dict[str, Any]:
        """
        Get performance optimization report.
        
        Returns:
            Dictionary with performance report
        """
        hot_paths = self.identify_hot_paths(limit=10)
        suggestions = self.generate_optimization_suggestions()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "hot_paths": [
                {
                    "function": p.function_name,
                    "total_time": p.total_time,
                    "average_time": p.average_time,
                    "call_count": p.call_count
                }
                for p in hot_paths
            ],
            "optimization_suggestions": [
                {
                    "function": s.function_name,
                    "current_time": s.current_time,
                    "suggestion": s.suggested_improvement,
                    "estimated_gain": s.estimated_gain,
                    "priority": s.priority
                }
                for s in suggestions
            ],
            "baseline_metrics": self.baseline_metrics
        }


# Global instance
_performance_optimizer: Optional[PerformanceOptimizer] = None


def get_performance_optimizer() -> PerformanceOptimizer:
    """Get global PerformanceOptimizer instance."""
    global _performance_optimizer
    if _performance_optimizer is None:
        _performance_optimizer = PerformanceOptimizer()
    return _performance_optimizer

