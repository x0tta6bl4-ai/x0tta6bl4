"""
Comprehensive test suite for load testing framework.

Tests LoadTestExecutor, PerformanceBenchmark, SLOValidator, and related functionality
for various load patterns and scenarios.
"""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.testing.load_testing import (LoadPattern, LoadTestConfig,
                                      LoadTestExecutor, LoadTestResults,
                                      PerformanceBenchmark, RequestMetrics,
                                      SLOValidator, compare_load_tests)

logger = logging.getLogger(__name__)


class TestLoadPattern:
    """Test LoadPattern enum."""

    def test_load_patterns_exist(self):
        assert LoadPattern.CONSTANT.value == "constant"
        assert LoadPattern.RAMP.value == "ramp"
        assert LoadPattern.SPIKE.value == "spike"
        assert LoadPattern.WAVE.value == "wave"
        assert LoadPattern.STRESS.value == "stress"


class TestLoadTestConfig:
    """Test LoadTestConfig dataclass."""

    def test_config_creation_with_defaults(self):
        config = LoadTestConfig(
            name="test",
            pattern=LoadPattern.CONSTANT,
            initial_load=10,
            max_load=100,
            duration_seconds=30.0,
        )
        assert config.name == "test"
        assert config.pattern == LoadPattern.CONSTANT
        assert config.initial_load == 10
        assert config.max_load == 100
        assert config.duration_seconds == 30.0
        assert config.ramp_duration_seconds == 10.0
        assert config.spike_magnitude == 2.0

    def test_config_creation_with_custom_values(self):
        config = LoadTestConfig(
            name="custom_test",
            pattern=LoadPattern.RAMP,
            initial_load=5,
            max_load=200,
            duration_seconds=60.0,
            ramp_duration_seconds=20.0,
            spike_magnitude=3.0,
        )
        assert config.ramp_duration_seconds == 20.0
        assert config.spike_magnitude == 3.0


class TestRequestMetrics:
    """Test RequestMetrics dataclass."""

    def test_successful_request_metrics(self):
        metric = RequestMetrics(
            request_id="req_1",
            start_time=100.0,
            end_time=100.5,
            success=True,
            latency_ms=500.0,
        )
        assert metric.request_id == "req_1"
        assert metric.success is True
        assert metric.latency_ms == 500.0
        assert metric.error is None

    def test_failed_request_metrics(self):
        metric = RequestMetrics(
            request_id="req_2",
            start_time=100.0,
            end_time=100.1,
            success=False,
            latency_ms=100.0,
            error="Connection timeout",
        )
        assert metric.success is False
        assert metric.error == "Connection timeout"


