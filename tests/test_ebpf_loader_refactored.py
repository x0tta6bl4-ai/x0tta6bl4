"""
Tests for Refactored eBPF Loader Module

Tests the modular eBPF loader architecture:
- ProgramLoader: ELF parsing and program loading
- AttachManager: Interface attachment
- MapManager: Map operations
- Orchestrator: High-level coordination
"""

import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, mock_open


class TestEBPFProgramLoader:
    """Tests for EBPFProgramLoader component."""
    
    @pytest.fixture
    def loader(self, tmp_path):
        """Create program loader with temp directory."""
        from src.network.ebpf.loader.program_loader import EBPFProgramLoader
        return EBPFProgramLoader(programs_dir=tmp_path)
    
    def test_initialization(self, loader, tmp_path):
        """Test loader initialization."""
        assert loader.programs_dir == tmp_path
        assert loader.loaded_programs == {}
    
    def test_parse_elf_sections_no_library(self, loader, tmp_path):
        """Test ELF parsing when pyelftools not available."""
        # Create dummy file
        elf_file = tmp_path / "test.o"
        elf_file.write_bytes(b"dummy")
        
        with patch('src.network.ebpf.loader.program_loader.ELF_TOOLS_AVAILABLE', False):
            sections = loader.parse_elf_sections(elf_file)
            assert sections == {}
    
    def test_load_program_file_not_found(self, loader):
        """Test loading non-existent program."""
        from src.network.ebpf.loader.program_loader import EBPFLoadError, EBPFProgramType
        
        with pytest.raises(EBPFLoadError, match="not found"):
            loader.load("nonexistent.o", EBPFProgramType.XDP)
    
    def test_load_program_invalid_extension(self, loader, tmp_path):
        """Test loading file with wrong extension."""
        from src.network.ebpf.loader.program_loader import EBPFLoadError, EBPFProgramType
        
        # Create file with wrong extension
        invalid_file = tmp_path / "test.txt"
        invalid_file.write_text("not an elf file")
        
        with pytest.raises(EBPFLoadError, match="Expected .o"):
            loader.load("test.txt", EBPFProgramType.XDP)
    
    def test_unload_program_not_loaded(self, loader):
        """Test unloading program that was never loaded."""
        result = loader.unload("nonexistent_id")
        assert result is False
    
    def test_get_program_not_found(self, loader):
        """Test getting non-existent program."""
        result = loader.get_program("nonexistent_id")
        assert result is None
    
    def test_list_programs_empty(self, loader):
        """Test listing programs when none loaded."""
        result = loader.list_programs()
        assert result == {}


class TestEBPFAttachManager:
    """Tests for EBPFAttachManager component."""
    
    @pytest.fixture
    def manager(self):
        """Create attach manager."""
        from src.network.ebpf.loader.attach_manager import EBPFAttachManager
        return EBPFAttachManager()
    
    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager.attached_interfaces == {}
    
    def test_verify_interface_not_found(self, manager):
        """Test verification of non-existent interface."""
        from src.network.ebpf.loader.attach_manager import EBPFAttachError
        
        with patch('pathlib.Path.exists', return_value=False):
            with pytest.raises(EBPFAttachError, match="not found"):
                manager.verify_interface("nonexistent0")
    
    def test_get_interface_attachments_empty(self, manager):
        """Test getting attachments for interface with none."""
        result = manager.get_interface_attachments("eth0")
        assert result == []
    
    def test_remove_attachment_not_found(self, manager):
        """Test removing non-existent attachment."""
        result = manager.remove_attachment("eth0", "nonexistent_id")
        assert result is False


class TestEBPFMapManager:
    """Tests for EBPFMapManager component."""
    
    @pytest.fixture
    def manager(self):
        """Create map manager."""
        from src.network.ebpf.loader.map_manager import EBPFMapManager
        return EBPFMapManager()
    
    def test_initialization(self, manager):
        """Test manager initialization."""
        assert manager is not None
    
    def test_get_stats_no_bpftool(self, manager):
        """Test getting stats when bpftool not available."""
        with patch.object(manager, '_bpftool_available', False):
            stats = manager.get_stats()
            assert stats["total_packets"] == 0
            assert stats["passed_packets"] == 0
            assert stats["dropped_packets"] == 0
            assert stats["forwarded_packets"] == 0
    
    def test_read_map_no_bpftool(self, manager):
        """Test reading map when bpftool not available."""
        with patch.object(manager, '_bpftool_available', False):
            result = manager.read_map("test_map")
            assert result == {}
    
    def test_update_entry_no_bpftool(self, manager):
        """Test updating entry when bpftool not available."""
        with patch.object(manager, '_bpftool_available', False):
            result = manager.update_entry("test_map", "key", "value")
            assert result is False
    
    def test_update_routes_no_bpftool(self, manager):
        """Test updating routes when bpftool not available."""
        with patch.object(manager, '_bpftool_available', False):
            result = manager.update_routes({"10.0.0.1": "eth0"})
            assert result is False
    
    def test_list_maps_no_bpftool(self, manager):
        """Test listing maps when bpftool not available."""
        with patch.object(manager, '_bpftool_available', False):
            result = manager.list_maps()
            assert result == []


