# Anti-Geolocation & Anonymity Hardening System

A comprehensive, production-ready implementation of multi-layered anti-geolocation and anonymity hardening that addresses the complete threat model of IP-based geolocation, DNS leakage, WebRTC exposure, browser fingerprinting, behavioral tracking, and advanced correlation attacks.

## Overview

This system provides defense-in-depth anonymization across network, transport, application, and identity layers with automated monitoring and remediation capabilities.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ANTI-GEOLOCATION SYSTEM                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    IDENTITY COMPARTMENTALIZATION                     │   │
│  │   Isolated container/VM profiles with distinct fingerprints         │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    APPLICATION LAYER (Browser)                       │   │
│  │   • WebRTC elimination        • Canvas/WebGL randomization          │   │
│  │   • Geolocation blocking      • Fingerprint spoofing                │   │
│  │   • Cookie isolation          • Timezone spoofing                   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    TRANSPORT LAYER                                   │   │
│  │   • DoH/DoT/ODoH DNS          • Traffic shaping                     │   │
│  │   • Timing obfuscation        • Cover traffic                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    NETWORK LAYER                                     │   │
│  │   • VPN chaining              • Tor integration                     │   │
│  │   • Proxy rotation            • Automatic failover                  │   │
│  │   • Health monitoring         • Killswitch                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    SYSTEM LAYER                                      │   │
│  │   • MAC rotation              • Hostname randomization              │   │
│  │   • NTP privacy               • Hardware obfuscation                │   │
│  │   • IPv6 disable              • Machine ID spoofing                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    MONITORING & ALERTING                             │   │
│  │   • Real-time leak detection  • Automated remediation               │   │
│  │   • Multi-channel alerts      • Event logging                       │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Installation

```bash
# Clone or download the repository
cd anti-geolocation-system

# Run the installation script
sudo ./deployment/install.sh

# Verify installation
sudo ./deployment/verify.sh
```

### Basic Usage

```bash
# Enable killswitch (do this AFTER connecting to VPN)
sudo killswitch enable

# Check killswitch status
sudo killswitch status

# Setup encrypted DNS
sudo dns-proxy setup

# Apply traffic shaping
sudo traffic-shaper full

# Harden system
sudo system-harden apply

# Create identity profile
sudo identity-manager create "Anonymous Profile"

# Start leak monitoring
sudo systemctl start leak-detector
```

## Layer 1: Network Anonymization

### VPN Chain Manager

Multi-hop VPN chaining with automatic failover and health monitoring.

**Features:**
- Weighted random endpoint selection
- Automatic chain rotation
- Health monitoring with leak detection
- Emergency killswitch activation

**Configuration:** Edit `/etc/anti-geolocation/vpn-chain-config.yaml`

```yaml
endpoints:
  - name: mullvad-se1
    host: se1-wireguard.mullvad.net
    port: 51820
    protocol: wireguard
    credentials_path: /etc/wireguard/mullvad/se1
    weight: 10
```

**Usage:**
```bash
# Start VPN chain
sudo systemctl start vpn-chain

# Rotate chain manually
sudo python3 /opt/anti-geolocation/network-layer/vpn-chain-manager.py /etc/anti-geolocation/vpn-chain-config.yaml rotate
```

### Killswitch

Network killswitch that drops all non-VPN traffic.

```bash
# Enable killswitch
sudo killswitch enable

# Disable killswitch
sudo killswitch disable

# Test killswitch
sudo killswitch test

# Monitor VPN and auto-enable killswitch
sudo killswitch monitor
```

## Layer 2: Transport Security

### Encrypted DNS (DoH/DoT/ODoH)

```bash
# Install and configure all DNS proxies
sudo dns-proxy setup

# Check status
sudo dns-proxy status

# Test DNS
sudo dns-proxy test
```

**Services configured:**
- cloudflared (DoH) on 127.0.0.1:5053
- dnscrypt-proxy (ODoH) on 127.0.0.1:5300
- systemd-resolved (DoT) on 127.0.0.1:53

### Traffic Shaping

```bash
# Apply full traffic shaping
sudo traffic-shaper full

# Add timing obfuscation
sudo traffic-shaper timing

# Enable cover traffic
sudo traffic-shaper cover

# Check status
sudo traffic-shaper status
```

## Layer 3: Application Hardening

### Firefox

Copy the hardening configuration to your Firefox profile:

```bash
# Find your Firefox profile
ls ~/.mozilla/firefox/*.default*/

# Copy user.js
cp application-layer/firefox-hardening.js ~/.mozilla/firefox/XXXXXX.default/user.js

# Restart Firefox
```

**Key settings:**
- WebRTC completely disabled
- Resist Fingerprinting (RFP) enabled
- Geolocation API disabled
- DNS over HTTPS enabled
- Total Cookie Protection enabled

### Chrome/Chromium

```bash
# Apply Chrome hardening
sudo ./application-layer/chrome-hardening.sh setup

# Use hardened launcher
google-chrome-hardened
```

## Layer 4: System Hardening

```bash
# Apply all system hardening
sudo system-harden apply

# Check status
sudo system-harden status

# Rotate MAC address
sudo system-harden mac eth0

# Change hostname
sudo system-harden hostname

# Spoof machine ID
sudo system-harden machine-id
```

**Features:**
- Automatic MAC address rotation
- Hostname randomization
- NTP privacy configuration
- IPv6 disablement
- Machine ID spoofing

## Layer 5: Identity Compartmentalization

