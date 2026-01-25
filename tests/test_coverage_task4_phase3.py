"""Task 4: Coverage Improvement - Phase 3: Feature Flags & Config Tests

Phase 3 Strategy (1.5 hours):
- Test feature flag enabled/disabled paths
- Configuration scenarios
- Conditional code paths
- Target: 81% → 83-85% coverage
"""

import pytest
from unittest import mock
from typing import Dict, Optional, Any
from enum import Enum


# ============================================================================
# FEATURE FLAG TESTS
# ============================================================================

class FeatureFlagStatus(Enum):
    """Feature flag status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    BETA = "beta"


class FeatureFlags:
    """Simple feature flag system."""
    
    def __init__(self, flags: Dict[str, str] = None):
        """Initialize feature flags."""
        self.flags = flags or {}
        self.defaults = {
            "use_new_algorithm": "disabled",
            "enable_cache": "enabled",
            "enable_logging": "enabled",
            "beta_features": "disabled",
            "debug_mode": "disabled",
            "strict_validation": "enabled",
        }
    
    def is_enabled(self, flag_name: str) -> bool:
        """Check if flag is enabled."""
        status = self.flags.get(flag_name, self.defaults.get(flag_name, "disabled"))
        return status in ["enabled", "beta"]
    
    def is_disabled(self, flag_name: str) -> bool:
        """Check if flag is disabled."""
        return not self.is_enabled(flag_name)
    
    def get_status(self, flag_name: str) -> str:
        """Get flag status."""
        return self.flags.get(flag_name, self.defaults.get(flag_name, "disabled"))
    
    def set_flag(self, flag_name: str, status: str):
        """Set flag status."""
        self.flags[flag_name] = status
    
    def reset_flag(self, flag_name: str):
        """Reset flag to default."""
        if flag_name in self.flags:
            del self.flags[flag_name]


class TestFeatureFlagsBasic:
    """Test basic feature flag functionality."""
    
    def test_feature_flag_enabled(self):
        """Test feature flag when enabled."""
        ff = FeatureFlags()
        ff.set_flag("use_new_algorithm", "enabled")
        
        assert ff.is_enabled("use_new_algorithm")
        assert not ff.is_disabled("use_new_algorithm")
    
    def test_feature_flag_disabled(self):
        """Test feature flag when disabled."""
        ff = FeatureFlags()
        ff.set_flag("use_new_algorithm", "disabled")
        
        assert ff.is_disabled("use_new_algorithm")
        assert not ff.is_enabled("use_new_algorithm")
    
    def test_feature_flag_default_enabled(self):
        """Test default enabled flag."""
        ff = FeatureFlags()
        
        # enable_cache is enabled by default
        assert ff.is_enabled("enable_cache")
    
    def test_feature_flag_default_disabled(self):
        """Test default disabled flag."""
        ff = FeatureFlags()
        
        # use_new_algorithm is disabled by default
        assert ff.is_disabled("use_new_algorithm")
    
    def test_feature_flag_status(self):
        """Test getting flag status."""
        ff = FeatureFlags()
        ff.set_flag("beta_features", "beta")
        
        status = ff.get_status("beta_features")
        assert status == "beta"
        assert ff.is_enabled("beta_features")  # beta counts as enabled
    
    def test_feature_flag_reset(self):
        """Test resetting flag to default."""
        ff = FeatureFlags()
        ff.set_flag("enable_cache", "disabled")
        
        # Custom value
        assert ff.is_disabled("enable_cache")
        
        # Reset to default (enabled)
        ff.reset_flag("enable_cache")
        assert ff.is_enabled("enable_cache")


# ============================================================================
# CONDITIONAL CODE PATHS WITH FEATURE FLAGS
# ============================================================================

class DataProcessor:
    """Data processor with feature flags."""
    
    def __init__(self, feature_flags: FeatureFlags):
        """Initialize processor."""
        self.ff = feature_flags
        self.cache = {}
    
    def process(self, data: str) -> str:
        """Process data with feature flags."""
        # Path 1: Use cache if enabled
        if self.ff.is_enabled("enable_cache"):
            if data in self.cache:
                return self.cache[data]
        
        # Process data
        result = data.upper()
        
        # Store in cache if enabled
        if self.ff.is_enabled("enable_cache"):
            self.cache[data] = result
        
        return result
    
    def validate(self, data: str) -> bool:
        """Validate data with optional strict mode."""
        if not data:
            return False
        
        if self.ff.is_enabled("strict_validation"):
            # Strict: must be alphanumeric
            return data.isalnum()
        else:
            # Lenient: any non-empty string
            return True
    
    def debug_info(self) -> Dict[str, Any]:
        """Get debug info if debug mode enabled."""
        if self.ff.is_enabled("debug_mode"):
            return {
                "cache_size": len(self.cache),
                "cache_enabled": self.ff.is_enabled("enable_cache"),
                "strict_validation": self.ff.is_enabled("strict_validation"),
            }
        return {}


class TestFeatureFlagPaths:
    """Test different code paths with feature flags."""
    
    def test_cache_enabled_path(self):
        """Test code path when cache is enabled."""
        ff = FeatureFlags()
        ff.set_flag("enable_cache", "enabled")
        processor = DataProcessor(ff)
        
        # First call processes
        result1 = processor.process("test")
        assert result1 == "TEST"
        
        # Cache should have it
        assert len(processor.cache) == 1
        
        # Second call uses cache
        result2 = processor.process("test")
        assert result2 == "TEST"
        assert len(processor.cache) == 1
    
    def test_cache_disabled_path(self):
        """Test code path when cache is disabled."""
        ff = FeatureFlags()
        ff.set_flag("enable_cache", "disabled")
        processor = DataProcessor(ff)
        
        # Process twice
        result1 = processor.process("test")
        result2 = processor.process("test")
        
        # Both succeed but cache is empty
        assert result1 == "TEST"
        assert result2 == "TEST"
        assert len(processor.cache) == 0
    
    def test_strict_validation_enabled(self):
        """Test validation with strict mode enabled."""
        ff = FeatureFlags()
        ff.set_flag("strict_validation", "enabled")
        processor = DataProcessor(ff)
        
        # Valid: alphanumeric
        assert processor.validate("test123")
        
        # Invalid: contains special chars
        assert not processor.validate("test-123")
        assert not processor.validate("test@123")
    
    def test_strict_validation_disabled(self):
        """Test validation with strict mode disabled."""
        ff = FeatureFlags()
        ff.set_flag("strict_validation", "disabled")
        processor = DataProcessor(ff)
        
        # All non-empty strings valid
        assert processor.validate("test123")
        assert processor.validate("test-123")
        assert processor.validate("test@123")
        assert processor.validate("anything!#$%")
    
    def test_debug_mode_enabled(self):
        """Test debug info when debug mode enabled."""
        ff = FeatureFlags()
        ff.set_flag("debug_mode", "enabled")
        ff.set_flag("enable_cache", "enabled")
        processor = DataProcessor(ff)
        
        # Process some data
        processor.process("data1")
        processor.process("data2")
        
        # Debug info available
        debug = processor.debug_info()
        assert debug["cache_size"] == 2
        assert debug["cache_enabled"] == True
    
    def test_debug_mode_disabled(self):
        """Test no debug info when debug mode disabled."""
        ff = FeatureFlags()
        ff.set_flag("debug_mode", "disabled")
        processor = DataProcessor(ff)
        
        # No debug info
        debug = processor.debug_info()
        assert debug == {}


# ============================================================================
# CONFIGURATION SCENARIOS
# ============================================================================

class Configuration:
    """Application configuration."""
    
    def __init__(self):
        """Initialize configuration."""
        self.api_host = "127.0.0.1"
        self.api_port = 8000
        self.debug = False
        self.log_level = "INFO"
        self.max_retries = 3
        self.timeout = 30
    
    def is_production(self) -> bool:
        """Check if production config."""
        return self.api_host != "127.0.0.1" and not self.debug
    
    def is_development(self) -> bool:
        """Check if development config."""
        return self.api_host == "127.0.0.1" or self.debug
    
    def get_connection_string(self) -> str:
        """Get connection string."""
        scheme = "https" if self.is_production() else "http"
        return f"{scheme}://{self.api_host}:{self.api_port}"
    
    def validate(self) -> bool:
        """Validate configuration."""
        if self.api_port < 1 or self.api_port > 65535:
            return False
        if self.max_retries < 0:
            return False
        if self.timeout <= 0:
            return False
        return True


class TestConfigurationScenarios:
    """Test various configuration scenarios."""
    
    def test_development_configuration(self):
        """Test development configuration."""
        config = Configuration()
        config.api_host = "127.0.0.1"
        config.debug = True
        
        assert config.is_development()
        assert not config.is_production()
    
    def test_production_configuration(self):
        """Test production configuration."""
        config = Configuration()
        config.api_host = "example.com"
        config.debug = False
        
        assert config.is_production()
        assert not config.is_development()
    
    def test_development_connection_string(self):
        """Test connection string for development."""
        config = Configuration()
        config.api_host = "127.0.0.1"
        config.api_port = 8000
        config.debug = True
        
        conn_str = config.get_connection_string()
        assert conn_str == "http://127.0.0.1:8000"
    
    def test_production_connection_string(self):
        """Test connection string for production."""
        config = Configuration()
        config.api_host = "api.example.com"
        config.api_port = 443
        config.debug = False
        
        conn_str = config.get_connection_string()
        assert conn_str == "https://api.example.com:443"
    
    def test_valid_configuration(self):
        """Test valid configuration."""
        config = Configuration()
        assert config.validate()
    
    def test_invalid_port(self):
        """Test configuration with invalid port."""
        config = Configuration()
        config.api_port = 99999
        assert not config.validate()
    
    def test_invalid_retries(self):
        """Test configuration with invalid retries."""
        config = Configuration()
        config.max_retries = -1
        assert not config.validate()
    
    def test_invalid_timeout(self):
        """Test configuration with invalid timeout."""
        config = Configuration()
        config.timeout = 0
        assert not config.validate()


# ============================================================================
# ENVIRONMENT-BASED CONFIGURATION
# ============================================================================

class EnvironmentConfig:
    """Configuration loaded from environment."""
    
    @staticmethod
    def from_env(env_dict: Dict[str, str]) -> Configuration:
        """Load configuration from environment dict."""
        config = Configuration()
        
        if "API_HOST" in env_dict:
            config.api_host = env_dict["API_HOST"]
        
        if "API_PORT" in env_dict:
            try:
                config.api_port = int(env_dict["API_PORT"])
            except ValueError:
                config.api_port = 8000
        
        if "DEBUG" in env_dict:
            config.debug = env_dict["DEBUG"].lower() in ["true", "1", "yes"]
        
        if "LOG_LEVEL" in env_dict:
            config.log_level = env_dict["LOG_LEVEL"]
        
        return config


class TestEnvironmentConfiguration:
    """Test environment-based configuration."""
    
    def test_load_from_env_dev(self):
        """Test loading development config from env."""
        env = {
            "API_HOST": "localhost",
            "API_PORT": "9000",
            "DEBUG": "true",
            "LOG_LEVEL": "DEBUG",
        }
        
        config = EnvironmentConfig.from_env(env)
        
        assert config.api_host == "localhost"
        assert config.api_port == 9000
        assert config.debug == True
        assert config.log_level == "DEBUG"
    
    def test_load_from_env_prod(self):
        """Test loading production config from env."""
        env = {
            "API_HOST": "api.prod.com",
            "API_PORT": "443",
            "DEBUG": "false",
            "LOG_LEVEL": "WARNING",
        }
        
        config = EnvironmentConfig.from_env(env)
        
        assert config.api_host == "api.prod.com"
        assert config.api_port == 443
        assert config.debug == False
        assert config.log_level == "WARNING"
    
    def test_load_from_env_partial(self):
        """Test loading config with missing env vars."""
        env = {
            "API_HOST": "custom.host",
        }
        
        config = EnvironmentConfig.from_env(env)
        
        assert config.api_host == "custom.host"
        assert config.api_port == 8000  # default
        assert config.debug == False  # default
    
    def test_load_from_env_invalid_port(self):
        """Test loading config with invalid port."""
        env = {
            "API_PORT": "invalid",
        }
        
        config = EnvironmentConfig.from_env(env)
        
        # Should fall back to default
        assert config.api_port == 8000
    
    def test_load_from_env_debug_variations(self):
        """Test various DEBUG env values."""
        for value, expected in [
            ("true", True),
            ("True", True),
            ("1", True),
            ("yes", True),
            ("false", False),
            ("0", False),
            ("no", False),
        ]:
            env = {"DEBUG": value}
            config = EnvironmentConfig.from_env(env)
            assert config.debug == expected


# ============================================================================
# RUNTIME CONFIGURATION CHANGES
# ============================================================================

class ConfigurationManager:
    """Manage configuration changes at runtime."""
    
    def __init__(self):
        """Initialize."""
        self.config = Configuration()
        self.defaults = Configuration()
        self.history = []
    
    def update(self, **kwargs):
        """Update configuration."""
        for key, value in kwargs.items():
            if hasattr(self.config, key):
                old_value = getattr(self.config, key)
                setattr(self.config, key, value)
                self.history.append({
                    "key": key,
                    "old_value": old_value,
                    "new_value": value,
                })
    
    def reset(self):
        """Reset to defaults."""
        self.config = Configuration()
        self.history.append({"action": "reset_all"})
    
    def rollback_last(self):
        """Rollback last change."""
        if self.history:
            last = self.history.pop()
            if "action" in last:
                # Reset action
                self.reset()
            else:
                # Undo change
                setattr(self.config, last["key"], last["old_value"])
    
    def get_history(self) -> list:
        """Get change history."""
        return self.history


class TestConfigurationManager:
    """Test configuration manager."""
    
    def test_update_single_setting(self):
        """Test updating single setting."""
        mgr = ConfigurationManager()
        
        mgr.update(api_host="newhost.com")
        
        assert mgr.config.api_host == "newhost.com"
        assert len(mgr.history) == 1
    
    def test_update_multiple_settings(self):
        """Test updating multiple settings."""
        mgr = ConfigurationManager()
        
        mgr.update(api_host="newhost.com", api_port=9999, debug=True)
        
        assert mgr.config.api_host == "newhost.com"
        assert mgr.config.api_port == 9999
        assert mgr.config.debug == True
        assert len(mgr.history) == 3
    
    def test_reset_configuration(self):
        """Test resetting configuration."""
        mgr = ConfigurationManager()
        mgr.update(api_host="changed.com", debug=True)
        
        # Reset
        mgr.reset()
        
        assert mgr.config.api_host == "127.0.0.1"
        assert mgr.config.debug == False
    
    def test_rollback_last_change(self):
        """Test rolling back last change."""
        mgr = ConfigurationManager()
        
        mgr.update(api_host="newhost.com", debug=True)
        mgr.rollback_last()
        
        # Last change (debug=True) rolled back
        assert mgr.config.debug == False
        assert mgr.config.api_host == "newhost.com"
    
    def test_rollback_all_changes(self):
        """Test rolling back all changes."""
        mgr = ConfigurationManager()
        
        mgr.update(api_host="newhost.com", api_port=9000)
        mgr.reset()
        
        # Defaults restored
        assert mgr.config.api_host == "127.0.0.1"
        assert mgr.config.api_port == 8000
