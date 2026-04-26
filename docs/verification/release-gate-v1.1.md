# Release Gate — v1.1

Date: 2026-03-25
Decision basis:

- `bash scripts/verify-v1.1.sh --fast`
- `bash ebpf/prod/verify-local.sh --no-status`
- `bash scripts/agents/check_coordination_contract.sh`

Canonical companion status document:

- `docs/verification/v1.1-hardening-status.md`

---

## Decision

### Go / No-Go

- `NO-GO` for final defensible sign-off
- `GO` for controlled pre-pilot hardening and operator-driven live validation

This repository is already in a real execution/hardening phase, but not yet at
the point where all public-facing claims can be backed by environment-specific
artifacts.

---

## Verified Here

Current fast verification posture is environment-sensitive.
Use the latest `bash scripts/verify-v1.1.sh --fast` run and the newest
`verify_run` entry in `.agent-coord/log.jsonl` for current counts instead of
relying on copied snapshot totals in prose.

Canonical operating path for this branch:

- verification baseline: `bash scripts/verify-v1.1.sh --fast`
- cycle-end snapshot: `python3 scripts/ops/readiness_snapshot.py --refresh`
- operating model reference: `docs/verification/CANONICAL_OPERATING_MODEL.md`

The strongest currently verified local facts are:

- config/YAML parsing passes
- Helm lint passes in the current local environment
- CO-RE generation path is wired
- kernel and BTF prerequisites are present
- coordination docs are guarded against drift
- SOC2 evidence docs exist and pass sanity checks
- eBPF benchmark harness runs in plan-only mode without making throughput claims
- Docker-backed local validation paths are available in this environment
- the 5G adapter has a working local signaling validation path against real
  containerized Open5GS AMF/UPF endpoints
- the Open5GS HTTP bridge now has local real-http evidence backed by a fresh
  machine-readable artifact in `docs/verification/open5gs-http-bridge-20260402T104311Z/`
- SPIRE runtime can issue a standard X.509-SVID leaf and x0tta6bl4 can generate
  and verify a detached PQ attestation artifact bound to that issued leaf

---

## Blockers

These are the blockers preventing final sign-off:

1. Live XDP attach on a real NIC is not yet backed by a fresh, locally preserved artifact.
2. PPS benchmark `>= 5M` is not yet measured in a canonical benchmark artifact set.
3. Keyless cosign + Rekor evidence needs a current canonical CI-backed artifact chain, not only historical notes.
4. Open5GS validation is still split across environments, but the remote bridge path has now crossed its minimum success threshold.
   Fresh remote probe bundles in `docs/verification/open5gs-remote-probe-20260402T110306Z/` and `docs/verification/open5gs-remote-probe-20260402T112430Z/` show current candidates still failing.
   The newer SOCKS-backed probe narrows this to:
   `89.125.1.107:{18014,18080,18083,8010,3000} /bridge/sessions -> curl-exit-52 (Empty reply from server)`,
   `https://maas.01164.com/bridge/sessions -> curl-exit-35`,
   `http://maas.01164.com/bridge/sessions -> HTTP/1.1 409 Conflict`.
   An additional probe from 2026-04-12 in `docs/verification/open5gs-remote-probe-20260412T200635Z/` shows that `http://89.125.1.107:18080`
   is now reachable, but it identifies itself as `open5gs-http-bridge-stub`, returns a `stub-*` session id, accepts obviously invalid payloads,
   and still fails to complete the HTTP exchange cleanly. Treat this as stub reachability, not production-like bridge proof.
   A further probe from 2026-04-13 in `docs/verification/open5gs-remote-probe-20260413T072848Z/` shows the stub has been replaced with the real bridge handler:
   `GET /health` now returns bridge metadata and external `POST /bridge/sessions` fails closed with `HTTP/1.0 502 Bad Gateway`,
   including a machine-readable body that points to the current blocker: `SCTP transport failure to AMF (127.0.0.1:38412): connection refused`.
   This improves the remote bridge posture from fake-success to honest transport failure, but it still does not satisfy the requirement for a successful non-local session response.
   A later probe from 2026-04-13 in `docs/verification/open5gs-remote-probe-20260413T074948Z/` then shows the remote bridge path succeeding with
   `HTTP/1.0 200 OK` and `{"accepted": true, "latency_ms": 25, "cause": ""}` after wiring the VPS bridge to containerized Open5GS AMF/UPF.
   A follow-up verification in `docs/verification/open5gs-remote-probe-20260413T081650Z/` shows that after switching those containers to `restart=always`,
   the path remains healthy even after `systemctl restart docker` on the VPS.
   This closes the minimum remote bridge-response requirement, while still falling short of any production-traffic or full mobile-core claim.
   A later probe from 2026-04-13 in `docs/verification/open5gs-remote-probe-20260413T074948Z/` closes that specific gap:
   the remote endpoint now returns a successful non-local machine-readable bridge response
   `{"accepted": true, "latency_ms": 25, "cause": ""}` from `http://89.125.1.107:18080/bridge/sessions`.
   Treat this as remote bridge-path success evidence with a containerized VPS backend, not as evidence of production traffic or a broader field-validated Open5GS deployment.
