"""
Tests for remaining security and monitoring modules:
- security/identity_normalization: CVE-2020-12812 protection
- security/anti_meave_oracle: Agent swarm protection
- security/policy_decision_adapter: Policy normalization
- monitoring/advanced_sla_metrics: SLA tracking
- monitoring/alerting_rules: Alert rules
- monitoring/grafana_dashboards: Dashboard builder
- optimization/rag_hnsw_optimizer: HNSW optimization, QueryCache
"""

import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# security/identity_normalization
# ---------------------------------------------------------------------------

class TestIdentityNormalization:
    def test_normalize_identity_lowercase(self):
        from src.security.identity_normalization import normalize_identity
        token, canonical = normalize_identity("Node-1")
        assert canonical == "node-1"
        assert isinstance(token, bytes)
        assert len(token) == 32

    def test_normalize_identity_already_lower(self):
        from src.security.identity_normalization import normalize_identity
        token, canonical = normalize_identity("my-node-01")
        assert canonical == "my-node-01"

    def test_normalize_empty_raises(self):
        from src.security.identity_normalization import normalize_identity
        with pytest.raises(ValueError, match="empty"):
            normalize_identity("")

    def test_normalize_invalid_chars_raises(self):
        from src.security.identity_normalization import normalize_identity
        with pytest.raises(ValueError, match="Invalid identifier"):
            normalize_identity("node@1")

    def test_validate_identifier_valid(self):
        from src.security.identity_normalization import validate_identifier
        assert validate_identifier("node-1") is True
        assert validate_identifier("my_node.01") is True
        assert validate_identifier("abc123") is True

    def test_validate_identifier_uppercase_rejected(self):
        from src.security.identity_normalization import validate_identifier
        assert validate_identifier("Node-1") is False

    def test_validate_identifier_empty(self):
        from src.security.identity_normalization import validate_identifier
        assert validate_identifier("") is False

    def test_enforce_lowercase_passes(self):
        from src.security.identity_normalization import enforce_lowercase_rule
        result = enforce_lowercase_rule("node-1")
        assert result == "node-1"

    def test_enforce_lowercase_raises(self):
        from src.security.identity_normalization import enforce_lowercase_rule
        with pytest.raises(ValueError, match="CVE-2020-12812"):
            enforce_lowercase_rule("Node-1")

    def test_constants(self):
        from src.security.identity_normalization import (
            X0TTA6BL4_IDENTIFIER, HIP3_14CIRZ_IDENTIFIER,
        )
        assert X0TTA6BL4_IDENTIFIER == "x0tta6bl4"
        assert HIP3_14CIRZ_IDENTIFIER == "hip3.14cirz"


# ---------------------------------------------------------------------------
# security/anti_meave_oracle
# ---------------------------------------------------------------------------

class TestAntiMeaveOracle:
    def test_capability_types(self):
        from src.security.anti_meave_oracle import CapabilityType
        assert CapabilityType.READ.value == "read"
        assert CapabilityType.ADMIN.value == "admin"
        assert CapabilityType.CRYPTO.value == "crypto"

    def test_threat_level_values(self):
        from src.security.anti_meave_oracle import ThreatLevel
        assert ThreatLevel.NONE.value == 0
        assert ThreatLevel.CRITICAL.value == 4

    def test_capability_not_expired(self):
        from src.security.anti_meave_oracle import Capability, CapabilityType
        cap = Capability(
            name="read-data",
            capability_type=CapabilityType.READ,
            expires_at=time.time() + 3600,
        )
        assert cap.is_expired() is False
        assert cap.is_valid() is True

    def test_capability_expired(self):
        from src.security.anti_meave_oracle import Capability, CapabilityType
        cap = Capability(
            name="read-data",
            capability_type=CapabilityType.READ,
            expires_at=time.time() - 1,
        )
        assert cap.is_expired() is True
        assert cap.is_valid() is False

    def test_capability_no_expiry(self):
        from src.security.anti_meave_oracle import Capability, CapabilityType
        cap = Capability(name="read-data", capability_type=CapabilityType.READ)
        assert cap.is_expired() is False

    def test_capability_can_affect_nodes(self):
        from src.security.anti_meave_oracle import Capability, CapabilityType
        cap = Capability(
            name="write-data",
            capability_type=CapabilityType.WRITE,
            max_affected_nodes=5,
            max_affected_percentage=0.1,
        )
        assert cap.can_affect_nodes(3, 100) is True
        assert cap.can_affect_nodes(10, 100) is False
        assert cap.can_affect_nodes(5, 100) is True

    def test_agent_profile(self):
        from src.security.anti_meave_oracle import AgentProfile
        profile = AgentProfile(agent_id="agent-1", swarm_id="swarm-1")
        assert profile.actions_taken == 0
        assert profile.threat_score == 0.0
        profile.record_action(["node-1", "node-2"])
        assert profile.actions_taken == 1
        assert "node-1" in profile.nodes_affected

    def test_threat_alert(self):
        from src.security.anti_meave_oracle import ThreatAlert, ThreatLevel
        alert = ThreatAlert(
            alert_id="alert-1",
            agent_id="agent-1",
            threat_level=ThreatLevel.HIGH,
            description="Suspicious activity",
        )
        assert alert.resolved is False
        assert alert.threat_level == ThreatLevel.HIGH