class TestLoadTestExecutor:
    """Test LoadTestExecutor class."""

    @pytest.fixture
    def executor(self):
        return LoadTestExecutor(max_concurrent_requests=50)

    @pytest.mark.asyncio
    async def test_execute_request_success(self, executor):
        async def success_func(request_id):
            await asyncio.sleep(0.01)

        metric = await executor._execute_request(1, success_func)
        assert metric.request_id == "req_1"
        assert metric.success is True
        assert metric.latency_ms > 0
        assert metric.error is None

    @pytest.mark.asyncio
    async def test_execute_request_failure(self, executor):
        async def failure_func(request_id):
            raise ValueError("Test error")

        metric = await executor._execute_request(1, failure_func)
        assert metric.request_id == "req_1"
        assert metric.success is False
        assert metric.error == "Test error"
        assert metric.latency_ms > 0

    def test_constant_load_generator(self, executor):
        config = LoadTestConfig(
            name="constant",
            pattern=LoadPattern.CONSTANT,
            initial_load=10,
            max_load=100,
            duration_seconds=30.0,
        )
        generator = executor._get_load_generator(config)
        assert generator(0) == 10
        assert generator(15) == 10
        assert generator(30) == 10

    def test_ramp_load_generator(self, executor):
        config = LoadTestConfig(
            name="ramp",
            pattern=LoadPattern.RAMP,
            initial_load=10,
            max_load=100,
            duration_seconds=30.0,
            ramp_duration_seconds=10.0,
        )
        generator = executor._get_load_generator(config)
        assert generator(0) == 10
        assert 40 <= generator(5) <= 60
        assert generator(10) >= 100
        assert generator(15) >= 100

    def test_spike_load_generator(self, executor):
        config = LoadTestConfig(
            name="spike",
            pattern=LoadPattern.SPIKE,
            initial_load=10,
            max_load=100,
            duration_seconds=60.0,
        )
        generator = executor._get_load_generator(config)
        assert generator(0) == 10
        assert generator(5) == 10
        assert generator(12) == 100
        assert generator(25) == 10
        assert generator(42) == 100

    def test_wave_load_generator(self, executor):
        config = LoadTestConfig(
            name="wave",
            pattern=LoadPattern.WAVE,
            initial_load=10,
            max_load=100,
            duration_seconds=40.0,
        )
        generator = executor._get_load_generator(config)
        assert 10 <= generator(0) <= 100
        assert 10 <= generator(5) <= 100
        assert 10 <= generator(10) <= 100
        assert 10 <= generator(20) <= 100

    def test_stress_load_generator(self, executor):
        config = LoadTestConfig(
            name="stress",
            pattern=LoadPattern.STRESS,
            initial_load=10,
            max_load=200,
            duration_seconds=20.0,
        )
        generator = executor._get_load_generator(config)
        assert generator(0) == 10
        assert 10 < generator(10) < 200
        assert generator(20) >= 200

    def test_calculate_results_with_metrics(self, executor):
        executor.request_metrics = [
            RequestMetrics("req_1", 0, 0.1, True, 100.0),
            RequestMetrics("req_2", 0.1, 0.2, True, 200.0),
            RequestMetrics("req_3", 0.2, 0.25, False, 50.0, "timeout"),
            RequestMetrics("req_4", 0.25, 0.35, True, 150.0),
        ]

        config = LoadTestConfig(
            name="test",
            pattern=LoadPattern.CONSTANT,
            initial_load=10,
            max_load=100,
            duration_seconds=30.0,
        )

        results = executor._calculate_results(config, 10.0, 4)

        assert results.test_name == "test"
        assert results.total_requests == 4
        assert results.successful_requests == 3
        assert results.failed_requests == 1
        assert results.min_latency_ms == 100.0
        assert results.max_latency_ms == 200.0
        assert 140 < results.avg_latency_ms < 160
        assert results.error_rate == 0.25
        assert results.throughput_rps == 0.4

    @pytest.mark.asyncio
    async def test_constant_load_test(self, executor):
        async def mock_request(request_id):
            await asyncio.sleep(0.001)

        config = LoadTestConfig(
            name="constant_test",
            pattern=LoadPattern.CONSTANT,
            initial_load=5,
            max_load=20,
            duration_seconds=0.5,
        )

        results = await executor.run_test(config, mock_request)

        assert results.test_name == "constant_test"
        assert results.pattern == LoadPattern.CONSTANT
        assert results.successful_requests > 0
        assert results.error_rate >= 0
        assert results.throughput_rps > 0
        assert len(executor.test_results) == 1

    @pytest.mark.asyncio
    async def test_ramp_load_test(self, executor):
        async def mock_request(request_id):
            await asyncio.sleep(0.001)

        config = LoadTestConfig(
            name="ramp_test",
            pattern=LoadPattern.RAMP,
            initial_load=2,
            max_load=10,
            duration_seconds=0.5,
            ramp_duration_seconds=0.2,
        )

        results = await executor.run_test(config, mock_request)

        assert results.pattern == LoadPattern.RAMP
        assert results.successful_requests > 0
        assert results.throughput_rps > 0

    @pytest.mark.asyncio
    async def test_spike_load_test(self, executor):
        async def mock_request(request_id):
            await asyncio.sleep(0.001)

        config = LoadTestConfig(
            name="spike_test",
            pattern=LoadPattern.SPIKE,
            initial_load=3,
            max_load=15,
            duration_seconds=0.5,
        )

        results = await executor.run_test(config, mock_request)

        assert results.pattern == LoadPattern.SPIKE
        assert results.successful_requests > 0

    @pytest.mark.asyncio
    async def test_test_with_failures(self, executor):
        call_count = 0

        async def failing_request(request_id):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("Simulated failure")
            await asyncio.sleep(0.001)

        config = LoadTestConfig(
            name="failing_test",
            pattern=LoadPattern.CONSTANT,
            initial_load=5,
            max_load=20,
            duration_seconds=0.3,
        )

        results = await executor.run_test(config, failing_request)

        assert results.failed_requests > 0
        assert results.error_rate > 0
        assert results.error_rate <= 1.0

    def test_concurrent_request_limiting(self, executor):
        executor.max_concurrent_requests = 10
        assert executor.max_concurrent_requests == 10


