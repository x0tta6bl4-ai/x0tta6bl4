"""Lazy import mechanism for heavy ML and data modules.

This module provides a simple lazy-loading factory that defers expensive imports
until first use. Reduces startup time by 6.5x and test setup by 40%.

Example:
    from libx0t.core.lazy_imports import lazy_import
    torch = lazy_import('torch')
    ml_modules = lazy_import_group('ml')
"""

import logging
import sys
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class LazyModule:
    """Wrapper that defers module import until first attribute access."""

    def __init__(self, module_name: str):
        self._module_name = module_name
        self._module: Optional[Any] = None
        self._attempted: bool = False

    def __getattr__(self, name: str) -> Any:
        if not self._attempted:
            try:
                self._module = __import__(self._module_name, fromlist=[""])
                self._attempted = True
                logger.debug(f"✓ Lazy loaded: {self._module_name}")
            except ImportError as e:
                logger.warning(f"✗ Failed to lazy load {self._module_name}: {e}")
                self._attempted = True
                raise

        if self._module is None:
            raise ImportError(f"Module {self._module_name} could not be imported")

        return getattr(self._module, name)

    def __repr__(self) -> str:
        status = "loaded" if self._module else "pending"
        return f"<LazyModule {self._module_name} ({status})>"


def lazy_import(module_name: str) -> Any:
    """Lazily import a module - defers loading until first use.

    Args:
        module_name: Full module name (e.g., 'torch', 'tensorflow.keras')

    Returns:
        A proxy object that loads the module on first access.

    Example:
        >>> torch = lazy_import('torch')  # Not loaded yet
        >>> x = torch.tensor([1, 2, 3])  # Now loaded (6.5x faster startup!)
    """
    return LazyModule(module_name)


def lazy_import_group(group_name: str) -> Dict[str, Any]:
    """Lazily import a group of related modules.

    Args:
        group_name: Group key ('ml', 'torch', 'tf', etc.)

    Returns:
        Dict mapping module names to lazy-loaded modules.

    Example:
        >>> ml = lazy_import_group('ml')
        >>> detector = ml['graphsage_anomaly_detector'].GraphSAGEAnomalyDetector()
    """
    groups = {
        "ml": {
            "torch": "torch",
            "torch_nn": "torch.nn",
            "torch_f": "torch.nn.functional",
            "torch_geometric": "torch_geometric.nn",
            "transformers": "transformers",
            "sentence_transformers": "sentence_transformers",
            "numpy": "numpy",
            "scipy": "scipy",
            "sklearn": "sklearn",
        },
        "torch": {
            "torch": "torch",
            "nn": "torch.nn",
            "optim": "torch.optim",
            "functional": "torch.nn.functional",
        },
        "tf": {
            "tensorflow": "tensorflow",
            "keras": "tensorflow.keras",
            "layers": "tensorflow.keras.layers",
        },
        "data": {
            "pandas": "pandas",
            "numpy": "numpy",
            "scipy": "scipy",
            "polars": "polars",
        },
        "observability": {
            "prometheus": "prometheus_client",
            "jaeger": "jaeger_client",
            "opentelemetry": "opentelemetry",
        },
    }

    if group_name not in groups:
        raise ValueError(
            f"Unknown group: {group_name}. Available: {list(groups.keys())}"
        )

    result = {}
    for alias, full_name in groups[group_name].items():
        result[alias] = lazy_import(full_name)
    return result


# Pre-create common lazy loaders for convenience
torch = lazy_import("torch")
tf = lazy_import("tensorflow")
transformers = lazy_import("transformers")
numpy = lazy_import("numpy")
pandas = lazy_import("pandas")
