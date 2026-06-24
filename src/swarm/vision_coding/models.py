"""Vision coding models."""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

"""
Vision Coding Module - Coding with Vision для Kimi K2.5
Реализация визуального программирования, отладки и анализа графов.
"""

import asyncio
import hashlib
import heapq
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy  # type: ignore
from PIL import Image, ImageDraw, ImageFont  # type: ignore

logger = logging.getLogger(__name__)


class AnalysisType(Enum):
    """Типы визуального анализа"""

    UI_LAYOUT = auto()
    CODE_STRUCTURE = auto()
    GRAPH_PATHFINDING = auto()
    ERROR_DETECTION = auto()
    PERFORMANCE_VISUALIZATION = auto()
    DATA_FLOW = auto()


class Severity(Enum):
    """Уровень серьёзности проблемы"""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class BoundingBox:
    """Ограничивающий прямоугольник"""

    x: float
    y: float
    width: float
    height: float

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x + self.width / 2, self.y + self.height / 2)

    @property
    def area(self) -> float:
        return self.width * self.height

    def contains(self, point: Tuple[float, float]) -> bool:
        px, py = point
        return (
            self.x <= px <= self.x + self.width and self.y <= py <= self.y + self.height
        )

    def intersects(self, other: "BoundingBox") -> bool:
        return not (
            self.x + self.width < other.x
            or other.x + other.width < self.x
            or self.y + self.height < other.y
            or other.y + other.height < self.y
        )


@dataclass
class Style:
    """Стиль визуального элемента"""

    color: str = "#00FF00"
    border_width: float = 2.0
    opacity: float = 0.8
    font_size: int = 12
    fill_color: Optional[str] = None
    dash_pattern: Optional[List[int]] = None


@dataclass
class OverlayElement:
    """Элемент визуального наложения"""

    element_type: str
    location: BoundingBox
    style: Style
    content: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Issue:
    """Найденная проблема"""

    issue_type: str
    severity: Severity
    location: BoundingBox
    description: str
    suggestion: str = ""
    confidence: float = 0.0


@dataclass
class Suggestion:
    """Предложение по улучшению"""

    suggestion_type: str
    confidence: float
    action: str
    code_snippet: str = ""
    explanation: str = ""


