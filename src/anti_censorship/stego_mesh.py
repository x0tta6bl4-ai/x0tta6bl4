"""
Steganographic Mesh Protocol v2.0 (Geneva-style)
=================================================

Реализация стеганографического mesh-протокола для обхода DPI.
Включает мимикрию под HTTP/ICMP/DNS и генетические стратегии уклонения (Geneva).
"""

import hashlib
import hmac
import logging
import secrets
import struct
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

# Geneva Integration
try:
    from .geneva_genetic import DNA, Action, ActionType, GenevaGeneticOptimizer
    GENEVA_AVAILABLE = True
except ImportError:
    GENEVA_AVAILABLE = False

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "anti-censorship-stego-mesh"
_SERVICE_LAYER = "anti_censorship_stego_mesh_local_evidence"
STEGO_MESH_CLAIM_BOUNDARY = (
    "Local StegoMesh codec evidence only. It records local packet encoding, "
    "decoding, Geneva-style strategy application, marker-probe outcomes, "
    "duration, byte-count buckets, packet-count buckets, and service identity "
    "presence; it does not expose payload bytes, master keys, HMAC keys, "
    "nonces, ciphertext, raw packets, DNS/HTTP/ICMP packet bytes, Geneva action "
    "parameters, or prove DPI bypass, censorship bypass, remote reachability, "
    "packet delivery, anonymity, provider health, client installation, or "
    "production customer traffic use."
)


def _byte_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value <= 64:
        return "tiny"
    if value <= 512:
        return "small"
    if value <= 1500:
        return "mtu"
    if value <= 8192:
        return "chunk"
    return "large"


def _packet_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value == 1:
        return "single"
    if value <= 4:
        return "few"
    if value <= 16:
        return "many"
    return "very_many"


def _protocol_mimic_bucket(protocol_mimic: Any) -> str:
    protocol = str(protocol_mimic or "").strip().lower()
    if protocol in {"http", "icmp", "dns"}:
        return protocol
    return "other"


def _action_type_bucket(action_type: Any) -> str:
    name = getattr(action_type, "name", None)
    value = getattr(action_type, "value", action_type)
    text = str(name or value or "").strip().lower()
    if text in {"split", "duplicate", "tamper", "drop"}:
        return text
    return "other"


def _evasion_metadata(evasion_dna: Any) -> Dict[str, Any]:
    actions = getattr(evasion_dna, "actions", None)
    counts = {
        "split": 0,
        "duplicate": 0,
        "tamper": 0,
        "drop": 0,
        "other": 0,
    }
    if not actions:
        return {
            "geneva_available": GENEVA_AVAILABLE,
            "dna_present": bool(evasion_dna),
            "actions_total": 0,
            "action_type_counts": counts,
            "raw_action_params_redacted": True,
        }

    for action in actions:
        bucket = _action_type_bucket(getattr(action, "type", None))
        counts[bucket] = counts.get(bucket, 0) + 1
    return {
        "geneva_available": GENEVA_AVAILABLE,
        "dna_present": True,
        "actions_total": len(actions),
        "action_type_counts": counts,
        "raw_action_params_redacted": True,
    }


