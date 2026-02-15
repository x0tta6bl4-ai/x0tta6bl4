"""
Production-ready Alerting Rules for x0tta6bl4

Defines comprehensive alerting rules for:
- Error rates
- Latency
- Resource utilization
- Security events
- MAPE-K cycles
- Mesh network
- SPIFFE/SPIRE
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class AlertRuleSeverity(Enum):
    """Alert rule severity levels"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AlertRule:
    """Alert rule definition"""

    name: str
    description: str
    severity: AlertRuleSeverity
    metric_name: str
    threshold: float
    comparison: str  # "gt", "lt", "eq", "gte", "lte"
    duration: str  # Duration string (e.g., "5m", "1h")
    labels: Dict[str, str]
    annotations: Dict[str, str]
    runbook_url: Optional[str] = None
    enabled: bool = True


@dataclass
class AlertRoute:
    """Alert routing configuration"""

    route_id: str
    name: str
    match_labels: Dict[str, str]  # Labels to match
    receiver: str  # Receiver name (e.g., "telegram", "pagerduty", "slack")
    enabled: bool = True


@dataclass
class AlertGroup:
    """Alert grouping configuration"""

    group_id: str
    name: str
    match_labels: Dict[str, str]  # Labels to group by
    group_interval: str = "5m"  # How long to wait before grouping
    repeat_interval: str = "12h"  # How long to wait before repeating
    enabled: bool = True


@dataclass
class AlertSuppression:
    """Alert suppression configuration"""

    suppression_id: str
    name: str
    match_labels: Dict[str, str]  # Labels to suppress
    duration: str = "1h"  # Suppression duration
    enabled: bool = True
    expires_at: Optional[datetime] = None


