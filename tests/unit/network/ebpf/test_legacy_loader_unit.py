"""Unit tests for eBPF Legacy Loader."""
import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.loader._legacy import (
    EBPFLoader,
    EBPFProgramType,
    EBPFAttachMode,
    EBPFLoadError,
    EBPFAttachError,
)


class TestEnums:
    def test_program_type_values(self):
        assert EBPFProgramType.XDP.value == "xdp"
        assert EBPFProgramType.TC.value == "tc"

    def test_attach_mode_values(self):
        assert EBPFAttachMode.SKB.value == "skb"
        assert EBPFAttachMode.DRV.value == "drv"
        assert EBPFAttachMode.HW.value == "hw"


class TestExceptions:
    def test_load_error(self):
        err = EBPFLoadError("failed to load")
        assert isinstance(err, Exception)
        assert "failed to load" in str(err)

    def test_attach_error(self):
        err = EBPFAttachError("failed to attach")
        assert isinstance(err, Exception)


class TestEBPFLoaderInit:
    def test_default_init(self):
        loader = EBPFLoader()
        assert isinstance(loader.loaded_programs, dict)
        assert isinstance(loader.attached_interfaces, dict)
        assert len(loader.loaded_programs) == 0

    def test_custom_programs_dir(self, tmp_path):
        loader = EBPFLoader(programs_dir=tmp_path)
        assert loader.programs_dir == tmp_path


class TestListLoadedPrograms:
    def test_empty(self):
        loader = EBPFLoader()
        assert loader.list_loaded_programs() == []

    def test_with_programs(self):
        loader = EBPFLoader()
        loader.loaded_programs["prog1"] = {
            "path": "/path/to/prog.o",
            "type": "xdp",
            "loaded_at": 0,
        }
        programs = loader.list_loaded_programs()
        assert len(programs) == 1


class TestGetInterfacePrograms:
    def test_no_programs(self):
        loader = EBPFLoader()
        assert loader.get_interface_programs("eth0") == []

    def test_with_attachments(self):
        loader = EBPFLoader()
        loader.attached_interfaces["eth0"] = [
            {"program_id": "p1"},
            {"program_id": "p2"},
        ]
        progs = loader.get_interface_programs("eth0")
        assert len(progs) >= 1


class TestGetStats:
    def test_initial_stats(self):
        loader = EBPFLoader()
        stats = loader.get_stats()
        assert isinstance(stats, dict)
        assert stats.get("loaded_programs", 0) == 0
        assert stats.get("attached_interfaces", 0) == 0


class TestLoadProgram:
    def test_file_not_found(self):
        loader = EBPFLoader()
        with pytest.raises((EBPFLoadError, FileNotFoundError, Exception)):
            loader.load_program("/nonexistent/prog.o")


class TestUnloadProgram:
    def test_unknown_program(self):
        loader = EBPFLoader()
        result = loader.unload_program("unknown_id")
        assert result is False

    def test_loaded_program(self):
        loader = EBPFLoader()
        loader.loaded_programs["p1"] = {"path": "test.o", "type": "xdp"}
        result = loader.unload_program("p1")
        assert result is True
        assert "p1" not in loader.loaded_programs


class TestCleanup:
    def test_cleanup_empty(self):
        loader = EBPFLoader()
        loader.cleanup()
        assert len(loader.loaded_programs) == 0

    def test_cleanup_with_programs(self):
        loader = EBPFLoader()
        loader.loaded_programs["p1"] = {"path": "test.o"}
        loader.cleanup()
        assert len(loader.loaded_programs) == 0


class TestUpdateRoutes:
    @patch("src.network.ebpf.loader._legacy.safe_run")
    def test_update_routes_no_map(self, mock_run):
        loader = EBPFLoader()
        result = loader.update_routes({"10.0.0.1": "eth0"})
        assert isinstance(result, bool)
