"""
Unit tests for eBPF Loader

Tests the core eBPF program lifecycle:
- Loading programs from .o files
- Attaching to network interfaces
- Detaching and unloading
- Error handling
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.network.ebpf.loader import (EBPFAttachError, EBPFAttachMode,
                                     EBPFLoader, EBPFLoadError,
                                     EBPFProgramType)


class TestEBPFLoader:
    """Test suite for EBPFLoader class"""

    def test_loader_initialization(self, tmp_path):
        """Test loader initializes with correct defaults"""
        loader = EBPFLoader(programs_dir=tmp_path)
        assert loader.programs_dir == tmp_path
        assert len(loader.loaded_programs) == 0
        assert len(loader.attached_interfaces) == 0

    def test_load_program_file_not_found(self, tmp_path):
        """Test loading non-existent program raises error"""
        loader = EBPFLoader(programs_dir=tmp_path)

        with pytest.raises(EBPFLoadError, match="not found"):
            loader.load_program("nonexistent.o")

    def test_load_program_invalid_extension(self, tmp_path):
        """Test loading file with wrong extension raises error"""
        loader = EBPFLoader(programs_dir=tmp_path)

        # Create a .txt file instead of .o
        invalid_file = tmp_path / "program.txt"
        invalid_file.write_text("not an eBPF program")

        with pytest.raises(EBPFLoadError, match="Invalid.*Expected .o"):
            loader.load_program("program.txt")

    def test_load_program_success(self, tmp_path):
        """Test successful program loading"""
        loader = EBPFLoader(programs_dir=tmp_path)

        # Create a minimal ELF header
        program_file = tmp_path / "test_xdp.o"
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)

        # Mock _load_via_bpftool to avoid actual bpftool call
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o", EBPFProgramType.XDP)

            assert program_id is not None
            assert program_id in loader.loaded_programs
            assert loader.loaded_programs[program_id]["type"] == EBPFProgramType.XDP
            assert loader.loaded_programs[program_id]["loaded"] is True

    def test_attach_to_interface_program_not_loaded(self):
        """Test attaching non-existent program raises error"""
        loader = EBPFLoader()

        with pytest.raises(EBPFAttachError, match="not loaded"):
            loader.attach_to_interface("fake_id", "eth0")

    def test_attach_to_interface_success(self, tmp_path):
        """Test successful interface attachment"""
        loader = EBPFLoader(programs_dir=tmp_path)

        # Load a program first
        program_file = tmp_path / "test_xdp.o"
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)
        # Mock _load_via_bpftool to avoid actual bpftool call
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o")

        # Attach to interface - mock interface check and XDP verification
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="up"),
            patch(
                "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
            ),
            patch.object(loader, "_verify_xdp_attachment", return_value=True),
        ):
            result = loader.attach_to_interface(program_id, "eth0", EBPFAttachMode.SKB)

            assert result is True
            assert "eth0" in loader.attached_interfaces
            assert any(
                att.get("program_id") == program_id
                for att in loader.attached_interfaces["eth0"]
            )
            assert loader.loaded_programs[program_id]["attached_to"] == "eth0"

    def test_attach_twice_same_interface(self, tmp_path):
        """Test attaching same program twice returns success but doesn't duplicate"""
        loader = EBPFLoader(programs_dir=tmp_path)

        program_file = tmp_path / "test_xdp.o"
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)
        # Mock _load_via_bpftool
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o")

        # Attach twice - mock interface check
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="up"),
            patch(
                "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
            ),
            patch.object(loader, "_verify_xdp_attachment", return_value=True),
        ):
            loader.attach_to_interface(program_id, "eth0")
            result = loader.attach_to_interface(program_id, "eth0")

            assert result is True
            assert len(loader.attached_interfaces["eth0"]) == 1

    def test_detach_from_interface_success(self, tmp_path):
        """Test successful detachment"""
        loader = EBPFLoader(programs_dir=tmp_path)

        program_file = tmp_path / "test_xdp.o"
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)
        # Mock _load_via_bpftool
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o")

        # Mock interface check for attach
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="up"),
            patch(
                "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
            ),
            patch.object(loader, "_verify_xdp_attachment", return_value=True),
        ):
            loader.attach_to_interface(program_id, "eth0")

        # Detach - mock subprocess
        with patch(
            "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
        ):
            result = loader.detach_from_interface(program_id, "eth0")

        assert result is True
        assert program_id not in loader.attached_interfaces.get("eth0", [])
        assert "attached_to" not in loader.loaded_programs[program_id]

    def test_unload_program_success(self, tmp_path):
        """Test successful program unload"""
        loader = EBPFLoader(programs_dir=tmp_path)

        program_file = tmp_path / "test_xdp.o"
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)
        # Mock _load_via_bpftool
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o")

        result = loader.unload_program(program_id)

        assert result is True
        assert program_id not in loader.loaded_programs

    def test_unload_attached_program_auto_detaches(self, tmp_path):
        """Test unloading attached program automatically detaches it"""
        loader = EBPFLoader(programs_dir=tmp_path)

        program_file = tmp_path / "test_xdp.o"
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)
        # Mock _load_via_bpftool
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o")

        # Mock interface check for attach
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="up"),
            patch(
                "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
            ),
            patch.object(loader, "_verify_xdp_attachment", return_value=True),
        ):
            loader.attach_to_interface(program_id, "eth0")

        # Unload should auto-detach - mock subprocess
        with patch(
            "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
        ):
            result = loader.unload_program(program_id)

            assert result is True
            assert program_id not in loader.loaded_programs
            assert not any(
                att.get("program_id") == program_id
                for att in loader.attached_interfaces.get("eth0", [])
            )

    def test_list_loaded_programs(self, tmp_path):
        """Test listing all loaded programs"""
        loader = EBPFLoader(programs_dir=tmp_path)

        # Load two programs
        for i in range(2):
            program_file = tmp_path / f"test_{i}.o"
            # Create minimal ELF header
            elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
            program_file.write_bytes(elf_header)
            # Mock _load_via_bpftool to avoid actual bpftool call
            with patch.object(loader, "_load_via_bpftool") as mock_load:
                mock_load.return_value = (123 + i, f"/sys/fs/bpf/test_{i}")
                loader.load_program(f"test_{i}.o")

        programs = loader.list_loaded_programs()

        assert len(programs) == 2
        assert all("id" in prog for prog in programs)

    def test_get_interface_programs(self, tmp_path):
        """Test getting programs attached to specific interface"""
        loader = EBPFLoader(programs_dir=tmp_path)

        program_file = tmp_path / "test_xdp.o"
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        program_file.write_bytes(elf_header)
        # Mock _load_via_bpftool
        with patch.object(loader, "_load_via_bpftool") as mock_load:
            mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
            program_id = loader.load_program("test_xdp.o")

        # Mock interface check for attach
        with (
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="up"),
            patch(
                "subprocess.run", return_value=Mock(returncode=0, stdout="", stderr="")
            ),
            patch.object(loader, "_verify_xdp_attachment", return_value=True),
        ):
            loader.attach_to_interface(program_id, "eth0")

        programs = loader.get_interface_programs("eth0")

        assert len(programs) == 1
        assert program_id in programs


class TestEBPFProgramType:
    """Test eBPF program type enum"""

    def test_program_types_exist(self):
        """Verify all expected program types are defined"""
        assert EBPFProgramType.XDP.value == "xdp"
        assert EBPFProgramType.TC.value == "tc"
        assert EBPFProgramType.CGROUP_SKB.value == "cgroup_skb"
        assert EBPFProgramType.SOCKET_FILTER.value == "socket_filter"


class TestEBPFAttachMode:
    """Test XDP attach mode enum"""

    def test_attach_modes_exist(self):
        """Verify all XDP attach modes are defined"""
        assert EBPFAttachMode.SKB.value == "skb"
        assert EBPFAttachMode.DRV.value == "drv"
        assert EBPFAttachMode.HW.value == "hw"
