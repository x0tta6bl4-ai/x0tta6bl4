# Security Policy

## Supported Versions

| Version | Supported |
|:--------|:----------|
| 3.6.x | ✅ Yes |
| 3.5.x | ✅ Yes |
| < 3.5 | ❌ No |

## Reporting a Vulnerability

If you discover a security vulnerability, please report it responsibly:

1. **Do NOT open a public issue**
2. Email: security@x0tta6bl4.dev (or open a private GitHub security advisory)
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

## Response Timeline

| Action | Timeline |
|:-------|:---------|
| Acknowledge report | 48 hours |
| Initial assessment | 1 week |
| Fix or mitigation | 2-4 weeks |
| Public disclosure | After fix is released |

## Scope

In-scope:
- PQC (ML-KEM-768, ML-DSA-65) implementation flaws
- SPIRE/SPIFFE authentication bypass
- MAPE-K self-healing manipulation
- eBPF/XDP kernel-level vulnerabilities
- VPN protocol weaknesses (VLESS, Reality, XHTTP)
- API authentication/authorization bypass
- Injection attacks (SQL, command, etc.)

Out-of-scope:
- Denial of service (DoS)
- Social engineering
- Physical attacks
- Issues in third-party dependencies (report upstream)

## Bug Bounty

This is an independent engineering research project with zero budget. We cannot offer monetary rewards, but we will:

- Credit you in release notes
- Add you to the SECURITY.md acknowledgments
- Provide a reference letter if needed

## Security Best Practices

For deployment security, see:
- [`docs/security/`](docs/security/) — Security hardening guides
- [`src/security/`](src/security/) — Security implementation
- [`tests/security/`](tests/security/) — Security test suite
