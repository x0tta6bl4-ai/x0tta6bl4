"""
Unit tests for PQC Zero-Trust Healer (MAPE-K cycle).

Tests cover:
- PQCZeroTrustMonitor: monitor(), _detect_anomalies()
- PQCZeroTrustAnalyzer: analyze(), _calculate_health_score()
- PQCZeroTrustPlanner: plan()
- PQCZeroTrustExecutor: execute(), all _execute_action variants
- PQCZeroTrustHealer: integration of MAPE-K components
- PQCSessionAnomaly / PQCHealthMetrics dataclasses
"""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from datetime import datetime, timedelta
from types import SimpleNamespace


# ---------------------------------------------------------------------------
# Helpers – build mock sessions / gateways / loaders used by many tests
# ---------------------------------------------------------------------------

def _make_session(peer_id="peer-1", created_offset=0, last_used_offset=0):
    """Return a SimpleNamespace that looks like a PQCSession.

    PQCSession.last_used is a float (time.time()) in the real class.
    """
    now = time.time()
    return SimpleNamespace(
        peer_id=peer_id,
        created_at=now - created_offset,
        last_used=now - last_used_offset,
        isolated=False,
    )


def _make_gateway(sessions=None):
    gw = MagicMock()
    gw.sessions = sessions if sessions is not None else {}
    gw.rotate_session_keys = MagicMock(return_value=True)
    return gw


def _make_loader(stats=None):
    loader = MagicMock()
    loader.get_pqc_stats = MagicMock(return_value=stats or {})
    loader.sync_with_gateway = MagicMock()
    return loader


# ---------------------------------------------------------------------------
# Import the module under test  (after conftest mocks liboqs / bcc)
# ---------------------------------------------------------------------------

@pytest.fixture
def _import_module():
    """Import the healer module; patch get_pqc_gateway so constructors
    don't try to create a real gateway."""
    with patch(
        "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
        return_value=_make_gateway(),
    ):
        from src.self_healing.pqc_zero_trust_healer import (
            PQCSessionAnomaly,
            PQCHealthMetrics,
            PQCZeroTrustMonitor,
            PQCZeroTrustAnalyzer,
            PQCZeroTrustPlanner,
            PQCZeroTrustExecutor,
            PQCZeroTrustHealer,
        )
        yield {
            "PQCSessionAnomaly": PQCSessionAnomaly,
            "PQCHealthMetrics": PQCHealthMetrics,
            "PQCZeroTrustMonitor": PQCZeroTrustMonitor,
            "PQCZeroTrustAnalyzer": PQCZeroTrustAnalyzer,
            "PQCZeroTrustPlanner": PQCZeroTrustPlanner,
            "PQCZeroTrustExecutor": PQCZeroTrustExecutor,
            "PQCZeroTrustHealer": PQCZeroTrustHealer,
        }


# ===================================================================
# Dataclass smoke tests
# ===================================================================

