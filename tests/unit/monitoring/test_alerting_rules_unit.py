"""
Unit tests for src/monitoring/alerting_rules.py

Covers: AlertingRules, AlertRule, AlertRoute, AlertGroup, AlertSuppression,
        AlertRuleSeverity, get_alerting_rules, all public methods and edge cases.
"""

from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from src.monitoring.alerting_rules import (AlertGroup, AlertingRules,
                                           AlertRoute, AlertRule,
                                           AlertRuleSeverity, AlertSuppression,
                                           get_alerting_rules)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def alerting():
    """Fresh AlertingRules instance."""
    return AlertingRules()


@pytest.fixture
def sample_rule():
    """A minimal custom AlertRule for testing."""
    return AlertRule(
        name="TestRule",
        description="A test rule",
        severity=AlertRuleSeverity.WARNING,
        metric_name="test_metric",
        threshold=42.0,
        comparison="gt",
        duration="5m",
        labels={"component": "test", "severity": "warning"},
        annotations={"summary": "Test alert"},
    )


@pytest.fixture
def sample_route():
    return AlertRoute(
        route_id="test_route",
        name="Test Route",
        match_labels={"severity": "warning"},
        receiver="slack",
    )


@pytest.fixture
def sample_group():
    return AlertGroup(
        group_id="test_group",
        name="Test Group",
        match_labels={"component": "test"},
    )


@pytest.fixture
def sample_suppression():
    return AlertSuppression(
        suppression_id="test_suppression",
        name="Test Suppression",
        match_labels={"component": "test"},
        duration="1h",
    )


# ---------------------------------------------------------------------------
# AlertRuleSeverity enum
# ---------------------------------------------------------------------------


class TestAlertRuleSeverity:
    def test_severity_values(self):
        assert AlertRuleSeverity.INFO.value == "info"
        assert AlertRuleSeverity.WARNING.value == "warning"
        assert AlertRuleSeverity.ERROR.value == "error"
        assert AlertRuleSeverity.CRITICAL.value == "critical"

    def test_severity_count(self):
        assert len(AlertRuleSeverity) == 4


# ---------------------------------------------------------------------------
# Dataclass instantiation
# ---------------------------------------------------------------------------


class TestDataclasses:
    def test_alert_rule_defaults(self):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="m",
            threshold=1.0,
            comparison="gt",
            duration="1m",
            labels={},
            annotations={},
        )
        assert rule.runbook_url is None
        assert rule.enabled is True

    def test_alert_route_defaults(self):
        route = AlertRoute(route_id="id", name="n", match_labels={}, receiver="r")
        assert route.enabled is True

    def test_alert_group_defaults(self):
        group = AlertGroup(group_id="id", name="n", match_labels={})
        assert group.group_interval == "5m"
        assert group.repeat_interval == "12h"
        assert group.enabled is True

    def test_alert_suppression_defaults(self):
        sup = AlertSuppression(suppression_id="id", name="n", match_labels={})
        assert sup.duration == "1h"
        assert sup.enabled is True
        assert sup.expires_at is None


# ---------------------------------------------------------------------------
# AlertingRules initialisation
# ---------------------------------------------------------------------------


class TestAlertingRulesInit:
    def test_default_rules_loaded(self, alerting):
        assert len(alerting.rules) > 0

    def test_default_routes_loaded(self, alerting):
        assert len(alerting.routes) == 3

    def test_default_groups_loaded(self, alerting):
        assert len(alerting.groups) == 2

    def test_no_suppressions_on_init(self, alerting):
        assert len(alerting.suppressions) == 0

    def test_no_custom_rules_on_init(self, alerting):
        assert len(alerting.custom_rules) == 0

    def test_expected_default_rule_names(self, alerting):
        names = {r.name for r in alerting.rules}
        expected = {
            "HighErrorRate",
            "CriticalErrorRate",
            "HighLatencyP95",
            "CriticalLatencyP95",
            "HighCPUUsage",
            "HighMemoryUsage",
            "PQCHandshakeFailure",
            "PQCFallbackEnabled",
            "SPIFFEAuthFailure",
            "MAPEKCycleSlow",
            "MAPEKRecoveryFailed",
            "MeshNodeDown",
            "HighPacketLoss",
        }
        assert expected.issubset(names)


