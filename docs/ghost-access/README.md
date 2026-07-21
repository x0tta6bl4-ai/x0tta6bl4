# Ghost Access

Ghost Access is the VPN product/service layer of the x0tta6bl4 platform, built on Xray-core with a post-quantum cryptography (PQC) mesh overlay (ML-KEM + ML-DSA). It provides censorship-resistant, self-healing connectivity.

## Architecture

The system operates across several layers:
1. **x-ui panel**: Web interface for managing inbound connections and users.
2. **Xray-core**: Underlying proxy technology handling multiplexing, TLS, and routing.
3. **Ghost VPN Overlay**: The proprietary mesh VPN routing layer.
4. **PQC Mesh Network**: The self-healing underlying transport network secured by ML-KEM + ML-DSA.

## Components

- **Telegram Bot**: User-facing bot for automated provisioning and client configuration generation.
- **Client Configs**: Subscription links or individual profiles for end-user clients.
- **NL VPS Infrastructure**: Primary production environment (`89.125.1.107`).
- **SPB VPS Infrastructure**: Staging and secondary node (SSH alias: `sb`).

## Current Status

- **NL Environment**: Production
- **SPB Environment**: Staging

## Key Features

- **Automated Provisioning**: Quick onboarding via Telegram bot.
- **Multi-protocol Support**: 
  - VLESS + XTLS (Reality)
  - VMess + WebSocket (WS)
- **Self-Healing Mesh**: Automatically reroutes traffic if nodes become inaccessible.
- **Post-Quantum Cryptography**: Resistant to future quantum computing attacks.

## Related Documentation

- [Self-Test Checklist](./SELF_TEST_CHECKLIST.md)
- [VPN User Guide](../vpn/VPN_USER_GUIDE.md)
- [VPN Profile Health Runbook](../operations/vpn-profile-health-runbook.md)