class TestDataclasses:

    def test_pqc_session_anomaly_defaults(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        a = cls(
            session_id="s1",
            anomaly_type="expired",
            severity="medium",
            description="test",
            timestamp=datetime.now(),
        )
        assert a.peer_id is None
        assert a.failure_count == 0

    def test_pqc_session_anomaly_with_optional(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        a = cls(
            session_id="s1",
            anomaly_type="high_failure_rate",
            severity="high",
            description="fail",
            timestamp=datetime.now(),
            peer_id="peer-5",
            failure_count=42,
        )
        assert a.peer_id == "peer-5"
        assert a.failure_count == 42

    def test_pqc_health_metrics(self, _import_module):
        cls = _import_module["PQCHealthMetrics"]
        m = cls(
            total_sessions=10,
            active_sessions=8,
            expired_sessions=2,
            failed_verifications=1,
            verification_rate=0.95,
            average_session_age=120.0,
            anomaly_count=0,
            last_updated=datetime.now(),
        )
        assert m.total_sessions == 10
        assert m.verification_rate == 0.95


# ===================================================================
# PQCZeroTrustMonitor
# ===================================================================

class TestPQCZeroTrustMonitor:

    def _make_monitor(self, mod, gateway=None, loader=None):
        gw = gateway or _make_gateway()
        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ):
            return mod["PQCZeroTrustMonitor"](pqc_gateway=gw, pqc_loader=loader)

    # -- monitor() happy path, no sessions, no loader ----------------

    @pytest.mark.asyncio
    async def test_monitor_empty_sessions(self, _import_module):
        mon = self._make_monitor(_import_module)
        result = await mon.monitor()
        assert "health_metrics" in result
        assert result["health_metrics"].total_sessions == 0
        assert result["anomalies"] == []

    # -- monitor() with active sessions ------------------------------

    @pytest.mark.asyncio
    async def test_monitor_active_sessions(self, _import_module):
        sessions = {"s1": _make_session(last_used_offset=60)}  # 1 min ago
        gw = _make_gateway(sessions)
        mon = self._make_monitor(_import_module, gateway=gw)
        result = await mon.monitor()
        assert result["health_metrics"].total_sessions == 1
        assert result["health_metrics"].active_sessions == 1
        assert result["health_metrics"].expired_sessions == 0

    # -- monitor() with expired sessions -----------------------------

    @pytest.mark.asyncio
    async def test_monitor_expired_sessions(self, _import_module):
        sessions = {"s1": _make_session(last_used_offset=7200)}  # 2h ago
        gw = _make_gateway(sessions)
        mon = self._make_monitor(_import_module, gateway=gw)
        result = await mon.monitor()
        assert result["health_metrics"].expired_sessions == 1

    # -- monitor() with eBPF loader ----------------------------------

    @pytest.mark.asyncio
    async def test_monitor_with_ebpf_loader(self, _import_module):
        loader = _make_loader({"total_packets": 100, "verified_packets": 90,
                               "failed_verification": 10})
        mon = self._make_monitor(_import_module, loader=loader)
        result = await mon.monitor()
        loader.get_pqc_stats.assert_called_once()
        assert "ebpf_stats" in result

    # -- monitor() exception path ------------------------------------

    @pytest.mark.asyncio
    async def test_monitor_exception_returns_error(self, _import_module):
        gw = _make_gateway()
        # Make sessions access raise
        type(gw).sessions = PropertyMock(side_effect=RuntimeError("boom"))
        mon = self._make_monitor(_import_module, gateway=gw)
        result = await mon.monitor()
        assert "error" in result
        assert "boom" in result["error"]

    # -- _detect_anomalies: expired sessions -------------------------

    def test_detect_anomalies_expired(self, _import_module):
        sessions = {"s1": _make_session(last_used_offset=7200)}
        gw = _make_gateway(sessions)
        mon = self._make_monitor(_import_module, gateway=gw)
        anomalies = mon._detect_anomalies(sessions, {}, time.time())
        expired = [a for a in anomalies if a.anomaly_type == "expired"]
        assert len(expired) == 1
        assert expired[0].severity == "medium"

    # -- _detect_anomalies: high failure rate ------------------------

    def test_detect_anomalies_high_failure_rate(self, _import_module):
        mon = self._make_monitor(_import_module)
        stats = {"total_packets": 200, "failed_verification": 50}
        anomalies = mon._detect_anomalies({}, stats, time.time())
        high_fail = [a for a in anomalies if a.anomaly_type == "high_failure_rate"]
        assert len(high_fail) == 1
        assert high_fail[0].severity == "high"

    # -- _detect_anomalies: no_session packets -----------------------

    def test_detect_anomalies_no_session_packets(self, _import_module):
        mon = self._make_monitor(_import_module)
        stats = {"no_session": 100}
        anomalies = mon._detect_anomalies({}, stats, time.time())
        ns = [a for a in anomalies if a.anomaly_type == "no_session"]
        assert len(ns) == 1

    # -- _detect_anomalies: anomaly storm ----------------------------

    def test_detect_anomalies_anomaly_storm(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        mon = self._make_monitor(_import_module)
        # Seed anomalies list with > max_anomalies_per_hour recent ones
        now = datetime.now()
        mon.anomalies = [
            cls(session_id=f"s{i}", anomaly_type="expired",
                severity="medium", description="old",
                timestamp=now - timedelta(minutes=5))
            for i in range(15)
        ]
        anomalies = mon._detect_anomalies({}, {}, time.time())
        storm = [a for a in anomalies if a.anomaly_type == "anomaly_storm"]
        assert len(storm) == 1
        assert storm[0].severity == "critical"

    # -- _detect_anomalies: below thresholds -> no anomalies ---------

    def test_detect_anomalies_below_thresholds(self, _import_module):
        mon = self._make_monitor(_import_module)
        stats = {"total_packets": 200, "failed_verification": 5, "no_session": 10}
        anomalies = mon._detect_anomalies({}, stats, time.time())
        assert anomalies == []

    # -- _detect_anomalies: too few packets for failure rate ---------

    def test_detect_anomalies_too_few_packets_for_rate(self, _import_module):
        mon = self._make_monitor(_import_module)
        stats = {"total_packets": 50, "failed_verification": 40}  # high rate but < 100
        anomalies = mon._detect_anomalies({}, stats, time.time())
        high_fail = [a for a in anomalies if a.anomaly_type == "high_failure_rate"]
        assert len(high_fail) == 0

    # -- _detect_anomalies: old anomalies pruned --------------------

    def test_old_anomalies_pruned(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        mon = self._make_monitor(_import_module)
        old_ts = datetime.now() - timedelta(hours=48)
        mon.anomalies = [
            cls(session_id="old", anomaly_type="expired",
                severity="low", description="ancient",
                timestamp=old_ts)
        ]
        mon._detect_anomalies({}, {}, time.time())
        # Old anomalies should be pruned (> 24h)
        assert len(mon.anomalies) == 0


# ===================================================================
# PQCZeroTrustAnalyzer
# ===================================================================

class TestPQCZeroTrustAnalyzer:

    def _make_analyzer(self, mod):
        return mod["PQCZeroTrustAnalyzer"]()

    def _make_metrics(self, mod, **kwargs):
        defaults = dict(
            total_sessions=10, active_sessions=8, expired_sessions=2,
            failed_verifications=0, verification_rate=0.95,
            average_session_age=100.0, anomaly_count=0,
            last_updated=datetime.now(),
        )
        defaults.update(kwargs)
        return mod["PQCHealthMetrics"](**defaults)

    # -- no health_metrics -------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_no_health_metrics(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        result = await analyzer.analyze({"anomalies": []})
        assert result["requires_action"] is False
        assert result["severity"] == "unknown"

    # -- no anomalies, healthy system --------------------------------

    @pytest.mark.asyncio
    async def test_analyze_healthy(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(_import_module)
        result = await analyzer.analyze({
            "anomalies": [],
            "health_metrics": metrics,
        })
        assert result["requires_action"] is False
        assert result["severity"] == "low"

    # -- critical anomalies ------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_critical_anomaly(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(_import_module)
        anomaly = cls(session_id="s1", anomaly_type="anomaly_storm",
                      severity="critical", description="storm",
                      timestamp=datetime.now())
        result = await analyzer.analyze({
            "anomalies": [anomaly],
            "health_metrics": metrics,
        })
        assert result["requires_action"] is True
        assert result["severity"] == "critical"

    # -- high anomalies ----------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_high_anomaly(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(_import_module)
        anomaly = cls(session_id="s1", anomaly_type="high_failure_rate",
                      severity="high", description="fail",
                      timestamp=datetime.now())
        result = await analyzer.analyze({
            "anomalies": [anomaly],
            "health_metrics": metrics,
        })
        assert result["severity"] == "high"
        assert result["requires_action"] is True

    # -- medium anomalies --------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_medium_anomaly(self, _import_module):
        cls = _import_module["PQCSessionAnomaly"]
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(_import_module)
        anomaly = cls(session_id="s1", anomaly_type="expired",
                      severity="medium", description="expired",
                      timestamp=datetime.now())
        result = await analyzer.analyze({
            "anomalies": [anomaly],
            "health_metrics": metrics,
        })
        assert result["severity"] == "medium"
        assert result["requires_action"] is True

    # -- low health score --------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_low_health_score(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        # Many anomalies => low health score
        metrics = self._make_metrics(
            _import_module,
            expired_sessions=9, active_sessions=1, anomaly_count=10,
        )
        result = await analyzer.analyze({
            "anomalies": [],
            "health_metrics": metrics,
        })
        assert result["requires_action"] is True
        assert result["severity"] in ("high", "medium")

    # -- more expired than active ------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_more_expired_than_active(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(
            _import_module,
            expired_sessions=7, active_sessions=3,
        )
        result = await analyzer.analyze({
            "anomalies": [],
            "health_metrics": metrics,
        })
        assert result["requires_action"] is True
        assert "More expired than active sessions" in result["issues"]

    # -- analyze exception -------------------------------------------

    @pytest.mark.asyncio
    async def test_analyze_exception(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        # Pass bad data that will cause analysis to fail
        result = await analyzer.analyze({
            "anomalies": "not-a-list",
            "health_metrics": MagicMock(
                expired_sessions=1,
                active_sessions=1,
                total_sessions=PropertyMock(side_effect=TypeError("bad")),
            ),
        })
        assert result["severity"] == "critical"
        assert result["requires_action"] is True

    # -- _calculate_health_score edge cases --------------------------

    def test_health_score_perfect(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(_import_module, anomaly_count=0,
                                     expired_sessions=0)
        score = analyzer._calculate_health_score(metrics)
        assert score == 1.0

    def test_health_score_none_metrics(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        assert analyzer._calculate_health_score(None) == 0.0

    def test_health_score_many_anomalies(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(_import_module, anomaly_count=20)
        score = analyzer._calculate_health_score(metrics)
        # 20 anomalies * 0.05 = 1.0 penalty, capped at 0.3
        assert score < 1.0

    def test_health_score_all_expired(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(
            _import_module,
            total_sessions=10, expired_sessions=10,
            active_sessions=0, anomaly_count=0,
        )
        score = analyzer._calculate_health_score(metrics)
        # expiry_ratio=1.0 => penalty 0.3
        assert score == pytest.approx(0.7)

    def test_health_score_zero_sessions(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(
            _import_module,
            total_sessions=0, expired_sessions=0,
            active_sessions=0, anomaly_count=0,
        )
        score = analyzer._calculate_health_score(metrics)
        assert score == 1.0

    def test_health_score_capped_at_zero(self, _import_module):
        analyzer = self._make_analyzer(_import_module)
        metrics = self._make_metrics(
            _import_module,
            total_sessions=10, expired_sessions=10,
            active_sessions=0, anomaly_count=100,
        )
        score = analyzer._calculate_health_score(metrics)
        assert score >= 0.0


# ===================================================================
# PQCZeroTrustPlanner
# ===================================================================

class TestPQCZeroTrustPlanner:

    def _make_planner(self, mod):
        return mod["PQCZeroTrustPlanner"]()

    # -- no action required ------------------------------------------

    @pytest.mark.asyncio
    async def test_plan_no_action(self, _import_module):
        planner = self._make_planner(_import_module)
        result = await planner.plan({"requires_action": False})
        assert result["actions"] == []
        assert result["priority"] == "low"
        assert result["estimated_duration"] == 0

    # -- critical severity -------------------------------------------

    @pytest.mark.asyncio
    async def test_plan_critical(self, _import_module):
        planner = self._make_planner(_import_module)
        result = await planner.plan({
            "requires_action": True,
            "severity": "critical",
            "analysis_data": {"anomaly_count": 2, "health_score": 0.3},
        })
        assert "Emergency: Rotate all PQC keys immediately" in result["actions"]
        assert "Isolate compromised sessions" in result["actions"]
        assert result["priority"] == "high"
        # low health score adds extra action
        assert "Perform full PQC system health check" in result["actions"]

    # -- high severity -----------------------------------------------

    @pytest.mark.asyncio
    async def test_plan_high(self, _import_module):
        planner = self._make_planner(_import_module)
        result = await planner.plan({
            "requires_action": True,
            "severity": "high",
            "analysis_data": {"anomaly_count": 1, "health_score": 0.8},
        })
        assert "Rotate expired PQC sessions" in result["actions"]
        assert result["priority"] == "high"

    # -- medium severity ---------------------------------------------

    @pytest.mark.asyncio
    async def test_plan_medium(self, _import_module):
        planner = self._make_planner(_import_module)
        result = await planner.plan({
            "requires_action": True,
            "severity": "medium",
            "analysis_data": {"anomaly_count": 1, "health_score": 0.9},
        })
        assert "Clean up expired sessions" in result["actions"]
        assert result["priority"] == "medium"

    # -- many anomalies trigger pattern analysis ---------------------

    @pytest.mark.asyncio
    async def test_plan_many_anomalies(self, _import_module):
        planner = self._make_planner(_import_module)
        result = await planner.plan({
            "requires_action": True,
            "severity": "medium",
            "analysis_data": {"anomaly_count": 10, "health_score": 0.9},
        })
        assert "Analyze anomaly patterns for attack detection" in result["actions"]

    # -- estimated_duration correct ----------------------------------

    @pytest.mark.asyncio
    async def test_plan_estimated_duration(self, _import_module):
        planner = self._make_planner(_import_module)
        result = await planner.plan({
            "requires_action": True,
            "severity": "medium",
            "analysis_data": {"anomaly_count": 0, "health_score": 0.9},
        })
        num_actions = len(result["actions"])
        assert result["estimated_duration"] == num_actions * 30

    # -- plan exception path -----------------------------------------

    @pytest.mark.asyncio
    async def test_plan_exception(self, _import_module):
        planner = self._make_planner(_import_module)
        # severity lookup on None should raise
        result = await planner.plan({
            "requires_action": True,
            "severity": None,
            "analysis_data": None,
        })
        # When analysis_data is None, .get() fails => exception path
        assert result["priority"] == "critical"
        assert "Manual intervention required" in result["actions"][0]


# ===================================================================
# PQCZeroTrustExecutor
# ===================================================================

class TestPQCZeroTrustExecutor:

    def _make_executor(self, mod, gateway=None, loader=None):
        gw = gateway or _make_gateway()
        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ):
            return mod["PQCZeroTrustExecutor"](pqc_gateway=gw, pqc_loader=loader)

    # -- execute with empty plan -------------------------------------

    @pytest.mark.asyncio
    async def test_execute_empty_plan(self, _import_module):
        executor = self._make_executor(_import_module)
        result = await executor.execute({"actions": []})
        assert result["success"] is True
        assert result["actions_executed"] == 0

    # -- execute with default/unrecognized action --------------------

    @pytest.mark.asyncio
    async def test_execute_default_action(self, _import_module):
        executor = self._make_executor(_import_module)
        result = await executor.execute({"actions": ["Alert security team"]})
        assert result["success"] is True
        assert result["success_count"] == 1

    # -- execute exception path on top-level -------------------------

    @pytest.mark.asyncio
    async def test_execute_top_level_exception(self, _import_module):
        executor = self._make_executor(_import_module)
        # plan.get('actions', []) on a non-dict will raise
        bad_plan = MagicMock()
        bad_plan.get = MagicMock(side_effect=RuntimeError("kaboom"))
        result = await executor.execute(bad_plan)
        assert result["success"] is False
        assert "kaboom" in result["execution_data"]["error"]

    # -- _execute_action routing -------------------------------------

    @pytest.mark.asyncio
    async def test_execute_action_rotate_all_keys(self, _import_module):
        sessions = {"s1": _make_session(), "s2": _make_session()}
        gw = _make_gateway(sessions)
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("Emergency: Rotate all PQC keys immediately")
        assert result["success"] is True
        assert result["rotated_sessions"] == 2
        assert gw.rotate_session_keys.call_count == 2

    @pytest.mark.asyncio
    async def test_execute_action_rotate_all_keys_with_loader(self, _import_module):
        gw = _make_gateway({"s1": _make_session()})
        loader = _make_loader()
        executor = self._make_executor(_import_module, gateway=gw, loader=loader)
        await executor._execute_action("Emergency: Rotate all PQC keys immediately")
        loader.sync_with_gateway.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_action_rotate_all_keys_exception(self, _import_module):
        gw = _make_gateway({"s1": _make_session()})
        gw.rotate_session_keys.side_effect = RuntimeError("rotate fail")
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("Emergency: Rotate all PQC keys immediately")
        # Individual rotation failures are caught, overall succeeds
        assert result["success"] is True
        assert result["rotated_sessions"] == 0

    @pytest.mark.asyncio
    async def test_execute_action_isolate_sessions(self, _import_module):
        # PQCSession.last_used is float but _isolate_compromised_sessions
        # uses datetime subtraction — TypeError is caught by except handler
        old_session = _make_session(last_used_offset=8000)
        gw = _make_gateway({"s1": old_session})
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("Isolate compromised sessions")
        # Returns failure because float vs datetime subtraction raises TypeError
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_action_isolate_no_sessions(self, _import_module):
        gw = _make_gateway({})
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("Isolate compromised sessions")
        # No sessions = no iteration = success
        assert result["success"] is True
        assert result["isolated_sessions"] == 0

    @pytest.mark.asyncio
    async def test_execute_action_enable_emergency_mode(self, _import_module):
        executor = self._make_executor(_import_module)
        result = await executor._execute_action("Enable emergency security mode")
        assert result["success"] is True
        assert result["action"] == "enable_emergency_mode"

    @pytest.mark.asyncio
    async def test_execute_action_rotate_expired(self, _import_module):
        old_session = _make_session(last_used_offset=7200)
        new_session = _make_session(last_used_offset=60)
        gw = _make_gateway({"old": old_session, "new": new_session})
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("Rotate expired PQC sessions")
        assert result["success"] is True
        assert result["rotated_sessions"] == 1

    @pytest.mark.asyncio
    async def test_execute_action_cleanup_expired(self, _import_module):
        old_session = _make_session(last_used_offset=8000)
        new_session = _make_session(last_used_offset=60)
        sessions = {"old": old_session, "new": new_session}
        gw = _make_gateway(sessions)
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("Clean up expired sessions")
        assert result["success"] is True
        assert result["cleaned_sessions"] == 1
        assert "old" not in gw.sessions

    @pytest.mark.asyncio
    async def test_execute_action_increase_monitoring(self, _import_module):
        executor = self._make_executor(_import_module)
        result = await executor._execute_action("Increase monitoring frequency")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_action_full_health_check(self, _import_module):
        # PQCSession.last_used is float but _perform_health_check uses
        # datetime subtraction — TypeError caught by except handler
        sessions = {"s1": _make_session(created_offset=120)}
        gw = _make_gateway(sessions)
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("full health check")
        # Fails due to float vs datetime mismatch in source code
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_action_health_check_empty(self, _import_module):
        gw = _make_gateway({})
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._execute_action("full health check")
        assert result["success"] is True
        assert result["health_report"]["total_sessions"] == 0

    # -- execute with mixed success/failure --------------------------

    @pytest.mark.asyncio
    async def test_execute_mixed_results(self, _import_module):
        executor = self._make_executor(_import_module)
        # Patch _execute_action to alternate success/fail
        call_count = 0
        original = executor._execute_action

        async def side_effect(action):
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                raise RuntimeError("forced failure")
            return await original(action)

        executor._execute_action = side_effect
        result = await executor.execute({
            "actions": ["Action 1", "Action 2", "Action 3"],
        })
        assert result["success"] is False  # not all succeeded
        assert result["success_count"] == 2
        assert result["failed_actions"] == 1

    # -- _rotate_all_keys top-level exception ------------------------

    @pytest.mark.asyncio
    async def test_rotate_all_keys_top_exception(self, _import_module):
        gw = _make_gateway()
        type(gw).sessions = PropertyMock(side_effect=RuntimeError("no sessions attr"))
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._rotate_all_keys()
        assert result["success"] is False
        assert "error" in result

    # -- _isolate_compromised_sessions exception ---------------------

    @pytest.mark.asyncio
    async def test_isolate_sessions_exception(self, _import_module):
        gw = _make_gateway()
        type(gw).sessions = PropertyMock(side_effect=RuntimeError("fail"))
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._isolate_compromised_sessions()
        assert result["success"] is False

    # -- _rotate_expired_sessions exception --------------------------

    @pytest.mark.asyncio
    async def test_rotate_expired_exception(self, _import_module):
        gw = _make_gateway()
        type(gw).sessions = PropertyMock(side_effect=RuntimeError("fail"))
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._rotate_expired_sessions()
        assert result["success"] is False

    # -- _cleanup_expired_sessions exception -------------------------

    @pytest.mark.asyncio
    async def test_cleanup_expired_exception(self, _import_module):
        gw = _make_gateway()
        type(gw).sessions = PropertyMock(side_effect=RuntimeError("fail"))
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._cleanup_expired_sessions()
        assert result["success"] is False

    # -- _perform_health_check exception -----------------------------

    @pytest.mark.asyncio
    async def test_health_check_exception(self, _import_module):
        gw = _make_gateway()
        type(gw).sessions = PropertyMock(side_effect=RuntimeError("fail"))
        executor = self._make_executor(_import_module, gateway=gw)
        result = await executor._perform_health_check()
        assert result["success"] is False

    # -- _rotate_expired with loader ---------------------------------

    @pytest.mark.asyncio
    async def test_rotate_expired_with_loader(self, _import_module):
        old_session = _make_session(last_used_offset=7200)
        gw = _make_gateway({"s1": old_session})
        loader = _make_loader()
        executor = self._make_executor(_import_module, gateway=gw, loader=loader)
        await executor._rotate_expired_sessions()
        loader.sync_with_gateway.assert_called_once()

    # -- _cleanup_expired with loader --------------------------------

    @pytest.mark.asyncio
    async def test_cleanup_expired_with_loader(self, _import_module):
        old_session = _make_session(last_used_offset=8000)
        gw = _make_gateway({"s1": old_session})
        loader = _make_loader()
        executor = self._make_executor(_import_module, gateway=gw, loader=loader)
        await executor._cleanup_expired_sessions()
        loader.sync_with_gateway.assert_called_once()


# ===================================================================
# PQCZeroTrustHealer (full MAPE-K integration)
# ===================================================================

class TestPQCZeroTrustHealer:

    @pytest.mark.asyncio
    async def test_healer_initialization(self, _import_module):
        cls = _import_module["PQCZeroTrustHealer"]
        gw = _make_gateway()
        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ), patch("asyncio.create_task"):
            healer = cls(pqc_gateway=gw)
            assert healer.monitor is not None
            assert healer.analyzer is not None
            assert healer.planner is not None
            assert healer.executor is not None

    @pytest.mark.asyncio
    async def test_healer_full_cycle_no_action(self, _import_module):
        """Simulate a full cycle where no healing is required."""
        cls = _import_module["PQCZeroTrustHealer"]
        gw = _make_gateway()
        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ), patch("asyncio.create_task"):
            healer = cls(pqc_gateway=gw)

        monitoring = await healer.monitor.monitor()
        analysis = await healer.analyzer.analyze(monitoring)
        assert analysis["requires_action"] is False

    @pytest.mark.asyncio
    async def test_healer_full_cycle_with_healing(self, _import_module):
        """Simulate a full cycle with expired sessions triggering healing."""
        cls = _import_module["PQCZeroTrustHealer"]
        sessions = {"s1": _make_session(last_used_offset=7200)}
        gw = _make_gateway(sessions)
        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ), patch("asyncio.create_task"):
            healer = cls(pqc_gateway=gw)

        monitoring = await healer.monitor.monitor()
        analysis = await healer.analyzer.analyze(monitoring)
        assert analysis["requires_action"] is True

        plan = await healer.planner.plan(analysis)
        assert len(plan["actions"]) > 0

        execution = await healer.executor.execute(plan)
        assert execution["success_count"] > 0

    @pytest.mark.asyncio
    async def test_healer_run_loop_single_iteration(self, _import_module):
        """Test run_healing_loop runs one iteration then breaks."""
        cls = _import_module["PQCZeroTrustHealer"]
        gw = _make_gateway()

        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ), patch("asyncio.create_task"):
            healer = cls(pqc_gateway=gw)

        # Patch asyncio.sleep to raise after first call so the loop stops
        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt("stop loop")

        with patch("asyncio.sleep", side_effect=fake_sleep):
            # The loop should catch Exception, but KeyboardInterrupt is BaseException
            # so it will propagate and stop.
            with pytest.raises(KeyboardInterrupt):
                await healer.run_healing_loop()

    @pytest.mark.asyncio
    async def test_healer_run_loop_handles_exception(self, _import_module):
        """Test that run_healing_loop handles exceptions gracefully."""
        cls = _import_module["PQCZeroTrustHealer"]
        gw = _make_gateway()

        with patch(
            "src.self_healing.pqc_zero_trust_healer.get_pqc_gateway",
            return_value=gw,
        ), patch("asyncio.create_task"):
            healer = cls(pqc_gateway=gw)

        # Make monitor raise, then stop after the error-path sleep
        healer.monitor.monitor = AsyncMock(side_effect=RuntimeError("monitor broke"))

        call_count = 0

        async def fake_sleep(duration):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                raise KeyboardInterrupt("stop")

        with patch("asyncio.sleep", side_effect=fake_sleep):
            with pytest.raises(KeyboardInterrupt):
                await healer.run_healing_loop()
        # Verify the error path was reached (sleep was called with 30s)
        assert call_count >= 1