5. Live SX1303 HAL binding is not yet evidenced.
6. Real DP backend validation is not yet evidenced.
7. Playwright E2E and k6 still require a full production-like running stack and fresh artifacts.
8. SPIRE PQ posture is currently evidenced as `standard leaf SVID + detached PQ attestation artifact`; this does not justify claims about PQ OIDs inside the leaf or ML-KEM inside the SPIRE/TLS handshake.

---

## Required Evidence Before Sign-Off

### Required for final eBPF datapath claims

- `sudo -E IFACE=<real-nic> ebpf/prod/verify-local.sh --live-attach`
- clean output with no verifier/kernel rejection
- operator-preserved command log

### Required for throughput claims

- `RUN_BENCH=1 sudo -E IFACE=<real-nic> ebpf/prod/benchmark-harness.sh`
- `ebpf/prod/results/benchmark-<timestamp>.json`
- JSON contains `"pass": true`

### Required for supply-chain attestation claims

- CI keyless run for `security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native`
- Rekor log entry or equivalent CI evidence

### Required for chart/runtime claims

- containerized chart render through `charts/render-in-docker.sh`
- cluster-level enforcement checks for multi-tenant isolation

### Required for 5G / LoRa / DP claims

- real Open5GS transport evidence
- if the claim is about the HTTP bridge, require an HTTP bridge session log or equivalent machine-readable bridge artifact; local SCTP/PFCP signaling validation alone is not sufficient
- canonical bridge path: `OPEN5GS_HTTP_BASE_URL=http://<bridge-host>:<port> OPEN5GS_UE_ID=<ue-id> OPEN5GS_SLICE_ID=<slice-id> bash scripts/ops/run_open5gs_http_bridge_validation.sh`
- real SX1303 HAL evidence
- real DP backend evidence

### Required for stronger SPIRE / PQC identity claims

- `make spire-pq-attestation-validation`
- preserved JSON/Markdown report artifacts in `docs/verification/`
- if the claim is about PQ OIDs inside the leaf SVID itself, require a separate artifact-backed proof path; detached PQ attestation alone is not sufficient

---

## Public Claim Restrictions

Do not publicly state the following as verified facts yet:

- measured PPS throughput
- `98.5% uptime`
- `1.8s MTTR`
- `94%` GNN accuracy as production validation
- Rekor-attested verification
- production-deployed live Open5GS / SX1303 / DP backend
- PQ OIDs embedded in the SPIRE leaf SVID
- ML-KEM-enabled SPIRE mTLS handshake

These remain simulated, blocked, or dependent on separate evidence.

---

## Operator Next Steps

Recommended order:

0. `python3 scripts/ops/readiness_snapshot.py --refresh`
1. `sudo -E IFACE=eth0 ebpf/prod/verify-local.sh --live-attach`
2. `RUN_BENCH=1 sudo -E IFACE=eth0 ebpf/prod/benchmark-harness.sh`
3. CI keyless signing / Rekor path with current release-bound artifacts
4. canonical Open5GS validation:
   - local signaling validation may be used for adapter transport proof
   - HTTP bridge claims still require bridge-specific evidence
   - use `bash scripts/ops/run_open5gs_http_bridge_validation.sh` for real bridge evidence collection
   - use `bash scripts/ops/probe_open5gs_remote_bridge.sh` to refresh remote candidate evidence before attempting another VPS/edge proof cycle
   - remote target access must be reproducible, not prose-only
5. canonical SPIRE PQ identity validation:
   - detached PQ attestation path may be used for workload identity proof
   - do not promote this to PQ leaf-SVID or PQ TLS-handshake claims
6. live SX1303 / DP validation

Until those artifacts exist, this branch should be described as:

`evidence-driven hardening branch with verified local preflight paths and pending live validation`
