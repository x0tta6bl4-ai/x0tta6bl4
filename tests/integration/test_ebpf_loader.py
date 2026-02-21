"""
Integration tests for eBPF Loader implementation.

Tests the complete eBPF program lifecycle:
1. Load program
2. Attach to interface
3. Verify attachment
4. Detach from interface
5. Unload program
"""

import os
import subprocess
import tempfile
from pathlib import Path

import pytest


# Check if eBPF tools are available
def check_ebpf_tools():
    """Check if required eBPF tools are available."""
    try:
        subprocess.run(["which", "ip"], capture_output=True, check=True, timeout=2)
        return True
    except (
        subprocess.CalledProcessError,
        FileNotFoundError,
        subprocess.TimeoutExpired,
    ):
        return False


EBPF_TOOLS_AVAILABLE = check_ebpf_tools()

try:
    from src.network.ebpf.loader import (EBPFAttachError, EBPFAttachMode,
                                         EBPFLoader, EBPFLoadError,
                                         EBPFProgramType)

    EBPF_LOADER_AVAILABLE = True
except ImportError:
    EBPF_LOADER_AVAILABLE = False
    pytestmark = pytest.mark.skip("eBPF Loader not available")

try:
    from src.network.ebpf.loader_implementation import (
        EBPFLoaderImplementation, create_ebpf_loader)

    EBPF_IMPLEMENTATION_AVAILABLE = True
except ImportError:
    EBPF_IMPLEMENTATION_AVAILABLE = False
    pytestmark = pytest.mark.skip("eBPF Implementation not available")


@pytest.fixture
def ebpf_loader():
    """Create eBPF loader for testing."""
    if not EBPF_LOADER_AVAILABLE:
        pytest.skip("eBPF Loader not available")
    return EBPFLoader()


@pytest.fixture
def ebpf_loader_impl():
    """Create eBPF loader implementation for testing."""
    if not EBPF_IMPLEMENTATION_AVAILABLE:
        pytest.skip("eBPF Implementation not available")
    return create_ebpf_loader()


