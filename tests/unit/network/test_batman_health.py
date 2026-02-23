"""
Unit Tests for Batman-adv Health Monitoring
============================================

Tests for BatmanHealthMonitor, BatmanMetricsCollector, and MAPE-K integration.
"""

import asyncio
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

# Import Batman components
from libx0t.network.batman.health_monitor import (
    BatmanHealthMonitor,
    HealthCheckResult,
    HealthStatus,
    HealthCheckType,
    NodeHealthReport,
    create_health_monitor_for_mapek,
)
from libx0t.network.batman.metrics import (
    BatmanMetricsCollector,
    BatmanMetricsSnapshot,
    create_metrics_collector_for_mapek,
)
from libx0t.network.batman.mape_k_integration import (
    BatmanAnomaly,
    BatmanAnomalyType,
    BatmanMAPEKMonitor,
    BatmanMAPEKAnalyzer,
    BatmanMAPEKPlanner,
    BatmanMAPEKExecutor,
    BatmanMAPEKKnowledge,
    BatmanMAPEKLoop,
    BatmanRecoveryAction,
    BatmanRecoveryPlan,
    create_batman_mapek_loop,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_subprocess():
    """Mock subprocess for batctl commands."""
    with patch('subprocess.run') as mock_run:
        yield mock_run


@pytest.fixture
def health_monitor():
    """Create a BatmanHealthMonitor instance for testing."""
    return BatmanHealthMonitor(
        node_id="test-node-001",
        interface="bat0",
        check_interval=5.0,
        enable_prometheus=False,
    )


@pytest.fixture
def metrics_collector():
    """Create a BatmanMetricsCollector instance for testing."""
    return BatmanMetricsCollector(
        node_id="test-node-001",
        interface="bat0",
        collection_interval=5.0,
    )


@pytest.fixture
def mapek_loop():
    """Create a BatmanMAPEKLoop instance for testing."""
    return BatmanMAPEKLoop(
        node_id="test-node-001",
        interface="bat0",
        cycle_interval=5.0,
        auto_heal=False,  # Disable auto-heal for testing
    )


# ============================================================================
# BatmanHealthMonitor Tests
# ============================================================================

class TestBatmanHealthMonitor:
    """Tests for BatmanHealthMonitor class."""
    
    def test_initialization(self, health_monitor):
        """Test health monitor initialization."""
        assert health_monitor.node_id == "test-node-001"
        assert health_monitor.interface == "bat0"
        assert health_monitor.check_interval == 5.0
        assert not health_monitor._running
        assert health_monitor._last_report is None
    
    def test_health_status_enum(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.UNKNOWN.value == "unknown"
    
    def test_health_check_type_enum(self):
        """Test HealthCheckType enum values."""
        assert HealthCheckType.CONNECTIVITY.value == "connectivity"
        assert HealthCheckType.LINK_QUALITY.value == "link_quality"
        assert HealthCheckType.ORIGINATOR_TABLE.value == "originator_table"
        assert HealthCheckType.GATEWAY.value == "gateway"
        assert HealthCheckType.INTERFACE.value == "interface"
        assert HealthCheckType.ROUTING.value == "routing"
    
    def test_calculate_overall_score(self, health_monitor):
        """Test overall score calculation."""
        checks = [
            HealthCheckResult(
                check_type=HealthCheckType.CONNECTIVITY,
                status=HealthStatus.HEALTHY,
                score=1.0,
                message="OK",
            ),
            HealthCheckResult(
                check_type=HealthCheckType.LINK_QUALITY,
                status=HealthStatus.HEALTHY,
                score=0.8,
                message="Good",
            ),
        ]
        
        score = health_monitor._calculate_overall_score(checks)
        assert 0.0 <= score <= 1.0
        assert score > 0.8  # Should be high with healthy checks
    
    def test_determine_status_healthy(self, health_monitor):
        """Test status determination for healthy score."""
        status = health_monitor._determine_status(0.9)
        assert status == HealthStatus.HEALTHY
    
    def test_determine_status_degraded(self, health_monitor):
        """Test status determination for degraded score."""
        status = health_monitor._determine_status(0.6)
        assert status == HealthStatus.DEGRADED
    
    def test_determine_status_unhealthy(self, health_monitor):
        """Test status determination for unhealthy score."""
        status = health_monitor._determine_status(0.3)
        assert status == HealthStatus.UNHEALTHY
    
    def test_generate_recommendations(self, health_monitor):
        """Test recommendation generation."""
        checks = [
            HealthCheckResult(
                check_type=HealthCheckType.CONNECTIVITY,
                status=HealthStatus.UNHEALTHY,
                score=0.0,
                message="No connectivity",
            ),
            HealthCheckResult(
                check_type=HealthCheckType.GATEWAY,
                status=HealthStatus.UNHEALTHY,
                score=0.0,
                message="No gateway",
            ),
        ]
        
        recommendations = health_monitor._generate_recommendations(checks)
        assert len(recommendations) > 0
        assert any("connectivity" in r.lower() for r in recommendations)
    
    @pytest.mark.asyncio
    async def test_check_interface_up(self, health_monitor, mock_subprocess):
        """Test interface check when interface is up."""
        # Use "state UP" instead of "state UNKNOWN" to pass the health check
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="2: bat0: <BROADCAST,MULTICAST,UP,LOWER_UP> mtu 1500 qdisc noqueue state UP mode DEFAULT group default qlen 1000"
        )
        
        result = await health_monitor._check_interface()
        
        assert result.check_type == HealthCheckType.INTERFACE
        assert result.status == HealthStatus.HEALTHY
        assert result.score == 1.0
    
    @pytest.mark.asyncio
    async def test_check_interface_down(self, health_monitor, mock_subprocess):
        """Test interface check when interface is down."""
        mock_subprocess.return_value = MagicMock(
            returncode=1,
            stdout=""
        )
        
        result = await health_monitor._check_interface()
        
        assert result.check_type == HealthCheckType.INTERFACE
        assert result.status == HealthStatus.UNHEALTHY
        assert result.score == 0.0
    
    @pytest.mark.asyncio
    async def test_check_originator_table_empty(self, health_monitor, mock_subprocess):
        """Test originator table check when empty."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="BATMAN_IV bat0 table\nOriginator      last-seen (#/255) Nexthop       [outgoingIF]"
        )
        
        result = await health_monitor._check_originator_table()
        
        assert result.check_type == HealthCheckType.ORIGINATOR_TABLE
        assert result.status == HealthStatus.UNHEALTHY
    
    @pytest.mark.asyncio
    async def test_check_originator_table_populated(self, health_monitor, mock_subprocess):
        """Test originator table check with originators."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.010s   (255) aa:bb:cc:dd:ee:ff [ bat0-0]
* 11:22:33:44:55:66    0.020s   (200) 11:22:33:44:55:66 [ bat0-1]
"""
        )
        
        result = await health_monitor._check_originator_table()
        
        assert result.check_type == HealthCheckType.ORIGINATOR_TABLE
        assert result.details["originators_count"] == 2
    
    @pytest.mark.asyncio
    async def test_run_health_checks(self, health_monitor, mock_subprocess):
        """Test running all health checks."""
        # Mock all subprocess calls
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.010s   (255) aa:bb:cc:dd:ee:ff [ bat0-0]
"""
        )
        
        report = await health_monitor.run_health_checks()
        
        assert isinstance(report, NodeHealthReport)
        assert report.node_id == "test-node-001"
        assert len(report.checks) > 0
        assert isinstance(report.overall_status, HealthStatus)
        assert 0.0 <= report.overall_score <= 1.0
    
    def test_get_health_trend_insufficient_data(self, health_monitor):
        """Test health trend with insufficient data."""
        trend = health_monitor.get_health_trend()
        assert trend["trend"] == "insufficient_data"
    
    def test_get_health_trend_improving(self, health_monitor):
        """Test health trend detection for improving health."""
        # Add some health reports with improving scores
        for i, score in enumerate([0.3, 0.4, 0.5, 0.6, 0.7, 0.8]):
            report = NodeHealthReport(
                node_id="test-node-001",
                overall_status=HealthStatus.HEALTHY if score >= 0.8 else HealthStatus.DEGRADED,
                overall_score=score,
            )
            health_monitor._health_history.append(report)
        
        trend = health_monitor.get_health_trend()
        assert trend["trend"] == "improving"
    
    def test_get_health_trend_declining(self, health_monitor):
        """Test health trend detection for declining health."""
        # Add some health reports with declining scores
        for i, score in enumerate([0.8, 0.7, 0.6, 0.5, 0.4, 0.3]):
            report = NodeHealthReport(
                node_id="test-node-001",
                overall_status=HealthStatus.DEGRADED,
                overall_score=score,
            )
            health_monitor._health_history.append(report)
        
        trend = health_monitor.get_health_trend()
        assert trend["trend"] == "declining"
    
    def test_register_custom_check(self, health_monitor):
        """Test registering a custom health check."""
        async def custom_check():
            return HealthCheckResult(
                check_type=HealthCheckType.CONNECTIVITY,
                status=HealthStatus.HEALTHY,
                score=1.0,
                message="Custom check passed",
            )
        
        health_monitor.register_custom_check("custom_test", custom_check)
        
        assert "custom_test" in health_monitor._custom_checks
        assert health_monitor._custom_checks["custom_test"] == custom_check


