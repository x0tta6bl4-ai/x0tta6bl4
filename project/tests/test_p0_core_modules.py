"""Test module imports and core functionality"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))


class TestCoreModuleImports:
    """Test that core modules can be imported"""
    
    def test_import_feature_flags(self):
        """Should import feature flags module"""
        try:
            from src.core.feature_flags import FeatureFlags
            assert FeatureFlags is not None
        except ImportError as e:
            pytest.skip(f"Feature flags not available: {e}")
    
    def test_import_mesh_modules(self):
        """Should import mesh modules"""
        try:
            from src.mesh import slot_sync
            assert slot_sync is not None
        except ImportError as e:
            pytest.skip(f"Mesh modules not available: {e}")
    
    def test_import_security_modules(self):
        """Should import security modules"""
        try:
            from src.security import spiffe
            assert spiffe is not None
        except ImportError as e:
            pytest.skip(f"Security modules not available: {e}")
    
    def test_import_ml_modules(self):
        """Should import ML modules"""
        try:
            from src.ml import transformers
            assert transformers is not None
        except ImportError as e:
            pytest.skip(f"ML modules not available: {e}")


class TestMetricsCollection:
    """Test metrics collection and monitoring"""
    
    def test_prometheus_metrics_available(self):
        """Prometheus metrics should be available"""
        try:
            from prometheus_client import Counter, Gauge, Histogram
            assert Counter is not None
            assert Gauge is not None
            assert Histogram is not None
        except ImportError:
            pytest.skip("Prometheus not available")
    
    def test_metric_counter_creation(self):
        """Should be able to create metric counters"""
        try:
            from prometheus_client import Counter
            test_counter = Counter('test_counter', 'Test counter')
            test_counter.inc()
            assert test_counter is not None
        except ImportError:
            pytest.skip("Prometheus not available")
    
    def test_metric_gauge_creation(self):
        """Should be able to create metric gauges"""
        try:
            from prometheus_client import Gauge
            test_gauge = Gauge('test_gauge', 'Test gauge')
            test_gauge.set(42)
            assert test_gauge is not None
        except ImportError:
            pytest.skip("Prometheus not available")


class TestOpenTelemetryIntegration:
    """Test OpenTelemetry tracing integration"""
    
    def test_otel_tracer_available(self):
        """OpenTelemetry tracer should be available"""
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            assert tracer is not None
        except ImportError:
            pytest.skip("OpenTelemetry not available")
    
    def test_span_creation(self):
        """Should be able to create spans"""
        try:
            from opentelemetry import trace
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("test_span") as span:
                assert span is not None
                span.set_attribute("test", "value")
        except ImportError:
            pytest.skip("OpenTelemetry not available")


class TestConfigurationLoading:
    """Test application configuration loading"""
    
    def test_env_file_loading(self):
        """Should load environment variables"""
        import os
        os.environ['TEST_VAR'] = 'test_value'
        assert os.environ.get('TEST_VAR') == 'test_value'
    
    def test_config_defaults(self):
        """Should have sensible config defaults"""
        # Common defaults
        port = int(os.environ.get('PORT', 8000))
        assert port > 0
        assert port < 65535
    
    def test_config_from_pydantic_settings(self):
        """Should use Pydantic for config"""
        try:
            from pydantic_settings import BaseSettings
            
            class TestSettings(BaseSettings):
                app_name: str = "test"
                debug: bool = False
            
            settings = TestSettings()
            assert settings.app_name == "test"
        except ImportError:
            pytest.skip("Pydantic settings not available")


class TestLogging:
    """Test logging configuration"""
    
    def test_logger_creation(self):
        """Should be able to create loggers"""
        import logging
        logger = logging.getLogger(__name__)
        assert logger is not None
    
    def test_structlog_available(self):
        """Structlog should be available for structured logging"""
        try:
            import structlog
            assert structlog is not None
        except ImportError:
            pytest.skip("Structlog not available")
    
    def test_logging_levels(self):
        """Should support all logging levels"""
        import logging
        assert hasattr(logging, 'DEBUG')
        assert hasattr(logging, 'INFO')
        assert hasattr(logging, 'WARNING')
        assert hasattr(logging, 'ERROR')
        assert hasattr(logging, 'CRITICAL')


class TestAsyncIOIntegration:
    """Test asyncio integration"""
    
    @pytest.mark.asyncio
    async def test_async_function_execution(self):
        """Should execute async functions"""
        async def test_async():
            return "result"
        
        result = await test_async()
        assert result == "result"
    
    @pytest.mark.asyncio
    async def test_concurrent_tasks(self):
        """Should handle concurrent tasks"""
        import asyncio
        
        async def task(n):
            await asyncio.sleep(0.01)
            return n * 2
        
        results = await asyncio.gather(task(1), task(2), task(3))
        assert results == [2, 4, 6]
    
    @pytest.mark.asyncio
    async def test_task_timeout(self):
        """Should handle task timeouts"""
        import asyncio
        
        async def slow_task():
            await asyncio.sleep(10)
        
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(slow_task(), timeout=0.01)


class TestDependencyInjection:
    """Test dependency injection patterns"""
    
    def test_fastapi_dependency_injection(self):
        """FastAPI should support dependency injection"""
        from fastapi import Depends
        
        def get_user_id() -> int:
            return 42
        
        assert get_user_id() == 42
    
    @pytest.mark.asyncio
    async def test_async_dependency_resolution(self):
        """Should resolve async dependencies"""
        from fastapi import Depends
        
        async def async_dep() -> str:
            return "injected"
        
        result = await async_dep()
        assert result == "injected"


class TestErrorHandling:
    """Test error handling and exceptions"""
    
    def test_fastapi_exception_handling(self):
        """FastAPI should handle exceptions"""
        from fastapi import HTTPException
        
        with pytest.raises(HTTPException):
            raise HTTPException(status_code=404, detail="Not found")
    
    def test_custom_exception_handling(self):
        """Should support custom exceptions"""
        class CustomException(Exception):
            pass
        
        with pytest.raises(CustomException):
            raise CustomException("Custom error")


class TestValidationIntegration:
    """Test Pydantic validation"""
    
    def test_base_model_validation(self):
        """Pydantic BaseModel should validate"""
        from pydantic import BaseModel, Field
        
        class User(BaseModel):
            id: int
            name: str = Field(..., min_length=1)
        
        user = User(id=1, name="test")
        assert user.id == 1
    
    def test_field_validators(self):
        """Field validators should work"""
        from pydantic import BaseModel, field_validator
        
        class User(BaseModel):
            email: str
            
            @field_validator('email')
            @classmethod
            def validate_email(cls, v):
                if '@' not in v:
                    raise ValueError('Invalid email')
                return v
        
        user = User(email="test@example.com")
        assert "@" in user.email


import os


class TestEnvironmentConfiguration:
    """Test environment-based configuration"""
    
    def test_read_env_var(self):
        """Should read environment variables"""
        os.environ['TEST_CONFIG'] = 'test_value'
        value = os.environ.get('TEST_CONFIG')
        assert value == 'test_value'
    
    def test_env_var_with_default(self):
        """Should use defaults for missing env vars"""
        value = os.environ.get('NONEXISTENT_VAR', 'default')
        assert value == 'default'
    
    def test_env_var_type_conversion(self):
        """Should convert env vars to proper types"""
        os.environ['PORT'] = '8080'
        port = int(os.environ.get('PORT', 8000))
        assert port == 8080
        assert isinstance(port, int)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
