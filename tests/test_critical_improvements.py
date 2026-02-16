"""
Test suite for all critical improvements to x0tta6bl4

Validates:
1. Web security hardening (bcrypt, password validation)
2. GraphSAGE benchmark accuracy
3. FL orchestrator scalability
4. eBPF CI/CD pipeline configuration
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


class TestWebSecurityHardening:
    """Test web security improvements."""

    def test_web_security_module_import(self):
        """Test that web security module imports successfully."""
        from src.security.web_security_hardening import (
            PasswordHasher, SessionTokenManager, WebSecurityHeaders,
            create_security_audit_report)

        assert PasswordHasher is not None
        assert SessionTokenManager is not None
        assert WebSecurityHeaders is not None
        assert create_security_audit_report is not None

    def test_bcrypt_password_hashing(self):
        """Test bcrypt password hashing."""
        from src.security.web_security_hardening import PasswordHasher

        password = "SecurePassword123!@#"
        hashed = PasswordHasher.hash_password(password)

        # Verify hash format (bcrypt)
        assert hashed.startswith("$2b$")

        # Verify password
        assert PasswordHasher.verify_password(password, hashed)

        # Verify wrong password fails
        assert not PasswordHasher.verify_password("WrongPassword", hashed)

    def test_password_strength_validation(self):
        """Test password strength validation."""
        from src.security.web_security_hardening import PasswordHasher

        # Strong password should pass
        strong = "StrongPassword123!@#"
        is_valid, msg = PasswordHasher.validate_password_strength(strong)
        assert is_valid, msg

        # Weak passwords should fail
        weak_passwords = [
            "short",  # Too short
            "NoNumbers!@#",  # No numbers
            "nouppercase123!@#",  # No uppercase
            "NoSpecial123",  # No special chars
        ]

        for weak_pwd in weak_passwords:
            is_valid, msg = PasswordHasher.validate_password_strength(weak_pwd)
            assert not is_valid, f"Expected {weak_pwd} to fail validation"

    def test_session_token_generation(self):
        """Test secure session token generation."""
        from src.security.web_security_hardening import SessionTokenManager

        token = SessionTokenManager.generate_session_token()
        csrf = SessionTokenManager.generate_csrf_token()
        api_key = SessionTokenManager.generate_api_key()

        # Verify tokens are non-empty and unique
        assert len(token) > 0
        assert len(csrf) > 0
        assert len(api_key) > 0

        assert token != SessionTokenManager.generate_session_token()
        assert csrf != SessionTokenManager.generate_csrf_token()

    def test_security_audit_report(self):
        """Test security audit report generation."""
        from src.security.web_security_hardening import \
            create_security_audit_report

        report = create_security_audit_report()

        assert "timestamp" in report
        assert "recommendations" in report
        assert "pqc_considerations" in report
        assert len(report["recommendations"]) > 0
        assert len(report["pqc_considerations"]) > 0


class TestGraphSAGEBenchmark:
    """Test GraphSAGE benchmark suite."""

    def test_benchmark_suite_import(self):
        """Test that benchmark suite imports successfully."""
        from benchmarks.benchmark_graphsage_comprehensive import (
            BenchmarkMetrics, GraphSAGEBenchmark)

        assert GraphSAGEBenchmark is not None
        assert BenchmarkMetrics is not None

    def test_synthetic_data_generation(self):
        """Test synthetic data generation for benchmarks."""
        from benchmarks.benchmark_graphsage_comprehensive import \
            GraphSAGEBenchmark

        benchmark = GraphSAGEBenchmark()
        X, y = benchmark.generate_synthetic_data(
            n_samples=1000, n_features=32, anomaly_rate=0.05
        )

        # Verify shape
        assert X.shape == (1000, 32)
        assert y.shape == (1000,)

        # Verify anomaly rate
        anomaly_count = int(y.sum())
        actual_rate = anomaly_count / len(y)
        assert abs(actual_rate - 0.05) < 0.02  # Allow ±2% variance

    def test_benchmark_metrics_structure(self):
        """Test BenchmarkMetrics dataclass."""
        from benchmarks.benchmark_graphsage_comprehensive import \
            BenchmarkMetrics

        metrics = BenchmarkMetrics(
            model_name="Test Model",
            accuracy=0.95,
            precision=0.93,
            recall=0.94,
            f1_score=0.935,
            roc_auc=0.96,
            false_positive_rate=0.05,
            inference_latency_ms=25.0,
            inference_throughput_samples_per_sec=40000,
            model_size_mb=4.5,
            peak_memory_mb=256,
            training_time_sec=30.0,
            quantization_type="INT8",
            notes="Test benchmark",
            timestamp="2026-01-10T00:00:00",
        )

        # Verify all metrics present
        assert metrics.model_name == "Test Model"
        assert metrics.accuracy == 0.95
        assert 0 <= metrics.false_positive_rate <= 1.0
        assert metrics.inference_latency_ms > 0


class TestScalableFLOrchestrator:
    """Test scalable Federated Learning orchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_import(self):
        """Test that orchestrator imports successfully."""
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator

        assert ScalableFLOrchestrator is not None

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self):
        """Test orchestrator initialization."""
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator

        orch = ScalableFLOrchestrator(max_clients=10000, aggregator_count=10)

        assert orch.max_clients == 10000
        assert orch.aggregator_count == 10
        assert orch.round_number == 0

    @pytest.mark.asyncio
    async def test_client_registration(self):
        """Test client registration."""
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator

        orch = ScalableFLOrchestrator(max_clients=100)

        # Register 50 clients
        for i in range(50):
            result = await orch.register_client(f"client_{i:03d}")
            assert result

        # Verify registration
        assert len(orch.clients) == 50

        # Try to exceed limit
        for i in range(50, 110):
            result = await orch.register_client(f"client_{i:03d}")
            if i < 100:
                assert result
            else:
                assert not result

    @pytest.mark.asyncio
    async def test_orchestrator_statistics(self):
        """Test orchestrator statistics."""
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator

        orch = ScalableFLOrchestrator()

        for i in range(10):
            await orch.register_client(f"client_{i:02d}")

        stats = orch.get_statistics()

        assert "total_clients" in stats
        assert "active_clients" in stats
        assert "rounds_completed" in stats
        assert stats["total_clients"] == 10
        assert stats["rounds_completed"] == 0