# ============================================================================
# BatmanMetricsCollector Tests
# ============================================================================

class TestBatmanMetricsCollector:
    """Tests for BatmanMetricsCollector class."""
    
    def test_initialization(self, metrics_collector):
        """Test metrics collector initialization."""
        assert metrics_collector.node_id == "test-node-001"
        assert metrics_collector.interface == "bat0"
        assert metrics_collector.collection_interval == 5.0
        assert not metrics_collector._running
    
    def test_metrics_snapshot_to_dict(self):
        """Test BatmanMetricsSnapshot to_dict method."""
        snapshot = BatmanMetricsSnapshot(
            originators_count=5,
            neighbors_count=3,
            avg_link_quality=0.85,
        )
        
        data = snapshot.to_dict()
        
        assert data["originators_count"] == 5
        assert data["neighbors_count"] == 3
        assert data["avg_link_quality"] == 0.85
        assert "timestamp" in data
    
    @pytest.mark.asyncio
    async def test_collect_topology_metrics(self, metrics_collector, mock_subprocess):
        """Test topology metrics collection."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.010s   (255) aa:bb:cc:dd:ee:ff [ bat0-0]
* 11:22:33:44:55:66    0.020s   (200) 11:22:33:44:55:66 [ bat0-1]
"""
        )
        
        snapshot = BatmanMetricsSnapshot()
        await metrics_collector._collect_topology_metrics(snapshot)
        
        assert snapshot.originators_count == 2
    
    @pytest.mark.asyncio
    async def test_collect_link_metrics(self, metrics_collector, mock_subprocess):
        """Test link metrics collection."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.010s   (255) aa:bb:cc:dd:ee:ff [ bat0-0]
* 11:22:33:44:55:66    0.020s   (200) 11:22:33:44:55:66 [ bat0-1]
"""
        )
        
        snapshot = BatmanMetricsSnapshot()
        await metrics_collector._collect_link_metrics(snapshot)
        
        assert snapshot.total_links == 2
        assert snapshot.avg_link_quality > 0
    
    @pytest.mark.asyncio
    async def test_collect(self, metrics_collector, mock_subprocess):
        """Test full metrics collection."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="BATMAN_IV bat0 table\n"
        )
        
        snapshot = await metrics_collector.collect()
        
        assert isinstance(snapshot, BatmanMetricsSnapshot)
        assert metrics_collector._last_snapshot == snapshot
    
    def test_get_last_snapshot(self, metrics_collector):
        """Test getting last snapshot."""
        snapshot = BatmanMetricsSnapshot(originators_count=10)
        metrics_collector._last_snapshot = snapshot
        
        result = metrics_collector.get_last_snapshot()
        
        assert result == snapshot
        assert result.originators_count == 10


# ============================================================================
# BatmanMAPEKAnalyzer Tests
# ============================================================================

class TestBatmanMAPEKAnalyzer:
    """Tests for BatmanMAPEKAnalyzer class."""
    
    def test_initialization(self):
        """Test analyzer initialization."""
        analyzer = BatmanMAPEKAnalyzer()
        assert analyzer._anomaly_history == []
    
    def test_analyze_healthy_node(self):
        """Test analysis of healthy node."""
        analyzer = BatmanMAPEKAnalyzer()
        
        monitoring_data = {
            "health_report": {
                "node_id": "test-node-001",
                "overall_score": 0.95,
                "overall_status": "healthy",
                "checks": [],
            },
            "metrics": {
                "latency_ms": 10.0,
                "packet_loss_percent": 0.1,
                "avg_link_quality": 0.95,
            },
        }
        
        anomalies = analyzer.analyze(monitoring_data)
        
        assert len(anomalies) == 0
    
    def test_analyze_unhealthy_node(self):
        """Test analysis of unhealthy node."""
        analyzer = BatmanMAPEKAnalyzer()
        
        monitoring_data = {
            "health_report": {
                "node_id": "test-node-001",
                "overall_score": 0.3,
                "overall_status": "unhealthy",
                "checks": [],
            },
            "metrics": {
                "latency_ms": 150.0,
                "packet_loss_percent": 10.0,
                "avg_link_quality": 0.3,
            },
        }
        
        anomalies = analyzer.analyze(monitoring_data)
        
        assert len(anomalies) > 0
        assert any(a.anomaly_type == BatmanAnomalyType.NODE_UNHEALTHY for a in anomalies)
    
    def test_analyze_high_latency(self):
        """Test detection of high latency."""
        analyzer = BatmanMAPEKAnalyzer()
        
        monitoring_data = {
            "health_report": {
                "node_id": "test-node-001",
                "overall_score": 0.9,
                "checks": [],
            },
            "metrics": {
                "latency_ms": 150.0,
                "packet_loss_percent": 0.0,
                "avg_link_quality": 0.9,
            },
        }
        
        anomalies = analyzer.analyze(monitoring_data)
        
        assert any(a.anomaly_type == BatmanAnomalyType.HIGH_LATENCY for a in anomalies)
    
    def test_analyze_packet_loss(self):
        """Test detection of packet loss."""
        analyzer = BatmanMAPEKAnalyzer()
        
        monitoring_data = {
            "health_report": {
                "node_id": "test-node-001",
                "overall_score": 0.9,
                "checks": [],
            },
            "metrics": {
                "latency_ms": 10.0,
                "packet_loss_percent": 10.0,
                "avg_link_quality": 0.9,
            },
        }
        
        anomalies = analyzer.analyze(monitoring_data)
        
        assert any(a.anomaly_type == BatmanAnomalyType.PACKET_LOSS for a in anomalies)
    
    def test_analyze_no_gateway(self):
        """Test detection of no gateway."""
        analyzer = BatmanMAPEKAnalyzer()
        
        monitoring_data = {
            "health_report": {
                "node_id": "test-node-001",
                "overall_score": 0.9,
                "checks": [
                    {
                        "type": "gateway",
                        "status": "unhealthy",
                        "score": 0.0,
                        "message": "No gateway available",
                    }
                ],
            },
            "metrics": {},
        }
        
        anomalies = analyzer.analyze(monitoring_data)
        
        assert any(a.anomaly_type == BatmanAnomalyType.NO_GATEWAY for a in anomalies)


# ============================================================================
# BatmanMAPEKPlanner Tests
# ============================================================================

class TestBatmanMAPEKPlanner:
    """Tests for BatmanMAPEKPlanner class."""
    
    def test_initialization(self):
        """Test planner initialization."""
        planner = BatmanMAPEKPlanner()
        assert planner._plan_history == []
        assert planner._plan_counter == 0
    
    def test_plan_for_interface_down(self):
        """Test planning for interface down anomaly."""
        planner = BatmanMAPEKPlanner()
        
        anomalies = [
            BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.INTERFACE_DOWN,
                severity="critical",
                description="Interface is down",
                affected_node="test-node-001",
            )
        ]
        
        plan = planner.plan(anomalies)
        
        assert BatmanRecoveryAction.RESTART_INTERFACE in plan.actions
        assert plan.priority == 1  # Highest priority
    
    def test_plan_for_no_gateway(self):
        """Test planning for no gateway anomaly."""
        planner = BatmanMAPEKPlanner()
        
        anomalies = [
            BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.NO_GATEWAY,
                severity="medium",
                description="No gateway available",
                affected_node="test-node-001",
            )
        ]
        
        plan = planner.plan(anomalies)
        
        assert BatmanRecoveryAction.RESELECT_GATEWAY in plan.actions
    
    def test_plan_for_multiple_anomalies(self):
        """Test planning for multiple anomalies."""
        planner = BatmanMAPEKPlanner()
        
        anomalies = [
            BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.HIGH_LATENCY,
                severity="medium",
                description="High latency",
                affected_node="test-node-001",
            ),
            BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.PACKET_LOSS,
                severity="high",
                description="Packet loss",
                affected_node="test-node-001",
            ),
        ]
        
        plan = planner.plan(anomalies)
        
        assert len(plan.actions) > 0
        assert plan.priority <= 3  # Should have reasonable priority


# ============================================================================
# BatmanMAPEKExecutor Tests
# ============================================================================

class TestBatmanMAPEKExecutor:
    """Tests for BatmanMAPEKExecutor class."""
    
    def test_initialization(self):
        """Test executor initialization."""
        executor = BatmanMAPEKExecutor(interface="bat0")
        assert executor.interface == "bat0"
        assert executor._execution_history == []
    
    @pytest.mark.asyncio
    async def test_execute_restart_interface(self, mock_subprocess):
        """Test executing restart interface action."""
        mock_subprocess.return_value = MagicMock(returncode=0)
        
        executor = BatmanMAPEKExecutor(interface="bat0")
        result = await executor._restart_interface()
        
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_execute_reselect_gateway(self, mock_subprocess):
        """Test executing reselect gateway action."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="client"
        )
        
        executor = BatmanMAPEKExecutor(interface="bat0")
        result = await executor._reselect_gateway()
        
        assert result["status"] == "success"
    
    @pytest.mark.asyncio
    async def test_execute_escalate(self):
        """Test executing escalate action."""
        executor = BatmanMAPEKExecutor(interface="bat0")
        
        plan = BatmanRecoveryPlan(
            plan_id="test-plan",
            anomalies=[],
            actions=[BatmanRecoveryAction.ESCALATE],
            priority=1,
            estimated_duration_seconds=0,
        )
        
        result = await executor._escalate(plan)
        
        assert result["status"] == "escalated"


