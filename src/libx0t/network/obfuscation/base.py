"""
Obfuscation Layer for x0tta6bl4 Mesh Network.
Provides pluggable transport obfuscation to bypass DPI (Deep Packet Inspection).
"""
from __future__ import annotations

import socket
import hashlib
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from src.core.thinking.agent_thinking import AgentThinkingCoach

_SERVICE_AGENT = "libx0t-network-obfuscation-transport"
_KNOWN_TRANSPORT_NAMES = frozenset(
    {"xor", "faketls", "shadowsocks", "domain_fronting"}
)
_SECRET_KWARG_NAMES = frozenset(
    {"api_key", "key", "password", "private_key", "secret", "token", "uuid"}
)
_NETWORK_SELECTOR_KWARG_NAMES = frozenset(
    {"cdn_domain", "domain", "front_domain", "host", "server", "sni"}
)
OBFUSCATION_TRANSPORT_CLAIM_BOUNDARY = (
    "Local libx0t obfuscation transport factory evidence only. It records "
    "transport constructor success/failure and redacted option-shape metadata; "
    "it does not prove DPI bypass, censorship bypass, remote reachability, "
    "packet delivery, provider health, client installation, or production "
    "customer traffic use."
)
_TRANSPORT_THINKING_COACH = AgentThinkingCoach(
    agent_id=_SERVICE_AGENT,
    role="security",
    capabilities=("zero-trust", "ops", "network"),
    extra_techniques=("weighted_decision_matrix",),
)
_LAST_TRANSPORT_THINKING_CONTEXT: Dict[str, Any] = {}


def _sha256_text(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _transport_name_bucket(name: str) -> str:
    if not name:
        return "empty"
    if name in _KNOWN_TRANSPORT_NAMES:
        return name
    return "custom"


def _constructor_kwargs_metadata(kwargs: Dict[str, Any]) -> Dict[str, Any]:
    keys = {str(key) for key in kwargs}
    secret_keys = keys & _SECRET_KWARG_NAMES
    network_selector_keys = keys & _NETWORK_SELECTOR_KWARG_NAMES
    numeric_options = sum(
        1
        for value in kwargs.values()
        if isinstance(value, (int, float)) and not isinstance(value, bool)
    )
    bool_options = sum(1 for value in kwargs.values() if isinstance(value, bool))
    return {
        "fields_total": len(keys),
        "secret_material_present": bool(secret_keys),
        "secret_fields_count": len(secret_keys),
        "network_selector_present": bool(network_selector_keys),
        "network_selector_fields_count": len(network_selector_keys),
        "numeric_options_count": numeric_options,
        "bool_options_count": bool_options,
        "raw_values_redacted": True,
        "field_names_redacted": True,
    }


def _prepare_transport_thinking_context(
    *,
    task_type: str,
    goal: str,
    name: str = "",
    transport_class: Any = None,
    constructor_kwargs: Optional[Dict[str, Any]] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    global _LAST_TRANSPORT_THINKING_CONTEXT
    safe_kwargs = constructor_kwargs or {}
    context: Dict[str, Any] = {
        "task_type": task_type,
        "goal": goal,
        "transport": {
            "name_bucket": _transport_name_bucket(name),
            "name_hash": _sha256_text(name),
            "class_hash": _sha256_text(
                f"{getattr(transport_class, '__module__', '')}."
                f"{getattr(transport_class, '__qualname__', '')}"
            ),
            "registered_transport_count": len(TransportManager._transports),
            "raw_name_redacted": True,
            "raw_class_name_redacted": True,
        },
        "constructor": _constructor_kwargs_metadata(safe_kwargs),
        "constraints": {
            "redact_constructor_values": True,
            "redact_secret_material": True,
            "redact_network_selectors": True,
            "local_factory_only": True,
        },
        "safety_boundary": OBFUSCATION_TRANSPORT_CLAIM_BOUNDARY,
    }
    if extra:
        context.update(extra)
    _LAST_TRANSPORT_THINKING_CONTEXT = _TRANSPORT_THINKING_COACH.prepare_task(context)
    return _LAST_TRANSPORT_THINKING_CONTEXT


def get_transport_thinking_status() -> Dict[str, Any]:
    return {
        "thinking": _TRANSPORT_THINKING_COACH.status(),
        "last_thinking_context": _LAST_TRANSPORT_THINKING_CONTEXT,
        "claim_boundary": OBFUSCATION_TRANSPORT_CLAIM_BOUNDARY,
    }


class ObfuscationTransport(ABC):
    """Abstract base class for obfuscation transports."""

    @abstractmethod
    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        """Wrap a socket with obfuscation layer."""
        pass

    @abstractmethod
    def obfuscate(self, data: bytes) -> bytes:
        """Obfuscate data packet."""
        pass

    @abstractmethod
    def deobfuscate(self, data: bytes) -> bytes:
        """De-obfuscate data packet."""
        pass


class TransportManager:
    """Factory for creating and managing obfuscation transports."""

    _transports = {}

    @classmethod
    def register(cls, name: str, transport_class):
        _prepare_transport_thinking_context(
            task_type="libx0t_obfuscation_transport_register",
            goal="Register local obfuscation transport class without exposing constructor secrets.",
            name=name,
            transport_class=transport_class,
        )
        cls._transports[name] = transport_class

    @classmethod
    def create(cls, name: str, **kwargs) -> Optional[ObfuscationTransport]:
        if name not in cls._transports:
            _prepare_transport_thinking_context(
                task_type="libx0t_obfuscation_transport_not_found",
                goal="Record missing obfuscation transport without exposing requested name.",
                name=name,
                constructor_kwargs=kwargs,
            )
            return None
        transport_class = cls._transports[name]
        try:
            _prepare_transport_thinking_context(
                task_type="libx0t_obfuscation_transport_create",
                goal="Create a registered obfuscation transport with redacted constructor metadata.",
                name=name,
                transport_class=transport_class,
                constructor_kwargs=kwargs,
            )
            transport = transport_class(**kwargs)
        except Exception as exc:
            _prepare_transport_thinking_context(
                task_type="libx0t_obfuscation_transport_create_failed",
                goal="Record obfuscation transport constructor failure with redacted metadata.",
                name=name,
                transport_class=transport_class,
                constructor_kwargs=kwargs,
                extra={"error_type": type(exc).__name__},
            )
            raise
        _prepare_transport_thinking_context(
            task_type="libx0t_obfuscation_transport_created",
            goal="Record created obfuscation transport with redacted constructor metadata.",
            name=name,
            transport_class=transport_class,
            constructor_kwargs=kwargs,
        )
        return transport

    @classmethod
    def get_thinking_status(cls) -> Dict[str, Any]:
        return get_transport_thinking_status()