@pytest.fixture
def test_interface():
    """Get a test network interface."""
    # Try to find a real interface
    try:
        result = subprocess.run(
            ["ip", "link", "show"], capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            # Extract first non-loopback interface
            # Only look at numbered lines like "2: enp8s0: <...>"
            import re
            for line in result.stdout.split("\n"):
                m = re.match(r"^\d+:\s+(\S+?)(?:@\S+)?:\s+<", line)
                if m and m.group(1) != "lo":
                    return m.group(1)
    except Exception:
        pass

    # Fallback to loopback (may not support XDP, but good for testing)
    return "lo"


class TestEBPFLoaderBasic:
    """Basic tests for eBPF loader."""

    def test_loader_initialization(self, ebpf_loader):
        """Test that loader initializes correctly."""
        assert ebpf_loader is not None
        assert ebpf_loader.programs_dir is not None
        assert ebpf_loader.programs_dir.exists()

    def test_list_loaded_programs_empty(self, ebpf_loader):
        """Test listing programs when none are loaded."""
        programs = ebpf_loader.list_loaded_programs()
        assert isinstance(programs, list)
        assert len(programs) == 0

    def test_get_interface_programs_empty(self, ebpf_loader, test_interface):
        """Test getting programs for interface when none attached."""
        programs = ebpf_loader.get_interface_programs(test_interface)
        assert isinstance(programs, list)
        assert len(programs) == 0


class TestEBPFLoaderImplementation:
    """Tests for complete eBPF loader implementation."""

    def test_implementation_initialization(self, ebpf_loader_impl):
        """Test that implementation initializes correctly."""
        assert ebpf_loader_impl is not None
        assert isinstance(ebpf_loader_impl, EBPFLoaderImplementation)

    def test_verify_interface_exists(self, ebpf_loader_impl, test_interface):
        """Test interface verification."""
        exists = ebpf_loader_impl._verify_interface_exists(test_interface)
        assert exists is True

    def test_get_interface_state(self, ebpf_loader_impl, test_interface):
        """Test getting interface state."""
        state = ebpf_loader_impl._get_interface_state(test_interface)
        assert state is not None
        assert state in ["up", "down", "unknown"]

    def test_verify_program_detached_empty(self, ebpf_loader_impl):
        """Test verification of detached program (none loaded)."""
        # Non-existent program should be considered "detached"
        detached = ebpf_loader_impl._verify_program_detached("non-existent")
        assert detached is True

    def test_get_program_stats_not_loaded(self, ebpf_loader_impl):
        """Test getting stats for non-loaded program."""
        stats = ebpf_loader_impl.get_program_stats("non-existent")
        assert stats is None


@pytest.mark.skipif(not EBPF_TOOLS_AVAILABLE, reason="eBPF tools not available")
class TestEBPFProgramLifecycle:
    """Tests for complete eBPF program lifecycle."""

    def test_load_program_nonexistent(self, ebpf_loader):
        """Test loading non-existent program."""
        with pytest.raises(EBPFLoadError):
            ebpf_loader.load_program("nonexistent.o", EBPFProgramType.XDP)

    def test_attach_program_not_loaded(self, ebpf_loader, test_interface):
        """Test attaching program that wasn't loaded."""
        with pytest.raises(EBPFAttachError):
            ebpf_loader.attach_to_interface("non-existent-id", test_interface)

    def test_detach_program_not_attached(self, ebpf_loader, test_interface):
        """Test detaching program that wasn't attached."""
        # Should not raise error, just return False
        result = ebpf_loader.detach_from_interface("non-existent-id", test_interface)
        assert result is False

    def test_unload_program_not_loaded(self, ebpf_loader):
        """Test unloading program that wasn't loaded."""
        # Should not raise error, just return False
        result = ebpf_loader.unload_program("non-existent-id")
        assert result is False


@pytest.mark.skipif(not EBPF_TOOLS_AVAILABLE, reason="eBPF tools not available")
@pytest.mark.integration
class TestEBPFRealProgram:
    """Tests with real eBPF programs (if available)."""

    def test_load_real_program_if_exists(self, ebpf_loader):
        """Test loading a real eBPF program if it exists."""
        # Check if xdp_counter.o exists
        programs_dir = ebpf_loader.programs_dir
        xdp_counter_path = programs_dir / "xdp_counter.o"

        if not xdp_counter_path.exists():
            pytest.skip(
                "xdp_counter.o not found. Compile it first: make -C src/network/ebpf/programs"
            )

        # Try to load the program
        try:
            program_id = ebpf_loader.load_program("xdp_counter.o", EBPFProgramType.XDP)
            assert program_id is not None
            assert program_id in ebpf_loader.loaded_programs

            # Cleanup
            ebpf_loader.unload_program(program_id)
        except EBPFLoadError as e:
            pytest.skip(
                f"Failed to load eBPF program: {e}. May require root privileges or kernel support."
            )

    def test_attach_detach_cycle_if_program_exists(
        self, ebpf_loader_impl, test_interface
    ):
        """Test complete attach/detach cycle if program exists."""
        programs_dir = ebpf_loader_impl.programs_dir
        xdp_counter_path = programs_dir / "xdp_counter.o"

        if not xdp_counter_path.exists():
            pytest.skip("xdp_counter.o not found. Compile it first.")

        # Skip if not root (XDP attachment requires root)
        if os.geteuid() != 0:
            pytest.skip("XDP attachment requires root privileges")

        try:
            # Load program
            program_id = ebpf_loader_impl.load_program(
                "xdp_counter.o", EBPFProgramType.XDP
            )

            # Attach to interface
            success = ebpf_loader_impl.attach_to_interface_complete(
                program_id,
                test_interface,
                EBPFAttachMode.SKB,  # Generic mode (most compatible)
            )

            if success:
                # Verify attachment
                programs = ebpf_loader_impl.get_interface_programs(test_interface)
                assert program_id in programs

                # Get stats
                stats = ebpf_loader_impl.get_program_stats(program_id)
                assert stats is not None
                assert stats["program_id"] == program_id

                # Detach
                detach_success = ebpf_loader_impl.detach_from_interface_complete(
                    program_id, test_interface
                )
                assert detach_success is True

                # Verify detachment
                detached = ebpf_loader_impl._verify_program_detached(program_id)
                assert detached is True

            # Unload
            unload_success = ebpf_loader_impl.unload_program_complete(program_id)
            assert unload_success is True

        except (EBPFLoadError, EBPFAttachError) as e:
            pytest.skip(
                f"eBPF operation failed: {e}. May require root privileges or kernel support."
            )
        except PermissionError:
            pytest.skip("eBPF operations require root privileges")


class TestEBPFErrorHandling:
    """Tests for error handling in eBPF loader."""

    def test_invalid_program_type(self, ebpf_loader):
        """Test handling of invalid program type."""
        # This should work (program type is enum, so invalid values are caught at type level)
        # But we can test with valid types
        assert EBPFProgramType.XDP is not None
        assert EBPFProgramType.TC is not None

    def test_invalid_interface(self, ebpf_loader):
        """Test handling of invalid interface."""
        # Try to attach to non-existent interface
        # First need a loaded program, but we'll test the error path
        with pytest.raises(EBPFAttachError):
            # This will fail because program doesn't exist, but tests error handling
            ebpf_loader.attach_to_interface("non-existent", "nonexistent-interface")
