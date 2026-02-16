"""
Tests for EBPFLoader - core eBPF program loading functionality.

These tests cover:
- Program loading and unloading
- Interface attachment/detachment
- Statistics gathering
- Route updates
- Error handling
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.network.ebpf.loader import (EBPFAttachError, EBPFAttachMode,
                                     EBPFLoader, EBPFLoadError,
                                     EBPFProgramType)


@pytest.fixture
def temp_ebpf_file():
    """Create temporary eBPF object file for testing."""
    with tempfile.NamedTemporaryFile(mode="wb", suffix=".o", delete=False) as f:
        # Create a minimal valid ELF file structure
        # This is a simplified ELF header (not a real eBPF program)
        elf_header = b"\x7fELF"  # ELF magic
        elf_header += b"\x02\x01\x01\x00"  # 64-bit, little-endian
        elf_header += b"\x00" * 0x10
        elf_header += b"\x02"  # Type: ET_EXEC
        elf_header += b"\x3e\x00"  # Machine: EM_X86_64
        elf_header += b"\x01\x00\x00\x00"  # Version
        elf_header += b"\x00" * 0x38

        f.write(elf_header)
        return f.name


@pytest.fixture
def temp_programs_dir():
    """Create temporary directory for eBPF programs."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def loader(temp_programs_dir):
    """Create EBPFLoader instance for testing."""
    return EBPFLoader(programs_dir=temp_programs_dir)


@pytest.fixture
def mock_safe_run():
    """Mock safe_run function."""
    with patch("src.network.ebpf.loader.safe_run") as mock:
        yield mock


@pytest.fixture
def mock_subprocess_run():
    """Mock subprocess.run."""
    with patch("src.network.ebpf.loader.subprocess.run") as mock:
        yield mock


