from __future__ import annotations

import types
from datetime import datetime, timedelta
from pathlib import Path

import pytest

import src as src_pkg
from src.quality.code_quality_analyzer import CodeQualityAnalyzer, QualityMetrics


def _sample_metrics(**overrides):
    base = dict(
        file_path="a.py",
        language="PYTHON",
        lines_of_code=20,
        complexity_score=8.0,
        maintainability_index=82.0,
        test_coverage=65.0,
        security_issues=0,
        style_violations=2,
        duplicate_code=1.0,
        technical_debt=10,
    )
    base.update(overrides)
    return QualityMetrics(**base)


def test_quality_metrics_overall_score_penalizes_risky_factors():
    good = _sample_metrics()
    bad = _sample_metrics(
        complexity_score=35.0,
        security_issues=4,
        style_violations=30,
        duplicate_code=20.0,
        test_coverage=10.0,
        maintainability_index=20.0,
    )
    assert good.overall_score() > bad.overall_score()


def test_detect_language_and_unknown(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))
    assert analyzer._detect_language(Path("x.py")) == "PYTHON"
    assert analyzer._detect_language(Path("x.tsx")) == "TYPESCRIPT"
    assert analyzer._detect_language(Path("x.rs")) == "RUST"
    assert analyzer._detect_language(Path("x.xyz")) == "UNKNOWN"


def test_count_loc_and_complexity_paths(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))
    content = """
# comment
def f(x):
    if x and x > 0:
        return x
    return 0
"""
    assert analyzer._count_lines_of_code(content) >= 4
    assert analyzer._python_complexity(content) >= 2.0
    assert analyzer._generic_complexity(content) >= 2.0
    assert analyzer._calculate_complexity("if (x) { return y; }", "GO") >= 1.0
    assert analyzer._python_complexity("def broken(:\n") >= 1.0


def test_multiline_comment_with_and_exception_paths(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))

    multiline = """
'''
inside comment
'''
value = 1
"""
    assert analyzer._count_lines_of_code(multiline) == 1

    complex_python = """
def f():
    try:
        value = 1
    except Exception:
        value = 2
    with open("x.txt", "w") as h:
        h.write(str(value))
"""
    assert analyzer._python_complexity(complex_python) >= 3.0


def test_maintainability_coverage_style_and_duplicates(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))

    code_file = tmp_path / "module.py"
    code_file.write_text("def run():\n    assert True\n", encoding="utf-8")
    (tmp_path / "test_module.py").write_text("def test_run():\n    assert True\n")

    coverage = analyzer._estimate_test_coverage(
        code_file, code_file.read_text(encoding="utf-8")
    )
    assert coverage >= 60.0

    style_content = "class bad:\n\tpass\n" + ("x = 1 " * 80)
    violations = analyzer._check_style_compliance(style_content, "PYTHON")
    assert violations >= 2

    duplicate_content = "\n".join(
        [
            "value = important_variable + another_variable",
            "value = important_variable + another_variable",
            "result = important_variable + another_variable",
            "result = important_variable + another_variable",
            "x = 1",
            "y = 2",
            "z = 3",
            "a = 4",
            "b = 5",
            "c = 6",
        ]
    )
    assert analyzer._detect_duplicates(duplicate_content) > 0
    assert analyzer._line_similarity("a b c", "a b") > 0
    assert analyzer._line_similarity("", "a b") == 0.0


def test_maintainability_and_duplicates_edge_cases(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))

    assert analyzer._calculate_maintainability("", "PYTHON") == 100.0

    short_content = "\n".join(["x"] * 9)
    assert analyzer._detect_duplicates(short_content) == 0.0

    unique_long_lines = "\n".join(
        [
            "alpha beta gamma delta",
            "one two three four five",
            "red green blue yellow",
            "cat dog bird fish",
            "spring summer autumn winter",
            "left right up down",
            "north south east west",
            "apple orange banana grape",
            "python rust go java",
            "cloud edge mesh node",
        ]
    )
    assert analyzer._detect_duplicates(unique_long_lines) == 0.0

    short_dense_lines = "\n".join(["tiny"] * 10)
    assert analyzer._detect_duplicates(short_dense_lines) == 0.0


