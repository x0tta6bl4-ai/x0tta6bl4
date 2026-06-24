# x0tta6bl4 Xray VPS Deployment System

Xray Core deployment system with VLESS-XTLS-Reality-Vision as the current
production profile and fallback examples quarantined until external validation
proves they work for real users.

## Current production profile policy

As of the latest local validation, only **VLESS-XTLS-Reality-Vision on TCP port
443** is distributable to users.

Do not distribute profiles for ports **8443**, **9443**, **8388**, or **8080**
until `sudo bash scripts/validate-installation.sh` proves external reachability
for that exact public port. Local Xray listeners are not enough proof: a router,
NAT rule, or another TLS service can still make a profile fail for real users.

Fallback examples that are not externally verified are kept in
`clients/quarantine-unverified/` and are reference material only.

## 🌟 Features

- **VLESS-XTLS-Reality-Vision** - Primary protocol with maximum speed and security
- **Trojan-XTLS-Reality** - Fallback #1, issue only after external validation
- **VLESS-splitHTTP/xHTTP** - Fallback #2, issue only after external validation
- **Shadowsocks 2022** - Fallback #3, issue only after external validation
- **ShadowTLS/VMess WebSocket** - Fallback #4, issue only after external validation
- **Automatic WARP routing** for Google/Netflix services
- **BBR TCP optimization** for best performance
- **Comprehensive health checks** and monitoring
- **One-command deployment** with automatic validation

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Client Compatibility](#client-compatibility)
- [Installation](#installation)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Security](#security)
- [License](#license)

## 🚀 Quick Start

```bash
# Clone and install
git clone https://github.com/x0tta6bl4/xray-vps.git
cd x0tta6bl4-xray-vps

# Run installation script
sudo bash scripts/install-xray.sh

# Validate installation
sudo bash scripts/validate-installation.sh
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Client Devices                        │
│  (FlClashX / v2rayN / Nekoray / Shadowrocket / Streisand)   │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    x0tta6bl4 VPS Server                      │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Xray Core v25.1.30                  │   │
│  ├─────────────────────────────────────────────────────┤   │
│  │  Port 443  │ VLESS-XTLS-Reality-Vision (Primary)    │   │
│  │  Port 9443 │ Trojan-XTLS-Reality (validate first)   │   │
│  │  Port 8443 │ VLESS-splitHTTP/xHTTP (validate first) │   │
│  │  Port 8388 │ Shadowsocks 2022 (validate first)      │   │
│  │  Port 8080 │ ShadowTLS/VMess (validate first)       │   │
│  └─────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Traffic Routing & Filtering             │   │
│  │  • GeoIP/Geosite blocking (CN, private)             │   │
│  │  • Ad blocking                                      │   │
│  │  • WARP routing for Google/Netflix                │   │
│  └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

See [Architecture Diagram](docs/architecture-diagram.md) for detailed visual documentation.

## 📱 Client Compatibility Matrix

| Client | Platform | VLESS-Reality :443 | Fallback profiles |
|--------|----------|:------------------:|:-----------------:|
| **FlClashX** | macOS/iOS | supported | validate public port first |
| **v2rayN** | Windows | supported | validate public port first |
| **Nekoray** | Windows/Linux | supported | validate public port first |
| **v2rayNG** | Android | supported | validate public port first |
| **Shadowrocket** | iOS | supported | validate public port first |
| **Streisand** | iOS | supported | validate public port first |
| **Quantumult X** | iOS | supported | validate public port first |
| **Surge** | macOS/iOS | supported | validate public port first |

### Recommended Clients by Platform

- **macOS**: FlClashX (Free), Surge (Paid)
- **iOS**: Shadowrocket (Paid), Streisand (Free), FlClashX (Free)
- **Windows**: v2rayN (Free), Nekoray (Free)
- **Android**: v2rayNG (Free)
- **Linux**: Nekoray (Free)

## 🔧 Installation

### Prerequisites

- Clean VPS with Ubuntu 20.04+, Debian 11+, CentOS 8+, or AlmaLinux 8+
- Root access
- At least 512MB RAM
- 1GB free disk space

### Automated Installation

```bash
# Download and run installer
curl -fsSL https://raw.githubusercontent.com/x0tta6bl4/xray-vps/main/scripts/install-xray.sh | sudo bash

# Or clone and run locally
git clone https://github.com/x0tta6bl4/xray-vps.git
cd x0tta6bl4-xray-vps
sudo bash scripts/install-xray.sh
```

The installer will:
1. Install Xray Core v25.1.30
2. Generate Reality key pairs
3. Create optimized configuration
4. Configure firewall rules
5. Enable BBR congestion control
6. Generate client configurations
7. Start and validate the service

### Manual Installation

See [Setup Guide](docs/xray-setup-guide.md) for detailed manual installation instructions.

## ⚙️ Configuration

### Server Configuration

Server configuration is located at `/usr/local/etc/xray/config.json`.

Key configuration files:
- [Server Config Template](configs/server-config.json) - Base server configuration
- [Client distribution policy](clients/README_DISTRIBUTION_POLICY.md) - Current
  production profile rules
- [FlClashX Configs](clients/flclashx/) - Active macOS/iOS Reality profile
- [v2ray Configs](clients/v2ray/) - Active Windows/Linux Reality profile

### Environment Variables

The following placeholders need to be replaced in configuration files:

| Placeholder | Description | Example |
|-------------|-------------|---------|
| `REPLACE_SERVER_IP` | Your VPS public IP | `192.0.2.1` |
| `REPLACE_UUID_VLESS` | VLESS UUID | `550e8400-e29b-41d4-a716-446655440000` |
| `REPLACE_UUID_TROJAN` | Trojan UUID | `550e8400-e29b-41d4-a716-446655440001` |
| `REPLACE_PUBLIC_KEY` | Reality public key | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| `REPLACE_PRIVATE_KEY` | Reality private key | `XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` |
| `REPLACE_SHORT_ID` | Reality short ID | `0123456789abcdef` |
| `REPLACE_REALITY_SERVER_NAME` | First SNI value from the live Reality server config | `www.example.com` |
| `REPLACE_SS_PASSWORD` | Shadowsocks password | `base64-encoded-password` |
| `REPLACE_TROJAN_PASSWORD` | Trojan password | `password-string` |

### Client Configuration

After installation, client configurations are saved to `/root/xray-clients/`:

```
/root/xray-clients/
├── vless-reality.json      # VLESS + Reality config
├── vless-reality.qr.txt    # QR code for the default Reality profile
├── README_STATUS.txt       # Current distribution policy
├── disabled-*/             # Old or unverified client files, do not distribute
└── *.qr.txt                # QR codes for mobile clients
```

To regenerate production client profiles from the live Xray config without
restarting Xray:

```bash
sudo bash scripts/generate-live-client-profiles.sh --dry-run
sudo bash scripts/generate-live-client-profiles.sh
sudo bash scripts/validate-installation.sh
sudo bash scripts/check-client-distribution-gate.sh
```

The generator reads `/usr/local/etc/xray/config.json` and writes only
`vless-reality*.json` profiles. It does not generate fallback profiles.
The distribution gate fails if active client files contain fallback profiles,
HTML error pages, unsupported Reality fingerprints, malformed `shortId` values,
or Reality values that do not match the live server config.

## 🔍 Troubleshooting

### Validation Script

Run the validation script to check installation health:

```bash
sudo bash scripts/validate-installation.sh
```

This checks:
- Xray binary and version
- Service status
- Configuration validity
- Port listening status
- Certificate validity
- Log errors
- System resources

### Common Issues

#### Service Won't Start

```bash
# Check for configuration errors
sudo xray -test -config /usr/local/etc/xray/config.json

# View service logs
sudo journalctl -u xray -f

# Check error logs
sudo tail -f /var/log/xray/error.log
```

#### Connection Issues

```bash
# Check if ports are listening
sudo ss -tlnp | grep xray

# Test connectivity
curl -v telnet://YOUR_SERVER_IP:443

# Check firewall status
sudo ufw status
# or
sudo firewall-cmd --list-all
```

#### Reality Connection Fails

1. Verify the configured SNI domain is accessible:
   `SNI=$(sudo jq -r '([.inbounds[] | select(.streamSettings.security=="reality")][0].streamSettings.realitySettings.serverNames[0])' /usr/local/etc/xray/config.json); curl -I "https://${SNI}"`
2. Check Reality keys match between client and server
3. Ensure system time is synchronized: `timedatectl status`

### Log Analysis

```bash
# View access logs
sudo tail -f /var/log/xray/access.log

# View error logs
sudo tail -f /var/log/xray/error.log

# Search for specific errors
sudo grep "error" /var/log/xray/error.log | tail -20
```

## 🔒 Security

### Reality Protocol

The Reality protocol provides:
- **X25519 key exchange** for perfect forward secrecy
- **Short ID authentication** to prevent replay attacks
- **SNI spoofing** to masquerade as legitimate websites
- **TLS fingerprint randomization** to evade detection

### XTLS Vision

XTLS Vision provides:
- **Zero-copy forwarding** for maximum performance
- **Direct kernel bypass** to minimize overhead
- **Traffic obfuscation** that appears as regular TLS

### Best Practices

1. **Keep Xray updated**: Check for updates regularly
2. **Use strong UUIDs**: Generate cryptographically secure UUIDs
3. **Rotate keys periodically**: Update Reality keys monthly
4. **Monitor logs**: Watch for unusual connection patterns
5. **Use WARP for sensitive sites**: Route Google/Netflix through WARP
6. **Enable firewall**: Only expose necessary ports

## 📊 Performance Tuning

### System Optimizations Applied

- **BBR congestion control** for better throughput
- **Increased TCP buffers** for high-latency connections
- **Optimized file descriptors** for high connection counts
- **TCP fast open** for reduced latency

### Benchmarks

Expected performance on a 1Gbps VPS:

| Protocol | Speed | Latency | CPU Usage |
|----------|-------|---------|-----------|
| VLESS-XTLS-Reality-Vision | ~900 Mbps | ~10ms | Low |
| Trojan-XTLS-Reality | ~850 Mbps | ~12ms | Low |
| VLESS-splitHTTP | ~600 Mbps | ~20ms | Medium |
| Shadowsocks 2022 | ~700 Mbps | ~8ms | Low |

## 🔄 Deployment & Rollback

### Deployment Plan

See [Deployment Guide](docs/deployment-plan.md) for:
- Pre-deployment checklist
- Step-by-step deployment procedures
- Health check procedures
- Rollback procedures

### Backup and Restore

```bash
# Backup configuration
sudo bash scripts/backup-config.sh

# Restore from backup
sudo bash scripts/restore-config.sh /path/to/backup.tar.gz
```

## 📝 Protocol Details

### VLESS-XTLS-Reality-Vision (Primary)

- **Port**: 443
- **Security**: Reality + XTLS Vision
- **SNI**: use `serverNames[0]` from `/usr/local/etc/xray/config.json`
- **Flow**: xtls-rprx-vision
- **Best for**: Maximum speed and security

### Trojan-XTLS-Reality (Fallback #1)

- **Port**: 9443
- **Distribution status**: Do not issue until external reachability passes
- **Security**: Reality + TLS
- **SNI**: do not issue until externally validated
- **Best for**: High security environments

### VLESS-splitHTTP (Fallback #2)

- **Port**: 8443
- **Distribution status**: Do not issue until the public TLS endpoint matches local Xray
- **Transport**: SplitHTTP
- **Security**: TLS
- **Best for**: Packet fragmentation support

### Shadowsocks 2022 (Fallback #3)

- **Port**: 8388
- **Distribution status**: Do not issue until external reachability passes
- **Method**: 2022-blake3-aes-256-gcm
- **Best for**: Simple compatibility

### ShadowTLS (Fallback #4)

- **Port**: 8080
- **Distribution status**: Do not issue until external reachability passes
- **Security**: TLS
- **Best for**: Maximum stealth

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under the MIT License - see [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Xray Core](https://github.com/XTLS/Xray-core) - The underlying proxy platform
- [XTLS](https://github.com/XTLS) - Reality and XTLS protocols
- [Project V](https://www.v2ray.com/) - V2Ray project

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/x0tta6bl4/xray-vps/issues)
- **Discussions**: [GitHub Discussions](https://github.com/x0tta6bl4/xray-vps/discussions)
- **Documentation**: [Wiki](https://github.com/x0tta6bl4/xray-vps/wiki)

---

<p align="center">
  <strong>x0tta6bl4 Xray VPS</strong><br>
  Fast • Secure • Stealthy
</p>
