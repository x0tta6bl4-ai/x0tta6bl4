"""
Status collector for /status endpoint
Собирает реальные данные о состоянии системы для API
"""

import psutil
import time
from typing import Dict, Any, Optional
from datetime import datetime
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


class SystemMetricsCollector:
    """Собирает метрики системы (CPU, память, диск, сеть)"""
    
    def xǁSystemMetricsCollectorǁ__init____mutmut_orig(self):
        self.start_time = time.time()
        self._last_net_io = psutil.net_io_counters()
        self._last_net_io_time = time.time()
    
    def xǁSystemMetricsCollectorǁ__init____mutmut_1(self):
        self.start_time = None
        self._last_net_io = psutil.net_io_counters()
        self._last_net_io_time = time.time()
    
    def xǁSystemMetricsCollectorǁ__init____mutmut_2(self):
        self.start_time = time.time()
        self._last_net_io = None
        self._last_net_io_time = time.time()
    
    def xǁSystemMetricsCollectorǁ__init____mutmut_3(self):
        self.start_time = time.time()
        self._last_net_io = psutil.net_io_counters()
        self._last_net_io_time = None
    
    xǁSystemMetricsCollectorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁ__init____mutmut_1': xǁSystemMetricsCollectorǁ__init____mutmut_1, 
        'xǁSystemMetricsCollectorǁ__init____mutmut_2': xǁSystemMetricsCollectorǁ__init____mutmut_2, 
        'xǁSystemMetricsCollectorǁ__init____mutmut_3': xǁSystemMetricsCollectorǁ__init____mutmut_3
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁ__init____mutmut_orig)
    xǁSystemMetricsCollectorǁ__init____mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁ__init__'
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_orig(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_1(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = None
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_2(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_3(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_4(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = None
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_5(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "XXpercentXX": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_6(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "PERCENT": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_7(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(None, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_8(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, None),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_9(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_10(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, ),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_11(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 3),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_12(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "XXcoresXX": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_13(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "CORES": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_14(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "XXper_cpuXX": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_15(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "PER_CPU": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_16(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(None, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_17(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, None) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_18(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_19(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, ) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_20(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 3) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_21(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=None, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_22(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=None)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_23(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_24(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, )]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_25(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=1.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_26(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=False)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_27(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(None)
            return {"percent": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_28(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"XXpercentXX": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_29(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"PERCENT": 0, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_30(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 1, "cores": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_31(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "XXcoresXX": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_32(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "CORES": 0, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_33(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 1, "per_cpu": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_34(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "XXper_cpuXX": []}
    
    def xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_35(self) -> Dict[str, Any]:
        """CPU метрики"""
        try:
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            return {
                "percent": round(cpu_percent, 2),
                "cores": cpu_count,
                "per_cpu": [round(x, 2) for x in psutil.cpu_percent(interval=0.1, percpu=True)]
            }
        except Exception as e:
            logger.warning(f"Failed to get CPU metrics: {e}")
            return {"percent": 0, "cores": 0, "PER_CPU": []}
    
    xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_1': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_1, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_2': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_2, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_3': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_3, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_4': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_4, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_5': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_5, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_6': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_6, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_7': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_7, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_8': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_8, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_9': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_9, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_10': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_10, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_11': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_11, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_12': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_12, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_13': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_13, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_14': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_14, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_15': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_15, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_16': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_16, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_17': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_17, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_18': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_18, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_19': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_19, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_20': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_20, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_21': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_21, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_22': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_22, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_23': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_23, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_24': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_24, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_25': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_25, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_26': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_26, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_27': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_27, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_28': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_28, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_29': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_29, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_30': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_30, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_31': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_31, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_32': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_32, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_33': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_33, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_34': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_34, 
        'xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_35': xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_35
    }
    
    def get_cpu_metrics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_cpu_metrics.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_orig)
    xǁSystemMetricsCollectorǁget_cpu_metrics__mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁget_cpu_metrics'
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_orig(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_1(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = None
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_2(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "XXtotal_mbXX": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_3(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "TOTAL_MB": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_4(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(None, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_5(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, None),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_6(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_7(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, ),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_8(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 * 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_9(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total * 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_10(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1025 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_11(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1025, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_12(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 3),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_13(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "XXused_mbXX": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_14(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "USED_MB": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_15(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(None, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_16(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, None),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_17(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_18(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, ),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_19(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 * 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_20(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used * 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_21(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1025 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_22(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1025, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_23(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 3),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_24(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "XXavailable_mbXX": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_25(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "AVAILABLE_MB": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_26(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(None, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_27(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, None),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_28(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_29(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, ),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_30(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 * 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_31(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available * 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_32(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1025 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_33(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1025, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_34(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 3),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_35(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "XXpercentXX": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_36(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "PERCENT": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_37(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(None, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_38(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, None)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_39(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_40(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, )
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_41(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 3)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_42(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(None)
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_43(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"XXtotal_mbXX": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_44(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"TOTAL_MB": 0, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_45(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 1, "used_mb": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_46(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "XXused_mbXX": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_47(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "USED_MB": 0, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_48(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 1, "available_mb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_49(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "XXavailable_mbXX": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_50(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "AVAILABLE_MB": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_51(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 1, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_52(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "XXpercentXX": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_53(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "PERCENT": 0}
    
    def xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_54(self) -> Dict[str, Any]:
        """Память метрики"""
        try:
            vm = psutil.virtual_memory()
            return {
                "total_mb": round(vm.total / 1024 / 1024, 2),
                "used_mb": round(vm.used / 1024 / 1024, 2),
                "available_mb": round(vm.available / 1024 / 1024, 2),
                "percent": round(vm.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get memory metrics: {e}")
            return {"total_mb": 0, "used_mb": 0, "available_mb": 0, "percent": 1}
    
    xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_1': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_1, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_2': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_2, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_3': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_3, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_4': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_4, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_5': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_5, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_6': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_6, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_7': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_7, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_8': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_8, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_9': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_9, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_10': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_10, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_11': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_11, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_12': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_12, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_13': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_13, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_14': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_14, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_15': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_15, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_16': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_16, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_17': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_17, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_18': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_18, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_19': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_19, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_20': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_20, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_21': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_21, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_22': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_22, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_23': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_23, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_24': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_24, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_25': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_25, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_26': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_26, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_27': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_27, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_28': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_28, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_29': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_29, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_30': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_30, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_31': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_31, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_32': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_32, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_33': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_33, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_34': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_34, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_35': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_35, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_36': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_36, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_37': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_37, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_38': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_38, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_39': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_39, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_40': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_40, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_41': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_41, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_42': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_42, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_43': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_43, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_44': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_44, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_45': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_45, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_46': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_46, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_47': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_47, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_48': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_48, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_49': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_49, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_50': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_50, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_51': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_51, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_52': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_52, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_53': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_53, 
        'xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_54': xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_54
    }
    
    def get_memory_metrics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_memory_metrics.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_orig)
    xǁSystemMetricsCollectorǁget_memory_metrics__mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁget_memory_metrics'
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_orig(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_1(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = None
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_2(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage(None)
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_3(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('XX/XX')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_4(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "XXtotal_gbXX": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_5(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "TOTAL_GB": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_6(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(None, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_7(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, None),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_8(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_9(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, ),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_10(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 * 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_11(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 * 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_12(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total * 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_13(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1025 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_14(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1025 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_15(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1025, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_16(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 3),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_17(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "XXused_gbXX": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_18(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "USED_GB": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_19(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(None, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_20(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, None),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_21(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_22(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, ),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_23(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 * 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_24(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 * 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_25(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used * 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_26(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1025 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_27(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1025 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_28(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1025, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_29(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 3),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_30(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "XXfree_gbXX": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_31(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "FREE_GB": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_32(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(None, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_33(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, None),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_34(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_35(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, ),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_36(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 * 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_37(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 * 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_38(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free * 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_39(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1025 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_40(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1025 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_41(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1025, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_42(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 3),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_43(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "XXpercentXX": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_44(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "PERCENT": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_45(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(None, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_46(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, None)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_47(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_48(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, )
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_49(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 3)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_50(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(None)
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_51(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"XXtotal_gbXX": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_52(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"TOTAL_GB": 0, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_53(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 1, "used_gb": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_54(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "XXused_gbXX": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_55(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "USED_GB": 0, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_56(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 1, "free_gb": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_57(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "XXfree_gbXX": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_58(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "FREE_GB": 0, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_59(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 1, "percent": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_60(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "XXpercentXX": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_61(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "PERCENT": 0}
    
    def xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_62(self) -> Dict[str, Any]:
        """Диск метрики"""
        try:
            disk = psutil.disk_usage('/')
            return {
                "total_gb": round(disk.total / 1024 / 1024 / 1024, 2),
                "used_gb": round(disk.used / 1024 / 1024 / 1024, 2),
                "free_gb": round(disk.free / 1024 / 1024 / 1024, 2),
                "percent": round(disk.percent, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get disk metrics: {e}")
            return {"total_gb": 0, "used_gb": 0, "free_gb": 0, "percent": 1}
    
    xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_1': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_1, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_2': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_2, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_3': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_3, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_4': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_4, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_5': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_5, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_6': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_6, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_7': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_7, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_8': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_8, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_9': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_9, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_10': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_10, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_11': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_11, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_12': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_12, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_13': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_13, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_14': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_14, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_15': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_15, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_16': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_16, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_17': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_17, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_18': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_18, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_19': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_19, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_20': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_20, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_21': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_21, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_22': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_22, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_23': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_23, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_24': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_24, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_25': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_25, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_26': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_26, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_27': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_27, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_28': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_28, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_29': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_29, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_30': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_30, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_31': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_31, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_32': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_32, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_33': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_33, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_34': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_34, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_35': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_35, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_36': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_36, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_37': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_37, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_38': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_38, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_39': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_39, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_40': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_40, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_41': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_41, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_42': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_42, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_43': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_43, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_44': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_44, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_45': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_45, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_46': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_46, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_47': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_47, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_48': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_48, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_49': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_49, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_50': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_50, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_51': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_51, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_52': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_52, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_53': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_53, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_54': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_54, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_55': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_55, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_56': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_56, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_57': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_57, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_58': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_58, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_59': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_59, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_60': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_60, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_61': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_61, 
        'xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_62': xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_62
    }
    
    def get_disk_metrics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_disk_metrics.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_orig)
    xǁSystemMetricsCollectorǁget_disk_metrics__mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁget_disk_metrics'
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_orig(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_1(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = None
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_2(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = None
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_3(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() + self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_4(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = None
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_5(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) * time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_6(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv + self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_7(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta >= 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_8(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 1 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_9(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 1
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_10(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = None
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_11(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) * time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_12(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent + self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_13(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta >= 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_14(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 1 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_15(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 1
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_16(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = None
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_17(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 1
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_18(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') or hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_19(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(None, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_20(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, None) and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_21(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr('dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_22(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, ) and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_23(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'XXdropinXX') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_24(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'DROPIN') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_25(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(None, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_26(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, None):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_27(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr('dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_28(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, ):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_29(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'XXdropoutXX'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_30(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'DROPOUT'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_31(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = None
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_32(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv - net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_33(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = None
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_34(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in / 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_35(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin * total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_36(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 101) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_37(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in >= 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_38(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 1 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_39(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 1
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_40(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = None
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_41(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = None
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_42(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "XXbytes_sentXX": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_43(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "BYTES_SENT": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_44(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "XXbytes_recvXX": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_45(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "BYTES_RECV": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_46(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "XXpackets_in_per_secXX": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_47(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "PACKETS_IN_PER_SEC": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_48(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(None, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_49(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, None),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_50(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_51(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, ),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_52(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 3),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_53(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "XXpackets_out_per_secXX": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_54(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "PACKETS_OUT_PER_SEC": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_55(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(None, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_56(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, None),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_57(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_58(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, ),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_59(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 3),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_60(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "XXpacket_loss_percentXX": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_61(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "PACKET_LOSS_PERCENT": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_62(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(None, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_63(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, None)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_64(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_65(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, )
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_66(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 3)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_67(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(None)
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_68(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "XXbytes_sentXX": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_69(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "BYTES_SENT": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_70(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 1,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_71(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "XXbytes_recvXX": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_72(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "BYTES_RECV": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_73(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 1,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_74(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "XXpackets_in_per_secXX": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_75(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "PACKETS_IN_PER_SEC": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_76(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 1,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_77(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "XXpackets_out_per_secXX": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_78(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "PACKETS_OUT_PER_SEC": 0,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_79(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 1,
                "packet_loss_percent": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_80(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "XXpacket_loss_percentXX": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_81(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "PACKET_LOSS_PERCENT": 0
            }
    
    def xǁSystemMetricsCollectorǁget_network_metrics__mutmut_82(self) -> Dict[str, Any]:
        """Сетевые метрики"""
        try:
            net_io = psutil.net_io_counters()
            time_delta = time.time() - self._last_net_io_time
            
            # Вычисляем пакеты в секунду
            packets_in_per_sec = (net_io.packets_recv - self._last_net_io.packets_recv) / time_delta if time_delta > 0 else 0
            packets_out_per_sec = (net_io.packets_sent - self._last_net_io.packets_sent) / time_delta if time_delta > 0 else 0
            
            # Вычисляем потерь (если доступно)
            packet_loss = 0
            if hasattr(net_io, 'dropin') and hasattr(net_io, 'dropout'):
                total_packets_in = net_io.packets_recv + net_io.dropin
                packet_loss = (net_io.dropin / total_packets_in * 100) if total_packets_in > 0 else 0
            
            self._last_net_io = net_io
            self._last_net_io_time = time.time()
            
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_in_per_sec": round(packets_in_per_sec, 2),
                "packets_out_per_sec": round(packets_out_per_sec, 2),
                "packet_loss_percent": round(packet_loss, 2)
            }
        except Exception as e:
            logger.warning(f"Failed to get network metrics: {e}")
            return {
                "bytes_sent": 0,
                "bytes_recv": 0,
                "packets_in_per_sec": 0,
                "packets_out_per_sec": 0,
                "packet_loss_percent": 1
            }
    
    xǁSystemMetricsCollectorǁget_network_metrics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_1': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_1, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_2': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_2, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_3': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_3, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_4': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_4, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_5': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_5, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_6': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_6, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_7': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_7, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_8': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_8, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_9': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_9, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_10': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_10, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_11': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_11, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_12': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_12, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_13': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_13, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_14': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_14, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_15': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_15, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_16': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_16, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_17': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_17, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_18': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_18, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_19': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_19, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_20': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_20, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_21': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_21, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_22': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_22, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_23': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_23, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_24': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_24, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_25': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_25, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_26': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_26, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_27': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_27, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_28': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_28, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_29': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_29, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_30': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_30, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_31': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_31, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_32': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_32, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_33': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_33, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_34': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_34, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_35': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_35, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_36': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_36, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_37': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_37, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_38': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_38, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_39': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_39, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_40': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_40, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_41': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_41, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_42': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_42, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_43': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_43, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_44': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_44, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_45': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_45, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_46': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_46, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_47': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_47, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_48': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_48, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_49': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_49, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_50': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_50, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_51': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_51, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_52': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_52, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_53': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_53, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_54': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_54, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_55': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_55, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_56': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_56, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_57': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_57, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_58': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_58, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_59': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_59, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_60': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_60, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_61': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_61, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_62': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_62, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_63': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_63, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_64': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_64, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_65': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_65, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_66': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_66, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_67': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_67, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_68': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_68, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_69': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_69, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_70': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_70, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_71': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_71, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_72': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_72, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_73': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_73, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_74': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_74, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_75': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_75, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_76': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_76, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_77': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_77, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_78': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_78, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_79': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_79, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_80': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_80, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_81': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_81, 
        'xǁSystemMetricsCollectorǁget_network_metrics__mutmut_82': xǁSystemMetricsCollectorǁget_network_metrics__mutmut_82
    }
    
    def get_network_metrics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_network_metrics__mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_network_metrics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_network_metrics.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁget_network_metrics__mutmut_orig)
    xǁSystemMetricsCollectorǁget_network_metrics__mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁget_network_metrics'
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_orig(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_1(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "XXtotalXX": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_2(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "TOTAL": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_3(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "XXrunningXX": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_4(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "RUNNING": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_5(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(None)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_6(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(2 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_7(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(None) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_8(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['XXstatusXX']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_9(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['STATUS']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_10(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['XXstatusXX'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_11(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['STATUS'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_12(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] != psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_13(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(None)
            return {"total": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_14(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"XXtotalXX": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_15(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"TOTAL": 0, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_16(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 1, "running": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_17(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "XXrunningXX": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_18(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "RUNNING": 0}
    
    def xǁSystemMetricsCollectorǁget_process_count__mutmut_19(self) -> Dict[str, Any]:
        """Информация о процессах"""
        try:
            return {
                "total": len(psutil.pids()),
                "running": sum(1 for p in psutil.process_iter(['status']) if p.info['status'] == psutil.STATUS_RUNNING)
            }
        except Exception as e:
            logger.warning(f"Failed to get process metrics: {e}")
            return {"total": 0, "running": 1}
    
    xǁSystemMetricsCollectorǁget_process_count__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁget_process_count__mutmut_1': xǁSystemMetricsCollectorǁget_process_count__mutmut_1, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_2': xǁSystemMetricsCollectorǁget_process_count__mutmut_2, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_3': xǁSystemMetricsCollectorǁget_process_count__mutmut_3, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_4': xǁSystemMetricsCollectorǁget_process_count__mutmut_4, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_5': xǁSystemMetricsCollectorǁget_process_count__mutmut_5, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_6': xǁSystemMetricsCollectorǁget_process_count__mutmut_6, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_7': xǁSystemMetricsCollectorǁget_process_count__mutmut_7, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_8': xǁSystemMetricsCollectorǁget_process_count__mutmut_8, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_9': xǁSystemMetricsCollectorǁget_process_count__mutmut_9, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_10': xǁSystemMetricsCollectorǁget_process_count__mutmut_10, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_11': xǁSystemMetricsCollectorǁget_process_count__mutmut_11, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_12': xǁSystemMetricsCollectorǁget_process_count__mutmut_12, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_13': xǁSystemMetricsCollectorǁget_process_count__mutmut_13, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_14': xǁSystemMetricsCollectorǁget_process_count__mutmut_14, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_15': xǁSystemMetricsCollectorǁget_process_count__mutmut_15, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_16': xǁSystemMetricsCollectorǁget_process_count__mutmut_16, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_17': xǁSystemMetricsCollectorǁget_process_count__mutmut_17, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_18': xǁSystemMetricsCollectorǁget_process_count__mutmut_18, 
        'xǁSystemMetricsCollectorǁget_process_count__mutmut_19': xǁSystemMetricsCollectorǁget_process_count__mutmut_19
    }
    
    def get_process_count(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_process_count__mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_process_count__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_process_count.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁget_process_count__mutmut_orig)
    xǁSystemMetricsCollectorǁget_process_count__mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁget_process_count'
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_orig(self) -> float:
        """Время работы системы в секундах"""
        return round(time.time() - self.start_time, 2)
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_1(self) -> float:
        """Время работы системы в секундах"""
        return round(None, 2)
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_2(self) -> float:
        """Время работы системы в секундах"""
        return round(time.time() - self.start_time, None)
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_3(self) -> float:
        """Время работы системы в секундах"""
        return round(2)
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_4(self) -> float:
        """Время работы системы в секундах"""
        return round(time.time() - self.start_time, )
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_5(self) -> float:
        """Время работы системы в секундах"""
        return round(time.time() + self.start_time, 2)
    
    def xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_6(self) -> float:
        """Время работы системы в секундах"""
        return round(time.time() - self.start_time, 3)
    
    xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_1': xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_1, 
        'xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_2': xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_2, 
        'xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_3': xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_3, 
        'xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_4': xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_4, 
        'xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_5': xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_5, 
        'xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_6': xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_6
    }
    
    def get_uptime_seconds(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_orig"), object.__getattribute__(self, "xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_uptime_seconds.__signature__ = _mutmut_signature(xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_orig)
    xǁSystemMetricsCollectorǁget_uptime_seconds__mutmut_orig.__name__ = 'xǁSystemMetricsCollectorǁget_uptime_seconds'


class MeshNetworkMetrics:
    """Метрики mesh сети"""
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_orig(self):
        self.peer_count = 0
        self.connected_peers = 0
        self.bandwidth_limit_mbps = 0
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_1(self):
        self.peer_count = None
        self.connected_peers = 0
        self.bandwidth_limit_mbps = 0
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_2(self):
        self.peer_count = 1
        self.connected_peers = 0
        self.bandwidth_limit_mbps = 0
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_3(self):
        self.peer_count = 0
        self.connected_peers = None
        self.bandwidth_limit_mbps = 0
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_4(self):
        self.peer_count = 0
        self.connected_peers = 1
        self.bandwidth_limit_mbps = 0
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_5(self):
        self.peer_count = 0
        self.connected_peers = 0
        self.bandwidth_limit_mbps = None
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_6(self):
        self.peer_count = 0
        self.connected_peers = 0
        self.bandwidth_limit_mbps = 1
        self.last_update = None
    
    def xǁMeshNetworkMetricsǁ__init____mutmut_7(self):
        self.peer_count = 0
        self.connected_peers = 0
        self.bandwidth_limit_mbps = 0
        self.last_update = ""
    
    xǁMeshNetworkMetricsǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshNetworkMetricsǁ__init____mutmut_1': xǁMeshNetworkMetricsǁ__init____mutmut_1, 
        'xǁMeshNetworkMetricsǁ__init____mutmut_2': xǁMeshNetworkMetricsǁ__init____mutmut_2, 
        'xǁMeshNetworkMetricsǁ__init____mutmut_3': xǁMeshNetworkMetricsǁ__init____mutmut_3, 
        'xǁMeshNetworkMetricsǁ__init____mutmut_4': xǁMeshNetworkMetricsǁ__init____mutmut_4, 
        'xǁMeshNetworkMetricsǁ__init____mutmut_5': xǁMeshNetworkMetricsǁ__init____mutmut_5, 
        'xǁMeshNetworkMetricsǁ__init____mutmut_6': xǁMeshNetworkMetricsǁ__init____mutmut_6, 
        'xǁMeshNetworkMetricsǁ__init____mutmut_7': xǁMeshNetworkMetricsǁ__init____mutmut_7
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshNetworkMetricsǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMeshNetworkMetricsǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMeshNetworkMetricsǁ__init____mutmut_orig)
    xǁMeshNetworkMetricsǁ__init____mutmut_orig.__name__ = 'xǁMeshNetworkMetricsǁ__init__'
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_orig(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "connected_peers": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_1(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "XXtotal_peersXX": self.peer_count,
            "connected_peers": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_2(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "TOTAL_PEERS": self.peer_count,
            "connected_peers": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_3(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "XXconnected_peersXX": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_4(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "CONNECTED_PEERS": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_5(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "connected_peers": self.connected_peers,
            "XXbandwidth_limit_mbpsXX": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_6(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "connected_peers": self.connected_peers,
            "BANDWIDTH_LIMIT_MBPS": self.bandwidth_limit_mbps,
            "last_update": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_7(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "connected_peers": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "XXlast_updateXX": self.last_update
        }
    
    def xǁMeshNetworkMetricsǁget_metrics__mutmut_8(self) -> Dict[str, Any]:
        """Получить метрики mesh сети"""
        return {
            "total_peers": self.peer_count,
            "connected_peers": self.connected_peers,
            "bandwidth_limit_mbps": self.bandwidth_limit_mbps,
            "LAST_UPDATE": self.last_update
        }
    
    xǁMeshNetworkMetricsǁget_metrics__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshNetworkMetricsǁget_metrics__mutmut_1': xǁMeshNetworkMetricsǁget_metrics__mutmut_1, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_2': xǁMeshNetworkMetricsǁget_metrics__mutmut_2, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_3': xǁMeshNetworkMetricsǁget_metrics__mutmut_3, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_4': xǁMeshNetworkMetricsǁget_metrics__mutmut_4, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_5': xǁMeshNetworkMetricsǁget_metrics__mutmut_5, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_6': xǁMeshNetworkMetricsǁget_metrics__mutmut_6, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_7': xǁMeshNetworkMetricsǁget_metrics__mutmut_7, 
        'xǁMeshNetworkMetricsǁget_metrics__mutmut_8': xǁMeshNetworkMetricsǁget_metrics__mutmut_8
    }
    
    def get_metrics(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshNetworkMetricsǁget_metrics__mutmut_orig"), object.__getattribute__(self, "xǁMeshNetworkMetricsǁget_metrics__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_metrics.__signature__ = _mutmut_signature(xǁMeshNetworkMetricsǁget_metrics__mutmut_orig)
    xǁMeshNetworkMetricsǁget_metrics__mutmut_orig.__name__ = 'xǁMeshNetworkMetricsǁget_metrics'
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_orig(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_1(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = None  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_2(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 3  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_3(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = None
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_4(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 2
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_5(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = None
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_6(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 101
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_7(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = None
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_8(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(None)
            self.peer_count = 0
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_9(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = None
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_10(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 1
            self.connected_peers = 0
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_11(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = None
    
    def xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_12(self) -> None:
        """Обновить метрики из batman-adv"""
        try:
            # Попытка прочитать информацию из batman-adv (если доступно)
            # Для разработки используем заглушку
            self.peer_count = 2  # Фиксированное значение для dev
            self.connected_peers = 1
            self.bandwidth_limit_mbps = 100
            self.last_update = datetime.utcnow().isoformat()
        except Exception as e:
            logger.debug(f"Could not read batman-adv metrics: {e}")
            self.peer_count = 0
            self.connected_peers = 1
    
    xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_1': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_1, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_2': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_2, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_3': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_3, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_4': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_4, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_5': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_5, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_6': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_6, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_7': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_7, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_8': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_8, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_9': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_9, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_10': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_10, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_11': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_11, 
        'xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_12': xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_12
    }
    
    def update_from_batman_adv(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_orig"), object.__getattribute__(self, "xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_mutants"), args, kwargs, self)
        return result 
    
    update_from_batman_adv.__signature__ = _mutmut_signature(xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_orig)
    xǁMeshNetworkMetricsǁupdate_from_batman_adv__mutmut_orig.__name__ = 'xǁMeshNetworkMetricsǁupdate_from_batman_adv'


class StatusData:
    """Агрегирует все данные о статусе системы"""
    
    def xǁStatusDataǁ__init____mutmut_orig(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_1(self):
        self.system_metrics = None
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_2(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = None
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_3(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = None
    
    def xǁStatusDataǁ__init____mutmut_4(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "XXrunningXX": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_5(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "RUNNING": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_6(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": True,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_7(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "XXcurrent_phaseXX": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_8(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "CURRENT_PHASE": None,
            "iterations": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_9(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "XXiterationsXX": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_10(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "ITERATIONS": 0,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_11(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 1,
            "last_cycle_time_ms": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_12(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "XXlast_cycle_time_msXX": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_13(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "LAST_CYCLE_TIME_MS": 0
        }
    
    def xǁStatusDataǁ__init____mutmut_14(self):
        self.system_metrics = SystemMetricsCollector()
        self.mesh_metrics = MeshNetworkMetrics()
        self.loop_state = {
            "running": False,
            "current_phase": None,
            "iterations": 0,
            "last_cycle_time_ms": 1
        }
    
    xǁStatusDataǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁStatusDataǁ__init____mutmut_1': xǁStatusDataǁ__init____mutmut_1, 
        'xǁStatusDataǁ__init____mutmut_2': xǁStatusDataǁ__init____mutmut_2, 
        'xǁStatusDataǁ__init____mutmut_3': xǁStatusDataǁ__init____mutmut_3, 
        'xǁStatusDataǁ__init____mutmut_4': xǁStatusDataǁ__init____mutmut_4, 
        'xǁStatusDataǁ__init____mutmut_5': xǁStatusDataǁ__init____mutmut_5, 
        'xǁStatusDataǁ__init____mutmut_6': xǁStatusDataǁ__init____mutmut_6, 
        'xǁStatusDataǁ__init____mutmut_7': xǁStatusDataǁ__init____mutmut_7, 
        'xǁStatusDataǁ__init____mutmut_8': xǁStatusDataǁ__init____mutmut_8, 
        'xǁStatusDataǁ__init____mutmut_9': xǁStatusDataǁ__init____mutmut_9, 
        'xǁStatusDataǁ__init____mutmut_10': xǁStatusDataǁ__init____mutmut_10, 
        'xǁStatusDataǁ__init____mutmut_11': xǁStatusDataǁ__init____mutmut_11, 
        'xǁStatusDataǁ__init____mutmut_12': xǁStatusDataǁ__init____mutmut_12, 
        'xǁStatusDataǁ__init____mutmut_13': xǁStatusDataǁ__init____mutmut_13, 
        'xǁStatusDataǁ__init____mutmut_14': xǁStatusDataǁ__init____mutmut_14
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁStatusDataǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁStatusDataǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁStatusDataǁ__init____mutmut_orig)
    xǁStatusDataǁ__init____mutmut_orig.__name__ = 'xǁStatusDataǁ__init__'
    
    def xǁStatusDataǁget_status__mutmut_orig(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_1(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = None
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_2(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["XXpercentXX"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_3(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["PERCENT"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_4(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = None
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_5(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["XXpercentXX"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_6(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["PERCENT"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_7(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = None
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_8(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["XXpercentXX"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_9(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["PERCENT"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_10(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = None
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_11(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["XXpacket_loss_percentXX"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_12(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["PACKET_LOSS_PERCENT"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_13(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 or packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_14(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 or disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_15(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 or mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_16(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent <= 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_17(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 81 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_18(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent <= 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_19(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 81 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_20(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent <= 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_21(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 91 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_22(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss <= 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_23(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 6:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_24(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = None
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_25(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "XXhealthyXX"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_26(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "HEALTHY"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_27(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 or packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_28(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 or disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_29(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 or mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_30(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent <= 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_31(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 91 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_32(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent <= 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_33(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 91 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_34(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent <= 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_35(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 96 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_36(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss <= 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_37(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 11:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_38(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = None
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_39(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "XXwarningXX"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_40(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "WARNING"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_41(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = None
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_42(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "XXcriticalXX"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_43(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "CRITICAL"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_44(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "XXstatusXX": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_45(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "STATUS": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_46(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "XXversionXX": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_47(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "VERSION": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_48(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "XX3.1.0XX",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_49(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "XXtimestampXX": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_50(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "TIMESTAMP": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_51(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "XXuptime_secondsXX": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_52(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "UPTIME_SECONDS": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_53(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "XXsystemXX": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_54(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "SYSTEM": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_55(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "XXcpuXX": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_56(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "CPU": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_57(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "XXmemoryXX": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_58(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "MEMORY": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_59(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "XXdiskXX": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_60(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "DISK": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_61(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "XXprocessesXX": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_62(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "PROCESSES": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_63(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "XXnetworkXX": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_64(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "NETWORK": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_65(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "XXmeshXX": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_66(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "MESH": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_67(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "XXloopXX": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_68(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "LOOP": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_69(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "XXhealthXX": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_70(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "HEALTH": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_71(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "XXcpu_okXX": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_72(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "CPU_OK": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_73(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent <= 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_74(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 81,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_75(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "XXmemory_okXX": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_76(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "MEMORY_OK": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_77(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent <= 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_78(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 81,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_79(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "XXdisk_okXX": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_80(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "DISK_OK": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_81(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent <= 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_82(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 91,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_83(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "XXnetwork_okXX": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_84(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "NETWORK_OK": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_85(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss <= 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_86(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 6,
                "mesh_connected": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_87(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "XXmesh_connectedXX": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_88(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "MESH_CONNECTED": self.mesh_metrics.connected_peers > 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_89(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers >= 0
            }
        }
    
    def xǁStatusDataǁget_status__mutmut_90(self) -> Dict[str, Any]:
        """Получить полный статус системы"""
        
        # Обновить метрики mesh сети
        self.mesh_metrics.update_from_batman_adv()
        
        # Определить общее здоровье системы
        cpu_percent = self.system_metrics.get_cpu_metrics()["percent"]
        mem_percent = self.system_metrics.get_memory_metrics()["percent"]
        disk_percent = self.system_metrics.get_disk_metrics()["percent"]
        packet_loss = self.system_metrics.get_network_metrics()["packet_loss_percent"]
        
        # Определить статус (здорова, предупреждение, критичная)
        if cpu_percent < 80 and mem_percent < 80 and disk_percent < 90 and packet_loss < 5:
            status = "healthy"
        elif cpu_percent < 90 and mem_percent < 90 and disk_percent < 95 and packet_loss < 10:
            status = "warning"
        else:
            status = "critical"
        
        return {
            "status": status,
            "version": "3.1.0",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": self.system_metrics.get_uptime_seconds(),
            
            # Система
            "system": {
                "cpu": self.system_metrics.get_cpu_metrics(),
                "memory": self.system_metrics.get_memory_metrics(),
                "disk": self.system_metrics.get_disk_metrics(),
                "processes": self.system_metrics.get_process_count(),
                "network": self.system_metrics.get_network_metrics()
            },
            
            # Mesh сеть
            "mesh": self.mesh_metrics.get_metrics(),
            
            # MAPE-K loop
            "loop": self.loop_state,
            
            # Здоровье компонентов
            "health": {
                "cpu_ok": cpu_percent < 80,
                "memory_ok": mem_percent < 80,
                "disk_ok": disk_percent < 90,
                "network_ok": packet_loss < 5,
                "mesh_connected": self.mesh_metrics.connected_peers > 1
            }
        }
    
    xǁStatusDataǁget_status__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁStatusDataǁget_status__mutmut_1': xǁStatusDataǁget_status__mutmut_1, 
        'xǁStatusDataǁget_status__mutmut_2': xǁStatusDataǁget_status__mutmut_2, 
        'xǁStatusDataǁget_status__mutmut_3': xǁStatusDataǁget_status__mutmut_3, 
        'xǁStatusDataǁget_status__mutmut_4': xǁStatusDataǁget_status__mutmut_4, 
        'xǁStatusDataǁget_status__mutmut_5': xǁStatusDataǁget_status__mutmut_5, 
        'xǁStatusDataǁget_status__mutmut_6': xǁStatusDataǁget_status__mutmut_6, 
        'xǁStatusDataǁget_status__mutmut_7': xǁStatusDataǁget_status__mutmut_7, 
        'xǁStatusDataǁget_status__mutmut_8': xǁStatusDataǁget_status__mutmut_8, 
        'xǁStatusDataǁget_status__mutmut_9': xǁStatusDataǁget_status__mutmut_9, 
        'xǁStatusDataǁget_status__mutmut_10': xǁStatusDataǁget_status__mutmut_10, 
        'xǁStatusDataǁget_status__mutmut_11': xǁStatusDataǁget_status__mutmut_11, 
        'xǁStatusDataǁget_status__mutmut_12': xǁStatusDataǁget_status__mutmut_12, 
        'xǁStatusDataǁget_status__mutmut_13': xǁStatusDataǁget_status__mutmut_13, 
        'xǁStatusDataǁget_status__mutmut_14': xǁStatusDataǁget_status__mutmut_14, 
        'xǁStatusDataǁget_status__mutmut_15': xǁStatusDataǁget_status__mutmut_15, 
        'xǁStatusDataǁget_status__mutmut_16': xǁStatusDataǁget_status__mutmut_16, 
        'xǁStatusDataǁget_status__mutmut_17': xǁStatusDataǁget_status__mutmut_17, 
        'xǁStatusDataǁget_status__mutmut_18': xǁStatusDataǁget_status__mutmut_18, 
        'xǁStatusDataǁget_status__mutmut_19': xǁStatusDataǁget_status__mutmut_19, 
        'xǁStatusDataǁget_status__mutmut_20': xǁStatusDataǁget_status__mutmut_20, 
        'xǁStatusDataǁget_status__mutmut_21': xǁStatusDataǁget_status__mutmut_21, 
        'xǁStatusDataǁget_status__mutmut_22': xǁStatusDataǁget_status__mutmut_22, 
        'xǁStatusDataǁget_status__mutmut_23': xǁStatusDataǁget_status__mutmut_23, 
        'xǁStatusDataǁget_status__mutmut_24': xǁStatusDataǁget_status__mutmut_24, 
        'xǁStatusDataǁget_status__mutmut_25': xǁStatusDataǁget_status__mutmut_25, 
        'xǁStatusDataǁget_status__mutmut_26': xǁStatusDataǁget_status__mutmut_26, 
        'xǁStatusDataǁget_status__mutmut_27': xǁStatusDataǁget_status__mutmut_27, 
        'xǁStatusDataǁget_status__mutmut_28': xǁStatusDataǁget_status__mutmut_28, 
        'xǁStatusDataǁget_status__mutmut_29': xǁStatusDataǁget_status__mutmut_29, 
        'xǁStatusDataǁget_status__mutmut_30': xǁStatusDataǁget_status__mutmut_30, 
        'xǁStatusDataǁget_status__mutmut_31': xǁStatusDataǁget_status__mutmut_31, 
        'xǁStatusDataǁget_status__mutmut_32': xǁStatusDataǁget_status__mutmut_32, 
        'xǁStatusDataǁget_status__mutmut_33': xǁStatusDataǁget_status__mutmut_33, 
        'xǁStatusDataǁget_status__mutmut_34': xǁStatusDataǁget_status__mutmut_34, 
        'xǁStatusDataǁget_status__mutmut_35': xǁStatusDataǁget_status__mutmut_35, 
        'xǁStatusDataǁget_status__mutmut_36': xǁStatusDataǁget_status__mutmut_36, 
        'xǁStatusDataǁget_status__mutmut_37': xǁStatusDataǁget_status__mutmut_37, 
        'xǁStatusDataǁget_status__mutmut_38': xǁStatusDataǁget_status__mutmut_38, 
        'xǁStatusDataǁget_status__mutmut_39': xǁStatusDataǁget_status__mutmut_39, 
        'xǁStatusDataǁget_status__mutmut_40': xǁStatusDataǁget_status__mutmut_40, 
        'xǁStatusDataǁget_status__mutmut_41': xǁStatusDataǁget_status__mutmut_41, 
        'xǁStatusDataǁget_status__mutmut_42': xǁStatusDataǁget_status__mutmut_42, 
        'xǁStatusDataǁget_status__mutmut_43': xǁStatusDataǁget_status__mutmut_43, 
        'xǁStatusDataǁget_status__mutmut_44': xǁStatusDataǁget_status__mutmut_44, 
        'xǁStatusDataǁget_status__mutmut_45': xǁStatusDataǁget_status__mutmut_45, 
        'xǁStatusDataǁget_status__mutmut_46': xǁStatusDataǁget_status__mutmut_46, 
        'xǁStatusDataǁget_status__mutmut_47': xǁStatusDataǁget_status__mutmut_47, 
        'xǁStatusDataǁget_status__mutmut_48': xǁStatusDataǁget_status__mutmut_48, 
        'xǁStatusDataǁget_status__mutmut_49': xǁStatusDataǁget_status__mutmut_49, 
        'xǁStatusDataǁget_status__mutmut_50': xǁStatusDataǁget_status__mutmut_50, 
        'xǁStatusDataǁget_status__mutmut_51': xǁStatusDataǁget_status__mutmut_51, 
        'xǁStatusDataǁget_status__mutmut_52': xǁStatusDataǁget_status__mutmut_52, 
        'xǁStatusDataǁget_status__mutmut_53': xǁStatusDataǁget_status__mutmut_53, 
        'xǁStatusDataǁget_status__mutmut_54': xǁStatusDataǁget_status__mutmut_54, 
        'xǁStatusDataǁget_status__mutmut_55': xǁStatusDataǁget_status__mutmut_55, 
        'xǁStatusDataǁget_status__mutmut_56': xǁStatusDataǁget_status__mutmut_56, 
        'xǁStatusDataǁget_status__mutmut_57': xǁStatusDataǁget_status__mutmut_57, 
        'xǁStatusDataǁget_status__mutmut_58': xǁStatusDataǁget_status__mutmut_58, 
        'xǁStatusDataǁget_status__mutmut_59': xǁStatusDataǁget_status__mutmut_59, 
        'xǁStatusDataǁget_status__mutmut_60': xǁStatusDataǁget_status__mutmut_60, 
        'xǁStatusDataǁget_status__mutmut_61': xǁStatusDataǁget_status__mutmut_61, 
        'xǁStatusDataǁget_status__mutmut_62': xǁStatusDataǁget_status__mutmut_62, 
        'xǁStatusDataǁget_status__mutmut_63': xǁStatusDataǁget_status__mutmut_63, 
        'xǁStatusDataǁget_status__mutmut_64': xǁStatusDataǁget_status__mutmut_64, 
        'xǁStatusDataǁget_status__mutmut_65': xǁStatusDataǁget_status__mutmut_65, 
        'xǁStatusDataǁget_status__mutmut_66': xǁStatusDataǁget_status__mutmut_66, 
        'xǁStatusDataǁget_status__mutmut_67': xǁStatusDataǁget_status__mutmut_67, 
        'xǁStatusDataǁget_status__mutmut_68': xǁStatusDataǁget_status__mutmut_68, 
        'xǁStatusDataǁget_status__mutmut_69': xǁStatusDataǁget_status__mutmut_69, 
        'xǁStatusDataǁget_status__mutmut_70': xǁStatusDataǁget_status__mutmut_70, 
        'xǁStatusDataǁget_status__mutmut_71': xǁStatusDataǁget_status__mutmut_71, 
        'xǁStatusDataǁget_status__mutmut_72': xǁStatusDataǁget_status__mutmut_72, 
        'xǁStatusDataǁget_status__mutmut_73': xǁStatusDataǁget_status__mutmut_73, 
        'xǁStatusDataǁget_status__mutmut_74': xǁStatusDataǁget_status__mutmut_74, 
        'xǁStatusDataǁget_status__mutmut_75': xǁStatusDataǁget_status__mutmut_75, 
        'xǁStatusDataǁget_status__mutmut_76': xǁStatusDataǁget_status__mutmut_76, 
        'xǁStatusDataǁget_status__mutmut_77': xǁStatusDataǁget_status__mutmut_77, 
        'xǁStatusDataǁget_status__mutmut_78': xǁStatusDataǁget_status__mutmut_78, 
        'xǁStatusDataǁget_status__mutmut_79': xǁStatusDataǁget_status__mutmut_79, 
        'xǁStatusDataǁget_status__mutmut_80': xǁStatusDataǁget_status__mutmut_80, 
        'xǁStatusDataǁget_status__mutmut_81': xǁStatusDataǁget_status__mutmut_81, 
        'xǁStatusDataǁget_status__mutmut_82': xǁStatusDataǁget_status__mutmut_82, 
        'xǁStatusDataǁget_status__mutmut_83': xǁStatusDataǁget_status__mutmut_83, 
        'xǁStatusDataǁget_status__mutmut_84': xǁStatusDataǁget_status__mutmut_84, 
        'xǁStatusDataǁget_status__mutmut_85': xǁStatusDataǁget_status__mutmut_85, 
        'xǁStatusDataǁget_status__mutmut_86': xǁStatusDataǁget_status__mutmut_86, 
        'xǁStatusDataǁget_status__mutmut_87': xǁStatusDataǁget_status__mutmut_87, 
        'xǁStatusDataǁget_status__mutmut_88': xǁStatusDataǁget_status__mutmut_88, 
        'xǁStatusDataǁget_status__mutmut_89': xǁStatusDataǁget_status__mutmut_89, 
        'xǁStatusDataǁget_status__mutmut_90': xǁStatusDataǁget_status__mutmut_90
    }
    
    def get_status(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁStatusDataǁget_status__mutmut_orig"), object.__getattribute__(self, "xǁStatusDataǁget_status__mutmut_mutants"), args, kwargs, self)
        return result 
    
    get_status.__signature__ = _mutmut_signature(xǁStatusDataǁget_status__mutmut_orig)
    xǁStatusDataǁget_status__mutmut_orig.__name__ = 'xǁStatusDataǁget_status'


# Глобальный экземпляр
_status_data: Optional[StatusData] = None


def x_get_status_data__mutmut_orig() -> StatusData:
    """Получить глобальный объект статуса"""
    global _status_data
    if _status_data is None:
        _status_data = StatusData()
    return _status_data


def x_get_status_data__mutmut_1() -> StatusData:
    """Получить глобальный объект статуса"""
    global _status_data
    if _status_data is not None:
        _status_data = StatusData()
    return _status_data


def x_get_status_data__mutmut_2() -> StatusData:
    """Получить глобальный объект статуса"""
    global _status_data
    if _status_data is None:
        _status_data = None
    return _status_data

x_get_status_data__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_status_data__mutmut_1': x_get_status_data__mutmut_1, 
    'x_get_status_data__mutmut_2': x_get_status_data__mutmut_2
}

def get_status_data(*args, **kwargs):
    result = _mutmut_trampoline(x_get_status_data__mutmut_orig, x_get_status_data__mutmut_mutants, args, kwargs)
    return result 

get_status_data.__signature__ = _mutmut_signature(x_get_status_data__mutmut_orig)
x_get_status_data__mutmut_orig.__name__ = 'x_get_status_data'


def get_current_status() -> Dict[str, Any]:
    """Получить текущий статус системы"""
    return get_status_data().get_status()
