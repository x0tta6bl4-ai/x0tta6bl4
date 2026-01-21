#!/usr/bin/env python3
"""
Unit tests for EBPFLoader

Tests the core functionality of the eBPF program loader including:
- Program loading
- Interface attachment/detachment
- Statistics collection
- Route updates
- Cleanup operations
"""

import pytest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# Import the module under test
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.network.ebpf.loader import (
    EBPFLoader,
    EBPFProgramType,
    EBPFAttachMode,
    EBPFLoadError,
    EBPFAttachError
)


class TestEBPFLoaderInit:
    """Tests for EBPFLoader initialization"""
    
    def test_init_default_programs_dir(self):
        """Test initialization with default programs directory"""
        loader = EBPFLoader()
        assert loader.programs_dir is not None
        assert loader.loaded_programs == {}
        assert loader.attached_interfaces == {}
    
    def test_init_custom_programs_dir(self, tmp_path):
        """Test initialization with custom programs directory"""
        loader = EBPFLoader(programs_dir=tmp_path)
        assert loader.programs_dir == tmp_path


class TestEBPFLoaderLoadProgram:
    """Tests for load_program method"""
    
    def test_load_program_file_not_found(self, tmp_path):
        """Test loading non-existent program raises error"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with pytest.raises(EBPFLoadError) as exc_info:
            loader.load_program("nonexistent.o")
        
        assert "not found" in str(exc_info.value)
    
    def test_load_program_invalid_extension(self, tmp_path):
        """Test loading file with wrong extension raises error"""
        # Create a file with wrong extension
        test_file = tmp_path / "test.txt"
        test_file.write_text("not an eBPF program")
        
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with pytest.raises(EBPFLoadError) as exc_info:
            loader.load_program("test.txt")
        
        assert "Invalid eBPF program file" in str(exc_info.value)
    
    def test_load_program_success(self, tmp_path):
        """Test successful program loading"""
        # Create a dummy .o file
        test_file = tmp_path / "test_program.o"
        test_file.write_bytes(b'\x7fELF' + b'\x00' * 100)  # Minimal ELF header
        
        loader = EBPFLoader(programs_dir=tmp_path)
        
        # Mock bpftool to avoid actual loading
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="bpftool not found")
            
            program_id = loader.load_program("test_program.o", EBPFProgramType.XDP)
        
        assert program_id is not None
        assert "xdp_test_program" in program_id
        assert program_id in loader.loaded_programs
        assert loader.loaded_programs[program_id]["loaded"] is True


class TestEBPFLoaderAttach:
    """Tests for attach_to_interface method"""
    
    def test_attach_program_not_loaded(self, tmp_path):
        """Test attaching non-loaded program raises error"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with pytest.raises(EBPFAttachError) as exc_info:
            loader.attach_to_interface("nonexistent_program", "eth0")
        
        assert "not loaded" in str(exc_info.value)
    
    def test_attach_interface_not_found(self, tmp_path):
        """Test attaching to non-existent interface raises error"""
        # Create and load a program first
        test_file = tmp_path / "test.o"
        test_file.write_bytes(b'\x7fELF' + b'\x00' * 100)
        
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="")
            program_id = loader.load_program("test.o")
        
        with pytest.raises(EBPFAttachError) as exc_info:
            loader.attach_to_interface(program_id, "nonexistent_interface_xyz")
        
        assert "not found" in str(exc_info.value)


class TestEBPFLoaderGetStats:
    """Tests for get_stats method"""
    
    def test_get_stats_no_bpftool(self, tmp_path):
        """Test get_stats returns zeros when bpftool not available"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bpftool not found")
            
            stats = loader.get_stats()
        
        assert stats['total_packets'] == 0
        assert stats['passed_packets'] == 0
        assert stats['dropped_packets'] == 0
        assert stats['forwarded_packets'] == 0
    
    def test_get_stats_with_data(self, tmp_path):
        """Test get_stats parses bpftool output correctly"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        # Mock bpftool output
        mock_output = '[{"key": 0, "value": 1000}, {"key": 1, "value": 900}, {"key": 2, "value": 50}, {"key": 3, "value": 50}]'
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout=mock_output)
            
            stats = loader.get_stats()
        
        assert stats['total_packets'] == 1000
        assert stats['passed_packets'] == 900
        assert stats['dropped_packets'] == 50
        assert stats['forwarded_packets'] == 50