class TestLoadTestResults:
    """Test LoadTestResults dataclass."""

    def test_results_creation(self):
        results = LoadTestResults(
            test_name="test",
            pattern=LoadPattern.CONSTANT,
            total_requests=100,
            successful_requests=95,
            failed_requests=5,
            min_latency_ms=10.0,
            max_latency_ms=500.0,
            avg_latency_ms=150.0,
            p50_latency_ms=120.0,
            p95_latency_ms=400.0,
            p99_latency_ms=480.0,
            throughput_rps=100.0,
            test_duration_seconds=1.0,
            error_rate=0.05,
        )

        assert results.test_name == "test"
        assert results.successful_requests == 95
        assert results.failed_requests == 5
        assert results.error_rate == 0.05
        assert results.throughput_rps == 100.0


class TestPerformanceBenchmark:
    """Test PerformanceBenchmark class."""

    @pytest.fixture
    def benchmark(self):
        return PerformanceBenchmark()

    @pytest.mark.asyncio
    async def test_benchmark_operation_success(self, benchmark):
        async def fast_operation():
            await asyncio.sleep(0.001)

        results = await benchmark.benchmark_operation(
            "fast_op", fast_operation, iterations=10
        )

        assert "min_ms" in results
        assert "max_ms" in results
        assert "avg_ms" in results
        assert "p95_ms" in results
        assert "p99_ms" in results
        assert results["iterations"] == 10
        assert results["min_ms"] > 0
        assert results["avg_ms"] >= results["min_ms"]
        assert results["max_ms"] >= results["avg_ms"]

    @pytest.mark.asyncio
    async def test_benchmark_operation_with_failures(self, benchmark):
        call_count = 0

        async def sometimes_failing_operation():
            nonlocal call_count
            call_count += 1
            if call_count % 3 == 0:
                raise RuntimeError("Simulated error")
            await asyncio.sleep(0.001)

        results = await benchmark.benchmark_operation(
            "failing_op", sometimes_failing_operation, iterations=9
        )

        assert results["iterations"] == 9
        assert "avg_ms" in results

    @pytest.mark.asyncio
    async def test_benchmark_multiple_operations(self, benchmark):
        async def op1():
            await asyncio.sleep(0.001)

        async def op2():
            await asyncio.sleep(0.002)

        await benchmark.benchmark_operation("op1", op1, iterations=5)
        await benchmark.benchmark_operation("op2", op2, iterations=5)

        summary = benchmark.get_benchmark_summary()
        assert summary["total_benchmarks"] == 2
        assert "op1" in summary["benchmarks"]
        assert "op2" in summary["benchmarks"]

    @pytest.mark.asyncio
    async def test_benchmark_operation_empty_iterations(self, benchmark):
        async def noop():
            pass

        results = await benchmark.benchmark_operation("noop", noop, iterations=0)
        assert results["iterations"] == 0


