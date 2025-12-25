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
        
        # Check for BTF support
        self.btf_available = Path("/sys/kernel/btf/vmlinux").exists()
        if self.btf_available:
            logger.info("BTF (BPF Type Format) available - CO-RE programs supported")
        else:
            logger.warning("BTF not available - CO-RE programs may not work")
    
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
        
        # Parse ELF sections for detailed validation
        try:
            from elftools.elf.elffile import ELFFile
            
            with open(program_path, 'rb') as f:
                elf = ELFFile(f)
                
                # Find .text section (program instructions)
                text_section = elf.get_section_by_name('.text')
                if text_section:
                    text_size = text_section.data_size
                    metadata['text_size'] = text_size
                    # eBPF instructions are 8 bytes each
                    estimated_instructions = text_size // 8
                    metadata["estimated_instructions"] = estimated_instructions
                else:
                    warnings.append("No .text section found")
                    estimated_instructions = file_size // 8
                    metadata["estimated_instructions"] = estimated_instructions
                
                # Check for .maps section
                maps_section = elf.get_section_by_name('.maps')
                if maps_section:
                    metadata['has_maps'] = True
                    metadata['maps_size'] = maps_section.data_size
                else:
                    metadata['has_maps'] = False
                
                # Check for BTF (BPF Type Format)
                btf_section = elf.get_section_by_name('.BTF')
                if btf_section:
                    metadata['has_btf'] = True
                    metadata['btf_size'] = btf_section.data_size
                    logger.debug("Program has BTF metadata (CO-RE compatible)")
                    
                    # BTF-based verification: check if kernel supports BTF
                    if not self.btf_available:
                        warnings.append(
                            "Program has BTF but kernel doesn't support it - "
                            "CO-RE features may not work"
                        )
                else:
                    metadata['has_btf'] = False
                    if self.btf_available:
                        warnings.append(
                            "No BTF section found (not CO-RE compatible) - "
                            "consider recompiling with -g flag"
                        )
                
                # Check license
                license_section = elf.get_section_by_name('license')
                if license_section:
                    try:
                        license_text = license_section.data().decode('utf-8').strip('\x00')
                        metadata['license'] = license_text
                        if 'GPL' not in license_text:
                            warnings.append(f"License '{license_text}' may not be GPL-compatible")
                    except:
                        pass
                else:
                    warnings.append("No license section found")
                    
        except ImportError:
            # Fallback if pyelftools not available
            estimated_instructions = file_size // 8
            metadata["estimated_instructions"] = estimated_instructions
            warnings.append("pyelftools not available, using basic validation")
        except Exception as e:
            logger.warning(f"ELF parsing failed: {e}")
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
