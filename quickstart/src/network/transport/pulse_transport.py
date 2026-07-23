"""Deterministic local Ghost Pulse UDP transport.

This module supports repo-local timing evidence only. It can make sender-side
delay plans replayable from a seed, but it does not prove DPI evasion, provider
whitelist behavior, remote reachability, anonymity, or production readiness.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
from statistics import mean
from typing import Any

from .udp_shaped import PeerInfo, ShapedUDPTransport

logger = logging.getLogger(__name__)

PULSE_LOCAL_CLAIM_BOUNDARY = (
    "Ghost Pulse timing plans are deterministic local sender evidence only; "
    "they are not DPI, provider whitelist, remote reachability, anonymity, or "
    "production proof."
)

_REPLAY_FIELDS = (
    "index",
    "mode",
    "profile_label",
    "next_profile_label",
    "mode_shift_roll",
    "mode_shifted",
    "planned_delay_ms",
)
_MODE_PROFILES = {
    "corporate": (
        ("short", 0.012),
        ("meeting", 0.024),
        ("idle", 0.041),
        ("burst-gap", 0.018),
    ),
    "whitelist": (
        ("catalog", 0.032),
        ("cdn", 0.047),
        ("media-gap", 0.071),
        ("idle", 0.095),
    ),
}


def _safe_mode(value: str | None) -> str:
    return value if value in _MODE_PROFILES else "corporate"


def _numeric_summary(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "min": None, "max": None, "mean": None}
    return {
        "count": len(values),
        "min": round(min(values), 6),
        "max": round(max(values), 6),
        "mean": round(mean(values), 6),
    }


class PulseUDPTransport(ShapedUDPTransport):
    """UDP transport with deterministic local timing-plan replay support."""

    def __init__(self, *args: Any, pulse_seed: int | None = None, **kwargs: Any) -> None:
        self.mode = _safe_mode(os.getenv("PULSE_MODE", "corporate").lower())
        self.pulse_seed = int(pulse_seed if pulse_seed is not None else 20260521)
        self._pulse_rng = random.Random(f"{self.mode}:{self.pulse_seed}")
        self._profile_index = 0
        self._timing_samples: list[dict[str, Any]] = []
        self.last_send_ts = 0.0
        self.pulse_packets_sent = 0
        self.pulse_delay_error_total = 0.0
        self.pulse_coherence = 1.0

        if kwargs.get("traffic_profile") == "GHOST_PULSE":
            kwargs["traffic_profile"] = "none"
        else:
            kwargs.setdefault("traffic_profile", "none")
        super().__init__(*args, **kwargs)

    def plan_next_delay(self) -> dict[str, Any]:
        profiles = _MODE_PROFILES[self.mode]
        profile_label, base_delay = profiles[self._profile_index]
        roll = self._pulse_rng.random()
        mode_shifted = roll < 0.31
        next_index = (
            self._pulse_rng.randrange(len(profiles))
            if mode_shifted
            else (self._profile_index + 1) % len(profiles)
        )
        next_profile_label = profiles[next_index][0]
        jitter_factor = 0.82 + (self._pulse_rng.random() * 0.36)
        planned_delay = max(0.001, base_delay * jitter_factor)
        self._profile_index = next_index
        return {
            "mode": self.mode,
            "profile_label": profile_label,
            "next_profile_label": next_profile_label,
            "mode_shift_roll": round(roll, 6),
            "mode_shifted": mode_shifted,
            "planned_delay": planned_delay,
            "planned_delay_ms": planned_delay * 1000.0,
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
        }

    async def send_to(
        self,
        data: bytes,
        address: tuple[str, int],
        reliable: bool = False,
    ) -> bool:
        if not self._socket or not self._running:
            return False

        delay_plan = self.plan_next_delay()
        now = time.time()
        time_since_last = now - self.last_send_ts if self.last_send_ts else 0.0
        wait_time = max(0.0, delay_plan["planned_delay"] - time_since_last)
        if wait_time > 0:
            await asyncio.sleep(wait_time)

        try:
            packet_data = self._prepare_packet(data, requires_ack=reliable)
            previous_send_ts = self.last_send_ts
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._socket.sendto(packet_data, address),
            )
            sent_ts = time.time()
            self.last_send_ts = sent_ts
            self.pulse_packets_sent += 1

            actual_gap = None
            error = None
            if previous_send_ts:
                actual_gap = max(0.0, sent_ts - previous_send_ts)
                error = min(
                    1.0,
                    abs(actual_gap - delay_plan["planned_delay"])
                    / max(delay_plan["planned_delay"], 0.001),
                )
                self.pulse_delay_error_total += error
                self.pulse_coherence = max(
                    0.0,
                    1.0 - (self.pulse_delay_error_total / self.pulse_packets_sent),
                )

            self._record_timing_sample(
                planned_delay=delay_plan["planned_delay"],
                wait_time=wait_time,
                actual_gap=actual_gap,
                error=error,
                profile_label=delay_plan["profile_label"],
                payload_size=len(data),
                mode_shift_roll=delay_plan["mode_shift_roll"],
                mode_shifted=delay_plan["mode_shifted"],
                next_profile_label=delay_plan["next_profile_label"],
            )

            if address not in self._peers:
                self._peers[address] = PeerInfo(address=address)
            self._peers[address].packets_sent += 1
            self._peers[address].last_seen = sent_ts
            self._total_sent += 1
            self._analyzer.record_packet(len(packet_data))
            return True
        except Exception as exc:
            logger.error("Pulse UDP send failed for %s: %s", address, exc)
            return False

    def _record_timing_sample(
        self,
        *,
        planned_delay: float,
        wait_time: float,
        actual_gap: float | None,
        error: float | None,
        profile_label: str,
        payload_size: int,
        mode_shift_roll: float,
        mode_shifted: bool,
        next_profile_label: str,
    ) -> None:
        self._timing_samples.append(
            {
                "index": len(self._timing_samples) + 1,
                "mode": self.mode,
                "profile_label": profile_label,
                "next_profile_label": next_profile_label,
                "mode_shift_roll": mode_shift_roll,
                "mode_shifted": mode_shifted,
                "planned_delay_ms": planned_delay * 1000.0,
                "wait_time_ms": wait_time * 1000.0,
                "actual_gap_ms": actual_gap * 1000.0 if actual_gap is not None else None,
                "relative_error": error,
                "payload_size_bytes": payload_size,
            }
        )

    @staticmethod
    def timing_plan_replay_digest(samples: list[dict[str, Any]]) -> str:
        normalized = [
            {
                key: (
                    round(float(sample[key]), 6)
                    if key in {"mode_shift_roll", "planned_delay_ms"}
                    and sample.get(key) is not None
                    else sample.get(key)
                )
                for key in _REPLAY_FIELDS
            }
            for sample in samples
        ]
        encoded = json.dumps(
            normalized,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()

    @staticmethod
    def timing_plan_replay_projection(samples: list[dict[str, Any]]) -> dict[str, Any]:
        planned = [
            float(sample["planned_delay_ms"])
            for sample in samples
            if isinstance(sample.get("planned_delay_ms"), (int, float))
        ]
        return {
            "sample_count": len(samples),
            "modes": sorted({str(sample.get("mode")) for sample in samples}),
            "profile_labels": sorted(
                {str(sample.get("profile_label")) for sample in samples}
            ),
            "planned_delay_ms": _numeric_summary(planned),
            "sha256": PulseUDPTransport.timing_plan_replay_digest(samples),
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
        }

    def _timing_summary(self) -> dict[str, Any]:
        planned = [
            float(sample["planned_delay_ms"])
            for sample in self._timing_samples
            if isinstance(sample.get("planned_delay_ms"), (int, float))
        ]
        actual = [
            float(sample["actual_gap_ms"])
            for sample in self._timing_samples
            if isinstance(sample.get("actual_gap_ms"), (int, float))
        ]
        error = [
            float(sample["relative_error"])
            for sample in self._timing_samples
            if isinstance(sample.get("relative_error"), (int, float))
        ]
        return {
            "samples_recorded": len(self._timing_samples),
            "planned_delay_ms": _numeric_summary(planned),
            "actual_gap_ms": _numeric_summary(actual),
            "relative_error": _numeric_summary(error),
            "coherence": round(self.pulse_coherence, 6),
            "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
        }

    def get_stats(self) -> dict[str, Any]:
        stats = super().get_stats()
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
        stats.update(
            {
                "pulse_mode": self.mode,
                "pulse_rng_seed": self.pulse_seed,
                "pulse_packets_sent": self.pulse_packets_sent,
                "pulse_coherence": round(self.pulse_coherence, 6),
                "protocol": "x0tta6bl4_pulse",
                "evidence_status": "EXPERIMENTAL_LOCAL_TIMING_PROFILE",
                "stealth_mode": "NOT_VERIFIED",
                "timing_plan_samples": samples,
                "timing_plan_samples_tail": samples[-10:],
                "timing_plan_summary": self._timing_summary(),
                "timing_plan_replay": replay,
                "claim_boundary": PULSE_LOCAL_CLAIM_BOUNDARY,
            }
        )
        return stats