# ---------------------------------------------------------------------------
# security/policy_decision_adapter
# ---------------------------------------------------------------------------

class TestPolicyDecisionAdapter:
    def test_policy_allowed_dict_allow(self):
        from src.security.policy_decision_adapter import policy_allowed
        assert policy_allowed({"allowed": True}) is True
        assert policy_allowed({"allowed": False}) is False

    def test_policy_allowed_dict_effect(self):
        from src.security.policy_decision_adapter import policy_allowed
        assert policy_allowed({"effect": "allow"}) is True
        assert policy_allowed({"effect": "deny"}) is False
        assert policy_allowed({"effect": "audit"}) is True
        assert policy_allowed({"effect": "challenge"}) is False

    def test_policy_allowed_object(self):
        from src.security.policy_decision_adapter import policy_allowed
        obj = MagicMock()
        obj.allowed = True
        assert policy_allowed(obj) is True
        obj.allowed = False
        assert policy_allowed(obj) is False

    def test_policy_allowed_none(self):
        from src.security.policy_decision_adapter import policy_allowed
        assert policy_allowed(None) is False

    def test_policy_allowed_string(self):
        from src.security.policy_decision_adapter import policy_allowed
        # Strings without attributes fall through to bool()
        assert policy_allowed("allow") is True
        assert policy_allowed("deny") is True  # bool("deny") == True
        assert policy_allowed("") is False

    def test_policy_reason_dict(self):
        from src.security.policy_decision_adapter import policy_reason
        assert policy_reason({"reason": "trusted"}) == "trusted"
        assert policy_reason({"detail": "blocked"}) == "blocked"
        assert policy_reason({}) == ""

    def test_policy_reason_object(self):
        from src.security.policy_decision_adapter import policy_reason
        obj = MagicMock()
        obj.reason = "policy violation"
        assert policy_reason(obj) == "policy violation"

    def test_policy_rules_dict(self):
        from src.security.policy_decision_adapter import policy_rules
        assert policy_rules({"matched_rules": ["r1", "r2"]}) == ["r1", "r2"]
        assert policy_rules({"rules": ["r1"]}) == ["r1"]
        assert policy_rules({"rule_id": "r1"}) == ["r1"]

    def test_policy_rules_object(self):
        from src.security.policy_decision_adapter import policy_rules
        obj = MagicMock()
        obj.matched_rules = ["rule-1"]
        assert policy_rules(obj) == ["rule-1"]


# ---------------------------------------------------------------------------
# monitoring/advanced_sla_metrics
# ---------------------------------------------------------------------------

