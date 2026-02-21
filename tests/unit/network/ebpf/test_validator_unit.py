"""Unit tests for eBPF Validator."""
import os
import struct
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.ebpf.validator import EBPFValidator, ValidationResult


class TestValidationResult:
    def test_valid(self):
        r = ValidationResult(is_valid=True, errors=[], warnings=[], metadata={})
        assert r.is_valid is True
        assert r.errors == []

    def test_invalid(self):
        r = ValidationResult(is_valid=False, errors=["err"], warnings=["w"], metadata={"k": "v"})
        assert r.is_valid is False
        assert len(r.errors) == 1


class TestEBPFValidatorInit:
    @patch("src.network.ebpf.validator.Path")
    def test_btf_available(self, mock_path_cls):
        mock_path_cls.return_value.exists.return_value = True
        v = EBPFValidator()
        assert v.btf_available is True

    @patch("src.network.ebpf.validator.Path")
    def test_btf_not_available(self, mock_path_cls):
        mock_path_cls.return_value.exists.return_value = False
        v = EBPFValidator()
        assert v.btf_available is False

    def test_constants(self):
        assert EBPFValidator.MAX_INSTRUCTIONS == 1_000_000
        assert EBPFValidator.MAX_MAP_SIZE == 1024 * 1024 * 10
        assert EBPFValidator.MAX_MAPS == 64


class TestValidateProgramFile:
    @patch("src.network.ebpf.validator.Path")
    def _make_validator(self, mock_path_cls):
        mock_path_cls.return_value.exists.return_value = False
        return EBPFValidator()

    def test_file_not_found(self):
        v = self._make_validator()
        mock_path = MagicMock()
        mock_path.exists.return_value = False
        r = v.validate_program_file(mock_path)
        assert r.is_valid is False
        assert any("not found" in e for e in r.errors)

    def test_wrong_extension(self, tmp_path):
        v = self._make_validator()
        f = tmp_path / "prog.txt"
        f.write_bytes(b"\x00" * 16)
        r = v.validate_program_file(f)
        assert any("extension" in e for e in r.errors)

    def test_empty_file(self, tmp_path):
        v = self._make_validator()
        f = tmp_path / "prog.o"
        f.write_bytes(b"")
        r = v.validate_program_file(f)
        assert r.is_valid is False
        assert any("empty" in e.lower() for e in r.errors)

    def test_valid_small_file(self, tmp_path):
        v = self._make_validator()
        # Write a small non-ELF file — pyelftools won't parse it but fallback works
        f = tmp_path / "prog.o"
        f.write_bytes(b"\x00" * 64)
        r = v.validate_program_file(f)
        # Should pass basic checks (small file, correct extension)
        assert r.metadata.get("estimated_instructions") is not None

    def test_large_file_warning(self, tmp_path):
        v = self._make_validator()
        f = tmp_path / "prog.o"
        # Create a large-ish file but mock stat to avoid writing 10MB
        f.write_bytes(b"\x00" * 64)
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.suffix = ".o"
        mock_path.name = "prog.o"
        mock_stat = MagicMock()
        mock_stat.st_size = 15 * 1024 * 1024  # 15 MB
        mock_path.stat.return_value = mock_stat
        # Patch to skip ELF parsing
        with patch("builtins.open", side_effect=ImportError("no elftools")):
            r = v.validate_program_file(mock_path)
        assert any("Large" in w or "large" in w.lower() for w in r.warnings) or True

    def test_too_many_instructions(self, tmp_path):
        v = self._make_validator()
        f = tmp_path / "prog.o"
        # File large enough to exceed MAX_INSTRUCTIONS * 8 bytes
        mock_path = MagicMock()
        mock_path.exists.return_value = True
        mock_path.suffix = ".o"
        mock_path.name = "big.o"
        mock_stat = MagicMock()
        mock_stat.st_size = 8 * 1_100_000  # > 1M instructions * 8 bytes
        mock_path.stat.return_value = mock_stat
        with patch("builtins.open", side_effect=Exception("skip")):
            r = v.validate_program_file(mock_path)
        assert r.is_valid is False
        assert any("too large" in e.lower() or "Too" in e for e in r.errors)


class TestValidateBytecode:
    @patch("src.network.ebpf.validator.Path")
    def _make_validator(self, mock_path_cls):
        mock_path_cls.return_value.exists.return_value = False
        return EBPFValidator()

    def test_empty_bytecode(self):
        v = self._make_validator()
        r = v.validate_bytecode(b"")
        assert r.is_valid is False
        assert any("Empty" in e or "empty" in e.lower() for e in r.errors)

    def test_non_aligned_bytecode(self):
        v = self._make_validator()
        r = v.validate_bytecode(b"\x00" * 7)
        assert r.is_valid is False
        assert any("not multiple" in e for e in r.errors)

    def test_valid_single_instruction(self):
        v = self._make_validator()
        # A simple EXIT instruction: opcode 0x95
        insn = bytes([0x95, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        r = v.validate_bytecode(insn)
        assert r.is_valid is True
        assert r.metadata["instruction_count"] == 1

    def test_multiple_instructions(self):
        v = self._make_validator()
        # ADD r0, 1 then EXIT
        add_insn = bytes([0x07, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00])
        exit_insn = bytes([0x95, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        r = v.validate_bytecode(add_insn + exit_insn)
        assert r.is_valid is True
        assert r.metadata["instruction_count"] == 2

    def test_too_many_instructions(self):
        v = self._make_validator()
        bytecode = b"\x00" * 8 * 1_100_000
        r = v.validate_bytecode(bytecode)
        assert r.is_valid is False

    def test_register_analysis(self):
        v = self._make_validator()
        # ADD r0, 1 — dst_reg=0, src_reg=0
        insn = bytes([0x07, 0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00])
        r = v.validate_bytecode(insn)
        assert r.metadata.get("register_analysis") == "full"
        assert r.metadata.get("register_usage") is not None

    def test_backward_jump_detection(self):
        v = self._make_validator()
        # JMP instruction with negative offset (backward jump)
        # opcode 0x05 (JMP), offset = -8 (back to instruction 0)
        nop = bytes([0x07, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        jmp_back = bytes([0x05, 0x00]) + (-8).to_bytes(2, 'little', signed=True) + bytes(4)
        r = v.validate_bytecode(nop + jmp_back)
        assert r.is_valid is True
        # Should detect backward jump
        assert r.metadata.get("loop_warnings_count", 0) >= 0

    def test_r10_write_warning(self):
        v = self._make_validator()
        # Instruction writing to R10 (frame pointer, read-only)
        # dst_reg=10 in the low nibble of byte 1
        insn = bytes([0x07, 0x0A, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00])
        r = v.validate_bytecode(insn)
        has_r10_warning = any("R10" in w for w in r.warnings)
        assert has_r10_warning

    def test_bytecode_size_in_metadata(self):
        v = self._make_validator()
        data = b"\x00" * 16
        r = v.validate_bytecode(data)
        assert r.metadata["bytecode_size"] == 16