class TestSLOValidator:
    """Test SLOValidator class."""

    @pytest.fixture
    def validator(self):
        return SLOValidator()

    @pytest.fixture
    def passing_results(self):
        return LoadTestResults(
            test_name="passing",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=999,
            failed_requests=1,
            min_latency_ms=10.0,
            max_latency_ms=80.0,
            avg_latency_ms=50.0,
            p50_latency_ms=45.0,
            p95_latency_ms=75.0,
            p99_latency_ms=80.0,
            throughput_rps=200.0,
            test_duration_seconds=5.0,
            error_rate=0.001,
        )

    @pytest.fixture
    def failing_results(self):
        return LoadTestResults(
            test_name="failing",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=900,
            failed_requests=100,
            min_latency_ms=100.0,
            max_latency_ms=500.0,
            avg_latency_ms=300.0,
            p50_latency_ms=250.0,
            p95_latency_ms=450.0,
            p99_latency_ms=500.0,
            throughput_rps=50.0,
            test_duration_seconds=20.0,
            error_rate=0.1,
        )

    def test_default_slo_definitions(self, validator):
        assert "api_response" in validator.slo_definitions
        assert "database" in validator.slo_definitions
        assert "mesh_communication" in validator.slo_definitions

    def test_validate_passing_results(self, validator, passing_results):
        passed, violations = validator.validate_results(
            passing_results, slo_name="api_response"
        )
        assert passed is True
        assert len(violations) == 0

    def test_validate_failing_p99_latency(self, validator):
        results = LoadTestResults(
            test_name="test",
            pattern=LoadPattern.CONSTANT,
            total_requests=100,
            successful_requests=100,
            failed_requests=0,
            min_latency_ms=10.0,
            max_latency_ms=200.0,
            avg_latency_ms=150.0,
            p50_latency_ms=140.0,
            p95_latency_ms=180.0,
            p99_latency_ms=200.0,
            throughput_rps=100.0,
            test_duration_seconds=1.0,
            error_rate=0.0,
        )

        passed, violations = validator.validate_results(
            results, slo_name="api_response"
        )
        assert passed is False
        assert any("P99" in v for v in violations)

    def test_validate_failing_error_rate(self, validator):
        results = LoadTestResults(
            test_name="test",
            pattern=LoadPattern.CONSTANT,
            total_requests=100,
            successful_requests=99,
            failed_requests=1,
            min_latency_ms=10.0,
            max_latency_ms=50.0,
            avg_latency_ms=30.0,
            p50_latency_ms=25.0,
            p95_latency_ms=45.0,
            p99_latency_ms=50.0,
            throughput_rps=200.0,
            test_duration_seconds=0.5,
            error_rate=0.01,
        )

        passed, violations = validator.validate_results(
            results, slo_name="api_response"
        )
        assert passed is False
        assert len(violations) > 0

    def test_validate_failing_throughput(self, validator):
        results = LoadTestResults(
            test_name="test",
            pattern=LoadPattern.CONSTANT,
            total_requests=50,
            successful_requests=50,
            failed_requests=0,
            min_latency_ms=10.0,
            max_latency_ms=50.0,
            avg_latency_ms=30.0,
            p50_latency_ms=25.0,
            p95_latency_ms=45.0,
            p99_latency_ms=50.0,
            throughput_rps=50.0,
            test_duration_seconds=1.0,
            error_rate=0.0,
        )

        passed, violations = validator.validate_results(
            results, slo_name="api_response"
        )
        assert passed is False
        assert len(violations) > 0

    def test_validate_with_nonexistent_slo(self, validator, passing_results):
        passed, violations = validator.validate_results(
            passing_results, slo_name="nonexistent_slo"
        )
        assert passed is False
        assert len(violations) > 0

    def test_validate_default_slo(self, validator, passing_results):
        passed, violations = validator.validate_results(passing_results)
        assert passed is True

    def test_set_custom_slo(self, validator):
        custom_slo = {
            "p99_latency_ms": 50,
            "error_rate": 0.0001,
            "min_throughput_rps": 500,
        }
        validator.set_custom_slo("custom", custom_slo)

        assert "custom" in validator.slo_definitions
        assert validator.slo_definitions["custom"] == custom_slo

    def test_validate_with_custom_slo(self, validator):
        custom_slo = {
            "p99_latency_ms": 50,
            "error_rate": 0.0001,
            "min_throughput_rps": 500,
        }
        validator.set_custom_slo("custom", custom_slo)

        results = LoadTestResults(
            test_name="test",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=1000,
            failed_requests=0,
            min_latency_ms=5.0,
            max_latency_ms=45.0,
            avg_latency_ms=25.0,
            p50_latency_ms=20.0,
            p95_latency_ms=40.0,
            p99_latency_ms=45.0,
            throughput_rps=600.0,
            test_duration_seconds=1.67,
            error_rate=0.0,
        )

        passed, violations = validator.validate_results(results, slo_name="custom")
        assert passed is True

    def test_validate_database_slo(self, validator):
        results = LoadTestResults(
            test_name="db_test",
            pattern=LoadPattern.CONSTANT,
            total_requests=10000,
            successful_requests=10000,
            failed_requests=0,
            min_latency_ms=1.0,
            max_latency_ms=45.0,
            avg_latency_ms=20.0,
            p50_latency_ms=18.0,
            p95_latency_ms=40.0,
            p99_latency_ms=45.0,
            throughput_rps=1500.0,
            test_duration_seconds=6.67,
            error_rate=0.0,
        )

        passed, violations = validator.validate_results(results, slo_name="database")
        assert passed is True

    def test_validate_mesh_slo(self, validator):
        results = LoadTestResults(
            test_name="mesh_test",
            pattern=LoadPattern.CONSTANT,
            total_requests=100,
            successful_requests=99,
            failed_requests=1,
            min_latency_ms=50.0,
            max_latency_ms=180.0,
            avg_latency_ms=120.0,
            p50_latency_ms=110.0,
            p95_latency_ms=170.0,
            p99_latency_ms=180.0,
            throughput_rps=75.0,
            test_duration_seconds=1.33,
            error_rate=0.01,
        )

        passed, violations = validator.validate_results(
            results, slo_name="mesh_communication"
        )
        assert passed is True


