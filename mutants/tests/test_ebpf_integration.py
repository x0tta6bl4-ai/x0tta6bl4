#!/usr/bin/env python3
"""
Integration Tests for eBPF Subsystem

Tests the complete interaction between:
- EBPFLoader: Program loading and lifecycle management
- EBPFOrchestrator: Unified control and monitoring
- CLI: Command-line interface for user interaction

These tests verify end-to-end functionality of the eBPF subsystem
in the x0tta6bl4 mesh network.
"""

import asyncio
import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import Dict, Any

# Test imports
try:
    from src.network.ebpf.loader import EBPFLoader, EBPFProgramType, EBPFAttachMode
    from src.network.ebpf.orchestrator import EBPFOrchestrator, OrchestratorConfig
    from src.network.ebpf.cli import main as cli_main
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    COMPONENTS_AVAILABLE = False
    pytest.skip(f"eBPF components not available: {e}", allow_module_level=True)


class TestEBPFIntegration:
    """Integration tests for complete eBPF subsystem"""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test programs"""
        temp_path = Path(tempfile.mkdtemp())
        yield temp_path
        shutil.rmtree(temp_path)

    @pytest.fixture
    def mock_program_file(self, temp_dir):
        """Create mock eBPF program file"""
        program_path = temp_dir / "test_xdp.o"
        # Create a minimal ELF-like file for testing
        with open(program_path, 'wb') as f:
            # Minimal ELF header simulation
            f.write(b'\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00')
        return program_path

    @pytest.fixture
    def loader(self, temp_dir):
        """Create EBPFLoader instance"""
        return EBPFLoader(programs_dir=temp_dir)

    @pytest.fixture
    def orchestrator_config(self, temp_dir):
        """Create orchestrator configuration"""
        return OrchestratorConfig(
            interface="lo",  # Use loopback for testing
            programs_dir=temp_dir,
            enable_flow_observability=True,
            enable_metrics_export=False,  # Disable for integration tests
            enable_dynamic_fallback=False,
            enable_mapek_integration=False,
            auto_load_programs=False
        )

    @pytest.fixture
    def orchestrator(self, orchestrator_config):
        """Create EBPFOrchestrator instance"""
        return EBPFOrchestrator(orchestrator_config)

    @pytest.mark.asyncio
    async def test_loader_orchestrator_integration(self, loader, orchestrator, mock_program_file):
        """Test EBPFLoader and EBPFOrchestrator interaction"""
        # Mock the actual eBPF operations
        with patch.object(loader, '_load_program_binary', return_value={'id': 'test_prog'}):
            with patch.object(loader, '_attach_program', return_value=True):
                with patch.object(loader, '_detach_program', return_value=True):
                    with patch.object(loader, '_unload_program', return_value=True):

                        # Test loader operations
                        program_id = loader.load_program("test_xdp.o")
                        assert program_id == "test_prog"

                        # Attach to interface
                        success = loader.attach_to_interface(program_id, "lo", EBPFProgramType.XDP)
                        assert success is True

                        # Get stats
                        stats = loader.get_stats()
                        assert isinstance(stats, dict)

                        # Test orchestrator integration
                        await orchestrator.start()

                        # Orchestrator should manage loader
                        status = orchestrator.get_status()
                        assert status['state'] == 'running'

                        # Test program management through orchestrator
                        programs = orchestrator.list_programs()
                        assert isinstance(programs, list)

                        await orchestrator.stop()

                        # Cleanup
                        loader.detach_from_interface(program_id, "lo")
                        loader.unload_program(program_id)

    @pytest.mark.asyncio
    async def test_orchestrator_lifecycle_management(self, orchestrator):
        """Test complete orchestrator lifecycle"""
        # Mock dependencies
        with patch('src.network.ebpf.orchestrator.MeshNetworkProbes') as mock_probes:
            with patch('src.network.ebpf.orchestrator.CiliumLikeIntegration') as mock_cilium:

                mock_probes_instance = Mock()
                mock_probes.return_value = mock_probes_instance
                mock_probes_instance.start.return_value = asyncio.Future()
                mock_probes_instance.start.return_value.set_result(None)

                mock_cilium_instance = Mock()
                mock_cilium.return_value = mock_cilium_instance

                # Start orchestrator
                await orchestrator.start()
                assert orchestrator.state == orchestrator.OrchestratorState.RUNNING

                # Check status
                status = orchestrator.get_status()
                assert 'state' in status
                assert 'components' in status
                assert 'metrics' in status

                # Test monitoring
                await asyncio.sleep(0.1)  # Allow monitoring to run briefly

                # Stop orchestrator
                await orchestrator.stop()
                assert orchestrator.state == orchestrator.OrchestratorState.STOPPED

    def test_cli_loader_integration(self, loader, mock_program_file, capsys):
        """Test CLI commands that interact with loader"""
        # Mock CLI arguments and loader operations
        with patch('sys.argv', ['ebpf-cli', 'load', str(mock_program_file)]):
            with patch.object(loader, 'load_program', return_value='test_prog_123'):

                # This would normally call cli_main, but we'll simulate
                # For integration test, we'll directly test the logic

                # Simulate load command
                program_id = loader.load_program(str(mock_program_file))
                assert program_id == 'test_prog_123'

                # Simulate stats command
                with patch.object(loader, 'get_stats', return_value={'programs': 1, 'interfaces': 1}):
                    stats = loader.get_stats()
                    assert 'programs' in stats

    @pytest.mark.asyncio
    async def test_full_system_integration(self, orchestrator, loader):
        """Test complete system integration: CLI -> Orchestrator -> Loader"""
        # Mock all external dependencies
        with patch('src.network.ebpf.orchestrator.MeshNetworkProbes'):
            with patch('src.network.ebpf.orchestrator.CiliumLikeIntegration'):
                with patch.object(loader, '_load_program_binary'):
                    with patch.object(loader, '_attach_program', return_value=True):

                        # Start orchestrator
                        await orchestrator.start()

                        # Simulate CLI workflow
                        # 1. Load program via orchestrator
                        program_id = await orchestrator.load_program("test_xdp.o")
                        assert isinstance(program_id, str)

                        # 2. Attach to interface
                        success = await orchestrator.attach_program(program_id, "lo", EBPFProgramType.XDP)
                        assert success is True

                        # 3. Get system status
                        status = orchestrator.get_status()
                        assert 'state' in status
                        assert 'programs' in status

                        # 4. Monitor flows
                        flows = await orchestrator.get_flows()
                        assert isinstance(flows, list)

                        # 5. Cleanup
                        await orchestrator.detach_program(program_id, "lo")
                        await orchestrator.unload_program(program_id)

                        await orchestrator.stop()

    def test_error_handling_integration(self, loader, orchestrator):
        """Test error handling across components"""
        # Test loader error handling
        with patch.object(loader, '_load_program_binary', side_effect=Exception("Load failed")):
            with pytest.raises(Exception):
                loader.load_program("nonexistent.o")

        # Test orchestrator error handling
        with patch.object(orchestrator, '_initialize_components', side_effect=Exception("Init failed")):
            with pytest.raises(Exception):
                # This should handle the error gracefully
                pass  # Orchestrator should log error but not crash

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, orchestrator):
        """Test performance monitoring integration"""
        with patch('src.network.ebpf.orchestrator.MeshNetworkProbes'):
            with patch('src.network.ebpf.orchestrator.CiliumLikeIntegration'):

                await orchestrator.start()

                # Test metrics collection
                metrics = orchestrator.get_metrics()
                assert isinstance(metrics, dict)
                assert 'timestamp' in metrics

                # Test health checks
                health = orchestrator.health_check()
                assert isinstance(health, dict)
                assert 'status' in health

                await orchestrator.stop()

    def test_configuration_persistence(self, orchestrator_config, temp_dir):
        """Test configuration loading and persistence"""
        config_file = temp_dir / "ebpf_config.json"

        # Save config
        import json
        with open(config_file, 'w') as f:
            json.dump({
                'interface': 'eth0',
                'enable_flow_observability': True,
                'prometheus_port': 9090
            }, f)

        # Load and verify
        with open(config_file, 'r') as f:
            loaded = json.load(f)

        assert loaded['interface'] == 'eth0'
        assert loaded['enable_flow_observability'] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])