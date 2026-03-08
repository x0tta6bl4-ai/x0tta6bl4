"""
Unit tests for scripts/ops/mttr_chaos_report.py

All tests run in CI mode (no cluster, no real chaos injection).
"""

import importlib.util
import json
import sys
import tempfile
import os
from unittest import mock

import pytest


# ---------------------------------------------------------------------------
# Module loader
# ---------------------------------------------------------------------------

def _load_report_module(extra_env: dict | None = None):
    env = {"MTTR_HW_MODE": "0", "MTTR_SEED": "42"}
    if extra_env:
        env.update(extra_env)
    mod_name = "_mttr_chaos_report_test"
    if mod_name in sys.modules:
        del sys.modules[mod_name]
    spec = importlib.util.spec_from_file_location(
        mod_name,
        "/mnt/projects/scripts/ops/mttr_chaos_report.py",
    )
    mod = importlib.util.module_from_spec(spec)
    with mock.patch.dict("os.environ", env):
        spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rmod():
    return _load_report_module()


# ---------------------------------------------------------------------------
# ScenarioResult
# ---------------------------------------------------------------------------

class TestScenarioResult:
    def test_ttd_slo_pass_within(self, rmod):
        r = rmod.ScenarioResult("x", "d", "f", ttd_s=10.0, ttr_s=60.0, healed=True)
        assert r.ttd_slo_pass is True

    def test_ttd_slo_fail_over(self, rmod):
        r = rmod.ScenarioResult("x", "d", "f", ttd_s=35.0, ttr_s=60.0, healed=True)
        assert r.ttd_slo_pass is False

    def test_ttr_slo_pass_within(self, rmod):
        r = rmod.ScenarioResult("x", "d", "f", ttd_s=5.0, ttr_s=200.0, healed=True)
        assert r.ttr_slo_pass is True

    def test_ttr_slo_fail_over(self, rmod):
        r = rmod.ScenarioResult("x", "d", "f", ttd_s=5.0, ttr_s=400.0, healed=True)
        assert r.ttr_slo_pass is False

    def test_not_healed_does_not_affect_slo_fields(self, rmod):
        r = rmod.ScenarioResult("x", "d", "f", ttd_s=5.0, ttr_s=600.0, healed=False)
        # fields exist but ttr_slo_pass is False (600 > 300)
        assert r.ttr_slo_pass is False


# ---------------------------------------------------------------------------
# ChaosReport.compute_summary
# ---------------------------------------------------------------------------

class TestComputeSummary:
    def _make_report(self, rmod, results):
        report = rmod.ChaosReport()
        report.scenarios = results
        report.compute_summary()
        return report

    def test_empty_scenarios(self, rmod):
        report = self._make_report(rmod, [])
        assert report.summary == {}

    def test_all_healed(self, rmod):
        results = [
            rmod.ScenarioResult("a", "", "f", ttd_s=5.0, ttr_s=50.0, healed=True),
            rmod.ScenarioResult("b", "", "f", ttd_s=10.0, ttr_s=100.0, healed=True),
        ]
        report = self._make_report(rmod, results)
        s = report.summary
        assert s["healed"] == 2
        assert s["failed_to_heal"] == 0
        assert s["heal_rate_pct"] == 100.0
        assert s["mttr_s"] == pytest.approx(75.0, abs=0.01)
        assert s["mttd_s"] == pytest.approx(7.5, abs=0.01)

    def test_one_not_healed(self, rmod):
        results = [
            rmod.ScenarioResult("a", "", "f", ttd_s=5.0, ttr_s=50.0, healed=True),
            rmod.ScenarioResult("b", "", "f", ttd_s=5.0, ttr_s=600.0, healed=False),
        ]
        report = self._make_report(rmod, results)
        s = report.summary
        assert s["healed"] == 1
        assert s["failed_to_heal"] == 1
        assert s["heal_rate_pct"] == 50.0
        # MTTR only counts healed scenarios
        assert s["mttr_s"] == pytest.approx(50.0, abs=0.01)

    def test_mttr_slo_pass(self, rmod):
        results = [rmod.ScenarioResult("a", "", "f", 5.0, 200.0, True)]
        report = self._make_report(rmod, results)
        assert report.summary["mttr_slo_pass"] is True

    def test_mttr_slo_fail(self, rmod):
        results = [rmod.ScenarioResult("a", "", "f", 5.0, 400.0, True)]
        report = self._make_report(rmod, results)
        assert report.summary["mttr_slo_pass"] is False

    def test_worst_ttr(self, rmod):
        results = [
            rmod.ScenarioResult("a", "", "f", 5.0, 50.0, True),
            rmod.ScenarioResult("b", "", "f", 5.0, 200.0, True),
        ]
        report = self._make_report(rmod, results)
        assert report.summary["worst_ttr_s"] == pytest.approx(200.0, abs=0.01)

    def test_worst_ttd(self, rmod):
        results = [
            rmod.ScenarioResult("a", "", "f", 5.0, 50.0, True),
            rmod.ScenarioResult("b", "", "f", 25.0, 50.0, True),
        ]
        report = self._make_report(rmod, results)
        assert report.summary["worst_ttd_s"] == pytest.approx(25.0, abs=0.01)