# ---------------------------------------------------------------------------
# get_rules
# ---------------------------------------------------------------------------


class TestGetRules:
    def test_get_rules_enabled_only(self, alerting):
        all_rules = alerting.get_rules(enabled_only=True)
        assert all(r.enabled for r in all_rules)

    def test_get_rules_all(self, alerting):
        alerting.rules[0].enabled = False
        all_rules = alerting.get_rules(enabled_only=False)
        assert any(not r.enabled for r in all_rules)

    def test_get_rules_excludes_disabled(self, alerting):
        alerting.rules[0].enabled = False
        enabled = alerting.get_rules(enabled_only=True)
        assert alerting.rules[0] not in enabled


# ---------------------------------------------------------------------------
# get_rules_by_severity
# ---------------------------------------------------------------------------


class TestGetRulesBySeverity:
    def test_warning_rules(self, alerting):
        rules = alerting.get_rules_by_severity(AlertRuleSeverity.WARNING)
        assert len(rules) > 0
        assert all(r.severity == AlertRuleSeverity.WARNING for r in rules)

    def test_critical_rules(self, alerting):
        rules = alerting.get_rules_by_severity(AlertRuleSeverity.CRITICAL)
        assert len(rules) > 0
        assert all(r.severity == AlertRuleSeverity.CRITICAL for r in rules)

    def test_excludes_disabled(self, alerting):
        # Disable all warning rules
        for r in alerting.rules:
            if r.severity == AlertRuleSeverity.WARNING:
                r.enabled = False
        rules = alerting.get_rules_by_severity(AlertRuleSeverity.WARNING)
        assert len(rules) == 0

    def test_info_returns_empty_by_default(self, alerting):
        rules = alerting.get_rules_by_severity(AlertRuleSeverity.INFO)
        assert len(rules) == 0


# ---------------------------------------------------------------------------
# get_rules_by_component
# ---------------------------------------------------------------------------


class TestGetRulesByComponent:
    def test_http_component(self, alerting):
        rules = alerting.get_rules_by_component("http")
        assert len(rules) > 0
        assert all(r.labels.get("component") == "http" for r in rules)

    def test_security_component(self, alerting):
        rules = alerting.get_rules_by_component("security")
        assert len(rules) > 0

    def test_mesh_component(self, alerting):
        rules = alerting.get_rules_by_component("mesh")
        assert len(rules) > 0

    def test_resource_component(self, alerting):
        rules = alerting.get_rules_by_component("resource")
        assert len(rules) > 0

    def test_mape_k_component(self, alerting):
        rules = alerting.get_rules_by_component("mape_k")
        assert len(rules) > 0

    def test_nonexistent_component(self, alerting):
        rules = alerting.get_rules_by_component("nonexistent")
        assert len(rules) == 0

    def test_excludes_disabled(self, alerting):
        for r in alerting.rules:
            if r.labels.get("component") == "http":
                r.enabled = False
        rules = alerting.get_rules_by_component("http")
        assert len(rules) == 0


# ---------------------------------------------------------------------------
# enable_rule / disable_rule
# ---------------------------------------------------------------------------


class TestEnableDisableRule:
    def test_disable_existing_rule(self, alerting):
        assert alerting.disable_rule("HighErrorRate") is True
        rule = next(r for r in alerting.rules if r.name == "HighErrorRate")
        assert rule.enabled is False

    def test_enable_disabled_rule(self, alerting):
        alerting.disable_rule("HighErrorRate")
        assert alerting.enable_rule("HighErrorRate") is True
        rule = next(r for r in alerting.rules if r.name == "HighErrorRate")
        assert rule.enabled is True

    def test_disable_nonexistent_rule(self, alerting):
        assert alerting.disable_rule("NoSuchRule") is False

    def test_enable_nonexistent_rule(self, alerting):
        assert alerting.enable_rule("NoSuchRule") is False

    def test_enable_already_enabled(self, alerting):
        # Should still return True
        assert alerting.enable_rule("HighErrorRate") is True


# ---------------------------------------------------------------------------
# add_custom_rule / remove_custom_rule
# ---------------------------------------------------------------------------