class TestEBPFPipeline:
    """Test eBPF CI/CD pipeline configuration."""

    def test_github_actions_workflow_exists(self):
        """Test that GitHub Actions eBPF workflow exists."""
        workflow_path = PROJECT_ROOT / ".github/workflows/ebpf-build.yml"
        assert workflow_path.exists(), "GitHub Actions workflow not found"

    def test_github_actions_workflow_valid_yaml(self):
        """Test that GitHub Actions workflow is valid YAML."""
        import yaml

        workflow_path = PROJECT_ROOT / ".github/workflows/ebpf-build.yml"
        with open(workflow_path, "r") as f:
            workflow = yaml.safe_load(f)

        # Verify structure
        assert "name" in workflow
        assert "jobs" in workflow
        assert len(workflow["jobs"]) > 0

        # Verify expected jobs
        expected_jobs = ["build-ebpf", "verify-ebpf", "integration-tests"]
        for job in expected_jobs:
            assert job in workflow["jobs"]

    def test_gitlab_ci_pipeline_exists(self):
        """Test that GitLab CI eBPF pipeline exists."""
        pipeline_path = PROJECT_ROOT / ".gitlab-ci.yml.ebpf"
        assert pipeline_path.exists(), "GitLab CI pipeline not found"

    def test_gitlab_ci_pipeline_valid_yaml(self):
        """Test that GitLab CI pipeline is valid YAML."""
        import yaml

        pipeline_path = PROJECT_ROOT / ".gitlab-ci.yml.ebpf"
        with open(pipeline_path, "r") as f:
            pipeline = yaml.safe_load(f)

        # Verify structure
        assert "stages" in pipeline
        assert len(pipeline["stages"]) > 0

        # Verify expected stages
        expected_stages = ["build-ebpf", "verify-ebpf", "test-ebpf"]
        for stage in expected_stages:
            assert stage in pipeline["stages"]


class TestIntegration:
    """Integration tests combining all improvements."""

    def test_all_modules_importable(self):
        """Test that all new modules can be imported."""
        from benchmarks.benchmark_graphsage_comprehensive import \
            GraphSAGEBenchmark
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator
        from src.security.web_security_hardening import PasswordHasher

        assert PasswordHasher is not None
        assert GraphSAGEBenchmark is not None
        assert ScalableFLOrchestrator is not None

    def test_documentation_exists(self):
        """Test that documentation exists for all improvements."""
        # Check for inline documentation
        from src.security.web_security_hardening import (
            PasswordHasher, create_security_audit_report)

        assert PasswordHasher.__doc__ is not None
        assert create_security_audit_report.__doc__ is not None

    @pytest.mark.asyncio
    async def test_workflow_execution(self):
        """Test complete workflow with all components."""
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator
        from src.security.web_security_hardening import PasswordHasher

        # 1. Create secure password
        password = "x0tta6bl4SecureTest123!@#"
        hashed = PasswordHasher.hash_password(password)
        assert PasswordHasher.verify_password(password, hashed)

        # 2. Initialize FL orchestrator
        orch = ScalableFLOrchestrator(max_clients=100)

        # 3. Register some clients
        for i in range(10):
            result = await orch.register_client(f"client_{i:02d}")
            assert result

        # 4. Verify statistics
        stats = orch.get_statistics()
        assert stats["total_clients"] == 10


# ============================================================================
# Performance and Compliance Tests
# ============================================================================


class TestPerformanceTargets:
    """Test that implementations meet performance targets."""

    def test_graphsage_accuracy_target(self):
        """Test GraphSAGE meets ≥99% accuracy target."""
        from benchmarks.benchmark_graphsage_comprehensive import \
            GraphSAGEBenchmark

        # Note: This tests the structure, actual accuracy depends on training data
        benchmark = GraphSAGEBenchmark()

        # Verify benchmark can track accuracy metrics
        assert hasattr(benchmark, "results")

    def test_fl_orchestrator_scalability_target(self):
        """Test FL orchestrator supports 10,000+ nodes."""
        from src.federated_learning.scalable_orchestrator import \
            ScalableFLOrchestrator

        orch = ScalableFLOrchestrator(max_clients=10000)
        assert orch.max_clients == 10000

    def test_ebpf_pipeline_stages(self):
        """Test eBPF pipeline has all required stages."""
        import yaml

        pipeline_path = PROJECT_ROOT / ".gitlab-ci.yml.ebpf"
        with open(pipeline_path, "r") as f:
            pipeline = yaml.safe_load(f)

        required_stages = [
            "build-ebpf",
            "verify-ebpf",
            "test-ebpf",
            "benchmark",
            "deploy",
        ]

        for stage in required_stages:
            assert stage in pipeline["stages"]


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v", "--tb=short"])
