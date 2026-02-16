#!/usr/bin/env python3
"""
Tests for MAPE-K Quality Integration module.

Tests the autonomous code quality monitoring and improvement functionality.
"""

import asyncio
import shutil
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.quality.mapek_quality_integration import (MAPEKQualityMonitor,
                                                   QualityImprovement,
                                                   QualityThresholds)


class TestMAPEKQualityMonitor:
    """Test cases for MAPEKQualityMonitor class."""

    @pytest.fixture
    def temp_repo(self):
        """Create a temporary repository for testing."""
        temp_dir = tempfile.mkdtemp()
        repo_path = Path(temp_dir)

        # Create a simple Python file for testing
        test_file = repo_path / "test_module.py"
        test_file.write_text(
            """
def test_function():
    '''A test function'''
    return "test"

class TestClass:
    def method(self):
        return "method"
"""
        )

        yield repo_path

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.fixture
    def quality_monitor(self, temp_repo):
        """Create a MAPEKQualityMonitor instance."""
        with patch("src.quality.mapek_quality_integration.CodeQualityAnalyzer"):
            with patch("src.quality.mapek_quality_integration.ThreadSafeMAPEKLoop"):
                with patch("src.quality.mapek_quality_integration.ThreadSafeMetrics"):
                    monitor = MAPEKQualityMonitor(str(temp_repo))
                    return monitor

    @pytest.fixture
    def quality_improvement(self, temp_repo):
        """Create a QualityImprovement instance for testing."""
        return QualityImprovement(
            action_type="ADD_TESTS",
            file_path=str(temp_repo / "test_module.py"),
            description="Add tests for test_module.py",
            priority="MEDIUM",
            estimated_effort=30,
            automated=True,
        )

    @pytest.mark.asyncio
    async def test_suggest_test_addition_success(
        self, quality_monitor, quality_improvement, temp_repo
    ):
        """Test that _suggest_test_addition successfully generates test file."""
        result = await quality_monitor._suggest_test_addition(quality_improvement)

        assert result is True

        # Check that test file was created
        test_file = temp_repo / "tests" / "test_test_module.py"
        assert test_file.exists(), "Test file should be created"

        # Check test file content
        content = test_file.read_text()
        assert "test_test_function" in content, "Test method should be generated"
        # Class name is TestTest_module (uses underscore from filename, not PascalCase)
        assert "TestTest_module" in content, "Test class should be generated"
        assert (
            "from test_module import" in content
        ), "Import statement should be present"

    @pytest.mark.asyncio
    async def test_suggest_test_addition_file_not_found(self, quality_monitor):
        """Test that _suggest_test_addition returns False for non-existent file."""
        improvement = QualityImprovement(
            action_type="ADD_TESTS",
            file_path="/nonexistent/file.py",
            description="Add tests",
            priority="MEDIUM",
            estimated_effort=30,
            automated=True,
        )

        result = await quality_monitor._suggest_test_addition(improvement)

        assert result is False

    @pytest.mark.asyncio
    async def test_suggest_test_addition_syntax_error(self, quality_monitor, temp_repo):
        """Test that _suggest_test_addition handles syntax errors gracefully."""
        # Create a file with syntax error
        bad_file = temp_repo / "bad_syntax.py"
        bad_file.write_text("def broken_function(\n    return 'missing colon'")

        improvement = QualityImprovement(
            action_type="ADD_TESTS",
            file_path=str(bad_file),
            description="Add tests",
            priority="MEDIUM",
            estimated_effort=30,
            automated=True,
        )

        result = await quality_monitor._suggest_test_addition(improvement)

        assert result is False

    @pytest.mark.asyncio
    async def test_suggest_test_addition_existing_test_file(
        self, quality_monitor, quality_improvement, temp_repo
    ):
        """Test that _suggest_test_addition returns True if test file already exists."""
        # Create existing test file
        test_dir = temp_repo / "tests"
        test_dir.mkdir(exist_ok=True)
        test_file = test_dir / "test_test_module.py"
        test_file.write_text("# Existing test file")

        result = await quality_monitor._suggest_test_addition(quality_improvement)

        assert result is True
        # Verify original content is preserved
        assert test_file.read_text() == "# Existing test file"

    @pytest.mark.asyncio
    async def test_suggest_test_addition_no_functions(self, quality_monitor, temp_repo):
        """Test that _suggest_test_addition handles files with no functions."""
        # Create a file with no functions
        empty_file = temp_repo / "empty_module.py"
        empty_file.write_text("# Just a comment")

        improvement = QualityImprovement(
            action_type="ADD_TESTS",
            file_path=str(empty_file),
            description="Add tests",
            priority="MEDIUM",
            estimated_effort=30,
            automated=True,
        )

        result = await quality_monitor._suggest_test_addition(improvement)

        # Should still create test file, but with no test methods
        assert result is True
        test_file = temp_repo / "tests" / "test_empty_module.py"
        assert test_file.exists()

    def test_quality_thresholds_defaults(self):
        """Test that QualityThresholds has correct default values."""
        thresholds = QualityThresholds()

        assert thresholds.min_overall_score == 70.0
        assert thresholds.max_complexity == 15.0
        assert thresholds.min_test_coverage == 50.0
        assert thresholds.max_security_issues == 5
        assert thresholds.max_technical_debt_hours == 8.0
        assert thresholds.min_maintainability == 60.0

    def test_quality_improvement_creation(self):
        """Test that QualityImprovement can be created with all fields."""
        improvement = QualityImprovement(
            action_type="REFACTOR",
            file_path="/path/to/file.py",
            description="Refactor complex function",
            priority="HIGH",
            estimated_effort=60,
            automated=True,
        )

        assert improvement.action_type == "REFACTOR"
        assert improvement.file_path == "/path/to/file.py"
        assert improvement.description == "Refactor complex function"
        assert improvement.priority == "HIGH"
        assert improvement.estimated_effort == 60
        assert improvement.automated is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
