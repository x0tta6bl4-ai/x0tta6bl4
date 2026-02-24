"""
Zero-Knowledge Proof Authentication Module.
Privacy-preserving authentication without revealing credentials.

Implements:
- Schnorr ZKP Protocol for identity proof
- Pedersen Commitments for secret sharing
- Challenge-Response for verification
"""

import hashlib
import hmac
import logging
import secrets
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


# Криптографические параметры (256-bit security)
# Используем параметры группы для Schnorr
P = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141  # Prime
G = 2  # Generator
Q = (P - 1) // 2  # Group order


class ZKPProtocol(Enum):
    """Поддерживаемые ZKP протоколы."""

    SCHNORR = "schnorr"
    PEDERSEN = "pedersen"
    CHAUM = "chaum"


@dataclass
class ZKPChallenge:
    """Challenge для ZKP верификации."""

    challenge_id: str
    commitment: int
    challenge: int
    timestamp: float
    protocol: ZKPProtocol = ZKPProtocol.SCHNORR


@dataclass
class ZKPProof:
    """Доказательство без раскрытия секрета."""

    proof_id: str
    response: int
    public_key: int
    protocol: ZKPProtocol = ZKPProtocol.SCHNORR


class SchnorrZKP:
    """
    Schnorr Zero-Knowledge Proof Protocol.

    Позволяет доказать знание секретного ключа без его раскрытия.

    Протокол:
    1. Prover: выбирает random r, отправляет commitment = g^r mod p
    2. Verifier: отправляет random challenge c
    3. Prover: отправляет response s = r + c*x mod q (x - секретный ключ)
    4. Verifier: проверяет g^s = commitment * y^c mod p (y - публичный ключ)
    """

    def __init__(self, secret_key: Optional[int] = None):
        """
        Инициализация с опциональным секретным ключом.

        Args:
            secret_key: Секретный ключ (если None - генерируется новый)
        """
        self.secret_key = secret_key or secrets.randbelow(Q - 1) + 1
        self.public_key = pow(G, self.secret_key, P)

        # Для верификации
        self._pending_challenges: Dict[str, ZKPChallenge] = {}

    @staticmethod
    def generate_keypair() -> Tuple[int, int]:
        """
        Генерация пары ключей.

        Returns:
            (secret_key, public_key)
        """
        secret = secrets.randbelow(Q - 1) + 1
        public = pow(G, secret, P)
        return secret, public

    def create_commitment(self) -> Tuple[int, int]:
        """
        Шаг 1: Создание commitment (обязательства).

        Returns:
            (commitment, random_nonce) - commitment публикуется, nonce хранится секретно
        """
        r = secrets.randbelow(Q - 1) + 1
        commitment = pow(G, r, P)
        return commitment, r

    def generate_challenge(self, commitment: int, prover_id: str) -> ZKPChallenge:
        """
        Шаг 2 (Verifier): Генерация challenge.

        Args:
            commitment: Commitment от prover
            prover_id: Идентификатор prover

        Returns:
            ZKPChallenge с challenge value
        """
        import time

        challenge = secrets.randbelow(Q - 1) + 1
        challenge_id = hashlib.sha256(
            f"{prover_id}{commitment}{challenge}{time.time()}".encode()
        ).hexdigest()[:16]

        zkp_challenge = ZKPChallenge(
            challenge_id=challenge_id,
            commitment=commitment,
            challenge=challenge,
            timestamp=time.time(),
        )

        self._pending_challenges[challenge_id] = zkp_challenge
        return zkp_challenge

    def create_response(self, nonce: int, challenge: int) -> int:
        """
        Шаг 3 (Prover): Создание response.

        Args:
            nonce: Random nonce из create_commitment
            challenge: Challenge от verifier

        Returns:
            response = r + c*x mod q
        """
        response = (nonce + challenge * self.secret_key) % Q
        return response

    def create_proof(self, challenge: ZKPChallenge, nonce: int) -> ZKPProof:
        """
        Создание полного доказательства.

        Args:
            challenge: Challenge от verifier
            nonce: Nonce из commitment

        Returns:
            ZKPProof
        """
        response = self.create_response(nonce, challenge.challenge)

        return ZKPProof(
            proof_id=challenge.challenge_id,
            response=response,
            public_key=self.public_key,
        )

    def verify_proof(self, challenge: ZKPChallenge, proof: ZKPProof) -> bool:
        """
        Шаг 4: Верификация доказательства.

        Проверяет: g^s == commitment * y^c mod p

        Args:
            challenge: Оригинальный challenge
            proof: Proof от prover

        Returns:
            True если доказательство валидно
        """
        try:
            # g^s mod p
            left = pow(G, proof.response, P)

            # commitment * y^c mod p
            y_c = pow(proof.public_key, challenge.challenge, P)
            right = (challenge.commitment * y_c) % P

            valid = left == right

            if valid:
                logger.info(f"ZKP verification successful for proof {proof.proof_id}")
            else:
                logger.warning(f"ZKP verification failed for proof {proof.proof_id}")

            return valid

        except Exception as e:
            logger.error(f"ZKP verification error: {e}")
            return False

    def verify_by_id(self, challenge_id: str, proof: ZKPProof) -> bool:
        """
        Верификация по challenge_id.

        Args:
            challenge_id: ID сохранённого challenge
            proof: Proof от prover

        Returns:
            True если валидно
        """
        challenge = self._pending_challenges.get(challenge_id)
        if not challenge:
            logger.warning(f"Challenge {challenge_id} not found")
            return False

        # Проверяем timeout (5 минут)
        import time

        if time.time() - challenge.timestamp > 300:
            logger.warning(f"Challenge {challenge_id} expired")
            del self._pending_challenges[challenge_id]
            return False

        result = self.verify_proof(challenge, proof)

        # Удаляем использованный challenge
        del self._pending_challenges[challenge_id]

        return result


