"""First-party anti-DPI profile helpers for x0tta6bl4 VPN."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from .fragmentation import PacketFragmenter
from .protocol import MAX_PAYLOAD_BYTES


GenevaActionName = Literal["split", "duplicate", "tamper", "drop"]


class AntiDpiProfileError(ValueError):
    """Raised when a first-party anti-DPI profile is invalid."""


@dataclass(frozen=True)
class FirstPartyGenevaAction:
    """One Geneva-style packet shaping action.

    Only ``split`` is safe for the first-party VPN TUN path. Other Geneva-style
    actions are tracked in the profile but ignored by default because they can
    corrupt an authenticated VPN stream.
    """

    action: GenevaActionName
    value: int | None = None

    def __post_init__(self) -> None:
        if self.action not in ("split", "duplicate", "tamper", "drop"):
            raise AntiDpiProfileError("Geneva action is invalid")
        if self.value is not None and self.value < 1:
            raise AntiDpiProfileError("Geneva action value must be positive")

    def to_json_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"action": self.action}
        if self.value is not None:
            payload["value"] = self.value
        return payload

    @classmethod
    def from_json_dict(cls, payload: dict[str, object]) -> "FirstPartyGenevaAction":
        value = payload.get("value")
        return cls(
            action=str(payload.get("action", "split")),  # type: ignore[arg-type]
            value=None if value is None else int(value),
        )


@dataclass(frozen=True)
class FirstPartyGenevaStrategy:
    """Safe Geneva-style shaping policy for first-party VPN payloads."""

    enabled: bool = True
    actions: tuple[FirstPartyGenevaAction, ...] = field(
        default_factory=lambda: (FirstPartyGenevaAction("split", 512),)
    )
    allow_unsafe_actions: bool = False
    min_fragment_payload_size: int = 64

    def __post_init__(self) -> None:
        if self.min_fragment_payload_size < 32:
            raise AntiDpiProfileError("minimum fragment payload size is too small")
        for action in self.actions:
            if not isinstance(action, FirstPartyGenevaAction):
                raise AntiDpiProfileError("Geneva strategy action is invalid")

    @property
    def unsafe_action_names(self) -> tuple[str, ...]:
        if self.allow_unsafe_actions:
            return ()
        return tuple(
            action.action
            for action in self.actions
            if action.action in ("duplicate", "tamper", "drop")
        )

    def selected_fragment_payload_size(self, default_size: int = 512) -> int:
        """Return a safe fragment size derived from enabled split actions."""

        if not self.enabled:
            raise AntiDpiProfileError("Geneva strategy is disabled")
        selected = int(default_size)
        for action in self.actions:
            if action.action == "split" and action.value is not None:
                selected = int(action.value)
        return max(
            self.min_fragment_payload_size,
            min(selected, MAX_PAYLOAD_BYTES),
        )

    def fragmenter(self, default_size: int = 512) -> PacketFragmenter:
        return PacketFragmenter(
            max_payload_size=self.selected_fragment_payload_size(default_size)
        )

    def to_json_dict(self) -> dict[str, object]:
        return {
            "actions": [action.to_json_dict() for action in self.actions],
            "allow_unsafe_actions": self.allow_unsafe_actions,
            "enabled": self.enabled,
            "ignored_unsafe_actions": list(self.unsafe_action_names),
            "min_fragment_payload_size": self.min_fragment_payload_size,
            "selected_fragment_payload_size": (
                self.selected_fragment_payload_size() if self.enabled else None
            ),
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, object]) -> "FirstPartyGenevaStrategy":
        raw_actions = payload.get("actions") or ()
        if not isinstance(raw_actions, (list, tuple)):
            raise AntiDpiProfileError("Geneva actions must be a list")
        return cls(
            enabled=bool(payload.get("enabled", True)),
            actions=tuple(
                FirstPartyGenevaAction.from_json_dict(item)
                for item in raw_actions
                if isinstance(item, dict)
            )
            or (FirstPartyGenevaAction("split", 512),),
            allow_unsafe_actions=bool(payload.get("allow_unsafe_actions", False)),
            min_fragment_payload_size=int(
                payload.get("min_fragment_payload_size", 64)
            ),
        )


@dataclass(frozen=True)
class FirstPartyAntiDpiProfile:
    """Anti-DPI settings that can be carried inside first-party VPN configs."""

    enabled: bool = True
    profile_id: str = "x0vpn-anti-dpi-v1"
    transport: Literal["tcp", "camouflage"] = "camouflage"
    geneva: FirstPartyGenevaStrategy = field(default_factory=FirstPartyGenevaStrategy)
    tesla_enabled: bool = True
    tesla_slot_seconds: int = 60
    tesla_disclosure_delay_slots: int = 1

    def __post_init__(self) -> None:
        if self.transport not in ("tcp", "camouflage"):
            raise AntiDpiProfileError("anti-DPI transport is invalid")
        if not self.profile_id.strip():
            raise AntiDpiProfileError("anti-DPI profile id is required")
        if self.tesla_slot_seconds < 1:
            raise AntiDpiProfileError("TESLA slot seconds must be positive")
        if self.tesla_disclosure_delay_slots < 1:
            raise AntiDpiProfileError("TESLA disclosure delay must be positive")

    def fragmenter(self) -> PacketFragmenter | None:
        if not self.enabled or not self.geneva.enabled:
            return None
        return self.geneva.fragmenter()

    def to_json_dict(self) -> dict[str, object]:
        return {
            "enabled": self.enabled,
            "profile_id": self.profile_id,
            "transport": self.transport,
            "camouflage": {"enabled": self.transport == "camouflage"},
            "geneva": self.geneva.to_json_dict(),
            "tesla": {
                "enabled": self.tesla_enabled,
                "slot_seconds": self.tesla_slot_seconds,
                "disclosure_delay_slots": self.tesla_disclosure_delay_slots,
            },
        }

    @classmethod
    def from_json_dict(cls, payload: dict[str, object]) -> "FirstPartyAntiDpiProfile":
        geneva_payload = payload.get("geneva") or {}
        if not isinstance(geneva_payload, dict):
            raise AntiDpiProfileError("anti-DPI Geneva profile must be an object")
        tesla_payload = payload.get("tesla") or {}
        if not isinstance(tesla_payload, dict):
            raise AntiDpiProfileError("anti-DPI TESLA profile must be an object")
        return cls(
            enabled=bool(payload.get("enabled", True)),
            profile_id=str(payload.get("profile_id", "x0vpn-anti-dpi-v1")),
            transport=str(payload.get("transport", "camouflage")),  # type: ignore[arg-type]
            geneva=FirstPartyGenevaStrategy.from_json_dict(geneva_payload),
            tesla_enabled=bool(tesla_payload.get("enabled", True)),
            tesla_slot_seconds=int(tesla_payload.get("slot_seconds", 60)),
            tesla_disclosure_delay_slots=int(
                tesla_payload.get("disclosure_delay_slots", 1)
            ),
        )
