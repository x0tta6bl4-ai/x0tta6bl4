"""
ML Extensions for x0tta6bl4

RAG (Retrieval-Augmented Generation), LoRA (Low-Rank Adaptation),
Anomaly Detection, Smart Decision Making, and MLOps Integration.

Uses lazy loading to avoid heavy dependencies (torch, numpy, transformers) at import time.
"""

import importlib

# Map of public attributes to their submodules
_LAZY_MAPPING = {
    "RAGAnalyzer": ".rag",
    "VectorStore": ".rag",
    "Document": ".rag",
    "LoRAAdapter": ".lora",
    "LoRAConfig": ".lora",
    "Anomaly": ".anomaly",
    "AnomalyDetectionSystem": ".anomaly",
    "NeuralAnomalyDetector": ".anomaly",
    "DecisionEngine": ".decision",
    "Policy": ".decision",
    "PolicyPriority": ".decision",
    "PolicyRanker": ".decision",
    "MLOpsManager": ".mlops",
    "ModelRegistry": ".mlops",
    "PerformanceMonitor": ".mlops",
    "RetrainingOrchestrator": ".mlops",
}

def __getattr__(name):
    if name in _LAZY_MAPPING:
        submodule_name = _LAZY_MAPPING[name]
        try:
            module = importlib.import_module(submodule_name, __package__)
            return getattr(module, name)
        except ImportError:
            # Fallback to stubs if production version fails to load
            if "RAG" in name or "Vector" in name or name == "Document":
                try:
                    module = importlib.import_module(".rag_stub", __package__)
                    return getattr(module, name)
                except (ImportError, AttributeError):
                    pass
            
            # Generic stub fallback for other classes
            class Stub:
                def __init__(self, *args, **kwargs): pass
            if name == "PolicyPriority":
                class PolicyPriority:
                    HIGH = "high"; MEDIUM = "medium"; LOW = "low"
                return PolicyPriority
            return Stub

    if name == "ml":
        # Handle the legacy recursive import from src/__init__.py if needed
        from . import anomaly, decision, lora, mlops, rag
        return None # This is just to satisfy the import mechanism

    # Standard version import
    if name == "__version__":
        from src.version import __version__
        return __version__

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = list(_LAZY_MAPPING.keys())