class PedersenCommitment:
    """
    Pedersen Commitment Scheme.

    Позволяет commit к значению без его раскрытия,
    с возможностью позже доказать что значение было именно таким.

    C = g^m * h^r mod p
    где m - сообщение, r - random blinding factor
    
    SECURITY: H is derived deterministically from a fixed seed to ensure
    consistency across sessions while maintaining the security requirement
    that log_G(H) is unknown (computationally infeasible to compute).
    """

    # Второй генератор для Pedersen (должен быть выбран так, что log_g(h) неизвестен)
    # Используем детерминистический вывод из seed для консистентности между сессиями
    # H = SHA-256("x0tta6bl4_pedersen_h_v1") mod P
    _H_SEED = hashlib.sha256(b"x0tta6bl4_pedersen_h_generator_v1_secure").digest()
    H = int.from_bytes(_H_SEED, 'big') % P
    
    # Убеждаемся что H != G и H != 1
    while H == G or H == 1:
        _H_SEED = hashlib.sha256(_H_SEED).digest()
        H = int.from_bytes(_H_SEED, 'big') % P

    @classmethod
    def commit(cls, value: int) -> Tuple[int, int]:
        """
        Создание commitment к значению.

        Args:
            value: Значение для commit

        Returns:
            (commitment, blinding_factor)
        """
        r = secrets.randbelow(Q - 1) + 1
        commitment = (pow(G, value, P) * pow(cls.H, r, P)) % P
        return commitment, r

    @classmethod
    def verify(cls, commitment: int, value: int, blinding_factor: int) -> bool:
        """
        Верификация commitment.

        Args:
            commitment: Оригинальный commitment
            value: Заявленное значение
            blinding_factor: Blinding factor

        Returns:
            True если commitment валиден
        """
        expected = (pow(G, value, P) * pow(cls.H, blinding_factor, P)) % P
        return commitment == expected

    @classmethod
    def add_commitments(cls, c1: int, c2: int) -> int:
        """
        Гомоморфное сложение commitments.

        C(a) * C(b) = C(a + b)
        """
        return (c1 * c2) % P


