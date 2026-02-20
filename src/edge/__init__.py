"""
Edge Computing Module - Distributed edge computing for MaaS.

Provides edge node management, task distribution, and local processing
capabilities for reduced latency and improved resilience.
"""

from .edge_node import EdgeNode, EdgeNodeConfig, EdgeNodeManager
from .task_distributor import TaskDistributor, DistributionStrategy as TaskDistributionStrategy
from .edge_cache import EdgeCache, CachePolicy

__all__ = [
    "EdgeNode",
    "EdgeNodeConfig",
    "EdgeNodeManager",
    "TaskDistributor",
    "TaskDistributionStrategy",
    "EdgeCache",
    "CachePolicy",
]