class TestEBPFLoaderUpdateRoutes:
    """Tests for update_routes method"""
    
    def test_update_routes_no_bpftool(self, tmp_path):
        """Test update_routes returns False when bpftool not available"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = FileNotFoundError("bpftool not found")
            
            result = loader.update_routes({"192.168.1.1": "2"})
        
        assert result is False
    
    def test_update_routes_success(self, tmp_path):
        """Test update_routes succeeds with valid data"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0)
            
            result = loader.update_routes({
                "3232235777": "2",  # 192.168.1.1 as int
                "3232235778": "3"   # 192.168.1.2 as int
            })
        
        assert result is True
        assert mock_run.call_count == 2


class TestEBPFLoaderCleanup:
    """Tests for cleanup method"""
    
    def test_cleanup_empty(self, tmp_path):
        """Test cleanup with no loaded programs"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        # Should not raise
        loader.cleanup()
        
        assert loader.loaded_programs == {}
        assert loader.attached_interfaces == {}
    
    def test_cleanup_with_programs(self, tmp_path):
        """Test cleanup properly cleans up loaded programs"""
        test_file = tmp_path / "test.o"
        test_file.write_bytes(b'\x7fELF' + b'\x00' * 100)
        
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="")
            program_id = loader.load_program("test.o")
        
        assert len(loader.loaded_programs) == 1
        
        loader.cleanup()
        
        assert loader.loaded_programs == {}


class TestEBPFLoaderLoadPrograms:
    """Tests for load_programs method"""
    
    def test_load_programs_empty_dir(self, tmp_path):
        """Test load_programs with empty directory"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        loaded = loader.load_programs()
        
        assert loaded == []
    
    def test_load_programs_nonexistent_dir(self, tmp_path):
        """Test load_programs with non-existent directory"""
        loader = EBPFLoader(programs_dir=tmp_path / "nonexistent")
        
        loaded = loader.load_programs()
        
        assert loaded == []
    
    def test_load_programs_multiple_files(self, tmp_path):
        """Test load_programs loads all .o files"""
        # Create multiple .o files
        for name in ["xdp_test1.o", "xdp_test2.o", "tc_test.o"]:
            (tmp_path / name).write_bytes(b'\x7fELF' + b'\x00' * 100)
        
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="")
            
            loaded = loader.load_programs()
        
        assert len(loaded) == 3


class TestEBPFLoaderListPrograms:
    """Tests for list_loaded_programs method"""
    
    def test_list_empty(self, tmp_path):
        """Test listing with no programs"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        programs = loader.list_loaded_programs()
        
        assert programs == []
    
    def test_list_with_programs(self, tmp_path):
        """Test listing loaded programs"""
        test_file = tmp_path / "test.o"
        test_file.write_bytes(b'\x7fELF' + b'\x00' * 100)
        
        loader = EBPFLoader(programs_dir=tmp_path)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stderr="")
            loader.load_program("test.o")
        
        programs = loader.list_loaded_programs()
        
        assert len(programs) == 1
        assert "id" in programs[0]
        assert "path" in programs[0]


class TestEBPFLoaderGetInterfacePrograms:
    """Tests for get_interface_programs method"""
    
    def test_get_interface_programs_empty(self, tmp_path):
        """Test getting programs for interface with none attached"""
        loader = EBPFLoader(programs_dir=tmp_path)
        
        programs = loader.get_interface_programs("eth0")
        
        assert programs == []


# Integration tests (require actual eBPF support)
@pytest.mark.skipif(
    not os.path.exists("/sys/fs/bpf"),
    reason="BPF filesystem not available"
)
class TestEBPFLoaderIntegration:
    """Integration tests requiring actual eBPF support"""
    
    def test_real_stats_collection(self):
        """Test real stats collection from eBPF maps"""
        loader = EBPFLoader()
        stats = loader.get_stats()
        
        # Should return dict with expected keys
        assert 'total_packets' in stats
        assert 'passed_packets' in stats
        assert 'dropped_packets' in stats
        assert 'forwarded_packets' in stats


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