class AlertingRules:
    """
    Production-ready alerting rules for x0tta6bl4.

    Provides comprehensive alerting rules for all system components with:
    - Custom alert rules
    - Alert routing
    - Alert grouping
    - Alert suppression
    """

    def __init__(self):
        self.rules: List[AlertRule] = []
        self.custom_rules: Dict[str, AlertRule] = {}  # Custom user-defined rules
        self.routes: List[AlertRoute] = []
        self.groups: List[AlertGroup] = []
        self.suppressions: List[AlertSuppression] = []

        self._load_default_rules()
        self._load_default_routes()
        self._load_default_groups()

        logger.info(
            f"AlertingRules initialized with {len(self.rules)} rules, {len(self.routes)} routes, {len(self.groups)} groups"
        )

    def _load_default_rules(self):
        """Load default production-ready alerting rules"""

        # Error Rate Rules
        self.rules.extend(
            [
                AlertRule(
                    name="HighErrorRate",
                    description="Error rate is above 1%",
                    severity=AlertRuleSeverity.WARNING,
                    metric_name="http_requests_total{status=~'5..'}",
                    threshold=0.01,  # 1%
                    comparison="gt",
                    duration="5m",
                    labels={"component": "http", "severity": "warning"},
                    annotations={
                        "summary": "High error rate detected",
                        "description": "Error rate is {{ $value | humanizePercentage }} (threshold: 1%)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#high-error-rate",
                    },
                    runbook_url="docs/operations/RUNBOOKS_COMPLETE.md#проблема-высокая-загрузка-cpu-90",
                ),
                AlertRule(
                    name="CriticalErrorRate",
                    description="Error rate is above 5%",
                    severity=AlertRuleSeverity.CRITICAL,
                    metric_name="http_requests_total{status=~'5..'}",
                    threshold=0.05,  # 5%
                    comparison="gt",
                    duration="2m",
                    labels={"component": "http", "severity": "critical"},
                    annotations={
                        "summary": "Critical error rate detected",
                        "description": "Error rate is {{ $value | humanizePercentage }} (threshold: 5%)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#critical-error-rate",
                    },
                ),
            ]
        )

        # Latency Rules
        self.rules.extend(
            [
                AlertRule(
                    name="HighLatencyP95",
                    description="P95 latency is above 150ms",
                    severity=AlertRuleSeverity.WARNING,
                    metric_name="http_request_duration_seconds{quantile='0.95'}",
                    threshold=0.15,  # 150ms
                    comparison="gt",
                    duration="5m",
                    labels={"component": "http", "severity": "warning"},
                    annotations={
                        "summary": "High latency detected",
                        "description": "P95 latency is {{ $value | humanizeDuration }} (threshold: 150ms)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#high-latency",
                    },
                ),
                AlertRule(
                    name="CriticalLatencyP95",
                    description="P95 latency is above 200ms",
                    severity=AlertRuleSeverity.CRITICAL,
                    metric_name="http_request_duration_seconds{quantile='0.95'}",
                    threshold=0.2,  # 200ms
                    comparison="gt",
                    duration="2m",
                    labels={"component": "http", "severity": "critical"},
                    annotations={
                        "summary": "Critical latency detected",
                        "description": "P95 latency is {{ $value | humanizeDuration }} (threshold: 200ms)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#critical-latency",
                    },
                ),
            ]
        )

        # Resource Utilization Rules
        self.rules.extend(
            [
                AlertRule(
                    name="HighCPUUsage",
                    description="CPU usage is above 90%",
                    severity=AlertRuleSeverity.WARNING,
                    metric_name="node_cpu_usage_percent",
                    threshold=90.0,
                    comparison="gt",
                    duration="5m",
                    labels={"component": "resource", "severity": "warning"},
                    annotations={
                        "summary": "High CPU usage",
                        "description": "CPU usage is {{ $value }}% (threshold: 90%)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#high-cpu",
                    },
                ),
                AlertRule(
                    name="HighMemoryUsage",
                    description="Memory usage is above 85%",
                    severity=AlertRuleSeverity.WARNING,
                    metric_name="node_memory_usage_percent",
                    threshold=85.0,
                    comparison="gt",
                    duration="5m",
                    labels={"component": "resource", "severity": "warning"},
                    annotations={
                        "summary": "High memory usage",
                        "description": "Memory usage is {{ $value }}% (threshold: 85%)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#high-memory",
                    },
                ),
            ]
        )

        # Security Rules
        self.rules.extend(
            [
                AlertRule(
                    name="PQCHandshakeFailure",
                    description="PQC handshake failure detected",
                    severity=AlertRuleSeverity.CRITICAL,
                    metric_name="pqc_handshake_failures_total",
                    threshold=1.0,
                    comparison="gt",
                    duration="1m",
                    labels={"component": "security", "severity": "critical"},
                    annotations={
                        "summary": "PQC handshake failure",
                        "description": "PQC handshake failed: {{ $labels.reason }}",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#pqc-failure",
                    },
                ),
                AlertRule(
                    name="PQCFallbackEnabled",
                    description="PQC fallback mode enabled",
                    severity=AlertRuleSeverity.CRITICAL,
                    metric_name="pqc_fallback_enabled",
                    threshold=1.0,
                    comparison="eq",
                    duration="1m",
                    labels={"component": "security", "severity": "critical"},
                    annotations={
                        "summary": "PQC fallback mode active",
                        "description": "System running in INSECURE fallback mode: {{ $labels.reason }}",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#pqc-fallback",
                    },
                ),
                AlertRule(
                    name="SPIFFEAuthFailure",
                    description="SPIFFE authentication failure",
                    severity=AlertRuleSeverity.ERROR,
                    metric_name="spire_auth_failure_total",
                    threshold=5.0,
                    comparison="gt",
                    duration="5m",
                    labels={"component": "security", "severity": "error"},
                    annotations={
                        "summary": "SPIFFE auth failures",
                        "description": "{{ $value }} SPIFFE authentication failures in last 5 minutes",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#spiffe-failure",
                    },
                ),
            ]
        )

        # MAPE-K Rules
        self.rules.extend(
            [
                AlertRule(
                    name="MAPEKCycleSlow",
                    description="MAPE-K cycle duration is above 5 seconds",
                    severity=AlertRuleSeverity.WARNING,
                    metric_name="mape_k_cycle_duration_seconds",
                    threshold=5.0,
                    comparison="gt",
                    duration="5m",
                    labels={"component": "mape_k", "severity": "warning"},
                    annotations={
                        "summary": "Slow MAPE-K cycle",
                        "description": "MAPE-K cycle duration is {{ $value }}s (threshold: 5s)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#mape-k-slow",
                    },
                ),
                AlertRule(
                    name="MAPEKRecoveryFailed",
                    description="MAPE-K recovery action failed",
                    severity=AlertRuleSeverity.ERROR,
                    metric_name="self_healing_events_total{success='false'}",
                    threshold=1.0,
                    comparison="gt",
                    duration="5m",
                    labels={"component": "mape_k", "severity": "error"},
                    annotations={
                        "summary": "MAPE-K recovery failed",
                        "description": "Recovery action failed: {{ $labels.action }}",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#mape-k-failure",
                    },
                ),
            ]
        )

        # Mesh Network Rules
        self.rules.extend(
            [
                AlertRule(
                    name="MeshNodeDown",
                    description="Mesh node is down",
                    severity=AlertRuleSeverity.ERROR,
                    metric_name="mesh_peers_count",
                    threshold=1.0,
                    comparison="lt",
                    duration="2m",
                    labels={"component": "mesh", "severity": "error"},
                    annotations={
                        "summary": "Mesh node down",
                        "description": "Mesh node {{ $labels.node_id }} is down",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#mesh-node-down",
                    },
                ),
                AlertRule(
                    name="HighPacketLoss",
                    description="Packet loss is above 5%",
                    severity=AlertRuleSeverity.WARNING,
                    metric_name="mesh_packet_loss_percent",
                    threshold=5.0,
                    comparison="gt",
                    duration="5m",
                    labels={"component": "mesh", "severity": "warning"},
                    annotations={
                        "summary": "High packet loss",
                        "description": "Packet loss is {{ $value }}% (threshold: 5%)",
                        "runbook_url": "https://docs.x0tta6bl4.com/runbooks#high-packet-loss",
                    },
                ),
            ]
        )

        logger.info(f"Loaded {len(self.rules)} default alerting rules")

    def get_rules(self, enabled_only: bool = True) -> List[AlertRule]:
        """Get all alerting rules"""
        if enabled_only:
            return [r for r in self.rules if r.enabled]
        return self.rules

    def get_rules_by_severity(self, severity: AlertRuleSeverity) -> List[AlertRule]:
        """Get rules by severity"""
        return [r for r in self.rules if r.severity == severity and r.enabled]

    def get_rules_by_component(self, component: str) -> List[AlertRule]:
        """Get rules by component"""
        return [
            r
            for r in self.rules
            if r.labels.get("component") == component and r.enabled
        ]

    def enable_rule(self, rule_name: str) -> bool:
        """Enable a rule"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = True
                logger.info(f"Enabled rule: {rule_name}")
                return True
        return False

    def disable_rule(self, rule_name: str) -> bool:
        """Disable a rule"""
        for rule in self.rules:
            if rule.name == rule_name:
                rule.enabled = False
                logger.info(f"Disabled rule: {rule_name}")
                return True
        return False

    def to_prometheus_rules(self) -> Dict[str, Any]:
        """
        Convert rules to Prometheus alerting rules format.

        Returns:
            Dict in Prometheus alerting rules format
        """
        groups = []

        # Group rules by component
        components = {}
        for rule in self.rules:
            if not rule.enabled:
                continue

            component = rule.labels.get("component", "general")
            if component not in components:
                components[component] = []
            components[component].append(rule)

        # Create groups
        for component, rules in components.items():
            alerts = []
            for rule in rules:
                alert = {
                    "alert": rule.name,
                    "expr": self._build_promql_expr(rule),
                    "for": rule.duration,
                    "labels": {**rule.labels, "severity": rule.severity.value},
                    "annotations": rule.annotations,
                }
                alerts.append(alert)

            groups.append(
                {"name": f"x0tta6bl4_{component}", "interval": "30s", "rules": alerts}
            )

        return {"groups": groups}

    def _build_promql_expr(self, rule: AlertRule) -> str:
        """Build PromQL expression for rule"""
        metric = (
            rule.metric_name.split("{")[0]
            if "{" in rule.metric_name
            else rule.metric_name
        )

        # Simple expression builder
        if rule.comparison == "gt":
            return f"{metric} > {rule.threshold}"
        elif rule.comparison == "lt":
            return f"{metric} < {rule.threshold}"
        elif rule.comparison == "gte":
            return f"{metric} >= {rule.threshold}"
        elif rule.comparison == "lte":
            return f"{metric} <= {rule.threshold}"
        elif rule.comparison == "eq":
            return f"{metric} == {rule.threshold}"
        else:
            return f"{metric} > {rule.threshold}"  # Default

    def add_custom_rule(self, rule: AlertRule) -> bool:
        """
        Add a custom alert rule.

        Args:
            rule: Custom alert rule to add

        Returns:
            True if rule added successfully
        """
        if rule.name in self.custom_rules:
            logger.warning(f"Custom rule {rule.name} already exists, updating")

        self.custom_rules[rule.name] = rule
        self.rules.append(rule)
        logger.info(f"Added custom alert rule: {rule.name}")
        return True

    def remove_custom_rule(self, rule_name: str) -> bool:
        """
        Remove a custom alert rule.

        Args:
            rule_name: Name of rule to remove

        Returns:
            True if rule removed
        """
        if rule_name in self.custom_rules:
            del self.custom_rules[rule_name]
            self.rules = [r for r in self.rules if r.name != rule_name]
            logger.info(f"Removed custom alert rule: {rule_name}")
            return True
        return False

    def _load_default_routes(self):
        """Load default alert routing configurations"""
        self.routes = [
            AlertRoute(
                route_id="critical_to_pagerduty",
                name="Critical to PagerDuty",
                match_labels={"severity": "critical"},
                receiver="pagerduty",
            ),
            AlertRoute(
                route_id="security_to_telegram",
                name="Security alerts to Telegram",
                match_labels={"component": "security"},
                receiver="telegram",
            ),
            AlertRoute(
                route_id="error_to_slack",
                name="Error alerts to Slack",
                match_labels={"severity": "error"},
                receiver="slack",
            ),
        ]
        logger.info(f"Loaded {len(self.routes)} default alert routes")

    def add_route(self, route: AlertRoute) -> bool:
        """
        Add an alert route.

        Args:
            route: Alert route to add

        Returns:
            True if route added
        """
        self.routes.append(route)
        logger.info(f"Added alert route: {route.name}")
        return True

    def get_route_for_alert(self, alert_labels: Dict[str, str]) -> Optional[AlertRoute]:
        """
        Get route for an alert based on labels.

        Args:
            alert_labels: Labels of the alert

        Returns:
            Matching AlertRoute or None
        """
        for route in self.routes:
            if not route.enabled:
                continue

            # Check if all match_labels are present in alert_labels
            if all(alert_labels.get(k) == v for k, v in route.match_labels.items()):
                return route

        return None

    def _load_default_groups(self):
        """Load default alert grouping configurations"""
        self.groups = [
            AlertGroup(
                group_id="by_component",
                name="Group by Component",
                match_labels={},  # Group all alerts
                group_interval="5m",
                repeat_interval="12h",
            ),
            AlertGroup(
                group_id="by_node",
                name="Group by Node",
                match_labels={"node_id": "*"},  # Group by node_id
                group_interval="2m",
                repeat_interval="6h",
            ),
        ]
        logger.info(f"Loaded {len(self.groups)} default alert groups")

    def add_group(self, group: AlertGroup) -> bool:
        """
        Add an alert group.

        Args:
            group: Alert group to add

        Returns:
            True if group added
        """
        self.groups.append(group)
        logger.info(f"Added alert group: {group.name}")
        return True

    def get_group_for_alert(self, alert_labels: Dict[str, str]) -> Optional[AlertGroup]:
        """
        Get group for an alert based on labels.

        Args:
            alert_labels: Labels of the alert

        Returns:
            Matching AlertGroup or None
        """
        for group in self.groups:
            if not group.enabled:
                continue

            # Check if match_labels match (supports wildcard *)
            matches = True
            for key, value in group.match_labels.items():
                if value == "*":
                    # Wildcard: just check if key exists
                    if key not in alert_labels:
                        matches = False
                        break
                else:
                    # Exact match
                    if alert_labels.get(key) != value:
                        matches = False
                        break

            if matches:
                return group

        return None

    def add_suppression(self, suppression: AlertSuppression) -> bool:
        """
        Add an alert suppression.

        Args:
            suppression: Alert suppression to add

        Returns:
            True if suppression added
        """
        # Parse duration and set expiry
        if suppression.duration:
            duration_seconds = self._parse_duration(suppression.duration)
            suppression.expires_at = datetime.now() + timedelta(
                seconds=duration_seconds
            )

        self.suppressions.append(suppression)
        logger.info(
            f"Added alert suppression: {suppression.name} (expires: {suppression.expires_at})"
        )
        return True

    def remove_suppression(self, suppression_id: str) -> bool:
        """
        Remove an alert suppression.

        Args:
            suppression_id: ID of suppression to remove

        Returns:
            True if suppression removed
        """
        initial_count = len(self.suppressions)
        self.suppressions = [
            s for s in self.suppressions if s.suppression_id != suppression_id
        ]
        removed = len(self.suppressions) < initial_count
        if removed:
            logger.info(f"Removed alert suppression: {suppression_id}")
        return removed

    def is_alert_suppressed(self, alert_labels: Dict[str, str]) -> bool:
        """
        Check if an alert should be suppressed.

        Args:
            alert_labels: Labels of the alert

        Returns:
            True if alert should be suppressed
        """
        now = datetime.now()

        # Remove expired suppressions
        self.suppressions = [
            s for s in self.suppressions if not s.expires_at or s.expires_at > now
        ]

        for suppression in self.suppressions:
            if not suppression.enabled:
                continue

            # Check if all match_labels are present in alert_labels
            if all(
                alert_labels.get(k) == v for k, v in suppression.match_labels.items()
            ):
                logger.debug(f"Alert suppressed by: {suppression.name}")
                return True

        return False

    def _parse_duration(self, duration_str: str) -> int:
        """
        Parse duration string to seconds.

        Args:
            duration_str: Duration string (e.g., "5m", "1h", "30s")

        Returns:
            Duration in seconds
        """
        if duration_str.endswith("s"):
            return int(duration_str[:-1])
        elif duration_str.endswith("m"):
            return int(duration_str[:-1]) * 60
        elif duration_str.endswith("h"):
            return int(duration_str[:-1]) * 3600
        elif duration_str.endswith("d"):
            return int(duration_str[:-1]) * 86400
        else:
            # Assume seconds
            return int(duration_str)

    def get_alerting_status(self) -> Dict[str, Any]:
        """Get alerting system status"""
        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules if r.enabled),
            "custom_rules": len(self.custom_rules),
            "routes": len(self.routes),
            "groups": len(self.groups),
            "active_suppressions": len(
                [
                    s
                    for s in self.suppressions
                    if not s.expires_at or s.expires_at > datetime.now()
                ]
            ),
        }


# Global instance
_alerting_rules: Optional[AlertingRules] = None


def get_alerting_rules() -> AlertingRules:
    """Get global alerting rules instance"""
    global _alerting_rules
    if _alerting_rules is None:
        _alerting_rules = AlertingRules()
    return _alerting_rules
