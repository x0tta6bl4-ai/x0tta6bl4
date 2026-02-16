"""
Tests for Extended eBPF Validator Features.

Tests the enhanced loop detection and register analysis:
- Backward jump detection
- Nested loop detection
- Register usage analysis
- Read-only register protection
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.network.ebpf.validator import EBPFValidator, ValidationResult


class TestEBPFValidatorExtended:
    """Test extended eBPF validator features."""

    @pytest.fixture
    def validator(self):
        """Create validator instance."""
        return EBPFValidator()

    def test_backward_jump_detection(self, validator):
        """Test detection of backward jumps (potential loops)."""
        # Create bytecode with backward jump
        # Instruction format: [opcode(1)][dst_src(1)][offset(2)][imm(4)]
        bytecode = bytearray(8 * 10)  # 10 instructions

        # Instruction 5: jump backward to instruction 2
        # Offset = -3 instructions = -24 bytes
        bytecode[5 * 8 + 0] = 0x05  # JMP opcode
        bytecode[5 * 8 + 2 : 5 * 8 + 4] = (-24).to_bytes(2, "little", signed=True)

        result = validator.validate_bytecode(bytes(bytecode))

        # Should detect backward jump
        assert any("backward jump" in warning.lower() for warning in result.warnings)
        assert result.metadata.get("loop_analysis") in ["basic", "none_detected"]

    def test_nested_loop_detection(self, validator):
        """Test detection of nested loops."""
        # Create bytecode with multiple jumps to same target
        bytecode = bytearray(8 * 10)

        # Multiple instructions jump to instruction 2
        target_instruction = 2
        for jump_from in [4, 6, 8]:
            offset = (target_instruction - jump_from) * 8
            bytecode[jump_from * 8 + 0] = 0x05  # JMP
            bytecode[jump_from * 8 + 2 : jump_from * 8 + 4] = offset.to_bytes(
                2, "little", signed=True
            )

        result = validator.validate_bytecode(bytes(bytecode))

        # Should detect nested loops
        assert any(
            "multiple jumps" in warning.lower() or "nested loop" in warning.lower()
            for warning in result.warnings
        )

    def test_register_usage_analysis(self, validator):
        """Test register usage analysis."""
        # Create bytecode that uses various registers
        bytecode = bytearray(8 * 5)

        # Use R1 (source) and R2 (destination)
        bytecode[0] = 0x07  # ADD opcode
        bytecode[1] = 0x21  # R2 = dst, R1 = src

        result = validator.validate_bytecode(bytes(bytecode))

        # Should have register usage metadata
        assert "register_usage" in result.metadata
        assert "registers_used" in result.metadata

    def test_read_only_register_protection(self, validator):
        """Test detection of write to read-only register (R10)."""
        # Create bytecode that attempts to write to R10
        bytecode = bytearray(8 * 3)

        # Attempt to write to R10 (frame pointer, read-only)
        # eBPF instruction byte 1: (src_reg << 4) | dst_reg
        # So for dst=10 (0xa), src=0: byte = 0x0a
        bytecode[0] = 0x07  # ADD opcode
        bytecode[1] = 0x0A  # dst=R10, src=R0

        result = validator.validate_bytecode(bytes(bytecode))

        # Should warn about write to read-only register
        assert any(
            "read-only" in warning.lower() or "r10" in warning.lower()
            for warning in result.warnings
        )

    def test_loop_analysis_metadata(self, validator):
        """Test that loop analysis metadata is included."""
        bytecode = bytearray(8 * 10)

        result = validator.validate_bytecode(bytes(bytecode))

        # Should have loop analysis metadata
        assert "loop_analysis" in result.metadata
        assert "loop_warnings_count" in result.metadata
        assert isinstance(result.metadata["loop_warnings_count"], int)

    def test_no_loops_detected(self, validator):
        """Test that programs without loops are correctly identified."""
        # Create simple bytecode without loops (forward-only)
        bytecode = bytearray(8 * 5)

        # All forward jumps
        for i in range(3):
            bytecode[i * 8 + 0] = 0x05  # JMP
            bytecode[i * 8 + 2 : i * 8 + 4] = (8).to_bytes(
                2, "little", signed=True
            )  # Forward

        result = validator.validate_bytecode(bytes(bytecode))

        # Should not detect loops
        assert result.metadata.get("loop_analysis") in ["basic", "none_detected"]
        assert result.metadata.get("loop_warnings_count", 0) == 0
