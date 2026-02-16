#!/usr/bin/env python3
"""
Comprehensive unit tests for MAPE-K Quality Integration module.

Covers all public methods, error paths, and edge cases not covered
by the existing test file.
"""

import asyncio
import json
import shutil
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, PropertyMock, patch

import pytest

from src.quality.mapek_quality_integration import (MAPEKQualityMonitor,
                                                   QualityImprovement,
                                                   QualityThresholds)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def temp_repo(tmp_path):
    """Create a temporary repository with a sample Python file."""
    sample = tmp_path / "sample.py"
    sample.write_text("def hello():\n    return 'world'\n\nclass Foo:\n    pass\n")
    return tmp_path


@pytest.fixture
def mock_deps():
    """Patch the three heavy dependencies used by MAPEKQualityMonitor.__init__."""
    with (
        patch("src.quality.mapek_quality_integration.CodeQualityAnalyzer") as mock_cqa,
        patch("src.quality.mapek_quality_integration.ThreadSafeMAPEKLoop") as mock_loop,
        patch(
            "src.quality.mapek_quality_integration.ThreadSafeMetrics"
        ) as mock_metrics,
    ):
        yield {
            "CodeQualityAnalyzer": mock_cqa,
            "ThreadSafeMAPEKLoop": mock_loop,
            "ThreadSafeMetrics": mock_metrics,
        }


@pytest.fixture
def monitor(temp_repo, mock_deps):
    """Create a MAPEKQualityMonitor with mocked dependencies."""
    m = MAPEKQualityMonitor(str(temp_repo))
    return m


@pytest.fixture
def monitor_with_custom_thresholds(temp_repo, mock_deps):
    """Create monitor with non-default thresholds."""
    thresholds = QualityThresholds(
        min_overall_score=80.0,
        max_complexity=10.0,
        min_test_coverage=70.0,
        max_security_issues=2,
        max_technical_debt_hours=4.0,
        min_maintainability=75.0,
    )
    return MAPEKQualityMonitor(str(temp_repo), thresholds=thresholds)


def _make_total_metrics(
    overall_score=85.0,
    security_issues=0,
    technical_debt=60,
    test_coverage=80.0,
    complexity_score=5.0,
    style_violations=5,
    maintainability_index=80.0,
    duplicate_code=2.0,
):
    """Helper to create a mock total_metrics object."""
    m = Mock()
    m.overall_score = Mock(return_value=overall_score)
    m.security_issues = security_issues
    m.technical_debt = technical_debt
    m.test_coverage = test_coverage
    m.complexity_score = complexity_score
    m.style_violations = style_violations
    m.maintainability_index = maintainability_index
    m.duplicate_code = duplicate_code
    return m


# ---------------------------------------------------------------------------
# QualityThresholds tests
# ---------------------------------------------------------------------------


class TestQualityThresholds:
    def test_defaults(self):
        t = QualityThresholds()
        assert t.min_overall_score == 70.0
        assert t.max_complexity == 15.0
        assert t.min_test_coverage == 50.0
        assert t.max_security_issues == 5
        assert t.max_technical_debt_hours == 8.0
        assert t.min_maintainability == 60.0

    def test_custom_values(self):
        t = QualityThresholds(min_overall_score=90.0, max_complexity=5.0)
        assert t.min_overall_score == 90.0
        assert t.max_complexity == 5.0


# ---------------------------------------------------------------------------
# QualityImprovement tests
# ---------------------------------------------------------------------------


class TestQualityImprovement:
    def test_creation(self):
        imp = QualityImprovement(
            action_type="FIX_SECURITY",
            file_path="/a/b.py",
            description="Fix XSS",
            priority="CRITICAL",
            estimated_effort=15,
        )
        assert imp.automated is False  # default

    def test_automated_flag(self):
        imp = QualityImprovement(
            action_type="FORMAT_CODE",
            file_path="x.py",
            description="fmt",
            priority="LOW",
            estimated_effort=5,
            automated=True,
        )
        assert imp.automated is True


# ---------------------------------------------------------------------------
# MAPEKQualityMonitor.__init__ tests
# ---------------------------------------------------------------------------


class TestMAPEKQualityMonitorInit:
    def test_default_thresholds(self, temp_repo, mock_deps):
        m = MAPEKQualityMonitor(str(temp_repo))
        assert m.thresholds.min_overall_score == 70.0
        assert m.repo_root == Path(temp_repo)

    def test_custom_thresholds(self, monitor_with_custom_thresholds):
        assert monitor_with_custom_thresholds.thresholds.min_overall_score == 80.0

    def test_initial_state(self, monitor):
        assert monitor.quality_metrics == {}
        assert monitor.improvement_queue == []
        assert monitor.last_analysis_time is None


