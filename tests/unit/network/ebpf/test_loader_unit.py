"""
Unit tests for src/network/ebpf/loader.py - EBPFLoader.

Covers:
- EBPFLoader initialization
- load_program: success, file-not-found, bad extension, ELF parsing, bpftool
- attach_to_interface: XDP/TC attach, mode fallback, already-attached, errors
- detach_from_interface: XDP/TC detach, not-found cases
- unload_program: normal, with pinned path, still-attached auto-detach
- list_loaded_programs, get_interface_programs, get_stats, update_routes
- cleanup, load_programs (batch)
- _parse_elf_sections with/without elftools
- _verify_xdp_attachment, _verify_attachment
- _try_bpftool_attach
"""

import json
import subprocess
import time
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, call, mock_open, patch

import pytest

from src.network.ebpf.loader import (
    EBPFAttachError,
    EBPFAttachMode,
    EBPFLoadError,
    EBPFLoader,
    EBPFProgramType,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def loader(tmp_path):
    """Create an EBPFLoader with a tmp programs directory."""
    return EBPFLoader(programs_dir=tmp_path)


@pytest.fixture
def loader_with_program(loader, tmp_path):
    """Create loader with a fake .o file on disk and a pre-loaded program entry."""
    prog_file = tmp_path / "test_prog.o"
    prog_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

    program_id = "xdp_test_prog_12345"
    loader.loaded_programs[program_id] = {
        "path": str(prog_file),
        "type": EBPFProgramType.XDP,
        "loaded": True,
        "size_bytes": prog_file.stat().st_size,
        "sections": [],
        "text_size": 0,
        "has_btf": False,
        "has_maps": False,
        "license": "GPL",
        "pinned_path": None,
        "prog_fd": None,
    }
    return loader, program_id


# ---------------------------------------------------------------------------
# Enum / Exception basics
# ---------------------------------------------------------------------------

class TestEnums:
    def test_program_types(self):
        assert EBPFProgramType.XDP.value == "xdp"
        assert EBPFProgramType.TC.value == "tc"
        assert EBPFProgramType.CGROUP_SKB.value == "cgroup_skb"
        assert EBPFProgramType.SOCKET_FILTER.value == "socket_filter"

    def test_attach_modes(self):
        assert EBPFAttachMode.SKB.value == "skb"
        assert EBPFAttachMode.DRV.value == "drv"
        assert EBPFAttachMode.HW.value == "hw"

    def test_exceptions(self):
        with pytest.raises(EBPFLoadError):
            raise EBPFLoadError("load err")
        with pytest.raises(EBPFAttachError):
            raise EBPFAttachError("attach err")


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

class TestInit:
    def test_default_programs_dir(self):
        loader = EBPFLoader()
        assert loader.programs_dir == Path(__file__).parent / ".." / ".." / ".." / ".." / "src" / "network" / "ebpf" / "programs" or "programs" in str(loader.programs_dir)
        assert loader.loaded_programs == {}
        assert loader.attached_interfaces == {}

    def test_custom_programs_dir(self, tmp_path):
        loader = EBPFLoader(programs_dir=tmp_path)
        assert loader.programs_dir == tmp_path


# ---------------------------------------------------------------------------
# _parse_elf_sections
# ---------------------------------------------------------------------------

class TestParseElfSections:
    @patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", False)
    def test_no_elftools(self, loader, tmp_path):
        fake_file = tmp_path / "prog.o"
        fake_file.write_bytes(b"\x7fELF")
        result = loader._parse_elf_sections(fake_file)
        assert result == {}

    @patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", True)
    def test_with_elftools_success(self, loader, tmp_path):
        fake_file = tmp_path / "prog.o"
        fake_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        mock_section_text = MagicMock()
        mock_section_text.name = ".text"
        mock_section_text.data.return_value = b"\xb7\x00\x00\x00\x02"
        mock_section_text.data_size = 5
        mock_section_text.__getitem__ = lambda self, key: 0x40 if key == "sh_offset" else None

        mock_section_license = MagicMock()
        mock_section_license.name = "license"
        mock_section_license.data.return_value = b"GPL\x00"
        mock_section_license.data_size = 4
        mock_section_license.__getitem__ = lambda self, key: 0x80 if key == "sh_offset" else None

        mock_section_btf = MagicMock()
        mock_section_btf.name = ".BTF"
        mock_section_btf.data.return_value = b"\x00" * 16
        mock_section_btf.data_size = 16
        mock_section_btf.__getitem__ = lambda self, key: 0xC0 if key == "sh_offset" else None

        mock_section_maps = MagicMock()
        mock_section_maps.name = ".maps"
        mock_section_maps.data.return_value = b"\x00" * 8
        mock_section_maps.data_size = 8
        mock_section_maps.__getitem__ = lambda self, key: 0x100 if key == "sh_offset" else None

        # A section that should be ignored
        mock_section_other = MagicMock()
        mock_section_other.name = ".rodata"

        mock_elf = MagicMock()
        mock_elf.iter_sections.return_value = [
            mock_section_text,
            mock_section_license,
            mock_section_btf,
            mock_section_maps,
            mock_section_other,
        ]

        with patch("src.network.ebpf.loader.ELFFile", return_value=mock_elf):
            result = loader._parse_elf_sections(fake_file)

        assert ".text" in result
        assert result[".text"]["size"] == 5
        assert "license" in result
        assert result["license"]["text"] == "GPL"
        assert ".BTF" in result
        assert ".maps" in result
        assert ".rodata" not in result

    @patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", True)
    def test_license_decode_failure(self, loader, tmp_path):
        fake_file = tmp_path / "prog.o"
        fake_file.write_bytes(b"\x7fELF" + b"\x00" * 100)

        mock_section_license = MagicMock()
        mock_section_license.name = "license"
        bad_bytes = b"\xff\xfe"
        mock_section_license.data.return_value = bad_bytes
        mock_section_license.data_size = 2
        mock_section_license.__getitem__ = lambda self, key: 0

        # Make decode raise
        mock_data = MagicMock()
        mock_data.decode.side_effect = UnicodeDecodeError("utf-8", b"", 0, 1, "bad")
        mock_section_license.data.return_value = mock_data

        mock_elf = MagicMock()
        mock_elf.iter_sections.return_value = [mock_section_license]

        with patch("src.network.ebpf.loader.ELFFile", return_value=mock_elf):
            result = loader._parse_elf_sections(fake_file)
        # Should not crash; license section exists but has no 'text' key
        assert "license" in result
        assert "text" not in result["license"]

    @patch("src.network.ebpf.loader.ELF_TOOLS_AVAILABLE", True)
    def test_elf_parse_exception(self, loader, tmp_path):
        fake_file = tmp_path / "prog.o"
        fake_file.write_bytes(b"\x7fELF")

        with patch("src.network.ebpf.loader.ELFFile", side_effect=Exception("bad elf")):
            result = loader._parse_elf_sections(fake_file)
        assert result == {}


# ---------------------------------------------------------------------------
# _load_via_bpftool
# ---------------------------------------------------------------------------

class TestLoadViaBpftool:
    def test_bpftool_not_found(self, loader, tmp_path):
        prog = tmp_path / "test.o"
        prog.write_bytes(b"\x7fELF")

        mock_result = MagicMock()
        mock_result.returncode = 1  # which bpftool not found
        with patch("src.network.ebpf.loader.safe_run", return_value=mock_result):
            fd, path = loader._load_via_bpftool(prog, EBPFProgramType.XDP)
        assert fd is None and path is None

    def test_bpftool_load_success(self, loader, tmp_path):
        prog = tmp_path / "test.o"
        prog.write_bytes(b"\x7fELF")

        which_result = MagicMock(returncode=0)
        load_result = MagicMock(returncode=0)

        with patch("src.network.ebpf.loader.safe_run", side_effect=[which_result, load_result]):
            with patch.object(Path, "mkdir"):
                fd, path = loader._load_via_bpftool(prog, EBPFProgramType.XDP)
        assert fd is None
        assert path is not None
        assert "x0tta6bl4_test" in path

    def test_bpftool_load_failure(self, loader, tmp_path):
        prog = tmp_path / "test.o"
        prog.write_bytes(b"\x7fELF")

        which_result = MagicMock(returncode=0)
        load_result = MagicMock(returncode=1, stderr="permission denied")

        with patch("src.network.ebpf.loader.safe_run", side_effect=[which_result, load_result]):
            with patch.object(Path, "mkdir"):
                fd, path = loader._load_via_bpftool(prog, EBPFProgramType.XDP)
        assert fd is None and path is None

    def test_bpftool_file_not_found(self, loader, tmp_path):
        prog = tmp_path / "test.o"
        prog.write_bytes(b"\x7fELF")

        with patch("src.network.ebpf.loader.safe_run", side_effect=FileNotFoundError):
            fd, path = loader._load_via_bpftool(prog, EBPFProgramType.XDP)
        assert fd is None and path is None

    def test_bpftool_timeout(self, loader, tmp_path):
        prog = tmp_path / "test.o"
        prog.write_bytes(b"\x7fELF")

        with patch("src.network.ebpf.loader.safe_run", side_effect=subprocess.TimeoutExpired("bpftool", 10)):
            fd, path = loader._load_via_bpftool(prog, EBPFProgramType.XDP)
        assert fd is None and path is None

    def test_bpftool_generic_exception(self, loader, tmp_path):
        prog = tmp_path / "test.o"
        prog.write_bytes(b"\x7fELF")

        with patch("src.network.ebpf.loader.safe_run", side_effect=RuntimeError("unexpected")):
            fd, path = loader._load_via_bpftool(prog, EBPFProgramType.XDP)
        assert fd is None and path is None


# ---------------------------------------------------------------------------
# load_program
# ---------------------------------------------------------------------------

class TestLoadProgram:
    def test_file_not_found(self, loader, tmp_path):
        with pytest.raises(EBPFLoadError, match="not found"):
            loader.load_program("nonexistent.o")

    def test_invalid_extension(self, loader, tmp_path):
        bad_file = tmp_path / "prog.c"
        bad_file.write_text("int main() {}")
        with pytest.raises(EBPFLoadError, match="Invalid"):
            loader.load_program("prog.c")

    def test_load_success_with_bpftool(self, loader, tmp_path):
        prog = tmp_path / "xdp_filter.o"
        prog.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with patch.object(loader, "_parse_elf_sections", return_value={
            ".text": {"data": b"\x00", "size": 10, "offset": 0},
            "license": {"data": b"GPL", "size": 3, "offset": 0, "text": "GPL"},
        }):
            with patch.object(loader, "_load_via_bpftool", return_value=(None, "/sys/fs/bpf/x0tta6bl4_xdp_filter")):
                pid = loader.load_program("xdp_filter.o", EBPFProgramType.XDP)

        assert pid in loader.loaded_programs
        assert loader.loaded_programs[pid]["loaded"] is True
        assert loader.loaded_programs[pid]["pinned_path"] == "/sys/fs/bpf/x0tta6bl4_xdp_filter"

    def test_load_success_without_bpftool_with_sections(self, loader, tmp_path):
        """When bpftool fails but ELF sections were parsed, load still succeeds."""
        prog = tmp_path / "xdp_prog.o"
        prog.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with patch.object(loader, "_parse_elf_sections", return_value={
            ".text": {"data": b"\x00", "size": 10, "offset": 0},
        }):
            with patch.object(loader, "_load_via_bpftool", return_value=(None, None)):
                pid = loader.load_program("xdp_prog.o")

        assert pid in loader.loaded_programs
        assert loader.loaded_programs[pid]["pinned_path"] is None

    def test_load_fails_no_sections_no_bpftool(self, loader, tmp_path):
        """When both ELF parsing returns empty and bpftool fails, should raise."""
        prog = tmp_path / "bad_prog.o"
        prog.write_bytes(b"\x7fELF" + b"\x00" * 10)

        with patch.object(loader, "_parse_elf_sections", return_value={}):
            with patch.object(loader, "_load_via_bpftool", return_value=(None, None)):
                with pytest.raises(EBPFLoadError, match="Invalid eBPF program"):
                    loader.load_program("bad_prog.o")

    def test_load_non_gpl_license_warning(self, loader, tmp_path):
        prog = tmp_path / "proprietary.o"
        prog.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with patch.object(loader, "_parse_elf_sections", return_value={
            ".text": {"data": b"\x00", "size": 10, "offset": 0},
            "license": {"data": b"MIT", "size": 3, "offset": 0, "text": "MIT"},
        }):
            with patch.object(loader, "_load_via_bpftool", return_value=(None, "/sys/fs/bpf/test")):
                pid = loader.load_program("proprietary.o")
        assert loader.loaded_programs[pid]["license"] == "MIT"

    def test_load_tc_program(self, loader, tmp_path):
        prog = tmp_path / "tc_classifier.o"
        prog.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with patch.object(loader, "_parse_elf_sections", return_value={".text": {"data": b"", "size": 5, "offset": 0}}):
            with patch.object(loader, "_load_via_bpftool", return_value=(None, None)):
                pid = loader.load_program("tc_classifier.o", EBPFProgramType.TC)

        assert "tc_" in pid
        assert loader.loaded_programs[pid]["type"] == EBPFProgramType.TC

    def test_load_records_metrics(self, loader, tmp_path):
        prog = tmp_path / "prog.o"
        prog.write_bytes(b"\x7fELF" + b"\x00" * 100)

        with patch.object(loader, "_parse_elf_sections", return_value={".text": {"data": b"", "size": 5, "offset": 0}}):
            with patch.object(loader, "_load_via_bpftool", return_value=(None, None)):
                with patch("src.network.ebpf.loader.record_ebpf_event") as mock_event:
                    with patch("src.network.ebpf.loader.record_ebpf_compilation") as mock_comp:
                        pid = loader.load_program("prog.o")
                        mock_event.assert_called_once_with("program_load", "xdp")
                        mock_comp.assert_called_once()


# ---------------------------------------------------------------------------
# attach_to_interface
# ---------------------------------------------------------------------------

class TestAttachToInterface:
    def test_program_not_loaded(self, loader):
        with pytest.raises(EBPFAttachError, match="not loaded"):
            loader.attach_to_interface("fake_id", "eth0")

    def test_interface_not_found(self, loader_with_program):
        loader, pid = loader_with_program
        with patch("src.network.ebpf.loader.Path") as mock_path_cls:
            # Make interface path not exist
            mock_iface_path = MagicMock()
            mock_iface_path.exists.return_value = False
            mock_path_cls.return_value = mock_iface_path

            # Need to preserve the actual loaded_programs path
            with pytest.raises(EBPFAttachError, match="not found"):
                loader.attach_to_interface(pid, "eth99")

    def test_xdp_attach_success(self, loader_with_program):
        loader, pid = loader_with_program

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "up"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            with patch.object(loader, "_attach_xdp", return_value=True):
                result = loader.attach_to_interface(pid, "eth0", EBPFAttachMode.SKB)

        assert result is True
        assert "eth0" in loader.attached_interfaces
        assert loader.loaded_programs[pid]["attached_to"] == "eth0"

    def test_tc_attach_success(self, loader_with_program):
        loader, pid = loader_with_program
        loader.loaded_programs[pid]["type"] = EBPFProgramType.TC

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "up"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            with patch.object(loader, "_attach_tc", return_value=True):
                result = loader.attach_to_interface(pid, "eth0")

        assert result is True

    def test_unsupported_type_raises(self, loader_with_program):
        loader, pid = loader_with_program
        loader.loaded_programs[pid]["type"] = EBPFProgramType.CGROUP_SKB

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "up"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            with pytest.raises(EBPFAttachError, match="Unsupported"):
                loader.attach_to_interface(pid, "eth0")

    def test_already_attached(self, loader_with_program):
        loader, pid = loader_with_program
        loader.attached_interfaces["eth0"] = [{"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}]

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "up"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            result = loader.attach_to_interface(pid, "eth0")
        assert result is True

    def test_interface_down_brings_up(self, loader_with_program):
        loader, pid = loader_with_program

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "down"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            with patch("src.network.ebpf.loader.safe_run") as mock_run:
                with patch.object(loader, "_attach_xdp", return_value=True):
                    result = loader.attach_to_interface(pid, "eth0")

        assert result is True
        mock_run.assert_called_once()

    def test_interface_down_fail_to_bring_up(self, loader_with_program):
        loader, pid = loader_with_program

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "down"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            with patch("src.network.ebpf.loader.safe_run", side_effect=subprocess.CalledProcessError(1, "ip")):
                with pytest.raises(EBPFAttachError, match="Failed to bring interface up"):
                    loader.attach_to_interface(pid, "eth0")

    def test_loopback_warning(self, loader_with_program):
        """Attaching to lo should still work but log a warning."""
        loader, pid = loader_with_program

        mock_iface_path = MagicMock()
        mock_iface_path.exists.return_value = True
        mock_operstate = MagicMock()
        mock_operstate.exists.return_value = True
        mock_operstate.read_text.return_value = "up"
        mock_iface_path.__truediv__ = MagicMock(return_value=mock_operstate)

        with patch("src.network.ebpf.loader.Path", return_value=mock_iface_path):
            with patch.object(loader, "_attach_xdp", return_value=True):
                result = loader.attach_to_interface(pid, "lo")
        assert result is True


# ---------------------------------------------------------------------------
# _attach_xdp
# ---------------------------------------------------------------------------

class TestAttachXDP:
    def test_skb_mode_success(self, loader):
        mock_result = MagicMock(returncode=0)
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            with patch.object(loader, "_verify_xdp_attachment", return_value=True):
                result = loader._attach_xdp("/path/prog.o", "eth0", EBPFAttachMode.SKB)
        assert result is True

    def test_hw_mode_fallback_to_skb(self, loader):
        """HW mode fails, DRV mode fails, SKB mode succeeds."""
        fail_result = MagicMock()
        success_result = MagicMock(returncode=0)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] <= 2:
                raise subprocess.CalledProcessError(1, "ip", stderr="not supported")
            return success_result

        with patch("src.network.ebpf.loader.subprocess.run", side_effect=side_effect):
            with patch.object(loader, "_verify_xdp_attachment", return_value=True):
                result = loader._attach_xdp("/path/prog.o", "eth0", EBPFAttachMode.HW)
        assert result is True

    def test_all_modes_fail(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, "ip", stderr="fail")):
            with pytest.raises(EBPFAttachError, match="Failed to attach XDP"):
                loader._attach_xdp("/path/prog.o", "eth0", EBPFAttachMode.SKB)

    def test_drv_mode_tries_drv_then_skb(self, loader):
        """DRV mode should try drv first, then skb."""
        fail_result = subprocess.CalledProcessError(1, "ip", stderr="not supported")
        success_result = MagicMock(returncode=0)

        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise fail_result
            return success_result

        with patch("src.network.ebpf.loader.subprocess.run", side_effect=side_effect):
            with patch.object(loader, "_verify_xdp_attachment", return_value=True):
                result = loader._attach_xdp("/path/prog.o", "eth0", EBPFAttachMode.DRV)
        assert result is True
        assert call_count[0] == 2

    def test_verification_fails_tries_next_mode(self, loader):
        """If verification fails, try next mode."""
        mock_result = MagicMock(returncode=0)
        verify_calls = [0]

        def verify_side(*args, **kwargs):
            verify_calls[0] += 1
            # First call fails verification, second succeeds
            return verify_calls[0] > 1

        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            with patch.object(loader, "_verify_xdp_attachment", side_effect=verify_side):
                # DRV mode: tries drv (verify fails), then skb (verify succeeds)
                result = loader._attach_xdp("/path/prog.o", "eth0", EBPFAttachMode.DRV)
        assert result is True


# ---------------------------------------------------------------------------
# _attach_tc
# ---------------------------------------------------------------------------

class TestAttachTC:
    def test_tc_success(self, loader):
        with patch("src.network.ebpf.loader.safe_run"):
            with patch("src.network.ebpf.loader.subprocess.run", return_value=MagicMock(returncode=0)):
                result = loader._attach_tc("/path/tc.o", "eth0")
        assert result is True

    def test_tc_failure(self, loader):
        with patch("src.network.ebpf.loader.safe_run"):
            with patch("src.network.ebpf.loader.subprocess.run",
                        side_effect=subprocess.CalledProcessError(1, "tc", stderr="error")):
                with pytest.raises(EBPFAttachError, match="Failed to attach TC"):
                    loader._attach_tc("/path/tc.o", "eth0")


# ---------------------------------------------------------------------------
# _verify_xdp_attachment
# ---------------------------------------------------------------------------

class TestVerifyXDPAttachment:
    def test_xdp_present(self, loader):
        mock_result = MagicMock(returncode=0)
        mock_result.stdout = "eth0: <BROADCAST,UP> xdp mode drv"
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_xdp_attachment("eth0", "drv") is True

    def test_xdp_off(self, loader):
        mock_result = MagicMock(returncode=0)
        mock_result.stdout = "eth0: <BROADCAST,UP> xdp off"
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_xdp_attachment("eth0", "skb") is False

    def test_no_xdp_in_output(self, loader):
        mock_result = MagicMock(returncode=0)
        mock_result.stdout = "eth0: <BROADCAST,UP>"
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_xdp_attachment("eth0", "skb") is False

    def test_command_fails(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, "ip")):
            assert loader._verify_xdp_attachment("eth0", "skb") is False

    def test_offload_mode(self, loader):
        mock_result = MagicMock(returncode=0)
        mock_result.stdout = "eth0: xdp hw mode"
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_xdp_attachment("eth0", "offload") is True


