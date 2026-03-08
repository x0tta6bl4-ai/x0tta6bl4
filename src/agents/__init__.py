# 🤖 AI Agents package for x0tta6bl4
"""
AI Agents for autonomous operations.

This package contains all AI agents for x0tta6bl4:
- Monitoring: Health Monitor, Log Analyzer
- Healing: Auto-Healer
- Development: Spec-to-Code, Documentation
- Orchestration: Agent Orchestrator
"""

# Orchestration
from src.agents.orchestration import (
    AgentOrchestrator,
    AgentStatus,
    get_orchestrator,
)

# Monitoring agents
from src.agents.monitoring import (
    Alert,
    AlertSeverity,
    HealthCheckResult,
    HealthMonitorAgent,
    HealthStatus,
    get_health_monitor,
)

# Logging agents
from src.agents.logging import (
    DetectedIssue,
    IssueSeverity,
    LogAnalyzerAgent,
    LogEntry,
    LogLevel,
    LogPattern,
    get_log_analyzer,
)

# Healing agents
from src.agents.healing import (
    AutoHealerAgent,
    HealingAction,
    HealingIncident,
    HealingMetrics,
    HealingStatus,
    get_auto_healer,
)

# Development agents
from src.agents.development import (
    DocumentationAgent,
    SpecToCodeAgent,
    CodeLanguage,
    CodeType,
    Specification,
    GeneratedCode,
    get_spec_to_code_agent,
    get_documentation_agent,
)

__all__ = [
    # Orchestration
    "AgentOrchestrator",
    "AgentStatus",
    "get_orchestrator",
    # Monitoring
    "Alert",
    "AlertSeverity", 
    "HealthCheckResult",
    "HealthMonitorAgent",
    "HealthStatus",
    "get_health_monitor",
    # Logging
    "DetectedIssue",
    "IssueSeverity",
    "LogAnalyzerAgent",
    "LogEntry",
    "LogLevel",
    "LogPattern",
    "get_log_analyzer",
    # Healing
    "AutoHealerAgent",
    "HealingAction",
    "HealingIncident",
    "HealingMetrics",
    "HealingStatus",
    "get_auto_healer",
    # Development
    "DocumentationAgent",
    "SpecToCodeAgent",
    "CodeLanguage",
    "CodeType",
    "Specification",
    "GeneratedCode",
    "get_spec_to_code_agent",
    "get_documentation_agent",
]

# Version
__version__ = "1.0.0"
