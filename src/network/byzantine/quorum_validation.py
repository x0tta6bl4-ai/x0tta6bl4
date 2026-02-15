"""
Quorum Validation для критических событий.

Критические события (link down, node failure, governance) требуют
кворумной валидации перед принятием решения.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class CriticalEventType(Enum):
    """Типы критических событий."""

    NODE_FAILURE = "node_failure"
    LINK_DOWN = "link_down"
    TOPOLOGY_PARTITION = "topology_partition"
    GOVERNANCE_PROPOSAL = "governance_proposal"
    KEY_ROTATION = "key_rotation"
    SECURITY_INCIDENT = "security_incident"


@dataclass
class CriticalEvent:
    """Критическое событие, требующее кворумной валидации."""

    event_type: CriticalEventType
    source: str  # Node that reported the event
    target: str  # Affected node/link
    timestamp: float
    evidence: Dict[str, Any]  # Evidence for the event
    signatures: Dict[str, bytes]  # Signatures from validating nodes
    validated: bool = False
    quorum_reached: bool = False

    def add_signature(self, node_id: str, signature: bytes):
        """Добавить подпись валидатора."""
        self.signatures[node_id] = signature


class QuorumValidator:
    """
    Quorum Validator для критических событий.

    Критические события требуют подтверждения от кворума узлов
    перед принятием решения (например, исключение узла из сети).
    """

    def __init__(self, node_id: str, total_nodes: int, quorum_threshold: float = 0.67):
        """
        Инициализация Quorum Validator.

        Args:
            node_id: ID узла
            total_nodes: Общее количество узлов в сети
            quorum_threshold: Порог кворума (0.67 = 67% = 2/3)
        """
        self.node_id = node_id
        self.total_nodes = total_nodes
        self.quorum_threshold = quorum_threshold
        self.quorum_size = int(total_nodes * quorum_threshold) + 1

        # Track pending events
        self._pending_events: Dict[str, CriticalEvent] = {}

        # Track validated events
        self._validated_events: Set[str] = set()

        # Reputation for event sources
        self._source_reputation: Dict[str, float] = defaultdict(lambda: 1.0)

        logger.info(
            f"✅ Quorum Validator initialized: "
            f"n={total_nodes}, quorum={self.quorum_size} ({quorum_threshold*100:.0f}%)"
        )

    def report_critical_event(
        self,
        event_type: CriticalEventType,
        target: str,
        evidence: Dict[str, Any],
        source: Optional[str] = None,
    ) -> CriticalEvent:
        """
        Сообщить о критическом событии.

        Args:
            event_type: Тип события
            target: Затронутый узел/линк
            evidence: Доказательства события
            source: Источник события (по умолчанию self.node_id)

        Returns:
            CriticalEvent объект
        """
        if source is None:
            source = self.node_id

        event_id = f"{event_type.value}:{target}:{int(time.time())}"

        event = CriticalEvent(
            event_type=event_type,
            source=source,
            target=target,
            timestamp=time.time(),
            evidence=evidence,
            # Count reporter's own attestation as the initial signature.
            signatures={source: b"source_report"},
        )

        self._pending_events[event_id] = event

        logger.info(
            f"📢 Critical event reported: {event_type.value} for {target} "
            f"(source: {source}, quorum needed: {self.quorum_size})"
        )

        return event

    def validate_event(
        self, event: CriticalEvent, validator_node_id: str, signature: bytes
    ) -> bool:
        """
        Валидировать критическое событие (добавить подпись валидатора).

        Args:
            event: Событие для валидации
            validator_node_id: ID узла-валидатора
            signature: Подпись валидатора

        Returns:
            True если кворум достигнут
        """
        # Check if already validated
        event_id = f"{event.event_type.value}:{event.target}:{int(event.timestamp)}"
        if event_id in self._validated_events:
            return True

        # Add signature
        event.add_signature(validator_node_id, signature)

        # Check quorum
        if len(event.signatures) >= self.quorum_size:
            event.quorum_reached = True
            event.validated = True
            self._validated_events.add(event_id)

            logger.info(
                f"✅ Quorum reached for event {event_id}: "
                f"{len(event.signatures)}/{self.quorum_size} signatures"
            )

            # Reward source for accurate reporting
            self._source_reputation[event.source] = min(
                2.0, self._source_reputation[event.source] * 1.1
            )

            return True

        logger.debug(
            f"⏳ Quorum progress for {event_id}: "
            f"{len(event.signatures)}/{self.quorum_size} signatures"
        )

        return False

    def is_validated(self, event: CriticalEvent) -> bool:
        """Проверить, валидировано ли событие."""
        event_id = f"{event.event_type.value}:{event.target}:{int(event.timestamp)}"
        return event_id in self._validated_events

    def get_quorum_progress(self, event: CriticalEvent) -> tuple:
        """Получить прогресс кворума."""
        return len(event.signatures), self.quorum_size

    def get_source_reputation(self, source: str) -> float:
        """Получить репутацию источника событий."""
        return self._source_reputation[source]

    def penalize_source(self, source: str, reason: str):
        """Наказать источник за ложные события."""
        self._source_reputation[source] *= 0.8

        if self._source_reputation[source] < 0.3:
            logger.warning(
                f"🔴 Source {source} has low reputation "
                f"({self._source_reputation[source]:.2f}) - possible false reports"
            )
