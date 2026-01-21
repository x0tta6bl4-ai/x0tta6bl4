"""
Signed Gossip Protocol for Control-Plane Messages.

Все управляющие сообщения подписаны PQC подписями (Dilithium3)
для защиты от Byzantine attacks.
"""
import logging
import time
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)

# Try to import liboqs
try:
    from oqs import Signature
    LIBOQS_AVAILABLE = True
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - signed gossip disabled")


class MessageType(Enum):
    """Типы control-plane сообщений."""
    BEACON = "beacon"
    ROUTE_UPDATE = "route_update"
    NODE_FAILURE = "node_failure"
    TOPOLOGY_CHANGE = "topology_change"
    GOVERNANCE_PROPOSAL = "governance_proposal"
    KEY_ROTATION = "key_rotation"


@dataclass
class SignedMessage:
    """Подписанное control-plane сообщение."""
    msg_type: MessageType
    sender: str
    timestamp: float
    nonce: int  # Anti-replay
    epoch: int  # Anti-replay (increments on key rotation)
    payload: Dict[str, Any]
    signature: bytes
    public_key: bytes  # Dilithium3 public key
    
    def serialize(self) -> bytes:
        """Сериализация для подписи (без signature)."""
        data = {
            "type": self.msg_type.value,
            "sender": self.sender,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
            "epoch": self.epoch,
            "payload": self.payload
        }
        return json.dumps(data, sort_keys=True).encode('utf-8')
    
    def verify(self) -> bool:
        """Проверить подпись сообщения."""
        if not LIBOQS_AVAILABLE:
            logger.warning("⚠️ liboqs not available - cannot verify signature")
            return False
        
        try:
            sig = Signature("Dilithium3")
            sig.set_public_key(self.public_key)
            
            message_data = self.serialize()
            is_valid = sig.verify(message_data, self.signature)
            
            return is_valid
        except Exception as e:
            logger.error(f"Failed to verify signature: {e}")
            return False