# ============================================================================
# BatmanMAPEKKnowledge Tests
# ============================================================================

class TestBatmanMAPEKKnowledge:
    """Tests for BatmanMAPEKKnowledge class."""
    
    def test_initialization(self):
        """Test knowledge initialization."""
        knowledge = BatmanMAPEKKnowledge()
        assert knowledge._incident_history == []
        assert knowledge._successful_actions == {}
        assert knowledge._failed_actions == {}
    
    def test_record_incident(self):
        """Test recording an incident."""
        knowledge = BatmanMAPEKKnowledge()
        
        anomalies = [
            BatmanAnomaly(
                anomaly_type=BatmanAnomalyType.NO_GATEWAY,
                severity="medium",
                description="No gateway",
                affected_node="test-node-001",
            )
        ]
        
        plan = BatmanRecoveryPlan(
            plan_id="test-plan",
            anomalies=anomalies,
            actions=[BatmanRecoveryAction.RESELECT_GATEWAY],
            priority=3,
            estimated_duration_seconds=5.0,
        )
        
        execution_result = {
            "actions_executed": [{"action": "reselect_gateway", "result": {"status": "success"}}],
            "actions_failed": [],
        }
        
        knowledge.record_incident(anomalies, plan, execution_result)
        
        assert len(knowledge._incident_history) == 1
        assert knowledge._successful_actions.get("reselect_gateway") == 1
    
    def test_get_action_success_rate(self):
        """Test getting action success rate."""
        knowledge = BatmanMAPEKKnowledge()
        
        # Record some successes and failures
        knowledge._successful_actions["restart_interface"] = 8
        knowledge._failed_actions["restart_interface"] = 2
        
        rate = knowledge.get_action_success_rate("restart_interface")
        
        assert rate == 0.8
    
    def test_get_action_success_rate_unknown(self):
        """Test getting success rate for unknown action."""
        knowledge = BatmanMAPEKKnowledge()
        
        rate = knowledge.get_action_success_rate("unknown_action")
        
        assert rate == 0.5  # Unknown defaults to 0.5
    
    def test_record_health_trend(self):
        """Test recording health trend."""
        knowledge = BatmanMAPEKKnowledge()
        
        knowledge.record_health_trend("node-001", 0.8)
        knowledge.record_health_trend("node-001", 0.9)
        
        assert len(knowledge._node_health_trends["node-001"]) == 2