class TestCustomRules:
    def test_add_custom_rule(self, alerting, sample_rule):
        assert alerting.add_custom_rule(sample_rule) is True
        assert sample_rule.name in alerting.custom_rules
        assert sample_rule in alerting.rules

    def test_add_duplicate_custom_rule_updates(self, alerting, sample_rule):
        alerting.add_custom_rule(sample_rule)
        updated = AlertRule(
            name="TestRule",
            description="Updated",
            severity=AlertRuleSeverity.CRITICAL,
            metric_name="test_metric",
            threshold=99.0,
            comparison="lt",
            duration="10m",
            labels={"component": "test", "severity": "critical"},
            annotations={"summary": "Updated"},
        )
        assert alerting.add_custom_rule(updated) is True
        assert alerting.custom_rules["TestRule"].threshold == 99.0

    def test_remove_custom_rule(self, alerting, sample_rule):
        alerting.add_custom_rule(sample_rule)
        assert alerting.remove_custom_rule("TestRule") is True
        assert "TestRule" not in alerting.custom_rules
        assert all(r.name != "TestRule" for r in alerting.rules)

    def test_remove_nonexistent_custom_rule(self, alerting):
        assert alerting.remove_custom_rule("NoSuchRule") is False


# ---------------------------------------------------------------------------
# to_prometheus_rules
# ---------------------------------------------------------------------------


class TestToPrometheusRules:
    def test_returns_groups_key(self, alerting):
        result = alerting.to_prometheus_rules()
        assert "groups" in result

    def test_groups_have_expected_structure(self, alerting):
        result = alerting.to_prometheus_rules()
        for group in result["groups"]:
            assert "name" in group
            assert group["name"].startswith("x0tta6bl4_")
            assert "interval" in group
            assert "rules" in group

    def test_rules_have_expected_fields(self, alerting):
        result = alerting.to_prometheus_rules()
        for group in result["groups"]:
            for rule in group["rules"]:
                assert "alert" in rule
                assert "expr" in rule
                assert "for" in rule
                assert "labels" in rule
                assert "annotations" in rule

    def test_disabled_rules_excluded(self, alerting):
        alerting.disable_rule("HighErrorRate")
        result = alerting.to_prometheus_rules()
        all_alert_names = []
        for group in result["groups"]:
            for rule in group["rules"]:
                all_alert_names.append(rule["alert"])
        assert "HighErrorRate" not in all_alert_names

    def test_all_disabled_returns_empty_groups(self, alerting):
        for r in alerting.rules:
            r.enabled = False
        result = alerting.to_prometheus_rules()
        assert result["groups"] == []

    def test_custom_rule_in_prometheus_output(self, alerting, sample_rule):
        alerting.add_custom_rule(sample_rule)
        result = alerting.to_prometheus_rules()
        all_alert_names = []
        for group in result["groups"]:
            for rule in group["rules"]:
                all_alert_names.append(rule["alert"])
        assert "TestRule" in all_alert_names


# ---------------------------------------------------------------------------
# _build_promql_expr
# ---------------------------------------------------------------------------


class TestBuildPromqlExpr:
    def test_gt_comparison(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="my_metric",
            threshold=10.0,
            comparison="gt",
            duration="1m",
            labels={},
            annotations={},
        )
        assert alerting._build_promql_expr(rule) == "my_metric > 10.0"

    def test_lt_comparison(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="my_metric",
            threshold=5.0,
            comparison="lt",
            duration="1m",
            labels={},
            annotations={},
        )
        assert alerting._build_promql_expr(rule) == "my_metric < 5.0"

    def test_gte_comparison(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="my_metric",
            threshold=5.0,
            comparison="gte",
            duration="1m",
            labels={},
            annotations={},
        )
        assert alerting._build_promql_expr(rule) == "my_metric >= 5.0"

    def test_lte_comparison(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="my_metric",
            threshold=5.0,
            comparison="lte",
            duration="1m",
            labels={},
            annotations={},
        )
        assert alerting._build_promql_expr(rule) == "my_metric <= 5.0"

    def test_eq_comparison(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="my_metric",
            threshold=1.0,
            comparison="eq",
            duration="1m",
            labels={},
            annotations={},
        )
        assert alerting._build_promql_expr(rule) == "my_metric == 1.0"

    def test_unknown_comparison_defaults_to_gt(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="my_metric",
            threshold=1.0,
            comparison="unknown",
            duration="1m",
            labels={},
            annotations={},
        )
        assert alerting._build_promql_expr(rule) == "my_metric > 1.0"

    def test_metric_with_labels_strips_labels(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="http_requests_total{status=~'5..'}",
            threshold=0.01,
            comparison="gt",
            duration="1m",
            labels={},
            annotations={},
        )
        expr = alerting._build_promql_expr(rule)
        assert expr == "http_requests_total > 0.01"

    def test_metric_without_labels_unchanged(self, alerting):
        rule = AlertRule(
            name="r",
            description="d",
            severity=AlertRuleSeverity.INFO,
            metric_name="simple_metric",
            threshold=1.0,
            comparison="gt",
            duration="1m",
            labels={},
            annotations={},
        )
        expr = alerting._build_promql_expr(rule)
        assert expr == "simple_metric > 1.0"


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


