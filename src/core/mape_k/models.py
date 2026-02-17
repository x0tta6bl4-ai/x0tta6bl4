"""
Data models for Meta-Cognitive MAPE-K.

Contains all dataclasses and enums used across MAPE-K phases.
"""
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


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

    approaches: List[Dict[str, Any]] = field(default_factory=list)
    failure_history: List[Dict[str, Any]] = field(default_factory=list)
    success_probabilities: Dict[str, float] = field(default_factory=dict)
    selected_approach: Optional[str] = None
    reasoning: Optional[str] = None
    # Enhanced techniques
    hats_analysis: Optional[Dict[str, Any]] = None
    first_principles: Optional[Dict[str, Any]] = None
    reverse_plan: Optional[List[str]] = None


@dataclass
class ReasoningPath:
    """Plan for reasoning path."""

    first_step: str
    dead_ends_to_avoid: List[str] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
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
    end_time: Optional[float] = None


@dataclass
class ReasoningAnalytics:
    """Analytics for thinking process."""

    algorithm_used: str
    reasoning_time: float
    approaches_tried: int
    dead_ends: int
    breakthrough_moment: Optional[str] = None
    success: bool = False
    meta_insight: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionLogEntry:
    """Entry in execution log."""

    step: Dict[str, Any]
    result: Dict[str, Any]
    duration: float
    reasoning_approach: str
    meta_insights: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)


@dataclass
class MAPEKCycleResult:
    """Result of complete MAPE-K cycle."""

    meta_plan: Dict[str, Any]
    metrics: Dict[str, Any]
    analysis: Dict[str, Any]
    plan: Dict[str, Any]
    execution_log: Dict[str, Any]
    knowledge: Dict[str, Any]
    success: bool = True
    error: Optional[str] = None
