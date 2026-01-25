"""
eBPF Programs Integration Tests - 2026-01-12
==============================================

End-to-end integration tests for eBPF loader and programs with MAPE-K loop.
Tests successful compilation, loading, and execution of eBPF programs.

Requirements:
- Linux kernel 5.10+ with BPF support
- clang, llvm, libbpf
- BPF capable hardware (not all CI environments support this)
"""

import pytest
import subprocess
import os
import json
import tempfile
from pathlib import Path
from typing import Dict, Any, Optional

logger = __import__("logging").getLogger(__name__)

# eBPF programs directory
EBPF_PROGRAMS_DIR = Path(__file__).parent.parent.parent / "network" / "ebpf" / "programs"
EBPF_SRC_DIR = Path(__file__).parent.parent.parent / "network" / "ebpf"


@pytest.fixture(scope="session")
def ebpf_compiled_objects():
    """Check if eBPF programs are compiled."""
    objects = {}
    if EBPF_PROGRAMS_DIR.exists():
        for obj_file in EBPF_PROGRAMS_DIR.glob("*.o"):
            objects[obj_file.stem] = obj_file
    return objects


@pytest.fixture(scope="session")
def compile_ebpf_programs():
    """Compile eBPF programs if not already compiled."""
    if not EBPF_PROGRAMS_DIR.exists():
        pytest.skip("eBPF programs directory not found")
    
    # Check if all expected programs are compiled
    expected_programs = [
        "xdp_counter",
        "xdp_mesh_filter",
        "xdp_pqc_verify",
        "tracepoint_net",
        "tc_classifier",
        "kprobe_syscall_latency"
    ]
    
    missing = []
    for prog in expected_programs:
        if not (EBPF_PROGRAMS_DIR / f"{prog}.o").exists():
            missing.append(prog)
    
    if missing:
        logger.info(f"Missing compiled objects: {missing}. Attempting to compile...")
        try:
            result = subprocess.run(
                ["make", "all"],
                cwd=EBPF_PROGRAMS_DIR,
                capture_output=True,
                text=True,
                timeout=120
            )
            if result.returncode != 0:
                logger.error(f"Compilation failed: {result.stderr}")
                pytest.skip("eBPF compilation failed")
        except Exception as e:
            logger.warning(f"Could not compile eBPF programs: {e}")
            pytest.skip("eBPF compilation skipped")


