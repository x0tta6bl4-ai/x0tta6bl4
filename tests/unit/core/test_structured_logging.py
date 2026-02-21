"""
Unit tests for structured logging module.
"""

import json
import logging
import pytest
from io import StringIO
from unittest.mock import patch, MagicMock

from src.core.structured_logging import (
    StructuredFormatter,
    StructuredLogger,
    mask_sensitive,
    set_trace_context,
    generate_trace_id,
    generate_span_id,
    get_logger,
    timed,
    LogContext,
    configure_logging,
    SENSITIVE_FIELDS,
    MASK,
)


class TestMaskSensitive:
    """Tests for sensitive data masking."""
    
    def test_mask_password(self):
        """Test password is masked."""
        data = {"password": "secret123"}
        result = mask_sensitive(data)
        assert result["password"] == MASK
    
    def test_mask_api_key(self):
        """Test API key is masked."""
        data = {"api_key": "sk-1234567890"}
        result = mask_sensitive(data)
        assert result["api_key"] == MASK
    
    def test_mask_nested(self):
        """Test nested sensitive data is masked."""
        data = {
            "user": {
                "name": "John",
                "password": "secret",
                "credentials": {
                    "token": "abc123",
                }
            }
        }
        result = mask_sensitive(data)
        assert result["user"]["name"] == "John"
        assert result["user"]["password"] == MASK
        assert result["user"]["credentials"]["token"] == MASK
    
    def test_mask_list(self):
        """Test list items are processed."""
        data = {
            "users": [
                {"name": "Alice", "password": "pass1"},
                {"name": "Bob", "password": "pass2"},
            ]
        }
        result = mask_sensitive(data)
        assert result["users"][0]["password"] == MASK
        assert result["users"][1]["password"] == MASK
    
    def test_no_mask_regular_fields(self):
        """Test regular fields are not masked."""
        data = {"username": "alice", "email": "alice@example.com"}
        result = mask_sensitive(data)
        assert result["username"] == "alice"
        assert result["email"] == "alice@example.com"
    
    def test_max_depth(self):
        """Test max recursion depth is respected."""
        data = {"level1": {"level2": {"level3": {"level4": {"level5": {"level6": {"level7": {"level8": {"level9": {"level10": {"level11": "deep"}}}}}}}}}}}
        result = mask_sensitive(data)
        # Should not raise, just stop recursing
        assert "level1" in result