# ---------------------------------------------------------------------------
# _verify_attachment (bpftool-based)
# ---------------------------------------------------------------------------

class TestVerifyAttachment:
    def test_success(self, loader):
        mock_result = MagicMock(returncode=0, stdout="42: xdp id 42 tag abc")
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_attachment(42, "eth0", EBPFProgramType.XDP) is True

    def test_not_found(self, loader):
        mock_result = MagicMock(returncode=1, stdout="")
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_attachment(42, "eth0", EBPFProgramType.XDP) is False

    def test_timeout(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.TimeoutExpired("bpftool", 5)):
            assert loader._verify_attachment(42, "eth0", EBPFProgramType.XDP) is False

    def test_file_not_found(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=FileNotFoundError):
            assert loader._verify_attachment(42, "eth0", EBPFProgramType.XDP) is False

    def test_generic_exception(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=RuntimeError("oops")):
            assert loader._verify_attachment(42, "eth0", EBPFProgramType.XDP) is False

    def test_id_not_in_output(self, loader):
        mock_result = MagicMock(returncode=0, stdout="99: xdp id 99 tag xyz")
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            assert loader._verify_attachment(42, "eth0", EBPFProgramType.XDP) is False


# ---------------------------------------------------------------------------
# detach_from_interface
# ---------------------------------------------------------------------------