def test_security_detection_and_severity_mapping(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))
    content = """
password = "hardcoded"
cursor.execute("SELECT * FROM users WHERE id = %s")
document.write("<script>alert(1)</script>")
hash_value = md5(data)
"""
    issues = analyzer._detect_security_issues(content, "sample.py")
    categories = {issue["category"] for issue in issues}
    assert "HARDCODED_SECRET" in categories
    assert "SQL_INJECTION" in categories
    assert "XSS" in categories
    assert "WEAK_CRYPTO" in categories
    assert analyzer._determine_severity("SQL_INJECTION") == "CRITICAL"
    assert analyzer._determine_severity("UNKNOWN") == "LOW"


def test_technical_debt_and_recommendations(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))
    debt = analyzer._calculate_technical_debt(
        complexity=25.0, security_issues=3, style_violations=15
    )
    assert debt > 0

    metrics = _sample_metrics(
        complexity_score=25.0,
        maintainability_index=40.0,
        test_coverage=10.0,
        security_issues=2,
        style_violations=60,
        duplicate_code=30.0,
    )
    recommendations = analyzer._generate_recommendations(metrics)
    assert recommendations
    assert any("security issues" in item for item in recommendations)


def test_trend_history_limits_and_recent_trends(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))

    for idx in range(120):
        analyzer._update_trend_history(
            _sample_metrics(
                complexity_score=10 + idx,
                test_coverage=70.0,
                timestamp=datetime.now() - timedelta(minutes=idx),
            )
        )

    assert len(analyzer.quality_history) == analyzer.max_history_size
    assert len(analyzer._get_recent_trends(limit=5)) == 5
    assert len(analyzer._get_recent_trends(limit=0)) == analyzer.max_history_size


def test_analyze_file_handles_utf8_latin1_and_missing(tmp_path):
    analyzer = CodeQualityAnalyzer(str(tmp_path))

    utf8_file = tmp_path / "utf8_module.py"
    utf8_file.write_text("def ok():\n    return 1\n", encoding="utf-8")
    utf8_metrics = analyzer.analyze_file(str(utf8_file))
    assert utf8_metrics.language == "PYTHON"
    assert utf8_metrics.lines_of_code > 0

    latin1_file = tmp_path / "latin1_module.py"
    latin1_file.write_bytes("name = 'olá'\n".encode("latin-1"))
    latin1_metrics = analyzer.analyze_file(str(latin1_file))
    assert latin1_metrics.lines_of_code > 0

    with pytest.raises(FileNotFoundError):
        analyzer.analyze_file(str(tmp_path / "absent.py"))


def test_analyze_repository_aggregates_and_handles_failures(tmp_path, monkeypatch):
    (tmp_path / "app.py").write_text(
        "password = '123'\nif True:\n    print('ok')\n", encoding="utf-8"
    )
    (tmp_path / "frontend.js").write_text(
        "document.write('<div>x</div>')\n", encoding="utf-8"
    )
    (tmp_path / "ignored_test.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "skip.py").write_text("print('skip')\n", encoding="utf-8")

    analyzer = CodeQualityAnalyzer(str(tmp_path))

    original_analyze_file = analyzer.analyze_file

    def _analyze_with_one_failure(path):
        if path.endswith("frontend.js"):
            raise RuntimeError("synthetic failure")
        return original_analyze_file(path)

    monkeypatch.setattr(analyzer, "analyze_file", _analyze_with_one_failure)
    results = analyzer.analyze_repository()

    assert results["files_analyzed"] == 1
    assert results["total_metrics"] is not None
    assert "PYTHON" in results["language_breakdown"]
    assert isinstance(results["recommendations"], list)
    assert analyzer.quality_history


def test_src_package_getattr_ml_and_missing(monkeypatch):
    fake_ml = types.ModuleType("src.ml")
    monkeypatch.setitem(src_pkg.__dict__, "ml", fake_ml)

    assert src_pkg.__getattr__("ml") is fake_ml

    with pytest.raises(AttributeError):
        src_pkg.__getattr__("missing_attr")
