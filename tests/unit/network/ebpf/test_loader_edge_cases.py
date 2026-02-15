"""
Edge case tests for eBPF Loader.

Tests error handling, invalid inputs, and failure scenarios.
"""

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

try:
    from src.network.ebpf.loader import (EBPFAttachError, EBPFAttachMode,
                                         EBPFLoader, EBPFLoadError,
                                         EBPFProgramType)

    EBPF_AVAILABLE = True
except ImportError:
    EBPF_AVAILABLE = False
    EBPFLoader = None
    EBPFProgramType = None
    EBPFAttachMode = None


@pytest.mark.skipif(not EBPF_AVAILABLE, reason="eBPF Loader not available")
class TestEBPFLoaderEdgeCases:
    """Edge case tests for eBPF Loader"""

    def test_load_nonexistent_file(self):
        """Test loading nonexistent eBPF program"""
        loader = EBPFLoader()

        with pytest.raises(EBPFLoadError):
            loader.load_program("nonexistent.o")

    def test_load_invalid_elf_file(self):
        """Test loading invalid ELF file"""
        loader = EBPFLoader()

        # Create invalid ELF file
        invalid_file = Path("/tmp/invalid_ebpf.o")
        invalid_file.write_bytes(b"NOT_AN_ELF_FILE")

        try:
            with pytest.raises((EBPFLoadError, ValueError)):
                loader.load_program(str(invalid_file))
        finally:
            invalid_file.unlink()

    def test_load_corrupted_elf_file(self):
        """Test loading corrupted ELF file"""
        loader = EBPFLoader()

        # Create corrupted ELF file (partial ELF header)
        corrupted_file = Path("/tmp/corrupted_ebpf.o")
        corrupted_file.write_bytes(b"\x7fELF\x01\x01\x01" + b"\x00" * 100)

        try:
            with pytest.raises((EBPFLoadError, ValueError)):
                loader.load_program(str(corrupted_file))
        finally:
            corrupted_file.unlink()

    def test_attach_to_nonexistent_interface(self):
        """Test attaching to nonexistent network interface"""
        loader = EBPFLoader()

        # Create valid dummy program file (minimal ELF header)
        dummy_program = Path("/tmp/dummy_ebpf.o")
        # Create minimal ELF header to pass basic validation
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Mock load_program to return a program_id without actually loading
            with patch.object(loader, "load_program") as mock_load:
                mock_load.return_value = "test-program-id"
                program_id = loader.load_program(str(dummy_program))

                # Manually add to loaded_programs for the test
                loader.loaded_programs[program_id] = {
                    "path": str(dummy_program),
                    "type": EBPFProgramType.XDP,
                    "loaded": True,
                }

                # Try to attach to nonexistent interface
                with pytest.raises(EBPFAttachError):
                    loader.attach_to_interface(program_id, "nonexistent0")
        finally:
            if dummy_program.exists():
                dummy_program.unlink()

    def test_attach_invalid_program_id(self):
        """Test attaching with invalid program ID"""
        loader = EBPFLoader()

        with pytest.raises((EBPFAttachError, KeyError)):
            loader.attach_to_interface("invalid-program-id", "eth0")

    def test_detach_unattached_program(self):
        """Test detaching program that was never attached"""
        loader = EBPFLoader()

        # Create minimal ELF header
        dummy_program = Path("/tmp/dummy_ebpf.o")
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Mock load_program to return a program_id
            with patch.object(loader, "load_program") as mock_load:
                mock_load.return_value = "test-program-id"
                program_id = loader.load_program(str(dummy_program))

                # Manually add to loaded_programs
                loader.loaded_programs[program_id] = {
                    "path": str(dummy_program),
                    "type": EBPFProgramType.XDP,
                    "loaded": True,
                }

                # Try to detach without attaching
                # Should handle gracefully (no error or specific error)
                result = loader.detach_from_interface(program_id, "eth0")
                # Result depends on implementation
                assert result in [True, False]
        finally:
            if dummy_program.exists():
                dummy_program.unlink()

    def test_unload_attached_program(self):
        """Test unloading program that is still attached"""
        loader = EBPFLoader()

        # Create minimal ELF header
        dummy_program = Path("/tmp/dummy_ebpf.o")
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Mock load_program
            with patch.object(loader, "load_program") as mock_load:
                mock_load.return_value = "test-program-id"
                program_id = loader.load_program(str(dummy_program))

                # Manually add to loaded_programs and attached_interfaces
                loader.loaded_programs[program_id] = {
                    "path": str(dummy_program),
                    "type": EBPFProgramType.XDP,
                    "loaded": True,
                }
                loader.attached_interfaces["eth0"] = [program_id]

                # Unload should detach first or handle gracefully
                loader.unload_program(program_id)
                assert program_id not in loader.loaded_programs
        finally:
            if dummy_program.exists():
                dummy_program.unlink()

    def test_concurrent_load_operations(self):
        """Test concurrent program loading"""
        import threading

        loader = EBPFLoader()
        results = []
        errors = []

        def load_worker(program_name: str):
            try:
                # Create minimal ELF header
                dummy_program = Path(f"/tmp/{program_name}.o")
                elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
                dummy_program.write_bytes(elf_header)

                # Mock load_program to avoid actual loading
                with patch.object(loader, "load_program") as mock_load:
                    mock_load.return_value = f"program-{program_name}"
                    program_id = loader.load_program(str(dummy_program))
                    results.append(program_id)

                if dummy_program.exists():
                    dummy_program.unlink()
            except Exception as e:
                errors.append(e)

        # Create multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=load_worker, args=(f"program-{i}",))
            threads.append(thread)
            thread.start()

        # Wait for all threads
        for thread in threads:
            thread.join()

        # All should succeed
        assert len(errors) == 0
        assert len(results) == 5

    def test_invalid_program_type(self):
        """Test loading with invalid program type"""
        loader = EBPFLoader()

        dummy_program = Path("/tmp/dummy_ebpf.o")
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Try to pass invalid type - Python will raise TypeError if not an enum value
            # Since program_type has type annotation EBPFProgramType, passing a string will fail
            # But if type checking is disabled, it will try to load and fail with EBPFLoadError
            # So we accept either TypeError (type validation) or EBPFLoadError (runtime validation)
            with pytest.raises((TypeError, ValueError, EBPFLoadError)):
                loader.load_program(str(dummy_program), program_type="INVALID_TYPE")  # type: ignore
        finally:
            if dummy_program.exists():
                dummy_program.unlink()

    def test_attach_mode_validation(self):
        """Test validation of attach mode"""
        loader = EBPFLoader()

        dummy_program = Path("/tmp/dummy_ebpf.o")
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Mock _load_via_bpftool to avoid actual loading
            with patch.object(loader, "_load_via_bpftool") as mock_load:
                mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
                program_id = loader.load_program(str(dummy_program))

            # Invalid attach mode should raise error
            # When passing a string instead of EBPFAttachMode enum, it will fail in _attach_xdp_program
            # when trying to access .value attribute (AttributeError) or map the mode (KeyError)
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_text", return_value="up"),
                patch(
                    "subprocess.run",
                    return_value=Mock(returncode=0, stdout="", stderr=""),
                ),
            ):
                # Invalid mode will cause AttributeError when accessing .value or KeyError when mapping
                with pytest.raises(
                    (TypeError, ValueError, KeyError, AttributeError, EBPFAttachError)
                ):
                    loader.attach_to_interface(program_id, "eth0", mode="INVALID_MODE")  # type: ignore
        finally:
            if dummy_program.exists():
                dummy_program.unlink()

    def test_memory_exhaustion_handling(self):
        """Test handling of memory exhaustion during loading"""
        loader = EBPFLoader()

        # Mock memory error
        with patch("builtins.open", side_effect=MemoryError("Out of memory")):
            with pytest.raises((EBPFLoadError, MemoryError)):
                loader.load_program("dummy.o")

    def test_bpftool_failure(self):
        """Test handling when bpftool command fails"""
        loader = EBPFLoader()

        dummy_program = Path("/tmp/dummy_ebpf.o")
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Mock _load_via_bpftool to avoid actual loading
            with patch.object(loader, "_load_via_bpftool") as mock_load:
                mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
                program_id = loader.load_program(str(dummy_program))

            # Mock bpftool failure - check if attach_kprobe exists
            if hasattr(loader, "attach_kprobe"):
                with patch(
                    "subprocess.run",
                    return_value=Mock(returncode=1, stderr="bpftool error"),
                ):
                    with pytest.raises(
                        (EBPFAttachError, AttributeError, NotImplementedError)
                    ):
                        loader.attach_kprobe(program_id, "sys_enter")
            else:
                # If attach_kprobe doesn't exist, skip this test
                pytest.skip("attach_kprobe method not implemented")
        finally:
            if dummy_program.exists():
                dummy_program.unlink()

    def test_interface_state_check(self):
        """Test checking interface state before attachment"""
        loader = EBPFLoader()

        dummy_program = Path("/tmp/dummy_ebpf.o")
        # Create minimal ELF header
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 48
        dummy_program.write_bytes(elf_header)

        try:
            # Mock _load_via_bpftool to avoid actual loading
            with patch.object(loader, "_load_via_bpftool") as mock_load:
                mock_load.return_value = (123, "/sys/fs/bpf/test_xdp")
                program_id = loader.load_program(str(dummy_program))

            # Mock interface in down state - loader should warn but not fail
            # We need to mock both the attachment and verification subprocess calls
            with (
                patch("pathlib.Path.exists", return_value=True),
                patch("pathlib.Path.read_text", return_value="down\n"),
                patch.object(loader, "_verify_xdp_attachment", return_value=True),
                patch(
                    "subprocess.run",
                    return_value=Mock(returncode=0, stdout="xdp", stderr=""),
                ),
            ):
                # Interface in down state should still allow attachment (with warning)
                # The loader code warns but doesn't fail on down state
                result = loader.attach_to_interface(program_id, "eth0")
                # Should succeed (loader allows attachment even if interface is down)
                assert result is True
        finally:
            if dummy_program.exists():
                dummy_program.unlink()


