"""
Automated Kill-Switch for Geo-Leak Detector
Implements emergency network isolation when leaks are detected
"""
import asyncio
import subprocess
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, List
from dataclasses import dataclass

import structlog

from config.settings import settings
from src.core.leak_detector import LeakEvent, LeakType


logger = structlog.get_logger()


class KillSwitchAction(Enum):
    """Available kill-switch actions"""
    BLOCK_ALL_TRAFFIC = "block_all_traffic"
    KILL_VPN = "kill_vpn"
    KILL_BROWSERS = "kill_browsers"
    FLUSH_DNS = "flush_dns"
    DISABLE_IPV6 = "disable_ipv6"
    BLOCK_NON_VPN = "block_non_vpn"


@dataclass
class KillSwitchResult:
    """Result of kill-switch action"""
    action: KillSwitchAction
    success: bool
    timestamp: datetime
    message: str
    details: Optional[Dict] = None


class KillSwitchManager:
    """
    Automated Kill-Switch Manager
    
    Implements defense-in-depth network isolation when geolocation
    leaks are detected. Based on ANTI_GEOLOCATION_HARDENING_GUIDE.md
    emergency protocols.
    """
    
    def __init__(self):
        self.enabled = settings.detection.auto_remediate
        self.script_path = settings.detection.killswitch_script
        self.action_history: List[KillSwitchResult] = []
        self.logger = structlog.get_logger().bind(component="killswitch")
        
        # Action mapping for leak types
        self.leak_actions: Dict[LeakType, List[KillSwitchAction]] = {
            LeakType.IP_LEAK: [
                KillSwitchAction.KILL_VPN,
                KillSwitchAction.BLOCK_NON_VPN,
                KillSwitchAction.KILL_BROWSERS
            ],
            LeakType.DNS_LEAK: [
                KillSwitchAction.FLUSH_DNS,
                KillSwitchAction.BLOCK_ALL_TRAFFIC
            ],
            LeakType.WEBRTC_LEAK: [
                KillSwitchAction.KILL_BROWSERS,
                KillSwitchAction.BLOCK_ALL_TRAFFIC
            ],
            LeakType.IPV6_LEAK: [
                KillSwitchAction.DISABLE_IPV6,
                KillSwitchAction.BLOCK_NON_VPN
            ],
            LeakType.GEOLOCATION_LEAK: [
                KillSwitchAction.KILL_BROWSERS,
                KillSwitchAction.BLOCK_ALL_TRAFFIC
            ],
        }
    
    async def trigger(self, leak: LeakEvent) -> List[KillSwitchResult]:
        """
        Trigger kill-switch for a detected leak
        
        Args:
            leak: The detected leak event
            
        Returns:
            List of action results
        """
        if not self.enabled:
            self.logger.warning("Kill-switch is disabled, skipping remediation")
            return []
        
        self.logger.critical(
            "Kill-switch triggered",
            leak_type=leak.leak_type.value,
            severity=leak.severity.value
        )
        
        results = []
        actions = self.leak_actions.get(leak.leak_type, [KillSwitchAction.BLOCK_ALL_TRAFFIC])
        
        for action in actions:
            try:
                result = await self._execute_action(action)
                results.append(result)
                
                if result.success:
                    self.logger.info(
                        f"Kill-switch action executed: {action.value}",
                        message=result.message
                    )
                else:
                    self.logger.error(
                        f"Kill-switch action failed: {action.value}",
                        message=result.message
                    )
                    
            except Exception as e:
                self.logger.error(
                    f"Exception during kill-switch action: {action.value}",
                    error=str(e)
                )
                results.append(KillSwitchResult(
                    action=action,
                    success=False,
                    timestamp=datetime.utcnow(),
                    message=f"Exception: {str(e)}"
                ))
        
        self.action_history.extend(results)
        return results
    
    async def _execute_action(self, action: KillSwitchAction) -> KillSwitchResult:
        """Execute a specific kill-switch action"""
        timestamp = datetime.utcnow()
        
        action_handlers = {
            KillSwitchAction.BLOCK_ALL_TRAFFIC: self._block_all_traffic,
            KillSwitchAction.KILL_VPN: self._kill_vpn,
            KillSwitchAction.KILL_BROWSERS: self._kill_browsers,
            KillSwitchAction.FLUSH_DNS: self._flush_dns,
            KillSwitchAction.DISABLE_IPV6: self._disable_ipv6,
            KillSwitchAction.BLOCK_NON_VPN: self._block_non_vpn,
        }
        
        handler = action_handlers.get(action)
        if handler:
            return await handler(timestamp)
        
        return KillSwitchResult(
            action=action,
            success=False,
            timestamp=timestamp,
            message="Unknown action"
        )
    
    async def _block_all_traffic(self, timestamp: datetime) -> KillSwitchResult:
        """Block all outbound traffic using iptables/nftables"""
        try:
            # Try nftables first (modern)
            nft_result = subprocess.run(
                ["nft", "add", "table", "inet", "killswitch"],
                capture_output=True,
                text=True
            )
            
            if nft_result.returncode == 0:
                # Create nftables rules
                commands = [
                    ["nft", "add", "chain", "inet", "killswitch", "output", "{ type filter hook output priority 0 ; }"],
                    ["nft", "add", "rule", "inet", "killswitch", "output", "drop"],
                ]
                
                for cmd in commands:
                    subprocess.run(cmd, capture_output=True, text=True)
                
                return KillSwitchResult(
                    action=KillSwitchAction.BLOCK_ALL_TRAFFIC,
                    success=True,
                    timestamp=timestamp,
                    message="All outbound traffic blocked via nftables",
                    details={"method": "nftables"}
                )
            
            # Fallback to iptables
            iptables_result = subprocess.run(
                ["iptables", "-A", "OUTPUT", "-j", "DROP"],
                capture_output=True,
                text=True
            )
            
            if iptables_result.returncode == 0:
                return KillSwitchResult(
                    action=KillSwitchAction.BLOCK_ALL_TRAFFIC,
                    success=True,
                    timestamp=timestamp,
                    message="All outbound traffic blocked via iptables",
                    details={"method": "iptables"}
                )
            
            return KillSwitchResult(
                action=KillSwitchAction.BLOCK_ALL_TRAFFIC,
                success=False,
                timestamp=timestamp,
                message=f"Failed to block traffic: {iptables_result.stderr}",
                details={"nftables_error": nft_result.stderr, "iptables_error": iptables_result.stderr}
            )
            
        except Exception as e:
            return KillSwitchResult(
                action=KillSwitchAction.BLOCK_ALL_TRAFFIC,
                success=False,
                timestamp=timestamp,
                message=f"Exception: {str(e)}"
            )
    
    async def _kill_vpn(self, timestamp: datetime) -> KillSwitchResult:
        """Kill VPN connections"""
        killed_processes = []
        errors = []
        
        # Kill OpenVPN
        try:
            result = subprocess.run(
                ["pkill", "-f", "openvpn"],
                capture_output=True,
                text=True
            )
            killed_processes.append("openvpn")
        except Exception as e:
            errors.append(f"openvpn: {str(e)}")
        
        # Kill WireGuard
        try:
            result = subprocess.run(
                ["wg-quick", "down", "all"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                killed_processes.append("wireguard")
        except Exception as e:
            errors.append(f"wireguard: {str(e)}")
        
        # Kill Cloudflare WARP
        try:
            result = subprocess.run(
                ["pkill", "-f", "warp-svc"],
                capture_output=True,
                text=True
            )
            killed_processes.append("warp")
        except Exception as e:
            errors.append(f"warp: {str(e)}")
        
        # Kill Xray/V2Ray
        try:
            result = subprocess.run(
                ["pkill", "-f", "xray"],
                capture_output=True,
                text=True
            )
            killed_processes.append("xray")
        except Exception as e:
            errors.append(f"xray: {str(e)}")
        
        return KillSwitchResult(
            action=KillSwitchAction.KILL_VPN,
            success=len(killed_processes) > 0,
            timestamp=timestamp,
            message=f"Killed VPN processes: {', '.join(killed_processes)}" if killed_processes else "No VPN processes found",
            details={"killed": killed_processes, "errors": errors}
        )
    
    async def _kill_browsers(self, timestamp: datetime) -> KillSwitchResult:
        """Kill browser processes"""
        killed_processes = []
        browsers = ["firefox", "chrome", "chromium", "brave", "opera", "edge"]
        
        for browser in browsers:
            try:
                result = subprocess.run(
                    ["pkill", "-f", browser],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    killed_processes.append(browser)
            except Exception:
                pass
        
        return KillSwitchResult(
            action=KillSwitchAction.KILL_BROWSERS,
            success=True,
            timestamp=timestamp,
            message=f"Killed browser processes: {', '.join(killed_processes)}" if killed_processes else "No browser processes found",
            details={"killed": killed_processes}
        )
    
    async def _flush_dns(self, timestamp: datetime) -> KillSwitchResult:
        """Flush DNS cache and restart DNS services"""
        actions = []
        errors = []
        
        # Flush systemd-resolved
        try:
            result = subprocess.run(
                ["systemd-resolve", "--flush-caches"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                actions.append("flushed_systemd_resolve")
        except Exception as e:
            errors.append(f"systemd-resolve: {str(e)}")
        
        # Restart cloudflared
        try:
            result = subprocess.run(
                ["systemctl", "restart", "cloudflared-proxy-dns"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                actions.append("restarted_cloudflared")
        except Exception as e:
            errors.append(f"cloudflared: {str(e)}")
        
        # Restart dnscrypt-proxy
        try:
            result = subprocess.run(
                ["systemctl", "restart", "dnscrypt-proxy"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                actions.append("restarted_dnscrypt")
        except Exception as e:
            errors.append(f"dnscrypt-proxy: {str(e)}")
        
        # Clear local DNS cache
        try:
            result = subprocess.run(
                ["resolvectl", "flush-caches"],
                capture_output=True,
                text=True
            )
            if result.returncode == 0:
                actions.append("flushed_resolvectl")
        except Exception as e:
            errors.append(f"resolvectl: {str(e)}")
        
        return KillSwitchResult(
            action=KillSwitchAction.FLUSH_DNS,
            success=len(actions) > 0,
            timestamp=timestamp,
            message=f"DNS actions: {', '.join(actions)}" if actions else "No DNS actions performed",
            details={"actions": actions, "errors": errors}
        )
    
    async def _disable_ipv6(self, timestamp: datetime) -> KillSwitchResult:
        """Disable IPv6 at kernel level"""
        try:
            # Disable IPv6
            sysctl_commands = [
                ["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=1"],
                ["sysctl", "-w", "net.ipv6.conf.default.disable_ipv6=1"],
                ["sysctl", "-w", "net.ipv6.conf.lo.disable_ipv6=1"],
            ]
            
            success_count = 0
            for cmd in sysctl_commands:
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    success_count += 1
            
            return KillSwitchResult(
                action=KillSwitchAction.DISABLE_IPV6,
                success=success_count > 0,
                timestamp=timestamp,
                message=f"IPv6 disabled on {success_count}/3 interfaces",
                details={"success_count": success_count}
            )
            
        except Exception as e:
            return KillSwitchResult(
                action=KillSwitchAction.DISABLE_IPV6,
                success=False,
                timestamp=timestamp,
                message=f"Exception: {str(e)}"
            )
    
    async def _block_non_vpn(self, timestamp: datetime) -> KillSwitchResult:
        """Block all non-VPN traffic"""
        try:
            # Get VPN interface (commonly tun0, wg0, etc.)
            vpn_interfaces = ["tun0", "tun1", "wg0", "wg1", "warp"]
            active_vpn = None
            
            for iface in vpn_interfaces:
                result = subprocess.run(
                    ["ip", "link", "show", iface],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    active_vpn = iface
                    break
            
            if not active_vpn:
                # No VPN interface found, block everything
                return await self._block_all_traffic(timestamp)
            
            # Block all traffic except through VPN interface
            commands = [
                ["iptables", "-F", "OUTPUT"],  # Flush existing rules
                ["iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"],  # Allow loopback
                ["iptables", "-A", "OUTPUT", "-o", active_vpn, "-j", "ACCEPT"],  # Allow VPN
                ["iptables", "-A", "OUTPUT", "-j", "DROP"],  # Drop everything else
            ]
            
            for cmd in commands:
                subprocess.run(cmd, capture_output=True, text=True)
            
            return KillSwitchResult(
                action=KillSwitchAction.BLOCK_NON_VPN,
                success=True,
                timestamp=timestamp,
                message=f"Blocked non-VPN traffic, allowed through {active_vpn}",
                details={"vpn_interface": active_vpn}
            )
            
        except Exception as e:
            return KillSwitchResult(
                action=KillSwitchAction.BLOCK_NON_VPN,
                success=False,
                timestamp=timestamp,
                message=f"Exception: {str(e)}"
            )
    
    async def restore_network(self) -> List[KillSwitchResult]:
        """Restore network connectivity after emergency"""
        results = []
        timestamp = datetime.utcnow()
        
        # Restore iptables
        try:
            subprocess.run(["iptables", "-F", "OUTPUT"], capture_output=True)
            results.append(KillSwitchResult(
                action=KillSwitchAction.BLOCK_ALL_TRAFFIC,
                success=True,
                timestamp=timestamp,
                message="Restored iptables rules"
            ))
        except Exception as e:
            results.append(KillSwitchResult(
                action=KillSwitchAction.BLOCK_ALL_TRAFFIC,
                success=False,
                timestamp=timestamp,
                message=f"Failed to restore iptables: {str(e)}"
            ))
        
        # Restore IPv6
        try:
            subprocess.run(
                ["sysctl", "-w", "net.ipv6.conf.all.disable_ipv6=0"],
                capture_output=True
            )
            results.append(KillSwitchResult(
                action=KillSwitchAction.DISABLE_IPV6,
                success=True,
                timestamp=timestamp,
                message="Restored IPv6"
            ))
        except Exception as e:
            results.append(KillSwitchResult(
                action=KillSwitchAction.DISABLE_IPV6,
                success=False,
                timestamp=timestamp,
                message=f"Failed to restore IPv6: {str(e)}"
            ))
        
        self.logger.info("Network restoration attempted", results=len(results))
        return results
    
    def get_status(self) -> Dict:
        """Get kill-switch status"""
        return {
            "enabled": self.enabled,
            "script_path": self.script_path,
            "total_actions": len(self.action_history),
            "recent_actions": [
                {
                    "action": r.action.value,
                    "success": r.success,
                    "timestamp": r.timestamp.isoformat(),
                    "message": r.message
                }
                for r in self.action_history[-10:]
            ]
        }
