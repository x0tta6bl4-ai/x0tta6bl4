# x0tta6bl4 Xray VPS Deployment System

A comprehensive, production-ready Xray Core deployment system featuring Reality protocol, XTLS Vision, and multiple fallback protocols for maximum compatibility and stealth.

## 🌟 Features

- **VLESS-XTLS-Reality-Vision** - Primary protocol with maximum speed and security
- **Trojan-XTLS-Reality** - Fallback #1 with enhanced security
- **VLESS-splitHTTP** - Fallback #2 for packet fragmentation support
- **Shadowsocks 2022** - Fallback #3 for simple compatibility
- **ShadowTLS** - Fallback #4 for maximum stealth
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
│  │  Port 9443 │ Trojan-XTLS-Reality (Fallback #1)      │   │
│  │  Port 8443 │ VLESS-splitHTTP (Fallback #2)          │   │
│  │  Port 8388 │ Shadowsocks 2022 (Fallback #3)         │   │
│  │  Port 8080 │ ShadowTLS (Fallback #4)                │   │
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

| Client | Platform | VLESS-Reality | Trojan-Reality | VLESS-xHTTP | Shadowsocks | ShadowTLS |
|--------|----------|:-------------:|:--------------:|:-----------:|:-----------:|:---------:|
| **FlClashX** | macOS/iOS | ✅ | ✅ | ✅ | ✅ | ✅ |
| **v2rayN** | Windows | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Nekoray** | Windows/Linux | ✅ | ✅ | ✅ | ✅ | ❌ |
| **v2rayNG** | Android | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Shadowrocket** | iOS | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Streisand** | iOS | ✅ | ✅ | ❌ | ❌ | ✅ |
| **Quantumult X** | iOS | ✅ | ✅ | ✅ | ✅ | ❌ |
| **Surge** | macOS/iOS | ✅ | ✅ | ❌ | ✅ | ✅ |

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
- [FlClashX Configs](clients/flclashx/) - macOS/iOS client configurations
- [v2ray Configs](clients/v2ray/) - Windows/Linux client configurations

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
| `REPLACE_SS_PASSWORD` | Shadowsocks password | `base64-encoded-password` |
| `REPLACE_TROJAN_PASSWORD` | Trojan password | `password-string` |

### Client Configuration

After installation, client configurations are saved to `/root/xray-clients/`:

```
/root/xray-clients/
├── vless-reality.json      # VLESS + Reality config
├── vless-xhttp.json        # VLESS + xHTTP config
├── vmess-ws.json           # VMess + WebSocket config
├── trojan.json             # Trojan config
├── shadowsocks.txt         # Shadowsocks URL
└── *.qr.txt                # QR codes for mobile clients
```

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

1. Verify SNI domain is accessible: `curl -I https://www.microsoft.com`
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
- **SNI**: www.microsoft.com
- **Flow**: xtls-rprx-vision
- **Best for**: Maximum speed and security

### Trojan-XTLS-Reality (Fallback #1)

- **Port**: 9443
- **Security**: Reality + TLS
- **SNI**: www.microsoft.com
- **Best for**: High security environments

### VLESS-splitHTTP (Fallback #2)

- **Port**: 8443
- **Transport**: SplitHTTP
- **Security**: TLS
- **Best for**: Packet fragmentation support

### Shadowsocks 2022 (Fallback #3)

- **Port**: 8388
- **Method**: 2022-blake3-aes-256-gcm
- **Best for**: Simple compatibility

### ShadowTLS (Fallback #4)

- **Port**: 8080
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
