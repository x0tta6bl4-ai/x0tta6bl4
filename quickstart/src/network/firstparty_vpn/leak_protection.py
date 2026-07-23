"""Linux client leak-protection validation for first-party VPN rollout."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Sequence

from .linux_policy import LinuxNetworkPolicyConfig, LinuxPolicyCommand
from .ops import CommandPlanEvidence, assert_privacy_safe


class LinuxLeakProtectionError(ValueError):
    """Raised when Linux leak-protection evidence is invalid."""


@dataclass(frozen=True)
class LinuxLeakProtectionEvidence:
    """Privacy-safe evidence that client traffic is forced through the VPN."""

    controls: tuple[str, ...]
    reasons: tuple[str, ...]
    command_plan: CommandPlanEvidence

    @property
    def passed(self) -> bool:
        return not self.reasons

    def evidence_hash(self) -> str:
        return hashlib.sha256(
            b"x0vpn-linux-leak-protection-v1"
            + json.dumps(
                self.to_json_dict(),
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

    def to_json_dict(self) -> dict[str, object]:
        payload = {
            "command_plan": self.command_plan.to_json_dict(),
            "controls": list(self.controls),
            "passed": self.passed,
            "reasons": list(self.reasons),
        }
        assert_privacy_safe(payload)
        return payload


def evaluate_linux_leak_protection(
    *,
    config: LinuxNetworkPolicyConfig,
    commands: Sequence[LinuxPolicyCommand],
) -> LinuxLeakProtectionEvidence:
    """Validate that a planned client policy prevents route and DNS leaks."""
    command_set = set(commands)
    controls: list[str] = []
    reasons: list[str] = []

    if config.route_all_traffic:
        _require_command(
            command_set,
            ("ip", "route", "replace", "default", "dev", config.tun_name),
            controls,
            reasons,
            "full_tunnel_default_route",
            "full_tunnel_default_route_missing",
        )

    if config.dns_servers:
        _require_command(
            command_set,
            ("resolvectl", "dns", config.tun_name, *config.dns_servers),
            controls,
            reasons,
            "tun_dns_servers",
            "tun_dns_servers_missing",
        )
        _require_command(
            command_set,
            ("resolvectl", "domain", config.tun_name, "~."),
            controls,
            reasons,
            "tun_dns_domain",
            "tun_dns_domain_missing",
        )
        _require_command(
            command_set,
            ("resolvectl", "default-route", config.tun_name, "yes"),
            controls,
            reasons,
            "tun_dns_default_route",
            "tun_dns_default_route_missing",
        )
    else:
        reasons.append("tun_dns_servers_not_configured")

    if config.enable_kill_switch:
        _require_command(
            command_set,
            ("nft", "add", "table", "inet", config.table_name),
            controls,
            reasons,
            "kill_switch_table",
            "kill_switch_table_missing",
        )
        if _has_drop_output_chain(command_set, config.table_name):
            controls.append("kill_switch_output_drop_policy")
        else:
            reasons.append("kill_switch_output_drop_policy_missing")
        _require_command(
            command_set,
            (
                "nft",
                "add",
                "rule",
                "inet",
                config.table_name,
                "output",
                "oifname",
                "lo",
                "accept",
            ),
            controls,
            reasons,
            "kill_switch_loopback_allow",
            "kill_switch_loopback_allow_missing",
        )
        _require_command(
            command_set,
            (
                "nft",
                "add",
                "rule",
                "inet",
                config.table_name,
                "output",
                "oifname",
                config.tun_name,
                "accept",
            ),
            controls,
            reasons,
            "kill_switch_tun_allow",
            "kill_switch_tun_allow_missing",
        )
    else:
        reasons.append("kill_switch_disabled")

    for endpoint in config.remote_endpoints:
        if config.route_all_traffic:
            _require_command(
                command_set,
                (
                    "ip",
                    "route",
                    "replace",
                    endpoint.route_prefix,
                    "via",
                    config.underlay_gateway or "",
                    "dev",
                    config.underlay_interface or "",
                ),
                controls,
                reasons,
                "underlay_endpoint_route",
                "underlay_endpoint_route_missing",
            )
        _require_command(
            command_set,
            (
                "nft",
                "add",
                "rule",
                "inet",
                config.table_name,
                "output",
                endpoint.family_token,
                "daddr",
                endpoint.host,
                endpoint.firewall_protocol,
                "dport",
                str(endpoint.port),
                "accept",
            ),
            controls,
            reasons,
            "underlay_endpoint_kill_switch_allow",
            "underlay_endpoint_kill_switch_allow_missing",
        )

    evidence = LinuxLeakProtectionEvidence(
        controls=tuple(dict.fromkeys(controls)),
        reasons=tuple(dict.fromkeys(reasons)),
        command_plan=CommandPlanEvidence.from_commands(commands),
    )
    assert_privacy_safe(evidence.to_json_dict())
    return evidence


def _require_command(
    command_set: set[LinuxPolicyCommand],
    command: LinuxPolicyCommand,
    controls: list[str],
    reasons: list[str],
    control: str,
    missing_reason: str,
) -> None:
    if command in command_set:
        controls.append(control)
    else:
        reasons.append(missing_reason)


def _has_drop_output_chain(
    command_set: set[LinuxPolicyCommand],
    table_name: str,
) -> bool:
    return any(
        command[:6] == ("nft", "add", "chain", "inet", table_name, "output")
        and "policy" in command
        and "drop" in command
        for command in command_set
    )