class TestRoutes:
    def test_add_route(self, alerting, sample_route):
        initial = len(alerting.routes)
        assert alerting.add_route(sample_route) is True
        assert len(alerting.routes) == initial + 1

    def test_get_route_for_alert_matches(self, alerting):
        # Default route: critical -> pagerduty
        route = alerting.get_route_for_alert({"severity": "critical"})
        assert route is not None
        assert route.receiver == "pagerduty"

    def test_get_route_for_alert_security(self, alerting):
        route = alerting.get_route_for_alert(
            {"component": "security", "severity": "error"}
        )
        assert route is not None
        # security route should match first (it's second in the list but severity=critical is first)
        # Actually the first route checks severity=critical which doesn't match error
        assert route.receiver == "telegram"

    def test_get_route_no_match(self, alerting):
        route = alerting.get_route_for_alert(
            {"component": "unknown", "severity": "info"}
        )
        assert route is None

    def test_disabled_route_skipped(self, alerting):
        for r in alerting.routes:
            r.enabled = False
        route = alerting.get_route_for_alert({"severity": "critical"})
        assert route is None

    def test_route_match_requires_all_labels(self, alerting):
        # Add route that needs two labels
        route = AlertRoute(
            route_id="multi",
            name="Multi",
            match_labels={"severity": "critical", "component": "security"},
            receiver="email",
        )
        alerting.add_route(route)
        # Only one label present - should not match this route but may match earlier ones
        result = alerting.get_route_for_alert({"severity": "critical"})
        # Should match the first default critical route, not our multi-label route
        assert result.route_id == "critical_to_pagerduty"

    def test_route_partial_match_not_returned(self, alerting):
        # Clear default routes, add one that needs two labels
        alerting.routes = [
            AlertRoute(
                route_id="multi",
                name="Multi",
                match_labels={"severity": "critical", "component": "security"},
                receiver="email",
            )
        ]
        result = alerting.get_route_for_alert({"severity": "critical"})
        assert result is None


# ---------------------------------------------------------------------------
# Groups
# ---------------------------------------------------------------------------


class TestGroups:
    def test_add_group(self, alerting, sample_group):
        initial = len(alerting.groups)
        assert alerting.add_group(sample_group) is True
        assert len(alerting.groups) == initial + 1

    def test_get_group_for_alert_empty_match(self, alerting):
        # First default group has empty match_labels, matches everything
        group = alerting.get_group_for_alert({"component": "http"})
        assert group is not None
        assert group.group_id == "by_component"

    def test_get_group_wildcard_match(self, alerting):
        # Remove the first catch-all group
        alerting.groups = [g for g in alerting.groups if g.group_id != "by_component"]
        group = alerting.get_group_for_alert({"node_id": "node-1"})
        assert group is not None
        assert group.group_id == "by_node"

    def test_get_group_wildcard_missing_key(self, alerting):
        alerting.groups = [g for g in alerting.groups if g.group_id != "by_component"]
        # no node_id in labels
        group = alerting.get_group_for_alert({"component": "http"})
        assert group is None

    def test_disabled_group_skipped(self, alerting):
        for g in alerting.groups:
            g.enabled = False
        group = alerting.get_group_for_alert({"component": "http"})
        assert group is None

    def test_exact_match_group(self, alerting):
        alerting.groups = [
            AlertGroup(
                group_id="exact",
                name="Exact",
                match_labels={"component": "security"},
            )
        ]
        assert alerting.get_group_for_alert({"component": "security"}) is not None
        assert alerting.get_group_for_alert({"component": "http"}) is None


