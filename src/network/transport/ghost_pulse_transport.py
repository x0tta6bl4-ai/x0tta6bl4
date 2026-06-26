"""
Ghost Pulse Transport — Combined Encryption and Timing Obfuscation
==================================================================

Combines:
1. Ghost Protocol (ChaCha20-Poly1305 + SRTP Mimicry)
2. Ghost Pulse (Deterministic Timing Profiles)

This transport provides both data-level and pattern-level obfuscation.
"""
from __future__ import annotations

import asyncio
import logging
import random
import secrets
import struct
import time
from statistics import mean
from typing import Any, Dict, List, Optional, Union

from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305

from .pulse_transport import PULSE_LOCAL_CLAIM_BOUNDARY, PulseUDPTransport

# Constants
SRTP_HEADER_SIZE = 12
NONCE_SIZE = 12
TAG_SIZE = 16
MIN_PACKET_SIZE = SRTP_HEADER_SIZE + NONCE_SIZE + TAG_SIZE

logger = logging.getLogger("ghost-pulse-transport")

_MODE_PROFILES = {
    "corporate": [
        ("short", 0.012),
        ("meeting", 0.024),
        ("idle", 0.041),
        ("burst-gap", 0.018),
    ],
    "whitelist": [
        ("catalog", 0.032),
        ("cdn", 0.047),
        ("media-gap", 0.071),
        ("idle", 0.095),
    ],
}


def _numeric_summary(values: List[float]) -> Dict[str, Union[float, int, None]]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean": round(mean(values), 6),
    }

class GhostPulseTransport:
    """
    Advanced transport combining AEAD encryption with deterministic timing profiles.
    """

    timing_plan_replay_digest = staticmethod(PulseUDPTransport.timing_plan_replay_digest)
    timing_plan_replay_projection = staticmethod(
        PulseUDPTransport.timing_plan_replay_projection
    )

    def __init__(
        self,
        master_key: bytes,
        mode: str = "corporate",
        pulse_seed: Optional[int] = None
    ):
        if not master_key or len(master_key) != 32:
            raise ValueError("Master key must be 32 bytes")

        self.cipher = ChaCha20Poly1305(master_key)
        self.packet_id = 0

        # Timing state
        self.mode = mode if mode in _MODE_PROFILES else "corporate"
        self.pulse_seed = pulse_seed if pulse_seed is not None else 20260521
        self._pulse_rng = random.Random(f"{self.mode}:{self.pulse_seed}")
        self._profile_index = 0
        self._timing_samples: List[Dict[str, Any]] = []
        self.last_send_ts = 0.0

        logger.info(f"GhostPulseTransport initialized (mode={self.mode}, seed={self.pulse_seed})")

    def wrap_packet(self, payload: bytes) -> bytes:
        """Encrypt and wrap payload with SRTP header mimicry."""
        nonce = secrets.token_bytes(NONCE_SIZE)

        # SRTP Header mimicry
        header = struct.pack(
            "!BBHII",
            0x80,  # Version=2
            111,   # OPUS
            self.packet_id & 0xFFFF,
            self.packet_id * 960,
            0xDEADBEEF,
        )

        ciphertext = self.cipher.encrypt(nonce, payload, header)
        self.packet_id += 1

        return header + nonce + ciphertext

    def unwrap_packet(self, packet: bytes) -> Optional[bytes]:
        """Unwrap and decrypt payload."""
        if len(packet) < MIN_PACKET_SIZE:
            return None

        try:
            header = packet[:SRTP_HEADER_SIZE]
            nonce = packet[SRTP_HEADER_SIZE:SRTP_HEADER_SIZE + NONCE_SIZE]
            ciphertext = packet[SRTP_HEADER_SIZE + NONCE_SIZE:]

            return self.cipher.decrypt(nonce, ciphertext, header)
        except Exception as e:
            logger.debug(f"Decryption failed: {e}")
            return None

    def plan_next_delay(self) -> float:
        """Calculate next deterministic delay based on profile."""
        profiles = _MODE_PROFILES[self.mode]
        profile_label, base_delay = profiles[self._profile_index]

        roll = self._pulse_rng.random()
        mode_shifted = roll < 0.31

        if mode_shifted:
            next_index = self._pulse_rng.randrange(len(profiles))
        else:
            next_index = (self._profile_index + 1) % len(profiles)

        jitter = 0.82 + (self._pulse_rng.random() * 0.36)
        planned_delay = max(0.001, base_delay * jitter)
        self._timing_samples.append(
            {
                "index": len(self._timing_samples) + 1,
                "mode": self.mode,
                "profile_label": profile_label,
                "next_profile_label": profiles[next_index][0],
                "mode_shift_roll": round(roll, 6),
                "mode_shifted": mode_shifted,
                "planned_delay_ms": planned_delay * 1000.0,
            }
        )
        self._profile_index = next_index
        return planned_delay

    async def wait_for_pulse(self):
        """Async wait to match the timing profile."""
        planned_delay = self.plan_next_delay()
        now = time.time()

        if self.last_send_ts > 0:
            elapsed = now - self.last_send_ts
            wait_time = max(0.0, planned_delay - elapsed)
            if wait_time > 0:
                await asyncio.sleep(wait_time)

        self.last_send_ts = time.time()

    def _timing_summary(self) -> Dict[str, Any]:
        planned = [
            float(sample["planned_delay_ms"])
            for sample in self._timing_samples
            if isinstance(sample.get("planned_delay_ms"), (int, float))
        ]
        return {
            "samples_recorded": len(self._timing_samples),
            "planned_delay_ms": _numeric_summary(planned),
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
        }

    def get_stats(self) -> Dict[str, Any]:
        samples = list(self._timing_samples)
        replay = {
            "status": "LOCAL_SEED_REPLAYABLE",
            "seed": self.pulse_seed,
            "mode": self.mode,
            "sample_count": len(samples),
            "sha256": self.timing_plan_replay_digest(samples),
            "projection": self.timing_plan_replay_projection(samples),
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
        }
        return {
            "packets_processed": self.packet_id,
            "mode": self.mode,
            "seed": self.pulse_seed,
            "protocol": "x0tta6bl4_ghost_pulse",
            "evidence_status": "EXPERIMENTAL_LOCAL_TIMING_PROFILE",
            "stealth_mode": "NOT_VERIFIED",
            "timing_plan_samples": samples,
            "timing_plan_samples_tail": samples[-10:],
            "timing_plan_summary": self._timing_summary(),
            "timing_plan_replay": replay,
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY
        }

