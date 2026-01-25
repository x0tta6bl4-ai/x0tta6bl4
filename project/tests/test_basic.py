"""Basic smoke tests for x0tta6bl4"""
import pytest


class TestBasic:
    """Basic functionality tests"""
    
    def test_import_fastapi(self):
        """FastAPI can be imported"""
        import fastapi
        assert fastapi.__version__
    
    def test_import_src(self):
        """src.core.app should be importable"""
        from src.core.app import app
        assert app is not None
        assert hasattr(app, 'routes')
    
    def test_python_version(self):
        """Python >= 3.10"""
        import sys
        assert sys.version_info >= (3, 10)
    
    @pytest.mark.asyncio
    async def test_app_startup(self):
        """FastAPI app can be created"""
        from fastapi import FastAPI
        app = FastAPI()
        assert app
    
    def test_env_var_access(self):
        """Environment variables can be read"""
        import os
        # Should not raise
        val = os.getenv('PATH', '/default')
        assert val


class TestImports:
    """Test critical imports"""
    
    def test_cryptography(self):
        import cryptography
        assert cryptography.__version__
    
    def test_pydantic(self):
        import pydantic
        assert pydantic.__version__
    
    def test_pytest(self):
        import pytest
        assert pytest.__version__