# ---------------------------------------------------------------------------
# Synthetic runner
# ---------------------------------------------------------------------------

class TestSyntheticRunner:
    def test_returns_scenario_result(self, rmod):
        defn = rmod._CI_SCENARIOS[0]
        result = rmod._run_synthetic(defn)
        assert isinstance(result, rmod.ScenarioResult)

    def test_name_matches(self, rmod):
        for defn in rmod._CI_SCENARIOS[:3]:
            result = rmod._run_synthetic(defn)
            assert result.name == defn[0]

    def test_ttd_within_realistic_range(self, rmod):
        for defn in rmod._CI_SCENARIOS:
            result = rmod._run_synthetic(defn)
            _, _, _, ttd_range, _ = defn
            assert result.ttd_s >= ttd_range[0] * 0.5
            assert result.ttd_s <= ttd_range[1] * 1.5

    def test_ttr_within_realistic_range_when_healed(self, rmod):
        for defn in rmod._CI_SCENARIOS:
            result = rmod._run_synthetic(defn)
            if result.healed:
                _, _, _, _, ttr_range = defn
                assert result.ttr_s >= ttr_range[0] * 0.5

    def test_all_scenarios_run(self, rmod):
        results = [rmod._run_synthetic(d) for d in rmod._CI_SCENARIOS]
        assert len(results) == len(rmod._CI_SCENARIOS)

    def test_seed_deterministic(self):
        # Load m1, compute r1 first — then load m2 so its random.seed(7)
        # call resets the global RNG back to the same starting state for r2.
        m1 = _load_report_module({"MTTR_SEED": "7"})
        r1 = [m1._run_synthetic(d) for d in m1._CI_SCENARIOS]
        m2 = _load_report_module({"MTTR_SEED": "7"})
        r2 = [m2._run_synthetic(d) for d in m2._CI_SCENARIOS]
        assert [x.ttd_s for x in r1] == [x.ttd_s for x in r2]


# ---------------------------------------------------------------------------
# Markdown rendering
# ---------------------------------------------------------------------------

class TestMarkdownRendering:
    def _make_full_report(self, rmod):
        report = rmod.ChaosReport()
        report.scenarios = [
            rmod.ScenarioResult("s1", "desc1", "pod-kill", 5.0, 60.0, True),
            rmod.ScenarioResult("s2", "desc2", "net-loss", 10.0, 120.0, False),
        ]
        report.compute_summary()
        return report

    def test_contains_header(self, rmod):
        md = rmod.render_markdown(self._make_full_report(rmod))
        assert "MTTR Chaos Report" in md

    def test_contains_slo_table(self, rmod):
        md = rmod.render_markdown(self._make_full_report(rmod))
        assert "SLO Targets" in md

    def test_contains_all_scenario_names(self, rmod):
        report = self._make_full_report(rmod)
        md = rmod.render_markdown(report)
        for sc in report.scenarios:
            assert sc.name in md

    def test_overall_gate_line(self, rmod):
        report = self._make_full_report(rmod)
        md = rmod.render_markdown(report)
        assert "Overall Gate" in md

    def test_pass_or_fail_present(self, rmod):
        report = self._make_full_report(rmod)
        md = rmod.render_markdown(report)
        assert "PASS" in md or "FAIL" in md

    def test_mode_synthetic_in_output(self, rmod):
        report = self._make_full_report(rmod)
        md = rmod.render_markdown(report)
        assert "SYNTHETIC" in md.upper() or "CI" in md.upper()