class TestCompareLoadTests:
    """Test compare_load_tests function."""

    def test_compare_identical_results(self):
        results1 = LoadTestResults(
            test_name="test1",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=1000,
            failed_requests=0,
            min_latency_ms=10.0,
            max_latency_ms=100.0,
            avg_latency_ms=50.0,
            p50_latency_ms=45.0,
            p95_latency_ms=90.0,
            p99_latency_ms=100.0,
            throughput_rps=100.0,
            test_duration_seconds=10.0,
            error_rate=0.0,
        )

        results2 = LoadTestResults(
            test_name="test2",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=1000,
            failed_requests=0,
            min_latency_ms=10.0,
            max_latency_ms=100.0,
            avg_latency_ms=50.0,
            p50_latency_ms=45.0,
            p95_latency_ms=90.0,
            p99_latency_ms=100.0,
            throughput_rps=100.0,
            test_duration_seconds=10.0,
            error_rate=0.0,
        )

        comparison = compare_load_tests(results1, results2)

        assert comparison["latency_change_percent"] == 0.0
        assert comparison["throughput_change_percent"] == 0.0
        assert comparison["error_rate_change_percent"] == 0.0

    def test_compare_worse_performance(self):
        results1 = LoadTestResults(
            test_name="test1",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=950,
            failed_requests=50,
            min_latency_ms=10.0,
            max_latency_ms=100.0,
            avg_latency_ms=50.0,
            p50_latency_ms=45.0,
            p95_latency_ms=90.0,
            p99_latency_ms=100.0,
            throughput_rps=100.0,
            test_duration_seconds=10.0,
            error_rate=0.02,
        )

        results2 = LoadTestResults(
            test_name="test2",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=900,
            failed_requests=100,
            min_latency_ms=20.0,
            max_latency_ms=200.0,
            avg_latency_ms=100.0,
            p50_latency_ms=90.0,
            p95_latency_ms=180.0,
            p99_latency_ms=200.0,
            throughput_rps=50.0,
            test_duration_seconds=20.0,
            error_rate=0.05,
        )

        comparison = compare_load_tests(results1, results2)

        assert comparison["latency_change_percent"] == 100.0
        assert comparison["throughput_change_percent"] == -50.0
        assert comparison["error_rate_change_percent"] == 150.0

    def test_compare_improved_performance(self):
        results1 = LoadTestResults(
            test_name="test1",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=900,
            failed_requests=100,
            min_latency_ms=20.0,
            max_latency_ms=200.0,
            avg_latency_ms=100.0,
            p50_latency_ms=90.0,
            p95_latency_ms=180.0,
            p99_latency_ms=200.0,
            throughput_rps=50.0,
            test_duration_seconds=20.0,
            error_rate=0.1,
        )

        results2 = LoadTestResults(
            test_name="test2",
            pattern=LoadPattern.CONSTANT,
            total_requests=1000,
            successful_requests=1000,
            failed_requests=0,
            min_latency_ms=10.0,
            max_latency_ms=100.0,
            avg_latency_ms=50.0,
            p50_latency_ms=45.0,
            p95_latency_ms=90.0,
            p99_latency_ms=100.0,
            throughput_rps=100.0,
            test_duration_seconds=10.0,
            error_rate=0.0,
        )

        comparison = compare_load_tests(results1, results2)

        assert comparison["latency_change_percent"] == -50.0
        assert comparison["throughput_change_percent"] == 100.0
        assert comparison["error_rate_change_percent"] < 0


