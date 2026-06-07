import asyncio
import json

from src.quality.code_quality_analyzer import CodeQualityAnalyzer, QualityMetrics
from src.quality.mapek_quality_integration import (
    MAPEKQualityMonitor,
    QualityImprovement,
)


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


def test_code_quality_analyzer_thinking_status_redacts_paths_and_code(tmp_path):
    secret_file = tmp_path / "secret_module_name.py"
    secret_file.write_text(
        'password = "secret-password-value"\n'
        "def secret_function_name():\n"
        "    return password\n",
        encoding="utf-8",
    )

    analyzer = CodeQualityAnalyzer(str(tmp_path))
    metrics = analyzer.analyze_file(str(secret_file))

    assert metrics.security_issues >= 1
    status = analyzer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "quality"
    _assert_redacted(
        status,
        str(tmp_path),
        str(secret_file),
        "secret_module_name.py",
        "secret-password-value",
        "secret_function_name",
    )


def test_mapek_quality_monitor_thinking_status_redacts_improvement_details(tmp_path):
    secret_file = tmp_path / "secret_quality_target.py"
    secret_file.write_text(
        'api_key = "secret-api-key-value"\n'
        "def secret_quality_function():\n"
        "    return api_key\n",
        encoding="utf-8",
    )

    monitor = MAPEKQualityMonitor(str(tmp_path))
    improvement = QualityImprovement(
        action_type="FIX_SECURITY",
        file_path=str(secret_file),
        description="Fix secret-api-key-value in secret_quality_function",
        priority="CRITICAL",
        estimated_effort=30,
        automated=False,
    )

    assert asyncio.run(monitor.execute_improvement(improvement)) is True
    status = monitor.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "quality"
    _assert_redacted(
        status,
        str(tmp_path),
        str(secret_file),
        "secret_quality_target.py",
        "secret-api-key-value",
        "secret_quality_function",
        "Fix secret-api-key-value in secret_quality_function",
    )

def test_mapek_quality_improvement_generation_redacts_security_issue_payload(tmp_path):
    monitor = MAPEKQualityMonitor(str(tmp_path))
    total_metrics = QualityMetrics(
        file_path="TOTAL",
        language="ALL",
        lines_of_code=10,
        complexity_score=20.0,
        maintainability_index=50.0,
        test_coverage=10.0,
        security_issues=1,
        style_violations=25,
        duplicate_code=0.0,
        technical_debt=900,
    )
    monitor._generate_improvements(
        {
            "total_metrics": total_metrics,
            "security_issues": [
                {
                    "file_path": str(tmp_path / "secret_payload.py"),
                    "category": "HARDCODED_SECRET",
                    "description": "secret finding description",
                    "severity": "HIGH",
                    "code_snippet": 'password = "secret-value"',
                }
            ],
        }
    )

    status = monitor.get_thinking_status()
    _assert_redacted(
        status,
        str(tmp_path),
        "secret_payload.py",
        "secret finding description",
        'password = "secret-value"',
    )
