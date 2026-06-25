"""
Data models for Meta-Cognitive MAPE-K.

Contains all dataclasses and enums used across MAPE-K phases.
"""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ReasoningApproach(Enum):
    """Approaches to reasoning."""

    MAPE_K_ONLY = "mape_k_only"
    RAG_SEARCH = "rag_search"
    GRAPHSAGE_PREDICTION = "graphsage_prediction"
    CAUSAL_ANALYSIS = "causal_analysis"
    COMBINED_RAG_GRAPHSAGE = "combined_rag_graphsage"
    COMBINED_ALL = "combined_all"


@dataclass
class SolutionSpace:
    """Map of solution space."""

    approaches: list[dict[str, Any]] = field(default_factory=list)
    failure_history: list[dict[str, Any]] = field(default_factory=list)
    success_probabilities: dict[str, float] = field(default_factory=dict)
    selected_approach: str | None = None
    reasoning: str | None = None
    # Enhanced techniques
    hats_analysis: dict[str, Any] | None = None
    first_principles: dict[str, Any] | None = None
    reverse_plan: list[str] | None = None


@dataclass
class ReasoningPath:
    """Plan for reasoning path."""

    first_step: str
    dead_ends_to_avoid: list[str] = field(default_factory=list)
    checkpoints: list[dict[str, Any]] = field(default_factory=list)
    estimated_time: float = 0.0


@dataclass
class ReasoningMetrics:
    """Metrics for thinking process."""

    reasoning_time: float = 0.0
    approaches_tried: int = 0
    dead_ends_encountered: int = 0
    confidence_level: float = 0.0
    knowledge_base_hits: int = 0
    cache_hit_rate: float = 0.0
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None


@dataclass
class ReasoningAnalytics:
    """Analytics for thinking process."""

    algorithm_used: str
    reasoning_time: float
    approaches_tried: int
    dead_ends: int
    breakthrough_moment: str | None = None
    success: bool = False
    meta_insight: dict[str, Any] | None = None


@dataclass
class ExecutionLogEntry:
    """Entry in execution log."""

    step: dict[str, Any]
    result: dict[str, Any]
    duration: float
    reasoning_approach: str
    meta_insights: dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class MAPEKCycleResult:
    """Result of complete MAPE-K cycle."""

    meta_plan: dict[str, Any]
    metrics: dict[str, Any]
    analysis: dict[str, Any]
    plan: dict[str, Any]
    execution_log: dict[str, Any]
    knowledge: dict[str, Any]
    success: bool = True
    error: str | None = None
