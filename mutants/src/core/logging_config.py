"""
Structured logging configuration for x0tta6bl4.

Provides:
- JSON-based structured logging
- Log levels configuration
- Multiple handlers (console, file, remote)
- Correlation IDs for request tracking
- Sensitive data masking
"""

import json
import logging
import logging.handlers
import os
import re
import sys
from datetime import datetime
from functools import lru_cache
from typing import Optional, Dict, Any

import structlog
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


@lru_cache
def get_log_level() -> str:
    """Get log level from environment"""
    return os.getenv("LOG_LEVEL", "INFO").upper()


def x_mask_sensitive_data__mutmut_orig(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_1(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = None
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_2(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'XXpassword["\']?\s*[:=]\s*["\']?[^"\'\s]+XX', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_3(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'PASSWORD["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_4(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'XXpassword=***XX'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_5(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'PASSWORD=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_6(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'XXtoken["\']?\s*[:=]\s*["\']?[^"\'\s]+XX', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_7(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'TOKEN["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_8(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'XXtoken=***XX'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_9(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'TOKEN=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_10(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'XXapi[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+XX', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_11(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'API[_-]?KEY["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_12(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'XXapi_key=***XX'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_13(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'API_KEY=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_14(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'XXauthorization["\']?\s*[:=]\s*["\']?[^"\'\s]+XX', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_15(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'AUTHORIZATION["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_16(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'XXauthorization=***XX'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_17(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'AUTHORIZATION=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_18(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = None
    
    return data


def x_mask_sensitive_data__mutmut_19(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(None, replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_20(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, None, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_21(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, None, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_22(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, flags=None)
    
    return data


def x_mask_sensitive_data__mutmut_23(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(replacement, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_24(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, data, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_25(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, flags=re.IGNORECASE)
    
    return data


def x_mask_sensitive_data__mutmut_26(data: str) -> str:
    """Mask sensitive data in logs"""
    patterns = [
        (r'password["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'password=***'),
        (r'token["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'token=***'),
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'api_key=***'),
        (r'authorization["\']?\s*[:=]\s*["\']?[^"\'\s]+', 'authorization=***'),
    ]
    
    for pattern, replacement in patterns:
        data = re.sub(pattern, replacement, data, )
    
    return data

x_mask_sensitive_data__mutmut_mutants : ClassVar[MutantDict] = {
'x_mask_sensitive_data__mutmut_1': x_mask_sensitive_data__mutmut_1, 
    'x_mask_sensitive_data__mutmut_2': x_mask_sensitive_data__mutmut_2, 
    'x_mask_sensitive_data__mutmut_3': x_mask_sensitive_data__mutmut_3, 
    'x_mask_sensitive_data__mutmut_4': x_mask_sensitive_data__mutmut_4, 
    'x_mask_sensitive_data__mutmut_5': x_mask_sensitive_data__mutmut_5, 
    'x_mask_sensitive_data__mutmut_6': x_mask_sensitive_data__mutmut_6, 
    'x_mask_sensitive_data__mutmut_7': x_mask_sensitive_data__mutmut_7, 
    'x_mask_sensitive_data__mutmut_8': x_mask_sensitive_data__mutmut_8, 
    'x_mask_sensitive_data__mutmut_9': x_mask_sensitive_data__mutmut_9, 
    'x_mask_sensitive_data__mutmut_10': x_mask_sensitive_data__mutmut_10, 
    'x_mask_sensitive_data__mutmut_11': x_mask_sensitive_data__mutmut_11, 
    'x_mask_sensitive_data__mutmut_12': x_mask_sensitive_data__mutmut_12, 
    'x_mask_sensitive_data__mutmut_13': x_mask_sensitive_data__mutmut_13, 
    'x_mask_sensitive_data__mutmut_14': x_mask_sensitive_data__mutmut_14, 
    'x_mask_sensitive_data__mutmut_15': x_mask_sensitive_data__mutmut_15, 
    'x_mask_sensitive_data__mutmut_16': x_mask_sensitive_data__mutmut_16, 
    'x_mask_sensitive_data__mutmut_17': x_mask_sensitive_data__mutmut_17, 
    'x_mask_sensitive_data__mutmut_18': x_mask_sensitive_data__mutmut_18, 
    'x_mask_sensitive_data__mutmut_19': x_mask_sensitive_data__mutmut_19, 
    'x_mask_sensitive_data__mutmut_20': x_mask_sensitive_data__mutmut_20, 
    'x_mask_sensitive_data__mutmut_21': x_mask_sensitive_data__mutmut_21, 
    'x_mask_sensitive_data__mutmut_22': x_mask_sensitive_data__mutmut_22, 
    'x_mask_sensitive_data__mutmut_23': x_mask_sensitive_data__mutmut_23, 
    'x_mask_sensitive_data__mutmut_24': x_mask_sensitive_data__mutmut_24, 
    'x_mask_sensitive_data__mutmut_25': x_mask_sensitive_data__mutmut_25, 
    'x_mask_sensitive_data__mutmut_26': x_mask_sensitive_data__mutmut_26
}

def mask_sensitive_data(*args, **kwargs):
    result = _mutmut_trampoline(x_mask_sensitive_data__mutmut_orig, x_mask_sensitive_data__mutmut_mutants, args, kwargs)
    return result 

mask_sensitive_data.__signature__ = _mutmut_signature(x_mask_sensitive_data__mutmut_orig)
x_mask_sensitive_data__mutmut_orig.__name__ = 'x_mask_sensitive_data'


class StructuredJsonFormatter(logging.Formatter):
    """Format logs as structured JSON for ELK/Loki"""
    
    def xǁStructuredJsonFormatterǁformat__mutmut_orig(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_1(self, record: logging.LogRecord) -> str:
        log_entry = None
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_2(self, record: logging.LogRecord) -> str:
        log_entry = {
            "XXtimestampXX": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_3(self, record: logging.LogRecord) -> str:
        log_entry = {
            "TIMESTAMP": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_4(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(None).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_5(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "XXlevelXX": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_6(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "LEVEL": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_7(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "XXloggerXX": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_8(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "LOGGER": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_9(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "XXmessageXX": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_10(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "MESSAGE": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_11(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "XXmoduleXX": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_12(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "MODULE": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_13(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "XXfunctionXX": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_14(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "FUNCTION": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_15(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "XXlineXX": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_16(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "LINE": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_17(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = None
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_18(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["XXexceptionXX"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_19(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["EXCEPTION"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_20(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(None)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_21(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(None, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_22(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, None):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_23(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr("request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_24(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, ):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_25(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "XXrequest_idXX"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_26(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "REQUEST_ID"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_27(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = None
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_28(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["XXrequest_idXX"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_29(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["REQUEST_ID"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_30(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(None, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_31(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, None):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_32(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr("user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_33(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, ):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_34(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "XXuser_idXX"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_35(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "USER_ID"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_36(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = None
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_37(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["XXuser_idXX"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_38(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["USER_ID"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_39(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(None, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_40(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, None):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_41(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr("duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_42(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, ):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_43(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "XXduration_msXX"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_44(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "DURATION_MS"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_45(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = None
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_46(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["XXduration_msXX"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_47(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["DURATION_MS"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_48(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = None
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_49(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_50(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "XXnameXX", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_51(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "NAME", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_52(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "XXmsgXX", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_53(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "MSG", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_54(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "XXargsXX", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_55(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "ARGS", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_56(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "XXcreatedXX", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_57(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "CREATED", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_58(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "XXfilenameXX", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_59(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "FILENAME", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_60(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "XXfuncNameXX",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_61(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcname",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_62(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "FUNCNAME",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_63(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "XXlevelnameXX", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_64(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "LEVELNAME", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_65(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "XXlevelnoXX", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_66(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "LEVELNO", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_67(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "XXlinenoXX", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_68(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "LINENO", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_69(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "XXmoduleXX", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_70(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "MODULE", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_71(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "XXmsecsXX",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_72(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "MSECS",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_73(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "XXmessageXX", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_74(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "MESSAGE", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_75(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "XXpathnameXX", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_76(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "PATHNAME", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_77(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "XXprocessXX", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_78(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "PROCESS", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_79(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "XXprocessNameXX", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_80(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processname", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_81(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "PROCESSNAME", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_82(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "XXrelativeCreatedXX",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_83(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativecreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_84(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "RELATIVECREATED",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_85(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "XXthreadXX", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_86(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "THREAD", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_87(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "XXthreadNameXX", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_88(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadname", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_89(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "THREADNAME", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_90(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "XXexc_infoXX", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_91(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "EXC_INFO", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_92(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "XXexc_textXX", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_93(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "EXC_TEXT", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_94(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "XXstack_infoXX"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_95(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "STACK_INFO"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_96(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(None)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_97(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = None
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_98(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(None, default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_99(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=None)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_100(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(default=str)
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_101(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, )
        serialized = mask_sensitive_data(serialized)
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_102(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = None
        
        return serialized
    
    def xǁStructuredJsonFormatterǁformat__mutmut_103(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)
        
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        
        if hasattr(record, "user_id"):
            log_entry["user_id"] = record.user_id
        
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms
        
        extra_fields = {
            k: v for k, v in record.__dict__.items()
            if k not in [
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "message", "pathname", "process", "processName", "relativeCreated",
                "thread", "threadName", "exc_info", "exc_text", "stack_info"
            ]
        }
        
        log_entry.update(extra_fields)
        
        # Mask sensitive data
        serialized = json.dumps(log_entry, default=str)
        serialized = mask_sensitive_data(None)
        
        return serialized
    
    xǁStructuredJsonFormatterǁformat__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁStructuredJsonFormatterǁformat__mutmut_1': xǁStructuredJsonFormatterǁformat__mutmut_1, 
        'xǁStructuredJsonFormatterǁformat__mutmut_2': xǁStructuredJsonFormatterǁformat__mutmut_2, 
        'xǁStructuredJsonFormatterǁformat__mutmut_3': xǁStructuredJsonFormatterǁformat__mutmut_3, 
        'xǁStructuredJsonFormatterǁformat__mutmut_4': xǁStructuredJsonFormatterǁformat__mutmut_4, 
        'xǁStructuredJsonFormatterǁformat__mutmut_5': xǁStructuredJsonFormatterǁformat__mutmut_5, 
        'xǁStructuredJsonFormatterǁformat__mutmut_6': xǁStructuredJsonFormatterǁformat__mutmut_6, 
        'xǁStructuredJsonFormatterǁformat__mutmut_7': xǁStructuredJsonFormatterǁformat__mutmut_7, 
        'xǁStructuredJsonFormatterǁformat__mutmut_8': xǁStructuredJsonFormatterǁformat__mutmut_8, 
        'xǁStructuredJsonFormatterǁformat__mutmut_9': xǁStructuredJsonFormatterǁformat__mutmut_9, 
        'xǁStructuredJsonFormatterǁformat__mutmut_10': xǁStructuredJsonFormatterǁformat__mutmut_10, 
        'xǁStructuredJsonFormatterǁformat__mutmut_11': xǁStructuredJsonFormatterǁformat__mutmut_11, 
        'xǁStructuredJsonFormatterǁformat__mutmut_12': xǁStructuredJsonFormatterǁformat__mutmut_12, 
        'xǁStructuredJsonFormatterǁformat__mutmut_13': xǁStructuredJsonFormatterǁformat__mutmut_13, 
        'xǁStructuredJsonFormatterǁformat__mutmut_14': xǁStructuredJsonFormatterǁformat__mutmut_14, 
        'xǁStructuredJsonFormatterǁformat__mutmut_15': xǁStructuredJsonFormatterǁformat__mutmut_15, 
        'xǁStructuredJsonFormatterǁformat__mutmut_16': xǁStructuredJsonFormatterǁformat__mutmut_16, 
        'xǁStructuredJsonFormatterǁformat__mutmut_17': xǁStructuredJsonFormatterǁformat__mutmut_17, 
        'xǁStructuredJsonFormatterǁformat__mutmut_18': xǁStructuredJsonFormatterǁformat__mutmut_18, 
        'xǁStructuredJsonFormatterǁformat__mutmut_19': xǁStructuredJsonFormatterǁformat__mutmut_19, 
        'xǁStructuredJsonFormatterǁformat__mutmut_20': xǁStructuredJsonFormatterǁformat__mutmut_20, 
        'xǁStructuredJsonFormatterǁformat__mutmut_21': xǁStructuredJsonFormatterǁformat__mutmut_21, 
        'xǁStructuredJsonFormatterǁformat__mutmut_22': xǁStructuredJsonFormatterǁformat__mutmut_22, 
        'xǁStructuredJsonFormatterǁformat__mutmut_23': xǁStructuredJsonFormatterǁformat__mutmut_23, 
        'xǁStructuredJsonFormatterǁformat__mutmut_24': xǁStructuredJsonFormatterǁformat__mutmut_24, 
        'xǁStructuredJsonFormatterǁformat__mutmut_25': xǁStructuredJsonFormatterǁformat__mutmut_25, 
        'xǁStructuredJsonFormatterǁformat__mutmut_26': xǁStructuredJsonFormatterǁformat__mutmut_26, 
        'xǁStructuredJsonFormatterǁformat__mutmut_27': xǁStructuredJsonFormatterǁformat__mutmut_27, 
        'xǁStructuredJsonFormatterǁformat__mutmut_28': xǁStructuredJsonFormatterǁformat__mutmut_28, 
        'xǁStructuredJsonFormatterǁformat__mutmut_29': xǁStructuredJsonFormatterǁformat__mutmut_29, 
        'xǁStructuredJsonFormatterǁformat__mutmut_30': xǁStructuredJsonFormatterǁformat__mutmut_30, 
        'xǁStructuredJsonFormatterǁformat__mutmut_31': xǁStructuredJsonFormatterǁformat__mutmut_31, 
        'xǁStructuredJsonFormatterǁformat__mutmut_32': xǁStructuredJsonFormatterǁformat__mutmut_32, 
        'xǁStructuredJsonFormatterǁformat__mutmut_33': xǁStructuredJsonFormatterǁformat__mutmut_33, 
        'xǁStructuredJsonFormatterǁformat__mutmut_34': xǁStructuredJsonFormatterǁformat__mutmut_34, 
        'xǁStructuredJsonFormatterǁformat__mutmut_35': xǁStructuredJsonFormatterǁformat__mutmut_35, 
        'xǁStructuredJsonFormatterǁformat__mutmut_36': xǁStructuredJsonFormatterǁformat__mutmut_36, 
        'xǁStructuredJsonFormatterǁformat__mutmut_37': xǁStructuredJsonFormatterǁformat__mutmut_37, 
        'xǁStructuredJsonFormatterǁformat__mutmut_38': xǁStructuredJsonFormatterǁformat__mutmut_38, 
        'xǁStructuredJsonFormatterǁformat__mutmut_39': xǁStructuredJsonFormatterǁformat__mutmut_39, 
        'xǁStructuredJsonFormatterǁformat__mutmut_40': xǁStructuredJsonFormatterǁformat__mutmut_40, 
        'xǁStructuredJsonFormatterǁformat__mutmut_41': xǁStructuredJsonFormatterǁformat__mutmut_41, 
        'xǁStructuredJsonFormatterǁformat__mutmut_42': xǁStructuredJsonFormatterǁformat__mutmut_42, 
        'xǁStructuredJsonFormatterǁformat__mutmut_43': xǁStructuredJsonFormatterǁformat__mutmut_43, 
        'xǁStructuredJsonFormatterǁformat__mutmut_44': xǁStructuredJsonFormatterǁformat__mutmut_44, 
        'xǁStructuredJsonFormatterǁformat__mutmut_45': xǁStructuredJsonFormatterǁformat__mutmut_45, 
        'xǁStructuredJsonFormatterǁformat__mutmut_46': xǁStructuredJsonFormatterǁformat__mutmut_46, 
        'xǁStructuredJsonFormatterǁformat__mutmut_47': xǁStructuredJsonFormatterǁformat__mutmut_47, 
        'xǁStructuredJsonFormatterǁformat__mutmut_48': xǁStructuredJsonFormatterǁformat__mutmut_48, 
        'xǁStructuredJsonFormatterǁformat__mutmut_49': xǁStructuredJsonFormatterǁformat__mutmut_49, 
        'xǁStructuredJsonFormatterǁformat__mutmut_50': xǁStructuredJsonFormatterǁformat__mutmut_50, 
        'xǁStructuredJsonFormatterǁformat__mutmut_51': xǁStructuredJsonFormatterǁformat__mutmut_51, 
        'xǁStructuredJsonFormatterǁformat__mutmut_52': xǁStructuredJsonFormatterǁformat__mutmut_52, 
        'xǁStructuredJsonFormatterǁformat__mutmut_53': xǁStructuredJsonFormatterǁformat__mutmut_53, 
        'xǁStructuredJsonFormatterǁformat__mutmut_54': xǁStructuredJsonFormatterǁformat__mutmut_54, 
        'xǁStructuredJsonFormatterǁformat__mutmut_55': xǁStructuredJsonFormatterǁformat__mutmut_55, 
        'xǁStructuredJsonFormatterǁformat__mutmut_56': xǁStructuredJsonFormatterǁformat__mutmut_56, 
        'xǁStructuredJsonFormatterǁformat__mutmut_57': xǁStructuredJsonFormatterǁformat__mutmut_57, 
        'xǁStructuredJsonFormatterǁformat__mutmut_58': xǁStructuredJsonFormatterǁformat__mutmut_58, 
        'xǁStructuredJsonFormatterǁformat__mutmut_59': xǁStructuredJsonFormatterǁformat__mutmut_59, 
        'xǁStructuredJsonFormatterǁformat__mutmut_60': xǁStructuredJsonFormatterǁformat__mutmut_60, 
        'xǁStructuredJsonFormatterǁformat__mutmut_61': xǁStructuredJsonFormatterǁformat__mutmut_61, 
        'xǁStructuredJsonFormatterǁformat__mutmut_62': xǁStructuredJsonFormatterǁformat__mutmut_62, 
        'xǁStructuredJsonFormatterǁformat__mutmut_63': xǁStructuredJsonFormatterǁformat__mutmut_63, 
        'xǁStructuredJsonFormatterǁformat__mutmut_64': xǁStructuredJsonFormatterǁformat__mutmut_64, 
        'xǁStructuredJsonFormatterǁformat__mutmut_65': xǁStructuredJsonFormatterǁformat__mutmut_65, 
        'xǁStructuredJsonFormatterǁformat__mutmut_66': xǁStructuredJsonFormatterǁformat__mutmut_66, 
        'xǁStructuredJsonFormatterǁformat__mutmut_67': xǁStructuredJsonFormatterǁformat__mutmut_67, 
        'xǁStructuredJsonFormatterǁformat__mutmut_68': xǁStructuredJsonFormatterǁformat__mutmut_68, 
        'xǁStructuredJsonFormatterǁformat__mutmut_69': xǁStructuredJsonFormatterǁformat__mutmut_69, 
        'xǁStructuredJsonFormatterǁformat__mutmut_70': xǁStructuredJsonFormatterǁformat__mutmut_70, 
        'xǁStructuredJsonFormatterǁformat__mutmut_71': xǁStructuredJsonFormatterǁformat__mutmut_71, 
        'xǁStructuredJsonFormatterǁformat__mutmut_72': xǁStructuredJsonFormatterǁformat__mutmut_72, 
        'xǁStructuredJsonFormatterǁformat__mutmut_73': xǁStructuredJsonFormatterǁformat__mutmut_73, 
        'xǁStructuredJsonFormatterǁformat__mutmut_74': xǁStructuredJsonFormatterǁformat__mutmut_74, 
        'xǁStructuredJsonFormatterǁformat__mutmut_75': xǁStructuredJsonFormatterǁformat__mutmut_75, 
        'xǁStructuredJsonFormatterǁformat__mutmut_76': xǁStructuredJsonFormatterǁformat__mutmut_76, 
        'xǁStructuredJsonFormatterǁformat__mutmut_77': xǁStructuredJsonFormatterǁformat__mutmut_77, 
        'xǁStructuredJsonFormatterǁformat__mutmut_78': xǁStructuredJsonFormatterǁformat__mutmut_78, 
        'xǁStructuredJsonFormatterǁformat__mutmut_79': xǁStructuredJsonFormatterǁformat__mutmut_79, 
        'xǁStructuredJsonFormatterǁformat__mutmut_80': xǁStructuredJsonFormatterǁformat__mutmut_80, 
        'xǁStructuredJsonFormatterǁformat__mutmut_81': xǁStructuredJsonFormatterǁformat__mutmut_81, 
        'xǁStructuredJsonFormatterǁformat__mutmut_82': xǁStructuredJsonFormatterǁformat__mutmut_82, 
        'xǁStructuredJsonFormatterǁformat__mutmut_83': xǁStructuredJsonFormatterǁformat__mutmut_83, 
        'xǁStructuredJsonFormatterǁformat__mutmut_84': xǁStructuredJsonFormatterǁformat__mutmut_84, 
        'xǁStructuredJsonFormatterǁformat__mutmut_85': xǁStructuredJsonFormatterǁformat__mutmut_85, 
        'xǁStructuredJsonFormatterǁformat__mutmut_86': xǁStructuredJsonFormatterǁformat__mutmut_86, 
        'xǁStructuredJsonFormatterǁformat__mutmut_87': xǁStructuredJsonFormatterǁformat__mutmut_87, 
        'xǁStructuredJsonFormatterǁformat__mutmut_88': xǁStructuredJsonFormatterǁformat__mutmut_88, 
        'xǁStructuredJsonFormatterǁformat__mutmut_89': xǁStructuredJsonFormatterǁformat__mutmut_89, 
        'xǁStructuredJsonFormatterǁformat__mutmut_90': xǁStructuredJsonFormatterǁformat__mutmut_90, 
        'xǁStructuredJsonFormatterǁformat__mutmut_91': xǁStructuredJsonFormatterǁformat__mutmut_91, 
        'xǁStructuredJsonFormatterǁformat__mutmut_92': xǁStructuredJsonFormatterǁformat__mutmut_92, 
        'xǁStructuredJsonFormatterǁformat__mutmut_93': xǁStructuredJsonFormatterǁformat__mutmut_93, 
        'xǁStructuredJsonFormatterǁformat__mutmut_94': xǁStructuredJsonFormatterǁformat__mutmut_94, 
        'xǁStructuredJsonFormatterǁformat__mutmut_95': xǁStructuredJsonFormatterǁformat__mutmut_95, 
        'xǁStructuredJsonFormatterǁformat__mutmut_96': xǁStructuredJsonFormatterǁformat__mutmut_96, 
        'xǁStructuredJsonFormatterǁformat__mutmut_97': xǁStructuredJsonFormatterǁformat__mutmut_97, 
        'xǁStructuredJsonFormatterǁformat__mutmut_98': xǁStructuredJsonFormatterǁformat__mutmut_98, 
        'xǁStructuredJsonFormatterǁformat__mutmut_99': xǁStructuredJsonFormatterǁformat__mutmut_99, 
        'xǁStructuredJsonFormatterǁformat__mutmut_100': xǁStructuredJsonFormatterǁformat__mutmut_100, 
        'xǁStructuredJsonFormatterǁformat__mutmut_101': xǁStructuredJsonFormatterǁformat__mutmut_101, 
        'xǁStructuredJsonFormatterǁformat__mutmut_102': xǁStructuredJsonFormatterǁformat__mutmut_102, 
        'xǁStructuredJsonFormatterǁformat__mutmut_103': xǁStructuredJsonFormatterǁformat__mutmut_103
    }
    
    def format(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁStructuredJsonFormatterǁformat__mutmut_orig"), object.__getattribute__(self, "xǁStructuredJsonFormatterǁformat__mutmut_mutants"), args, kwargs, self)
        return result 
    
    format.__signature__ = _mutmut_signature(xǁStructuredJsonFormatterǁformat__mutmut_orig)
    xǁStructuredJsonFormatterǁformat__mutmut_orig.__name__ = 'xǁStructuredJsonFormatterǁformat'


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive data"""
    
    def xǁSensitiveDataFilterǁfilter__mutmut_orig(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_1(self, record: logging.LogRecord) -> bool:
        record.msg = None
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_2(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(None)
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_3(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(None))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_4(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = None
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_5(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(None)
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_6(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(None))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_7(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = None
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_8(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    None
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_9(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(None) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_10(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(None)) for arg in record.args
                )
        
        return True
    
    def xǁSensitiveDataFilterǁfilter__mutmut_11(self, record: logging.LogRecord) -> bool:
        record.msg = mask_sensitive_data(str(record.msg))
        if record.args:
            if isinstance(record.args, dict):
                for key, value in record.args.items():
                    record.args[key] = mask_sensitive_data(str(value))
            else:
                record.args = tuple(
                    mask_sensitive_data(str(arg)) for arg in record.args
                )
        
        return False
    
    xǁSensitiveDataFilterǁfilter__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁSensitiveDataFilterǁfilter__mutmut_1': xǁSensitiveDataFilterǁfilter__mutmut_1, 
        'xǁSensitiveDataFilterǁfilter__mutmut_2': xǁSensitiveDataFilterǁfilter__mutmut_2, 
        'xǁSensitiveDataFilterǁfilter__mutmut_3': xǁSensitiveDataFilterǁfilter__mutmut_3, 
        'xǁSensitiveDataFilterǁfilter__mutmut_4': xǁSensitiveDataFilterǁfilter__mutmut_4, 
        'xǁSensitiveDataFilterǁfilter__mutmut_5': xǁSensitiveDataFilterǁfilter__mutmut_5, 
        'xǁSensitiveDataFilterǁfilter__mutmut_6': xǁSensitiveDataFilterǁfilter__mutmut_6, 
        'xǁSensitiveDataFilterǁfilter__mutmut_7': xǁSensitiveDataFilterǁfilter__mutmut_7, 
        'xǁSensitiveDataFilterǁfilter__mutmut_8': xǁSensitiveDataFilterǁfilter__mutmut_8, 
        'xǁSensitiveDataFilterǁfilter__mutmut_9': xǁSensitiveDataFilterǁfilter__mutmut_9, 
        'xǁSensitiveDataFilterǁfilter__mutmut_10': xǁSensitiveDataFilterǁfilter__mutmut_10, 
        'xǁSensitiveDataFilterǁfilter__mutmut_11': xǁSensitiveDataFilterǁfilter__mutmut_11
    }
    
    def filter(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁSensitiveDataFilterǁfilter__mutmut_orig"), object.__getattribute__(self, "xǁSensitiveDataFilterǁfilter__mutmut_mutants"), args, kwargs, self)
        return result 
    
    filter.__signature__ = _mutmut_signature(xǁSensitiveDataFilterǁfilter__mutmut_orig)
    xǁSensitiveDataFilterǁfilter__mutmut_orig.__name__ = 'xǁSensitiveDataFilterǁfilter'


def x_setup_logging__mutmut_orig(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_1(
    name: str = "XXx0tta6bl4XX",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_2(
    name: str = "X0TTA6BL4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_3(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = True,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_4(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 515,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_5(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is not None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_6(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = None
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_7(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = None
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_8(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(None)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_9(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(None)
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_10(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(None, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_11(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, None))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_12(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_13(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, ))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_14(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(None)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_15(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(None)
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_16(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = None
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_17(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(None)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_18(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(None)
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_19(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(None, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_20(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, None))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_21(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_22(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, ))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_23(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = None
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_24(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(None)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_25(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(None)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_26(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = None
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_27(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            None,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_28(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=None,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_29(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=None
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_30(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_31(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_32(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_33(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 / 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_34(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 / 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_35(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=101 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_36(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1025 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_37(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1025,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_38(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=11
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_39(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(None)
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_40(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(None, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_41(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, None))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_42(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_43(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, ))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_44(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(None)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_45(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(None)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_46(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote or remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_47(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = None
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_48(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=None
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_49(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(None)
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_50(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(None, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_51(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, None))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_52(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr("WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_53(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, ))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_54(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "XXWARNINGXX"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_55(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "warning"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_56(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = None
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_57(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                None
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_58(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'XXx0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)sXX'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_59(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'X0TTA6BL4[%(PROCESS)D]: %(NAME)S - %(LEVELNAME)S - %(MESSAGE)S'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_60(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(None)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_61(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(None)
        except Exception as e:
            logger.warning(f"Failed to setup remote syslog: {e}")
    
    return logger


def x_setup_logging__mutmut_62(
    name: str = "x0tta6bl4",
    log_level: Optional[str] = None,
    log_file: Optional[str] = None,
    enable_remote: bool = False,
    remote_host: Optional[str] = None,
    remote_port: int = 514,
) -> logging.Logger:
    """
    Setup structured logging with multiple handlers.
    
    Args:
        name: Logger name
        log_level: Log level (INFO, DEBUG, WARNING, ERROR)
        log_file: Path to log file
        enable_remote: Enable remote syslog
        remote_host: Remote syslog host
        remote_port: Remote syslog port
    
    Returns:
        Configured logger instance
    """
    
    if log_level is None:
        log_level = get_log_level()
    
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, log_level))
    
    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Add sensitive data filter
    logger.addFilter(SensitiveDataFilter())
    
    # Console handler (stdout)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, log_level))
    console_formatter = StructuredJsonFormatter()
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)
    
    # File handler if specified
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=100 * 1024 * 1024,
            backupCount=10
        )
        file_handler.setLevel(getattr(logging, log_level))
        file_handler.setFormatter(console_formatter)
        logger.addHandler(file_handler)
    
    # Remote syslog handler if enabled
    if enable_remote and remote_host:
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address=(remote_host, remote_port)
            )
            syslog_handler.setLevel(getattr(logging, "WARNING"))
            syslog_formatter = logging.Formatter(
                'x0tta6bl4[%(process)d]: %(name)s - %(levelname)s - %(message)s'
            )
            syslog_handler.setFormatter(syslog_formatter)
            logger.addHandler(syslog_handler)
        except Exception as e:
            logger.warning(None)
    
    return logger

x_setup_logging__mutmut_mutants : ClassVar[MutantDict] = {
'x_setup_logging__mutmut_1': x_setup_logging__mutmut_1, 
    'x_setup_logging__mutmut_2': x_setup_logging__mutmut_2, 
    'x_setup_logging__mutmut_3': x_setup_logging__mutmut_3, 
    'x_setup_logging__mutmut_4': x_setup_logging__mutmut_4, 
    'x_setup_logging__mutmut_5': x_setup_logging__mutmut_5, 
    'x_setup_logging__mutmut_6': x_setup_logging__mutmut_6, 
    'x_setup_logging__mutmut_7': x_setup_logging__mutmut_7, 
    'x_setup_logging__mutmut_8': x_setup_logging__mutmut_8, 
    'x_setup_logging__mutmut_9': x_setup_logging__mutmut_9, 
    'x_setup_logging__mutmut_10': x_setup_logging__mutmut_10, 
    'x_setup_logging__mutmut_11': x_setup_logging__mutmut_11, 
    'x_setup_logging__mutmut_12': x_setup_logging__mutmut_12, 
    'x_setup_logging__mutmut_13': x_setup_logging__mutmut_13, 
    'x_setup_logging__mutmut_14': x_setup_logging__mutmut_14, 
    'x_setup_logging__mutmut_15': x_setup_logging__mutmut_15, 
    'x_setup_logging__mutmut_16': x_setup_logging__mutmut_16, 
    'x_setup_logging__mutmut_17': x_setup_logging__mutmut_17, 
    'x_setup_logging__mutmut_18': x_setup_logging__mutmut_18, 
    'x_setup_logging__mutmut_19': x_setup_logging__mutmut_19, 
    'x_setup_logging__mutmut_20': x_setup_logging__mutmut_20, 
    'x_setup_logging__mutmut_21': x_setup_logging__mutmut_21, 
    'x_setup_logging__mutmut_22': x_setup_logging__mutmut_22, 
    'x_setup_logging__mutmut_23': x_setup_logging__mutmut_23, 
    'x_setup_logging__mutmut_24': x_setup_logging__mutmut_24, 
    'x_setup_logging__mutmut_25': x_setup_logging__mutmut_25, 
    'x_setup_logging__mutmut_26': x_setup_logging__mutmut_26, 
    'x_setup_logging__mutmut_27': x_setup_logging__mutmut_27, 
    'x_setup_logging__mutmut_28': x_setup_logging__mutmut_28, 
    'x_setup_logging__mutmut_29': x_setup_logging__mutmut_29, 
    'x_setup_logging__mutmut_30': x_setup_logging__mutmut_30, 
    'x_setup_logging__mutmut_31': x_setup_logging__mutmut_31, 
    'x_setup_logging__mutmut_32': x_setup_logging__mutmut_32, 
    'x_setup_logging__mutmut_33': x_setup_logging__mutmut_33, 
    'x_setup_logging__mutmut_34': x_setup_logging__mutmut_34, 
    'x_setup_logging__mutmut_35': x_setup_logging__mutmut_35, 
    'x_setup_logging__mutmut_36': x_setup_logging__mutmut_36, 
    'x_setup_logging__mutmut_37': x_setup_logging__mutmut_37, 
    'x_setup_logging__mutmut_38': x_setup_logging__mutmut_38, 
    'x_setup_logging__mutmut_39': x_setup_logging__mutmut_39, 
    'x_setup_logging__mutmut_40': x_setup_logging__mutmut_40, 
    'x_setup_logging__mutmut_41': x_setup_logging__mutmut_41, 
    'x_setup_logging__mutmut_42': x_setup_logging__mutmut_42, 
    'x_setup_logging__mutmut_43': x_setup_logging__mutmut_43, 
    'x_setup_logging__mutmut_44': x_setup_logging__mutmut_44, 
    'x_setup_logging__mutmut_45': x_setup_logging__mutmut_45, 
    'x_setup_logging__mutmut_46': x_setup_logging__mutmut_46, 
    'x_setup_logging__mutmut_47': x_setup_logging__mutmut_47, 
    'x_setup_logging__mutmut_48': x_setup_logging__mutmut_48, 
    'x_setup_logging__mutmut_49': x_setup_logging__mutmut_49, 
    'x_setup_logging__mutmut_50': x_setup_logging__mutmut_50, 
    'x_setup_logging__mutmut_51': x_setup_logging__mutmut_51, 
    'x_setup_logging__mutmut_52': x_setup_logging__mutmut_52, 
    'x_setup_logging__mutmut_53': x_setup_logging__mutmut_53, 
    'x_setup_logging__mutmut_54': x_setup_logging__mutmut_54, 
    'x_setup_logging__mutmut_55': x_setup_logging__mutmut_55, 
    'x_setup_logging__mutmut_56': x_setup_logging__mutmut_56, 
    'x_setup_logging__mutmut_57': x_setup_logging__mutmut_57, 
    'x_setup_logging__mutmut_58': x_setup_logging__mutmut_58, 
    'x_setup_logging__mutmut_59': x_setup_logging__mutmut_59, 
    'x_setup_logging__mutmut_60': x_setup_logging__mutmut_60, 
    'x_setup_logging__mutmut_61': x_setup_logging__mutmut_61, 
    'x_setup_logging__mutmut_62': x_setup_logging__mutmut_62
}

def setup_logging(*args, **kwargs):
    result = _mutmut_trampoline(x_setup_logging__mutmut_orig, x_setup_logging__mutmut_mutants, args, kwargs)
    return result 

setup_logging.__signature__ = _mutmut_signature(x_setup_logging__mutmut_orig)
x_setup_logging__mutmut_orig.__name__ = 'x_setup_logging'


def x_setup_structlog__mutmut_orig():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_1():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=None,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_2():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=None,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_3():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=None,
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_4():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=None,
    )


def x_setup_structlog__mutmut_5():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_6():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_7():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_8():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        )


def x_setup_structlog__mutmut_9():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt=None),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_10():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="XXisoXX"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_11():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="ISO"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def x_setup_structlog__mutmut_12():
    """Setup structlog for structured logging"""
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=False,
    )

x_setup_structlog__mutmut_mutants : ClassVar[MutantDict] = {
'x_setup_structlog__mutmut_1': x_setup_structlog__mutmut_1, 
    'x_setup_structlog__mutmut_2': x_setup_structlog__mutmut_2, 
    'x_setup_structlog__mutmut_3': x_setup_structlog__mutmut_3, 
    'x_setup_structlog__mutmut_4': x_setup_structlog__mutmut_4, 
    'x_setup_structlog__mutmut_5': x_setup_structlog__mutmut_5, 
    'x_setup_structlog__mutmut_6': x_setup_structlog__mutmut_6, 
    'x_setup_structlog__mutmut_7': x_setup_structlog__mutmut_7, 
    'x_setup_structlog__mutmut_8': x_setup_structlog__mutmut_8, 
    'x_setup_structlog__mutmut_9': x_setup_structlog__mutmut_9, 
    'x_setup_structlog__mutmut_10': x_setup_structlog__mutmut_10, 
    'x_setup_structlog__mutmut_11': x_setup_structlog__mutmut_11, 
    'x_setup_structlog__mutmut_12': x_setup_structlog__mutmut_12
}

def setup_structlog(*args, **kwargs):
    result = _mutmut_trampoline(x_setup_structlog__mutmut_orig, x_setup_structlog__mutmut_mutants, args, kwargs)
    return result 

setup_structlog.__signature__ = _mutmut_signature(x_setup_structlog__mutmut_orig)
x_setup_structlog__mutmut_orig.__name__ = 'x_setup_structlog'


def x_get_logger__mutmut_orig(name: str) -> logging.Logger:
    """Get configured logger instance"""
    return logging.getLogger(name)


def x_get_logger__mutmut_1(name: str) -> logging.Logger:
    """Get configured logger instance"""
    return logging.getLogger(None)

x_get_logger__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_logger__mutmut_1': x_get_logger__mutmut_1
}

def get_logger(*args, **kwargs):
    result = _mutmut_trampoline(x_get_logger__mutmut_orig, x_get_logger__mutmut_mutants, args, kwargs)
    return result 

get_logger.__signature__ = _mutmut_signature(x_get_logger__mutmut_orig)
x_get_logger__mutmut_orig.__name__ = 'x_get_logger'


class RequestIdContextVar:
    """Store request ID in logging context"""
    
    _context = {}
    
    @classmethod
    def set(cls, request_id: str):
        """Set request ID for current context"""
        cls._context[id(cls)] = request_id
    
    @classmethod
    def get(cls) -> Optional[str]:
        """Get request ID from current context"""
        return cls._context.get(id(cls))
    
    @classmethod
    def clear(cls):
        """Clear request ID from context"""
        cls._context.pop(id(cls), None)


class LoggingMiddleware:
    """ASGI middleware for structured request/response logging"""
    
    def xǁLoggingMiddlewareǁ__init____mutmut_orig(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = logger or get_logger("x0tta6bl4.http")
    
    def xǁLoggingMiddlewareǁ__init____mutmut_1(self, app, logger: Optional[logging.Logger] = None):
        self.app = None
        self.logger = logger or get_logger("x0tta6bl4.http")
    
    def xǁLoggingMiddlewareǁ__init____mutmut_2(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = None
    
    def xǁLoggingMiddlewareǁ__init____mutmut_3(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = logger and get_logger("x0tta6bl4.http")
    
    def xǁLoggingMiddlewareǁ__init____mutmut_4(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = logger or get_logger(None)
    
    def xǁLoggingMiddlewareǁ__init____mutmut_5(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = logger or get_logger("XXx0tta6bl4.httpXX")
    
    def xǁLoggingMiddlewareǁ__init____mutmut_6(self, app, logger: Optional[logging.Logger] = None):
        self.app = app
        self.logger = logger or get_logger("X0TTA6BL4.HTTP")
    
    xǁLoggingMiddlewareǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁLoggingMiddlewareǁ__init____mutmut_1': xǁLoggingMiddlewareǁ__init____mutmut_1, 
        'xǁLoggingMiddlewareǁ__init____mutmut_2': xǁLoggingMiddlewareǁ__init____mutmut_2, 
        'xǁLoggingMiddlewareǁ__init____mutmut_3': xǁLoggingMiddlewareǁ__init____mutmut_3, 
        'xǁLoggingMiddlewareǁ__init____mutmut_4': xǁLoggingMiddlewareǁ__init____mutmut_4, 
        'xǁLoggingMiddlewareǁ__init____mutmut_5': xǁLoggingMiddlewareǁ__init____mutmut_5, 
        'xǁLoggingMiddlewareǁ__init____mutmut_6': xǁLoggingMiddlewareǁ__init____mutmut_6
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁLoggingMiddlewareǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁLoggingMiddlewareǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁLoggingMiddlewareǁ__init____mutmut_orig)
    xǁLoggingMiddlewareǁ__init____mutmut_orig.__name__ = 'xǁLoggingMiddlewareǁ__init__'
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_orig(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_1(self, scope, receive, send):
        if scope["XXtypeXX"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_2(self, scope, receive, send):
        if scope["TYPE"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_3(self, scope, receive, send):
        if scope["type"] == "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_4(self, scope, receive, send):
        if scope["type"] != "XXhttpXX":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_5(self, scope, receive, send):
        if scope["type"] != "HTTP":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_6(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(None, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_7(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, None, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_8(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, None)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_9(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_10(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_11(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, )
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_12(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = None
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_13(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(None)
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_14(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(None)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_15(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = None
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_16(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get(None, "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_17(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", None)
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_18(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_19(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", )
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_20(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("XXpathXX", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_21(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("PATH", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_22(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "XXXX")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_23(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = None
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_24(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get(None, "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_25(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", None)
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_26(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_27(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", )
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_28(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("XXmethodXX", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_29(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("METHOD", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_30(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "XXXX")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_31(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = None
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_32(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = None
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_33(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 201
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_34(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["XXtypeXX"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_35(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["TYPE"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_36(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] != "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_37(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "XXhttp.response.startXX":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_38(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "HTTP.RESPONSE.START":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_39(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = None
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_40(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["XXstatusXX"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_41(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["STATUS"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_42(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(None)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_43(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(None, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_44(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, None, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_45(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, None)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_46(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_47(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_48(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, )
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_49(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = None
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_50(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 501
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_51(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = None
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_52(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) / 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_53(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() + start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_54(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1001
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_55(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                None,
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_56(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra=None
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_57(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_58(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_59(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "XXrequest_idXX": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_60(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "REQUEST_ID": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_61(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "XXmethodXX": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_62(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "METHOD": method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_63(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "XXpathXX": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_64(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "PATH": path,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_65(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "XXstatus_codeXX": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_66(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "STATUS_CODE": status_code,
                    "duration_ms": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_67(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "XXduration_msXX": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    async def xǁLoggingMiddlewareǁ__call____mutmut_68(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        import uuid
        import time
        
        request_id = str(uuid.uuid4())
        RequestIdContextVar.set(request_id)
        
        path = scope.get("path", "")
        method = scope.get("method", "")
        
        start_time = time.time()
        status_code = 200
        
        async def send_wrapper(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        
        except Exception as e:
            status_code = 500
            raise
        
        finally:
            duration_ms = (time.time() - start_time) * 1000
            
            self.logger.info(
                f"{method} {path}",
                extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "status_code": status_code,
                    "DURATION_MS": duration_ms,
                }
            )
            
            RequestIdContextVar.clear()
    
    xǁLoggingMiddlewareǁ__call____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁLoggingMiddlewareǁ__call____mutmut_1': xǁLoggingMiddlewareǁ__call____mutmut_1, 
        'xǁLoggingMiddlewareǁ__call____mutmut_2': xǁLoggingMiddlewareǁ__call____mutmut_2, 
        'xǁLoggingMiddlewareǁ__call____mutmut_3': xǁLoggingMiddlewareǁ__call____mutmut_3, 
        'xǁLoggingMiddlewareǁ__call____mutmut_4': xǁLoggingMiddlewareǁ__call____mutmut_4, 
        'xǁLoggingMiddlewareǁ__call____mutmut_5': xǁLoggingMiddlewareǁ__call____mutmut_5, 
        'xǁLoggingMiddlewareǁ__call____mutmut_6': xǁLoggingMiddlewareǁ__call____mutmut_6, 
        'xǁLoggingMiddlewareǁ__call____mutmut_7': xǁLoggingMiddlewareǁ__call____mutmut_7, 
        'xǁLoggingMiddlewareǁ__call____mutmut_8': xǁLoggingMiddlewareǁ__call____mutmut_8, 
        'xǁLoggingMiddlewareǁ__call____mutmut_9': xǁLoggingMiddlewareǁ__call____mutmut_9, 
        'xǁLoggingMiddlewareǁ__call____mutmut_10': xǁLoggingMiddlewareǁ__call____mutmut_10, 
        'xǁLoggingMiddlewareǁ__call____mutmut_11': xǁLoggingMiddlewareǁ__call____mutmut_11, 
        'xǁLoggingMiddlewareǁ__call____mutmut_12': xǁLoggingMiddlewareǁ__call____mutmut_12, 
        'xǁLoggingMiddlewareǁ__call____mutmut_13': xǁLoggingMiddlewareǁ__call____mutmut_13, 
        'xǁLoggingMiddlewareǁ__call____mutmut_14': xǁLoggingMiddlewareǁ__call____mutmut_14, 
        'xǁLoggingMiddlewareǁ__call____mutmut_15': xǁLoggingMiddlewareǁ__call____mutmut_15, 
        'xǁLoggingMiddlewareǁ__call____mutmut_16': xǁLoggingMiddlewareǁ__call____mutmut_16, 
        'xǁLoggingMiddlewareǁ__call____mutmut_17': xǁLoggingMiddlewareǁ__call____mutmut_17, 
        'xǁLoggingMiddlewareǁ__call____mutmut_18': xǁLoggingMiddlewareǁ__call____mutmut_18, 
        'xǁLoggingMiddlewareǁ__call____mutmut_19': xǁLoggingMiddlewareǁ__call____mutmut_19, 
        'xǁLoggingMiddlewareǁ__call____mutmut_20': xǁLoggingMiddlewareǁ__call____mutmut_20, 
        'xǁLoggingMiddlewareǁ__call____mutmut_21': xǁLoggingMiddlewareǁ__call____mutmut_21, 
        'xǁLoggingMiddlewareǁ__call____mutmut_22': xǁLoggingMiddlewareǁ__call____mutmut_22, 
        'xǁLoggingMiddlewareǁ__call____mutmut_23': xǁLoggingMiddlewareǁ__call____mutmut_23, 
        'xǁLoggingMiddlewareǁ__call____mutmut_24': xǁLoggingMiddlewareǁ__call____mutmut_24, 
        'xǁLoggingMiddlewareǁ__call____mutmut_25': xǁLoggingMiddlewareǁ__call____mutmut_25, 
        'xǁLoggingMiddlewareǁ__call____mutmut_26': xǁLoggingMiddlewareǁ__call____mutmut_26, 
        'xǁLoggingMiddlewareǁ__call____mutmut_27': xǁLoggingMiddlewareǁ__call____mutmut_27, 
        'xǁLoggingMiddlewareǁ__call____mutmut_28': xǁLoggingMiddlewareǁ__call____mutmut_28, 
        'xǁLoggingMiddlewareǁ__call____mutmut_29': xǁLoggingMiddlewareǁ__call____mutmut_29, 
        'xǁLoggingMiddlewareǁ__call____mutmut_30': xǁLoggingMiddlewareǁ__call____mutmut_30, 
        'xǁLoggingMiddlewareǁ__call____mutmut_31': xǁLoggingMiddlewareǁ__call____mutmut_31, 
        'xǁLoggingMiddlewareǁ__call____mutmut_32': xǁLoggingMiddlewareǁ__call____mutmut_32, 
        'xǁLoggingMiddlewareǁ__call____mutmut_33': xǁLoggingMiddlewareǁ__call____mutmut_33, 
        'xǁLoggingMiddlewareǁ__call____mutmut_34': xǁLoggingMiddlewareǁ__call____mutmut_34, 
        'xǁLoggingMiddlewareǁ__call____mutmut_35': xǁLoggingMiddlewareǁ__call____mutmut_35, 
        'xǁLoggingMiddlewareǁ__call____mutmut_36': xǁLoggingMiddlewareǁ__call____mutmut_36, 
        'xǁLoggingMiddlewareǁ__call____mutmut_37': xǁLoggingMiddlewareǁ__call____mutmut_37, 
        'xǁLoggingMiddlewareǁ__call____mutmut_38': xǁLoggingMiddlewareǁ__call____mutmut_38, 
        'xǁLoggingMiddlewareǁ__call____mutmut_39': xǁLoggingMiddlewareǁ__call____mutmut_39, 
        'xǁLoggingMiddlewareǁ__call____mutmut_40': xǁLoggingMiddlewareǁ__call____mutmut_40, 
        'xǁLoggingMiddlewareǁ__call____mutmut_41': xǁLoggingMiddlewareǁ__call____mutmut_41, 
        'xǁLoggingMiddlewareǁ__call____mutmut_42': xǁLoggingMiddlewareǁ__call____mutmut_42, 
        'xǁLoggingMiddlewareǁ__call____mutmut_43': xǁLoggingMiddlewareǁ__call____mutmut_43, 
        'xǁLoggingMiddlewareǁ__call____mutmut_44': xǁLoggingMiddlewareǁ__call____mutmut_44, 
        'xǁLoggingMiddlewareǁ__call____mutmut_45': xǁLoggingMiddlewareǁ__call____mutmut_45, 
        'xǁLoggingMiddlewareǁ__call____mutmut_46': xǁLoggingMiddlewareǁ__call____mutmut_46, 
        'xǁLoggingMiddlewareǁ__call____mutmut_47': xǁLoggingMiddlewareǁ__call____mutmut_47, 
        'xǁLoggingMiddlewareǁ__call____mutmut_48': xǁLoggingMiddlewareǁ__call____mutmut_48, 
        'xǁLoggingMiddlewareǁ__call____mutmut_49': xǁLoggingMiddlewareǁ__call____mutmut_49, 
        'xǁLoggingMiddlewareǁ__call____mutmut_50': xǁLoggingMiddlewareǁ__call____mutmut_50, 
        'xǁLoggingMiddlewareǁ__call____mutmut_51': xǁLoggingMiddlewareǁ__call____mutmut_51, 
        'xǁLoggingMiddlewareǁ__call____mutmut_52': xǁLoggingMiddlewareǁ__call____mutmut_52, 
        'xǁLoggingMiddlewareǁ__call____mutmut_53': xǁLoggingMiddlewareǁ__call____mutmut_53, 
        'xǁLoggingMiddlewareǁ__call____mutmut_54': xǁLoggingMiddlewareǁ__call____mutmut_54, 
        'xǁLoggingMiddlewareǁ__call____mutmut_55': xǁLoggingMiddlewareǁ__call____mutmut_55, 
        'xǁLoggingMiddlewareǁ__call____mutmut_56': xǁLoggingMiddlewareǁ__call____mutmut_56, 
        'xǁLoggingMiddlewareǁ__call____mutmut_57': xǁLoggingMiddlewareǁ__call____mutmut_57, 
        'xǁLoggingMiddlewareǁ__call____mutmut_58': xǁLoggingMiddlewareǁ__call____mutmut_58, 
        'xǁLoggingMiddlewareǁ__call____mutmut_59': xǁLoggingMiddlewareǁ__call____mutmut_59, 
        'xǁLoggingMiddlewareǁ__call____mutmut_60': xǁLoggingMiddlewareǁ__call____mutmut_60, 
        'xǁLoggingMiddlewareǁ__call____mutmut_61': xǁLoggingMiddlewareǁ__call____mutmut_61, 
        'xǁLoggingMiddlewareǁ__call____mutmut_62': xǁLoggingMiddlewareǁ__call____mutmut_62, 
        'xǁLoggingMiddlewareǁ__call____mutmut_63': xǁLoggingMiddlewareǁ__call____mutmut_63, 
        'xǁLoggingMiddlewareǁ__call____mutmut_64': xǁLoggingMiddlewareǁ__call____mutmut_64, 
        'xǁLoggingMiddlewareǁ__call____mutmut_65': xǁLoggingMiddlewareǁ__call____mutmut_65, 
        'xǁLoggingMiddlewareǁ__call____mutmut_66': xǁLoggingMiddlewareǁ__call____mutmut_66, 
        'xǁLoggingMiddlewareǁ__call____mutmut_67': xǁLoggingMiddlewareǁ__call____mutmut_67, 
        'xǁLoggingMiddlewareǁ__call____mutmut_68': xǁLoggingMiddlewareǁ__call____mutmut_68
    }
    
    def __call__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁLoggingMiddlewareǁ__call____mutmut_orig"), object.__getattribute__(self, "xǁLoggingMiddlewareǁ__call____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __call__.__signature__ = _mutmut_signature(xǁLoggingMiddlewareǁ__call____mutmut_orig)
    xǁLoggingMiddlewareǁ__call____mutmut_orig.__name__ = 'xǁLoggingMiddlewareǁ__call__'


# Application startup
if __name__ == "__main__":
    setup_structlog()
    logger = setup_logging("x0tta6bl4", log_file="/var/log/x0tta6bl4/app.log")
    
    logger.info("Logging configured")
    logger.debug("Debug message")
    logger.warning("Password=secret123 should be masked")
    logger.error("Error with token=abc123def456")
