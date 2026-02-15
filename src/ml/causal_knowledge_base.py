# Causal Knowledge Base
# Defines rules and heuristics for root cause analysis

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Callable, Any
from enum import Enum

class RootCauseType(Enum):
    """Root cause categories"""
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_DEGRADATION = "network_degradation"
    SERVICE_FAILURE = "service_failure"
    CONFIGURATION_ERROR = "configuration_error"
    EXTERNAL_INTERFERENCE = "external_interference"
    CASCADING_FAILURE = "cascading_failure"
    HARDWARE_FAILURE = "hardware_failure"
    DATABASE_ISSUE = "database_issue"
    SECURITY_INCIDENT = "security_incident"
    UNKNOWN = "unknown"

@dataclass
class CausalRule:
    """Rule for identifying a root cause"""
    rule_id: str
    name: str
    description: str
    cause_type: RootCauseType
    condition: Callable[[Dict[str, float]], bool]
    confidence_score: float
    explanation_template: str
    remediation_suggestions: List[str]
    required_metrics: List[str] = field(default_factory=list)

class CausalKnowledgeBase:
    """
    Knowledge Base containing rules for Causal Analysis.
    Centralizes heuristics to make them manageable and extensible.
    """
    
    def __init__(self):
        self.rules: List[CausalRule] = []
        self._initialize_default_rules()
        
    def _initialize_default_rules(self):
        """Initialize default set of heuristic rules"""
        
        # --- Resource Exhaustion ---
        self.rules.append(CausalRule(
            rule_id="cpu_critical",
            name="CPU Critical",
            description="CPU usage extremely high",
            cause_type=RootCauseType.RESOURCE_EXHAUSTION,
            condition=lambda m: m.get("cpu_percent", 0) > 95,
            confidence_score=0.95,
            explanation_template="CPU utilization is critical ({cpu_percent:.1f}%)",
            remediation_suggestions=[
                "Restart node to clear CPU load",
                "Identify and terminate CPU-heavy processes", 
                "Check for runaway loops"
            ],
            required_metrics=["cpu_percent"]
        ))
        
        self.rules.append(CausalRule(
            rule_id="cpu_high",
            name="CPU High",
            description="CPU usage high",
            cause_type=RootCauseType.RESOURCE_EXHAUSTION,
            condition=lambda m: 90 < m.get("cpu_percent", 0) <= 95,
            confidence_score=0.8,
            explanation_template="CPU utilization is high ({cpu_percent:.1f}%)",
            remediation_suggestions=["Monitor CPU usage", "Scale up if persistent"],
            required_metrics=["cpu_percent"]
        ))

        self.rules.append(CausalRule(
            rule_id="mem_critical",
            name="Memory Critical",
            description="Memory usage extremely high",
            cause_type=RootCauseType.RESOURCE_EXHAUSTION,
            condition=lambda m: m.get("memory_percent", 0) > 95,
            confidence_score=0.9,
            explanation_template="Memory utilization is critical ({memory_percent:.1f}%)",
            remediation_suggestions=[
                "Restart node to free memory",
                "Check for memory leaks",
                "Increase swap space or physical RAM"
            ],
            required_metrics=["memory_percent"]
        ))

        # --- Network Degradation ---
        self.rules.append(CausalRule(
            rule_id="packet_loss_high",
            name="High Packet Loss",
            description="Significant packet loss detected",
            cause_type=RootCauseType.NETWORK_DEGRADATION,
            condition=lambda m: m.get("loss_rate", 0) > 0.05,
            confidence_score=0.85,
            explanation_template="High packet loss rate ({loss_rate_pct:.1f}%)",
            remediation_suggestions=[
                "Check for RF interference",
                "Switch wireless channel",
                "Check physical links"
            ],
            required_metrics=["loss_rate"]
        ))
        
        self.rules.append(CausalRule(
            rule_id="latency_high",
            name="High Latency",
            description="Network latency is excessive",
            cause_type=RootCauseType.NETWORK_DEGRADATION,
            condition=lambda m: m.get("latency", 0) > 500,
            confidence_score=0.8,
            explanation_template="Network latency excessive ({latency:.0f}ms)",
            remediation_suggestions=[
                "Check for network congestion",
                "Review routing paths",
                "Prioritize traffic (QoS)"
            ],
            required_metrics=["latency"]
        ))

        self.rules.append(CausalRule(
            rule_id="signal_weak",
            name="Weak Signal",
            description="RSSI is very low",
            cause_type=RootCauseType.NETWORK_DEGRADATION,
            condition=lambda m: m.get("rssi", -50) < -85,
            confidence_score=0.75,
            explanation_template="Signal strength very weak ({rssi:.0f}dBm)",
            remediation_suggestions=[
                "Move node closer to AP",
                "Check antenna orientation",
                "Add relay node"
            ],
            required_metrics=["rssi"]
        ))

        # --- Database Issues (NEW) ---
        self.rules.append(CausalRule(
            rule_id="db_connections_max",
            name="DB Connection Pool Exhaustion",
            description="Database connection pool is full",
            cause_type=RootCauseType.DATABASE_ISSUE,
            condition=lambda m: m.get("db_active_connections", 0) >= m.get("db_max_connections", 100) * 0.95,
            confidence_score=0.9,
            explanation_template="Database connection pool exhausted ({db_active_connections}/{db_max_connections})",
            remediation_suggestions=[
                "Increase max_connections",
                "Check for connection leaks in app",
                "Implement connection pooling"
            ],
            required_metrics=["db_active_connections", "db_max_connections"]
        ))

        self.rules.append(CausalRule(
            rule_id="db_lock_wait",
            name="High DB Lock Wait",
            description="Database is spending too much time waiting for locks",
            cause_type=RootCauseType.DATABASE_ISSUE,
            condition=lambda m: m.get("db_lock_wait_time", 0) > 1000, # ms
            confidence_score=0.85,
            explanation_template="High database lock wait time ({db_lock_wait_time}ms)",
            remediation_suggestions=[
                "Identify long-running transactions",
                "Optimize queries causing contention",
                "Check for deadlocks"
            ],
            required_metrics=["db_lock_wait_time"]
        ))

        # --- Security Incidents (NEW) ---
        self.rules.append(CausalRule(
            rule_id="auth_failures_high",
            name="High Auth Failures",
            description="Spike in authentication failures indicating potential brute force",
            cause_type=RootCauseType.SECURITY_INCIDENT,
            condition=lambda m: m.get("auth_fail_rate", 0) > 10, # failures per minute/sec depending on metric
            confidence_score=0.8,
            explanation_template="High authentication failure rate ({auth_fail_rate}/sec)",
            remediation_suggestions=[
                "Check for brute force attack",
                "Verify auth service health",
                "Block offending IPs"
            ],
            required_metrics=["auth_fail_rate"]
        ))

    def evaluate(self, metrics: Dict[str, float]) -> List[Dict[str, Any]]:
        """
        Evaluate metrics against all rules.
        Returns a list of matched rule details.
        """
        matches = []
        for rule in self.rules:
            # Check if required metrics are present
            if not all(k in metrics for k in rule.required_metrics):
                continue
                
            try:
                if rule.condition(metrics):
                    # Format explanation
                    fmt_data = metrics.copy()
                    if "loss_rate" in fmt_data:
                        fmt_data["loss_rate_pct"] = fmt_data["loss_rate"] * 100
                    
                    explanation = rule.explanation_template.format(**fmt_data)
                    
                    matches.append({
                        "rule": rule,
                        "explanation": explanation,
                        "confidence": rule.confidence_score
                    })
            except Exception as e:
                # Log error but don't crash
                # logger.error(f"Error evaluating rule {rule.rule_id}: {e}")
                pass
                
        return matches