# ============================================================================
# BatmanMAPEKLoop Tests
# ============================================================================

class TestBatmanMAPEKLoop:
    """Tests for BatmanMAPEKLoop class."""
    
    def test_initialization(self, mapek_loop):
        """Test MAPE-K loop initialization."""
        assert mapek_loop.node_id == "test-node-001"
        assert mapek_loop.interface == "bat0"
        assert not mapek_loop._running
        assert not mapek_loop.auto_heal
    
    @pytest.mark.asyncio
    async def test_run_cycle(self, mapek_loop, mock_subprocess):
        """Test running a MAPE-K cycle."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.010s   (255) aa:bb:cc:dd:ee:ff [ bat0-0]
"""
        )
        
        result = await mapek_loop.run_cycle()
        
        assert "cycle_id" in result
        assert "node_id" in result
        assert "success" in result
        assert result["node_id"] == "test-node-001"
    
    def test_get_status(self, mapek_loop):
        """Test getting MAPE-K loop status."""
        status = mapek_loop.get_status()
        
        assert status["node_id"] == "test-node-001"
        assert status["interface"] == "bat0"
        assert "running" in status
        assert "cycle_count" in status
    
    def test_stop(self, mapek_loop):
        """Test stopping MAPE-K loop."""
        mapek_loop._running = True
        mapek_loop.stop()
        
        assert not mapek_loop._running


