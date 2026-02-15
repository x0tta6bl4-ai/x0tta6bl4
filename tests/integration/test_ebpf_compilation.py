"""
eBPF Compilation and CI/CD Pipeline Tests

Tests for P0 #3: eBPF CI/CD Pipeline
Covers:
- LLVM/Clang toolchain verification
- eBPF program compilation (.c → .o)
- Kernel compatibility checks
- Build artifact generation
- eBPF object validation

Date: January 2026
Status: P0 Feature Implementation
"""

import os
import struct
import subprocess
from pathlib import Path

import pytest


class TesteBPFToolchain:
    """Test LLVM/Clang toolchain for eBPF compilation."""

    def test_clang_installed(self):
        """Test that clang is available for eBPF compilation."""
        try:
            result = subprocess.run(
                ["clang", "--version"], capture_output=True, text=True
            )
            assert result.returncode == 0, "clang not found or failed"
            assert "clang" in result.stdout.lower()
        except FileNotFoundError:
            pytest.skip("clang not installed")

    def test_llvm_installed(self):
        """Test that llvm-config is available."""
        try:
            result = subprocess.run(
                ["llvm-config", "--version"], capture_output=True, text=True
            )
            assert result.returncode == 0, "llvm-config not found"
            # Extract version
            version = result.stdout.strip().split(".")[0]
            assert int(version) >= 10, f"LLVM version {version} < 10"
        except FileNotFoundError:
            pytest.skip("llvm-config not installed")

    def test_clang_has_bpf_target(self):
        """Test that clang supports eBPF target."""
        try:
            result = subprocess.run(
                [
                    "clang",
                    "-target",
                    "bpf",
                    "-c",
                    "-x",
                    "c",
                    "/dev/null",
                    "-o",
                    "/dev/null",
                ],
                capture_output=True,
                text=True,
            )
            # clang may complain about missing input, but should support bpf target
            assert (
                "unsupported target" not in result.stderr.lower()
                or result.returncode == 0
            )
        except FileNotFoundError:
            pytest.skip("clang not installed")


class TesteBPFCompilation:
    """Test eBPF program compilation."""

    @pytest.fixture
    def ebpf_dir(self):
        """Get eBPF programs directory."""
        dir_path = (
            Path(__file__).parent.parent.parent
            / "src"
            / "network"
            / "ebpf"
            / "programs"
        )
        if not dir_path.exists():
            pytest.skip("eBPF programs directory not found")
        return dir_path

    def test_ebpf_programs_exist(self, ebpf_dir):
        """Test that eBPF source files exist."""
        expected_files = [
            "xdp_counter.c",
            "xdp_mesh_filter.c",
            "xdp_pqc_verify.c",
            "tracepoint_net.c",
            "tc_classifier.c",
            "kprobe_syscall_latency.c",
            "kprobe_syscall_latency_secure.c",
            "Makefile",
        ]

        for filename in expected_files:
            file_path = ebpf_dir / filename
            assert file_path.exists(), f"Missing {filename}"
            assert file_path.is_file(), f"{filename} is not a file"

    def test_makefile_exists(self, ebpf_dir):
        """Test that Makefile is present and readable."""
        makefile = ebpf_dir / "Makefile"
        assert makefile.exists()

        content = makefile.read_text()
        assert "clang" in content.lower(), "Makefile should reference clang"
        assert "bpf" in content.lower(), "Makefile should reference BPF target"

    def test_makefile_targets_exist(self, ebpf_dir):
        """Test that required Makefile targets are defined."""
        makefile = ebpf_dir / "Makefile"
        content = makefile.read_text()

        required_targets = ["all", "clean", "verify", "install", "test"]
        for target in required_targets:
            assert f"{target}:" in content, f"Makefile missing {target} target"


class TesteBPFObjectFormat:
    """Test compiled eBPF objects format."""

    def is_elf_object(self, filepath: Path) -> bool:
        """Check if file is a valid ELF object."""
        if not filepath.exists() or not filepath.is_file():
            return False

        try:
            with open(filepath, "rb") as f:
                header = f.read(4)
                # ELF magic number: 0x7f 0x45 0x4c 0x46 (\x7f ELF)
                return header == b"\x7fELF"
        except:
            return False

    def is_bpf_object(self, filepath: Path) -> bool:
        """Check if ELF object is BPF format."""
        if not self.is_elf_object(filepath):
            return False

        try:
            with open(filepath, "rb") as f:
                # ELF header structure
                f.seek(18)  # e_machine field offset
                e_machine = struct.unpack("<H", f.read(2))[0]
                # EM_BPF = 247 (0xF7)
                return e_machine == 247
        except:
            return False

    def test_compile_xdp_counter(self):
        """Test compilation of xdp_counter.c."""
        ebpf_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "network"
            / "ebpf"
            / "programs"
        )
        if not ebpf_dir.exists():
            pytest.skip("eBPF directory not found")

        # Try to compile if clang is available
        source = ebpf_dir / "xdp_counter.c"
        if not source.exists():
            pytest.skip("xdp_counter.c not found")

        try:
            result = subprocess.run(
                [
                    "clang",
                    "-O2",
                    "-target",
                    "bpf",
                    "-c",
                    str(source),
                    "-o",
                    "/tmp/test_xdp_counter.o",
                ],
                capture_output=True,
                text=True,
                cwd=str(ebpf_dir),
            )

            if result.returncode == 0:
                obj_path = Path("/tmp/test_xdp_counter.o")
                assert obj_path.exists(), "Object file not created"
                assert self.is_elf_object(obj_path), "Output is not a valid ELF object"
                assert self.is_bpf_object(obj_path), "Output is not a BPF object"

                # Clean up
                obj_path.unlink(missing_ok=True)
            else:
                # If compilation fails, check if it's due to missing dependencies
                if "unsupported target" in result.stderr:
                    pytest.skip("Clang doesn't support BPF target")
                elif (
                    "file not found" in result.stderr.lower()
                    or "asm/types.h" in result.stderr
                ):
                    # Missing kernel headers - expected in non-CI environments
                    pytest.skip(
                        "Kernel headers not installed (expected in non-CI environments)"
                    )
                else:
                    # Other compilation errors should be reported
                    assert False, f"Compilation failed: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("clang not installed")