# ---------------------------------------------------------------------------
# Suppressions
# ---------------------------------------------------------------------------


class TestSuppressions:
    def test_add_suppression_sets_expires_at(self, alerting, sample_suppression):
        alerting.add_suppression(sample_suppression)
        assert sample_suppression.expires_at is not None
        assert sample_suppression.expires_at > datetime.now()

    def test_suppression_in_list_after_add(self, alerting, sample_suppression):
        alerting.add_suppression(sample_suppression)
        assert len(alerting.suppressions) == 1

    def test_remove_suppression(self, alerting, sample_suppression):
        alerting.add_suppression(sample_suppression)
        assert alerting.remove_suppression("test_suppression") is True
        assert len(alerting.suppressions) == 0

    def test_remove_nonexistent_suppression(self, alerting):
        assert alerting.remove_suppression("nonexistent") is False

    def test_is_alert_suppressed_true(self, alerting, sample_suppression):
        alerting.add_suppression(sample_suppression)
        assert alerting.is_alert_suppressed({"component": "test"}) is True

    def test_is_alert_suppressed_false(self, alerting, sample_suppression):
        alerting.add_suppression(sample_suppression)
        assert alerting.is_alert_suppressed({"component": "other"}) is False

    def test_is_alert_suppressed_no_suppressions(self, alerting):
        assert alerting.is_alert_suppressed({"component": "test"}) is False

    def test_expired_suppression_cleaned_up(self, alerting):
        sup = AlertSuppression(
            suppression_id="expired",
            name="Expired",
            match_labels={"component": "test"},
            duration="1h",
        )
        sup.expires_at = datetime.now() - timedelta(hours=1)
        alerting.suppressions.append(sup)
        # Calling is_alert_suppressed should clean up expired
        assert alerting.is_alert_suppressed({"component": "test"}) is False
        assert len(alerting.suppressions) == 0

    def test_disabled_suppression_not_applied(self, alerting):
        sup = AlertSuppression(
            suppression_id="disabled",
            name="Disabled",
            match_labels={"component": "test"},
            duration="1h",
            enabled=False,
        )
        sup.expires_at = datetime.now() + timedelta(hours=1)
        alerting.suppressions.append(sup)
        assert alerting.is_alert_suppressed({"component": "test"}) is False

    def test_suppression_without_expires_at_persists(self, alerting):
        sup = AlertSuppression(
            suppression_id="no_expiry",
            name="No Expiry",
            match_labels={"component": "test"},
            duration="1h",
        )
        # Manually set expires_at to None to test path
        sup.expires_at = None
        alerting.suppressions.append(sup)
        assert alerting.is_alert_suppressed({"component": "test"}) is True

    def test_add_suppression_with_empty_duration(self, alerting):
        sup = AlertSuppression(
            suppression_id="empty_dur",
            name="Empty Duration",
            match_labels={"component": "test"},
            duration="",
        )
        # Empty string is falsy, so no expires_at set
        alerting.add_suppression(sup)
        assert sup.expires_at is None


# ---------------------------------------------------------------------------
# _parse_duration
# ---------------------------------------------------------------------------


class TestParseDuration:
    def test_seconds(self, alerting):
        assert alerting._parse_duration("30s") == 30

    def test_minutes(self, alerting):
        assert alerting._parse_duration("5m") == 300

    def test_hours(self, alerting):
        assert alerting._parse_duration("2h") == 7200

    def test_days(self, alerting):
        assert alerting._parse_duration("1d") == 86400

    def test_plain_number_treated_as_seconds(self, alerting):
        assert alerting._parse_duration("120") == 120

    def test_large_duration(self, alerting):
        assert alerting._parse_duration("365d") == 365 * 86400


# ---------------------------------------------------------------------------
# get_alerting_status
# ---------------------------------------------------------------------------


