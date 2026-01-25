"""
Tests for eBPF Loader functionality.
"""
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from src.network.ebpf.loader import (
    EBPFLoader,
    EBPFProgramType,
    EBPFAttachMode,
    EBPFLoadError,
    EBPFAttachError
)


class TestEBPFLoader:
    """Test eBPF loader functionality"""
    
    def test_loader_initialization(self):
        """Test that loader initializes correctly"""
        loader = EBPFLoader()
        assert loader.programs_dir is not None
        assert isinstance(loader.loaded_programs, dict)
        assert isinstance(loader.attached_interfaces, dict)
    
    def test_load_program_file_not_found(self):
        """Test that loading non-existent program raises error"""
        loader = EBPFLoader()
        
        with pytest.raises(EBPFLoadError):
            loader.load_program("nonexistent.o", EBPFProgramType.XDP)
    
    def test_load_program_invalid_extension(self):
        """Test that loading non-.o file raises error"""
        loader = EBPFLoader()
        
        with tempfile.NamedTemporaryFile(suffix=".c", delete=False) as f:
            f.write(b"test")
            temp_path = f.name
        
        try:
            with pytest.raises(EBPFLoadError):
                loader.load_program(Path(temp_path).name, EBPFProgramType.XDP)
        finally:
            Path(temp_path).unlink()
    
    @patch('src.network.ebpf.loader.subprocess.run')
    @patch('src.network.ebpf.loader.Path.exists')
    def test_load_program_success(self, mock_exists, mock_subprocess):
        """Test successful program loading"""
        mock_exists.return_value = True
        
        # Mock ELF parsing (no pyelftools)
        with patch('src.network.ebpf.loader.ELF_TOOLS_AVAILABLE', False):
            loader = EBPFLoader()
            
            # Mock bpftool load
            mock_subprocess.return_value = Mock(returncode=0, stdout="", stderr="")
            
            # Create a mock .o file
            with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
                f.write(b"mock ebpf object")
                temp_path = f.name
            
            try:
                # Override programs_dir to point to temp directory
                loader.programs_dir = Path(temp_path).parent
                program_id = loader.load_program(Path(temp_path).name, EBPFProgramType.XDP)
                
                assert program_id is not None
                assert program_id.startswith("xdp_")
                assert program_id in loader.loaded_programs
            finally:
                Path(temp_path).unlink()
    
    def test_attach_to_interface_program_not_loaded(self):
        """Test that attaching non-loaded program raises error"""
        loader = EBPFLoader()
        
        with pytest.raises(EBPFAttachError):
            loader.attach_to_interface("nonexistent", "eth0")
    
    @patch('src.network.ebpf.loader.Path.exists')
    @patch('src.network.ebpf.loader.subprocess.run')
    def test_attach_to_interface_interface_not_found(self, mock_subprocess, mock_exists):
        """Test that attaching to non-existent interface raises error"""
        loader = EBPFLoader()
        
        # Mock program loaded
        loader.loaded_programs["test_prog"] = {
            "path": "/test/path.o",
            "type": EBPFProgramType.XDP,
            "loaded": True
        }
        
        # Mock interface not found
        mock_exists.return_value = False
        
        with pytest.raises(EBPFAttachError):
            loader.attach_to_interface("test_prog", "nonexistent")
    
    @patch('src.network.ebpf.loader.subprocess.run')
    @patch('pathlib.Path.exists')
    def test_attach_xdp_program_success(self, mock_exists, mock_subprocess):
        """Test successful XDP program attachment"""
        loader = EBPFLoader()
        
        # Mock program loaded
        loader.loaded_programs["test_prog"] = {
            "path": "/test/xdp_counter.o",
            "type": EBPFProgramType.XDP,
            "loaded": True,
            "pinned_path": None
        }
        
        # Since Path.exists is an instance method, we need to patch it at the class level
        # and make it return True for paths containing "eth0"
        original_exists = Path.exists
        
        def patched_exists(self):
            path_str = str(self)
            if "eth0" in path_str:
                return True
            return original_exists(self)
        
        # Also patch Path.read_text for operstate file
        original_read_text = Path.read_text
        
        def patched_read_text(self):
            path_str = str(self)
            if "operstate" in path_str and "eth0" in path_str:
                return "up"
            return original_read_text(self)
        
        with patch.object(Path, 'exists', patched_exists), \
             patch.object(Path, 'read_text', patched_read_text):
            # Mock subprocess.run to handle both attachment and verification calls
            def subprocess_side_effect(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "ip link set" in cmd_str:
                    # Attachment command
                    return Mock(returncode=0, stdout="", stderr="")
                elif "ip link show" in cmd_str:
                    # Verification command - must contain "xdp" in output
                    return Mock(returncode=0, stdout="eth0: <BROADCAST,MULTICAST,UP,LOWER_UP> xdp generic", stderr="")
                return Mock(returncode=0, stdout="", stderr="")
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            success = loader.attach_to_interface("test_prog", "eth0", EBPFAttachMode.SKB)
            
            assert success is True
            assert "eth0" in loader.attached_interfaces
            assert len(loader.attached_interfaces["eth0"]) > 0
            assert loader.attached_interfaces["eth0"][0]["program_id"] == "test_prog"
    
    def test_detach_from_interface(self):
        """Test detaching program from interface"""
        loader = EBPFLoader()
        
        # Setup: program attached with correct data structure
        loader.loaded_programs["test_prog"] = {
            "path": "/test/path.o",
            "type": EBPFProgramType.XDP,
            "attached_to": "eth0"
        }
        loader.attached_interfaces["eth0"] = [{
            "program_id": "test_prog",
            "type": EBPFProgramType.XDP,
            "mode": EBPFAttachMode.SKB,
            "attached_at": time.time()
        }]
        
        with patch('src.network.ebpf.loader.subprocess.run') as mock_subprocess:
            # Configure mock to handle both detach and verification calls
            def subprocess_side_effect(cmd, *args, **kwargs):
                cmd_str = " ".join(cmd)
                if "ip link set" in cmd_str:
                    # Detach command
                    return Mock(returncode=0, stdout="", stderr="")
                elif "ip link show" in cmd_str:
                    # Verification command - should NOT contain "xdp" after detach
                    return Mock(returncode=0, stdout="eth0: <BROADCAST,MULTICAST,UP,LOWER_UP>", stderr="")
                return Mock(returncode=0, stdout="", stderr="")
            
            mock_subprocess.side_effect = subprocess_side_effect
            
            success = loader.detach_from_interface("test_prog", "eth0")
            
            assert success is True
            assert len(loader.attached_interfaces.get("eth0", [])) == 0
    
    def test_unload_program(self):
        """Test unloading program"""
        loader = EBPFLoader()
        
        # Setup: program loaded
        loader.loaded_programs["test_prog"] = {
            "path": "/test/path.o",
            "type": EBPFProgramType.XDP,
            "pinned_path": None
        }
        
        success = loader.unload_program("test_prog")
        
        assert success is True
        assert "test_prog" not in loader.loaded_programs
    
    def test_list_loaded_programs(self):
        """Test listing loaded programs"""
        loader = EBPFLoader()
        
        loader.loaded_programs["prog1"] = {"type": EBPFProgramType.XDP}
        loader.loaded_programs["prog2"] = {"type": EBPFProgramType.TC}
        
        programs = loader.list_loaded_programs()
        
        assert len(programs) == 2
        assert any(p["id"] == "prog1" for p in programs)
        assert any(p["id"] == "prog2" for p in programs)
    
    def test_get_interface_programs(self):
        """Test getting programs attached to interface"""
        loader = EBPFLoader()
        
        loader.attached_interfaces["eth0"] = [
            {
                "program_id": "prog1",
                "type": EBPFProgramType.XDP,
                "mode": EBPFAttachMode.SKB,
                "attached_at": time.time()
            },
            {
                "program_id": "prog2",
                "type": EBPFProgramType.TC,
                "mode": EBPFAttachMode.DRV,
                "attached_at": time.time()
            }
        ]
        
        programs = loader.get_interface_programs("eth0")
        
        assert len(programs) == 2
        assert "prog1" in programs
        assert "prog2" in programs


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