class TestAdvancedSLAMetrics:
    def test_metric_type_values(self):
        from src.monitoring.advanced_sla_metrics import MetricType
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.HISTOGRAM.value == "histogram"

    def test_sla_status_values(self):
        from src.monitoring.advanced_sla_metrics import SLAStatus
        assert SLAStatus.HEALTHY.value == "healthy"
        assert SLAStatus.VIOLATION.value == "violation"

    def test_custom_metric_dataclass(self):
        from src.monitoring.advanced_sla_metrics import CustomMetric, MetricType
        metric = CustomMetric(
            name="api_latency",
            metric_type=MetricType.HISTOGRAM,
            unit="ms",
            description="API response latency",
        )
        assert metric.name == "api_latency"
        assert metric.metric_type == MetricType.HISTOGRAM

    def test_custom_metric_value(self):
        from src.monitoring.advanced_sla_metrics import CustomMetricValue
        value = CustomMetricValue(
            metric_name="api_latency",
            value=45.2,
            labels={"endpoint": "/api/v1"},
        )
        assert value.value == 45.2
        assert value.labels["endpoint"] == "/api/v1"

    def test_safe_hash(self):
        from src.monitoring.advanced_sla_metrics import _safe_hash
        assert _safe_hash("test") == _safe_hash("test")
        assert len(_safe_hash("test")) == 12

    def test_safe_count_bucket(self):
        from src.monitoring.advanced_sla_metrics import _safe_count_bucket
        assert _safe_count_bucket(0) == "0"
        assert _safe_count_bucket(5) == "4-10"
        assert _safe_count_bucket(200) == "100+"

    def test_safe_number_band(self):
        from src.monitoring.advanced_sla_metrics import _safe_number_band
        assert _safe_number_band("text") == "non_numeric"
        assert _safe_number_band(-1) == "negative"
        assert _safe_number_band(0) == "0"
        assert _safe_number_band(5) == "1-10"


# ---------------------------------------------------------------------------
# monitoring/alerting_rules
# ---------------------------------------------------------------------------

class TestAlertingRules:
    def test_alert_rule_severity_values(self):
        from src.monitoring.alerting_rules import AlertRuleSeverity
        assert AlertRuleSeverity.INFO.value == "info"
        assert AlertRuleSeverity.CRITICAL.value == "critical"

    def test_alert_rule_dataclass(self):
        from src.monitoring.alerting_rules import AlertRule, AlertRuleSeverity
        rule = AlertRule(
            name="HighErrorRate",
            description="Error rate above 1%",
            severity=AlertRuleSeverity.WARNING,
            metric_name="http_errors",
            threshold=0.01,
            comparison="gt",
            duration="5m",
            labels={"team": "platform"},
            annotations={"summary": "High error rate"},
        )
        assert rule.name == "HighErrorRate"
        assert rule.enabled is True

    def test_alerting_rules_init(self):
        from src.monitoring.alerting_rules import AlertingRules
        rules = AlertingRules()
        assert len(rules.rules) > 0
        assert len(rules.routes) > 0
        assert len(rules.groups) > 0

    def test_alert_route(self):
        from src.monitoring.alerting_rules import AlertRoute
        route = AlertRoute(
            route_id="route-1",
            name="telegram-critical",
            match_labels={"severity": "critical"},
            receiver="telegram",
        )
        assert route.receiver == "telegram"

    def test_alert_group(self):
        from src.monitoring.alerting_rules import AlertGroup
        group = AlertGroup(
            group_id="group-1",
            name="security-alerts",
            match_labels={"category": "security"},
        )
        assert group.group_interval == "5m"

    def test_alert_suppression(self):
        from src.monitoring.alerting_rules import AlertSuppression
        suppression = AlertSuppression(
            suppression_id="sup-1",
            name="maintenance-window",
            match_labels={"environment": "staging"},
            duration="2h",
        )
        assert suppression.duration == "2h"


# ---------------------------------------------------------------------------
# monitoring/grafana_dashboards
# ---------------------------------------------------------------------------

