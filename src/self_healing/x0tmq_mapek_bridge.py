"""
x0tta6bl4 x0tMQ + PQC + SPIRE + MAPE-K Bridge.
=================================================

Provides end-to-end integration between:
1. x0tMQ Post-Quantum MAVLink v2 messaging protocol (IETF Draft).
2. PQC Encryption Core (NIST FIPS 203 ML-KEM-768 & FIPS 204 ML-DSA-65).
3. Zero-Trust SPIFFE/SPIRE SVID authentication (`SVIDSigner`).
4. MAPE-K Self-Healing Manager (`SelfHealingManager`).

Compliance: Chief Engineer Mandate & 3-Tier Status Taxonomy.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, Optional

from src.security.pqc import (
    PQCKeyExchange,
    PQCDigitalSignature,
    is_liboqs_available,
)
from src.self_healing.svid_signer import SVIDSigner

logger = logging.getLogger(__name__)

X0TMQ_MAPE_K_MAGIC = 0x5830544D  # "X0TM"


@dataclass
class X0tMQMAPEKFrame:
    """Post-quantum protected x0tMQ message frame for MAPE-K loop telemetry and control."""

    magic: int
    sender_spiffe_id: str
    recipient_spiffe_id: str
    payload_type: str  # "TELEMETRY", "ANOMALY_REPORT", "HEALING_PLAN", "EXECUTE_ACTION"
    payload_json: str
    timestamp_utc: float
    pqc_signature_b64: str
    svid_signature: str
    svid_signature_ts: float
    svid_signer: str
    svid_schema: str


class X0tMQMAPEKBridge:
    """Bridge connecting x0tMQ PQC transport to MAPE-K Self-Healing Loop."""

    def __init__(self, spiffe_id: str = "spiffe://x0tta6bl4.mesh/node/default", mode: str = "dev"):
        self.spiffe_id = spiffe_id
        self.mode = mode
        self.svid_signer = SVIDSigner(spiffe_id=spiffe_id, mode=mode)
        self.pqc_kem = PQCKeyExchange()
        self.pqc_dsa = PQCDigitalSignature()
        self.keypair = self.pqc_dsa.generate_keypair()

    def pack_mapek_frame(
        self,
        recipient_spiffe_id: str,
        payload_type: str,
        payload_data: Dict[str, Any],
    ) -> X0tMQMAPEKFrame:
        """Encapsulate MAPE-K data into an x0tMQ PQC-signed frame."""
        timestamp = time.time()
        payload_json = json.dumps(payload_data, sort_keys=True)

        # 1. Sign with PQC ML-DSA-65
        sign_payload = f"{self.spiffe_id}:{recipient_spiffe_id}:{payload_type}:{payload_json}:{timestamp}".encode("utf-8")
        pqc_sig = self.pqc_dsa.sign(sign_payload, self.keypair.secret_key)
        raw_sig = getattr(pqc_sig, "signature_bytes", pqc_sig)
        if isinstance(raw_sig, bytes):
            pqc_signature_bytes = raw_sig
        else:
            pqc_signature_bytes = str(raw_sig).encode("utf-8")
        import base64
        pqc_sig_b64 = base64.b64encode(pqc_signature_bytes).decode("utf-8")

        # 2. Sign with SVIDSigner (HMAC or JWT)
        raw_msg = {
            "magic": X0TMQ_MAPE_K_MAGIC,
            "sender_spiffe_id": self.spiffe_id,
            "recipient_spiffe_id": recipient_spiffe_id,
            "payload_type": payload_type,
            "payload_json": payload_json,
            "timestamp_utc": timestamp,
            "pqc_signature_b64": pqc_sig_b64,
        }
        signed_msg = self.svid_signer.sign_payload(raw_msg)

        return X0tMQMAPEKFrame(
            magic=X0TMQ_MAPE_K_MAGIC,
            sender_spiffe_id=self.spiffe_id,
            recipient_spiffe_id=recipient_spiffe_id,
            payload_type=payload_type,
            payload_json=payload_json,
            timestamp_utc=timestamp,
            pqc_signature_b64=pqc_sig_b64,
            svid_signature=signed_msg.get("svid_signature", ""),
            svid_signature_ts=signed_msg.get("svid_signature_ts", timestamp),
            svid_signer=signed_msg.get("svid_signer", self.spiffe_id),
            svid_schema=signed_msg.get("svid_schema", ""),
        )

    def unpack_and_verify_frame(self, frame: X0tMQMAPEKFrame) -> tuple[bool, Dict[str, Any]]:
        """Verify SPIRE SVID and PQC ML-DSA signature on incoming x0tMQ frame."""
        if frame.magic != X0TMQ_MAPE_K_MAGIC:
            logger.error("❌ Invalid x0tMQ magic header: 0x%X", frame.magic)
            return False, {}

        # 1. Verify SPIRE SVID signature
        msg_dict = asdict(frame)
        svid_valid = self.svid_signer.verify_payload(msg_dict, expected_spiffe_id=frame.sender_spiffe_id)
        if not svid_valid:
            logger.error("❌ SVID verification failed for sender: %s", frame.sender_spiffe_id)
            return False, {}

        # 2. Verify PQC ML-DSA signature
        import base64
        try:
            sig_bytes = base64.b64decode(frame.pqc_signature_b64)
            sign_payload = f"{frame.sender_spiffe_id}:{frame.recipient_spiffe_id}:{frame.payload_type}:{frame.payload_json}:{frame.timestamp_utc}".encode("utf-8")
            pqc_valid = self.pqc_dsa.verify(sign_payload, sig_bytes, self.keypair.public_key)
        except Exception as exc:
            logger.error("❌ PQC ML-DSA verification exception: %s", exc)
            pqc_valid = False

        if not pqc_valid:
            logger.error("❌ PQC ML-DSA signature verification failed for sender: %s", frame.sender_spiffe_id)
            return False, {}

        payload_data = json.loads(frame.payload_json)
        return True, payload_data


def process_x0tmq_mapek_cycle(node_id: str = "default") -> dict:
    """Execute one integrated x0tMQ + PQC + SPIRE + MAPE-K cycle."""
    bridge = X0tMQMAPEKBridge(spiffe_id=f"spiffe://x0tta6bl4.mesh/node/{node_id}")

    # Pack telemetry
    telemetry_data = {"cpu_load": 12.5, "latency_ms": 42.1, "packet_loss": 0.0}
    frame = bridge.pack_mapek_frame(
        recipient_spiffe_id="spiffe://x0tta6bl4.mesh/node/nl-gateway",
        payload_type="TELEMETRY",
        payload_data=telemetry_data,
    )

    # Unpack and verify
    valid, unpacked_data = bridge.unpack_and_verify_frame(frame)

    return {
        "node_id": node_id,
        "x0tmq_magic_valid": frame.magic == X0TMQ_MAPE_K_MAGIC,
        "spiffe_verified": valid,
        "pqc_liboqs_active": is_liboqs_available(),
        "unpacked_data": unpacked_data,
    }