class TestEBPFLoaderOrchestrator:
    """Tests for EBPFLoaderOrchestrator (main entry point)."""
    
    @pytest.fixture
    def orchestrator(self, tmp_path):
        """Create orchestrator with temp directory."""
        from src.network.ebpf.loader.orchestrator import EBPFLoaderOrchestrator
        return EBPFLoaderOrchestrator(programs_dir=tmp_path)
    
    def test_initialization(self, orchestrator, tmp_path):
        """Test orchestrator initialization."""
        assert orchestrator.program_loader is not None
        assert orchestrator.attach_manager is not None
        assert orchestrator.map_manager is not None
    
    def test_list_loaded_programs_empty(self, orchestrator):
        """Test listing programs when none loaded."""
        result = orchestrator.list_loaded_programs()
        assert result == []
    
    def test_get_interface_programs_empty(self, orchestrator):
        """Test getting interface programs when none attached."""
        result = orchestrator.get_interface_programs("eth0")
        assert result == []
    
    def test_get_stats(self, orchestrator):
        """Test getting stats."""
        stats = orchestrator.get_stats()
        assert "total_packets" in stats
        assert "passed_packets" in stats
        assert "dropped_packets" in stats
        assert "forwarded_packets" in stats
    
    def test_unload_program_not_loaded(self, orchestrator):
        """Test unloading program that was never loaded."""
        result = orchestrator.unload_program("nonexistent_id")
        assert result is False
    
    def test_detach_from_interface_not_attached(self, orchestrator):
        """Test detaching program that was never attached."""
        result = orchestrator.detach_from_interface("nonexistent_id", "eth0")
        assert result is False
    
    def test_cleanup_empty(self, orchestrator):
        """Test cleanup when nothing loaded."""
        # Should not raise
        orchestrator.cleanup()
    
    def test_load_programs_empty_directory(self, orchestrator, tmp_path):
        """Test loading programs from empty directory."""
        result = orchestrator.load_programs()
        assert result == []
    
    def test_load_programs_no_directory(self, orchestrator):
        """Test loading programs when directory doesn't exist."""
        orchestrator.program_loader.programs_dir = Path("/nonexistent")
        result = orchestrator.load_programs()
        assert result == []


class TestBackwardCompatibility:
    """Tests for backward compatibility with original EBPFLoader."""
    
    def test_ebpfloader_alias(self):
        """Test that EBPFLoader is aliased to EBPFLoaderOrchestrator."""
        from src.network.ebpf.loader.orchestrator import EBPFLoader, EBPFLoaderOrchestrator
        
        assert EBPFLoader is EBPFLoaderOrchestrator
    
    def test_import_from_old_path(self):
        """Test that imports from old path still work."""
        # This tests that the module structure is compatible
        from src.network.ebpf.loader import (
            EBPFLoaderOrchestrator,
            EBPFProgramType,
            EBPFAttachMode,
            EBPFLoadError,
            EBPFAttachError,
        )
        
        assert EBPFProgramType.XDP.value == "xdp"
        assert EBPFAttachMode.SKB.value == "skb"


class TestEnums:
    """Tests for enum definitions."""
    
    def test_program_types(self):
        """Test EBPFProgramType enum values."""
        from src.network.ebpf.loader.program_loader import EBPFProgramType
        
        assert EBPFProgramType.XDP.value == "xdp"
        assert EBPFProgramType.TC.value == "tc"
        assert EBPFProgramType.CGROUP_SKB.value == "cgroup_skb"
        assert EBPFProgramType.SOCKET_FILTER.value == "socket_filter"
    
    def test_attach_modes(self):
        """Test EBPFAttachMode enum values."""
        from src.network.ebpf.loader.attach_manager import EBPFAttachMode
        
        assert EBPFAttachMode.SKB.value == "skb"
        assert EBPFAttachMode.DRV.value == "drv"
        assert EBPFAttachMode.HW.value == "hw"


class TestExceptions:
    """Tests for exception classes."""
    
    def test_ebpf_load_error(self):
        """Test EBPFLoadError exception."""
        from src.network.ebpf.loader.program_loader import EBPFLoadError
        
        with pytest.raises(EBPFLoadError):
            raise EBPFLoadError("Test error")
    
    def test_ebpf_attach_error(self):
        """Test EBPFAttachError exception."""
        from src.network.ebpf.loader.attach_manager import EBPFAttachError
        
        with pytest.raises(EBPFAttachError):
            raise EBPFAttachError("Test error")