# ============================================================================
# Factory Function Tests
# ============================================================================

class TestFactoryFunctions:
    """Tests for factory functions."""
    
    def test_create_health_monitor_for_mapek(self):
        """Test creating health monitor for MAPE-K."""
        monitor = create_health_monitor_for_mapek(
            node_id="test-node",
            interface="bat0",
        )
        
        assert isinstance(monitor, BatmanHealthMonitor)
        assert monitor.node_id == "test-node"
    
    def test_create_metrics_collector_for_mapek(self):
        """Test creating metrics collector for MAPE-K."""
        collector = create_metrics_collector_for_mapek(
            node_id="test-node",
            interface="bat0",
        )
        
        assert isinstance(collector, BatmanMetricsCollector)
        assert collector.node_id == "test-node"
    
    def test_create_batman_mapek_loop(self):
        """Test creating Batman MAPE-K loop."""
        loop = create_batman_mapek_loop(
            node_id="test-node",
            interface="bat0",
            auto_heal=True,
        )
        
        assert isinstance(loop, BatmanMAPEKLoop)
        assert loop.node_id == "test-node"
        assert loop.auto_heal


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Integration tests for Batman components."""
    
    @pytest.mark.asyncio
    async def test_full_mapek_cycle(self, mock_subprocess):
        """Test full MAPE-K cycle integration."""
        # Mock all subprocess calls
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
* aa:bb:cc:dd:ee:ff    0.010s   (255) aa:bb:cc:dd:ee:ff [ bat0-0]
"""
        )
        
        # Create components
        loop = BatmanMAPEKLoop(
            node_id="integration-test-node",
            interface="bat0",
            auto_heal=False,
        )
        
        # Run cycle
        result = await loop.run_cycle()
        
        assert result["success"]
        assert "monitoring" in result
        assert "anomalies" in result
    
    @pytest.mark.asyncio
    async def test_health_monitor_to_analyzer_flow(self, mock_subprocess):
        """Test flow from health monitor to analyzer."""
        mock_subprocess.return_value = MagicMock(
            returncode=0,
            stdout="""BATMAN_IV bat0 table
Originator      last-seen (#/255) Nexthop       [outgoingIF]
"""
        )
        
        # Create health monitor
        monitor = BatmanHealthMonitor(
            node_id="flow-test-node",
            interface="bat0",
            enable_prometheus=False,
        )
        
        # Run health checks
        report = await monitor.run_health_checks()
        
        # Create analyzer
        analyzer = BatmanMAPEKAnalyzer()
        
        # Analyze health report
        monitoring_data = {
            "health_report": report.to_dict(),
            "metrics": {},
        }
        
        anomalies = analyzer.analyze(monitoring_data)
        
        # Should detect issues with empty originator table
        assert len(anomalies) > 0


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
