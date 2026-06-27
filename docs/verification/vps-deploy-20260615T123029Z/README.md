# VPS Deployment Artifact — 20260615T123029Z

## Status: ✅ DEPLOYED

### Deployment Details

- **Target:** 89.125.1.107
- **Version:** 3.4.0
- **Port:** 8000
- **Health Check:** HTTP 200 OK

### Health Response

```json
{
  "status": "ok",
  "version": "3.4.0",
  "full_version": "3.4.0",
  "channel": "stable",
  "timestamp": "2026-06-15T12:30:29Z"
}
```

### What Was Deployed

1. **src/** — Core application code
2. **scripts/ops/** — Operations scripts
3. **ebpf/prod/** — eBPF production tools
4. **edge/5g/** — 5G edge integration
5. **security/sbom/** — Security/SBOM tools

### Services Running

| Service | Port | Status |
|---------|------|--------|
| x0tta6bl4 app | 8000 | ✅ Running |
| Open5GS HTTP Bridge | 18080 | ✅ Running |
| Open5GS AMF | 9090 | ✅ Running |
| x402 Paid API | 8120 | ✅ Running |

### Firewall Rules Added

- Port 8000/tcp — ALLOW (x0tta6bl4 app)

### Verification

```bash
curl http://89.125.1.107:8000/health
```

### Artifacts

- This document: `docs/verification/vps-deploy-20260615T123029Z/README.md`
