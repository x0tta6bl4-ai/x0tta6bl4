import json
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def _load_module():
    path = ROOT / "scripts/ops/verify_ghost_pulse_rng_replay.py"
    spec = importlib.util.spec_from_file_location("verify_ghost_pulse_rng_replay", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _local_evidence(replay_gate, mode="corporate", seed=20260521, count=5):
    replay = replay_gate.replay_timing_plan(mode=mode, seed=seed, sample_count=count)
    return {
        "local_probe": {
            "mode": mode,
            "seed": seed,
            "transport_stats": {
                "timing_plan_replay": {
                    "status": "LOCAL_SEED_REPLAYABLE",
                    "seed": seed,
                    "sample_count": count,
                    "sha256": replay["sha256"],
                },
                "timing_plan_samples": replay["projection"],
            },
        }
    }


def _matrix_evidence(replay_gate):
    rows = []
    for mode, seed in (("corporate", 20260522), ("whitelist", 20262522)):
        replay = replay_gate.replay_timing_plan(mode=mode, seed=seed, sample_count=4)
        rows.append(
            {
                "mode": mode,
                "seed": seed,
                "pulse_rng_seed": seed,
                "timing_plan_replay_seed": seed,
                "timing_plan_replay_status": "LOCAL_SEED_REPLAYABLE",
                "timing_plan_replay_samples": 4,
                "timing_plan_replay_sha256": replay["sha256"],
            }
        )
    return {"runs": rows}


def test_verify_local_accepts_matching_seed_replay(tmp_path):
    replay_gate = _load_module()
    evidence_path = tmp_path / "local.json"
    evidence_path.write_text(
        json.dumps(_local_evidence(replay_gate)),
        encoding="utf-8",
    )

    assert replay_gate.verify_local(evidence_path) == []


def test_verify_local_rejects_tampered_replay_digest(tmp_path):
    replay_gate = _load_module()
    evidence = _local_evidence(replay_gate)
    evidence["local_probe"]["transport_stats"]["timing_plan_replay"]["sha256"] = "0" * 64
    evidence_path = tmp_path / "local.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    failures = replay_gate.verify_local(evidence_path)

    assert any("local replay sha256 does not match seed replay" in item for item in failures)


def test_verify_matrix_accepts_matching_seed_replay_rows(tmp_path):
    replay_gate = _load_module()
    evidence_path = tmp_path / "matrix.json"
    evidence_path.write_text(
        json.dumps(_matrix_evidence(replay_gate)),
        encoding="utf-8",
    )

    assert replay_gate.verify_matrix(evidence_path) == []


def test_verify_matrix_rejects_row_with_wrong_seed_digest(tmp_path):
    replay_gate = _load_module()
    evidence = _matrix_evidence(replay_gate)
    evidence["runs"][1]["timing_plan_replay_sha256"] = (
        evidence["runs"][0]["timing_plan_replay_sha256"]
    )
    evidence_path = tmp_path / "matrix.json"
    evidence_path.write_text(json.dumps(evidence), encoding="utf-8")

    failures = replay_gate.verify_matrix(evidence_path)

    assert any("run 1: replay sha256 does not match seed replay" in item for item in failures)


def test_main_accepts_external_fixture_paths(tmp_path, monkeypatch, capsys):
    replay_gate = _load_module()
    local_path = tmp_path / "local.json"
    matrix_path = tmp_path / "matrix.json"
    local_path.write_text(json.dumps(_local_evidence(replay_gate)), encoding="utf-8")
    matrix_path.write_text(json.dumps(_matrix_evidence(replay_gate)), encoding="utf-8")
    monkeypatch.setattr(
        replay_gate.sys,
        "argv",
        [
            "verify_ghost_pulse_rng_replay.py",
            "--local-evidence",
            str(local_path),
            "--profile-matrix",
            str(matrix_path),
        ],
    )

    assert replay_gate.main() == 0
    output = capsys.readouterr().out
    assert "PASS: x0tta6bl4_pulse seed replay digests match evidence artifacts" in output
    assert str(local_path) in output
    assert str(matrix_path) in output
