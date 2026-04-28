from __future__ import annotations

import json
import subprocess


SCRIPT = "scripts/show_provider_hardware_tier.py"


def test_text_status_reports_limited_realtek_with_failed_benchmark(tmp_path):
    benchmark = {
        "timestamp": "20260402T083155Z",
        "iface": "enp8s0",
        "target_pps": 5000000,
        "measured_pps": 138621,
        "pass": False,
    }
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            SCRIPT,
            "--iface",
            "enp8s0",
            "--driver",
            "r8169",
            "--speed",
            "1000Mb/s",
            "--operstate",
            "up",
            "--benchmark-json",
            str(benchmark_path),
        ],
        cwd="/mnt/projects",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert "provider-hardware-tier status" in result.stdout
    assert "tier=limited" in result.stdout
    assert "verdict=hardware_limited" in result.stdout
    assert "benchmark_status=below_target" in result.stdout
    assert "measured_pps=138621" in result.stdout


def test_json_status_reports_gold_candidate_without_benchmark(tmp_path):
    empty_results = tmp_path / "results"
    empty_results.mkdir()

    result = subprocess.run(
        [
            "python3",
            SCRIPT,
            "--iface",
            "eth1",
            "--driver",
            "ice",
            "--speed",
            "25000Mb/s",
            "--operstate",
            "up",
            "--results-dir",
            str(empty_results),
            "--format",
            "json",
        ],
        cwd="/mnt/projects",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["hardware_tier"] == "gold"
    assert payload["af_xdp_zero_copy_ready"] is True
    assert payload["empirical_status"] == "not_benchmarked"
    assert payload["verdict"] == "candidate_for_zero_copy_benchmark"


def test_json_status_flags_iface_mismatch_when_latest_benchmark_is_for_another_nic(tmp_path):
    benchmark = {
        "timestamp": "20260402T083155Z",
        "iface": "enp8s0",
        "target_pps": 5000000,
        "measured_pps": 138621,
        "pass": False,
    }
    benchmark_path = tmp_path / "benchmark.json"
    benchmark_path.write_text(json.dumps(benchmark), encoding="utf-8")

    result = subprocess.run(
        [
            "python3",
            SCRIPT,
            "--iface",
            "eth9",
            "--driver",
            "ixgbe",
            "--speed",
            "10000Mb/s",
            "--operstate",
            "up",
            "--benchmark-json",
            str(benchmark_path),
            "--format",
            "json",
        ],
        cwd="/mnt/projects",
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    payload = json.loads(result.stdout)
    assert payload["hardware_tier"] == "silver"
    assert payload["empirical_status"] == "iface_mismatch"
    assert payload["verdict"] == "benchmark_iface_mismatch"