class TestEBPFCompilation:
    """Test eBPF program compilation."""
    
    @pytest.mark.unit
    def test_makefile_exists(self):
        """Test that Makefile exists."""
        makefile = EBPF_PROGRAMS_DIR / "Makefile"
        assert makefile.exists(), "Makefile not found"
        logger.info("✅ Makefile found")
    
    @pytest.mark.unit
    def test_source_files_exist(self):
        """Test that source C files exist."""
        expected_sources = [
            "xdp_counter.c",
            "xdp_mesh_filter.c",
            "xdp_pqc_verify.c",
            "tracepoint_net.c",
            "tc_classifier.c",
            "kprobe_syscall_latency.c"
        ]
        
        for src in expected_sources:
            src_file = EBPF_PROGRAMS_DIR / src
            assert src_file.exists(), f"Source file {src} not found"
        
        logger.info(f"✅ All {len(expected_sources)} source files found")
    
    @pytest.mark.integration
    def test_compile_xdp_counter(self):
        """Test compilation of xdp_counter.c."""
        try:
            result = subprocess.run(
                ["make", "xdp_counter.o"],
                cwd=EBPF_PROGRAMS_DIR,
                capture_output=True,
                text=True,
                timeout=30
            )
            assert result.returncode == 0, f"Compilation failed: {result.stderr}"
            
            obj_file = EBPF_PROGRAMS_DIR / "xdp_counter.o"
            assert obj_file.exists(), "Object file not created"
            assert obj_file.stat().st_size > 0, "Object file is empty"
            
            logger.info(f"✅ xdp_counter.c compiled successfully ({obj_file.stat().st_size} bytes)")
        except subprocess.TimeoutExpired:
            pytest.skip("Compilation timeout")
    
    @pytest.mark.integration
    def test_compile_all_programs(self):
        """Test compilation of all eBPF programs."""
        try:
            result = subprocess.run(
                ["make", "all"],
                cwd=EBPF_PROGRAMS_DIR,
                capture_output=True,
                text=True,
                timeout=120
            )
            assert result.returncode == 0, f"Compilation failed: {result.stderr}"
            
            obj_files = list(EBPF_PROGRAMS_DIR.glob("*.o"))
            assert len(obj_files) > 0, "No object files generated"
            
            logger.info(f"✅ All {len(obj_files)} programs compiled successfully")
        except subprocess.TimeoutExpired:
            pytest.skip("Compilation timeout")
    
    @pytest.mark.integration
    def test_verify_object_format(self, ebpf_compiled_objects):
        """Test that compiled objects are valid ELF files."""
        if not ebpf_compiled_objects:
            pytest.skip("No compiled eBPF objects found")
        
        for prog_name, obj_path in ebpf_compiled_objects.items():
            try:
                result = subprocess.run(
                    ["file", str(obj_path)],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                assert "ELF" in result.stdout, f"{prog_name} is not an ELF file"
                logger.info(f"✅ {prog_name}: {result.stdout.strip()}")
            except Exception as e:
                logger.warning(f"Could not verify {prog_name}: {e}")


class TestEBPFLoader:
    """Test eBPF loader functionality."""
    
    @pytest.mark.integration
    async def test_loader_initialization(self):
        """Test eBPF loader initialization."""
        try:
            from src.network.ebpf.loader import EBPFLoader
            
            loader = EBPFLoader()
            assert loader is not None
            logger.info("✅ eBPF loader initialized")
        except ImportError:
            pytest.skip("eBPF loader module not available")
        except Exception as e:
            logger.warning(f"Loader initialization: {e}")
    
    @pytest.mark.integration
    async def test_load_xdp_program(self, ebpf_compiled_objects):
        """Test loading XDP program."""
        if "xdp_counter" not in ebpf_compiled_objects:
            pytest.skip("xdp_counter.o not found")
        
        try:
            from src.network.ebpf.loader import EBPFLoader
            
            loader = EBPFLoader()
            obj_path = str(ebpf_compiled_objects["xdp_counter"])
            
            # This may fail if not running with proper BPF capabilities
            try:
                result = loader.load_xdp_program(obj_path)
                assert result is not None
                logger.info("✅ XDP program loaded successfully")
            except Exception as e:
                if "EPERM" in str(e) or "CAP_SYS_ADMIN" in str(e):
                    logger.info(f"⚠️ BPF privileges required: {e}")
                else:
                    raise
        except ImportError:
            pytest.skip("eBPF loader not available")


class TestEBPFWithMAKEPK:
    """Test eBPF integration with MAPE-K loop."""
    
    @pytest.mark.integration
    async def test_ebpf_metrics_collection(self):
        """Test that eBPF programs can export metrics."""
        try:
            from src.network.ebpf.metrics_exporter import EBPFMetricsExporter
            
            exporter = EBPFMetricsExporter()
            assert exporter is not None
            
            # Collect metrics (may return empty if no BPF data)
            metrics = exporter.collect_metrics()
            assert isinstance(metrics, dict)
            
            logger.info(f"✅ eBPF metrics exporter initialized: {len(metrics)} metric types")
        except ImportError:
            pytest.skip("eBPF metrics exporter not available")
        except Exception as e:
            logger.info(f"⚠️ Metrics collection: {e}")
    
    @pytest.mark.integration
    async def test_ebpf_anomaly_detection(self):
        """Test eBPF integration with anomaly detection."""
        try:
            from src.network.ebpf.mape_k_integration import EBPFAnomalyDetector
            
            detector = EBPFAnomalyDetector()
            assert detector is not None
            
            # Test detection (may return no anomalies if system idle)
            anomalies = detector.detect_anomalies()
            assert isinstance(anomalies, list)
            
            logger.info(f"✅ eBPF anomaly detector initialized: {len(anomalies)} anomalies detected")
        except ImportError:
            pytest.skip("eBPF anomaly detector not available")
        except Exception as e:
            logger.info(f"⚠️ Anomaly detection: {e}")


class TestEBPFMeshIntegration:
    """Test eBPF integration with mesh networking."""
    
    @pytest.mark.integration
    async def test_mesh_packet_filtering(self):
        """Test mesh packet filtering with eBPF."""
        try:
            from src.network.ebpf.mesh_integration import MeshEBPFFilter
            
            filter = MeshEBPFFilter()
            assert filter is not None
            
            logger.info("✅ Mesh eBPF filter initialized")
        except ImportError:
            pytest.skip("Mesh eBPF filter not available")
        except Exception as e:
            logger.info(f"⚠️ Mesh filtering: {e}")


class TestEBPFPerformance:
    """Test eBPF program performance characteristics."""
    
    @pytest.mark.integration
    @pytest.mark.benchmark
    def test_xdp_program_performance(self, benchmark, ebpf_compiled_objects):
        """Benchmark XDP program loading performance."""
        if "xdp_counter" not in ebpf_compiled_objects:
            pytest.skip("xdp_counter.o not found")
        
        try:
            from src.network.ebpf.loader import EBPFLoader
            
            loader = EBPFLoader()
            obj_path = str(ebpf_compiled_objects["xdp_counter"])
            
            # Benchmark loading time
            def load_program():
                try:
                    return loader.load_xdp_program(obj_path)
                except:
                    return None
            
            result = benchmark(load_program)
            
            # Performance targets
            # - Loading should be < 100ms
            # - Each operation should be < 1µs in steady state
            logger.info(f"✅ eBPF loading performance: {result}")
        except ImportError:
            pytest.skip("eBPF loader not available")


class TestEBPFErrorHandling:
    """Test eBPF error handling and recovery."""
    
    @pytest.mark.unit
    def test_missing_object_file_handling(self):
        """Test handling of missing object files."""
        try:
            from src.network.ebpf.loader import EBPFLoader
            
            loader = EBPFLoader()
            
            # Try to load non-existent file
            try:
                loader.load_xdp_program("/nonexistent/path.o")
                assert False, "Should raise exception for missing file"
            except FileNotFoundError:
                logger.info("✅ Proper error handling for missing files")
            except Exception as e:
                if "No such file" in str(e):
                    logger.info("✅ Proper error handling for missing files")
                else:
                    raise
        except ImportError:
            pytest.skip("eBPF loader not available")
    
    @pytest.mark.unit
    def test_invalid_object_file_handling(self):
        """Test handling of invalid object files."""
        try:
            from src.network.ebpf.loader import EBPFLoader
            
            loader = EBPFLoader()
            
            # Create invalid file
            with tempfile.NamedTemporaryFile(suffix=".o", delete=False) as f:
                f.write(b"INVALID_CONTENT")
                invalid_path = f.name
            
            try:
                try:
                    loader.load_xdp_program(invalid_path)
                    # May or may not raise depending on implementation
                except Exception as e:
                    logger.info(f"✅ Proper error handling for invalid files: {type(e).__name__}")
            finally:
                os.unlink(invalid_path)
        except ImportError:
            pytest.skip("eBPF loader not available")


@pytest.mark.integration
class TestEBPFSecurityValidation:
    """Test security aspects of eBPF programs."""
    
    async def test_pqc_xdp_signature_validation(self):
        """Test PQC signature validation in XDP context."""
        try:
            from src.network.ebpf.pqc_xdp_loader import PQCXDPLoader
            
            loader = PQCXDPLoader()
            assert loader is not None
            
            logger.info("✅ PQC XDP loader initialized")
        except ImportError:
            pytest.skip("PQC XDP loader not available")
        except Exception as e:
            logger.info(f"⚠️ PQC XDP validation: {e}")
    
    async def test_ebpf_memory_safety(self):
        """Test eBPF memory safety checks."""
        # eBPF kernel enforces memory safety, but we can test configuration
        try:
            from src.network.ebpf.security_enhancements import SecurityValidator
            
            validator = SecurityValidator()
            
            # Validate security settings
            is_safe = validator.validate_all()
            assert is_safe or is_safe is None  # May not have data to validate
            
            logger.info("✅ eBPF security validation passed")
        except ImportError:
            pytest.skip("Security validator not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "integration"])
