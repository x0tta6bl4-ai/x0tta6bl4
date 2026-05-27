from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "validate_baseline.py"
    spec = importlib.util.spec_from_file_location("validate_baseline", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load validate_baseline module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _metrics(
    *,
    success_rate_percent: float = 99.0,
    latency_p95_ms: float = 80.0,
    max_memory_mb: float = 256.0,
) -> dict:
    return {
        "success_rate_percent": success_rate_percent,
        "latency_p95_ms": latency_p95_ms,
        "max_memory_mb": max_memory_mb,
    }


def test_main_compares_current_metrics_against_baseline(tmp_path, capsys):
    module = _load_module()
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(baseline, {"summary": _metrics(success_rate_percent=98.5)})
    _write_json(current, {"summary": _metrics(success_rate_percent=99.0)})

    assert module.main(["--baseline", str(baseline), "--current", str(current)]) == 0

    output = capsys.readouterr().out
    assert "BASELINE VALIDATION: PASSED" in output


def test_main_fails_when_current_metrics_regress(tmp_path, capsys):
    module = _load_module()
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(baseline, {"summary": _metrics(latency_p95_ms=100.0)})
    _write_json(current, {"summary": _metrics(latency_p95_ms=130.0)})

    assert module.main(["--baseline", str(baseline), "--current", str(current)]) == 1

    output = capsys.readouterr().out
    assert "Latency P95" in output
    assert "BASELINE VALIDATION: FAILED" in output


def test_main_requires_current_metrics_file(tmp_path, capsys):
    module = _load_module()
    baseline = tmp_path / "baseline.json"
    _write_json(baseline, {"summary": _metrics()})

    assert module.main(["--baseline", str(baseline)]) == 2

    output = capsys.readouterr().out
    assert "Current metrics file is required" in output


def test_main_rejects_incomplete_current_metrics(tmp_path, capsys):
    module = _load_module()
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(baseline, {"summary": _metrics()})
    _write_json(
        current,
        {
            "summary": {
                "success_rate_percent": 99.0,
                "latency_p95_ms": 80.0,
            }
        },
    )

    assert module.main(["--baseline", str(baseline), "--current", str(current)]) == 2

    output = capsys.readouterr().out
    assert "max_memory_mb" in output


def test_current_metrics_env_can_supply_current_path(tmp_path, monkeypatch):
    module = _load_module()
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    _write_json(baseline, {"summary": _metrics()})
    _write_json(current, _metrics())
    monkeypatch.setenv(module.CURRENT_METRICS_ENV, str(current))

    assert module.main(["--baseline", str(baseline)]) == 0