# ---------------------------------------------------------------------------
# _calculate_health_score tests
# ---------------------------------------------------------------------------


class TestCalculateHealthScore:
    def test_no_quality_metrics(self, monitor):
        """Empty quality_metrics -> default 50.0."""
        assert monitor._calculate_health_score() == 50.0

    def test_no_total_metrics_key(self, monitor):
        """quality_metrics present but no total_metrics -> default 50.0."""
        monitor.quality_metrics = {"files_analyzed": 5}
        assert monitor._calculate_health_score() == 50.0

    def test_perfect_health(self, monitor):
        """All metrics ideal -> high health score."""
        tm = Mock()
        tm.overall_score = Mock(return_value=100.0)
        tm.security_issues = 0
        tm.technical_debt = 0
        monitor.quality_metrics = {"total_metrics": tm}
        score = monitor._calculate_health_score()
        assert score == pytest.approx(100.0, abs=1.0)

    def test_many_security_issues_lowers_health(self, monitor):
        tm = Mock()
        tm.overall_score = Mock(return_value=100.0)
        tm.security_issues = 20  # very high
        tm.technical_debt = 0
        monitor.quality_metrics = {"total_metrics": tm}
        score = monitor._calculate_health_score()
        # security_factor = max(0, 1 - 20*0.1) = 0
        # debt_factor = 1, quality_factor = 1
        # health = (1*0.5 + 0*0.3 + 1*0.2)*100 = 70
        assert score == pytest.approx(70.0, abs=1.0)

    def test_high_technical_debt_lowers_health(self, monitor):
        tm = Mock()
        tm.overall_score = Mock(return_value=100.0)
        tm.security_issues = 0
        tm.technical_debt = 60 * 48  # 48 hours in minutes
        monitor.quality_metrics = {"total_metrics": tm}
        score = monitor._calculate_health_score()
        # debt_factor = max(0, 1 - 48/24) = 0
        assert score == pytest.approx(80.0, abs=1.0)

    def test_health_clamped_to_0_100(self, monitor):
        tm = Mock()
        tm.overall_score = Mock(return_value=0.0)
        tm.security_issues = 100
        tm.technical_debt = 60 * 100
        monitor.quality_metrics = {"total_metrics": tm}
        score = monitor._calculate_health_score()
        assert 0.0 <= score <= 100.0


# ---------------------------------------------------------------------------
# _get_repository_stats tests
# ---------------------------------------------------------------------------


class TestGetRepositoryStats:
    def test_basic_stats(self, monitor, temp_repo):
        """Should count files and compute size."""
        stats = monitor._get_repository_stats()
        assert stats["file_count"] >= 1
        assert stats["size_mb"] >= 0

    def test_git_not_available(self, monitor, temp_repo):
        """When git is not available, defaults are used."""
        with patch("subprocess.run", side_effect=FileNotFoundError):
            stats = monitor._get_repository_stats()
        assert stats["last_commit_hours"] == float("inf")
        assert stats["active_branches"] == 1

    def test_git_timeout(self, monitor, temp_repo):
        import subprocess as sp

        with patch(
            "subprocess.run", side_effect=sp.TimeoutExpired(cmd="git", timeout=10)
        ):
            stats = monitor._get_repository_stats()
        assert stats["last_commit_hours"] == float("inf")
        assert stats["active_branches"] == 1

    def test_git_successful(self, monitor, temp_repo):
        import subprocess as sp
        import time

        commit_time = int(time.time()) - 3600  # 1 hour ago
        log_result = Mock(returncode=0, stdout=f"{commit_time}\n")
        branch_result = Mock(returncode=0, stdout="  main\n  dev\n  feature\n")

        def fake_run(cmd, **kwargs):
            if "log" in cmd:
                return log_result
            return branch_result

        with patch("subprocess.run", side_effect=fake_run):
            stats = monitor._get_repository_stats()
        assert stats["last_commit_hours"] == pytest.approx(1.0, abs=0.1)
        assert stats["active_branches"] == 3

    def test_git_nonzero_returncode(self, monitor, temp_repo):
        fail_result = Mock(returncode=1, stdout="")
        with patch("subprocess.run", return_value=fail_result):
            stats = monitor._get_repository_stats()
        assert stats["last_commit_hours"] == float("inf")
        assert stats["active_branches"] == 1


# ---------------------------------------------------------------------------
# _collect_system_metrics tests
# ---------------------------------------------------------------------------


class TestCollectSystemMetrics:
    def test_returns_expected_keys(self, monitor):
        with (
            patch.object(
                monitor,
                "_get_repository_stats",
                return_value={
                    "size_mb": 10.0,
                    "file_count": 42,
                    "last_commit_hours": 2.0,
                    "active_branches": 3,
                },
            ),
            patch.object(monitor, "_calculate_health_score", return_value=75.0),
        ):
            metrics = monitor._collect_system_metrics()
        assert metrics["repo_size_mb"] == 10.0
        assert metrics["file_count"] == 42
        assert metrics["health_score"] == 75.0


