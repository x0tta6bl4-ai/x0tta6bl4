"""
Byzantine Protection для Mesh Network.

Интегрирует Signed Gossip и Quorum Validation с mesh routing
для защиты от Byzantine attacks.
"""

import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

from .quorum_validation import (CriticalEvent, CriticalEventType,
                                QuorumValidator)
from .signed_gossip import MessageType, SignedGossip, SignedMessage

logger = logging.getLogger(__name__)


@dataclass
class MeshByzantineState:
    """Состояние Byzantine protection для mesh узла."""

    node_id: str
    signed_gossip: SignedGossip
    quorum_validator: QuorumValidator
    quarantined_nodes: Set[str]
    validated_failures: Set[str]  # Nodes validated as failed by quorum


class MeshByzantineProtection:
    """
    Byzantine Protection для Mesh Network.

    Интегрирует:
    - Signed Gossip для всех control-plane сообщений
    - Quorum Validation для критических событий (node failures, link down)
    - Reputation scoring и quarantine
    """

    def __init__(self, node_id: str, total_nodes: int, quorum_threshold: float = 0.67):
        """
        Инициализация Byzantine Protection.

        Args:
            node_id: ID узла
            total_nodes: Общее количество узлов в сети
            quorum_threshold: Порог кворума (0.67 = 67%)
        """
        self.node_id = node_id
        self.total_nodes = total_nodes

        # Initialize Signed Gossip
        try:
            self.signed_gossip = SignedGossip(node_id)
        except ImportError:
            logger.error("🔴 liboqs required for Byzantine protection!")
            raise

        # Initialize Quorum Validator
        self.quorum_validator = QuorumValidator(node_id, total_nodes, quorum_threshold)

        # Track state
        self.quarantined_nodes: Set[str] = set()
        self.validated_failures: Set[str] = set()

        logger.info(
            f"✅ Mesh Byzantine Protection initialized for {node_id} "
            f"(n={total_nodes}, quorum={self.quorum_validator.quorum_size})"
        )

    def sign_beacon(
        self, neighbors: List[str], timestamp: Optional[float] = None
    ) -> SignedMessage:
        """
        Подписать beacon сообщение.

        Args:
            neighbors: Список соседей
            timestamp: Timestamp (генерируется если None)

        Returns:
            SignedMessage с подписью
        """
        payload = {"neighbors": neighbors, "node_id": self.node_id}

        message = self.signed_gossip.sign_message(MessageType.BEACON, payload)

        return message

    def verify_beacon(self, message: SignedMessage) -> tuple[bool, Optional[str]]:
        """
        Проверить подписанный beacon.

        Returns:
            (is_valid, error_message)
        """
        return self.signed_gossip.verify_message(message)

    def report_node_failure(
        self, failed_node: str, evidence: Dict[str, Any]
    ) -> CriticalEvent:
        """
        Сообщить о сбое узла (требует кворумной валидации).

        Args:
            failed_node: ID упавшего узла
            evidence: Доказательства сбоя (latency, packet_loss, etc.)

        Returns:
            CriticalEvent объект
        """
        event = self.quorum_validator.report_critical_event(
            CriticalEventType.NODE_FAILURE, target=failed_node, evidence=evidence
        )

        logger.info(
            f"📢 Node failure reported: {failed_node} "
            f"(quorum needed: {self.quorum_validator.quorum_size})"
        )

        return event

    def validate_node_failure(
        self, event: CriticalEvent, validator_signature: bytes
    ) -> bool:
        """
        Валидировать сбой узла (добавить подпись валидатора).

        Args:
            event: Событие сбоя
            validator_signature: Подпись валидатора

        Returns:
            True если кворум достигнут
        """
        is_validated = self.quorum_validator.validate_event(
            event, self.node_id, validator_signature
        )

        if is_validated:
            # Mark node as validated failure
            self.validated_failures.add(event.target)

            # Remove from routing table
            logger.warning(
                f"🔴 Node {event.target} validated as FAILED by quorum. "
                f"Removing from routing table."
            )

        return is_validated

    def report_link_down(
        self, link_from: str, link_to: str, evidence: Dict[str, Any]
    ) -> CriticalEvent:
        """
        Сообщить о падении линка (требует кворумной валидации).

        Args:
            link_from: ID узла-источника линка
            link_to: ID узла-назначения линка
            evidence: Доказательства падения линка

        Returns:
            CriticalEvent объект
        """
        link_id = f"{link_from}->{link_to}"

        event = self.quorum_validator.report_critical_event(
            CriticalEventType.LINK_DOWN, target=link_id, evidence=evidence
        )

        logger.info(
            f"📢 Link down reported: {link_id} "
            f"(quorum needed: {self.quorum_validator.quorum_size})"
        )

        return event

    def is_node_quarantined(self, node_id: str) -> bool:
        """Проверить, находится ли узел в карантине."""
        return (
            self.signed_gossip.is_quarantined(node_id)
            or node_id in self.quarantined_nodes
        )

    def get_node_reputation(self, node_id: str) -> float:
        """Получить репутацию узла."""
        return self.signed_gossip.get_reputation(node_id)

    def get_validated_failures(self) -> Set[str]:
        """Получить список узлов, валидированных как упавшие."""
        # Event objects are shared across nodes in tests; sync local cache from
        # pending events so reporter node sees quorum outcome.
        for event in self.quorum_validator._pending_events.values():
            if event.validated:
                self.validated_failures.add(event.target)
        return self.validated_failures.copy()

    def should_accept_message(self, sender: str) -> bool:
        """
        Проверить, следует ли принимать сообщение от узла.

        Returns:
            True если узел не в карантине и имеет хорошую репутацию
        """
        if self.is_node_quarantined(sender):
            return False

        reputation = self.get_node_reputation(sender)
        if reputation < 0.3:
            return False

        return True

    def get_protection_stats(self) -> Dict[str, Any]:
        """Получить статистику Byzantine protection."""
        return {
            "node_id": self.node_id,
            "total_nodes": self.total_nodes,
            "quorum_size": self.quorum_validator.quorum_size,
            "quarantined_nodes": list(self.quarantined_nodes),
            "validated_failures": list(self.validated_failures),
            "node_reputations": {
                node_id: self.get_node_reputation(node_id)
                for node_id in self.quarantined_nodes
            },
        }