```bash
# Create new identity profile
sudo identity-manager create "Shopping Profile" --description "For online shopping"

# List all profiles
sudo identity-manager list

# Activate profile
sudo identity-manager activate <profile-id>

# Create Docker container for profile
sudo identity-manager docker create <profile-id>

# Run container
sudo identity-manager docker run <profile-id>
```

Each profile includes:
- Unique browser fingerprint
- Randomized MAC address
- Unique hostname
- Specific timezone/locale
- Isolated container environment

## Layer 6: Monitoring & Alerting

```bash
# Start leak detector
sudo systemctl start leak-detector

# Run single check
sudo leak-detector check

# Check status
sudo leak-detector status
```

**Configuration:** Edit `/etc/anti-geolocation/leak-detector.yaml`

```yaml
expected_exit_ips:
  - "104.16.XXX.XXX"  # Your VPN exit IPs

alert:
  email_enabled: true
  email_recipients:
    - alerts@example.com
  telegram_enabled: true
  telegram_bot_token: "YOUR_BOT_TOKEN"
  telegram_chat_id: "YOUR_CHAT_ID"
```

## Verification

### Automated Verification

```bash
sudo ./deployment/verify.sh
```

### Manual Verification

Visit these sites to verify protection:

| Test | URL | Expected Result |
|------|-----|-----------------|
| IP leak | https://ipleak.net | VPN IP only |
| DNS leak | https://dnsleaktest.com | No ISP DNS |
| WebRTC | https://browserleaks.com/webrtc | No host candidates |
| Canvas | https://browserleaks.com/canvas | Randomized |
| WebGL | https://browserleaks.com/webgl | Generic renderer |
| Fingerprint | https://coveryourtracks.eff.org | "Not unique" |
| IPv6 | https://test-ipv6.com | No IPv6 connectivity |

## Threat Mitigations

| Threat | Control | Implementation |
|--------|---------|----------------|
| IP geolocation | VPN chaining + killswitch | `vpn-chain-manager.py`, `killswitch.sh` |
| DNS leaks | DoH/DoT/ODoH | `dns-proxy.sh` |
| WebRTC leaks | Browser config + disable | `firefox-hardening.js` |
| Browser fingerprinting | RFP + randomization | `firefox-hardening.js`, `chrome-hardening.sh` |
| Behavioral tracking | Container isolation | `container-manager.py` |
| MAC tracking | MAC rotation | `linux-hardening.sh` |
| Timing analysis | Traffic shaping | `traffic-shaper.sh` |
| Hardware fingerprinting | DMI spoofing | `linux-hardening.sh` |

## Directory Structure

```
anti-geolocation-system/
├── network-layer/
│   ├── vpn-chain-manager.py      # VPN chain management
│   ├── vpn-chain-config.yaml     # VPN configuration
│   └── killswitch.sh             # Network killswitch
├── transport-layer/
│   ├── dns-proxy.sh              # Encrypted DNS setup
│   └── traffic-shaper.sh         # Traffic shaping
├── application-layer/
│   ├── firefox-hardening.js      # Firefox configuration
│   └── chrome-hardening.sh       # Chrome hardening
├── system-hardening/
│   └── linux-hardening.sh        # System hardening
├── identity-compartmentalization/
│   └── container-manager.py      # Identity management
├── monitoring/
│   └── leak-detector.py          # Leak detection
├── deployment/
│   ├── install.sh                # Installation script
│   └── verify.sh                 # Verification script
└── README.md                     # This file
```

## System Requirements

- Linux (Debian/Ubuntu, Fedora, Arch)
- Root access
- Python 3.8+
- systemd
- iptables
- WireGuard or OpenVPN

## Security Considerations

1. **VPN Credentials:** Store VPN credentials securely (e.g., in a password manager)
2. **Alert Channels:** Configure secure alert channels (avoid personal accounts)
3. **Regular Updates:** Keep the system and all components updated
4. **Testing:** Always test thoroughly before relying on this system
5. **Operational Security:** Follow operational security protocols in `ops-security/`

## Troubleshooting

### VPN Connection Issues

```bash
# Check VPN status
sudo systemctl status vpn-chain

# View logs
sudo journalctl -u vpn-chain -f

# Test killswitch
sudo killswitch test
```

### DNS Issues

```bash
# Check DNS proxy status
sudo systemctl status cloudflared-proxy-dns
sudo systemctl status dnscrypt-proxy

# Test DNS resolution
dig @127.0.0.1 cloudflare.com
dig @127.0.0.1 -p 5053 cloudflare.com
dig @127.0.0.1 -p 5300 cloudflare.com
```

### Browser Issues

```bash
# Reset Firefox profile
rm -rf ~/.mozilla/firefox/*.default*/
# Reapply hardening

# Check Chrome policies
chrome://policy/
```

## License

This project is provided for educational and privacy protection purposes. Users are responsible for complying with local laws and regulations.

## Disclaimer

This system provides strong privacy protections but cannot guarantee complete anonymity. Advanced adversaries may still be able to correlate activity through:
- Behavioral biometrics
- Traffic analysis
- Correlation attacks
- Targeted exploitation

Use this system as part of a comprehensive operational security strategy.

## Contributing

Contributions are welcome. Please ensure:
1. Code follows existing style
2. Changes are well-documented
3. Security implications are considered
4. Tests are included where applicable

## Support

For issues and questions:
1. Check the troubleshooting section
2. Review the logs in `/var/log/anti-geolocation/`
3. Verify configuration files
4. Test components individually