# ---------------------------------------------------------------------------
# _generate_improvements tests
# ---------------------------------------------------------------------------


class TestGenerateImprovements:
    def test_no_total_metrics(self, monitor):
        assert monitor._generate_improvements({}) == []

    def test_security_issues_generate_improvements(self, monitor):
        tm = _make_total_metrics(security_issues=3)
        issues = [
            {
                "file_path": "a.py",
                "category": "XSS",
                "description": "XSS vuln",
                "severity": "HIGH",
            },
            {
                "file_path": "b.py",
                "category": "SQLi",
                "description": "SQL injection",
                "severity": "CRITICAL",
            },
        ]
        result = monitor._generate_improvements(
            {"total_metrics": tm, "security_issues": issues}
        )
        sec_imps = [i for i in result if i.action_type == "FIX_SECURITY"]
        assert len(sec_imps) == 2
        # CRITICAL should sort before HIGH
        assert result[0].priority == "CRITICAL"

    def test_low_test_coverage_generates_add_tests(self, monitor):
        tm = _make_total_metrics(test_coverage=30.0)
        result = monitor._generate_improvements({"total_metrics": tm})
        add_tests = [i for i in result if i.action_type == "ADD_TESTS"]
        assert len(add_tests) == 1
        assert "30.0%" in add_tests[0].description

    def test_high_complexity_generates_refactor(self, monitor):
        tm = _make_total_metrics(complexity_score=20.0)
        result = monitor._generate_improvements({"total_metrics": tm})
        refactors = [
            i
            for i in result
            if i.action_type == "REFACTOR" and "complexity" in i.description.lower()
        ]
        assert len(refactors) == 1

    def test_high_technical_debt_generates_refactor(self, monitor):
        # max_technical_debt_hours default = 8, so 600 min = 10h > 8h
        tm = _make_total_metrics(technical_debt=600)
        result = monitor._generate_improvements({"total_metrics": tm})
        debt_refactors = [i for i in result if "debt" in i.description.lower()]
        assert len(debt_refactors) == 1

    def test_style_violations_generate_format_code(self, monitor):
        tm = _make_total_metrics(style_violations=30)
        result = monitor._generate_improvements({"total_metrics": tm})
        fmt = [i for i in result if i.action_type == "FORMAT_CODE"]
        assert len(fmt) == 1
        assert fmt[0].automated is True

    def test_no_improvements_when_all_good(self, monitor):
        tm = _make_total_metrics(
            security_issues=0,
            test_coverage=80.0,
            complexity_score=5.0,
            technical_debt=60,  # 1h
            style_violations=5,
        )
        result = monitor._generate_improvements({"total_metrics": tm})
        assert result == []

    def test_all_improvements_at_once(self, monitor):
        tm = _make_total_metrics(
            security_issues=2,
            test_coverage=30.0,
            complexity_score=20.0,
            technical_debt=600,
            style_violations=30,
        )
        issues = [
            {
                "file_path": "x.py",
                "category": "sec",
                "description": "bad",
                "severity": "HIGH",
            }
        ]
        result = monitor._generate_improvements(
            {"total_metrics": tm, "security_issues": issues}
        )
        types = {i.action_type for i in result}
        assert types == {"FIX_SECURITY", "ADD_TESTS", "REFACTOR", "FORMAT_CODE"}

    def test_security_issues_capped_at_five(self, monitor):
        tm = _make_total_metrics(security_issues=10)
        issues = [
            {
                "file_path": f"f{i}.py",
                "category": "sec",
                "description": f"issue {i}",
                "severity": "MEDIUM",
            }
            for i in range(10)
        ]
        result = monitor._generate_improvements(
            {"total_metrics": tm, "security_issues": issues}
        )
        sec_imps = [i for i in result if i.action_type == "FIX_SECURITY"]
        assert len(sec_imps) == 5

    def test_custom_thresholds_affect_improvements(
        self, monitor_with_custom_thresholds
    ):
        m = monitor_with_custom_thresholds
        # test_coverage 60 < 70 threshold -> ADD_TESTS
        tm = _make_total_metrics(test_coverage=60.0)
        result = m._generate_improvements({"total_metrics": tm})
        assert any(i.action_type == "ADD_TESTS" for i in result)

    def test_priority_sorting(self, monitor):
        tm = _make_total_metrics(
            security_issues=1, test_coverage=30.0, style_violations=30
        )
        issues = [
            {
                "file_path": "a.py",
                "category": "sec",
                "description": "bad",
                "severity": "LOW",
            }
        ]
        result = monitor._generate_improvements(
            {"total_metrics": tm, "security_issues": issues}
        )
        priorities = [i.priority for i in result]
        priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        order_values = [priority_order.get(p, 3) for p in priorities]
        assert order_values == sorted(order_values)


