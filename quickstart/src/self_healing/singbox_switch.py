"""
sing-box clash-api transport switch — Phase 1b actuator
=======================================================

The Phase 1 planner (``dpi_healing_planner``) decides *which* transport to climb
to. This module is the hand that actually flips it, on the client side, with
zero session drop and zero server change.

Mechanism: a dedicated **test** sing-box instance holds the live NL transports
(reality / xhttp / ws → NL:443) as parallel VLESS outbounds behind a
``selector`` outbound, and exposes the clash-api. Switching a transport is one
HTTP call to the selector — sing-box swaps the active outbound without tearing
down the TUN, so an in-flight session survives the switch. Nothing on NL is
touched: xray, x-ui, and the 12 paying users are never in the path.

``ClashApiSelectorBackend`` is a drop-in ``switch_protocol`` backend for
``RecoveryActionExecutor._routing_backend`` / the planner's executor, so the
whole A→P→E chain runs against a real actuator.

Safety: the backend refuses any profile other than the configured throwaway test
profile, and it targets a *separate* sing-box (its own clash-api port + SOCKS
inbound), never the operator's production v2rayN core. See
.claude/rules/50-prod-source-of-truth.md.
"""
from __future__ import annotations

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Protocol


class SwitchBackend(Protocol):
    def switch_protocol(self, protocol: str, mimic: Optional[str] = None, profile: Optional[str] = None) -> bool: ...

# (method, url, json_body|None) -> (status_code, parsed_json|None)
HttpFn = Callable[[str, str, Optional[Dict[str, Any]]], "tuple[int, Optional[Any]]"]


def _urllib_http(method: str, url: str, body: Optional[Dict[str, Any]]) -> "tuple[int, Optional[Any]]":
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=5.0) as resp:  # noqa: S310 - localhost clash-api only
        raw = resp.read()
        parsed = json.loads(raw) if raw else None
        return resp.status, parsed


@dataclass
class TransportRung:
    """One rung of the ladder: a ladder protocol mapped to a sing-box outbound."""

    protocol: str          # ladder name: "reality" | "xhttp" | "ws" | "cf-tunnel"
    outbound_tag: str      # sing-box outbound tag, e.g. "nl-reality"
    server: str
    server_port: int
    uuid: str
    transport_type: str = "reality"  # sing-box stream flavour
    sni: Optional[str] = None
    short_id: Optional[str] = None
    public_key: Optional[str] = None
    ws_path: Optional[str] = None
    host: Optional[str] = None

    def to_singbox_outbound(self) -> Dict[str, Any]:
        """Render this rung as a sing-box VLESS outbound.

        This is a template: fields left ``None`` are omitted so the operator can
        drop in real subscription params without editing every key.
        """
        ob: Dict[str, Any] = {
            "type": "vless",
            "tag": self.outbound_tag,
            "server": self.server,
            "server_port": self.server_port,
            "uuid": self.uuid,
            "flow": "xtls-rprx-vision" if self.transport_type == "reality" else "",
        }
        if self.transport_type == "reality":
            tls: Dict[str, Any] = {"enabled": True, "server_name": self.sni or ""}
            reality: Dict[str, Any] = {"enabled": True}
            if self.public_key:
                reality["public_key"] = self.public_key
            if self.short_id:
                reality["short_id"] = self.short_id
            tls["reality"] = reality
            tls["utls"] = {"enabled": True, "fingerprint": "chrome"}
            ob["tls"] = tls
        elif self.transport_type in ("xhttp", "ws"):
            ob["tls"] = {"enabled": True, "server_name": self.sni or "", "utls": {"enabled": True, "fingerprint": "chrome"}}
            ob["transport"] = {
                "type": "ws" if self.transport_type == "ws" else "xhttp",
                "path": self.ws_path or "/",
                **({"headers": {"Host": self.host}} if self.host else {}),
            }
        return ob


def build_test_singbox_config(
    rungs: List[TransportRung],
    *,
    selector_tag: str = "ghost-test-selector",
    socks_port: int = 10919,
    clash_controller: str = "127.0.0.1:10924",
    default_protocol: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a standalone test sing-box config: 3 transports + selector + clash-api.

    Runs alongside the operator's production v2rayN (different ports), so it
    never disturbs live traffic. The Phase 0 detector points ``--socks`` at
    ``socks_port``; the actuator drives ``clash_controller``.
    """
    if not rungs:
        raise ValueError("at least one transport rung is required")
    tags = [r.outbound_tag for r in rungs]
    default_tag = tags[0]
    if default_protocol:
        for r in rungs:
            if r.protocol == default_protocol:
                default_tag = r.outbound_tag
                break
    return {
        "log": {"level": "warn", "timestamp": True},
        "inbounds": [
            {
                "type": "socks",
                "tag": "socks-test-in",
                "listen": "127.0.0.1",
                "listen_port": socks_port,
            }
        ],
        "outbounds": [
            {
                "type": "selector",
                "tag": selector_tag,
                "outbounds": tags,
                "default": default_tag,
            },
            *[r.to_singbox_outbound() for r in rungs],
            {"type": "direct", "tag": "direct"},
        ],
        "route": {"final": selector_tag},
        "experimental": {"clash_api": {"external_controller": clash_controller}},
    }


class SwitchProtocolExecutor:
    """Adapts a ``switch_protocol`` backend to the planner's ``Executor`` API.

    Lets ``DpiHealingPlanner`` drive a real actuator: it turns the planner's
    ``execute("switch protocol to <p>", context)`` call into
    ``backend.switch_protocol(protocol, mimic, profile)``.
    """

    def __init__(self, backend: "SwitchBackend") -> None:
        self.backend = backend

    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool:
        context = context or {}
        return self.backend.switch_protocol(
            context.get("protocol"),
            context.get("mimic"),
            profile=context.get("profile"),
        )


class ClashApiSelectorBackend:
    """``switch_protocol``-compatible actuator driving a sing-box selector."""

    def __init__(
        self,
        *,
        controller: str,
        selector_tag: str,
        protocol_to_tag: Dict[str, str],
        test_profile: str,
        http: HttpFn = _urllib_http,
        verify: bool = True,
    ) -> None:
        # Normalise controller to a base URL.
        self.base = controller if controller.startswith("http") else f"http://{controller}"
        self.selector_tag = selector_tag
        self.protocol_to_tag = protocol_to_tag
        self.test_profile = test_profile
        self.http = http
        self.verify = verify
        self.switch_log: List[Dict[str, Any]] = []

    def _selector_url(self) -> str:
        return f"{self.base}/proxies/{self.selector_tag}"

    def active(self) -> Optional[str]:
        """Return the currently selected outbound tag, or None on error."""
        status, body = self.http("GET", self._selector_url(), None)
        if status == 200 and isinstance(body, dict):
            return body.get("now")
        return None

    def switch_protocol(self, protocol: str, mimic: Optional[str] = None, profile: Optional[str] = None) -> bool:
        target_profile = profile or self.test_profile
        if target_profile != self.test_profile:
            raise PermissionError(
                f"refusing transport switch on non-test profile {target_profile!r}; "
                f"only {self.test_profile!r} is permitted (rules/50)"
            )
        tag = self.protocol_to_tag.get(protocol)
        if tag is None:
            raise ValueError(f"no sing-box outbound mapped for protocol {protocol!r}")

        status, _ = self.http("PUT", self._selector_url(), {"name": tag})
        ok = status in (200, 204)
        if ok and self.verify:
            ok = self.active() == tag
        self.switch_log.append(
            {"protocol": protocol, "tag": tag, "profile": target_profile, "ok": ok, "http_status": status}
        )
        return ok
