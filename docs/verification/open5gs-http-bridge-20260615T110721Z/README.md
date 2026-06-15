# Open5GS Remote Bridge Probe Artifact — 2026-06-15

Observed at: `2026-06-15T11:07:27Z`

## Status: PASS

### Probe Results

| Endpoint | Status | Response |
|----------|--------|----------|
| `GET /health` | HTTP 200 | `{"ok": true, "bridge": "open5gs-local-http"}` |
| `POST /bridge/sessions` | HTTP 200 | `{"accepted": true, "latency_ms": 25, "cause": ""}` |

### Health Response Details

```json
{
  "ok": true,
  "path": "/bridge/sessions",
  "amf_endpoint": "89.125.1.107:38412",
  "upf_endpoint": "89.125.1.107:8805",
  "bridge": "open5gs-local-http"
}
```

### Session Response Details

```json
{
  "accepted": true,
  "latency_ms": 25,
  "cause": ""
}
```

### What This Proves

1. **Remote bridge endpoint is reachable** — `http://89.125.1.107:18080` responds to HTTP requests
2. **Health endpoint works** — Bridge metadata shows AMF and UPF endpoints are configured
3. **Session creation works** — `POST /bridge/sessions` returns HTTP 200 with `{"accepted": true}`
4. **Low latency** — 25ms response time indicates responsive bridge handler
5. **Containerized VPS backend** — Bridge is backed by containerized Open5GS AMF/UPF

### What This Does NOT Prove

- **Production traffic delivery** — This is a single session creation, not sustained traffic
- **Mobile core validation** — AMF/UPF are containerized, not production-grade
- **End-to-end 5G session** — No actual UE attachment or data plane verification
- **DPI bypass** — No DPI-related testing in this probe
- **Field-validated deployment** — This is VPS-hosted, not field-deployed

### Evidence Chain

| Date | Evidence | Status |
|------|----------|--------|
| 2026-04-02 | Local HTTP bridge evidence | ✅ Local only |
| 2026-04-13 | Remote bridge success (first) | ✅ Containerized VPS |
| 2026-04-28 | Remote bridge probe | ✅ HTTP 200 |
| 2026-05-09 | Go test `TestLiveOpen5GSHTTPBridgeSession` | ✅ PASS (5.3s) |
| **2026-06-15** | **Fresh remote bridge probe** | **✅ HTTP 200, 25ms** |

### Blocker #4 Assessment

The release gate states:

> Open5GS validation is still split across environments, but the remote bridge path has now crossed its minimum success threshold.

The fresh probe confirms:
- ✅ Remote bridge endpoint is healthy
- ✅ Session creation succeeds with HTTP 200
- ✅ Response indicates acceptance (`"accepted": true`)
- ✅ Latency is reasonable (25ms)

**Conclusion:** Blocker #4 is closed for the minimum success threshold (remote bridge response).

**Remaining gaps** (not part of blocker #4):
- No production traffic proof
- No mobile core field validation
- No DPI bypass evidence
- No end-to-end 5G session verification

### Artifacts

- Bridge log: `docs/verification/open5gs-http-bridge-20260615T110721Z/bridge.log`
- JSON probe: `docs/verification/open5gs-http-bridge-20260615T110721Z/probe.json`
- Previous evidence: `docs/verification/open5gs-http-bridge-20260509T120055Z/bridge.log`
