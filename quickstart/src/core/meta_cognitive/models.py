"""
Models and Types for Meta-Cognitive MAPE-K.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ReasoningApproach(Enum):
    """Reasoning approaches for the meta-cognitive layer."""

    MAPE_K_ONLY = "mape_k_only"
    RAG_SEARCH = "rag_search"
    GRAPHSAGE_PREDICTION = "graphsage_prediction"
    CAUSAL_ANALYSIS = "causal_analysis"
    COMBINED_RAG_GRAPHSAGE = "combined_rag_graphsage"
    COMBINED_ALL = "combined_all"


@dataclass
class SolutionSpace:
    """Map of the solution space."""

    approaches: List[Dict[str, Any]] = field(default_factory=list)
    failure_history: List[Dict[str, Any]] = field(default_factory=list)
    success_probabilities: Dict[str, float] = field(default_factory=dict)
    selected_approach: Optional[str] = None
    reasoning: Optional[str] = None
    
    # Enhancements: thinking techniques results
    hats_analysis: Optional[Dict[str, Any]] = None
    first_principles: Optional[Dict[str, Any]] = None
    reverse_plan: Optional[List[str]] = None


@dataclass
class ReasoningPath:
    """Plan for the reasoning path."""

    first_step: str
    dead_ends_to_avoid: List[str] = field(default_factory=list)
    checkpoints: List[Dict[str, Any]] = field(default_factory=list)
    estimated_time: float = 0.0


@dataclass
class ReasoningMetrics:
    """Metrics for the thinking process."""

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
    """Analytics for the thinking process."""

    algorithm_used: str
    reasoning_time: float
    approaches_tried: int
    dead_ends: int
    breakthrough_moment: Optional[str] = None
    success: bool = False
    meta_insight: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionLogEntry:
    """Entry in the execution log."""

    step: Dict[str, Any]
    result: Dict[str, Any]
    duration: float
    reasoning_approach: str
    meta_insights: Dict[str, Any]
    timestamp: float = field(default_factory=time.time)