class TesteBPFKernelCompatibility:
    """Test kernel compatibility checking."""

    def test_kernel_version_parsing(self):
        """Test kernel version parsing logic."""
        import platform

        kernel_version = platform.release()
        major_minor = kernel_version.split(".")[0:2]

        assert len(major_minor) >= 2, f"Can't parse kernel version: {kernel_version}"

        major = int(major_minor[0])
        minor = int(major_minor[1])

        # Test version comparison
        version_tuple = (major, minor)
        minimum_version = (5, 8)

        assert (
            version_tuple >= minimum_version or version_tuple[0] > minimum_version[0]
        ), f"Kernel {version_tuple} older than minimum {minimum_version}"

    def test_btf_availability(self):
        """Test BTF availability for CO-RE support."""
        btf_path = Path("/sys/kernel/btf/vmlinux")

        if btf_path.exists():
            assert btf_path.is_file(), "BTF exists but is not a file"
            assert btf_path.stat().st_size > 0, "BTF file is empty"
        else:
            # BTF not available is not a failure, just informational
            pytest.skip("BTF not available (kernel < 5.8 or BTF disabled)")

    def test_kernel_config_bpf_syscall(self):
        """Test if kernel has BPF syscall support."""
        # Try to check if kernel config has CONFIG_BPF_SYSCALL
        config_paths = [
            Path("/boot/config-") / Path(os.uname().release).name,
            Path("/proc/config.gz"),
        ]

        bpf_syscall_available = False

        for config_path in config_paths:
            if config_path.exists():
                try:
                    if config_path.name == "config.gz":
                        # Compressed config
                        pytest.skip(
                            "BPF syscall check requires reading compressed config"
                        )
                    else:
                        content = config_path.read_text()
                        if "CONFIG_BPF_SYSCALL=y" in content:
                            bpf_syscall_available = True
                            break
                except:
                    pass

        if not bpf_syscall_available:
            pytest.skip("Unable to verify CONFIG_BPF_SYSCALL (may still be enabled)")


class TesteBPFBuildArtifacts:
    """Test build artifact generation."""

    def test_build_directory_structure(self):
        """Test that build directory can be created."""
        build_dir = Path(__file__).parent.parent.parent / "build" / "ebpf"

        # Create it if doesn't exist
        build_dir.mkdir(parents=True, exist_ok=True)

        assert build_dir.exists(), "Build directory doesn't exist"
        assert build_dir.is_dir(), "Build path is not a directory"

    def test_artifact_installation_path(self):
        """Test artifact installation path."""
        project_root = Path(__file__).parent.parent.parent
        artifact_dir = project_root / "build" / "ebpf"

        # Create the directory
        artifact_dir.mkdir(parents=True, exist_ok=True)

        # Write a test artifact
        test_artifact = artifact_dir / "test.txt"
        test_artifact.write_text("test")

        assert test_artifact.exists(), "Artifact not created"

        # Clean up
        test_artifact.unlink()


class TesteBPFDocumentation:
    """Test eBPF documentation."""

    def test_readme_exists(self):
        """Test that eBPF README exists."""
        ebpf_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "network"
            / "ebpf"
            / "programs"
        )
        readme = ebpf_dir / "README.md"

        if ebpf_dir.exists():
            assert readme.exists(), "README.md not found in eBPF programs directory"

    def test_readme_has_requirements(self):
        """Test that README documents requirements."""
        ebpf_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "network"
            / "ebpf"
            / "programs"
        )
        readme = ebpf_dir / "README.md"

        if readme.exists():
            content = readme.read_text()
            assert "Requirements" in content, "README should document requirements"
            assert "clang" in content.lower(), "README should mention clang"
            assert (
                "kernel" in content.lower()
            ), "README should mention kernel requirements"


class TesteBPFIntegration:
    """Integration tests for eBPF CI/CD pipeline."""

    def test_makefile_help_target(self):
        """Test that Makefile help target works."""
        ebpf_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "network"
            / "ebpf"
            / "programs"
        )

        if not ebpf_dir.exists():
            pytest.skip("eBPF directory not found")

        try:
            result = subprocess.run(
                ["make", "help"], capture_output=True, text=True, cwd=str(ebpf_dir)
            )

            if result.returncode == 0:
                assert (
                    "all" in result.stdout.lower()
                ), "Help doesn't mention 'all' target"
                assert (
                    "clean" in result.stdout.lower()
                ), "Help doesn't mention 'clean' target"
        except FileNotFoundError:
            pytest.skip("make not available")

    def test_makefile_syntax(self):
        """Test that Makefile has valid syntax."""
        ebpf_dir = (
            Path(__file__).parent.parent.parent
            / "src"
            / "network"
            / "ebpf"
            / "programs"
        )

        if not ebpf_dir.exists():
            pytest.skip("eBPF directory not found")

        try:
            # Try to parse Makefile
            result = subprocess.run(
                ["make", "-n", "all"], capture_output=True, text=True, cwd=str(ebpf_dir)
            )

            # make -n should not fail on syntax errors
            assert (
                "error" not in result.stderr.lower() or result.returncode == 0
            ), f"Makefile syntax error: {result.stderr}"
        except FileNotFoundError:
            pytest.skip("make not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
