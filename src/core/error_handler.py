"""
Unified Error Handler Framework for x0tta6bl4.

Provides consistent error handling, logging, and alerting across all modules.
"""

import logging
import traceback
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime

logger = logging.getLogger(__name__)

# Optional alerting
try:
    from src.monitoring.alerting import send_alert, AlertSeverity, AlertManager
    ALERTING_AVAILABLE = True
except ImportError:
    ALERTING_AVAILABLE = False
    AlertManager = None  # type: ignore

# Prometheus metrics - create once at module level
_error_counter = None
try:
    from prometheus_client import Counter, REGISTRY
    # Check if metric already exists
    if 'x0tta6bl4_errors_total' not in [c.describe()[0].name for c in REGISTRY._names_to_collectors.values() if hasattr(c, 'describe')]:
        _error_counter = Counter(
            'x0tta6bl4_errors',
            'Total number of errors',
            ['error_type', 'context', 'severity']
        )
    else:
        # Get existing counter
        for collector in REGISTRY._names_to_collectors.values():
            if hasattr(collector, 'describe'):
                for desc in collector.describe():
                    if desc.name == 'x0tta6bl4_errors_total':
                        _error_counter = collector
                        break
except ImportError:
    pass  # Prometheus not available
except Exception:
    pass  # Registry issues


