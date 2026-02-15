from dataclasses import dataclass
from enum import Enum
from typing import List


class FailureType(Enum):
    NODE_FAILURE = "node_failure"
    LINK_FAILURE = "link_failure"
    BYZANTINE_FAULT = "byzantine_fault"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    UNKNOWN = "unknown"


@dataclass
class AnomalyAnalysis:
    failure_type: FailureType
    confidence: float
    recommended_action: str
    severity: float
    affected_nodes: List[str]
