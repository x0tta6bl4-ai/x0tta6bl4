"""Vision coding package."""
from __future__ import annotations
from .models import AnalysisType, BoundingBox, Issue, Severity, Style, Suggestion, VisualOverlay
from .graph import Graph, GraphNode, PathMetrics, BFSAlgorithm, AStarAlgorithm
from .cache import VisionCache
from .engine import VisionCodingEngine, analyze_maze, analyze_mesh_topology, detect_anomalies, get_vision_engine

__all__ = [
    "AnalysisType", "BoundingBox", "Issue", "Severity", "Style", "Suggestion", "VisualOverlay",
    "Graph", "GraphNode", "PathMetrics", "BFSAlgorithm", "AStarAlgorithm",
    "VisionCache", "VisionCodingEngine",
    "get_vision_engine", "analyze_maze", "analyze_mesh_topology", "detect_anomalies",
]
