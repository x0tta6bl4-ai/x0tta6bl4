"""Unit tests for eBPF Attach Manager."""
import os
import subprocess
import pytest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.loader.attach_manager import (
    EBPFAttachManager,
    EBPFAttachMode,
    EBPFAttachError,
)


class TestEBPFAttachMode:
    def test_skb(self):
        assert EBPFAttachMode.SKB.value == "skb"

    def test_drv(self):
        assert EBPFAttachMode.DRV.value == "drv"

    def test_hw(self):
        assert EBPFAttachMode.HW.value == "hw"


class TestEBPFAttachError:
    def test_is_exception(self):
        err = EBPFAttachError("test error")
        assert isinstance(err, Exception)
        assert str(err) == "test error"


class TestAttachManagerInit:
    def test_empty_interfaces(self):
        mgr = EBPFAttachManager()
        assert mgr.attached_interfaces == {}


class TestVerifyInterface:
    @patch("src.network.ebpf.loader.attach_manager.Path")
    def test_interface_not_found(self, mock_path_cls):
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = False
        mock_path_cls.return_value = mock_path_inst

        mgr = EBPFAttachManager()
        with pytest.raises(EBPFAttachError, match="not found"):
            mgr.verify_interface("fake0")

    @patch("src.network.ebpf.loader.attach_manager.Path")
    def test_interface_up(self, mock_path_cls):
        mock_path_inst = MagicMock()
        mock_path_inst.exists.return_value = True
        operstate = MagicMock()
        operstate.exists.return_value = True
        operstate.read_text.return_value = "up\n"
        mock_path_inst.__truediv__ = MagicMock(return_value=operstate)
        mock_path_cls.return_value = mock_path_inst

        mgr = EBPFAttachManager()
        assert mgr.verify_interface("eth0") is True


class TestGetInterfaceAttachments:
    def test_empty(self):
        mgr = EBPFAttachManager()
        assert mgr.get_interface_attachments("eth0") == []

    def test_with_data(self):
        mgr = EBPFAttachManager()
        mgr.attached_interfaces["eth0"] = [
            {"program_id": "p1", "type": "xdp", "mode": "skb", "attached_at": 0}
        ]
        result = mgr.get_interface_attachments("eth0")
        assert len(result) == 1
        assert result[0]["program_id"] == "p1"


class TestRemoveAttachment:
    def test_remove_existing(self):
        mgr = EBPFAttachManager()
        mgr.attached_interfaces["eth0"] = [
            {"program_id": "p1", "type": "xdp"},
            {"program_id": "p2", "type": "tc"},
        ]
        result = mgr.remove_attachment("eth0", "p1")
        assert result is True
        assert len(mgr.attached_interfaces["eth0"]) == 1

    def test_remove_nonexistent(self):
        mgr = EBPFAttachManager()
        result = mgr.remove_attachment("eth0", "p1")
        assert result is False
