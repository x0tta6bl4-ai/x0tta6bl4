# x0tta6bl4 Mesh Gateway - Setup Guide

## DETECTED LOCALE: RUSSIAN
## DETECTED TASK: MESH GATEWAY SETUP INSTRUCTIONS

---

# detailed Step-by-Step Guide: Routing All Network Traffic Through x0tta6bl4 Mesh Node

This guide describes how to configure your local computer to route all network traffic through a mesh node 'x0tta6bl4' as a transparent proxy gateway.

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Step 1: TUN/TAP Interface Setup](#step-1-tuntap-interface-setup)
4. [Step 2: Network Stack Configuration](#step-2-network-stack-configuration)
5. [Step 3: iptables/nftables Configuration](#step-3-iptablesnftables-configuration)
6. [Step 4: Routing Tables](#step-4-routing-tables)
7. [Step 5: x0tta6bl4 Integration](#step-5-x0tta6bl4-integration)
8. [Step 6: DNS Configuration](#step-6-dns-configuration)
9. [Step 7: Verification and Testing](#step-7-verification-and-testing)
10. [Step 8: Automation and Startup Scripts](#step-8-automation-and-startup-scripts)
11. [Troubleshooting](#troubleshooting)

---

## 1. Architecture Overview

```
+------------------+       +------------------+       +------------------+
|   Local PC      |       |   x0tta6bl4     |       |   Exit Node      |
|  (Entry Node)   |       |   Mesh Node     |       |  (Internet)     |
+------------------+       +------------------+       +------------------+
        |                          |                          |
   +----+----+                +----+----+                +----+----+
   |  tun0   |                |  mesh   |                |  eth0   |
   | 10.0.0.1|<-------------->| network |<-------------->| public  |
   +---------+   SOCKS5/      +---------+   PQC tunnel    +---------+
                 TUN tunnel
                        |
                 +------+------+
                 |  iptables   |
                 |  NAT/MANGLE |
                 +-------------+
```

### Traffic Flow

1. Application generates traffic
2. iptables captures and redirects to TUN interface
3. x0tta6bl4 reads from TUN, routes through mesh
4. Exit node sends to destination, returns response
5. Response travels back through mesh to application

---

## 2. Prerequisites

### System Requirements

```bash
# Check kernel version (must support TUN/TAP)
uname -r  # Should be >= 4.10

# Check for TUN module
lsmod | grep tun
# If not loaded:
sudo modprobe tun

# Install required packages
sudo apt install -y iptables iproute2 iputils-ping dnsutils curl
```

### x0tta6bl4 Requirements

```bash
# Python dependencies
pip install pyroute2 python-iptables tun  # or use system packages

# System packages for TUN/TAP
sudo apt install -y uml-utilities bridge-utils
```

### Permissions

```bash
# Commands require root or CAP_NET_ADMIN
sudo -i  # Run as root
```

---

## Step 1: TUN/TAP Interface Setup

### 1.1 Create TUN Interface

```bash
# Method A: Using ip command (modern)
sudo ip tuntap add dev tun0 mode tun

# Method B: Using tunctl (legacy)
sudo tunctl -t tun0

# Set interface UP
sudo ip link set tun0 up

# Assign IP address (point-to-point)
sudo ip addr add 10.0.0.1/32 dev tun0
sudo ip addr add 10.0.0.2 peer 10.0.0.1 dev tun0  # Alternative: point-to-point
```

### 1.2 Verify TUN Interface

```bash
ip addr show tun0
# Expected output:
# tun0: <POINTOPOINT,MULTICAST,NOARP,UP,LOWER_UP> mtu 1500 qdisc fq_codel state UNKNOWN
#     link/tun 00:00:00:00:00:00
#     inet 10.0.0.1/32 scope global tun0

# Check TUN device exists
ls -la /dev/net/tun
# crw-rw-rw- 1 root root 10, 200 Feb 16 14:00 /dev/net/tun
```

### 1.3 Python TUN Handler (for x0tta6bl4)

```python
# src/network/tun_handler.py
import os
import fcntl
import struct
import asyncio
from typing import Optional

TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000

class TUNInterface:
    """TUN interface handler for x0tta6bl4 mesh gateway."""
    
    def __init__(self, name: str = "tun0", mtu: int = 1500):
        self.name = name
        self.mtu = mtu
        self.fd: Optional[int] = None
        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None
        
    async def create(self) -> bool:
        """Create and configure TUN interface."""
        try:
            # Open /dev/net/tun
            self.fd = os.open("/dev/net/tun", os.O_RDWR | os.O_NONBLOCK)
            
            # Create interface
            ifr = struct.pack(
                f"16sH", 
                self.name.encode(), 
                IFF_TUN | IFF_NO_PI
            )
            fcntl.ioctl(self.fd, TUNSETIFF, ifr)
            
            # Set MTU
            os.system(f"ip link set dev {self.name} mtu {self.mtu}")
            
            # Bring up interface
            os.system(f"ip link set dev {self.name} up")
            
            # Create asyncio stream
            loop = asyncio.get_event_loop()
            self.reader = asyncio.StreamReader()
            self.writer = asyncio.StreamWriter(
                loop.create_connection(
                    lambda: asyncio.StreamReaderProtocol(self.reader),
                    sock=open(self.fd, 'rb')
                )[1]
            )
            
            return True
        except Exception as e:
            print(f"Failed to create TUN: {e}")
            return False
    
    async def read_packet(self) -> Optional[bytes]:
        """Read a packet from TUN interface."""
        if not self.reader:
            return None
        try:
            # Read packet length (2 bytes) + packet data
            header = await self.reader.read(2)
            if len(header) < 2:
                return None
            length = struct.unpack("!H", header)[0]
            packet = await self.reader.read(length)
            return packet
        except Exception:
            return None
    
    async def write_packet(self, packet: bytes) -> bool:
        """Write a packet to TUN interface."""
        if not self.writer:
            return False
        try:
            # Prepend packet length
            self.writer.write(struct.pack("!H", len(packet)) + packet)
            await self.writer.drain()
            return True
        except Exception:
            return False
    
    def close(self):
        """Close TUN interface."""
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
```

---

## Step 2: Network Stack Configuration

### 2.1 Enable IP Forwarding

```bash
# Enable IP forwarding
sudo sysctl -w net.ipv4.ip_forward=1

# Make permanent
echo "net.ipv4.ip_forward=1" | sudo tee -a /etc/sysctl.conf

# Apply
sudo sysctl -p
```

### 2.2 Configure Routing Table

```bash
# Create custom routing table
echo "200 x0tta6bl4_mesh" | sudo tee -a /etc/iproute2/rt_tables

# Add default route through TUN
sudo ip route add default dev tun0 table x0tta6bl4_mesh

# Add local network routes (to not route through mesh)
sudo ip route add 192.168.0.0/16 dev eth0 table main
sudo ip route add 10.0.0.0/8 dev eth0 table main
sudo ip route add 172.16.0.0/12 dev eth0 table main

# Add rule to use mesh table for marked packets
sudo ip rule add fwmark 0x1 table x0tta6bl4_mesh
```

### 2.3 Reverse Path Filtering

```bash
# Disable reverse path filtering (required for asymmetric routing)
sudo sysctl -w net.ipv4.conf.tun0.rp_filter=0
sudo sysctl -w net.ipv4.conf.all.rp_filter=0
```

---

## Step 3: iptables/nftables Configuration

### 3.1 iptables Configuration (Legacy)

```bash
# Flush existing rules (CAUTION: clears all firewall rules)
sudo iptables -F
sudo iptables -t nat -F
sudo iptables -t mangle -F

# Create custom chain for mesh routing
sudo iptables -t mangle -N X0TTA6BL4_MESH

# Mark packets for mesh routing
sudo iptables -t mangle -A OUTPUT -j X0TTA6BL4_MESH
sudo iptables -t mangle -A PREROUTING -j X0TTA6BL4_MESH

# Exclude local traffic
sudo iptables -t mangle -A X0TTA6BL4_MESH -d 10.0.0.0/8 -j RETURN
sudo iptables -t mangle -A X0TTA6BL4_MESH -d 172.16.0.0/12 -j RETURN
sudo iptables -t mangle -A X0TTA6BL4_MESH -d 192.168.0.0/16 -j RETURN
sudo iptables -t mangle -A X0TTA6BL4_MESH -d 127.0.0.0/8 -j RETURN

# Mark remaining packets
sudo iptables -t mangle -A X0TTA6BL4_MESH -j MARK --set-mark 0x1

# NAT for outgoing traffic
sudo iptables -t nat -A POSTROUTING -o tun0 -j MASQUERADE

# Allow forwarding
sudo iptables -A FORWARD -i tun0 -j ACCEPT
sudo iptables -A FORWARD -o tun0 -j ACCEPT

# Save rules
sudo iptables-save > /etc/iptables/rules.v4
```

### 3.2 nftables Configuration (Modern)

```bash
# Create nftables configuration
sudo tee /etc/nftables.conf << 'EOF'
#!/usr/sbin/nft -f

# Flush existing tables
flush ruleset

# Create table for mesh routing
table ip x0tta6bl4_mesh {
    # Mark chain
    chain mark {
        type route hook output priority mangle; policy accept;
        
        # Exclude local traffic
        ip daddr 10.0.0.0/8 accept
        ip daddr 172.16.0.0/12 accept
        ip daddr 192.168.0.0/16 accept
        ip daddr 127.0.0.0/8 accept
        
        # Mark for mesh routing
        meta mark set 0x1
    }
    
    # NAT chain
    chain postrouting {
        type nat hook postrouting priority srcnat; policy accept;
        oifname "tun0" masquerade
    }
    
    # Forward chain
    chain forward {
        type filter hook forward priority filter; policy accept;
        iifname "tun0" accept
        oifname "tun0" accept
    }
}

# Apply
EOF

sudo nft -f /etc/nftables.conf
```

### 3.3 Transparent Proxy with REDIRECT

```bash
# Redirect all TCP traffic to SOCKS5 proxy (port 1080)
sudo iptables -t nat -A OUTPUT -p tcp -m mark --mark 0x1 -j REDIRECT --to-ports 1080

# Or use TPROXY for true transparent proxying
sudo iptables -t mangle -A PREROUTING -p tcp -m mark --mark 0x1 -j TPROXY --on-port 1080 --tproxy-mark 0x1
```

---

## Step 4: Routing Tables

### 4.1 Policy Routing

```bash
# Show current routing tables
ip rule list
# 0:      from all lookup local
# 32766:  from all lookup main
# 32767:  from all lookup default

# Add policy rule for marked packets
sudo ip rule add fwmark 0x1 lookup x0tta6bl4_mesh prio 100

# Verify
ip rule list
# 100:    from all fwmark 0x1 lookup x0tta6bl4_mesh
# 32766:  from all lookup main
# 32767:  from all lookup default
```

### 4.2 Routing Table Contents

```bash
# Show mesh routing table
ip route show table x0tta6bl4_mesh
# default dev tun0 scope link

# Show main routing table
ip route show table main
# default via 192.168.1.1 dev eth0
# 192.168.1.0/24 dev eth0 proto kernel scope link src 192.168.1.100
```

### 4.3 Route Management Script

```bash
#!/bin/bash
# /usr/local/bin/x0tta6bl4-routes.sh

# Variables
TUN_DEV="tun0"
MESH_TABLE="x0tta6bl4_mesh"
MARK=0x1

# Add routes
add_routes() {
    # Create routing table if not exists
    grep -q "$MESH_TABLE" /etc/iproute2/rt_tables || \
        echo "200 $MESH_TABLE" >> /etc/iproute2/rt_tables
    
    # Add default route through TUN
    ip route add default dev $TUN_DEV table $MESH_TABLE 2>/dev/null || \
        ip route replace default dev $TUN_DEV table $MESH_TABLE
    
    # Add policy rule
    ip rule add fwmark $MARK lookup $MESH_TABLE prio 100 2>/dev/null || \
        ip rule replace fwmark $MARK lookup $MESH_TABLE prio 100
    
    echo "Routes added successfully"
}

# Remove routes
remove_routes() {
    ip route del default dev $TUN_DEV table $MESH_TABLE 2>/dev/null
    ip rule del fwmark $MARK lookup $MESH_TABLE 2>/dev/null
    echo "Routes removed successfully"
}

case "$1" in
    add) add_routes ;;
    remove) remove_routes ;;
    *) echo "Usage: $0 {add|remove}" ;;
esac
```

---

## Step 5: x0tta6bl4 Integration

### 5.1 Start SOCKS5 Proxy

```bash
# Start x0tta6bl4 VPN proxy
python3 -m src.network.vpn_proxy --port 1080 --host 127.0.0.1

# Or with mesh routing
python3 -m src.network.vpn_proxy --port 1080 --use-exit

# Or start mesh VPN bridge
python3 -m src.network.mesh_vpn_bridge
```

### 5.2 TUN-to-SOCKS5 Bridge

```python
# src/network/tun_socks_bridge.py
"""
TUN to SOCKS5 Bridge for x0tta6bl4
Reads packets from TUN interface and routes through SOCKS5 proxy.
"""

import asyncio
import struct
import socket
import logging
from typing import Optional, Tuple

from .tun_handler import TUNInterface
from .vpn_proxy import MeshVPNProxy

logger = logging.getLogger(__name__)

class TUNSOCKSBridge:
    """Bridge between TUN interface and SOCKS5 proxy."""
    
    def __init__(
        self,
        tun_name: str = "tun0",
        socks_host: str = "127.0.0.1",
        socks_port: int = 1080
    ):
        self.tun = TUNInterface(tun_name)
        self.socks_host = socks_host
        self.socks_port = socks_port
        self.running = False
        
    async def start(self):
        """Start the bridge."""
        # Create TUN interface
        if not await self.tun.create():
            raise RuntimeError("Failed to create TUN interface")
        
        self.running = True
        logger.info(f"TUN-SOCKS bridge started on {self.tun.name}")
        
        # Start packet processing loop
        await self._process_packets()
    
    async def stop(self):
        """Stop the bridge."""
        self.running = False
        self.tun.close()
    
    async def _process_packets(self):
        """Process packets from TUN interface."""
        while self.running:
            packet = await self.tun.read_packet()
            if packet is None:
                await asyncio.sleep(0.01)
                continue
            
            # Parse IP packet
            try:
                ip_packet = self._parse_ip_packet(packet)
                if ip_packet:
                    await self._route_packet(ip_packet)
            except Exception as e:
                logger.debug(f"Packet processing error: {e}")
    
    def _parse_ip_packet(self, packet: bytes) -> Optional[dict]:
        """Parse IP packet header."""
        if len(packet) < 20:
            return None
        
        version = packet[0] >> 4
        if version != 4:  # Only IPv4 for now
            return None
        
        header_len = (packet[0] & 0x0F) * 4
        protocol = packet[9]
        src_ip = socket.inet_ntoa(packet[12:16])
        dst_ip = socket.inet_ntoa(packet[16:20])
        
        return {
            "version": version,
            "header_len": header_len,
            "protocol": protocol,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "payload": packet[header_len:],
            "raw": packet
        }
    
    async def _route_packet(self, ip_packet: dict):
        """Route packet through SOCKS5 proxy."""
        protocol = ip_packet["protocol"]
        dst_ip = ip_packet["dst_ip"]
        
        # TCP (protocol 6)
        if protocol == 6:
            await self._route_tcp(ip_packet)
        # UDP (protocol 17)
        elif protocol == 17:
            await self._route_udp(ip_packet)
        # ICMP (protocol 1) - skip
        else:
            logger.debug(f"Unsupported protocol: {protocol}")
    
    async def _route_tcp(self, ip_packet: dict):
        """Route TCP packet through SOCKS5."""
        payload = ip_packet["payload"]
        if len(payload) < 20:
            return
        
        # Parse TCP header
        src_port = struct.unpack("!H", payload[0:2])[0]
        dst_port = struct.unpack("!H", payload[2:4])[0]
        
        logger.debug(f"TCP: {ip_packet['src_ip']}:{src_port} -> {ip_packet['dst_ip']}:{dst_port}")
        
        # Connect through SOCKS5
        try:
            reader, writer = await asyncio.wait_for(
                self._socks5_connect(
                    ip_packet["dst_ip"],
                    dst_port
                ),
                timeout=10.0
            )
            
            # Send payload (simplified - real implementation needs TCP state)
            # This is a basic demonstration
            
        except Exception as e:
            logger.debug(f"SOCKS5 connection failed: {e}")
    
    async def _route_udp(self, ip_packet: dict):
        """Route UDP packet through SOCKS5."""
        payload = ip_packet["payload"]
        if len(payload) < 8:
            return
        
        src_port = struct.unpack("!H", payload[0:2])[0]
        dst_port = struct.unpack("!H", payload[2:4])[0]
        
        logger.debug(f"UDP: {ip_packet['src_ip']}:{src_port} -> {ip_packet['dst_ip']}:{dst_port}")
        
        # UDP associate through SOCKS5
        # Implementation depends on SOCKS5 UDP support
    
    async def _socks5_connect(
        self,
        host: str,
        port: int
    ) -> Tuple[asyncio.StreamReader, asyncio.StreamWriter]:
        """Connect to target through SOCKS5 proxy."""
        # Connect to SOCKS5 proxy
        reader, writer = await asyncio.open_connection(
            self.socks_host,
            self.socks_port
        )
        
        # SOCKS5 handshake
        # 1. Greeting
        writer.write(b"\x05\x01\x00")  # Version 5, 1 method, no auth
        await writer.drain()
        
        response = await reader.read(2)
        if response != b"\x05\x00":
            raise RuntimeError("SOCKS5 handshake failed")
        
        # 2. Connect request
        request = b"\x05\x01\x00\x03"  # CONNECT, domain
        request += bytes([len(host)]) + host.encode()
        request += struct.pack("!H", port)
        
        writer.write(request)
        await writer.drain()
        
        # 3. Read response
        response = await reader.read(10)
        if response[1] != 0:
            raise RuntimeError(f"SOCKS5 connect failed: {response[1]}")
        
        return reader, writer


async def main():
    bridge = TUNSOCKSBridge()
    try:
        await bridge.start()
    except KeyboardInterrupt:
        await bridge.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    asyncio.run(main())
```

### 5.3 Complete Gateway Service

```bash
# /etc/systemd/system/x0tta6bl4-gateway.service
[Unit]
Description=x0tta6bl4 Mesh Gateway
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/x0tta6bl4
ExecStartPre=/usr/local/bin/x0tta6bl4-setup.sh
ExecStart=/usr/bin/python3 -m src.network.tun_socks_bridge
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
```

---

## Step 6: DNS Configuration

### 6.1 DNS over HTTPS (DoH)

```bash
# Install systemd-resolved or use dnsmasq
sudo apt install -y systemd-resolved

# Configure DoH
sudo mkdir -p /etc/systemd/resolved.conf.d
sudo tee /etc/systemd/resolved.conf.d/dns_over_https.conf << EOF
[Resolve]
DNS=1.1.1.1#cloudflare-dns.com 9.9.9.9#dns.quad9.net
DNSOverTLS=opportunistic
FallbackDNS=8.8.8.8 8.8.4.4
Cache=yes
EOF

# Restart resolved
sudo systemctl restart systemd-resolved
```

### 6.2 DNS through Mesh

```bash
# Route DNS through mesh (prevent leaks)
sudo iptables -t nat -A OUTPUT -p udp --dport 53 -j REDIRECT --to-ports 5353
sudo iptables -t nat -A OUTPUT -p tcp --dport 53 -j REDIRECT --to-ports 5353

# Start local DNS resolver that uses mesh
python3 -m src.network.dns_over_https --port 5353
```

---

## Step 7: Verification and Testing

### 7.1 Verify TUN Interface

```bash
# Check interface exists
ip addr show tun0

# Check routing
ip route show table x0tta6bl4_mesh

# Check iptables
sudo iptables -t mangle -L -n -v
sudo iptables -t nat -L -n -v
```

### 7.2 Test Connectivity

```bash
# Test through SOCKS5 proxy
curl -x socks5://127.0.0.1:1080 https://ifconfig.me

# Test transparent routing
curl https://ifconfig.me

# Test DNS
dig @127.0.0.1 google.com

# Test with tcpdump
sudo tcpdump -i tun0 -n
```

### 7.3 Check for Leaks

```bash
# DNS leak test
dig @8.8.8.8 test.com +short
# Should fail or return mesh-routed response

# WebRTC leak test (browser)
# Visit: https://browserleaks.com/webrtc

# IP leak test
curl -s https://ipinfo.io/json | jq
```

---

## Step 8: Automation and Startup Scripts

### 8.1 Complete Setup Script

```bash
#!/bin/bash
# /usr/local/bin/x0tta6bl4-setup.sh

set -e

echo "=== x0tta6bl4 Mesh Gateway Setup ==="

# 1. Load TUN module
modprobe tun

# 2. Create TUN interface
ip tuntap add dev tun0 mode tun 2>/dev/null || true
ip link set tun0 up
ip addr add 10.0.0.1/32 dev tun0 2>/dev/null || true

# 3. Enable IP forwarding
sysctl -w net.ipv4.ip_forward=1
sysctl -w net.ipv4.conf.tun0.rp_filter=0
sysctl -w net.ipv4.conf.all.rp_filter=0

# 4. Setup routing table
grep -q "x0tta6bl4_mesh" /etc/iproute2/rt_tables || \
    echo "200 x0tta6bl4_mesh" >> /etc/iproute2/rt_tables

ip route add default dev tun0 table x0tta6bl4_mesh 2>/dev/null || \
    ip route replace default dev tun0 table x0tta6bl4_mesh

ip rule add fwmark 0x1 lookup x0tta6bl4_mesh prio 100 2>/dev/null || \
    ip rule replace fwmark 0x1 lookup x0tta6bl4_mesh prio 100

# 5. Setup iptables
iptables -t mangle -F 2>/dev/null || true
iptables -t nat -F 2>/dev/null || true

iptables -t mangle -N X0TTA6BL4_MESH 2>/dev/null || true
iptables -t mangle -F X0TTA6BL4_MESH

iptables -t mangle -A X0TTA6BL4_MESH -d 10.0.0.0/8 -j RETURN
iptables -t mangle -A X0TTA6BL4_MESH -d 172.16.0.0/12 -j RETURN
iptables -t mangle -A X0TTA6BL4_MESH -d 192.168.0.0/16 -j RETURN
iptables -t mangle -A X0TTA6BL4_MESH -d 127.0.0.0/8 -j RETURN
iptables -t mangle -A X0TTA6BL4_MESH -j MARK --set-mark 0x1

iptables -t mangle -A OUTPUT -j X0TTA6BL4_MESH
iptables -t mangle -A PREROUTING -j X0TTA6BL4_MESH

iptables -t nat -A POSTROUTING -o tun0 -j MASQUERADE
iptables -A FORWARD -i tun0 -j ACCEPT
iptables -A FORWARD -o tun0 -j ACCEPT

# 6. Redirect to SOCKS5
iptables -t nat -A OUTPUT -p tcp -m mark --mark 0x1 -j REDIRECT --to-ports 1080

echo "=== Setup Complete ==="
echo "TUN interface: tun0 (10.0.0.1)"
echo "Routing table: x0tta6bl4_mesh (200)"
echo "SOCKS5 proxy: 127.0.0.1:1080"
```

### 8.2 Teardown Script

```bash
#!/bin/bash
# /usr/local/bin/x0tta6bl4-teardown.sh

echo "=== x0tta6bl4 Mesh Gateway Teardown ==="

# Remove iptables rules
iptables -t mangle -F X0TTA6BL4_MESH 2>/dev/null || true
iptables -t mangle -D OUTPUT -j X0TTA6BL4_MESH 2>/dev/null || true
iptables -t mangle -D PREROUTING -j X0TTA6BL4_MESH 2>/dev/null || true
iptables -t mangle -X X0TTA6BL4_MESH 2>/dev/null || true
iptables -t nat -F 2>/dev/null || true
iptables -F FORWARD 2>/dev/null || true

# Remove routing rules
ip rule del fwmark 0x1 lookup x0tta6bl4_mesh 2>/dev/null || true
ip route del default dev tun0 table x0tta6bl4_mesh 2>/dev/null || true

# Remove TUN interface
ip link set tun0 down 2>/dev/null || true
ip tuntap del dev tun0 mode tun 2>/dev/null || true

echo "=== Teardown Complete ==="
```

---

## Troubleshooting

### Common Issues

#### 1. TUN Interface Not Created

```bash
# Check TUN module
lsmod | grep tun
sudo modprobe tun

# Check permissions
ls -la /dev/net/tun
sudo chmod 666 /dev/net/tun
```

#### 2. No Traffic Through Mesh

```bash
# Check iptables marks
sudo iptables -t mangle -L -n -v

# Check routing rules
ip rule list
ip route show table x0tta6bl4_mesh

# Check SOCKS5 proxy
curl -v -x socks5://127.0.0.1:1080 https://ifconfig.me
```

#### 3. DNS Leaks

```bash
# Check DNS configuration
cat /etc/resolv.conf

# Force DNS through mesh
sudo iptables -t nat -A OUTPUT -p udp --dport 53 -j REDIRECT --to-ports 5353
```

#### 4. Connection Timeout

```bash
# Check mesh connectivity
curl -s http://localhost:8080/mesh/status

# Check exit node
curl -s http://localhost:8080/mesh/peers

# Increase timeout
sysctl -w net.ipv4.tcp_syn_retries=3
```

### Debug Mode

```bash
# Enable verbose logging
export X0TTA6BL4_DEBUG=1
python3 -m src.network.tun_socks_bridge --debug

# Monitor packets
sudo tcpdump -i tun0 -n -vv

# Monitor iptables
sudo watch -n 1 'iptables -t mangle -L -n -v'
```

---

## Security Considerations

1. **Kill Switch**: Implement automatic traffic blocking if mesh fails
2. **DNS Leak Prevention**: Always route DNS through mesh
3. **IPv6**: Disable or route through mesh to prevent leaks
4. **WebRTC**: Configure browser to disable WebRTC

```bash
# Kill switch implementation
iptables -A OUTPUT ! -o tun0 -m mark ! --mark 0x1 -j DROP

# Disable IPv6
sysctl -w net.ipv6.conf.all.disable_ipv6=1
```

---

## References

- [Linux TUN/TAP Documentation](https://www.kernel.org/doc/Documentation/networking/tuntap.txt)
- [iptables Tutorial](https://www.frozentux.net/iptables-tutorial/iptables-tutorial.html)
- [Policy Routing](https://lartc.org/howto/lartc.rpdb.html)
- [SOCKS5 Protocol RFC 1928](https://tools.ietf.org/html/rfc1928)