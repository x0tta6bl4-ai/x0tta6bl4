"""
MAPE-K Module - Meta-Cognitive Self-Healing Cycle.

This package provides a decomposed implementation of the MAPE-K cycle
with meta-cognitive capabilities.

Components:
- models: Data classes and enums
- meta_planning: Phase 0 - Solution space mapping
- monitoring: Phase 1 - System and reasoning monitoring
- analysis: Phase 2 - Problem and reasoning analysis
- planning: Phase 3 - Solution planning
- execution: Phase 4 - Plan execution
- knowledge: Phase 5 - Knowledge accumulation
- coordinator: Cycle orchestration

Usage:
    from src.core.mape_k import (
        MAPEKCoordinator,
        MetaPlanner,
        MonitoringPhase,
        AnalysisPhase,
        PlanningPhase,
        ExecutionPhase,
        KnowledgePhase,
    )
    
    # Create phase components
    meta_planner = MetaPlanner(knowledge_base=kb, graphsage=gs)
    monitoring = MonitoringPhase(mape_k_loop=loop)
    analysis = AnalysisPhase(mape_k_loop=loop, knowledge_base=kb)
    planning = PlanningPhase(mape_k_loop=loop)
    execution = ExecutionPhase(mape_k_loop=loop)
    knowledge = KnowledgePhase(knowledge_base=kb)
    
    # Create coordinator
    coordinator = MAPEKCoordinator(
        meta_planner=meta_planner,
        monitoring=monitoring,
        analysis=analysis,
        planning=planning,
        execution=execution,
        knowledge=knowledge,
    )
    
    # Run cycle
    result = await coordinator.run_full_cycle(task)
"""

# Models
from .models import (
    ReasoningApproach,
    SolutionSpace,
    ReasoningPath,
    ReasoningMetrics,
    ReasoningAnalytics,
    ExecutionLogEntry,
    MAPEKCycleResult,
)

# Phase components
from .meta_planning import MetaPlanner
from .monitoring import MonitoringPhase
from .analysis import AnalysisPhase
from .planning import PlanningPhase
from .execution import ExecutionPhase
from .knowledge import KnowledgePhase

# Coordinator
from .coordinator import MAPEKCoordinator

__all__ = [
    # Models
    "ReasoningApproach",
    "SolutionSpace",
    "ReasoningPath",
    "ReasoningMetrics",
    "ReasoningAnalytics",
    "ExecutionLogEntry",
    "MAPEKCycleResult",
    # Phase components
    "MetaPlanner",
    "MonitoringPhase",
    "AnalysisPhase",
    "PlanningPhase",
    "ExecutionPhase",
    "KnowledgePhase",
    # Coordinator
    "MAPEKCoordinator",
]
