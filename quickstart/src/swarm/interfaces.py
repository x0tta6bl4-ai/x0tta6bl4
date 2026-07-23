"""
Abstract Base Classes for Swarm components.
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class DecisionEngineInterface(ABC):
    @abstractmethod
    async def make_decision(self, context: Any, **kwargs) -> Any:
        """Reach a consensus-based decision."""
        pass


class SwarmNodeInterface(ABC):
    @property
    @abstractmethod
    def node_id(self) -> str:
        """Unique identifier of the node."""
        pass

    @abstractmethod
    async def initialize(self):
        """Initialize node resources."""
        pass

    @abstractmethod
    async def shutdown(self):
        """Graceful shutdown."""
        pass