# ---------------------------------------------------------------------------
# get_quality_report tests
# ---------------------------------------------------------------------------


class TestGetQualityReport:
    def test_no_data_returns_error(self, monitor):
        report = monitor.get_quality_report()
        assert "error" in report

    def test_with_data(self, monitor):
        tm = _make_total_metrics()
        monitor.quality_metrics = {"total_metrics": tm, "files_analyzed": 10}
        monitor.last_analysis_time = datetime(2025, 1, 1, 12, 0, 0)
        monitor.improvement_queue = [
            QualityImprovement("REFACTOR", "f.py", "desc", "HIGH", 30, False),
        ]
        monitor.metrics.get_stats_snapshot = Mock(return_value={"counters": {}})

        report = monitor.get_quality_report()
        assert "report_timestamp" in report
        assert report["last_analysis"] == "2025-01-01T12:00:00"
        assert len(report["improvement_queue"]) == 1
        assert report["improvement_queue"][0]["action_type"] == "REFACTOR"
        assert report["thresholds"]["min_overall_score"] == 70.0

    def test_last_analysis_none(self, monitor):
        monitor.quality_metrics = {"some": "data"}
        monitor.metrics.get_stats_snapshot = Mock(return_value={})
        report = monitor.get_quality_report()
        assert report["last_analysis"] is None


# ---------------------------------------------------------------------------
# analyze_quality tests
# ---------------------------------------------------------------------------


class TestAnalyzeQuality:
    @pytest.mark.asyncio
    async def test_analyze_quality_stores_results(self, monitor):
        tm = _make_total_metrics(
            overall_score=90.0,
            security_issues=1,
            technical_debt=120,
            test_coverage=75.0,
            complexity_score=8.0,
        )
        analysis = {
            "total_metrics": tm,
            "files_analyzed": 5,
            "security_issues": [],
        }
        monitor.quality_analyzer.analyze_repository = Mock(return_value=analysis)

        result = await monitor.analyze_quality()

        assert result is analysis
        assert monitor.quality_metrics is analysis
        assert monitor.last_analysis_time is not None
        monitor.metrics.set_gauge.assert_any_call("quality_score", 90.0)
        monitor.metrics.set_gauge.assert_any_call("security_issues", 1.0)
        monitor.metrics.set_gauge.assert_any_call("technical_debt", 120.0)

    @pytest.mark.asyncio
    async def test_analyze_quality_no_total_metrics(self, monitor):
        analysis = {"files_analyzed": 0}
        monitor.quality_analyzer.analyze_repository = Mock(return_value=analysis)

        # Source code accesses total_metrics.overall_score() without None check
        with pytest.raises(AttributeError):
            await monitor.analyze_quality()

    @pytest.mark.asyncio
    async def test_analyze_quality_generates_improvements(self, monitor):
        tm = _make_total_metrics(
            security_issues=3, test_coverage=30.0, style_violations=25
        )
        analysis = {
            "total_metrics": tm,
            "files_analyzed": 10,
            "security_issues": [
                {
                    "file_path": "a.py",
                    "category": "x",
                    "description": "y",
                    "severity": "HIGH",
                },
            ],
        }
        monitor.quality_analyzer.analyze_repository = Mock(return_value=analysis)

        await monitor.analyze_quality()
        assert len(monitor.improvement_queue) > 0


# ---------------------------------------------------------------------------
# _process_cycle_results tests
# ---------------------------------------------------------------------------


class TestProcessCycleResults:
    @pytest.mark.asyncio
    async def test_complete_phase(self, monitor):
        state = Mock()
        state.phase = "COMPLETE"
        state.decisions = ["decision_1", "decision_2"]
        state.actions = ["action_1"]

        await monitor._process_cycle_results(state)

        assert monitor.metrics.add_to_set.call_count == 3
        monitor.metrics.increment_counter.assert_called_with("actions_executed")

    @pytest.mark.asyncio
    async def test_error_phase(self, monitor):
        state = Mock()
        state.phase = "ERROR"
        state.metrics = {"error": "something broke"}

        await monitor._process_cycle_results(state)
        monitor.metrics.increment_counter.assert_called_with("failed_cycles")

    @pytest.mark.asyncio
    async def test_other_phase(self, monitor):
        state = Mock()
        state.phase = "IN_PROGRESS"
        # Should not raise or call metrics
        await monitor._process_cycle_results(state)

    @pytest.mark.asyncio
    async def test_error_phase_no_error_key(self, monitor):
        state = Mock()
        state.phase = "ERROR"
        state.metrics = {}  # no 'error' key -> uses 'Unknown error'
        await monitor._process_cycle_results(state)
        monitor.metrics.increment_counter.assert_called_with("failed_cycles")

    @pytest.mark.asyncio
    async def test_complete_no_decisions_or_actions(self, monitor):
        state = Mock()
        state.phase = "COMPLETE"
        state.decisions = []
        state.actions = []
        await monitor._process_cycle_results(state)
        # No add_to_set or increment_counter for actions
        monitor.metrics.add_to_set.assert_not_called()