# ---------------------------------------------------------------------------
# main() integration (file I/O, no real chaos)
# ---------------------------------------------------------------------------

class TestMainIntegration:
    def test_main_exits_0_on_slo_pass(self, rmod):
        """Run main with all scenarios passing — should exit 0."""
        with tempfile.TemporaryDirectory() as tmp:
            json_out = os.path.join(tmp, "mttr.json")
            md_out = os.path.join(tmp, "mttr.md")
            # Patch _run_synthetic to always return healthy, fast result
            fast = rmod.ScenarioResult("x", "d", "f", ttd_s=5.0, ttr_s=60.0, healed=True)
            with mock.patch.object(rmod, "_run_synthetic", return_value=fast):
                rc = rmod.main(["--output", json_out, "--markdown", md_out])
            assert rc == 0
            assert os.path.exists(json_out)
            assert os.path.exists(md_out)

    def test_main_exits_2_on_slo_breach(self, rmod):
        """If MTTR exceeds SLO, main should return 2."""
        with tempfile.TemporaryDirectory() as tmp:
            json_out = os.path.join(tmp, "mttr.json")
            md_out = os.path.join(tmp, "mttr.md")
            # Patch to return very slow recovery (SLO breach)
            slow = rmod.ScenarioResult("x", "d", "f", ttd_s=5.0, ttr_s=999.0, healed=True)
            with mock.patch.object(rmod, "_run_synthetic", return_value=slow):
                rc = rmod.main(["--output", json_out, "--markdown", md_out])
            assert rc == 2

    def test_json_output_schema(self, rmod):
        with tempfile.TemporaryDirectory() as tmp:
            json_out = os.path.join(tmp, "mttr.json")
            md_out = os.path.join(tmp, "mttr.md")
            fast = rmod.ScenarioResult("x", "d", "f", 5.0, 60.0, True)
            with mock.patch.object(rmod, "_run_synthetic", return_value=fast):
                rmod.main(["--output", json_out, "--markdown", md_out])
            data = json.loads(open(json_out).read())
            assert "schema_version" in data
            assert "timestamp" in data
            assert "mode" in data
            assert "scenarios" in data
            assert "summary" in data

    def test_scenarios_filter(self, rmod):
        with tempfile.TemporaryDirectory() as tmp:
            json_out = os.path.join(tmp, "mttr.json")
            md_out = os.path.join(tmp, "mttr.md")
            fast = rmod.ScenarioResult("api-pod-oom", "d", "f", 5.0, 60.0, True)
            with mock.patch.object(rmod, "_run_synthetic", return_value=fast):
                rc = rmod.main([
                    "--output", json_out, "--markdown", md_out,
                    "--scenarios", "api-pod-oom",
                ])
            assert rc == 0
            data = json.loads(open(json_out).read())
            assert len(data["scenarios"]) == 1
            assert data["scenarios"][0]["name"] == "api-pod-oom"

    def test_unknown_scenario_filter_returns_1(self, rmod):
        with tempfile.TemporaryDirectory() as tmp:
            json_out = os.path.join(tmp, "mttr.json")
            md_out = os.path.join(tmp, "mttr.md")
            rc = rmod.main([
                "--output", json_out, "--markdown", md_out,
                "--scenarios", "does-not-exist",
            ])
            assert rc == 1