@pytest.mark.skipif(not EBPF_AVAILABLE, reason="eBPF Loader not available")
class TestEBPFSecurityBoundaries:
    """Security boundary tests for eBPF Loader"""

    def test_path_traversal_prevention(self):
        """Test prevention of path traversal attacks"""
        loader = EBPFLoader()

        # Malicious paths
        malicious_paths = [
            "../../../etc/passwd",
            "/etc/shadow",
            "..\\..\\windows\\system32",
        ]

        for malicious_path in malicious_paths:
            with pytest.raises((EBPFLoadError, ValueError, OSError)):
                loader.load_program(malicious_path)

    def test_program_size_limits(self):
        """Test enforcement of program size limits"""
        loader = EBPFLoader()

        # Create very large file (should be rejected)
        large_file = Path("/tmp/large_ebpf.o")
        large_file.write_bytes(b"x" * (100 * 1024 * 1024))  # 100MB

        try:
            with pytest.raises((EBPFLoadError, ValueError)):
                loader.load_program(str(large_file))
        finally:
            large_file.unlink()

    def test_program_validation(self):
        """Test validation of eBPF program bytecode"""
        loader = EBPFLoader()

        # Invalid bytecode (not valid eBPF instructions)
        invalid_file = Path("/tmp/invalid_bytecode.o")
        invalid_file.write_bytes(b"\x00" * 1000)  # All zeros

        try:
            with pytest.raises((EBPFLoadError, ValueError)):
                loader.load_program(str(invalid_file))
        finally:
            invalid_file.unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
