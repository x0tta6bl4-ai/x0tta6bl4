"""Read-only Linux applied-state validation for first-party VPN rollout."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import json
import subprocess
from typing import Callable, Mapping

from .linux_policy import LinuxNetworkPolicyConfig, LinuxServerNatConfig
from .ops import assert_privacy_safe
from .tun import LinuxTunConfig
from src.core.security.subprocess_validator import safe_run

LinuxAppliedStateReadCommand = tuple[str, ...]
LinuxAppliedStateCommandRunner = Callable[[LinuxAppliedStateReadCommand], str]


class LinuxAppliedStateError(ValueError):
    """Raised when Linux applied-state evidence is invalid."""


@dataclass(frozen=True)
class LinuxAppliedStateSnapshot:
    """Read-only Linux state captured after applying a deployment packet."""

    interfaces: tuple[str, ...]
    routes: tuple[str, ...]
    dns: tuple[str, ...]
    nft_ruleset: str
    sysctls: Mapping[str, str] = field(default_factory=dict)
    captured_at: int = 0

    def __post_init__(self) -> None:
        if self.captured_at < 0:
            raise LinuxAppliedStateError("applied-state capture time cannot be negative")

    def state_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-linux-applied-state-snapshot-v1"
            + json.dumps(
                {
                    "dns": list(self.dns),
                    "interfaces": list(self.interfaces),
                    "nft_ruleset": self.nft_ruleset,
                    "routes": list(self.routes),
                    "sysctls": dict(sorted(self.sysctls.items())),
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "captured_at": self.captured_at,
            "dns_hash": _hash_text("\n".join(self.dns), "applied-state-dns"),
            "interface_count": len(self.interfaces),
            "interfaces_hash": _hash_text(
                "\n".join(self.interfaces),
                "applied-state-interfaces",
            ),
            "nft_ruleset_hash": _hash_text(
                self.nft_ruleset,
                "applied-state-nft-ruleset",
            ),
            "route_count": len(self.routes),
            "routes_hash": _hash_text("\n".join(self.routes), "applied-state-routes"),
            "state_hash": self.state_hash(),
            "sysctls_hash": _hash_text(
                json.dumps(dict(sorted(self.sysctls.items())), sort_keys=True),
                "applied-state-sysctls",
            ),
        }
        assert_privacy_safe(payload)
        return payload


@dataclass(frozen=True)
class LinuxAppliedStateEvidence:
    """Privacy-safe evidence that applied Linux state matches VPN controls."""

    controls: tuple[str, ...]
    reasons: tuple[str, ...]
    snapshot_hash: str
    captured_at: int

    def __post_init__(self) -> None:
        if len(self.snapshot_hash) != 64:
            raise LinuxAppliedStateError("snapshot hash must be sha256 hex")
        if self.captured_at < 0:
            raise LinuxAppliedStateError("applied-state evidence time cannot be negative")

    @property
    def passed(self) -> bool:
        return not self.reasons

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-linux-applied-state-evidence-v1"
            + json.dumps(
                self.to_json_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "captured_at": self.captured_at,
            "controls": list(self.controls),
            "passed": self.passed,
            "reasons": list(self.reasons),
            "snapshot_hash": self.snapshot_hash,
        }
        assert_privacy_safe(payload)
        return payload


def evaluate_linux_applied_state(
    *,
    client_network: LinuxNetworkPolicyConfig,
    server_nat: LinuxServerNatConfig,
    client_tun: LinuxTunConfig,
    server_tun: LinuxTunConfig,
    snapshot: LinuxAppliedStateSnapshot,
) -> LinuxAppliedStateEvidence:
    """Validate read-only post-apply Linux state for client and server controls."""
    controls: list[str] = []
    reasons: list[str] = []

    _validate_tun(
        tun_name=client_tun.name,
        label="client_tun",
        snapshot=snapshot,
        controls=controls,
        reasons=reasons,
    )
    _validate_tun(
        tun_name=server_tun.name,
        label="server_tun",
        snapshot=snapshot,
        controls=controls,
        reasons=reasons,
    )
    _validate_client_network(
        config=client_network,
        snapshot=snapshot,
        controls=controls,
        reasons=reasons,
    )
    _validate_server_nat(
        config=server_nat,
        snapshot=snapshot,
        controls=controls,
        reasons=reasons,
    )

    evidence = LinuxAppliedStateEvidence(
        controls=tuple(dict.fromkeys(controls)),
        reasons=tuple(dict.fromkeys(reasons)),
        snapshot_hash=snapshot.state_hash(),
        captured_at=snapshot.captured_at,
    )
    assert_privacy_safe(evidence.to_json_dict())
    return evidence


def collect_linux_applied_state_snapshot(
    *,
    command_runner: LinuxAppliedStateCommandRunner | None = None,
    now: int | None = None,
) -> LinuxAppliedStateSnapshot:
    """Collect read-only Linux state needed for post-apply VPN validation."""
    runner = command_runner or _default_read_command_runner
    captured_at = now if now is not None else _utc_now()
    interfaces = _parse_interfaces(
        runner(("ip", "-o", "link", "show")),
    )
    routes = _nonempty_lines(
        runner(("ip", "route", "show", "table", "main"))
        + "\n"
        + runner(("ip", "-6", "route", "show", "table", "main"))
    )
    dns = _nonempty_lines(runner(("resolvectl", "status")))
    nft_ruleset = runner(("nft", "list", "ruleset"))
    sysctls = {
        "net.ipv4.ip_forward": runner(
            ("sysctl", "-n", "net.ipv4.ip_forward")
        ).strip()
    }
    snapshot = LinuxAppliedStateSnapshot(
        interfaces=interfaces,
        routes=routes,
        dns=dns,
        nft_ruleset=nft_ruleset,
        sysctls=sysctls,
        captured_at=captured_at,
    )
    assert_privacy_safe(snapshot.to_json_dict())
    return snapshot


def _validate_tun(
    *,
    tun_name: str,
    label: str,
    snapshot: LinuxAppliedStateSnapshot,
    controls: list[str],
    reasons: list[str],
) -> None:
    if tun_name in snapshot.interfaces:
        controls.append(f"{label}_present")
    else:
        reasons.append(f"{label}_missing")


def _validate_client_network(
    *,
    config: LinuxNetworkPolicyConfig,
    snapshot: LinuxAppliedStateSnapshot,
    controls: list[str],
    reasons: list[str],
) -> None:
    route_text = "\n".join(snapshot.routes)
    dns_text = "\n".join(snapshot.dns)
    nft_text = _normalized_ruleset(snapshot.nft_ruleset)

    if config.route_all_traffic:
        if _contains_all(route_text, "default", "dev", config.tun_name):
            controls.append("full_tunnel_route_observed")
        else:
            reasons.append("full_tunnel_route_missing")

    if config.dns_servers:
        missing_dns = tuple(
            server for server in config.dns_servers if server not in dns_text
        )
        if _contains_all(dns_text, config.tun_name, *config.dns_servers):
            controls.append("tun_dns_servers_observed")
        elif missing_dns:
            reasons.append("tun_dns_servers_missing")
        else:
            reasons.append("tun_dns_interface_missing")

        if _contains_all(dns_text, config.tun_name, "~."):
            controls.append("tun_dns_default_domain_observed")
        else:
            reasons.append("tun_dns_default_domain_missing")
    else:
        reasons.append("tun_dns_servers_not_configured")

    if config.enable_kill_switch:
        _validate_client_kill_switch(config, nft_text, controls, reasons)
    else:
        reasons.append("kill_switch_disabled")

    for endpoint in config.remote_endpoints:
        if config.route_all_traffic:
            if _contains_all(
                route_text,
                endpoint.route_prefix,
                config.underlay_gateway or "",
                config.underlay_interface or "",
            ):
                controls.append("underlay_endpoint_route_observed")
            else:
                reasons.append("underlay_endpoint_route_missing")
        if _contains_all(
            nft_text,
            endpoint.family_token,
            "daddr",
            endpoint.host,
            endpoint.firewall_protocol,
            "dport",
            str(endpoint.port),
            "accept",
        ):
            controls.append("underlay_endpoint_kill_switch_allow_observed")
        else:
            reasons.append("underlay_endpoint_kill_switch_allow_missing")


def _validate_client_kill_switch(
    config: LinuxNetworkPolicyConfig,
    nft_text: str,
    controls: list[str],
    reasons: list[str],
) -> None:
    if _contains_all(nft_text, "table", "inet", config.table_name):
        controls.append("kill_switch_table_observed")
    else:
        reasons.append("kill_switch_table_missing")

    if _contains_all(nft_text, "hook", "output", "policy", "drop"):
        controls.append("kill_switch_output_drop_policy_observed")
    else:
        reasons.append("kill_switch_output_drop_policy_missing")

    if _contains_all(nft_text, "oifname", "lo", "accept"):
        controls.append("kill_switch_loopback_allow_observed")
    else:
        reasons.append("kill_switch_loopback_allow_missing")

    if _contains_all(nft_text, "oifname", config.tun_name, "accept"):
        controls.append("kill_switch_tun_allow_observed")
    else:
        reasons.append("kill_switch_tun_allow_missing")


def _validate_server_nat(
    *,
    config: LinuxServerNatConfig,
    snapshot: LinuxAppliedStateSnapshot,
    controls: list[str],
    reasons: list[str],
) -> None:
    nft_text = _normalized_ruleset(snapshot.nft_ruleset)

    if config.enable_ipv4_forwarding:
        if snapshot.sysctls.get("net.ipv4.ip_forward") == "1":
            controls.append("server_ipv4_forwarding_observed")
        else:
            reasons.append("server_ipv4_forwarding_missing")

    if config.enable_masquerade:
        if _contains_all(
            nft_text,
            "table",
            "ip",
            config.nat_table_name,
            "postrouting",
            "ip",
            "saddr",
            config.client_cidr,
            "oifname",
            config.uplink_interface,
            "masquerade",
        ):
            controls.append("server_masquerade_observed")
        else:
            reasons.append("server_masquerade_missing")

    if config.allow_vpn_listener:
        for listener in config.listeners:
            if _contains_all(
                nft_text,
                "table",
                "inet",
                config.filter_table_name,
                "input",
                "iifname",
                config.uplink_interface,
                listener.firewall_protocol,
                "dport",
                str(listener.port),
                "accept",
            ):
                controls.append("server_vpn_listener_observed")
            else:
                reasons.append("server_vpn_listener_missing")
                reasons.append(
                    "server_vpn_listener_missing:"
                    f"{listener.transport}:{listener.port}"
                )


def _normalized_ruleset(ruleset: str) -> str:
    return (
        ruleset.replace('"', " ")
        .replace("{", " ")
        .replace("}", " ")
        .replace(";", " ")
    )


def _contains_all(text: str, *needles: str) -> bool:
    return all(needle and needle in text for needle in needles)


def _hash_text(value: str, namespace: str) -> str:
    return hashlib.sha256(f"{namespace}|{value}".encode("utf-8")).hexdigest()


def _parse_interfaces(output: str) -> tuple[str, ...]:
    interfaces: list[str] = []
    for line in _nonempty_lines(output):
        parts = line.split(":", 2)
        if len(parts) >= 2 and parts[0].strip().isdigit():
            name = parts[1].strip().split("@", 1)[0]
        else:
            name = line.strip().split()[0].split("@", 1)[0]
        if name:
            interfaces.append(name)
    return tuple(dict.fromkeys(interfaces))


def _nonempty_lines(output: str) -> tuple[str, ...]:
    return tuple(line.strip() for line in output.splitlines() if line.strip())


def _default_read_command_runner(command: LinuxAppliedStateReadCommand) -> str:
    completed = safe_run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout


def _utc_now() -> int:
    return int(datetime.now(timezone.utc).timestamp())