class TestEBPFLoader:
    """Tests for EBPFLoader class."""

    def test_initialization(self, loader):
        """Test EBPFLoader initialization."""
        assert isinstance(loader, EBPFLoader)
        assert len(loader.loaded_programs) == 0
        assert len(loader.attached_interfaces) == 0
        assert isinstance(loader.programs_dir, Path)

    def test_load_program_valid_file(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test loading a valid eBPF program file."""
        # Copy temporary file to programs directory
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)
            assert isinstance(program_id, str)
            assert len(program_id) > 0
            assert program_id in loader.loaded_programs

    def test_load_program_invalid_format(self, loader):
        """Test loading invalid file format."""
        invalid_file = loader.programs_dir / "invalid.txt"
        with open(invalid_file, "w") as f:
            f.write("not an eBPF program")

        with pytest.raises(EBPFLoadError):
            loader.load_program(invalid_file.name, EBPFProgramType.XDP)

    def test_load_program_file_not_found(self, loader):
        """Test loading non-existent file."""
        with pytest.raises(EBPFLoadError):
            loader.load_program("nonexistent.o", EBPFProgramType.XDP)

    @patch("src.network.ebpf.loader.ELFFile")
    def test_parse_elf_sections(self, mock_elf_file, loader, temp_ebpf_file):
        """Test ELF section parsing."""
        # Copy temporary file to programs directory
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Create mock ELF sections
        mock_section1 = MagicMock()
        mock_section1.name = ".text"
        mock_section1.data.return_value = b"\x00" * 100
        mock_section1.data_size = 100

        mock_section2 = MagicMock()
        mock_section2.name = ".maps"
        mock_section2.data.return_value = b"\x00" * 50
        mock_section2.data_size = 50

        mock_section3 = MagicMock()
        mock_section3.name = "license"
        mock_section3.data.return_value = b"GPL"
        mock_section3.data_size = 3

        mock_elf = MagicMock()
        mock_elf.iter_sections.return_value = [
            mock_section1,
            mock_section2,
            mock_section3,
        ]

        mock_elf_file.return_value = mock_elf

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", True):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)
            program = loader.loaded_programs[program_id]

            assert program["sections"] == [".text", ".maps", "license"]
            assert program["text_size"] == 100
            assert program["has_maps"] == True
            assert program["license"] == "GPL"

    def test_attach_to_interface_valid(
        self, loader, temp_ebpf_file, mock_subprocess_run
    ):
        """Test attaching program to valid interface."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load and attach
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["ip", "link", "show", "dev", "eth0"]:
                return MagicMock(
                    returncode=0, stdout="eth0: xdp program attached", stderr=""
                )
            return MagicMock(returncode=0, stdout="12345", stderr="")

        mock_subprocess_run.side_effect = mock_run_side_effect

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            # Mock interface up check
            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    success = loader.attach_to_interface(program_id, "eth0")
                    assert success is True

            assert "eth0" in loader.attached_interfaces
            assert len(loader.attached_interfaces["eth0"]) == 1
            assert loader.attached_interfaces["eth0"][0]["program_id"] == program_id

    def test_attach_to_nonexistent_interface(
        self, loader, temp_ebpf_file, mock_subprocess_run
    ):
        """Test attaching to non-existent network interface."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            with patch("pathlib.Path.exists", return_value=False):
                with pytest.raises(EBPFAttachError):
                    loader.attach_to_interface(program_id, "nonexistent")

    def test_detach_from_interface(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test detaching program from interface."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Track attachment state
        is_attached = [True]

        # Mock successful bpftool load and attach/detach
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["ip", "link", "show", "dev", "eth0"]:
                if is_attached[0]:
                    return MagicMock(
                        returncode=0, stdout="eth0: xdp program attached", stderr=""
                    )
                else:
                    return MagicMock(returncode=0, stdout="eth0: xdp off", stderr="")
            if cmd == ["ip", "link", "set", "dev", "eth0", "xdp", "off"]:
                is_attached[0] = False
                return MagicMock(returncode=0, stdout="", stderr="")
            return MagicMock(returncode=0, stdout="12345", stderr="")

        mock_subprocess_run.side_effect = mock_run_side_effect

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    loader.attach_to_interface(program_id, "eth0")
                    assert len(loader.attached_interfaces["eth0"]) == 1

                success = loader.detach_from_interface(program_id, "eth0")
                assert success is True
                assert "eth0" not in loader.attached_interfaces

    def test_detach_from_nonexistent_interface(
        self, loader, temp_ebpf_file, mock_subprocess_run
    ):
        """Test detaching from non-existent interface."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            # Detaching from non-existent interface should return False (graceful handling)
            result = loader.detach_from_interface(program_id, "nonexistent")
            assert result is False

    def test_unload_program(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test unloading program."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load and unload
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)
            assert program_id in loader.loaded_programs

            success = loader.unload_program(program_id)
            assert success is True
            assert program_id not in loader.loaded_programs

    def test_unload_attached_program(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test trying to unload attached program."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load and attach
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["ip", "link", "show", "dev", "eth0"]:
                return MagicMock(
                    returncode=0, stdout="eth0: xdp program attached", stderr=""
                )
            return MagicMock(returncode=0, stdout="12345", stderr="")

        mock_subprocess_run.side_effect = mock_run_side_effect

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    loader.attach_to_interface(program_id, "eth0")

            # Unloading attached program should auto-detach and succeed (graceful handling)
            success = loader.unload_program(program_id)
            assert success is True
            assert program_id not in loader.loaded_programs

    def test_list_loaded_programs(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test listing loaded programs."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            programs = loader.list_loaded_programs()
            assert len(programs) == 1
            assert programs[0]["id"] == program_id

    def test_get_stats(self, loader, mock_subprocess_run):
        """Test getting eBPF stats from maps."""
        # Mock successful bpftool map dump with JSON output
        mock_json_output = """[
            {"key": 0, "value": 100},
            {"key": 1, "value": 80},
            {"key": 2, "value": 20},
            {"key": 3, "value": 60}
        ]"""

        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=mock_json_output.encode("utf-8"), stderr=b""
        )

        stats = loader.get_stats()
        assert isinstance(stats, dict)
        assert stats["total_packets"] == 100
        assert stats["passed_packets"] == 80
        assert stats["dropped_packets"] == 20
        assert stats["forwarded_packets"] == 60

    def test_get_stats_no_bpftool(self, loader):
        """Test stats retrieval when bpftool not available."""
        with patch(
            "src.network.ebpf.loader.subprocess.run", side_effect=FileNotFoundError
        ):
            stats = loader.get_stats()

            assert stats["total_packets"] == 0
            assert stats["passed_packets"] == 0
            assert stats["dropped_packets"] == 0
            assert stats["forwarded_packets"] == 0

    def test_update_routes(self, loader, mock_subprocess_run):
        """Test updating mesh routing table in eBPF map."""
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"", stderr=b""
        )

        routes = {"192.168.1.100": "1", "10.0.0.50": "2"}

        success = loader.update_routes(routes)
        assert success is True
        assert mock_subprocess_run.call_count == len(routes)

    def test_update_routes_bpftool_not_found(self, loader):
        """Test route updates when bpftool not found."""
        with patch(
            "src.network.ebpf.loader.subprocess.run", side_effect=FileNotFoundError
        ):
            routes = {"192.168.1.100": "1"}
            success = loader.update_routes(routes)
            assert success is False

    def test_cleanup(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test cleaning up all eBPF programs."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load and attach
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["ip", "link", "show", "dev", "eth0"]:
                return MagicMock(
                    returncode=0, stdout="eth0: xdp program attached", stderr=""
                )
            return MagicMock(returncode=0, stdout="12345", stderr="")

        mock_subprocess_run.side_effect = mock_run_side_effect

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    loader.attach_to_interface(program_id, "eth0")

            assert len(loader.loaded_programs) == 1
            assert len(loader.attached_interfaces) == 1

            loader.cleanup()

            assert len(loader.loaded_programs) == 0
            assert len(loader.attached_interfaces) == 0

    def test_load_programs_directory_scan(
        self, loader, temp_ebpf_file, mock_subprocess_run
    ):
        """Test loading all programs from directory."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_ids = loader.load_programs()

            assert len(program_ids) == 1
            assert len(loader.loaded_programs) == 1
            assert program_ids[0] in loader.loaded_programs

    def test_get_interface_programs(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test getting programs attached to specific interface."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load and attach
        def mock_run_side_effect(cmd, **kwargs):
            if cmd == ["ip", "link", "show", "dev", "eth0"]:
                return MagicMock(
                    returncode=0, stdout="eth0: xdp program attached", stderr=""
                )
            return MagicMock(returncode=0, stdout="12345", stderr="")

        mock_subprocess_run.side_effect = mock_run_side_effect

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    loader.attach_to_interface(program_id, "eth0")

            programs = loader.get_interface_programs("eth0")
            assert len(programs) == 1
            assert programs[0] == program_id

            # Test with non-existent interface
            assert len(loader.get_interface_programs("nonexistent")) == 0

    def test_load_program_without_btf(
        self, loader, temp_ebpf_file, mock_subprocess_run
    ):
        """Test loading program without BTF metadata."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.XDP)

            assert program_id in loader.loaded_programs
            assert loader.loaded_programs[program_id]["has_btf"] == False

    def test_verify_xdp_attachment(self, loader, mock_subprocess_run):
        """Test XDP attachment verification."""
        # Mock successful verification
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"eth0: xdp program attached", stderr=b""
        )

        with patch.object(loader, "_verify_xdp_attachment") as mock_verify:
            mock_verify.return_value = True

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    program_id = "test_program"
                    with patch.object(loader, "load_program", return_value=program_id):
                        with patch.object(
                            loader,
                            "loaded_programs",
                            {program_id: {"type": EBPFProgramType.XDP}},
                        ):
                            dest_file = loader.programs_dir / "test.o"
                            with open(dest_file, "wb") as f:
                                f.write(b"\x00")

                            success = loader._attach_xdp(
                                str(dest_file), "eth0", EBPFAttachMode.SKB
                            )
                            assert success is True

    def test_attach_tc_program(self, loader, temp_ebpf_file, mock_subprocess_run):
        """Test attaching TC program."""
        dest_file = loader.programs_dir / os.path.basename(temp_ebpf_file)
        with open(dest_file, "wb") as f:
            with open(temp_ebpf_file, "rb") as src:
                f.write(src.read())

        # Mock successful bpftool load and attach
        mock_subprocess_run.return_value = MagicMock(
            returncode=0, stdout=b"12345", stderr=b""
        )

        with patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False):
            program_id = loader.load_program(dest_file.name, EBPFProgramType.TC)

            with patch("pathlib.Path.exists", return_value=True):
                with patch("pathlib.Path.read_text", return_value="up"):
                    success = loader.attach_to_interface(program_id, "eth0")
                    assert success is True

            assert "eth0" in loader.attached_interfaces
            assert len(loader.attached_interfaces["eth0"]) == 1
            assert loader.attached_interfaces["eth0"][0]["type"] == EBPFProgramType.TC


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