# ---------------------------------------------------------------------------
# run_single_analysis tests
# ---------------------------------------------------------------------------


class TestRunSingleAnalysis:
    @pytest.mark.asyncio
    async def test_run_single_analysis(self, monitor):
        mock_state = Mock()
        mock_state.phase = "COMPLETE"
        mock_state.decisions = []
        mock_state.actions = []
        mock_state.get_snapshot = Mock(return_value={"phase": "COMPLETE"})

        monitor.mapek_loop.execute_cycle = AsyncMock(return_value=mock_state)

        result = await monitor.run_single_analysis()

        assert "analysis_timestamp" in result
        assert "quality_metrics" in result
        assert result["improvements_suggested"] == 0
        assert result["mapek_state"] == {"phase": "COMPLETE"}

    @pytest.mark.asyncio
    async def test_run_single_analysis_with_improvements(self, monitor):
        mock_state = Mock()
        mock_state.phase = "COMPLETE"
        mock_state.decisions = []
        mock_state.actions = []
        mock_state.get_snapshot = Mock(return_value={})

        monitor.mapek_loop.execute_cycle = AsyncMock(return_value=mock_state)
        monitor.improvement_queue = [
            QualityImprovement("FIX", "f.py", "d", "HIGH", 10),
            QualityImprovement("FIX", "g.py", "d", "HIGH", 10),
        ]

        result = await monitor.run_single_analysis()
        assert result["improvements_suggested"] == 2


# ---------------------------------------------------------------------------
# start_monitoring tests
# ---------------------------------------------------------------------------


class TestStartMonitoring:
    @pytest.mark.asyncio
    async def test_start_monitoring_runs_cycle(self, monitor):
        """Verify start_monitoring calls execute_cycle and then sleeps."""
        mock_state = Mock()
        mock_state.phase = "COMPLETE"
        mock_state.decisions = []
        mock_state.actions = []

        monitor.mapek_loop.execute_cycle = AsyncMock(return_value=mock_state)

        call_count = 0

        original_sleep = asyncio.sleep

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("stop loop")

        with patch(
            "src.quality.mapek_quality_integration.asyncio.sleep",
            side_effect=fake_sleep,
        ):
            with pytest.raises(KeyboardInterrupt):
                await monitor.start_monitoring(interval_seconds=1)

        assert monitor.mapek_loop.execute_cycle.call_count >= 1

    @pytest.mark.asyncio
    async def test_start_monitoring_handles_error(self, monitor):
        """On exception, the loop should continue after a brief sleep."""
        monitor.mapek_loop.execute_cycle = AsyncMock(side_effect=RuntimeError("boom"))

        call_count = 0

        async def fake_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise KeyboardInterrupt("stop")

        with patch(
            "src.quality.mapek_quality_integration.asyncio.sleep",
            side_effect=fake_sleep,
        ):
            with pytest.raises(KeyboardInterrupt):
                await monitor.start_monitoring(interval_seconds=1)

        # The error path sleeps 60s; we verify it was called
        assert call_count >= 1


# ---------------------------------------------------------------------------
# execute_improvement tests
# ---------------------------------------------------------------------------


