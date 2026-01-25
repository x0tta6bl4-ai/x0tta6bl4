from pathlib import Path
import tempfile
from src.network.ebpf.validator import EBPFValidator


def test_validate_program_file_missing():
    v = EBPFValidator()
    res = v.validate_program_file(Path('/no/such/file.o'))
    assert not res.is_valid
    assert any('not found' in e for e in res.errors)


def test_validate_program_file_empty(tmp_path):
    f = tmp_path / 'prog.o'
    f.write_bytes(b'')
    v = EBPFValidator()
    res = v.validate_program_file(f)
    assert not res.is_valid
    assert 'empty' in res.errors[0].lower()


def test_validate_program_file_large_warning(tmp_path):
    f = tmp_path / 'prog.o'
    # 2MB file triggers size warning path (not error)
    f.write_bytes(b'0' * (2 * 1024 * 1024))
    v = EBPFValidator()
    res = v.validate_program_file(f)
    assert res.is_valid  # large alone not invalid
    assert res.warnings or res.metadata['estimated_instructions'] > 0


def test_validate_bytecode_empty():
    v = EBPFValidator()
    res = v.validate_bytecode(b'')
    assert not res.is_valid
    assert 'empty' in res.errors[0].lower()


def test_validate_bytecode_alignment():
    v = EBPFValidator()
    # 3 bytes (not multiple of 8)
    res = v.validate_bytecode(b'123')
    assert not res.is_valid
    assert 'not multiple of 8' in res.errors[0]


def test_validate_bytecode_valid():
    v = EBPFValidator()
    # 16 bytes => 2 instructions
    res = v.validate_bytecode(b'0' * 16)
    assert res.is_valid
    assert res.metadata['instruction_count'] == 2