class SignedGossip:
    """
    Signed Gossip Protocol для control-plane.
    
    Features:
    - Все сообщения подписаны Dilithium3
    - Anti-replay (nonce + epoch)
    - Rate limiting
    - Quarantine для malicious узлов
    """
    
    def __init__(self, node_id: str, private_key: Optional[bytes] = None, public_key: Optional[bytes] = None):
        """
        Инициализация Signed Gossip.
        
        Args:
            node_id: ID узла
            private_key: Приватный ключ для подписи (генерируется если None)
            public_key: Публичный ключ (генерируется если None)
        """
        if not LIBOQS_AVAILABLE:
            raise ImportError("liboqs-python required for signed gossip")
        
        self.node_id = node_id
        # Use NIST name, fallback to legacy if needed
        try:
            self._sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            # Fallback to legacy name if NIST name not supported
            self._sig = Signature("Dilithium3")
        
        # Generate or use provided keys
        if private_key and public_key:
            self._sig.set_secret_key(private_key)
            self._sig.set_public_key(public_key)
            self.private_key = private_key
            self.public_key = public_key
        else:
            self.public_key, self.private_key = self._sig.generate_keypair()
            self._sig.set_secret_key(self.private_key)
            self._sig.set_public_key(self.public_key)
        
        # Anti-replay: track seen nonces per sender
        self._seen_nonces: Dict[str, Dict[int, set]] = defaultdict(lambda: defaultdict(set))  # sender -> epoch -> nonces
        
        # Rate limiting: messages per second per sender
        self._rate_limits: Dict[str, List[float]] = defaultdict(list)
        self._rate_limit = 10  # 10 messages per second
        
        # Quarantine: malicious nodes
        self._quarantined: Dict[str, float] = {}  # node_id -> quarantine_until
        self._quarantine_duration = 300  # 5 minutes
        
        # Reputation: track node behavior
        self._reputation: Dict[str, float] = defaultdict(lambda: 1.0)  # 0.0 - 1.0
        self._reputation_decay = 0.9  # Decay per violation
        self._reputation_recovery = 1.05  # Recovery per good message
        
        # Current epoch (increments on key rotation)
        self._current_epoch = 0
        
        logger.info(f"✅ Signed Gossip initialized for {node_id}")
    
    def sign_message(
        self,
        msg_type: MessageType,
        payload: Dict[str, Any],
        nonce: Optional[int] = None
    ) -> SignedMessage:
        """
        Подписать control-plane сообщение.
        
        Args:
            msg_type: Тип сообщения
            payload: Данные сообщения
            nonce: Nonce для anti-replay (генерируется если None)
            
        Returns:
            SignedMessage с подписью
        """
        if nonce is None:
            nonce = int(time.time() * 1000000)  # Microsecond precision
        
        message = SignedMessage(
            msg_type=msg_type,
            sender=self.node_id,
            timestamp=time.time(),
            nonce=nonce,
            epoch=self._current_epoch,
            payload=payload,
            signature=b"",  # Will be set below
            public_key=self.public_key
        )
        
        # Sign message
        message_data = message.serialize()
        signature = self._sig.sign(message_data)
        message.signature = signature
        
        return message
    
    def verify_message(self, message: SignedMessage) -> Tuple[bool, Optional[str]]:
        """
        Проверить подписанное сообщение.
        
        Returns:
            (is_valid, error_message)
        """
        # Check quarantine
        if message.sender in self._quarantined:
            if time.time() < self._quarantined[message.sender]:
                return False, f"Node {message.sender} is quarantined"
            else:
                # Quarantine expired
                del self._quarantined[message.sender]
        
        # Check rate limit
        now = time.time()
        self._rate_limits[message.sender] = [
            t for t in self._rate_limits[message.sender]
            if now - t < 1.0  # Last second
        ]
        
        if len(self._rate_limits[message.sender]) >= self._rate_limit:
            self._penalize_node(message.sender, "rate_limit_exceeded")
            return False, f"Rate limit exceeded for {message.sender}"
        
        # Check nonce (anti-replay)
        if message.nonce in self._seen_nonces[message.sender][message.epoch]:
            self._penalize_node(message.sender, "replay_attack")
            return False, f"Replay attack detected: nonce {message.nonce} already seen"
        
        # Check epoch (must be current or recent)
        if message.epoch < self._current_epoch - 1:
            return False, f"Stale epoch: {message.epoch} < {self._current_epoch - 1}"
        
        # Verify signature
        if not message.verify():
            self._penalize_node(message.sender, "invalid_signature")
            return False, "Invalid signature"
        
        # All checks passed
        self._seen_nonces[message.sender][message.epoch].add(message.nonce)
        self._rate_limits[message.sender].append(now)
        self._reward_node(message.sender)
        
        return True, None
    
    def _penalize_node(self, node_id: str, reason: str):
        """Наказать узел за нарушение."""
        self._reputation[node_id] *= self._reputation_decay
        
        if self._reputation[node_id] < 0.3:
            # Quarantine node
            self._quarantined[node_id] = time.time() + self._quarantine_duration
            logger.warning(
                f"🔴 Node {node_id} quarantined (reputation={self._reputation[node_id]:.2f}, reason={reason})"
            )
        else:
            logger.warning(
                f"⚠️ Node {node_id} penalized (reputation={self._reputation[node_id]:.2f}, reason={reason})"
            )
    
    def _reward_node(self, node_id: str):
        """Наградить узел за хорошее поведение."""
        self._reputation[node_id] = min(1.0, self._reputation[node_id] * self._reputation_recovery)
    
    def get_reputation(self, node_id: str) -> float:
        """Получить репутацию узла."""
        return self._reputation[node_id]
    
    def is_quarantined(self, node_id: str) -> bool:
        """Проверить, находится ли узел в карантине."""
        if node_id not in self._quarantined:
            return False
        
        if time.time() >= self._quarantined[node_id]:
            # Quarantine expired
            del self._quarantined[node_id]
            return False
        
        return True
    
    def rotate_keys(self):
        """Ротация ключей (увеличивает epoch)."""
        self._current_epoch += 1
        # Generate new keys
        self.public_key, self.private_key = self._sig.generate_keypair()
        self._sig.set_secret_key(self.private_key)
        self._sig.set_public_key(self.public_key)
        
        # Clear old nonces (keep only current epoch)
        self._seen_nonces = {k: {self._current_epoch: v.get(self._current_epoch, set())}
                            for k, v in self._seen_nonces.items()}
        
        logger.info(f"✅ Keys rotated, new epoch: {self._current_epoch}")