class TestExecuteImprovement:
    @pytest.mark.asyncio
    async def test_format_code_automated(self, monitor):
        imp = QualityImprovement("FORMAT_CODE", "x.py", "fmt", "LOW", 5, automated=True)
        with patch.object(
            monitor, "_auto_format_code", new_callable=AsyncMock, return_value=True
        ):
            result = await monitor.execute_improvement(imp)
        assert result is True
        monitor.metrics.increment_counter.assert_called_with("improvements_executed")

    @pytest.mark.asyncio
    async def test_format_code_not_automated(self, monitor):
        """FORMAT_CODE that is not automated -> unknown improvement type path."""
        imp = QualityImprovement(
            "FORMAT_CODE", "x.py", "fmt", "LOW", 5, automated=False
        )
        result = await monitor.execute_improvement(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_fix_security(self, monitor):
        imp = QualityImprovement("FIX_SECURITY", "x.py", "fix sec", "HIGH", 30)
        with patch.object(
            monitor, "_suggest_security_fix", new_callable=AsyncMock, return_value=True
        ):
            result = await monitor.execute_improvement(imp)
        assert result is True

    @pytest.mark.asyncio
    async def test_add_tests(self, monitor):
        imp = QualityImprovement("ADD_TESTS", "x.py", "add tests", "MEDIUM", 60)
        with patch.object(
            monitor, "_suggest_test_addition", new_callable=AsyncMock, return_value=True
        ):
            result = await monitor.execute_improvement(imp)
        assert result is True

    @pytest.mark.asyncio
    async def test_refactor(self, monitor):
        imp = QualityImprovement("REFACTOR", "x.py", "refactor", "MEDIUM", 120)
        with patch.object(
            monitor, "_suggest_refactoring", new_callable=AsyncMock, return_value=True
        ):
            result = await monitor.execute_improvement(imp)
        assert result is True

    @pytest.mark.asyncio
    async def test_unknown_type(self, monitor):
        imp = QualityImprovement("UNKNOWN_TYPE", "x.py", "??", "LOW", 5)
        result = await monitor.execute_improvement(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_action_returns_false(self, monitor):
        imp = QualityImprovement("ADD_TESTS", "x.py", "add tests", "MEDIUM", 60)
        with patch.object(
            monitor,
            "_suggest_test_addition",
            new_callable=AsyncMock,
            return_value=False,
        ):
            result = await monitor.execute_improvement(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_exception_in_action(self, monitor):
        imp = QualityImprovement("ADD_TESTS", "x.py", "add tests", "MEDIUM", 60)
        with patch.object(
            monitor,
            "_suggest_test_addition",
            new_callable=AsyncMock,
            side_effect=RuntimeError("fail"),
        ):
            result = await monitor.execute_improvement(imp)
        assert result is False


# ---------------------------------------------------------------------------
# _auto_format_code tests
# ---------------------------------------------------------------------------


class TestAutoFormatCode:
    @pytest.mark.asyncio
    async def test_already_formatted(self, monitor):
        result_mock = Mock(returncode=0, stdout="", stderr="")
        with patch("subprocess.run", return_value=result_mock):
            result = await monitor._auto_format_code()
        assert result is True

    @pytest.mark.asyncio
    async def test_needs_formatting_success(self, monitor):
        check_result = Mock(returncode=1, stdout="diff", stderr="")
        format_result = Mock(returncode=0, stdout="", stderr="")

        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return check_result
            return format_result

        with patch("subprocess.run", side_effect=fake_run):
            result = await monitor._auto_format_code()
        assert result is True

    @pytest.mark.asyncio
    async def test_needs_formatting_failure(self, monitor):
        check_result = Mock(returncode=1)
        format_result = Mock(returncode=1)

        call_count = 0

        def fake_run(cmd, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return check_result
            return format_result

        with patch("subprocess.run", side_effect=fake_run):
            result = await monitor._auto_format_code()
        assert result is False

    @pytest.mark.asyncio
    async def test_black_not_found(self, monitor):
        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = await monitor._auto_format_code()
        assert result is False

    @pytest.mark.asyncio
    async def test_timeout(self, monitor):
        import subprocess as sp

        with patch(
            "subprocess.run", side_effect=sp.TimeoutExpired(cmd="black", timeout=60)
        ):
            result = await monitor._auto_format_code()
        assert result is False


# ---------------------------------------------------------------------------
# _suggest_security_fix tests
# ---------------------------------------------------------------------------


class TestSuggestSecurityFix:
    @pytest.mark.asyncio
    async def test_file_not_found(self, monitor):
        imp = QualityImprovement(
            "FIX_SECURITY", "/nonexistent/file.py", "fix", "HIGH", 30
        )
        result = await monitor._suggest_security_fix(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_security_issues_in_file(self, monitor, temp_repo):
        sample_file = temp_repo / "sample.py"
        imp = QualityImprovement("FIX_SECURITY", str(sample_file), "fix", "HIGH", 30)

        mock_metrics = Mock()
        mock_metrics.security_issues = 0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_security_fix(imp)
        assert result is True

    @pytest.mark.asyncio
    async def test_hardcoded_secret_detected(self, monitor, temp_repo):
        secret_file = temp_repo / "secrets.py"
        secret_file.write_text("password = 'hunter2'\napi_key = 'abc123'\n")

        imp = QualityImprovement(
            "FIX_SECURITY", str(secret_file), "HARDCODED_SECRET found", "HIGH", 30
        )

        mock_metrics = Mock()
        mock_metrics.security_issues = 1
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_security_fix(imp)
        assert result is True

        # Check suggestion file was created
        suggestion_file = temp_repo / "secrets_security_fixes.json"
        assert suggestion_file.exists()
        data = json.loads(suggestion_file.read_text())
        assert any(s["type"] == "HARDCODED_SECRET" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_sql_injection_detected(self, monitor, temp_repo):
        sql_file = temp_repo / "db.py"
        sql_file.write_text(
            "cursor.execute('SELECT * FROM users WHERE id=' + user_id)\n"
        )

        imp = QualityImprovement(
            "FIX_SECURITY", str(sql_file), "SQL_INJECTION risk", "CRITICAL", 30
        )

        mock_metrics = Mock()
        mock_metrics.security_issues = 1
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_security_fix(imp)
        assert result is True

        suggestion_file = temp_repo / "db_security_fixes.json"
        assert suggestion_file.exists()
        data = json.loads(suggestion_file.read_text())
        assert any(s["type"] == "SQL_INJECTION" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_weak_crypto_detected(self, monitor, temp_repo):
        crypto_file = temp_repo / "hash.py"
        crypto_file.write_text("import hashlib\nh = hashlib.md5(data)\n")

        imp = QualityImprovement(
            "FIX_SECURITY", str(crypto_file), "WEAK_CRYPTO md5 usage", "HIGH", 30
        )

        mock_metrics = Mock()
        mock_metrics.security_issues = 1
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_security_fix(imp)
        assert result is True

        suggestion_file = temp_repo / "hash_security_fixes.json"
        data = json.loads(suggestion_file.read_text())
        assert any(s["type"] == "WEAK_CRYPTO" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_analyzer_exception(self, monitor, temp_repo):
        sample_file = temp_repo / "sample.py"
        imp = QualityImprovement("FIX_SECURITY", str(sample_file), "fix", "HIGH", 30)

        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(side_effect=RuntimeError("analyzer broke"))

        result = await monitor._suggest_security_fix(imp)
        assert result is False


# ---------------------------------------------------------------------------
# _suggest_test_addition tests
# ---------------------------------------------------------------------------


class TestSuggestTestAddition:
    @pytest.mark.asyncio
    async def test_success_creates_test_file(self, monitor, temp_repo):
        sample = temp_repo / "mymod.py"
        sample.write_text("def foo(): pass\ndef bar(): pass\nclass Baz: pass\n")
        imp = QualityImprovement("ADD_TESTS", str(sample), "add tests", "MEDIUM", 60)

        result = await monitor._suggest_test_addition(imp)
        assert result is True
        test_file = temp_repo / "tests" / "test_mymod.py"
        assert test_file.exists()
        content = test_file.read_text()
        assert "test_foo" in content
        assert "test_bar" in content

    @pytest.mark.asyncio
    async def test_file_not_found(self, monitor):
        imp = QualityImprovement("ADD_TESTS", "/no/such/file.py", "add", "MEDIUM", 60)
        result = await monitor._suggest_test_addition(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_syntax_error_in_file(self, monitor, temp_repo):
        bad = temp_repo / "bad.py"
        bad.write_text("def broken(\n")
        imp = QualityImprovement("ADD_TESTS", str(bad), "add", "MEDIUM", 60)
        result = await monitor._suggest_test_addition(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_existing_test_file_not_overwritten(self, monitor, temp_repo):
        sample = temp_repo / "existing.py"
        sample.write_text("def x(): pass\n")
        tests_dir = temp_repo / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "test_existing.py"
        test_file.write_text("# original content")

        imp = QualityImprovement("ADD_TESTS", str(sample), "add", "MEDIUM", 60)
        result = await monitor._suggest_test_addition(imp)
        assert result is True
        assert test_file.read_text() == "# original content"

    @pytest.mark.asyncio
    async def test_limits_to_five_functions(self, monitor, temp_repo):
        code = "\n".join(f"def func_{i}(): pass" for i in range(10))
        mod = temp_repo / "many_funcs.py"
        mod.write_text(code)
        imp = QualityImprovement("ADD_TESTS", str(mod), "add", "MEDIUM", 60)
        result = await monitor._suggest_test_addition(imp)
        assert result is True
        content = (temp_repo / "tests" / "test_many_funcs.py").read_text()
        # Only first 5 should have test methods
        test_methods = [
            line for line in content.split("\n") if "def test_func_" in line
        ]
        assert len(test_methods) == 5


# ---------------------------------------------------------------------------
# _suggest_refactoring tests
# ---------------------------------------------------------------------------


class TestSuggestRefactoring:
    @pytest.mark.asyncio
    async def test_file_not_found(self, monitor):
        imp = QualityImprovement("REFACTOR", "/no/file.py", "refactor", "MEDIUM", 120)
        result = await monitor._suggest_refactoring(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_no_issues_found(self, monitor, temp_repo):
        sample = temp_repo / "clean.py"
        sample.write_text("def small(): pass\n")
        imp = QualityImprovement("REFACTOR", str(sample), "refactor", "MEDIUM", 120)

        mock_metrics = Mock()
        mock_metrics.complexity_score = 5.0
        mock_metrics.maintainability_index = 80.0
        mock_metrics.duplicate_code = 1.0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_refactoring(imp)
        assert result is True
        # No suggestion file should be created
        assert not (temp_repo / "clean_refactoring_suggestions.json").exists()

    @pytest.mark.asyncio
    async def test_high_complexity(self, monitor, temp_repo):
        sample = temp_repo / "complex.py"
        sample.write_text("def f(): pass\n")
        imp = QualityImprovement("REFACTOR", str(sample), "refactor", "MEDIUM", 120)

        mock_metrics = Mock()
        mock_metrics.complexity_score = 25.0
        mock_metrics.maintainability_index = 80.0
        mock_metrics.duplicate_code = 1.0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_refactoring(imp)
        assert result is True
        suggestion_file = temp_repo / "complex_refactoring_suggestions.json"
        assert suggestion_file.exists()
        data = json.loads(suggestion_file.read_text())
        assert any(s["type"] == "HIGH_COMPLEXITY" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_low_maintainability(self, monitor, temp_repo):
        sample = temp_repo / "messy.py"
        sample.write_text("x = 1\n")
        imp = QualityImprovement("REFACTOR", str(sample), "refactor", "MEDIUM", 120)

        mock_metrics = Mock()
        mock_metrics.complexity_score = 5.0
        mock_metrics.maintainability_index = 30.0
        mock_metrics.duplicate_code = 1.0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_refactoring(imp)
        assert result is True
        data = json.loads(
            (temp_repo / "messy_refactoring_suggestions.json").read_text()
        )
        assert any(s["type"] == "LOW_MAINTAINABILITY" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_high_duplication(self, monitor, temp_repo):
        sample = temp_repo / "dup.py"
        sample.write_text("x = 1\n")
        imp = QualityImprovement("REFACTOR", str(sample), "refactor", "MEDIUM", 120)

        mock_metrics = Mock()
        mock_metrics.complexity_score = 5.0
        mock_metrics.maintainability_index = 80.0
        mock_metrics.duplicate_code = 20.0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_refactoring(imp)
        assert result is True
        data = json.loads((temp_repo / "dup_refactoring_suggestions.json").read_text())
        assert any(s["type"] == "CODE_DUPLICATION" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_long_function_detection(self, monitor, temp_repo):
        # Create a file with a function longer than 50 lines
        lines = ["def long_func():"]
        for i in range(60):
            lines.append(f"    x_{i} = {i}")
        sample = temp_repo / "longfunc.py"
        sample.write_text("\n".join(lines) + "\n")

        imp = QualityImprovement("REFACTOR", str(sample), "refactor", "MEDIUM", 120)

        mock_metrics = Mock()
        mock_metrics.complexity_score = 5.0
        mock_metrics.maintainability_index = 80.0
        mock_metrics.duplicate_code = 1.0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_refactoring(imp)
        assert result is True
        data = json.loads(
            (temp_repo / "longfunc_refactoring_suggestions.json").read_text()
        )
        assert any(s["type"] == "LONG_FUNCTION" for s in data["suggestions"])

    @pytest.mark.asyncio
    async def test_analyzer_exception(self, monitor, temp_repo):
        sample = temp_repo / "sample.py"
        imp = QualityImprovement("REFACTOR", str(sample), "refactor", "MEDIUM", 120)
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(side_effect=RuntimeError("crash"))

        result = await monitor._suggest_refactoring(imp)
        assert result is False

    @pytest.mark.asyncio
    async def test_syntax_error_in_ast_parse(self, monitor, temp_repo):
        """File with syntax error should still produce suggestions from metrics, just skip AST analysis."""
        bad_file = temp_repo / "badsyntax.py"
        bad_file.write_text("def broken(\n    invalid syntax here")

        imp = QualityImprovement("REFACTOR", str(bad_file), "refactor", "MEDIUM", 120)

        mock_metrics = Mock()
        mock_metrics.complexity_score = 25.0  # triggers HIGH_COMPLEXITY
        mock_metrics.maintainability_index = 80.0
        mock_metrics.duplicate_code = 1.0
        monitor.analyzer = Mock()
        monitor.analyzer.analyze_file = Mock(return_value=mock_metrics)

        result = await monitor._suggest_refactoring(imp)
        assert result is True
        data = json.loads(
            (temp_repo / "badsyntax_refactoring_suggestions.json").read_text()
        )
        assert any(s["type"] == "HIGH_COMPLEXITY" for s in data["suggestions"])
