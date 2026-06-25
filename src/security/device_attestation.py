"""
Device Trust Attestation Module.
Privacy-preserving device verification без раскрытия идентифицирующей информации.

Implements:
- Hardware fingerprinting (анонимизированный)
- Software integrity verification
- Behavioral attestation
- Trust score calculation
"""

import hashlib
import hmac
import logging
import platform
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_ref(value: object) -> Dict[str, Any]:
    return {"hash": _safe_hash(value), "present": value is not None}


def _score_band(value: float) -> str:
    if value >= 0.9:
        return "verified"
    if value >= 0.7:
        return "high"
    if value >= 0.5:
        return "medium"
    if value >= 0.3:
        return "low"
    return "untrusted"


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    return "100+"


class AttestationType(Enum):
    """Типы аттестации устройства."""

    HARDWARE = "hardware"
    SOFTWARE = "software"
    BEHAVIORAL = "behavioral"
    NETWORK = "network"
    COMPOSITE = "composite"


class TrustLevel(Enum):
    """Уровни доверия устройству."""

    UNTRUSTED = 0
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    VERIFIED = 4


@dataclass
class DeviceFingerprint:
    """Анонимизированный fingerprint устройства."""

    fingerprint_hash: str  # SHA-256 хэш характеристик
    platform_type: str  # Тип платформы (linux, windows, darwin)
    arch_type: str  # Архитектура (x86_64, arm64)
    attestation_time: float
    nonce: str  # Для предотвращения replay attacks

    def to_dict(self) -> Dict[str, Any]:
        return {
            "fingerprint_hash": self.fingerprint_hash,
            "platform_type": self.platform_type,
            "arch_type": self.arch_type,
            "attestation_time": self.attestation_time,
            "nonce": self.nonce,
        }


@dataclass
class AttestationClaim:
    """Заявление об аттестации."""

    claim_id: str
    device_fingerprint: DeviceFingerprint
    attestation_type: AttestationType
    evidence: Dict[str, Any]
    timestamp: float
    signature: str


@dataclass
class TrustScore:
    """Оценка доверия устройству."""

    device_id: str
    score: float  # 0.0 - 1.0
    level: TrustLevel
    factors: Dict[str, float]
    last_updated: float
    history: List[float] = field(default_factory=list)

    def update(self, new_score: float):
        """Обновить score с учётом истории."""
        self.history.append(self.score)
        if len(self.history) > 100:
            self.history.pop(0)

        # Weighted average с историей
        self.score = 0.7 * new_score + 0.3 * self.score
        self.level = self._calculate_level()
        self.last_updated = time.time()

    def _calculate_level(self) -> TrustLevel:
        if self.score >= 0.9:
            return TrustLevel.VERIFIED
        elif self.score >= 0.7:
            return TrustLevel.HIGH
        elif self.score >= 0.5:
            return TrustLevel.MEDIUM
        elif self.score >= 0.3:
            return TrustLevel.LOW
        else:
            return TrustLevel.UNTRUSTED