class ErrorSeverity(Enum):
    """Error severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorHandler:
    """
    Unified error handling framework.
    
    Provides:
    - Structured logging
    - Automatic alerting for critical errors
    - Error metrics
    - Consistent error format
    """
    
    @staticmethod
    async def handle_error(
        error: Exception,
        context: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Handle error with consistent logging and alerting.
        
        Args:
            error: Exception that occurred
            context: Context where error occurred (e.g., "mesh_router.start")
            severity: Error severity level
            additional_data: Additional data to include in logs
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        # Structured logging
        log_data = {
            "error_type": error_type,
            "error_message": error_message,
            "severity": severity.value,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            **(additional_data or {})
        }
        
        # Log based on severity
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(
                f"🚨 CRITICAL ERROR in {context}: {error_type}: {error_message}",
                extra=log_data,
                exc_info=True
            )
        elif severity == ErrorSeverity.HIGH:
            logger.error(
                f"❌ HIGH ERROR in {context}: {error_type}: {error_message}",
                extra=log_data,
                exc_info=True
            )
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(
                f"⚠️ MEDIUM ERROR in {context}: {error_type}: {error_message}",
                extra=log_data
            )
        elif severity == ErrorSeverity.LOW:
            logger.info(
                f"ℹ️ LOW ERROR in {context}: {error_type}: {error_message}",
                extra=log_data
            )
        else:
            logger.debug(
                f"🔍 ERROR in {context}: {error_type}: {error_message}",
                extra=log_data
            )
        
        # Alert for critical/high errors - Full integration with AlertManager
        if ALERTING_AVAILABLE and severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            try:
                alert_severity = AlertSeverity.CRITICAL if severity == ErrorSeverity.CRITICAL else AlertSeverity.ERROR
                
                # Use async send_alert function
                await send_alert(
                    f"ERROR_{context.upper().replace('.', '_')}",
                    alert_severity,
                    f"Error in {context}: {error_type}: {error_message}",
                    labels={
                        "error_type": error_type,
                        "context": context,
                        "severity": severity.value
                    },
                    annotations={
                        "error_message": error_message,
                        "traceback": traceback.format_exc()[-500:] if severity == ErrorSeverity.CRITICAL else None,
                        "additional_data": str(additional_data) if additional_data else None
                    },
                    skip_rate_limit=(severity == ErrorSeverity.CRITICAL)  # Skip rate limit for critical errors
                )
            except Exception as e:
                logger.warning(f"Failed to send alert: {e}")
        
        # Update error metrics (if Prometheus available)
        if _error_counter is not None:
            try:
                _error_counter.labels(
                    error_type=error_type,
                    context=context,
                    severity=severity.value
                ).inc()
            except Exception:
                pass  # Metric update failed

    @staticmethod
    def handle_error_sync(
        error: Exception,
        context: str,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        additional_data: Optional[Dict[str, Any]] = None
    ):
        """
        Synchronous version of handle_error.
        
        For use in non-async contexts.
        """
        error_type = type(error).__name__
        error_message = str(error)
        
        log_data = {
            "error_type": error_type,
            "error_message": error_message,
            "severity": severity.value,
            "context": context,
            "timestamp": datetime.now().isoformat(),
            **(additional_data or {})
        }
        
        if severity == ErrorSeverity.CRITICAL:
            logger.critical(
                f"🚨 CRITICAL ERROR in {context}: {error_type}: {error_message}",
                extra=log_data,
                exc_info=True
            )
        elif severity == ErrorSeverity.HIGH:
            logger.error(
                f"❌ HIGH ERROR in {context}: {error_type}: {error_message}",
                extra=log_data,
                exc_info=True
            )
        elif severity == ErrorSeverity.MEDIUM:
            logger.warning(
                f"⚠️ MEDIUM ERROR in {context}: {error_type}: {error_message}",
                extra=log_data
            )
        elif severity == ErrorSeverity.LOW:
            logger.info(
                f"ℹ️ LOW ERROR in {context}: {error_type}: {error_message}",
                extra=log_data
            )
        else:
            logger.debug(
                f"🔍 ERROR in {context}: {error_type}: {error_message}",
                extra=log_data
            )
        
        # Alert for critical/high errors - Full integration with AlertManager (sync version)
        if ALERTING_AVAILABLE and severity in [ErrorSeverity.CRITICAL, ErrorSeverity.HIGH]:
            try:
                import asyncio

                # Get or create AlertManager instance
                alert_manager = getattr(ErrorHandler.handle_error_sync, '_alert_manager', None)
                if alert_manager is None and AlertManager is not None:
                    alert_manager = AlertManager()
                    ErrorHandler.handle_error_sync._alert_manager = alert_manager

                if alert_manager is None:
                    raise ValueError("AlertManager not available")

                alert_severity = AlertSeverity.CRITICAL if severity == ErrorSeverity.CRITICAL else AlertSeverity.ERROR
                
                # Run async alert in sync context
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        # If loop is running, schedule as task
                        asyncio.create_task(alert_manager.send_alert(
                            f"ERROR_{context.upper().replace('.', '_')}",
                            alert_severity,
                            f"Error in {context}: {error_type}: {error_message}",
                            labels={
                                "error_type": error_type,
                                "context": context,
                                "severity": severity.value
                            },
                            annotations={
                                "error_message": error_message,
                                "traceback": traceback.format_exc()[-500:] if severity == ErrorSeverity.CRITICAL else None,
                                "additional_data": str(additional_data) if additional_data else None
                            }
                        ))
                    else:
                        # If no loop, run it
                        loop.run_until_complete(alert_manager.send_alert(
                            f"ERROR_{context.upper().replace('.', '_')}",
                            alert_severity,
                            f"Error in {context}: {error_type}: {error_message}",
                            labels={
                                "error_type": error_type,
                                "context": context,
                                "severity": severity.value
                            },
                            annotations={
                                "error_message": error_message,
                                "traceback": traceback.format_exc()[-500:] if severity == ErrorSeverity.CRITICAL else None,
                                "additional_data": str(additional_data) if additional_data else None
                            }
                        ))
                except RuntimeError:
                    # No event loop, create new one
                    asyncio.run(alert_manager.send_alert(
                        f"ERROR_{context.upper().replace('.', '_')}",
                        alert_severity,
                        f"Error in {context}: {error_type}: {error_message}",
                        labels={
                            "error_type": error_type,
                            "context": context,
                            "severity": severity.value
                        },
                        annotations={
                            "error_message": error_message,
                            "traceback": traceback.format_exc()[-500:] if severity == ErrorSeverity.CRITICAL else None,
                            "additional_data": str(additional_data) if additional_data else None
                        }
                    ))
            except Exception as e:
                logger.warning(f"Failed to send alert: {e}")

        # Update error metrics (if Prometheus available)
        if _error_counter is not None:
            try:
                _error_counter.labels(
                    error_type=error_type,
                    context=context,
                    severity=severity.value
                ).inc()
            except Exception:
                pass  # Metric update failed


def handle_error_decorator(context: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
    """
    Decorator for automatic error handling.
    
    Usage:
        @handle_error_decorator("my_function", ErrorSeverity.HIGH)
        async def my_function():
            ...
    """
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                await ErrorHandler.handle_error(e, context, severity)
                raise
        
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                ErrorHandler.handle_error_sync(e, context, severity)
                raise
        
        if hasattr(func, '__code__') and func.__code__.co_flags & 0x80:  # CO_COROUTINE
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