class TestDetachFromInterface:
    def test_program_not_loaded(self, loader):
        assert loader.detach_from_interface("fake", "eth0") is False

    def test_interface_not_attached(self, loader_with_program):
        loader, pid = loader_with_program
        assert loader.detach_from_interface(pid, "eth0") is False

    def test_program_not_on_interface(self, loader_with_program):
        loader, pid = loader_with_program
        loader.attached_interfaces["eth0"] = [{"program_id": "other_prog", "type": EBPFProgramType.XDP}]
        assert loader.detach_from_interface(pid, "eth0") is False

    def test_xdp_detach_success(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]
        loader.loaded_programs[pid]["attached_to"] = "eth0"

        with patch.object(loader, "_detach_xdp", return_value=True):
            result = loader.detach_from_interface(pid, "eth0")

        assert result is True
        assert "eth0" not in loader.attached_interfaces
        assert "attached_to" not in loader.loaded_programs[pid]

    def test_tc_detach_success(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.TC, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]

        with patch.object(loader, "_detach_tc", return_value=True):
            result = loader.detach_from_interface(pid, "eth0")
        assert result is True

    def test_unsupported_type_detach(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.SOCKET_FILTER, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]

        with pytest.raises(EBPFAttachError, match="Unsupported"):
            loader.detach_from_interface(pid, "eth0")

    def test_detach_keeps_other_attachments(self, loader_with_program):
        loader, pid = loader_with_program
        other_att = {"program_id": "other_prog", "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        my_att = {"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [other_att, my_att]

        with patch.object(loader, "_detach_xdp", return_value=True):
            result = loader.detach_from_interface(pid, "eth0")

        assert result is True
        assert "eth0" in loader.attached_interfaces
        assert len(loader.attached_interfaces["eth0"]) == 1


# ---------------------------------------------------------------------------
# _detach_xdp / _detach_tc
# ---------------------------------------------------------------------------

class TestDetachXDP:
    def test_success(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", return_value=MagicMock(returncode=0)):
            with patch.object(loader, "_verify_xdp_attachment", return_value=False):
                assert loader._detach_xdp("eth0") is True

    def test_still_attached_after_detach(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", return_value=MagicMock(returncode=0)):
            with patch.object(loader, "_verify_xdp_attachment", return_value=True):
                assert loader._detach_xdp("eth0") is False

    def test_command_fails(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, "ip", stderr="fail")):
            with pytest.raises(EBPFAttachError, match="Failed to detach XDP"):
                loader._detach_xdp("eth0")


class TestDetachTC:
    def test_success(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", return_value=MagicMock(returncode=0)):
            assert loader._detach_tc("eth0") is True

    def test_command_fails(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.CalledProcessError(1, "tc", stderr="no filter")):
            with pytest.raises(EBPFAttachError, match="Failed to detach TC"):
                loader._detach_tc("eth0")


# ---------------------------------------------------------------------------
# unload_program
# ---------------------------------------------------------------------------

class TestUnloadProgram:
    def test_not_loaded(self, loader):
        assert loader.unload_program("nonexistent") is False

    def test_unload_simple(self, loader_with_program):
        loader, pid = loader_with_program
        result = loader.unload_program(pid)
        assert result is True
        assert pid not in loader.loaded_programs

    def test_unload_with_pinned_path(self, loader_with_program, tmp_path):
        loader, pid = loader_with_program
        pinned = tmp_path / "pinned_prog"
        pinned.write_text("pinned")
        loader.loaded_programs[pid]["pinned_path"] = str(pinned)

        result = loader.unload_program(pid)
        assert result is True
        assert not pinned.exists()

    def test_unload_pinned_path_not_exists(self, loader_with_program):
        loader, pid = loader_with_program
        loader.loaded_programs[pid]["pinned_path"] = "/nonexistent/path"

        with patch("src.network.ebpf.loader.Path") as mock_path_cls:
            mock_pinned = MagicMock()
            mock_pinned.exists.return_value = False
            mock_path_cls.return_value = mock_pinned
            result = loader.unload_program(pid)
        assert result is True

    def test_unload_pinned_unlink_fails(self, loader_with_program, tmp_path):
        loader, pid = loader_with_program
        pinned = tmp_path / "pinned_prog"
        pinned.write_text("pinned")
        loader.loaded_programs[pid]["pinned_path"] = str(pinned)

        with patch("src.network.ebpf.loader.Path") as mock_path_cls:
            mock_pinned = MagicMock()
            mock_pinned.exists.return_value = True
            mock_pinned.unlink.side_effect = PermissionError("no perms")
            mock_path_cls.return_value = mock_pinned
            result = loader.unload_program(pid)
        # Should still succeed even if unlink fails
        assert result is True

    def test_unload_auto_detaches(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]

        with patch.object(loader, "detach_from_interface") as mock_detach:
            result = loader.unload_program(pid)

        assert result is True
        mock_detach.assert_called_once_with(pid, "eth0")

    def test_unload_auto_detach_failure_still_unloads(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]

        with patch.object(loader, "detach_from_interface", side_effect=Exception("detach fail")):
            result = loader.unload_program(pid)
        assert result is True
        assert pid not in loader.loaded_programs


# ---------------------------------------------------------------------------
# list / get helpers
# ---------------------------------------------------------------------------

class TestListAndGet:
    def test_list_loaded_programs_empty(self, loader):
        assert loader.list_loaded_programs() == []

    def test_list_loaded_programs(self, loader_with_program):
        loader, pid = loader_with_program
        programs = loader.list_loaded_programs()
        assert len(programs) == 1
        assert programs[0]["id"] == pid
        assert programs[0]["loaded"] is True

    def test_get_interface_programs_empty(self, loader):
        assert loader.get_interface_programs("eth0") == []

    def test_get_interface_programs(self, loader_with_program):
        loader, pid = loader_with_program
        loader.attached_interfaces["eth0"] = [
            {"program_id": pid, "type": EBPFProgramType.XDP},
            {"program_id": "another", "type": EBPFProgramType.TC},
        ]
        result = loader.get_interface_programs("eth0")
        assert pid in result
        assert "another" in result


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_with_bpftool_success(self, loader):
        map_data = [
            {"key": 0, "value": 1000},
            {"key": 1, "value": 800},
            {"key": 2, "value": 150},
            {"key": 3, "value": 50},
        ]
        mock_result = MagicMock(returncode=0, stdout=json.dumps(map_data))
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            stats = loader.get_stats()

        assert stats["total_packets"] == 1000
        assert stats["passed_packets"] == 800
        assert stats["dropped_packets"] == 150
        assert stats["forwarded_packets"] == 50

    def test_stats_bpftool_not_found(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", side_effect=FileNotFoundError):
            stats = loader.get_stats()
        assert stats["total_packets"] == 0

    def test_stats_bpftool_timeout(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.TimeoutExpired("bpftool", 5)):
            stats = loader.get_stats()
        assert stats["total_packets"] == 0

    def test_stats_bpftool_failure(self, loader):
        mock_result = MagicMock(returncode=1, stderr="no map")
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            stats = loader.get_stats()
        assert stats["total_packets"] == 0

    def test_stats_json_parse_error(self, loader):
        mock_result = MagicMock(returncode=0, stdout="not json")
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            stats = loader.get_stats()
        assert stats["total_packets"] == 0

    def test_stats_generic_exception(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", side_effect=RuntimeError("oops")):
            stats = loader.get_stats()
        assert stats["total_packets"] == 0


# ---------------------------------------------------------------------------
# update_routes
# ---------------------------------------------------------------------------

class TestUpdateRoutes:
    def test_update_success(self, loader):
        mock_result = MagicMock(returncode=0)
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            result = loader.update_routes({"10.0.0.1": "1", "10.0.0.2": "2"})
        assert result is True

    def test_partial_failure(self, loader):
        mock_result = MagicMock(returncode=1, stderr="key exists")
        with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
            result = loader.update_routes({"10.0.0.1": "1"})
        # Returns True even if individual updates fail (just logs warning)
        assert result is True

    def test_bpftool_not_found(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", side_effect=FileNotFoundError):
            result = loader.update_routes({"10.0.0.1": "1"})
        assert result is False

    def test_bpftool_timeout(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run",
                    side_effect=subprocess.TimeoutExpired("bpftool", 5)):
            result = loader.update_routes({"10.0.0.1": "1"})
        assert result is False

    def test_generic_exception(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run", side_effect=RuntimeError("bad")):
            result = loader.update_routes({"10.0.0.1": "1"})
        assert result is False

    def test_empty_routes(self, loader):
        with patch("src.network.ebpf.loader.subprocess.run") as mock_run:
            result = loader.update_routes({})
        assert result is True
        mock_run.assert_not_called()


# ---------------------------------------------------------------------------
# cleanup
# ---------------------------------------------------------------------------

class TestCleanup:
    def test_cleanup_empty(self, loader):
        loader.cleanup()
        assert loader.loaded_programs == {}
        assert loader.attached_interfaces == {}

    def test_cleanup_with_attached_programs(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]

        with patch.object(loader, "detach_from_interface") as mock_detach:
            with patch.object(loader, "unload_program") as mock_unload:
                loader.cleanup()

        # detach is called for the attached program
        mock_detach.assert_called_once_with(pid, "eth0")

    def test_cleanup_handles_errors(self, loader_with_program):
        loader, pid = loader_with_program
        att = {"program_id": pid, "type": EBPFProgramType.XDP, "mode": EBPFAttachMode.SKB}
        loader.attached_interfaces["eth0"] = [att]

        with patch.object(loader, "detach_from_interface", side_effect=Exception("fail")):
            with patch.object(loader, "unload_program", side_effect=Exception("fail")):
                loader.cleanup()  # Should not raise

        assert loader.loaded_programs == {}
        assert loader.attached_interfaces == {}


# ---------------------------------------------------------------------------
# load_programs (batch)
# ---------------------------------------------------------------------------

class TestLoadPrograms:
    def test_no_directory(self, loader):
        loader.programs_dir = Path("/nonexistent")
        result = loader.load_programs()
        assert result == []

    def test_no_o_files(self, loader, tmp_path):
        # tmp_path exists but has no .o files
        result = loader.load_programs()
        assert result == []

    def test_loads_xdp_and_tc(self, loader, tmp_path):
        (tmp_path / "xdp_mesh_filter.o").write_bytes(b"\x7fELF")
        (tmp_path / "tc_classifier.o").write_bytes(b"\x7fELF")
        (tmp_path / "generic_prog.o").write_bytes(b"\x7fELF")

        with patch.object(loader, "load_program", side_effect=["id1", "id2", "id3"]) as mock_load:
            result = loader.load_programs()

        assert len(result) == 3
        # Verify program types were inferred from filenames
        calls = mock_load.call_args_list
        types_used = {c.args[1] if len(c.args) > 1 else c.kwargs.get("program_type") for c in calls}
        # We can't predict exact call order due to glob, but check they were called
        assert mock_load.call_count == 3

    def test_handles_load_error(self, loader, tmp_path):
        (tmp_path / "bad.o").write_bytes(b"\x7fELF")
        (tmp_path / "good_xdp.o").write_bytes(b"\x7fELF")

        call_count = [0]
        def side_effect(name, ptype=EBPFProgramType.XDP):
            call_count[0] += 1
            if call_count[0] == 1:
                raise EBPFLoadError("bad file")
            return "good_id"

        with patch.object(loader, "load_program", side_effect=side_effect):
            result = loader.load_programs()

        # Only the successful one should be in the list
        assert len(result) == 1

    def test_handles_unexpected_error(self, loader, tmp_path):
        (tmp_path / "crash.o").write_bytes(b"\x7fELF")

        with patch.object(loader, "load_program", side_effect=RuntimeError("unexpected")):
            result = loader.load_programs()
        assert result == []


# ---------------------------------------------------------------------------
# _attach_xdp_program (the alternative XDP attach method)
# ---------------------------------------------------------------------------

class TestAttachXDPProgram:
    def test_bpftool_attach_success(self, loader):
        with patch.object(loader, "_try_bpftool_attach", return_value=True):
            result = loader._attach_xdp_program("eth0", "/path/prog.o", None, EBPFAttachMode.SKB)
        assert result is True

    def test_ip_link_fallback_success(self, loader):
        mock_result = MagicMock(returncode=0)
        with patch.object(loader, "_try_bpftool_attach", return_value=False):
            with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
                result = loader._attach_xdp_program("eth0", "/path/prog.o", None, EBPFAttachMode.SKB)
        assert result is True

    def test_ip_link_all_modes_fail(self, loader):
        mock_result = MagicMock(returncode=1, stderr="fail")
        with patch.object(loader, "_try_bpftool_attach", return_value=False):
            with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result):
                result = loader._attach_xdp_program("eth0", "/path/prog.o", None, EBPFAttachMode.SKB)
        assert result is False

    def test_uses_pinned_path_if_available(self, loader):
        mock_result = MagicMock(returncode=0)
        with patch.object(loader, "_try_bpftool_attach", return_value=False):
            with patch("src.network.ebpf.loader.subprocess.run", return_value=mock_result) as mock_run:
                loader._attach_xdp_program("eth0", "/path/prog.o", "/sys/fs/bpf/pinned", EBPFAttachMode.SKB)

        # Verify pinned_path was used in the command
        cmd = mock_run.call_args[0][0]
        assert "/sys/fs/bpf/pinned" in cmd

    def test_timeout_tries_next_mode(self, loader):
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise subprocess.TimeoutExpired("ip", 5)
            return MagicMock(returncode=0)

        with patch.object(loader, "_try_bpftool_attach", return_value=False):
            with patch("src.network.ebpf.loader.subprocess.run", side_effect=side_effect):
                result = loader._attach_xdp_program("eth0", "/path/prog.o", None, EBPFAttachMode.DRV)
        # DRV timeout, then SKB succeeds
        assert result is True

    def test_generic_exception_tries_next(self, loader):
        call_count = [0]
        def side_effect(*args, **kwargs):
            call_count[0] += 1
            if call_count[0] == 1:
                raise RuntimeError("unexpected")
            return MagicMock(returncode=0)

        with patch.object(loader, "_try_bpftool_attach", return_value=False):
            with patch("src.network.ebpf.loader.subprocess.run", side_effect=side_effect):
                result = loader._attach_xdp_program("eth0", "/path/prog.o", None, EBPFAttachMode.DRV)
        assert result is True

    def test_mode_order_starts_from_requested(self, loader):
        """When HW is requested, tries HW first, then others."""
        results = []
        def side_effect(cmd, *args, **kwargs):
            # Capture the mode flag used
            if "xdpoffload" in cmd:
                results.append("HW")
            elif "xdpdrv" in cmd:
                results.append("DRV")
            else:
                results.append("SKB")
            return MagicMock(returncode=0)

        with patch.object(loader, "_try_bpftool_attach", return_value=False):
            with patch("src.network.ebpf.loader.subprocess.run", side_effect=side_effect):
                loader._attach_xdp_program("eth0", "/path/prog.o", None, EBPFAttachMode.HW)

        # First successful call ends it
        assert results[0] == "HW"


# ---------------------------------------------------------------------------
# _try_bpftool_attach
# ---------------------------------------------------------------------------

class TestTryBpftoolAttach:
    def test_bpftool_not_available(self, loader):
        mock_result = MagicMock(returncode=1)
        with patch("src.network.ebpf.loader.safe_run", return_value=mock_result):
            assert loader._try_bpftool_attach("eth0", "/path/prog", [EBPFAttachMode.SKB]) is False

    def test_bpftool_available_program_found(self, loader):
        which_result = MagicMock(returncode=0)
        list_result = MagicMock(returncode=0, stdout="/path/prog listed")
        with patch("src.network.ebpf.loader.safe_run", return_value=which_result):
            with patch("src.network.ebpf.loader.subprocess.run", return_value=list_result):
                # Returns False because it still defers to ip link
                result = loader._try_bpftool_attach("eth0", "/path/prog", [EBPFAttachMode.SKB])
        assert result is False

    def test_bpftool_exception(self, loader):
        with patch("src.network.ebpf.loader.safe_run", side_effect=Exception("fail")):
            assert loader._try_bpftool_attach("eth0", "/path/prog", [EBPFAttachMode.SKB]) is False