class DeviceAttestor:
    """
    Privacy-preserving Device Attestation.

    Генерирует анонимизированные доказательства о состоянии устройства
    без раскрытия уникальных идентификаторов.
    """

    def __init__(self, secret_salt: Optional[str] = None):
        """
        Args:
            secret_salt: Секретная соль для fingerprinting (если None - генерируется)
        """
        self.secret_salt = secret_salt or secrets.token_hex(32)
        self._attestation_key = hashlib.sha256(self.secret_salt.encode()).digest()
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"device-attestor:{_safe_hash(self._attestation_key.hex())}",
            role="security",
            capabilities=("zero-trust",),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "device_attestor_init",
                "goal": "Initialize privacy-preserving device attestation",
                "signals": {
                    "salt_configured": secret_salt is not None,
                    "attestation_key_hash": _safe_hash(self._attestation_key.hex()),
                },
                "safety_boundary": (
                    "Do not expose salt, attestation key, fingerprint hash, nonce, "
                    "or signatures in thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_secret_salt": True,
                    "redact_attestation_key": True,
                    "redact_fingerprint": True,
                    "redact_nonce": True,
                    "redact_signature": True,
                },
                "safety_boundary": (
                    "Use only hashes, platform classes, evidence keys, and booleans."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def create_fingerprint(self) -> DeviceFingerprint:
        """
        Создать анонимизированный fingerprint устройства.

        Собирает характеристики устройства и хэширует их
        для создания уникального, но анонимного идентификатора.
        """
        # Собираем характеристики (не включаем уникальные идентификаторы)
        characteristics = {
            "platform": platform.system().lower(),
            "arch": platform.machine(),
            "python_version": platform.python_version(),
            "processor_type": self._anonymize_processor(),
        }

        # Создаём хэш характеристик с секретной солью
        char_string = "|".join(f"{k}:{v}" for k, v in sorted(characteristics.items()))
        fingerprint_hash = hmac.new(
            self._attestation_key, char_string.encode(), hashlib.sha256
        ).hexdigest()

        nonce = secrets.token_hex(16)

        fingerprint = DeviceFingerprint(
            fingerprint_hash=fingerprint_hash,
            platform_type=characteristics["platform"],
            arch_type=characteristics["arch"],
            attestation_time=time.time(),
            nonce=nonce,
        )
        self._record_thinking(
            "device_fingerprint_created",
            "Create anonymized device fingerprint",
            {
                "fingerprint": _safe_ref(fingerprint_hash),
                "platform_type": characteristics["platform"],
                "arch_type_hash": _safe_hash(characteristics["arch"]),
                "processor_type": characteristics["processor_type"],
                "nonce_present": bool(nonce),
            },
        )
        return fingerprint

    def _anonymize_processor(self) -> str:
        """Анонимизировать информацию о процессоре."""
        proc = platform.processor()
        # Возвращаем только тип, не модель
        if "intel" in proc.lower():
            return "intel"
        elif "amd" in proc.lower():
            return "amd"
        elif "arm" in proc.lower():
            return "arm"
        else:
            return "unknown"

    def create_attestation(
        self, attestation_type: AttestationType = AttestationType.COMPOSITE
    ) -> AttestationClaim:
        """
        Создать полное заявление об аттестации.

        Args:
            attestation_type: Тип аттестации

        Returns:
            AttestationClaim с подписью
        """
        fingerprint = self.create_fingerprint()

        evidence = {}

        if attestation_type in (AttestationType.HARDWARE, AttestationType.COMPOSITE):
            evidence["hardware"] = self._collect_hardware_evidence()

        if attestation_type in (AttestationType.SOFTWARE, AttestationType.COMPOSITE):
            evidence["software"] = self._collect_software_evidence()

        if attestation_type in (AttestationType.NETWORK, AttestationType.COMPOSITE):
            evidence["network"] = self._collect_network_evidence()

        # Создаём claim ID
        claim_id = hashlib.sha256(
            f"{fingerprint.fingerprint_hash}{fingerprint.nonce}{time.time()}".encode()
        ).hexdigest()[:16]

        # Подписываем claim
        claim_data = (
            f"{claim_id}|{fingerprint.fingerprint_hash}|{attestation_type.value}"
        )
        signature = hmac.new(
            self._attestation_key, claim_data.encode(), hashlib.sha256
        ).hexdigest()

        claim = AttestationClaim(
            claim_id=claim_id,
            device_fingerprint=fingerprint,
            attestation_type=attestation_type,
            evidence=evidence,
            timestamp=time.time(),
            signature=signature,
        )
        self._record_thinking(
            "device_attestation_created",
            "Create signed device attestation claim",
            {
                "claim": _safe_ref(claim_id),
                "attestation_type": attestation_type.value,
                "evidence_keys": sorted(evidence.keys()),
                "fingerprint": _safe_ref(fingerprint.fingerprint_hash),
                "signature_present": bool(signature),
            },
        )
        return claim

    def _collect_hardware_evidence(self) -> Dict[str, Any]:
        """Собрать evidence о hardware (анонимизированное)."""
        import os

        return {
            "cpu_count": os.cpu_count(),
            "platform_bits": platform.architecture()[0],
            "endianness": (
                "little" if int.from_bytes(b"\x01\x00", "little") == 1 else "big"
            ),
        }

    def _collect_software_evidence(self) -> Dict[str, Any]:
        """Собрать evidence о software."""
        return {
            "python_implementation": platform.python_implementation(),
            "python_version_tuple": platform.python_version_tuple(),
        }

    def _collect_network_evidence(self) -> Dict[str, Any]:
        """Собрать evidence о network capabilities."""
        import socket

        return {
            "ipv6_supported": socket.has_ipv6,
            "hostname_hash": hashlib.sha256(
                (socket.gethostname() + self.secret_salt).encode()
            ).hexdigest()[
                :16
            ],  # Хэш hostname, не сам hostname
        }

    def verify_attestation(self, claim: AttestationClaim) -> Tuple[bool, str]:
        """
        Верифицировать attestation claim.

        Args:
            claim: Заявление для верификации

        Returns:
            (valid, reason)
        """
        # 1. Проверяем подпись
        claim_data = f"{claim.claim_id}|{claim.device_fingerprint.fingerprint_hash}|{claim.attestation_type.value}"
        expected_signature = hmac.new(
            self._attestation_key, claim_data.encode(), hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(claim.signature, expected_signature):
            self._record_thinking(
                "device_attestation_verify_failed",
                "Reject attestation with invalid signature",
                {
                    "claim": _safe_ref(claim.claim_id),
                    "attestation_type": claim.attestation_type.value,
                    "reason": "invalid_signature",
                },
            )
            return False, "Invalid signature"

        # 2. Проверяем timestamp (не старше 5 минут)
        if time.time() - claim.timestamp > 300:
            self._record_thinking(
                "device_attestation_verify_failed",
                "Reject expired attestation",
                {
                    "claim": _safe_ref(claim.claim_id),
                    "attestation_type": claim.attestation_type.value,
                    "reason": "expired",
                },
            )
            return False, "Attestation expired"

        # 3. Проверяем nonce (защита от replay)
        # В реальной реализации nonce хранятся в базе

        self._record_thinking(
            "device_attestation_verified",
            "Accept device attestation claim",
            {
                "claim": _safe_ref(claim.claim_id),
                "attestation_type": claim.attestation_type.value,
                "fingerprint": _safe_ref(claim.device_fingerprint.fingerprint_hash),
            },
        )
        return True, "Valid"


class AdaptiveTrustManager:
    """
    Adaptive Trust Scoring System.

    Динамически оценивает уровень доверия на основе:
    - Device attestation
    - Behavioral patterns
    - Historical data
    - Network context
    """

    # Веса для разных факторов
    FACTOR_WEIGHTS = {
        "attestation": 0.25,
        "behavior": 0.25,
        "history": 0.20,
        "network": 0.15,
        "time": 0.15,
    }

    def __init__(self):
        self._device_scores: Dict[str, TrustScore] = {}
        self._attestor = DeviceAttestor()
        self._behavioral_data: Dict[str, List[Dict]] = {}
        self.thinking_coach = AgentThinkingCoach(
            agent_id="adaptive-trust-manager",
            role="security",
            capabilities=("zero-trust", "monitoring"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "adaptive_trust_manager_init",
                "goal": "Initialize adaptive trust scoring",
                "signals": {
                    "factor_count": len(self.FACTOR_WEIGHTS),
                    "known_device_count": 0,
                },
                "safety_boundary": (
                    "Do not expose raw device ids, behavior payloads, fingerprints, "
                    "or network context values in trust thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_device_identifiers": True,
                    "redact_behavior_payloads": True,
                    "redact_network_context": True,
                    "preserve_factor_weights": True,
                },
                "safety_boundary": (
                    "Use device hashes, factor names, score bands, counts, and flags."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def get_trust_score(self, device_id: str) -> TrustScore:
        """Получить текущий trust score устройства."""
        if device_id not in self._device_scores:
            self._device_scores[device_id] = TrustScore(
                device_id=device_id,
                score=0.5,  # Начальный нейтральный score
                level=TrustLevel.MEDIUM,
                factors={},
                last_updated=time.time(),
            )
            self._record_thinking(
                "adaptive_trust_score_initialized",
                "Initialize neutral trust score for device",
                {
                    "device": _safe_ref(device_id),
                    "score_band": _score_band(0.5),
                    "known_device_count_bucket": _safe_count_bucket(
                        len(self._device_scores)
                    ),
                },
            )
        return self._device_scores[device_id]

    def evaluate_trust(
        self,
        device_id: str,
        attestation: Optional[AttestationClaim] = None,
        behavior_event: Optional[Dict] = None,
        network_context: Optional[Dict] = None,
    ) -> TrustScore:
        """
        Оценить и обновить trust score.

        Args:
            device_id: ID устройства
            attestation: Attestation claim (опционально)
            behavior_event: Событие поведения (опционально)
            network_context: Сетевой контекст (опционально)

        Returns:
            Обновлённый TrustScore
        """
        trust_score = self.get_trust_score(device_id)
        factors = {}

        # 1. Attestation factor
        if attestation:
            valid, _ = self._attestor.verify_attestation(attestation)
            factors["attestation"] = 1.0 if valid else 0.0
        else:
            factors["attestation"] = trust_score.factors.get("attestation", 0.5)

        # 2. Behavioral factor
        if behavior_event:
            self._record_behavior(device_id, behavior_event)
        factors["behavior"] = self._calculate_behavior_score(device_id)

        # 3. Historical factor
        factors["history"] = self._calculate_history_score(trust_score)

        # 4. Network factor
        if network_context:
            factors["network"] = self._evaluate_network_context(network_context)
        else:
            factors["network"] = trust_score.factors.get("network", 0.5)

        # 5. Time factor (score decay для неактивных устройств)
        factors["time"] = self._calculate_time_factor(trust_score)

        # Weighted average
        new_score = sum(factors[f] * self.FACTOR_WEIGHTS[f] for f in factors)

        trust_score.factors = factors
        trust_score.update(new_score)
        self._record_thinking(
            "adaptive_trust_evaluated",
            "Evaluate adaptive device trust score",
            {
                "device": _safe_ref(device_id),
                "attestation_present": attestation is not None,
                "behavior_event_present": behavior_event is not None,
                "network_context_present": network_context is not None,
                "factor_bands": {
                    name: _score_band(score) for name, score in factors.items()
                },
                "new_score_band": _score_band(new_score),
                "updated_score_band": _score_band(trust_score.score),
                "trust_level": trust_score.level.name,
            },
        )

        logger.debug(
            f"Trust score for {device_id}: {trust_score.score:.2f} ({trust_score.level.name})"
        )

        return trust_score

    def _record_behavior(self, device_id: str, event: Dict):
        """Записать behavioral event."""
        if device_id not in self._behavioral_data:
            self._behavioral_data[device_id] = []

        self._behavioral_data[device_id].append({**event, "timestamp": time.time()})

        # Ограничиваем историю
        if len(self._behavioral_data[device_id]) > 1000:
            self._behavioral_data[device_id] = self._behavioral_data[device_id][-500:]
        self._record_thinking(
            "adaptive_trust_behavior_recorded",
            "Record redacted device behavior event",
            {
                "device": _safe_ref(device_id),
                "event_type": event.get("type"),
                "event_name_hash": _safe_hash(event.get("event")),
                "history_count_bucket": _safe_count_bucket(
                    len(self._behavioral_data[device_id])
                ),
            },
        )

    def _calculate_behavior_score(self, device_id: str) -> float:
        """Рассчитать score на основе поведения."""
        events = self._behavioral_data.get(device_id, [])

        if not events:
            return 0.5  # Neutral

        # Анализируем последние события
        recent = [e for e in events if time.time() - e["timestamp"] < 3600]

        if not recent:
            return 0.5

        # Подсчитываем позитивные/негативные события
        positive = sum(1 for e in recent if e.get("type") == "positive")
        negative = sum(1 for e in recent if e.get("type") == "negative")
        total = len(recent)

        if total == 0:
            return 0.5

        return min(1.0, max(0.0, (positive - negative * 2 + total) / (total * 2)))

    def _calculate_history_score(self, trust_score: TrustScore) -> float:
        """Score на основе исторических данных."""
        if not trust_score.history:
            return 0.5

        # Средний исторический score
        avg = sum(trust_score.history) / len(trust_score.history)

        # Тренд (улучшается или ухудшается)
        if len(trust_score.history) >= 5:
            recent_avg = sum(trust_score.history[-5:]) / 5
            trend_bonus = 0.1 if recent_avg > avg else -0.1
        else:
            trend_bonus = 0

        return min(1.0, max(0.0, avg + trend_bonus))

    def _evaluate_network_context(self, context: Dict) -> float:
        """Оценить сетевой контекст."""
        score = 0.5

        # Известная сеть
        if context.get("known_network"):
            score += 0.2

        # Зашифрованное соединение
        if context.get("encrypted"):
            score += 0.15

        # VPN/Tor (может быть и плюс и минус)
        if context.get("anonymized"):
            score += 0.1  # В контексте anti-censorship это плюс

        # Подозрительные паттерны
        if context.get("suspicious_patterns"):
            score -= 0.3

        return min(1.0, max(0.0, score))

    def _calculate_time_factor(self, trust_score: TrustScore) -> float:
        """Time decay для неактивных устройств."""
        hours_since_update = (time.time() - trust_score.last_updated) / 3600

        if hours_since_update < 1:
            return 1.0
        elif hours_since_update < 24:
            return 0.9
        elif hours_since_update < 168:  # 1 week
            return 0.7
        else:
            return 0.5

    def record_positive_event(self, device_id: str, event_type: str = "success"):
        """Записать позитивное событие."""
        self._record_behavior(device_id, {"type": "positive", "event": event_type})

    def record_negative_event(self, device_id: str, event_type: str = "failure"):
        """Записать негативное событие."""
        self._record_behavior(device_id, {"type": "negative", "event": event_type})

    def is_trusted(
        self, device_id: str, min_level: TrustLevel = TrustLevel.MEDIUM
    ) -> bool:
        """Проверить достаточен ли уровень доверия."""
        score = self.get_trust_score(device_id)
        trusted = score.level.value >= min_level.value
        self._record_thinking(
            "adaptive_trust_checked",
            "Check whether device meets trust threshold",
            {
                "device": _safe_ref(device_id),
                "current_level": score.level.name,
                "min_level": min_level.name,
                "trusted": trusted,
            },
        )
        return trusted

    def get_all_scores(self) -> Dict[str, TrustScore]:
        """Получить все trust scores."""
        return self._device_scores.copy()


# === Integration with Mesh Network ===


class MeshDeviceAttestor:
    """
    Device Attestation для Mesh Network.
    Интегрирует ZKP с Device Attestation.
    """

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.attestor = DeviceAttestor()
        self.trust_manager = AdaptiveTrustManager()
        self.thinking_coach = AgentThinkingCoach(
            agent_id=f"mesh-device-attestor:{_safe_hash(node_id)}",
            role="security",
            capabilities=("zero-trust",),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "mesh_device_attestor_init",
                "goal": "Initialize mesh device attestation workflow",
                "signals": {"node": _safe_ref(node_id)},
                "safety_boundary": (
                    "Do not expose raw node ids, peer ids, fingerprints, nonces, or "
                    "signatures in mesh attestation thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_node_identifiers": True,
                    "redact_peer_identifiers": True,
                    "redact_attestation_material": True,
                },
                "safety_boundary": (
                    "Use hashes, validity flags, trust levels, and score bands only."
                ),
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "attestor": self.attestor.get_thinking_status(),
            "trust_manager": self.trust_manager.get_thinking_status(),
        }

    def create_mesh_attestation(self) -> Dict[str, Any]:
        """Создать attestation для mesh network."""
        claim = self.attestor.create_attestation(AttestationType.COMPOSITE)
        self._record_thinking(
            "mesh_device_attestation_created",
            "Create mesh device attestation payload",
            {
                "node": _safe_ref(self.node_id),
                "claim": _safe_ref(claim.claim_id),
                "fingerprint": _safe_ref(claim.device_fingerprint.fingerprint_hash),
                "evidence_keys": sorted(claim.evidence.keys()),
            },
        )

        return {
            "type": "mesh_attestation",
            "node_id": self.node_id,
            "claim": {
                "claim_id": claim.claim_id,
                "fingerprint": claim.device_fingerprint.to_dict(),
                "evidence": claim.evidence,
                "timestamp": claim.timestamp,
                "signature": claim.signature,
            },
        }

    def verify_peer_attestation(
        self, attestation_data: Dict
    ) -> Tuple[bool, TrustScore]:
        """
        Верифицировать attestation от peer.

        Returns:
            (valid, trust_score)
        """
        peer_id = attestation_data.get("node_id", "unknown")
        claim_data = attestation_data.get("claim", {})

        # Reconstruct claim
        fingerprint = DeviceFingerprint(**claim_data["fingerprint"])

        claim = AttestationClaim(
            claim_id=claim_data["claim_id"],
            device_fingerprint=fingerprint,
            attestation_type=AttestationType.COMPOSITE,
            evidence=claim_data.get("evidence", {}),
            timestamp=claim_data["timestamp"],
            signature=claim_data["signature"],
        )

        # Verify
        valid, reason = self.attestor.verify_attestation(claim)

        # Update trust score
        trust_score = self.trust_manager.evaluate_trust(
            peer_id, attestation=claim if valid else None
        )

        if valid:
            self.trust_manager.record_positive_event(peer_id, "attestation_valid")
        else:
            self.trust_manager.record_negative_event(
                peer_id, f"attestation_invalid:{reason}"
            )
        self._record_thinking(
            "mesh_peer_attestation_verified",
            "Verify peer attestation and update trust",
            {
                "peer": _safe_ref(peer_id),
                "claim": _safe_ref(claim.claim_id),
                "valid": valid,
                "reason_hash": _safe_hash(reason),
                "trust_level": trust_score.level.name,
                "trust_score_band": _score_band(trust_score.score),
            },
        )

        return valid, trust_score
