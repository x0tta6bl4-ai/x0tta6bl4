"""
ML Extensions for x0tta6bl4

RAG (Retrieval-Augmented Generation), LoRA (Low-Rank Adaptation),
Anomaly Detection, Smart Decision Making, and MLOps Integration.

Note: Uses lightweight stubs for staging environment to avoid heavy dependencies like torch, numpy
"""

# Try to import production versions, fall back to stubs for staging
try:
    from .rag import RAGAnalyzer, VectorStore, Document
except ImportError:
    from .rag_stub import RAGAnalyzer, VectorStore, Document

try:
    from .lora import LoRAAdapter, LoRAConfig
except ImportError:
    # Stub for LoRA
    class LoRAConfig:
        def __init__(self, *args, **kwargs): pass
    class LoRAAdapter:
        def __init__(self, *args, **kwargs): pass

try:
    from .anomaly import AnomalyDetectionSystem, NeuralAnomalyDetector, Anomaly
except ImportError:
    # Stubs for anomaly detection
    class Anomaly:
        def __init__(self, *args, **kwargs): pass
    class NeuralAnomalyDetector:
        def __init__(self, *args, **kwargs): pass
    class AnomalyDetectionSystem:
        def __init__(self, *args, **kwargs): pass

try:
    from .decision import DecisionEngine, PolicyRanker, Policy, PolicyPriority
except ImportError:
    # Stubs for decision engine
    class PolicyPriority:
        HIGH = "high"
        MEDIUM = "medium"
        LOW = "low"
    class Policy:
        def __init__(self, *args, **kwargs): pass
    class PolicyRanker:
        def __init__(self, *args, **kwargs): pass
    class DecisionEngine:
        def __init__(self, *args, **kwargs): pass

try:
    from .mlops import MLOpsManager, ModelRegistry, PerformanceMonitor, RetrainingOrchestrator
except ImportError:
    # Stubs for MLOps
    class ModelRegistry:
        def __init__(self, *args, **kwargs): pass
    class PerformanceMonitor:
        def __init__(self, *args, **kwargs): pass
    class RetrainingOrchestrator:
        def __init__(self, *args, **kwargs): pass
    class MLOpsManager:
        def __init__(self, *args, **kwargs): pass

__all__ = [
    # RAG
    "RAGAnalyzer",
    "VectorStore",
    "Document",
    # LoRA
    "LoRAAdapter",
    "LoRAConfig",
    # Anomaly Detection
    "AnomalyDetectionSystem",
    "NeuralAnomalyDetector",
    "Anomaly",
    # Decision Making
    "DecisionEngine",
    "PolicyRanker",
    "Policy",
    "PolicyPriority",
    # MLOps
    "MLOpsManager",
    "ModelRegistry",
    "PerformanceMonitor",
    "RetrainingOrchestrator",
]

__version__ = "3.3.0"
