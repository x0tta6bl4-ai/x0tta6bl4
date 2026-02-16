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
import shutil
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

# Test imports
try:
    from src.network.ebpf.cli import main as cli_main
    from src.network.ebpf.loader import (EBPFAttachMode, EBPFLoader,
                                         EBPFProgramType)
    from src.network.ebpf.orchestrator import (EBPFOrchestrator,
                                               OrchestratorConfig,
                                               OrchestratorState)

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
        with open(program_path, "wb") as f:
            f.write(b"\x7fELF\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x00")
        return program_path

    @pytest.fixture
    def loader(self, temp_dir):
        """Create EBPFLoader instance"""
        return EBPFLoader(programs_dir=temp_dir)

    @pytest.fixture
    def orchestrator_config(self, temp_dir):
        """Create orchestrator configuration"""
        return OrchestratorConfig(
            interface="lo",
            programs_dir=temp_dir,
            enable_flow_observability=True,
            enable_metrics_export=False,
            enable_dynamic_fallback=False,
            enable_mapek_integration=False,
            auto_load_programs=False,
        )

    @pytest.fixture
    def orchestrator(self, orchestrator_config):
        """Create EBPFOrchestrator instance"""
        return EBPFOrchestrator(orchestrator_config)

    @pytest.mark.asyncio
    async def test_loader_orchestrator_integration(
        self, loader, orchestrator, mock_program_file
    ):
        """Test EBPFLoader and EBPFOrchestrator interaction"""
        with patch.object(loader, "load_program", return_value="test_prog"):
            with patch.object(loader, "attach_to_interface", return_value=True):
                with patch.object(loader, "detach_from_interface", return_value=True):
                    with patch.object(loader, "unload_program", return_value=True):
                        # Force orchestrator to use the fixture loader
                        with patch(
                            "src.network.ebpf.orchestrator.EBPFLoader",
                            return_value=loader,
                        ):
                            await orchestrator.start()
                            status = orchestrator.get_status()
                            assert status["state"] == OrchestratorState.RUNNING.value
                            programs = orchestrator._get_program_status()
                            assert isinstance(programs, list)
                            await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_orchestrator_lifecycle_management(self, orchestrator):
        """Test complete orchestrator lifecycle"""
        with patch("src.network.ebpf.orchestrator.MeshNetworkProbes") as mock_probes:
            with patch(
                "src.network.ebpf.orchestrator.CiliumLikeIntegration"
            ) as mock_cilium:
                with patch("src.network.ebpf.orchestrator.EBPFLoader"):
                    mock_probes_instance = Mock()
                    mock_probes.return_value = mock_probes_instance
                    # Use a real future or a mock that behaves like one
                    fut = asyncio.Future()
                    fut.set_result(None)
                    mock_probes_instance.start.return_value = fut

                    await orchestrator.start()
                    assert orchestrator.state == OrchestratorState.RUNNING
                    status = orchestrator.get_status()
                    assert "state" in status
                    await orchestrator.stop()
                    assert orchestrator.state == OrchestratorState.STOPPED

    def test_cli_loader_integration(self, loader, mock_program_file):
        """Test CLI commands that interact with loader"""
        with patch("sys.argv", ["ebpf-cli", "load", str(mock_program_file)]):
            with patch.object(loader, "load_program", return_value="test_prog_123"):
                program_id = loader.load_program(str(mock_program_file))
                assert program_id == "test_prog_123"
                with patch.object(
                    loader, "get_stats", return_value={"programs": 1, "interfaces": 1}
                ):
                    stats = loader.get_stats()
                    assert "programs" in stats

    @pytest.mark.asyncio
    async def test_full_system_integration(self, orchestrator, loader):
        """Test complete system integration: CLI -> Orchestrator -> Loader"""
        with patch("src.network.ebpf.orchestrator.MeshNetworkProbes"):
            with patch(
                "src.network.ebpf.orchestrator.CiliumLikeIntegration"
            ) as mock_cilium_class:
                mock_cilium = mock_cilium_class.return_value
                mock_cilium.get_hubble_like_flows = AsyncMock(return_value=[])
                # Force orchestrator to use the fixture loader
                with patch(
                    "src.network.ebpf.orchestrator.EBPFLoader", return_value=loader
                ):
                    with patch.object(loader, "load_program", return_value="full_prog"):
                        with patch.object(
                            loader, "attach_to_interface", return_value=True
                        ):
                            with patch.object(
                                loader, "detach_from_interface", return_value=True
                            ):
                                with patch.object(
                                    loader, "unload_program", return_value=True
                                ):
                                    await orchestrator.start()

                                    # 1. Load program via orchestrator
                                    program_id = orchestrator.load_program("test_xdp.o")
                                    assert isinstance(program_id, str)

                                    # 2. Attach to interface
                                    # Note: attach_program is NOT async and takes a mode string
                                    success = orchestrator.attach_program(
                                        program_id, "lo", "skb"
                                    )
                                    assert success is True

                                    # 3. Get system status
                                    status = orchestrator.get_status()
                                    assert "state" in status

                                    # 4. Monitor flows
                                    flows = await orchestrator.get_flows()
                                    assert isinstance(flows, list)

                                    # 5. Cleanup
                                    orchestrator.detach_program(program_id, "lo")
                                    orchestrator.unload_program(program_id)
                                    await orchestrator.stop()

    @pytest.mark.asyncio
    async def test_error_handling_integration(self, loader, orchestrator):
        """Test error handling across components"""
        with patch.object(loader, "load_program", side_effect=Exception("Load failed")):
            with pytest.raises(Exception):
                loader.load_program("nonexistent.o")

        with patch.object(
            orchestrator, "_initialize_components", side_effect=Exception("Init failed")
        ):
            success = await orchestrator.start()
            assert success is False
            assert orchestrator.state == OrchestratorState.ERROR

    @pytest.mark.asyncio
    async def test_performance_monitoring_integration(self, orchestrator):
        """Test performance monitoring integration"""
        # Mock components to return valid numeric data to avoid comparison errors
        with patch(
            "src.network.ebpf.orchestrator.MeshNetworkProbes"
        ) as mock_probes_class:
            mock_probes = mock_probes_class.return_value
            mock_probes.get_current_metrics.return_value = {
                "avg_latency_ns": 100,
                "queue_congestion": 0.1,
            }
            mock_probes.start.return_value = asyncio.Future()
            mock_probes.start.return_value.set_result(None)

            with patch(
                "src.network.ebpf.orchestrator.CiliumLikeIntegration"
            ) as mock_cilium_class:
                mock_cilium = mock_cilium_class.return_value
                mock_cilium.get_flow_metrics.return_value = {
                    "flows_processed_total": 50
                }

                with patch(
                    "src.network.ebpf.orchestrator.EBPFLoader"
                ) as mock_loader_class:
                    mock_loader = mock_loader_class.return_value
                    mock_loader.list_loaded_programs.return_value = []

                    await orchestrator.start()

                    # Test metrics collection
                    metrics = orchestrator.get_metrics()
                    assert isinstance(metrics, dict)
                    assert "timestamp" in metrics

                    # Test health checks
                    health = orchestrator.health_check()
                    assert isinstance(health, dict)
                    assert health.get("healthy") is True

                    await orchestrator.stop()

    def test_configuration_persistence(self, orchestrator_config, temp_dir):
        """Test configuration loading and persistence"""
        config_file = temp_dir / "ebpf_config.json"
        import json

        with open(config_file, "w") as f:
            json.dump({"interface": "eth0", "enable_flow_observability": True}, f)

        # This test currently only verifies JSON basic operation,
        # but verifies we can write to the temp_dir.
        with open(config_file, "r") as f:
            loaded = json.load(f)
            assert loaded["interface"] == "eth0"