class ZKPAuthenticator:
    """
    High-level authenticator с ZKP.

    Использование:
        # Prover
        auth = ZKPAuthenticator(node_id="alice")
        commitment = auth.start_auth()

        # Verifier
        challenge = verifier.generate_challenge(commitment, "alice")

        # Prover
        proof = auth.complete_auth(challenge)

        # Verifier
        valid = verifier.verify_authentication(proof)
    """

    def __init__(self, node_id: str, secret_key: Optional[int] = None):
        self.node_id = node_id
        self.zkp = SchnorrZKP(secret_key)

        # Текущий auth state
        self._current_nonce: Optional[int] = None
        self._current_commitment: Optional[int] = None

    @property
    def public_key(self) -> int:
        """Публичный ключ для верификации."""
        return self.zkp.public_key

    def start_auth(self) -> Dict[str, Any]:
        """
        Начать аутентификацию (Prover side).

        Returns:
            Dict с commitment для отправки verifier
        """
        commitment, nonce = self.zkp.create_commitment()
        self._current_nonce = nonce
        self._current_commitment = commitment

        return {
            "type": "zkp_auth_start",
            "node_id": self.node_id,
            "commitment": commitment,
            "public_key": self.public_key,
        }

    def generate_challenge(self, auth_start: Dict[str, Any]) -> Dict[str, Any]:
        """
        Генерация challenge (Verifier side).

        Args:
            auth_start: Данные от start_auth

        Returns:
            Dict с challenge для отправки prover
        """
        challenge = self.zkp.generate_challenge(
            auth_start["commitment"], auth_start["node_id"]
        )

        return {
            "type": "zkp_challenge",
            "challenge_id": challenge.challenge_id,
            "challenge": challenge.challenge,
            "for_node": auth_start["node_id"],
        }

    def complete_auth(self, challenge_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Завершить аутентификацию (Prover side).

        Args:
            challenge_data: Данные от generate_challenge

        Returns:
            Dict с proof для отправки verifier
        """
        if self._current_nonce is None:
            raise ValueError("Auth not started")

        response = self.zkp.create_response(
            self._current_nonce, challenge_data["challenge"]
        )

        proof = {
            "type": "zkp_proof",
            "proof_id": challenge_data["challenge_id"],
            "response": response,
            "public_key": self.public_key,
            "node_id": self.node_id,
        }

        # Очищаем state
        self._current_nonce = None
        self._current_commitment = None

        return proof

    def verify_authentication(self, proof_data: Dict[str, Any]) -> bool:
        """
        Верифицировать proof (Verifier side).

        Args:
            proof_data: Данные от complete_auth

        Returns:
            True если аутентификация успешна
        """
        proof = ZKPProof(
            proof_id=proof_data["proof_id"],
            response=proof_data["response"],
            public_key=proof_data["public_key"],
        )

        return self.zkp.verify_by_id(proof_data["proof_id"], proof)


# === Convenience Functions ===


def create_zkp_identity() -> Tuple[int, int, ZKPAuthenticator]:
    """
    Создать новую ZKP идентичность.

    Returns:
        (secret_key, public_key, authenticator)
    """
    secret, public = SchnorrZKP.generate_keypair()
    auth = ZKPAuthenticator(node_id="", secret_key=secret)
    return secret, public, auth


def verify_zkp_proof_simple(
    public_key: int, commitment: int, challenge: int, response: int
) -> bool:
    """
    Простая верификация ZKP proof.

    Args:
        public_key: Публичный ключ prover
        commitment: Commitment от prover
        challenge: Challenge value
        response: Response от prover

    Returns:
        True если proof валиден
    """
    # g^s == commitment * y^c mod p
    left = pow(G, response, P)
    y_c = pow(public_key, challenge, P)
    right = (commitment * y_c) % P
    return left == right