class TestGrafanaDashboards:
    def test_panel_dataclass(self):
        from src.monitoring.grafana_dashboards import GrafanaPanel
        panel = GrafanaPanel(
            title="CPU Usage",
            type="gauge",
            targets=[{"expr": "cpu_percent", "refId": "A"}],
        )
        d = panel.to_dict()
        assert d["title"] == "CPU Usage"
        assert d["type"] == "gauge"

    def test_dashboard_builder(self):
        from src.monitoring.grafana_dashboards import GrafanaDashboardBuilder
        builder = GrafanaDashboardBuilder(
            title="System Health",
            uid="system-health",
            description="System health dashboard",
        )
        builder.add_variable("node", "Node", "label_values(up, node)")
        builder.add_row("Overview")
        builder.add_metric_gauge("CPU", "cpu_percent", unit="percent")

        dashboard = builder.build()
        assert dashboard["title"] == "System Health"
        assert dashboard["uid"] == "system-health"
        assert len(dashboard["panels"]) >= 2

    def test_builder_returns_self(self):
        from src.monitoring.grafana_dashboards import GrafanaDashboardBuilder
        builder = GrafanaDashboardBuilder("test", "test-uid")
        result = builder.add_row("Row 1")
        assert result is builder


# ---------------------------------------------------------------------------
# optimization/rag_hnsw_optimizer (additional)
# ---------------------------------------------------------------------------

class TestAdaptiveParameterTuner:
    def test_record_latency(self):
        from src.optimization.rag_hnsw_optimizer import AdaptiveParameterTuner
        tuner = AdaptiveParameterTuner()
        tuner.record_latency(10.0)
        tuner.record_latency(20.0)
        assert tuner.query_count == 2

    def test_p95_latency(self):
        from src.optimization.rag_hnsw_optimizer import AdaptiveParameterTuner
        tuner = AdaptiveParameterTuner()
        for i in range(100):
            tuner.record_latency(float(i))
        p95 = tuner.get_p95_latency()
        assert p95 >= 90

    def test_p99_latency(self):
        from src.optimization.rag_hnsw_optimizer import AdaptiveParameterTuner
        tuner = AdaptiveParameterTuner()
        for i in range(100):
            tuner.record_latency(float(i))
        p99 = tuner.get_p99_latency()
        assert p99 >= 95

    def test_adapt_parameters_insufficient_data(self):
        from src.optimization.rag_hnsw_optimizer import AdaptiveParameterTuner
        tuner = AdaptiveParameterTuner()
        params = tuner.adapt_parameters()
        assert params.ef_search == 50  # default

    def test_adapt_parameters_high_latency(self):
        from src.optimization.rag_hnsw_optimizer import AdaptiveParameterTuner
        tuner = AdaptiveParameterTuner()
        for _ in range(20):
            tuner.record_latency(200.0)  # High latency
        params = tuner.adapt_parameters(target_latency_ms=100)
        assert params.ef_search <= 50  # Should reduce


class TestQueryCache:
    def test_put_get(self):
        from src.optimization.rag_hnsw_optimizer import QueryCache
        cache = QueryCache(max_size=10)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"

    def test_miss(self):
        from src.optimization.rag_hnsw_optimizer import QueryCache
        cache = QueryCache()
        assert cache.get("nonexistent") is None
        assert cache.misses == 1

    def test_eviction(self):
        from src.optimization.rag_hnsw_optimizer import QueryCache
        cache = QueryCache(max_size=2)
        cache.put("k1", "v1")
        cache.put("k2", "v2")
        cache.put("k3", "v3")
        assert len(cache.cache) == 2

    def test_hit_rate(self):
        from src.optimization.rag_hnsw_optimizer import QueryCache
        cache = QueryCache()
        cache.put("k1", "v1")
        cache.get("k1")  # hit
        cache.get("k2")  # miss
        assert cache.hit_rate() == 0.5


class TestQueryRewriterRewrite:
    def test_rewrite_high_quality(self):
        from src.optimization.rag_hnsw_optimizer import QueryRewriter
        rw = QueryRewriter()
        assert rw.rewrite_for_performance("test query", 0.9) == "test query"

    def test_rewrite_low_quality(self):
        from src.optimization.rag_hnsw_optimizer import QueryRewriter
        rw = QueryRewriter()
        result = rw.rewrite_for_performance("test query here now", 0.3)
        # Low quality query gets shortened
        assert len(result) > 0
