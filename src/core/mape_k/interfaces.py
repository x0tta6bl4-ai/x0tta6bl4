"""
Abstract Base Classes for MAPE-K components.
Ensures consistency across different MAPE-K implementations.
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class MonitorInterface(ABC):
    @abstractmethod
    def check(self, metrics: Dict[str, Any]) -> Any:
        """Collect metrics and detect initial anomalies."""
        pass


class AnalyzerInterface(ABC):
    @abstractmethod
    def analyze(self, metrics: Dict[str, Any], **kwargs) -> Any:
        """Analyze metrics and identify root cause."""
        pass


class PlannerInterface(ABC):
    @abstractmethod
    def plan(self, analysis_result: Any) -> Any:
        """Plan recovery strategy based on analysis."""
        pass


class ExecutorInterface(ABC):
    @abstractmethod
    def execute(self, action: Any, context: Optional[Dict[str, Any]] = None) -> bool:
        """Execute recovery action."""
        pass


class KnowledgeInterface(ABC):
    @abstractmethod
    def record(self, metrics: Dict[str, Any], issue: str, action: str, success: bool, **kwargs):
        """Record incident outcome for future learning."""
        pass

    @abstractmethod
    def get_recommended_action(self, issue: str) -> Optional[str]:
        """Get recommended action based on historical patterns."""
        pass