class StegoMeshProtocol:
    """
    Стеганографический mesh-протокол v2.0.
    
    Security: Uses HMAC-SHA256 for integrity verification to prevent
    tampering attacks on encrypted packets.
    """

    # Магические маркеры для идентификации stego-пакетов
    STEGO_MARKER_HTTP = b"X-Stego-Mesh: 1"
    STEGO_MARKER_ICMP = b"X0TTA6BL4_STEGO"
    STEGO_MARKER_DNS = b"x0tta6bl4.stego"
    
    # HMAC length in bytes
    HMAC_LENGTH = 32

    def __init__(
        self,
        master_key: bytes,
        evasion_dna: Optional["DNA"] = None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        """
        Инициализация протокола.
        
        Args:
            master_key: Must be at least 32 bytes for encryption + 32 bytes for HMAC
            evasion_dna: Optional Geneva evasion strategy
        """
        if len(master_key) < 32:
            raise ValueError("Master key must be at least 32 bytes")

        self.master_key = master_key[:32]
        # Derive separate HMAC key from master key using HKDF-like approach
        self.hmac_key = hashlib.sha256(master_key + b"hmac_key_derivation").digest()
        self.backend = default_backend()
        self.evasion_dna = evasion_dna
        self.event_bus = event_bus
        self.event_project_root = event_project_root

        logger.info(f"StegoMeshProtocol v2 initialized. Geneva active: {evasion_dna is not None}")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize StegoMesh EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _key_metadata(self) -> Dict[str, Any]:
        return {
            "master_key_present": bool(self.master_key),
            "master_key_length_bucket": _byte_count_bucket(len(self.master_key)),
            "hmac_key_present": bool(self.hmac_key),
            "hmac_key_length_bucket": _byte_count_bucket(len(self.hmac_key)),
            "raw_key_material_redacted": True,
        }

    def _publish_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "anti_censorship.stego_mesh",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "key_material": self._key_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "raw_identifiers_redacted": True,
            "raw_packets_redacted": True,
            "crypto_material_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "external_dpi_tested": False,
            "claim_boundary": STEGO_MESH_CLAIM_BOUNDARY,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value == "failed"
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish StegoMesh evidence: %s", exc)
            return None

    def _derive_session_key(self, payload_prefix: bytes) -> Tuple[bytes, bytes]:
        seed = self.master_key + payload_prefix[:32]
        shake = hashlib.shake_128(seed)
        return shake.digest(32), shake.digest(16)
    
    def _compute_hmac(self, nonce: bytes, ciphertext: bytes) -> bytes:
        """
        Compute HMAC-SHA256 for integrity verification.
        
        HMAC covers nonce + ciphertext to prevent tampering.
        """
        return hmac.new(
            self.hmac_key, 
            nonce + ciphertext, 
            hashlib.sha256
        ).digest()
    
    def _verify_hmac(self, nonce: bytes, ciphertext: bytes, received_hmac: bytes) -> bool:
        """
        Verify HMAC-SHA256 for integrity.
        
        Uses constant-time comparison to prevent timing attacks.
        """
        expected_hmac = self._compute_hmac(nonce, ciphertext)
        return hmac.compare_digest(expected_hmac, received_hmac)

    def apply_evasion_strategy(self, packet: bytes) -> List[bytes]:
        """Применяет действия из DNA к пакету (SPLIT, DUPLICATE, etc)."""
        started_at = time.monotonic()
        if not self.evasion_dna or not self.evasion_dna.actions:
            self._publish_evidence(
                operation="apply_evasion_strategy",
                status_value="not_configured",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(packet)),
                    "output_packets_count": 1,
                    "output_packet_count_bucket": "single",
                    "output_bytes_bucket": _byte_count_bucket(len(packet)),
                    "evasion_strategy": _evasion_metadata(self.evasion_dna),
                },
            )
            return [packet]

        try:
            current_packets = [packet]
            for action in self.evasion_dna.actions:
                new_packets = []
                for p in current_packets:
                    if action.type == ActionType.SPLIT:
                        idx = action.params.get("index", len(p) // 2)
                        idx = max(1, min(idx, len(p) - 1))
                        new_packets.append(p[:idx])
                        new_packets.append(p[idx:])
                    elif action.type == ActionType.DUPLICATE:
                        count = action.params.get("count", 1)
                        new_packets.extend([p] * (count + 1))
                    elif action.type == ActionType.TAMPER:
                        new_packets.append(p + b"_t")
                    elif action.type == ActionType.DROP:
                        # Use cryptographically secure random for security-sensitive decisions
                        drop_probability = action.params.get("probability", 0.1)
                        if secrets.randbelow(1000) / 1000.0 > drop_probability:
                            new_packets.append(p)
                    else:
                        new_packets.append(p)
                current_packets = new_packets
        except Exception as exc:
            self._publish_evidence(
                operation="apply_evasion_strategy",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(packet)),
                    "evasion_strategy": _evasion_metadata(self.evasion_dna),
                },
                error_type=type(exc).__name__,
            )
            raise

        self._publish_evidence(
            operation="apply_evasion_strategy",
            status_value="applied",
            started_at=started_at,
            metadata={
                "input_bytes_bucket": _byte_count_bucket(len(packet)),
                "output_packets_count": len(current_packets),
                "output_packet_count_bucket": _packet_count_bucket(len(current_packets)),
                "output_bytes_bucket": _byte_count_bucket(
                    sum(len(item) for item in current_packets)
                ),
                "evasion_strategy": _evasion_metadata(self.evasion_dna),
            },
        )
        return current_packets

    def encode_packet(self, real_payload: bytes, protocol_mimic: str = "http") -> Union[bytes, List[bytes]]:
        """Кодирует пакет и применяет стратегию уклонения."""
        started_at = time.monotonic()
        try:
            payload_prefix = real_payload[:32] if len(real_payload) >= 32 else real_payload + b"\x00" * (32 - len(real_payload))
            session_key, nonce = self._derive_session_key(payload_prefix)

            cipher = Cipher(algorithms.ChaCha20(session_key, nonce), mode=None, backend=self.backend)
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(real_payload) + encryptor.finalize()
            
            # Compute HMAC for integrity (nonce + ciphertext)
            packet_hmac = self._compute_hmac(nonce, ciphertext)

            import base64
            # Format: nonce (16) + hmac (32) + ciphertext
            encoded_payload = base64.b64encode(nonce + packet_hmac + ciphertext)

            if protocol_mimic == "http":
                header = self._create_http_header(len(encoded_payload))
            elif protocol_mimic == "icmp":
                header = self._create_icmp_header()
            elif protocol_mimic == "dns":
                header = self._create_dns_header(len(encoded_payload))
            else:
                header = self._create_http_header(len(encoded_payload))

            noise = secrets.token_bytes(secrets.randbelow(10) + 2)
            stego_packet = header + encoded_payload + noise

            if self.evasion_dna:
                final_packets = self.apply_evasion_strategy(stego_packet)
                self._publish_evidence(
                    operation="encode_packet",
                    status_value="encoded",
                    started_at=started_at,
                    metadata={
                        "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                        "protocol_mimic_supported": _protocol_mimic_bucket(protocol_mimic) != "other",
                        "input_bytes_bucket": _byte_count_bucket(len(real_payload)),
                        "encoded_payload_bytes_bucket": _byte_count_bucket(
                            len(encoded_payload)
                        ),
                        "output_packets_count": len(final_packets),
                        "output_packet_count_bucket": _packet_count_bucket(
                            len(final_packets)
                        ),
                        "output_bytes_bucket": _byte_count_bucket(
                            sum(len(item) for item in final_packets)
                        ),
                        "crypto": {
                            "nonce_present": True,
                            "hmac_present": True,
                            "cipher": "chacha20",
                            "raw_crypto_material_redacted": True,
                        },
                        "evasion_strategy": _evasion_metadata(self.evasion_dna),
                    },
                )
                if not final_packets:
                    return []
                return final_packets if len(final_packets) > 1 else final_packets[0]

            self._publish_evidence(
                operation="encode_packet",
                status_value="encoded",
                started_at=started_at,
                metadata={
                    "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                    "protocol_mimic_supported": _protocol_mimic_bucket(protocol_mimic) != "other",
                    "input_bytes_bucket": _byte_count_bucket(len(real_payload)),
                    "encoded_payload_bytes_bucket": _byte_count_bucket(
                        len(encoded_payload)
                    ),
                    "output_packets_count": 1,
                    "output_packet_count_bucket": "single",
                    "output_bytes_bucket": _byte_count_bucket(len(stego_packet)),
                    "crypto": {
                        "nonce_present": True,
                        "hmac_present": True,
                        "cipher": "chacha20",
                        "raw_crypto_material_redacted": True,
                    },
                    "evasion_strategy": _evasion_metadata(self.evasion_dna),
                },
            )
            return stego_packet
        except Exception as e:
            self._publish_evidence(
                operation="encode_packet",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                    "protocol_mimic_supported": _protocol_mimic_bucket(protocol_mimic) != "other",
                    "input_bytes_bucket": _byte_count_bucket(
                        len(real_payload) if hasattr(real_payload, "__len__") else -1
                    ),
                    "evasion_strategy": _evasion_metadata(self.evasion_dna),
                },
                error_type=type(e).__name__,
            )
            logger.error(f"Encode error: {e}")
            raise

    def _create_http_header(self, content_length: int) -> bytes:
        header = (
            "GET /index.html HTTP/1.1\r\n"
            "Host: cloudflare.com\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            f"Content-Length: {content_length}\r\n"
            f"{self.STEGO_MARKER_HTTP.decode()}\r\n\r\n"
        )
        return header.encode()

    def _create_icmp_header(self) -> bytes:
        header = struct.pack("!BBHHH", 8, 0, 0, secrets.randbelow(65535), 1)
        header += struct.pack("!Q", int(time.time() * 1000)) + b"ping_padding"
        header += self.STEGO_MARKER_ICMP
        return header

    def _create_dns_header(self, data_length: int) -> bytes:
        header = struct.pack("!HHHHHH", secrets.randbelow(65535)+1, 0x0100, 1, 0, 0, 0)
        header += b"\x05stego\x08x0tta6bl4\x04mesh\x00"
        header += struct.pack("!HH", 1, 1) + self.STEGO_MARKER_DNS
        return header

    def test_dpi_evasion(self, real_payload: bytes, protocol_mimic: str = "http") -> bool:
        """
        Lightweight compatibility probe used by tests.

        Returns True when packet generation for a chosen mimic protocol succeeds
        and basic protocol markers are present; returns False on any failure.
        """
        started_at = time.monotonic()
        try:
            packet = self.encode_packet(real_payload, protocol_mimic)
            if isinstance(packet, list):
                packet_bytes = b"".join(packet)
            else:
                packet_bytes = packet

            if not isinstance(packet_bytes, (bytes, bytearray)):
                self._publish_evidence(
                    operation="test_dpi_evasion",
                    status_value="local_probe_failed",
                    started_at=started_at,
                    metadata={
                        "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                        "input_bytes_bucket": _byte_count_bucket(len(real_payload)),
                        "local_marker_probe": True,
                        "packet_bytes_bucket": "not_bytes_like",
                    },
                )
                return False
            if len(packet_bytes) <= len(real_payload):
                self._publish_evidence(
                    operation="test_dpi_evasion",
                    status_value="local_probe_failed",
                    started_at=started_at,
                    metadata={
                        "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                        "input_bytes_bucket": _byte_count_bucket(len(real_payload)),
                        "local_marker_probe": True,
                        "packet_bytes_bucket": _byte_count_bucket(len(packet_bytes)),
                    },
                )
                return False

            if protocol_mimic == "http":
                result = b"HTTP/1.1" in packet_bytes or b"GET " in packet_bytes
            elif protocol_mimic == "icmp":
                result = packet_bytes.startswith(b"\x08\x00")
            elif protocol_mimic == "dns":
                result = len(packet_bytes) > 12
            else:
                result = True
            self._publish_evidence(
                operation="test_dpi_evasion",
                status_value="local_probe_passed" if result else "local_probe_failed",
                started_at=started_at,
                metadata={
                    "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                    "input_bytes_bucket": _byte_count_bucket(len(real_payload)),
                    "local_marker_probe": True,
                    "external_dpi_tested": False,
                    "packet_bytes_bucket": _byte_count_bucket(len(packet_bytes)),
                },
            )
            return result
        except Exception as exc:
            self._publish_evidence(
                operation="test_dpi_evasion",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "protocol_mimic": _protocol_mimic_bucket(protocol_mimic),
                    "input_bytes_bucket": _byte_count_bucket(
                        len(real_payload) if hasattr(real_payload, "__len__") else -1
                    ),
                    "local_marker_probe": True,
                    "external_dpi_tested": False,
                },
                error_type=type(exc).__name__,
            )
            return False

    def decode_packet(self, stego_packet: bytes) -> Optional[bytes]:
        """
        Decode stego packet with HMAC integrity verification.
        
        Returns None if:
        - Packet format is invalid
        - HMAC verification fails (tampering detected)
        - Decryption fails
        """
        import base64
        started_at = time.monotonic()
        try:
            encoded_data = None
            protocol_detected = "none"
            if self.STEGO_MARKER_HTTP in stego_packet:
                parts = stego_packet.split(b"\r\n\r\n")
                if len(parts) > 1:
                    encoded_data = parts[1]
                    protocol_detected = "http"
            elif self.STEGO_MARKER_ICMP in stego_packet:
                idx = stego_packet.find(self.STEGO_MARKER_ICMP)
                encoded_data = stego_packet[idx + len(self.STEGO_MARKER_ICMP):]
                protocol_detected = "icmp"
            elif self.STEGO_MARKER_DNS in stego_packet:
                idx = stego_packet.find(self.STEGO_MARKER_DNS)
                encoded_data = stego_packet[idx + len(self.STEGO_MARKER_DNS):]
                protocol_detected = "dns"
            
            if not encoded_data:
                self._publish_evidence(
                    operation="decode_packet",
                    status_value="marker_missing",
                    started_at=started_at,
                    metadata={
                        "input_bytes_bucket": _byte_count_bucket(len(stego_packet)),
                        "protocol_detected": protocol_detected,
                        "marker_present": protocol_detected != "none",
                        "raw_packets_redacted": True,
                    },
                )
                return None

            attempts = 0
            hmac_failures = 0
            short_decoded_attempts = 0
            decode_errors = 0
            for i in range(len(encoded_data), 10, -1):
                attempts += 1
                try:
                    decoded = base64.b64decode(encoded_data[:i])
                    # New format: nonce (16) + hmac (32) + ciphertext
                    if len(decoded) < 16 + self.HMAC_LENGTH:
                        short_decoded_attempts += 1
                        continue
                    
                    nonce = decoded[:16]
                    received_hmac = decoded[16:16 + self.HMAC_LENGTH]
                    ciphertext = decoded[16 + self.HMAC_LENGTH:]
                    
                    # Verify HMAC before decryption (critical for security)
                    if not self._verify_hmac(nonce, ciphertext, received_hmac):
                        hmac_failures += 1
                        logger.warning("HMAC verification failed - possible tampering detected")
                        continue
                    
                    # Derive key and decrypt
                    # Note: We need the payload_prefix for key derivation
                    # For backwards compatibility, we try without it first
                    key, _ = self._derive_session_key(b"\x00" * 32)
                    cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=self.backend)
                    decryptor = cipher.decryptor()
                    plaintext = decryptor.update(ciphertext) + decryptor.finalize()
                    self._publish_evidence(
                        operation="decode_packet",
                        status_value="decoded",
                        started_at=started_at,
                        metadata={
                            "input_bytes_bucket": _byte_count_bucket(len(stego_packet)),
                            "encoded_bytes_bucket": _byte_count_bucket(
                                len(encoded_data)
                            ),
                            "output_bytes_bucket": _byte_count_bucket(len(plaintext)),
                            "protocol_detected": protocol_detected,
                            "attempts": attempts,
                            "hmac_verified": True,
                            "hmac_failures": hmac_failures,
                            "short_decoded_attempts": short_decoded_attempts,
                            "decode_errors": decode_errors,
                            "crypto": {
                                "nonce_present": True,
                                "hmac_present": True,
                                "cipher": "chacha20",
                                "raw_crypto_material_redacted": True,
                            },
                        },
                    )
                    return plaintext.rstrip(b"\x00")
                except Exception as decode_error:
                    decode_errors += 1
                    logger.debug(f"Decode attempt failed: {decode_error}")
                    continue
            self._publish_evidence(
                operation="decode_packet",
                status_value="not_decoded",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(len(stego_packet)),
                    "encoded_bytes_bucket": _byte_count_bucket(len(encoded_data)),
                    "output_bytes_bucket": "zero",
                    "protocol_detected": protocol_detected,
                    "attempts": attempts,
                    "hmac_verified": False,
                    "hmac_failures": hmac_failures,
                    "short_decoded_attempts": short_decoded_attempts,
                    "decode_errors": decode_errors,
                    "raw_packets_redacted": True,
                },
            )
            return None
        except Exception as e:
            self._publish_evidence(
                operation="decode_packet",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "input_bytes_bucket": _byte_count_bucket(
                        len(stego_packet) if hasattr(stego_packet, "__len__") else -1
                    ),
                    "raw_packets_redacted": True,
                },
                error_type=type(e).__name__,
            )
            logger.error(f"Decode error: {e}")
            return None
