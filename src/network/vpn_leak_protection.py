#!/usr/bin/env python3
"""
VPN Leak Protection Module for x0tta6bl4
Prevents DNS, WebRTC, and IP leaks by implementing:
1. DNS-over-HTTPS (DoH) resolver integration
2. WebRTC leak detection and prevention
3. Kill switch functionality
4. Firewall configuration for leak protection
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import re
import sys
import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType, get_event_bus
from src.core.security.safe_subprocess import (SafeSubprocess, SecurityError,
                                      ValidationError)
from src.services.service_event_identity import service_event_identity

from .dns_over_https import DoHResolver

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "vpn-leak-protector"
_SERVICE_LAYER = "network_vpn_leak_protection_observed_state"
VPN_LEAK_PROTECTION_CLAIM_BOUNDARY = (
    "VPN leak protection evidence records local resolver/firewall/kill-switch "
    "intent, SafeSubprocess outcomes, and local leak-test summaries only. It "
    "does not prove remote VPN provider health, upstream DNS privacy, browser "
    "policy enforcement, complete host firewall correctness, or that all "
    "traffic is flowing through the VPN dataplane."
)


def _normalize_evidence_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    normalized = _normalize_evidence_value(value)
    if not normalized:
        return None
    return hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _bounded_text_metadata(value: Any) -> Dict[str, Any]:
    text = _normalize_evidence_value(value)
    return {
        "present": bool(text),
        "bytes": len(text.encode("utf-8", errors="replace")),
        "lines": text.count("\n") + 1 if text else 0,
        "sha256_prefix": _redacted_sha256_prefix(text),
        "raw_redacted": True,
    }


def _command_evidence(command: List[str], *, timeout_seconds: int = 10) -> Dict[str, Any]:
    executable = command[0] if command else None
    return {
        "executable": executable,
        "argv_count": len(command),
        "argv_sha256_prefix": _redacted_sha256_prefix(" ".join(command)),
        "timeout_seconds": timeout_seconds,
        "raw_args_redacted": True,
    }


def _identity_evidence() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_SERVICE_AGENT)
    return {
        "spiffe_id_present": bool(_normalize_evidence_value(identity.get("spiffe_id"))),
        "spiffe_id_hash": _redacted_sha256_prefix(identity.get("spiffe_id")),
        "did_present": bool(_normalize_evidence_value(identity.get("did"))),
        "did_hash": _redacted_sha256_prefix(identity.get("did")),
        "wallet_address_present": bool(
            _normalize_evidence_value(identity.get("wallet_address"))
        ),
        "wallet_address_hash": _redacted_sha256_prefix(
            identity.get("wallet_address")
        ),
        "raw_identity_redacted": True,
    }


_RESOLVER_EVIDENCE_FIELDS = {
    "event_id",
    "source_agent",
    "layer",
    "operation",
    "stage",
    "status",
    "reason",
    "record_type",
    "domain_hash",
    "resolver_mode",
    "answer_count",
    "attempt_count",
    "claim_boundary",
}


def _resolver_evidence_reference(resolver: Any) -> Dict[str, Any]:
    getter = getattr(resolver, "get_last_resolution_evidence", None)
    if not callable(getter):
        return {
            "available": False,
            "reason": "resolver_evidence_method_missing",
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    try:
        evidence = getter()
    except Exception as exc:
        return {
            "available": False,
            "reason": "resolver_evidence_read_failed",
            "error_hash": _redacted_sha256_prefix(exc),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    if not isinstance(evidence, dict) or not evidence:
        return {
            "available": False,
            "reason": "resolver_evidence_missing",
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }

    reference = {
        key: evidence.get(key)
        for key in sorted(_RESOLVER_EVIDENCE_FIELDS)
        if key in evidence
    }
    reference.update(
        {
            "available": bool(reference.get("event_id")),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
        }
    )
    return reference


def _dns_resolution_evidence_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    references = [
        item.get("resolver_evidence")
        for item in results
        if isinstance(item, dict) and isinstance(item.get("resolver_evidence"), dict)
    ]
    available = [
        reference
        for reference in references
        if reference.get("available") and reference.get("event_id")
    ]
    return {
        "available_count": len(available),
        "missing_count": len(references) - len(available),
        "event_ids": [reference.get("event_id") for reference in available[:20]],
        "source_agents": sorted(
            {
                str(reference.get("source_agent"))
                for reference in available
                if reference.get("source_agent")
            }
        ),
        "layers": sorted(
            {
                str(reference.get("layer"))
                for reference in available
                if reference.get("layer")
            }
        ),
        "resolver_modes": sorted(
            {
                str(reference.get("resolver_mode"))
                for reference in available
                if reference.get("resolver_mode")
            }
        ),
        "statuses": sorted(
            {
                str(reference.get("status"))
                for reference in available
                if reference.get("status")
            }
        ),
        "claim_boundary_present_count": sum(
            1 for reference in available if reference.get("claim_boundary")
        ),
        "raw_evidence_payloads_redacted": True,
        "payloads_redacted": True,
    }


def _event_evidence_reference(
    event_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "source_agent": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "operation": payload.get("operation"),
        "stage": payload.get("stage"),
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "observed_state": payload.get("observed_state"),
        "control_action": payload.get("control_action"),
        "claim_boundary": payload.get("claim_boundary"),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
    }


def _leak_details_summary(result: "LeakTestResult") -> Dict[str, Any]:
    details = result.details if isinstance(result.details, dict) else {}
    summary: Dict[str, Any] = {
        "leak_type": result.leak_type.value,
        "is_leaking": bool(result.is_leaking),
        "payloads_redacted": True,
    }
    if result.leak_type == LeakType.DNS:
        results = details.get("results") if isinstance(details.get("results"), list) else []
        summary.update(
            {
                "tested_domain_count": len(details.get("tested_domains", []) or []),
                "resolved_domain_count": sum(
                    1 for item in results if isinstance(item, dict) and item.get("success")
                ),
                "failed_domain_count": sum(
                    1 for item in results if isinstance(item, dict) and not item.get("success")
                ),
                "doh_resolution_evidence": _dns_resolution_evidence_summary(results),
            }
        )
    elif result.leak_type == LeakType.IP:
        summary.update(
            {
                "detected_ip_count": len(details.get("detected_ips", []) or []),
                "normalized_ip_count": len(details.get("normalized_ips", []) or []),
                "consistent_ip": details.get("consistent_ip")
                if isinstance(details.get("consistent_ip"), bool)
                else None,
                "vpn_server_configured": bool(os.getenv("VPN_SERVER", "").strip()),
                "warning_present": "warning" in details,
                "error_present": "error" in details,
            }
        )
    elif result.leak_type == LeakType.WebRTC:
        status = details.get("fix_status") if isinstance(details.get("fix_status"), dict) else {}
        fixes = details.get("fix_results") if isinstance(details.get("fix_results"), dict) else {}
        summary.update(
            {
                "status_field_count": len(status),
                "active_status_count": sum(1 for value in status.values() if bool(value)),
                "fix_result_count": len(fixes),
                "successful_fix_count": sum(1 for value in fixes.values() if bool(value)),
                "warning_present": "warning" in details,
                "error_present": "error" in details,
            }
        )
    return summary


class LeakType(Enum):
    """Types of VPN leaks that can be detected."""

    DNS = "dns"
    IP = "ip"
    WebRTC = "webrtc"
    ALL = "all"


class LeakTestResult:
    """Result of a leak test."""

    def __init__(self, leak_type: LeakType, is_leaking: bool, details: Any):
        self.leak_type = leak_type
        self.is_leaking = is_leaking
        self.details = details

    def __str__(self) -> str:
        status = "⚠️ LEAK DETECTED" if self.is_leaking else "✅ No leak"
        return f"{self.leak_type.value.upper()}: {status} - {self.details}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "leak_type": self.leak_type.value,
            "is_leaking": self.is_leaking,
            "details": self.details,
        }


class VPNLeakProtector:
    """Main VPN leak protection and detection class."""

    # Valid interface name pattern (alphanumeric, max 15 chars - IFNAMSIZ)
    INTERFACE_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,15}$")

    def __init__(
        self,
        doh_resolver: Optional[DoHResolver] = None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        if doh_resolver is None:
            # Directly create DoHResolver instance without asyncio.run()
            self.doh_resolver = DoHResolver(
                event_bus=event_bus,
                event_project_root=event_project_root,
            )
        else:
            self.doh_resolver = doh_resolver

        self.kill_switch_enabled = False
        self.protection_enabled = False
        self.original_dns_servers: List[str] = []
        self.vpn_interface: Optional[str] = None
        self._last_event_evidence: Optional[Dict[str, Any]] = None
        logger.info("VPNLeakProtector initialized")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize vpn-leak-protector EventBus: %s", exc)
            return None

    def _publish_event(
        self,
        *,
        operation: str,
        stage: str,
        status: str,
        started_at: float,
        event_type: Optional[EventType] = None,
        mutation: bool = False,
        observed_state: bool = False,
        interface: Optional[str] = None,
        command: Optional[List[str]] = None,
        command_result: Any = None,
        result_summary: Optional[Dict[str, Any]] = None,
        reason: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        output_metadata: Optional[Dict[str, Any]] = None
        if command_result is not None:
            output_metadata = {
                "success": bool(getattr(command_result, "success", False)),
                "returncode": getattr(command_result, "returncode", None),
                "stdout": _bounded_text_metadata(getattr(command_result, "stdout", "")),
                "stderr": _bounded_text_metadata(getattr(command_result, "stderr", "")),
                "payloads_redacted": True,
            }

        payload = {
            "component": "network.vpn_leak_protection",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "stage": stage,
            "status": status,
            "reason": reason,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "platform": sys.platform,
            "control_action": bool(mutation),
            "observed_state": bool(observed_state),
            "protection_enabled": bool(self.protection_enabled),
            "kill_switch_enabled": bool(self.kill_switch_enabled),
            "vpn_interface_hash": _redacted_sha256_prefix(
                interface if interface is not None else self.vpn_interface
            ),
            "dns_server_count": len(self.original_dns_servers),
            "service_identity": _identity_evidence(),
            "command": _command_evidence(command) if command else None,
            "output_metadata": output_metadata,
            "result_summary": result_summary or {},
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "claim_boundary": VPN_LEAK_PROTECTION_CLAIM_BOUNDARY,
        }
        try:
            event = bus.publish(
                event_type
                or (
                    EventType.TASK_BLOCKED
                    if status in {"blocked", "failed", "error"}
                    else EventType.PIPELINE_STAGE_END
                ),
                _SERVICE_AGENT,
                payload,
                priority=6 if mutation else 4,
            )
            self._last_event_evidence = _event_evidence_reference(event.event_id, payload)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish vpn-leak-protector event: %s", exc)
            self._last_event_evidence = None
            return None

    def get_last_event_evidence(self) -> Optional[Dict[str, Any]]:
        """Return a redacted reference to the latest vpn-leak-protector event."""
        if self._last_event_evidence is None:
            return None
        return dict(self._last_event_evidence)

    def _validate_interface_name(self, interface: Optional[str]) -> bool:
        """
        Validate VPN interface name to prevent command injection.

        Args:
            interface: Interface name to validate

        Returns:
            True if valid, False otherwise
        """
        if not interface:
            return False
        return bool(self.INTERFACE_PATTERN.match(interface))

    async def enable_protection(self, vpn_interface: str = "tun0") -> None:
        """
        Enable all leak protection mechanisms.

        Args:
            vpn_interface: VPN interface name (default: tun0)

        Raises:
            ValueError: If interface name is invalid
        """
        started_at = time.monotonic()
        # Validate interface name before using in commands
        if not self._validate_interface_name(vpn_interface):
            self._publish_event(
                operation="enable_protection",
                stage="validation",
                status="blocked",
                started_at=started_at,
                event_type=EventType.TASK_BLOCKED,
                mutation=True,
                interface=vpn_interface,
                reason="invalid_interface",
            )
            raise ValueError(f"Invalid VPN interface name: {vpn_interface}")

        self.vpn_interface = vpn_interface
        self.protection_enabled = True

        # Save original DNS configuration
        await self._save_original_dns()

        # Configure DNS-over-HTTPS
        await self._configure_doh()

        # Configure firewall
        await self._configure_firewall()

        # Enable kill switch
        await self._enable_kill_switch()

        self._publish_event(
            operation="enable_protection",
            stage="enabled",
            status="success",
            started_at=started_at,
            mutation=True,
            interface=vpn_interface,
            result_summary={
                "dns_servers_saved": len(self.original_dns_servers),
                "kill_switch_enabled": bool(self.kill_switch_enabled),
                "payloads_redacted": True,
            },
        )
        logger.info("VPN leak protection enabled")

    async def disable_protection(self) -> None:
        """Disable all leak protection mechanisms and restore original state."""
        started_at = time.monotonic()
        if not self.protection_enabled:
            logger.warning("Protection already disabled")
            self._publish_event(
                operation="disable_protection",
                stage="already_disabled",
                status="skipped",
                started_at=started_at,
                mutation=True,
                reason="already_disabled",
            )
            return

        self.protection_enabled = False

        # Disable kill switch
        await self._disable_kill_switch()

        # Restore original DNS configuration
        await self._restore_original_dns()

        # Restore firewall
        await self._restore_firewall()

        self._publish_event(
            operation="disable_protection",
            stage="disabled",
            status="success",
            started_at=started_at,
            mutation=True,
            result_summary={
                "kill_switch_enabled": bool(self.kill_switch_enabled),
                "dns_servers_saved": len(self.original_dns_servers),
                "payloads_redacted": True,
            },
        )
        logger.info("VPN leak protection disabled")

    async def _save_original_dns(self) -> None:
        """Save original DNS server configuration."""
        started_at = time.monotonic()
        command: Optional[List[str]] = None
        command_result: Any = None
        status = "success"
        reason: Optional[str] = None
        try:
            if sys.platform.startswith("linux"):
                # Check systemd-resolved or /etc/resolv.conf using SafeSubprocess
                command = ["cat", "/etc/resolv.conf"]
                result = SafeSubprocess.run(command, timeout=10)
                command_result = result

                if result.success:
                    lines = result.stdout.splitlines()
                    for line in lines:
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) >= 2:
                                self.original_dns_servers.append(parts[1])
                else:
                    status = "failed"
                    reason = "read_resolv_conf_failed"
            elif sys.platform == "win32":
                # Windows: Get DNS servers from network interfaces
                command = ["ipconfig", "/all"]
                result = SafeSubprocess.run(command, timeout=10)
                command_result = result

                if result.success:
                    # Parse DNS servers from ipconfig output
                    lines = result.stdout.splitlines()
                    in_dns_section = False
                    for line in lines:
                        if "DNS Servers" in line:
                            in_dns_section = True
                            continue
                        if (
                            in_dns_section
                            and line.strip()
                            and not any(
                                keyword in line
                                for keyword in [
                                    "Description",
                                    "Physical Address",
                                    "DHCP",
                                ]
                            )
                        ):
                            self.original_dns_servers.append(line.strip())
                            if len(self.original_dns_servers) >= 2:
                                in_dns_section = False
                else:
                    status = "failed"
                    reason = "ipconfig_failed"
            elif sys.platform == "darwin":
                # macOS: Get DNS servers from scutil
                command = ["scutil", "--dns"]
                result = SafeSubprocess.run(command, timeout=10)
                command_result = result

                if result.success:
                    lines = result.stdout.splitlines()
                    in_resolver_section = False
                    for line in lines:
                        if "resolver #0" in line:
                            in_resolver_section = True
                            continue
                        if in_resolver_section and "nameserver" in line:
                            parts = line.split(":")
                            if len(parts) >= 2:
                                server = parts[1].strip()
                                self.original_dns_servers.append(server)
                        if in_resolver_section and "flags" in line:
                            in_resolver_section = False
                else:
                    status = "failed"
                    reason = "scutil_failed"
            else:
                status = "skipped"
                reason = "unsupported_platform"

            logger.debug(f"Original DNS servers: {self.original_dns_servers}")

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.warning(f"Failed to save original DNS configuration: {e}")
        finally:
            self._publish_event(
                operation="save_original_dns",
                stage="dns_read",
                status=status,
                started_at=started_at,
                observed_state=True,
                command=command,
                command_result=command_result,
                result_summary={
                    "dns_server_count": len(self.original_dns_servers),
                    "payloads_redacted": True,
                },
                reason=reason,
            )

    async def _configure_doh(self) -> None:
        """Configure system to use DNS-over-HTTPS."""
        started_at = time.monotonic()
        status = "success"
        reason: Optional[str] = None
        systemd_active: Optional[bool] = None
        dns_success: Optional[bool] = None
        domain_success: Optional[bool] = None
        try:
            if sys.platform.startswith("linux"):
                # Configure systemd-resolved to use DoH (modern Linux systems)
                if os.path.exists("/etc/systemd/resolved.conf"):
                    # Check if systemd-resolved is running
                    result = SafeSubprocess.run(
                        ["systemctl", "is-active", "systemd-resolved"], timeout=10
                    )

                    if result.success and result.stdout.strip() == "active":
                        systemd_active = True
                        # Configure DNS-over-HTTPS for VPN interface using SafeSubprocess
                        # Note: resolvectl commands are split for safety
                        dns_result = SafeSubprocess.run(
                            [
                                "resolvectl",
                                "dns",
                                str(self.vpn_interface),
                                "1.1.1.1",
                                "8.8.8.8",
                            ],
                            timeout=10,
                        )
                        dns_success = bool(dns_result.success)
                        if not dns_result.success:
                            logger.warning(f"Failed to set DNS: {dns_result.stderr}")

                        domain_result = SafeSubprocess.run(
                            ["resolvectl", "domain", str(self.vpn_interface), "~."],
                            timeout=10,
                        )
                        domain_success = bool(domain_result.success)
                        if not domain_result.success:
                            logger.warning(
                                f"Failed to set domain: {domain_result.stderr}"
                            )
                        if not dns_result.success or not domain_result.success:
                            status = "failed"
                            reason = "resolvectl_failed"
                    else:
                        systemd_active = False
                        status = "skipped"
                        reason = "systemd_resolved_inactive"
                else:
                    status = "skipped"
                    reason = "resolved_conf_missing"
            elif sys.platform == "win32":
                # Windows: Modify network adapter DNS settings
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning("Windows DNS configuration not fully implemented")
            elif sys.platform == "darwin":
                # macOS: Configure DNS servers
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning("macOS DNS configuration not fully implemented")
            else:
                status = "skipped"
                reason = "unsupported_platform"

            logger.info("DNS-over-HTTPS configuration applied")

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.error(f"Failed to configure DNS-over-HTTPS: {e}")
        finally:
            self._publish_event(
                operation="configure_doh",
                stage="doh_configure",
                status=status,
                started_at=started_at,
                mutation=True,
                result_summary={
                    "systemd_resolved_active": systemd_active,
                    "dns_command_success": dns_success,
                    "domain_command_success": domain_success,
                    "payloads_redacted": True,
                },
                reason=reason,
            )

    async def _restore_original_dns(self) -> None:
        """Restore original DNS configuration."""
        started_at = time.monotonic()
        command: Optional[List[str]] = None
        command_result: Any = None
        status = "success"
        reason: Optional[str] = None
        try:
            if not self.original_dns_servers:
                logger.warning("No original DNS configuration to restore")
                status = "skipped"
                reason = "no_original_dns"
                return

            if sys.platform.startswith("linux"):
                # Restore systemd-resolved configuration using SafeSubprocess
                command = ["resolvectl", "revert", str(self.vpn_interface)]
                result = SafeSubprocess.run(command, timeout=10)
                command_result = result

                if result.success:
                    logger.debug("DNS configuration restored")
                else:
                    status = "failed"
                    reason = "resolvectl_revert_failed"
                    logger.warning(f"Failed to restore DNS: {result.stderr}")
            else:
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning(f"DNS restoration not implemented for {sys.platform}")

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.error(f"Failed to restore DNS configuration: {e}")
        finally:
            self._publish_event(
                operation="restore_original_dns",
                stage="dns_restore",
                status=status,
                started_at=started_at,
                mutation=True,
                command=command,
                command_result=command_result,
                result_summary={
                    "dns_server_count": len(self.original_dns_servers),
                    "payloads_redacted": True,
                },
                reason=reason,
            )

    async def _configure_firewall(self) -> None:
        """Configure firewall to block non-VPN traffic with split-tunneling for Google Cloud."""
        started_at = time.monotonic()
        status = "success"
        reason: Optional[str] = None
        attempted_commands = 0
        try:
            if sys.platform.startswith("linux"):
                # Use iptables to block all non-VPN traffic
                if os.path.exists("/sbin/iptables"):
                    # Allow loopback
                    attempted_commands += 1
                    await self._run_iptables_command(
                        ["-A", "INPUT", "-i", "lo", "-j", "ACCEPT"]
                    )
                    attempted_commands += 1
                    await self._run_iptables_command(
                        ["-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"]
                    )

                    # Split-tunneling: Allow direct access to Google Cloud services
                    # This prevents conflicts when SNI uses google domains
                    GOOGLE_CLOUD_NETWORKS = [
                        "8.8.8.8/32",  # Google DNS
                        "8.8.4.4/32",  # Google DNS
                        "108.177.0.0/17",  # Google APIs
                        "172.217.0.0/16",  # Google Cloud
                        "142.250.0.0/15",  # Google services
                        "216.58.192.0/19",  # Google
                    ]
                    for network in GOOGLE_CLOUD_NETWORKS:
                        attempted_commands += 1
                        await self._run_iptables_command(
                            ["-A", "OUTPUT", "-d", network, "-j", "ACCEPT"]
                        )

                    # Allow VPN interface
                    attempted_commands += 1
                    await self._run_iptables_command(
                        ["-A", "INPUT", "-i", str(self.vpn_interface), "-j", "ACCEPT"]
                    )
                    attempted_commands += 1
                    await self._run_iptables_command(
                        ["-A", "OUTPUT", "-o", str(self.vpn_interface), "-j", "ACCEPT"]
                    )

                    # Allow DNS over VPN
                    attempted_commands += 1
                    await self._run_iptables_command(
                        [
                            "-A",
                            "OUTPUT",
                            "-p",
                            "udp",
                            "--dport",
                            "53",
                            "-o",
                            str(self.vpn_interface),
                            "-j",
                            "ACCEPT",
                        ]
                    )
                    attempted_commands += 1
                    await self._run_iptables_command(
                        [
                            "-A",
                            "OUTPUT",
                            "-p",
                            "tcp",
                            "--dport",
                            "53",
                            "-o",
                            str(self.vpn_interface),
                            "-j",
                            "ACCEPT",
                        ]
                    )

                    # Allow HTTPS for DoH
                    attempted_commands += 1
                    await self._run_iptables_command(
                        [
                            "-A",
                            "OUTPUT",
                            "-p",
                            "tcp",
                            "--dport",
                            "443",
                            "-o",
                            str(self.vpn_interface),
                            "-j",
                            "ACCEPT",
                        ]
                    )

                    # Block all other outgoing traffic
                    attempted_commands += 1
                    await self._run_iptables_command(["-P", "OUTPUT", "DROP"])

                    logger.info(
                        "Firewall configuration applied with Google Cloud split-tunneling"
                    )
                else:
                    status = "skipped"
                    reason = "iptables_missing"
            else:
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning(
                    f"Firewall configuration not implemented for {sys.platform}"
                )

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.error(f"Failed to configure firewall: {e}")
        finally:
            self._publish_event(
                operation="configure_firewall",
                stage="firewall_configure",
                status=status,
                started_at=started_at,
                mutation=True,
                result_summary={
                    "attempted_command_count": attempted_commands,
                    "google_cloud_split_tunnel_rule_count": 6,
                    "payloads_redacted": True,
                },
                reason=reason,
            )

    async def _restore_firewall(self) -> None:
        """Restore original firewall configuration."""
        started_at = time.monotonic()
        status = "success"
        reason: Optional[str] = None
        attempted_commands = 0
        try:
            if sys.platform.startswith("linux"):
                if os.path.exists("/sbin/iptables"):
                    # Reset iptables to default state using SafeSubprocess
                    attempted_commands += 1
                    await self._run_iptables_command(["-F"])
                    attempted_commands += 1
                    await self._run_iptables_command(["-X"])
                    attempted_commands += 1
                    await self._run_iptables_command(["-P", "INPUT", "ACCEPT"])
                    attempted_commands += 1
                    await self._run_iptables_command(["-P", "OUTPUT", "ACCEPT"])
                    attempted_commands += 1
                    await self._run_iptables_command(["-P", "FORWARD", "ACCEPT"])

                    logger.info("Firewall configuration restored")
                else:
                    status = "skipped"
                    reason = "iptables_missing"
            else:
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning(
                    f"Firewall restoration not implemented for {sys.platform}"
                )

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.error(f"Failed to restore firewall configuration: {e}")
        finally:
            self._publish_event(
                operation="restore_firewall",
                stage="firewall_restore",
                status=status,
                started_at=started_at,
                mutation=True,
                result_summary={
                    "attempted_command_count": attempted_commands,
                    "payloads_redacted": True,
                },
                reason=reason,
            )

    async def _enable_kill_switch(self) -> None:
        """Enable kill switch functionality."""
        started_at = time.monotonic()
        self.kill_switch_enabled = True
        status = "success"
        reason: Optional[str] = None
        attempted_commands = 0

        try:
            if sys.platform.startswith("linux"):
                # Create a dedicated iptables chain for kill switch
                attempted_commands += 1
                await self._run_iptables_command(["-N", "VPN_KILL_SWITCH"])

                # Redirect all traffic through VPN interface
                attempted_commands += 1
                await self._run_iptables_command(
                    [
                        "-A",
                        "VPN_KILL_SWITCH",
                        "-o",
                        str(self.vpn_interface),
                        "-j",
                        "ACCEPT",
                    ]
                )
                attempted_commands += 1
                await self._run_iptables_command(
                    ["-A", "VPN_KILL_SWITCH", "-i", "lo", "-j", "ACCEPT"]
                )

                # Block everything else
                attempted_commands += 1
                await self._run_iptables_command(
                    ["-A", "VPN_KILL_SWITCH", "-j", "DROP"]
                )

                logger.info("Kill switch enabled")
            else:
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning(f"Kill switch not implemented for {sys.platform}")

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.error(f"Failed to enable kill switch: {e}")
            self.kill_switch_enabled = False
        finally:
            self._publish_event(
                operation="enable_kill_switch",
                stage="kill_switch_enable",
                status=status,
                started_at=started_at,
                mutation=True,
                result_summary={
                    "attempted_command_count": attempted_commands,
                    "kill_switch_enabled": bool(self.kill_switch_enabled),
                    "payloads_redacted": True,
                },
                reason=reason,
            )

    async def _disable_kill_switch(self) -> None:
        """Disable kill switch functionality."""
        started_at = time.monotonic()
        if not self.kill_switch_enabled:
            self._publish_event(
                operation="disable_kill_switch",
                stage="kill_switch_disable",
                status="skipped",
                started_at=started_at,
                mutation=True,
                reason="already_disabled",
            )
            return

        status = "success"
        reason: Optional[str] = None
        attempted_commands = 0
        try:
            if sys.platform.startswith("linux"):
                # Remove VPN_KILL_SWITCH chain
                attempted_commands += 1
                await self._run_iptables_command(["-F", "VPN_KILL_SWITCH"])
                attempted_commands += 1
                await self._run_iptables_command(["-X", "VPN_KILL_SWITCH"])

                logger.info("Kill switch disabled")
            else:
                status = "skipped"
                reason = "unsupported_platform"
                logger.warning(f"Kill switch not implemented for {sys.platform}")

        except Exception as e:
            status = "error"
            reason = "exception"
            logger.error(f"Failed to disable kill switch: {e}")

        self.kill_switch_enabled = False
        self._publish_event(
            operation="disable_kill_switch",
            stage="kill_switch_disable",
            status=status,
            started_at=started_at,
            mutation=True,
            result_summary={
                "attempted_command_count": attempted_commands,
                "kill_switch_enabled": bool(self.kill_switch_enabled),
                "payloads_redacted": True,
            },
            reason=reason,
        )

    async def _run_iptables_command(self, args: List[str]) -> Tuple[bool, str, str]:
        """
        Run an iptables command using SafeSubprocess.

        Args:
            args: List of iptables arguments

        Returns:
            Tuple of (success, stdout, stderr)
        """
        started_at = time.monotonic()
        cmd = ["iptables"] + args
        try:
            result = SafeSubprocess.run(cmd, timeout=10)

            if not result.success:
                logger.warning(f"iptables command failed: {result.stderr}")

            self._publish_event(
                operation="iptables_command",
                stage="iptables_run",
                status="success" if result.success else "failed",
                started_at=started_at,
                mutation=True,
                command=cmd,
                command_result=result,
                reason=None if result.success else "nonzero_return",
            )
            return result.success, result.stdout, result.stderr
        except (ValidationError, SecurityError) as e:
            logger.error(f"iptables command validation failed: {e}")
            self._publish_event(
                operation="iptables_command",
                stage="iptables_run",
                status="blocked",
                started_at=started_at,
                event_type=EventType.TASK_BLOCKED,
                mutation=True,
                command=cmd,
                result_summary={
                    "validation_error_hash": _redacted_sha256_prefix(e),
                    "payloads_redacted": True,
                },
                reason="validation_or_security_error",
            )
            return False, "", str(e)
        except Exception as e:
            logger.error(f"iptables command error: {e}")
            self._publish_event(
                operation="iptables_command",
                stage="iptables_run",
                status="error",
                started_at=started_at,
                event_type=EventType.TASK_BLOCKED,
                mutation=True,
                command=cmd,
                result_summary={
                    "error_hash": _redacted_sha256_prefix(e),
                    "payloads_redacted": True,
                },
                reason="exception",
            )
            return False, "", str(e)

    async def test_dns_leak(
        self, domains: Optional[List[str]] = None
    ) -> LeakTestResult:
        """
        Test for DNS leaks by checking if DNS queries are routed through VPN.

        Args:
            domains: List of test domains to resolve (default: ["example.com", "google.com"])

        Returns:
            LeakTestResult indicating if DNS leak is detected
        """
        started_at = time.monotonic()
        if domains is None:
            domains = ["example.com", "google.com"]

        details: Dict[str, Any] = {"tested_domains": domains, "results": []}

        all_resolved = True

        for domain in domains:
            try:
                dns_ips = await self.doh_resolver.resolve_a(domain)
                resolver_evidence = _resolver_evidence_reference(self.doh_resolver)

                # Verify DNS responses are valid and from expected DNS servers
                if not dns_ips:
                    logger.warning(f"Failed to resolve {domain}")
                    details["results"].append(
                        {
                            "domain": domain,
                            "success": False,
                            "resolver_evidence": resolver_evidence,
                        }
                    )
                    all_resolved = False
                    continue

                details["results"].append(
                    {
                        "domain": domain,
                        "resolved_ips": dns_ips,
                        "success": True,
                        "resolver_evidence": resolver_evidence,
                    }
                )

                logger.debug(f"Resolved {domain} to {dns_ips}")

            except Exception as e:
                logger.error(f"Error resolving {domain}: {e}")
                details["results"].append(
                    {
                        "domain": domain,
                        "error": str(e),
                        "success": False,
                        "resolver_evidence": _resolver_evidence_reference(
                            self.doh_resolver
                        ),
                    }
                )
                all_resolved = False

        # Check if all DNS queries succeeded without leaks
        is_leaking = not all_resolved

        result = LeakTestResult(LeakType.DNS, is_leaking, details)
        self._publish_event(
            operation="test_dns_leak",
            stage="dns_leak_test",
            status="leak_detected" if result.is_leaking else "success",
            started_at=started_at,
            observed_state=True,
            result_summary=_leak_details_summary(result),
        )
        return result

    async def test_ip_leak(self) -> LeakTestResult:
        """Test for IP leaks by checking if public IP matches VPN IP."""
        started_at = time.monotonic()
        details: Dict[str, Any] = {}

        try:
            # Get public IP via HTTP(S) from multiple services
            ip_services = [
                "https://api.ipify.org?format=json",
                "https://httpbin.org/ip",
                "https://icanhazip.com",
            ]

            detected_ips: List[str] = []

            for service in ip_services:
                try:
                    import aiohttp

                    async with aiohttp.ClientSession() as session:
                        async with session.get(
                            service, timeout=aiohttp.ClientTimeout(total=10)
                        ) as response:
                            if response.status == 200:
                                data = await response.text()

                                # Extract IP from response
                                if "json" in service:
                                    try:
                                        import json

                                        parsed = json.loads(data)
                                        if "ip" in parsed:
                                            detected_ips.append(parsed["ip"])
                                    except Exception as e:
                                        logger.debug(
                                            f"Failed to parse JSON from {service}: {e}"
                                        )
                                else:
                                    # Plain text response (icanhazip.com)
                                    ip = data.strip()
                                    if ip:
                                        detected_ips.append(ip)

                except Exception as e:
                    logger.debug(f"Failed to get IP from {service}: {e}")

            details["detected_ips"] = detected_ips

            if len(detected_ips) > 0:
                # Normalize IP addresses (remove any JSON structures or whitespace)
                normalized_ips: List[str] = []
                for ip_str in detected_ips:
                    # Remove any JSON wrapper (like {"origin": "89.125.1.107"})
                    if "{" in ip_str or "}" in ip_str or ":" in ip_str:
                        try:
                            import json

                            parsed = json.loads(ip_str)
                            if "ip" in parsed:
                                normalized_ips.append(parsed["ip"].strip())
                            elif "origin" in parsed:
                                normalized_ips.append(parsed["origin"].strip())
                        except Exception as e:
                            logger.debug(f"Failed to parse IP from JSON: {e}")
                    else:
                        normalized_ips.append(ip_str.strip())

                details["normalized_ips"] = normalized_ips

                # Check if all detected IPs are consistent
                unique_ips = list(set(normalized_ips))
                details["consistent_ip"] = len(unique_ips) == 1

                # Check if public IP matches our expected VPN IP (from environment)
                expected_vpn_ip = os.getenv("VPN_SERVER", "")
                if expected_vpn_ip:
                    is_leaking = expected_vpn_ip not in normalized_ips
                else:
                    # If no VPN_SERVER set, we can't determine if leaking
                    is_leaking = False
                    details["warning"] = (
                        "VPN_SERVER not configured, cannot determine leak status"
                    )
            else:
                is_leaking = True
                details["error"] = "Could not detect public IP"

        except Exception as e:
            logger.error(f"IP leak test failed: {e}")
            details["error"] = str(e)
            is_leaking = True

        result = LeakTestResult(LeakType.IP, is_leaking, details)
        self._publish_event(
            operation="test_ip_leak",
            stage="ip_leak_test",
            status="leak_detected" if result.is_leaking else "success",
            started_at=started_at,
            observed_state=True,
            result_summary=_leak_details_summary(result),
        )
        return result

    async def test_webrtc_leak(self) -> LeakTestResult:
        """Test for WebRTC leaks and apply fixes."""
        started_at = time.monotonic()
        details: Dict[str, Any] = {}

        try:
            # Import and apply WebRTC leak fix
            from .webrtc_leak_fix import get_webrtc_fix

            webrtc_fix = get_webrtc_fix()
            status = webrtc_fix.check_webrtc_status()
            details["fix_status"] = status

            # Apply fixes if not already applied
            if not any(status.values()):
                logger.info("Applying WebRTC leak fixes...")
                results = webrtc_fix.apply_browser_fixes()
                details["fix_results"] = results

            # Check if fixes are now active
            status = webrtc_fix.check_webrtc_status()
            is_leaking = not any(status.values())

            if is_leaking:
                details["warning"] = "WebRTC leak protection not fully active"
                logger.warning("WebRTC leak protection requires browser restart")
            else:
                details["status"] = "WebRTC leak protection active"
                logger.info("WebRTC leak protection is active")

        except Exception as e:
            logger.error(f"WebRTC leak test failed: {e}")
            details["error"] = str(e)
            is_leaking = True

        result = LeakTestResult(LeakType.WebRTC, is_leaking, details)
        self._publish_event(
            operation="test_webrtc_leak",
            stage="webrtc_leak_test",
            status="leak_detected" if result.is_leaking else "success",
            started_at=started_at,
            observed_state=True,
            result_summary=_leak_details_summary(result),
        )
        return result

    async def run_all_tests(self) -> List[LeakTestResult]:
        """Run all leak tests."""
        started_at = time.monotonic()
        tests = await asyncio.gather(
            self.test_dns_leak(), self.test_ip_leak(), self.test_webrtc_leak()
        )

        results = list(tests)
        self._publish_event(
            operation="run_all_tests",
            stage="leak_test_suite",
            status="leak_detected" if any(item.is_leaking for item in results) else "success",
            started_at=started_at,
            observed_state=True,
            result_summary={
                "test_count": len(results),
                "leak_count": sum(1 for item in results if item.is_leaking),
                "leak_types": [item.leak_type.value for item in results if item.is_leaking],
                "payloads_redacted": True,
            },
        )
        return results

    async def get_status(self) -> Dict[str, Any]:
        """Get current protection status."""
        started_at = time.monotonic()
        payload = {
            "protection_enabled": self.protection_enabled,
            "kill_switch_enabled": self.kill_switch_enabled,
            "vpn_interface": self.vpn_interface,
            "original_dns_servers": self.original_dns_servers,
            "resolver_info": self.doh_resolver.get_stats(),
        }
        self._publish_event(
            operation="get_status",
            stage="status_read",
            status="success",
            started_at=started_at,
            observed_state=True,
            result_summary={
                "resolver_info_present": bool(payload.get("resolver_info")),
                "dns_server_count": len(self.original_dns_servers),
                "last_doh_resolution_evidence": _resolver_evidence_reference(
                    self.doh_resolver
                ),
                "payloads_redacted": True,
            },
        )
        return payload


# Global protector instance
_global_protector: Optional[VPNLeakProtector] = None


async def get_vpn_protector() -> VPNLeakProtector:
    """Get or create the global VPN leak protector instance."""
    global _global_protector
    if _global_protector is None:
        _global_protector = VPNLeakProtector()
    return _global_protector


async def test_protection() -> None:
    """Test VPN leak protection functionality."""
    logging.basicConfig(level=logging.DEBUG)

    protector = VPNLeakProtector()

    print("Testing VPN Leak Protection...")
    status = await protector.get_status()
    print(f"Current status: {status}")

    # Run leak tests without VPN
    print("\n=== Running leak tests (VPN NOT connected) ===")
    tests = await protector.run_all_tests()

    for test in tests:
        print(f"  {test}")

    print("\n=== Enabling leak protection ===")
    try:
        await protector.enable_protection()
        status = await protector.get_status()
        print(f"Protection enabled: {status['protection_enabled']}")
        print(f"Kill switch: {status['kill_switch_enabled']}")
    except Exception as e:
        print(f"Error enabling protection: {e}")

    # Run tests with protection
    print("\n=== Running leak tests (VPN connected) ===")
    tests = await protector.run_all_tests()

    for test in tests:
        print(f"  {test}")

    print("\n=== Disabling protection ===")
    try:
        await protector.disable_protection()
        print("Protection disabled")
    except Exception as e:
        print(f"Error disabling protection: {e}")

    print("\nTest completed!")


if __name__ == "__main__":
    try:
        asyncio.run(test_protection())
    except KeyboardInterrupt:
        print("\nTest interrupted")