class TestStructuredFormatter:
    """Tests for JSON log formatter."""
    
    def test_format_basic(self):
        """Test basic log formatting."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        
        result = formatter.format(record)
        log_entry = json.loads(result)
        
        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test"
        assert log_entry["message"] == "Test message"
        assert log_entry["line"] == 42
        assert "timestamp" in log_entry
    
    def test_format_with_extra(self):
        """Test log with extra fields."""
        formatter = StructuredFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.custom_field = "custom_value"
        record.password = "secret"
        
        result = formatter.format(record)
        log_entry = json.loads(result)
        
        assert log_entry["extra"]["custom_field"] == "custom_value"
        assert log_entry["extra"]["password"] == MASK
    
    def test_format_with_exception(self):
        """Test log with exception info."""
        formatter = StructuredFormatter()
        
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys
            exc_info = sys.exc_info()
        
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        
        result = formatter.format(record)
        log_entry = json.loads(result)
        
        assert "exception" in log_entry
        assert log_entry["exception"]["type"] == "ValueError"
        assert log_entry["exception"]["message"] == "Test error"
        assert "stacktrace" in log_entry["exception"]
    
    def test_format_with_trace_context(self):
        """Test log with trace context."""
        import src.core.structured_logging as sl_module
        sl_module.trace_id_var.set("trace-123")
        sl_module.span_id_var.set("span-456")
        
        try:
            formatter = StructuredFormatter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=42,
                msg="Test message",
                args=(),
                exc_info=None,
            )
            
            result = formatter.format(record)
            log_entry = json.loads(result)
            
            assert log_entry["trace_id"] == "trace-123"
            assert log_entry["span_id"] == "span-456"
        finally:
            sl_module.trace_id_var.set(None)
            sl_module.span_id_var.set(None)


class TestStructuredLogger:
    """Tests for StructuredLogger class."""
    
    def test_info_log(self, capsys):
        """Test info level logging."""
        logger = get_logger("test_info")
        logger.info("Test info message", extra={"key": "value"})
        
        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())
        
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test info message"
        assert log_entry["extra"]["key"] == "value"
    
    def test_error_with_exception(self, capsys):
        """Test error logging with exception."""
        logger = get_logger("test_error")
        
        try:
            raise RuntimeError("Test error")
        except RuntimeError:
            logger.exception("Caught exception")
        
        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())
        
        assert log_entry["level"] == "ERROR"
        assert "exception" in log_entry
        assert log_entry["exception"]["type"] == "RuntimeError"


class TestTraceContext:
    """Tests for trace context management."""
    
    def test_generate_trace_id(self):
        """Test trace ID generation."""
        trace_id = generate_trace_id()
        assert len(trace_id) == 32  # UUID4 without dashes
        assert all(c in "0123456789abcdef" for c in trace_id)
    
    def test_generate_span_id(self):
        """Test span ID generation."""
        span_id = generate_span_id()
        assert len(span_id) == 16
        assert all(c in "0123456789abcdef" for c in span_id)
    
    def test_set_trace_context(self):
        """Test setting trace context."""
        import src.core.structured_logging as sl_module
        
        previous = set_trace_context(
            trace_id="test-trace",
            span_id="test-span",
            node_id="test-node",
        )
        
        assert sl_module.trace_id_var.get() == "test-trace"
        assert sl_module.span_id_var.get() == "test-span"
        assert sl_module.node_id_var.get() == "test-node"
        
        # Restore
        set_trace_context(**previous)


class TestLogContext:
    """Tests for LogContext context manager."""
    
    def test_log_context(self):
        """Test LogContext sets and restores context."""
        import src.core.structured_logging as sl_module
        
        # Set initial context
        sl_module.trace_id_var.set("initial-trace")
        
        with LogContext(trace_id="new-trace", node_id="node-1"):
            assert sl_module.trace_id_var.get() == "new-trace"
            assert sl_module.node_id_var.get() == "node-1"
        
        # Context should be restored
        assert sl_module.trace_id_var.get() == "initial-trace"
        assert sl_module.node_id_var.get() is None
    
    def test_log_context_auto_trace(self):
        """Test LogContext with auto-generated trace ID."""
        import src.core.structured_logging as sl_module
        
        with LogContext(trace_id="auto"):
            trace_id = sl_module.trace_id_var.get()
            assert trace_id is not None
            assert len(trace_id) == 32


class TestTimedDecorator:
    """Tests for timed decorator."""
    
    def test_timed_sync(self, capsys):
        """Test timed decorator for sync function."""
        @timed()
        def slow_function():
            import time
            time.sleep(0.01)
            return "result"
        
        result = slow_function()
        
        assert result == "result"
        
        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())
        
        assert "duration_ms" in log_entry["extra"]
        assert log_entry["extra"]["status"] == "success"
    
    def test_timed_with_error(self, capsys):
        """Test timed decorator with exception."""
        @timed()
        def failing_function():
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            failing_function()
        
        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())
        
        assert log_entry["level"] == "ERROR"
        assert log_entry["extra"]["status"] == "error"
        assert log_entry["extra"]["error_type"] == "ValueError"
    
    @pytest.mark.asyncio
    async def test_timed_async(self, capsys):
        """Test timed decorator for async function."""
        @timed()
        async def async_function():
            import asyncio
            await asyncio.sleep(0.01)
            return "async_result"
        
        result = await async_function()
        
        assert result == "async_result"
        
        captured = capsys.readouterr()
        log_entry = json.loads(captured.out.strip())
        
        assert "duration_ms" in log_entry["extra"]


class TestConfigureLogging:
    """Tests for logging configuration."""
    
    def test_configure_logging(self):
        """Test configure_logging sets up root logger."""
        root_logger = logging.getLogger()
        initial_handlers = len(root_logger.handlers)
        
        configure_logging(level=logging.DEBUG)
        
        assert len(root_logger.handlers) > initial_handlers
        assert root_logger.level == logging.DEBUG
        
        # Clean up - remove our handler
        root_logger.handlers = root_logger.handlers[:-1]