class TestGetAlertingStatus:
    def test_status_keys(self, alerting):
        status = alerting.get_alerting_status()
        assert "total_rules" in status
        assert "enabled_rules" in status
        assert "custom_rules" in status
        assert "routes" in status
        assert "groups" in status
        assert "active_suppressions" in status

    def test_status_values_on_init(self, alerting):
        status = alerting.get_alerting_status()
        assert status["total_rules"] == len(alerting.rules)
        assert status["enabled_rules"] == len(alerting.rules)  # All enabled by default
        assert status["custom_rules"] == 0
        assert status["routes"] == 3
        assert status["groups"] == 2
        assert status["active_suppressions"] == 0

    def test_status_after_modifications(
        self, alerting, sample_rule, sample_suppression
    ):
        alerting.add_custom_rule(sample_rule)
        alerting.disable_rule("HighErrorRate")
        alerting.add_suppression(sample_suppression)
        status = alerting.get_alerting_status()
        assert status["custom_rules"] == 1
        assert status["enabled_rules"] == status["total_rules"] - 1
        assert status["active_suppressions"] == 1

    def test_status_expired_suppression_not_counted(self, alerting):
        sup = AlertSuppression(
            suppression_id="expired",
            name="Expired",
            match_labels={},
            duration="1h",
        )
        sup.expires_at = datetime.now() - timedelta(hours=1)
        alerting.suppressions.append(sup)
        status = alerting.get_alerting_status()
        assert status["active_suppressions"] == 0


# ---------------------------------------------------------------------------
# get_alerting_rules (global singleton)
# ---------------------------------------------------------------------------


class TestGetAlertingRulesGlobal:
    def test_returns_alerting_rules_instance(self):
        with patch("src.monitoring.alerting_rules._alerting_rules", None):
            result = get_alerting_rules()
            assert isinstance(result, AlertingRules)

    def test_returns_same_instance(self):
        with patch("src.monitoring.alerting_rules._alerting_rules", None):
            first = get_alerting_rules()
            # Patch the global to the instance we just got
            with patch("src.monitoring.alerting_rules._alerting_rules", first):
                second = get_alerting_rules()
                assert first is second

    def test_uses_existing_instance(self):
        existing = AlertingRules()
        with patch("src.monitoring.alerting_rules._alerting_rules", existing):
            result = get_alerting_rules()
            assert result is existing


# ---------------------------------------------------------------------------
# Edge cases / integration-style within unit
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_add_then_disable_custom_rule(self, alerting, sample_rule):
        alerting.add_custom_rule(sample_rule)
        alerting.disable_rule("TestRule")
        rules = alerting.get_rules(enabled_only=True)
        assert all(r.name != "TestRule" for r in rules)

    def test_remove_custom_rule_does_not_affect_defaults(self, alerting, sample_rule):
        default_count = len(alerting.rules)
        alerting.add_custom_rule(sample_rule)
        alerting.remove_custom_rule("TestRule")
        assert len(alerting.rules) == default_count

    def test_prometheus_rules_severity_in_labels(self, alerting):
        result = alerting.to_prometheus_rules()
        for group in result["groups"]:
            for rule in group["rules"]:
                assert "severity" in rule["labels"]

    def test_multiple_suppressions_first_match_wins(self, alerting):
        sup1 = AlertSuppression(
            suppression_id="s1",
            name="S1",
            match_labels={"component": "test"},
            duration="1h",
        )
        sup2 = AlertSuppression(
            suppression_id="s2",
            name="S2",
            match_labels={"component": "test", "severity": "critical"},
            duration="1h",
        )
        alerting.add_suppression(sup1)
        alerting.add_suppression(sup2)
        # Should be suppressed by s1 (broader match)
        assert alerting.is_alert_suppressed({"component": "test"}) is True

    def test_suppression_requires_all_labels_to_match(self, alerting):
        sup = AlertSuppression(
            suppression_id="s",
            name="S",
            match_labels={"component": "test", "severity": "critical"},
            duration="1h",
        )
        alerting.add_suppression(sup)
        # Only component matches, severity doesn't
        assert (
            alerting.is_alert_suppressed({"component": "test", "severity": "warning"})
            is False
        )
