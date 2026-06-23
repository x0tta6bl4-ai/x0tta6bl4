import json
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from src.self_healing.ebpf_anomaly_detector import (
    EBPFAnalyzer,
    EBPFAnomaly,
    EBPFAnomalyType,
    EBPFExecutor,
    EBPFPlanner,
)
from src.self_healing.mape_k.analyzer import MAPEKAnalyzer
from src.self_healing.pqc_zero_trust_healer import (
    PQCHealthMetrics,
    PQCSessionAnomaly,
    PQCZeroTrustAnalyzer,
    PQCZeroTrustExecutor,
    PQCZeroTrustMonitor,
    PQCZeroTrustPlanner,
)


def _status_text(status):
    return json.dumps(status, sort_keys=True, default=str)


def _assert_redacted(status, *raw_values):
    text = _status_text(status)
    for raw_value in raw_values:
        assert str(raw_value) not in text


class _Loader:
    def cleanup(self):
        return None

    def load_programs(self):
        return None


@pytest.mark.asyncio
async def test_ebpf_self_healing_thinking_redacts_interface_and_context():
    analyzer = EBPFAnalyzer()
    anomaly = analyzer.analyze(
        {
            "interface": "secret-iface0",
            "total_packets": 100,
            "dropped_packets": 20,
        }
    )
    assert anomaly is not None
    _assert_redacted(analyzer.get_thinking_status(), "secret-iface0")

    planner = EBPFPlanner()
    actions = planner.plan(anomaly)
    assert actions
    _assert_redacted(planner.get_thinking_status(), "secret-iface0")

    executor = EBPFExecutor(
        _Loader(),
        node_id="secret-node",
        event_bus=None,
        require_policy=False,
    )
    assert executor.execute({"action": "clear_packet_queues", "interface": "secret-iface0"}) is False
    status = executor.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "healing"
    _assert_redacted(status, "secret-iface0", "secret-node")


@pytest.mark.asyncio
async def test_pqc_self_healing_thinking_redacts_session_peer_and_action_text():
    now = time.time()
    gateway = SimpleNamespace(
        sessions={
            "secret-session-id": SimpleNamespace(
                last_used=now - 7200,
                created_at=now - 7200,
                peer_id="secret-peer-id",
            )
        }
    )
    monitor = PQCZeroTrustMonitor(pqc_gateway=gateway)
    monitoring = await monitor.monitor()
    assert monitoring["health_metrics"].total_sessions == 1
    _assert_redacted(
        monitor.get_thinking_status(),
        "secret-session-id",
        "secret-peer-id",
    )

    analyzer = PQCZeroTrustAnalyzer()
    health = PQCHealthMetrics(
        total_sessions=1,
        active_sessions=0,
        expired_sessions=1,
        failed_verifications=0,
        verification_rate=1.0,
        average_session_age=7200,
        anomaly_count=1,
        last_updated=datetime.now(),
    )
    analysis = await analyzer.analyze(
        {
            "health_metrics": health,
            "anomalies": [
                PQCSessionAnomaly(
                    anomaly_type="expired",
                    severity="high",
                    description="secret anomaly description",
                    timestamp=datetime.now() - timedelta(minutes=1),
                    session_id="secret-session-id",
                    peer_id="secret-peer-id",
                )
            ],
        }
    )
    assert analysis["requires_action"] is True
    _assert_redacted(
        analyzer.get_thinking_status(),
        "secret anomaly description",
        "secret-session-id",
        "secret-peer-id",
    )

    planner = PQCZeroTrustPlanner()
    plan = await planner.plan(analysis)
    assert plan["actions"]
    _assert_redacted(planner.get_thinking_status(), "Rotate expired PQC sessions")

    executor = PQCZeroTrustExecutor(
        pqc_gateway=gateway,
        node_id="secret-node",
        event_bus=None,
        require_policy=False,
    )
    await executor.execute({"actions": ["secret manual action"], "priority": "high"})
    status = executor.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "healing"
    _assert_redacted(status, "secret manual action", "secret-node")


def test_mapek_analyzer_thinking_redacts_metrics_logs_and_node_id():
    analyzer = MAPEKAnalyzer()
    issue = analyzer.analyze(
        {
            "cpu_percent": 95,
            "logs": "secret logs with token",
            "service_id": "secret-service",
        },
        node_id="secret-node-id",
        event_id="secret-event-id",
    )
    assert issue
    status = analyzer.get_thinking_status()
    assert status["thinking"]["profile"]["role"] == "analysis"
    _assert_redacted(
        status,
        "secret logs with token",
        "secret-service",
        "secret-node-id",
        "secret-event-id",
    )
