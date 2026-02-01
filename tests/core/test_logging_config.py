"""
Tests for secure logging configuration.

Covers:
- Sensitive data masking (passwords, tokens, IPs)
- JSON structured logging format
- Log filter functionality
"""
import pytest
import json
import logging

from src.core.logging_config import (
    mask_sensitive_data,
    SensitiveDataFilter,
    StructuredJsonFormatter,
)


class TestMaskSensitiveData:
    """Tests for sensitive data masking function."""
    
    def test_mask_password(self):
        """Test password masking."""
        data = 'user password=secret123 action=login'
        result = mask_sensitive_data(data)
        assert 'password=***' in result
        assert 'secret123' not in result
    
    def test_mask_token(self):
        """Test token masking."""
        data = 'api token=abc123def456 request=GET'
        result = mask_sensitive_data(data)
        assert 'token=***' in result
        assert 'abc123def456' not in result
    
    def test_mask_api_key(self):
        """Test API key masking."""
        data = 'api_key=sk-1234567890abcdef'
        result = mask_sensitive_data(data)
        assert 'api_key=***' in result
        assert 'sk-1234567890abcdef' not in result
    
    def test_mask_authorization(self):
        """Test authorization header masking."""
        data = 'authorization=Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9'
        result = mask_sensitive_data(data)
        assert 'authorization=***' in result
    
    def test_mask_secret(self):
        """Test secret masking."""
        data = 'secret=my_super_secret_value'
        result = mask_sensitive_data(data)
        assert 'secret=***' in result
        assert 'my_super_secret_value' not in result
    
    def test_mask_private_key(self):
        """Test private key masking."""
        data = 'private_key=-----BEGIN RSA PRIVATE KEY-----'
        result = mask_sensitive_data(data)
        assert 'private_key=***' in result
    
    def test_mask_passwd(self):
        """Test passwd masking."""
        data = 'sudo passwd=user_password123'
        result = mask_sensitive_data(data)
        assert 'passwd=***' in result
        assert 'user_password123' not in result
    
    def test_mask_ip_address(self):
        """Test IP address masking."""
        data = 'Connecting to 192.168.1.100:8080'
        result = mask_sensitive_data(data)
        assert '192.168.1.***' in result
        assert '192.168.1.100' not in result
    
    def test_mask_email(self):
        """Test email masking."""
        data = 'User email: john.doe@example.com logged in'
        result = mask_sensitive_data(data)
        # Email is masked but first character is preserved
        assert '***@example.com' in result
        assert 'john.doe@example.com' not in result
    
    def test_mask_jwt_token(self):
        """Test JWT token masking."""
        # JWT tokens are already masked by the token pattern
        data = 'auth=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U'
        result = mask_sensitive_data(data)
        # JWT is masked (either as token or by JWT pattern)
        assert '***' in result or 'eyJhbGci' not in result
    
    def test_no_false_positives(self):
        """Test that safe data is not masked."""
        data = 'message=hello world status=success'
        result = mask_sensitive_data(data)
        assert result == data


class TestSensitiveDataFilter:
    """Tests for SensitiveDataFilter class."""
    
    def test_filter_masks_message(self):
        """Test that filter masks sensitive data in message."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='password=secret123',
            args=(),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert 'password=***' in record.msg
        assert 'secret123' not in record.msg
    
    def test_filter_masks_args_tuple(self):
        """Test that filter masks sensitive data in tuple args."""
        filter_obj = SensitiveDataFilter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='User %s logged in with %s',
            args=('john', 'password=secret123'),
            exc_info=None
        )
        
        filter_obj.filter(record)
        
        assert 'password=***' in record.args[1]
        assert 'secret123' not in record.args[1]


class TestStructuredJsonFormatter:
    """Tests for StructuredJsonFormatter class."""
    
    def test_format_basic_log(self):
        """Test basic log formatting."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name='test_logger',
            level=logging.INFO,
            pathname='test.py',
            lineno=10,
            msg='Test message',
            args=(),
            exc_info=None
        )
        record.created = 1609459200.0  # 2021-01-01 00:00:00 UTC
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed['level'] == 'INFO'
        assert parsed['logger'] == 'test_logger'
        assert parsed['message'] == 'Test message'
        assert parsed['module'] == 'test'
        # funcName is None when not in a function context
        assert 'function' in parsed
        assert parsed['line'] == 10
        assert 'timestamp' in parsed
    
    def test_format_masks_sensitive_data(self):
        """Test that formatter masks sensitive data."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='password=secret123',
            args=(),
            exc_info=None
        )
        record.created = 1609459200.0
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert 'password=***' in parsed['message']
        assert 'secret123' not in parsed['message']
    
    def test_format_with_extra_fields(self):
        """Test formatting with extra fields."""
        formatter = StructuredJsonFormatter()
        record = logging.LogRecord(
            name='test',
            level=logging.INFO,
            pathname='test.py',
            lineno=1,
            msg='Request processed',
            args=(),
            exc_info=None
        )
        record.created = 1609459200.0
        record.request_id = 'req-123'
        record.user_id = 'user-456'
        record.duration_ms = 150.5
        
        result = formatter.format(record)
        parsed = json.loads(result)
        
        assert parsed['request_id'] == 'req-123'
        assert parsed['user_id'] == 'user-456'
        assert parsed['duration_ms'] == 150.5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])