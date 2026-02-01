#!/usr/bin/env python3
"""
VPN Chain Manager with Automatic Failover and Health Monitoring
Implements multi-hop VPN chaining with Tor integration and proxy rotation
"""

import asyncio
import json
import logging
import random
import subprocess
import sys
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import aiohttp
import yaml


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DEGRADED = "degraded"
    FAILED = "failed"


class VPNProtocol(Enum):
    WIREGUARD = "wireguard"
    OPENVPN = "openvpn"
    IKEV2 = "ikev2"


@dataclass
class VPNEndpoint:
    """Represents a VPN endpoint configuration"""
    name: str
    host: str
    port: int
    protocol: VPNProtocol
    credentials_path: Optional[str] = None
    weight: int = 1
    health_check_url: str = "https://ifconfig.me"
    last_health_check: Optional[float] = None
    response_time_ms: Optional[float] = None
    state: ConnectionState = ConnectionState.DISCONNECTED
    consecutive_failures: int = 0
    max_failures: int = 3
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "protocol": self.protocol.value,
            "weight": self.weight,
            "state": self.state.value,
            "response_time_ms": self.response_time_ms,
        }


@dataclass
class ProxyConfig:
    """SOCKS/HTTP proxy configuration"""
    host: str
    port: int
    type: str = "socks5"  # socks5, socks4, http
    username: Optional[str] = None
    password: Optional[str] = None
    priority: int = 1


@dataclass
class ChainConfig:
    """VPN chain configuration"""
    hops: List[VPNEndpoint]
    proxy: Optional[ProxyConfig] = None
    tor_enabled: bool = False
    tor_control_port: int = 9051
    tor_socks_port: int = 9050
    rotation_interval: int = 3600  # seconds
    health_check_interval: int = 30  # seconds