class TestLoadTestingIntegration:
    """Integration tests for complete load testing workflows."""

    @pytest.mark.asyncio
    async def test_complete_load_test_workflow(self):
        executor = LoadTestExecutor(max_concurrent_requests=50)
        validator = SLOValidator()

        async def test_endpoint(request_id):
            await asyncio.sleep(0.01)

        config = LoadTestConfig(
            name="integration_test",
            pattern=LoadPattern.CONSTANT,
            initial_load=5,
            max_load=20,
            duration_seconds=0.5,
        )

        results = await executor.run_test(config, test_endpoint)

        assert results.successful_requests > 0

        passed, violations = validator.validate_results(results)
        assert isinstance(passed, bool)
        assert isinstance(violations, list)

    @pytest.mark.asyncio
    async def test_multiple_load_patterns(self):
        executor = LoadTestExecutor()
        patterns = [
            LoadPattern.CONSTANT,
            LoadPattern.RAMP,
            LoadPattern.SPIKE,
            LoadPattern.WAVE,
            LoadPattern.STRESS,
        ]

        async def fast_request(request_id):
            await asyncio.sleep(0.001)

        for pattern in patterns:
            config = LoadTestConfig(
                name=f"test_{pattern.value}",
                pattern=pattern,
                initial_load=2,
                max_load=10,
                duration_seconds=0.3,
            )

            results = await executor.run_test(config, fast_request)
            assert results.pattern == pattern

        assert len(executor.test_results) == 5

    @pytest.mark.asyncio
    async def test_benchmark_and_slo_validation(self):
        benchmark = PerformanceBenchmark()
        validator = SLOValidator()

        async def operation():
            await asyncio.sleep(0.001)

        results = await benchmark.benchmark_operation("op", operation, iterations=10)

        assert results["avg_ms"] > 0

        summary = benchmark.get_benchmark_summary()
        assert summary["total_benchmarks"] == 1
