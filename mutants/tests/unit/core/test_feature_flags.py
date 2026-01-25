"""
Tests for core feature flags module.
"""
import pytest
import os
import logging
from unittest.mock import patch

from src.core.feature_flags import FeatureFlags


class TestFeatureFlags:
    """Tests for FeatureFlags class"""
    
    def test_get_all_flags_returns_dict(self):
        """Test that get_all_flags returns a dictionary"""
        flags = FeatureFlags.get_all_flags()
        
        assert isinstance(flags, dict)
        assert "byzantine_protection" in flags
        assert "failover_enabled" in flags
        assert "pqc_beacons" in flags
        assert "minimal_mode" in flags
        assert "graphsage_enabled" in flags
        assert "spiffe_enabled" in flags
        assert "ebpf_enabled" in flags
        assert "fl_enabled" in flags
        assert "dao_enabled" in flags
    
    def test_get_all_flags_boolean_values(self):
        """Test that all flags are boolean values"""
        flags = FeatureFlags.get_all_flags()
        
        for flag_name, flag_value in flags.items():
            assert isinstance(flag_value, bool), f"Flag {flag_name} should be bool, got {type(flag_value)}"
    
    def test_byzantine_protection_flag(self):
        """Test BYZANTINE_PROTECTION flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_BYZANTINE": "true"}):
            # Reload module to pick up new env var
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.BYZANTINE_PROTECTION is True
    
    def test_failover_enabled_flag(self):
        """Test FAILOVER_ENABLED flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_FAILOVER": "true"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.FAILOVER_ENABLED is True
    
    def test_pqc_beacons_flag(self):
        """Test PQC_BEACONS flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_PQC_BEACONS": "true"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.PQC_BEACONS is True
    
    def test_minimal_mode_flag(self):
        """Test MINIMAL_MODE flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_MINIMAL": "true"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.MINIMAL_MODE is True
    
    def test_graphsage_enabled_flag(self):
        """Test GRAPHSAGE_ENABLED flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_GRAPHSAGE": "false"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.GRAPHSAGE_ENABLED is False
    
    def test_spiffe_enabled_flag(self):
        """Test SPIFFE_ENABLED flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_SPIFFE": "false"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.SPIFFE_ENABLED is False
    
    def test_ebpf_enabled_flag(self):
        """Test EBPF_ENABLED flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_EBPF": "false"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.EBPF_ENABLED is False
    
    def test_fl_enabled_flag(self):
        """Test FL_ENABLED flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_FL": "false"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.FL_ENABLED is False
    
    def test_dao_enabled_flag(self):
        """Test DAO_ENABLED flag"""
        with patch.dict(os.environ, {"X0TTA6BL4_DAO": "false"}):
            import importlib
            import src.core.feature_flags
            importlib.reload(src.core.feature_flags)
            from src.core.feature_flags import FeatureFlags
            
            assert FeatureFlags.DAO_ENABLED is False
    
    def test_log_status(self):
        """Test log_status method"""
        with patch('src.core.feature_flags.logger') as mock_logger:
            FeatureFlags.log_status()
            
            # Should log enabled and disabled flags
            assert mock_logger.info.call_count >= 2
    
    def test_log_status_with_enabled_flags(self):
        """Test log_status with some flags enabled"""
        with patch('src.core.feature_flags.logger') as mock_logger:
            FeatureFlags.log_status()
            
            # Check that info was called
            calls = [str(call) for call in mock_logger.info.call_args_list]
            assert any("Enabled" in str(call) for call in calls)
            assert any("Disabled" in str(call) for call in calls)

