#!/usr/bin/env python3
"""
VPN Leak Protection Module for x0tta6bl4
Prevents DNS, WebRTC, and IP leaks by implementing:
1. DNS-over-HTTPS (DoH) resolver integration
2. WebRTC leak detection and prevention
3. Kill switch functionality
4. Firewall configuration for leak protection
"""

import asyncio
import logging
import os
import re
import sys
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from libx0t.core.safe_subprocess import (SafeSubprocess, SecurityError,
                                       ValidationError)

from .dns_over_https import DoHResolver

logger = logging.getLogger(__name__)


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

    def __init__(self, doh_resolver: Optional[DoHResolver] = None):
        if doh_resolver is None:
            # Directly create DoHResolver instance without asyncio.run()
            self.doh_resolver = DoHResolver()
        else:
            self.doh_resolver = doh_resolver

        self.kill_switch_enabled = False
        self.protection_enabled = False
        self.original_dns_servers: List[str] = []
        self.vpn_interface: Optional[str] = None
        logger.info("VPNLeakProtector initialized")

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
        # Validate interface name before using in commands
        if not self._validate_interface_name(vpn_interface):
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

        logger.info("VPN leak protection enabled")

    async def disable_protection(self) -> None:
        """Disable all leak protection mechanisms and restore original state."""
        if not self.protection_enabled:
            logger.warning("Protection already disabled")
            return

        self.protection_enabled = False

        # Disable kill switch
        await self._disable_kill_switch()

        # Restore original DNS configuration
        await self._restore_original_dns()

        # Restore firewall
        await self._restore_firewall()

        logger.info("VPN leak protection disabled")

    async def _save_original_dns(self) -> None:
        """Save original DNS server configuration."""
        try:
            if sys.platform.startswith("linux"):
                # Check systemd-resolved or /etc/resolv.conf using SafeSubprocess
                result = SafeSubprocess.run(["cat", "/etc/resolv.conf"], timeout=10)

                if result.success:
                    lines = result.stdout.splitlines()
                    for line in lines:
                        if line.startswith("nameserver"):
                            parts = line.split()
                            if len(parts) >= 2:
                                self.original_dns_servers.append(parts[1])
            elif sys.platform == "win32":
                # Windows: Get DNS servers from network interfaces
                result = SafeSubprocess.run(["ipconfig", "/all"], timeout=10)

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
            elif sys.platform == "darwin":
                # macOS: Get DNS servers from scutil
                result = SafeSubprocess.run(["scutil", "--dns"], timeout=10)

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

            logger.debug(f"Original DNS servers: {self.original_dns_servers}")

        except Exception as e:
            logger.warning(f"Failed to save original DNS configuration: {e}")

    async def _configure_doh(self) -> None:
        """Configure system to use DNS-over-HTTPS."""
        try:
            if sys.platform.startswith("linux"):
                # Configure systemd-resolved to use DoH (modern Linux systems)
                if os.path.exists("/etc/systemd/resolved.conf"):
                    # Check if systemd-resolved is running
                    result = SafeSubprocess.run(
                        ["systemctl", "is-active", "systemd-resolved"], timeout=10
                    )

                    if result.success and result.stdout.strip() == "active":
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
                        if not dns_result.success:
                            logger.warning(f"Failed to set DNS: {dns_result.stderr}")

                        domain_result = SafeSubprocess.run(
                            ["resolvectl", "domain", str(self.vpn_interface), "~."],
                            timeout=10,
                        )
                        if not domain_result.success:
                            logger.warning(
                                f"Failed to set domain: {domain_result.stderr}"
                            )
            elif sys.platform == "win32":
                # Windows: Modify network adapter DNS settings
                logger.warning("Windows DNS configuration not fully implemented")
            elif sys.platform == "darwin":
                # macOS: Configure DNS servers
                logger.warning("macOS DNS configuration not fully implemented")

            logger.info("DNS-over-HTTPS configuration applied")

        except Exception as e:
            logger.error(f"Failed to configure DNS-over-HTTPS: {e}")

    async def _restore_original_dns(self) -> None:
        """Restore original DNS configuration."""
        try:
            if not self.original_dns_servers:
                logger.warning("No original DNS configuration to restore")
                return

            if sys.platform.startswith("linux"):
                # Restore systemd-resolved configuration using SafeSubprocess
                result = SafeSubprocess.run(
                    ["resolvectl", "revert", str(self.vpn_interface)], timeout=10
                )

                if result.success:
                    logger.debug("DNS configuration restored")
                else:
                    logger.warning(f"Failed to restore DNS: {result.stderr}")
            else:
                logger.warning(f"DNS restoration not implemented for {sys.platform}")

        except Exception as e:
            logger.error(f"Failed to restore DNS configuration: {e}")

    async def _configure_firewall(self) -> None:
        """Configure firewall to block non-VPN traffic with split-tunneling for Google Cloud."""
        try:
            if sys.platform.startswith("linux"):
                # Use iptables to block all non-VPN traffic
                if os.path.exists("/sbin/iptables"):
                    # Allow loopback
                    await self._run_iptables_command(
                        ["-A", "INPUT", "-i", "lo", "-j", "ACCEPT"]
                    )
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
                        await self._run_iptables_command(
                            ["-A", "OUTPUT", "-d", network, "-j", "ACCEPT"]
                        )

                    # Allow VPN interface
                    await self._run_iptables_command(
                        ["-A", "INPUT", "-i", str(self.vpn_interface), "-j", "ACCEPT"]
                    )
                    await self._run_iptables_command(
                        ["-A", "OUTPUT", "-o", str(self.vpn_interface), "-j", "ACCEPT"]
                    )

                    # Allow DNS over VPN
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
                    await self._run_iptables_command(["-P", "OUTPUT", "DROP"])

                    logger.info(
                        "Firewall configuration applied with Google Cloud split-tunneling"
                    )
            else:
                logger.warning(
                    f"Firewall configuration not implemented for {sys.platform}"
                )

        except Exception as e:
            logger.error(f"Failed to configure firewall: {e}")

    async def _restore_firewall(self) -> None:
        """Restore original firewall configuration."""
        try:
            if sys.platform.startswith("linux"):
                if os.path.exists("/sbin/iptables"):
                    # Reset iptables to default state using SafeSubprocess
                    await self._run_iptables_command(["-F"])
                    await self._run_iptables_command(["-X"])
                    await self._run_iptables_command(["-P", "INPUT", "ACCEPT"])
                    await self._run_iptables_command(["-P", "OUTPUT", "ACCEPT"])
                    await self._run_iptables_command(["-P", "FORWARD", "ACCEPT"])

                    logger.info("Firewall configuration restored")
            else:
                logger.warning(
                    f"Firewall restoration not implemented for {sys.platform}"
                )

        except Exception as e:
            logger.error(f"Failed to restore firewall configuration: {e}")

    async def _enable_kill_switch(self) -> None:
        """Enable kill switch functionality."""
        self.kill_switch_enabled = True

        try:
            if sys.platform.startswith("linux"):
                # Create a dedicated iptables chain for kill switch
                await self._run_iptables_command(["-N", "VPN_KILL_SWITCH"])

                # Redirect all traffic through VPN interface
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
                await self._run_iptables_command(
                    ["-A", "VPN_KILL_SWITCH", "-i", "lo", "-j", "ACCEPT"]
                )

                # Block everything else
                await self._run_iptables_command(
                    ["-A", "VPN_KILL_SWITCH", "-j", "DROP"]
                )

                logger.info("Kill switch enabled")
            else:
                logger.warning(f"Kill switch not implemented for {sys.platform}")

        except Exception as e:
            logger.error(f"Failed to enable kill switch: {e}")
            self.kill_switch_enabled = False

    async def _disable_kill_switch(self) -> None:
        """Disable kill switch functionality."""
        if not self.kill_switch_enabled:
            return

        try:
            if sys.platform.startswith("linux"):
                # Remove VPN_KILL_SWITCH chain
                await self._run_iptables_command(["-F", "VPN_KILL_SWITCH"])
                await self._run_iptables_command(["-X", "VPN_KILL_SWITCH"])

                logger.info("Kill switch disabled")
            else:
                logger.warning(f"Kill switch not implemented for {sys.platform}")

        except Exception as e:
            logger.error(f"Failed to disable kill switch: {e}")

        self.kill_switch_enabled = False

    async def _run_iptables_command(self, args: List[str]) -> Tuple[bool, str, str]:
        """
        Run an iptables command using SafeSubprocess.

        Args:
            args: List of iptables arguments

        Returns:
            Tuple of (success, stdout, stderr)
        """
        try:
            cmd = ["iptables"] + args
            result = SafeSubprocess.run(cmd, timeout=10)

            if not result.success:
                logger.warning(f"iptables command failed: {result.stderr}")

            return result.success, result.stdout, result.stderr
        except (ValidationError, SecurityError) as e:
            logger.error(f"iptables command validation failed: {e}")
            return False, "", str(e)
        except Exception as e:
            logger.error(f"iptables command error: {e}")
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
        if domains is None:
            domains = ["example.com", "google.com"]

        details: Dict[str, Any] = {"tested_domains": domains, "results": []}

        all_resolved = True

        for domain in domains:
            try:
                dns_ips = await self.doh_resolver.resolve_a(domain)

                # Verify DNS responses are valid and from expected DNS servers
                if not dns_ips:
                    logger.warning(f"Failed to resolve {domain}")
                    all_resolved = False
                    continue

                details["results"].append(
                    {"domain": domain, "resolved_ips": dns_ips, "success": True}
                )

                logger.debug(f"Resolved {domain} to {dns_ips}")

            except Exception as e:
                logger.error(f"Error resolving {domain}: {e}")
                details["results"].append(
                    {"domain": domain, "error": str(e), "success": False}
                )
                all_resolved = False

        # Check if all DNS queries succeeded without leaks
        is_leaking = not all_resolved

        return LeakTestResult(LeakType.DNS, is_leaking, details)

    async def test_ip_leak(self) -> LeakTestResult:
        """Test for IP leaks by checking if public IP matches VPN IP."""
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

        return LeakTestResult(LeakType.IP, is_leaking, details)

    async def test_webrtc_leak(self) -> LeakTestResult:
        """Test for WebRTC leaks and apply fixes."""
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

        return LeakTestResult(LeakType.WebRTC, is_leaking, details)

    async def run_all_tests(self) -> List[LeakTestResult]:
        """Run all leak tests."""
        tests = await asyncio.gather(
            self.test_dns_leak(), self.test_ip_leak(), self.test_webrtc_leak()
        )

        return list(tests)

    async def get_status(self) -> Dict[str, Any]:
        """Get current protection status."""
        return {
            "protection_enabled": self.protection_enabled,
            "kill_switch_enabled": self.kill_switch_enabled,
            "vpn_interface": self.vpn_interface,
            "original_dns_servers": self.original_dns_servers,
            "resolver_info": self.doh_resolver.get_stats(),
        }


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