class HealthMonitor:
    """Monitors VPN health and detects leaks"""
    
    LEAK_TEST_ENDPOINTS = [
        ("https://ipleak.net/json/", "ip"),
        ("https://dnsleaktest.com/api/servers", "dns"),
        ("https://www.dnsleaktest.com/api/servers", "dns_alt"),
        ("https://browserleaks.com/ip", "webrtc"),
    ]
    
    def __init__(self, expected_exit_ips: Set[str]):
        self.expected_exit_ips = expected_exit_ips
        self.leak_detected = False
        self.last_check_results: Dict = {}
        
    async def check_ip_leak(self, session: aiohttp.ClientSession) -> Tuple[bool, Dict]:
        """Check for IP leaks across multiple endpoints"""
        results = {}
        
        for url, test_type in self.LEAK_TEST_ENDPOINTS:
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results[test_type] = data
                        
                        # Check if detected IP matches expected exit
                        detected_ip = data.get("ip", data.get("query", ""))
                        if detected_ip and detected_ip not in self.expected_exit_ips:
                            self.leak_detected = True
                            logging.error(f"IP LEAK DETECTED: {detected_ip} at {url}")
                            
            except Exception as e:
                logging.warning(f"Health check failed for {url}: {e}")
                
        self.last_check_results = results
        return self.leak_detected, results
    
    async def check_dns_leak(self, session: aiohttp.ClientSession) -> Tuple[bool, List[str]]:
        """Check for DNS leaks"""
        leaked_dns = []
        
        try:
            async with session.get(
                "https://dnsleaktest.com/api/servers",
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    servers = await resp.json()
                    for server in servers:
                        isp = server.get("isp", "").lower()
                        if any(x in isp for x in ["google", "cloudflare", "your_isp"]):
                            continue
                        leaked_dns.append(server.get("ip", ""))
                        
        except Exception as e:
            logging.warning(f"DNS leak check failed: {e}")
            
        return len(leaked_dns) > 0, leaked_dns
    
    async def check_webrtc_leak(self) -> bool:
        """Check WebRTC leaks using external tool"""
        try:
            # This would integrate with browser automation
            # For now, return False (no leak detected)
            return False
        except Exception as e:
            logging.warning(f"WebRTC leak check failed: {e}")
            return False


class VPNChainManager:
    """Manages VPN chains with automatic failover"""
    
    def __init__(self, config_path: str):
        self.config_path = Path(config_path)
        self.config: Optional[ChainConfig] = None
        self.current_chain: List[VPNEndpoint] = []
        self.health_monitor: Optional[HealthMonitor] = None
        self.state = ConnectionState.DISCONNECTED
        self._load_config()
        
    def _load_config(self):
        """Load configuration from YAML"""
        with open(self.config_path, 'r') as f:
            data = yaml.safe_load(f)
            
        endpoints = [
            VPNEndpoint(
                name=e["name"],
                host=e["host"],
                port=e["port"],
                protocol=VPNProtocol(e["protocol"]),
                credentials_path=e.get("credentials_path"),
                weight=e.get("weight", 1),
            )
            for e in data.get("endpoints", [])
        ]
        
        proxy_data = data.get("proxy")
        proxy = None
        if proxy_data:
            proxy = ProxyConfig(**proxy_data)
            
        self.config = ChainConfig(
            hops=endpoints,
            proxy=proxy,
            tor_enabled=data.get("tor_enabled", False),
            tor_control_port=data.get("tor_control_port", 9051),
            tor_socks_port=data.get("tor_socks_port", 9050),
            rotation_interval=data.get("rotation_interval", 3600),
            health_check_interval=data.get("health_check_interval", 30),
        )
        
    def _select_chain(self, num_hops: int = 2) -> List[VPNEndpoint]:
        """Select VPN endpoints for chain using weighted random selection"""
        available = [e for e in self.config.hops if e.state != ConnectionState.FAILED]
        
        if len(available) < num_hops:
            raise ValueError(f"Not enough available endpoints ({len(available)} < {num_hops})")
            
        # Weighted selection without replacement
        selected = []
        weights = [e.weight for e in available]
        
        for _ in range(num_hops):
            if not available:
                break
            total = sum(weights)
            r = random.uniform(0, total)
            cumulative = 0
            
            for i, (endpoint, weight) in enumerate(zip(available, weights)):
                cumulative += weight
                if r <= cumulative:
                    selected.append(endpoint)
                    available.pop(i)
                    weights.pop(i)
                    break
                    
        return selected
    
    async def _health_check_endpoint(self, endpoint: VPNEndpoint) -> bool:
        """Perform health check on endpoint"""
        try:
            start = time.time()
            
            # Use curl through the VPN interface if connected
            cmd = [
                "curl", "-s", "--max-time", "10",
                "--interface", f"tun-{endpoint.name}",
                endpoint.health_check_url
            ]
            
            result = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await result.communicate()
            
            elapsed = (time.time() - start) * 1000
            endpoint.response_time_ms = elapsed
            endpoint.last_health_check = time.time()
            
            if result.returncode == 0:
                endpoint.consecutive_failures = 0
                endpoint.state = ConnectionState.CONNECTED
                return True
            else:
                endpoint.consecutive_failures += 1
                if endpoint.consecutive_failures >= endpoint.max_failures:
                    endpoint.state = ConnectionState.FAILED
                else:
                    endpoint.state = ConnectionState.DEGRADED
                return False
                
        except Exception as e:
            logging.error(f"Health check error for {endpoint.name}: {e}")
            endpoint.consecutive_failures += 1
            endpoint.state = ConnectionState.FAILED
            return False
    
    async def _connect_wireguard(self, endpoint: VPNEndpoint) -> bool:
        """Connect using WireGuard"""
        try:
            interface = f"tun-{endpoint.name}"
            
            # Generate WireGuard config
            config = f"""[Interface]
PrivateKey = $(cat {endpoint.credentials_path}/privatekey)
Address = 10.200.200.2/24
DNS = 1.1.1.1, 1.0.0.1

[Peer]
PublicKey = {endpoint.host}
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = {endpoint.host}:{endpoint.port}
PersistentKeepalive = 25
"""
            
            # Write config
            config_path = f"/etc/wireguard/{interface}.conf"
            with open(config_path, 'w') as f:
                f.write(config)
                
            # Bring up interface
            result = await asyncio.create_subprocess_exec(
                "wg-quick", "up", interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            return result.returncode == 0
            
        except Exception as e:
            logging.error(f"WireGuard connection failed for {endpoint.name}: {e}")
            return False
    
    async def _connect_openvpn(self, endpoint: VPNEndpoint) -> bool:
        """Connect using OpenVPN"""
        try:
            config_path = f"{endpoint.credentials_path}/config.ovpn"
            
            result = await asyncio.create_subprocess_exec(
                "openvpn", "--config", config_path,
                "--daemon",
                f"--log-append", f"/var/log/openvpn-{endpoint.name}.log",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await result.communicate()
            
            return result.returncode == 0
            
        except Exception as e:
            logging.error(f"OpenVPN connection failed for {endpoint.name}: {e}")
            return False
    
    async def connect_chain(self, num_hops: int = 2) -> bool:
        """Establish VPN chain"""
        self.state = ConnectionState.CONNECTING
        
        try:
            # Select chain
            self.current_chain = self._select_chain(num_hops)
            logging.info(f"Selected chain: {' -> '.join(e.name for e in self.current_chain)}")
            
            # Connect each hop
            for i, endpoint in enumerate(self.current_chain):
                logging.info(f"Connecting hop {i+1}/{num_hops}: {endpoint.name}")
                
                if endpoint.protocol == VPNProtocol.WIREGUARD:
                    success = await self._connect_wireguard(endpoint)
                elif endpoint.protocol == VPNProtocol.OPENVPN:
                    success = await self._connect_openvpn(endpoint)
                else:
                    logging.error(f"Unsupported protocol: {endpoint.protocol}")
                    success = False
                    
                if not success:
                    # Rollback and try different endpoint
                    await self.disconnect()
                    endpoint.state = ConnectionState.FAILED
                    return await self.connect_chain(num_hops)
                    
                endpoint.state = ConnectionState.CONNECTED
                
            # Initialize health monitor with expected exit IPs
            exit_ips = {e.host for e in self.current_chain}
            self.health_monitor = HealthMonitor(exit_ips)
            
            self.state = ConnectionState.CONNECTED
            logging.info("VPN chain established successfully")
            return True
            
        except Exception as e:
            logging.error(f"Chain connection failed: {e}")
            self.state = ConnectionState.FAILED
            return False
    
    async def disconnect(self):
        """Disconnect all VPN connections"""
        for endpoint in self.current_chain:
            try:
                if endpoint.protocol == VPNProtocol.WIREGUARD:
                    interface = f"tun-{endpoint.name}"
                    await asyncio.create_subprocess_exec(
                        "wg-quick", "down", interface,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                elif endpoint.protocol == VPNProtocol.OPENVPN:
                    # Kill OpenVPN process
                    await asyncio.create_subprocess_exec(
                        "pkill", "-f", f"openvpn.*{endpoint.name}",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                endpoint.state = ConnectionState.DISCONNECTED
                
            except Exception as e:
                logging.error(f"Disconnect error for {endpoint.name}: {e}")
                
        self.current_chain = []
        self.state = ConnectionState.DISCONNECTED
    
    async def rotate_chain(self):
        """Rotate to new chain"""
        logging.info("Rotating VPN chain...")
        await self.disconnect()
        await asyncio.sleep(2)
        return await self.connect_chain(len(self.current_chain) if self.current_chain else 2)
    
    async def health_check_loop(self):
        """Continuous health monitoring"""
        while self.state == ConnectionState.CONNECTED:
            try:
                # Check each endpoint
                for endpoint in self.current_chain:
                    healthy = await self._health_check_endpoint(endpoint)
                    if not healthy:
                        logging.warning(f"Endpoint {endpoint.name} unhealthy, triggering rotation")
                        await self.rotate_chain()
                        break
                        
                # Check for leaks
                if self.health_monitor:
                    connector = aiohttp.TCPConnector(ssl=False)
                    async with aiohttp.ClientSession(connector=connector) as session:
                        leak_detected, results = await self.health_monitor.check_ip_leak(session)
                        if leak_detected:
                            logging.critical("LEAK DETECTED! Emergency disconnect...")
                            await self.emergency_disconnect()
                            
                await asyncio.sleep(self.config.health_check_interval)
                
            except Exception as e:
                logging.error(f"Health check loop error: {e}")
                await asyncio.sleep(5)
    
    async def emergency_disconnect(self):
        """Emergency disconnect with killswitch activation"""
        logging.critical("EMERGENCY DISCONNECT ACTIVATED")
        
        # Kill all VPN connections
        await self.disconnect()
        
        # Activate killswitch (drop all non-VPN traffic)
        await self._activate_killswitch()
        
        self.state = ConnectionState.FAILED
    
    async def _activate_killswitch(self):
        """Activate network killswitch"""
        try:
            # Flush existing rules
            subprocess.run(["iptables", "-F"], check=False)
            subprocess.run(["iptables", "-X"], check=False)
            
            # Default drop
            subprocess.run(["iptables", "-P", "INPUT", "DROP"], check=False)
            subprocess.run(["iptables", "-P", "FORWARD", "DROP"], check=False)
            subprocess.run(["iptables", "-P", "OUTPUT", "DROP"], check=False)
            
            # Allow loopback
            subprocess.run(["iptables", "-A", "INPUT", "-i", "lo", "-j", "ACCEPT"], check=False)
            subprocess.run(["iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"], check=False)
            
            # Allow established connections
            subprocess.run([
                "iptables", "-A", "INPUT", "-m", "state",
                "--state", "ESTABLISHED,RELATED", "-j", "ACCEPT"
            ], check=False)
            
            logging.info("Killswitch activated - only loopback traffic allowed")
            
        except Exception as e:
            logging.error(f"Killswitch activation failed: {e}")
    
    def get_status(self) -> Dict:
        """Get current status"""
        return {
            "state": self.state.value,
            "current_chain": [e.to_dict() for e in self.current_chain],
            "config": {
                "tor_enabled": self.config.tor_enabled if self.config else False,
                "rotation_interval": self.config.rotation_interval if self.config else 0,
            },
            "health_monitor": {
                "leak_detected": self.health_monitor.leak_detected if self.health_monitor else False,
                "last_results": self.health_monitor.last_check_results if self.health_monitor else {},
            } if self.health_monitor else None,
        }


async def main():
    """Main entry point"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    if len(sys.argv) < 2:
        print("Usage: vpn-chain-manager.py <config.yaml> [command]")
        print("Commands: connect, disconnect, status, rotate")
        sys.exit(1)
        
    config_path = sys.argv[1]
    command = sys.argv[2] if len(sys.argv) > 2 else "connect"
    
    manager = VPNChainManager(config_path)
    
    if command == "connect":
        success = await manager.connect_chain()
        if success:
            # Start health monitoring
            await manager.health_check_loop()
        else:
            sys.exit(1)
            
    elif command == "disconnect":
        await manager.disconnect()
        
    elif command == "status":
        print(json.dumps(manager.get_status(), indent=2))
        
    elif command == "rotate":
        success = await manager.rotate_chain()
        sys.exit(0 if success else 1)
        
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
