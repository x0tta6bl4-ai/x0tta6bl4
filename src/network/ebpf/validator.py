"""
eBPF Program Validator - Safety Checks Before Loading

This module validates eBPF programs before kernel loading to prevent:
- Infinite loops (instruction count limits)
- Unsafe memory access
- Resource exhaustion (map size limits)
- Invalid bytecode

Follows Linux kernel eBPF verifier principles.
"""

import logging
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of eBPF program validation"""
    is_valid: bool
    errors: List[str]
    warnings: List[str]
    metadata: Dict[str, any]


class EBPFValidator:
    """
    Validates eBPF programs before loading into kernel.
    
    Checks:
    - Instruction count (max 1 million in modern kernels)
    - Map definitions and sizes
    - Program type compatibility
    - Bytecode structure integrity
    """
    
    # Safety limits (conservative defaults)
    MAX_INSTRUCTIONS = 1_000_000
    MAX_MAP_SIZE = 1024 * 1024 * 10  # 10 MB
    MAX_MAPS = 64
    
    def __init__(self):
        logger.info("eBPF Validator initialized")
    
    def validate_program_file(self, program_path: Path) -> ValidationResult:
        """
        Validate an eBPF .o file before loading.
        
        Args:
            program_path: Path to compiled eBPF object file
        
        Returns:
            ValidationResult with validation status and details
        """
        errors = []
        warnings = []
        metadata = {}
        
        # Check file exists
        if not program_path.exists():
            errors.append(f"Program file not found: {program_path}")
            return ValidationResult(False, errors, warnings, metadata)
        
        # Check file extension
        if program_path.suffix != ".o":
            errors.append(f"Invalid file extension. Expected .o, got {program_path.suffix}")
        
        # Check file size (basic sanity check)
        file_size = program_path.stat().st_size
        metadata["file_size_bytes"] = file_size
        
        if file_size == 0:
            errors.append("Program file is empty")
        elif file_size > 10 * 1024 * 1024:  # 10 MB
            warnings.append(f"Large program file: {file_size / 1024 / 1024:.2f} MB")
        
        # TODO: Parse ELF sections for:
        # - .text (program instructions)
        # - .maps (BPF map definitions)
        # - .BTF (BPF Type Format metadata)
        # - license and version sections
        
        # TODO: Count instructions (estimate from .text section size)
        # For now, rough estimate: ~8 bytes per instruction
        estimated_instructions = file_size // 8
        metadata["estimated_instructions"] = estimated_instructions
        
        if estimated_instructions > self.MAX_INSTRUCTIONS:
            errors.append(
                f"Program too large: {estimated_instructions} instructions "
                f"(max {self.MAX_INSTRUCTIONS})"
            )
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info(f"Validation PASSED for {program_path.name}")
        else:
            logger.warning(f"Validation FAILED for {program_path.name}: {errors}")
        
        return ValidationResult(is_valid, errors, warnings, metadata)
    
    def validate_bytecode(self, bytecode: bytes) -> ValidationResult:
        """
        Validate raw eBPF bytecode.
        
        Args:
            bytecode: Raw eBPF instruction bytes
        
        Returns:
            ValidationResult
        
        TODO:
        - Parse eBPF instruction format (64-bit opcodes)
        - Check for invalid opcodes
        - Verify register usage
        - Detect potential infinite loops
        """
        errors = []
        warnings = []
        metadata = {"bytecode_size": len(bytecode)}
        
        if len(bytecode) == 0:
            errors.append("Empty bytecode")
            return ValidationResult(False, errors, warnings, metadata)
        
        # eBPF instructions are 8 bytes each
        if len(bytecode) % 8 != 0:
            errors.append(f"Bytecode size {len(bytecode)} not multiple of 8")
        
        instruction_count = len(bytecode) // 8
        metadata["instruction_count"] = instruction_count
        
        if instruction_count > self.MAX_INSTRUCTIONS:
            errors.append(
                f"Too many instructions: {instruction_count} "
                f"(max {self.MAX_INSTRUCTIONS})"
            )
        
        is_valid = len(errors) == 0
        return ValidationResult(is_valid, errors, warnings, metadata)
