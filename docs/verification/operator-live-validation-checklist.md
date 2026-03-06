# Operator Live-Validation Checklist — v1.1

**Purpose:** Step-by-step runbook for an operator completing the gap between
"well-verified branch" and "live-cluster production release gate".
Complete every section in order. Do not mark a section PASS until the
artifact or output described is actually produced.

**Evidence principle:** If the output file or log line is not present,
the check did not happen. No exceptions.

---

## Pre-conditions

Before running this checklist, confirm the following pass in your environment:

```bash
./scripts/verify-v1.1.sh
```

All VERIFIED HERE checks must show `PASS`. Fix any `FAIL` before proceeding.

---

## Section A — Containerized Helm Render

**What this proves:** Helm templates are syntactically valid and produce
the expected Kubernetes resource kinds for all charts. Does NOT prove
cluster admission, admission webhooks, or runtime behaviour.

**Prerequisites:** Docker daemon reachable

**Command:**
```bash
charts/render-in-docker.sh
```

**Expected output files:**
```
charts/out/api-gateway/rendered.yaml
charts/out/api-gateway/resources.txt
charts/out/x0tta6bl4-commercial/rendered.yaml
charts/out/x0tta6bl4-commercial/resources.txt
charts/out/observability/rendered.yaml
charts/out/observability/resources.txt
charts/out/multi-tenant/rendered.yaml
charts/out/multi-tenant/resources.txt
charts/out/render-summary.txt
```

**Pass criterion:** `charts/out/render-summary.txt` contains only `PASS` lines.
The final printed line must be `Passed: 4 | Failed: 0`.

**Does NOT prove:** cluster admission, NetworkPolicy enforcement, RBAC enforcement.

- [ ] Command executed
- [ ] All 4 charts PASS
- [ ] `charts/out/render-summary.txt` preserved as evidence artifact

---

## Section B — SBOM Generation and CVE Gate

**What this proves:** Software Bill of Materials was generated for the Go agent
module and the full repository. Grype found no HIGH/CRITICAL or CVSS >= 7.0
vulnerabilities in those SBOMs at time of scan.

**Does NOT prove:** Container image CVE posture (scan the built image separately).
Does NOT prove Rekor transparency-log inclusion (see Section C).

**Prerequisites:** Docker daemon reachable

**Command:**
```bash
security/sbom/run-local-sbom-check.sh full --tool-mode docker
```

If the Docker-backed Grype scanner stalls, rerun with an explicit timeout:

```bash
SBOM_GRYPE_TIMEOUT_SEC=60 security/sbom/run-local-sbom-check.sh gate --tool-mode docker
```

**Expected output files:**
```
security/sbom/out/agent.cdx.json       (Go module SBOM — if agent/ exists)
security/sbom/out/repo.cdx.json        (repository CycloneDX SBOM)
security/sbom/out/repo.spdx.json       (repository SPDX SBOM)
security/sbom/out/agent.cdx.json.grype.json
security/sbom/out/repo.cdx.json.grype.json
security/sbom/out/repo.spdx.json.grype.json
```

**Pass criterion:** Final output line: `SBOM full completed using docker mode`
All `.grype.json` files exist. Grype exit 0 (no HIGH/CRITICAL/CVSS>=7 matches).

**Fail-fast criterion:** If Grype cannot complete, the script should exit non-zero
with a timeout/failure message instead of hanging indefinitely. A timeout is not
a passing gate.

**Record:** Save the grype JSON files. Note the scan timestamp.

- [ ] Command executed
- [ ] All SBOM artifacts present
- [ ] Grype reports show 0 blocking findings
- [ ] Scan date recorded: _______________

---

## Section C — Local Mock Signing (Developer Rehearsal)

**What this proves:** cosign can sign the SBOM blobs using a locally generated
ephemeral key pair, and can verify those signatures. Key pair and status file
are written to `security/sbom/out/`.

**What this DOES NOT prove:** Rekor transparency-log inclusion, keyless OIDC
signing, supply-chain attestation visible to third parties.

**Prerequisites:** SBOM artifacts from Section B must exist. Docker or native cosign.

**Command:**
```bash
security/sbom/verify-cosign-rekor.sh --mode mock --tool-mode docker
```

**Expected output files:**
```
security/sbom/out/mock-cosign.key
security/sbom/out/mock-cosign.pub
security/sbom/out/agent.cdx.json.sig     (if agent SBOM exists)
security/sbom/out/repo.cdx.json.sig
security/sbom/out/repo.spdx.json.sig
security/sbom/out/mock-signing-status.txt
```

**Pass criterion:** Final output line: `cosign signing completed: MOCK mode (local key only — Rekor NOT involved)`
The file `mock-signing-status.txt` must contain `rekor=skipped`.

- [ ] Command executed
- [ ] All `.sig` files present
- [ ] `mock-signing-status.txt` contains `rekor=skipped`
- [ ] Understood: this does NOT claim Rekor inclusion

---

## Section D — CI-Keyless Signing + Rekor Upload

**What this proves:** The SBOM artifacts were signed keylessly using a real OIDC
identity token and the signatures were uploaded to the Rekor public transparency log.
This is the only path that produces a valid supply-chain attestation.

**Prerequisites:**
- Must run in a CI environment with OIDC support (GitLab CI, GitHub Actions)
- `SIGSTORE_ID_TOKEN` must be set
- Native `cosign` and `rekor-cli` installed in the CI runner

**Command (CI only):**
```bash
security/sbom/verify-cosign-rekor.sh --mode ci-keyless --tool-mode native
```

**Expected outputs:**
```
security/sbom/out/agent.cdx.json.sig
security/sbom/out/agent.cdx.json.crt
security/sbom/out/repo.cdx.json.sig
security/sbom/out/repo.cdx.json.crt
security/sbom/out/repo.spdx.json.sig
security/sbom/out/repo.spdx.json.crt
```

**Pass criterion:** `rekor-cli get` returns a valid log entry for each artifact.
Rekor entry URLs logged to CI stdout.

**Blocked in local environment:** No local OIDC token available.

- [ ] CI job defined in `.gitlab-ci.yml` (job: `release:cosign-attest`)
- [ ] CI job ran successfully on a tagged release
- [ ] Rekor entry URLs preserved as CI artifacts
- [ ] Rekor log index recorded: _______________

---

## Section E — eBPF Verification (Plan + Build)

**What this proves:** The eBPF verification harness is wired correctly for the
current kernel and BTF setup, and the plan-only benchmark path is runnable.
In this local environment, source rebuild may be skipped if the local Go
toolchain is older than the `ebpf/prod` module requirement.

**Command:**
```bash
ebpf/prod/benchmark-harness.sh
```

**Expected output:**
- `PASS  kernel ... >= 6.1`
- `PASS  BTF present at /sys/kernel/btf/vmlinux`
- either:
  - `PASS  module-aware go build ./ebpf/prod → exit 0`
  - or `SKIP  local Go toolchain cannot rebuild ebpf/prod source here...`
- `PASS  CO-RE make -n shows bpf2go in plan`
- `PLAN-ONLY  no traffic generated; no throughput claimed`

**Additional reproducible path:** if local source rebuild is blocked by toolchain,
use:

```bash
ebpf/prod/build-in-docker.sh
```

**Does NOT prove:** XDP attachment to a real NIC, actual packet forwarding,
or any throughput figure.

- [ ] Command executed
- [ ] All PASS lines present
- [ ] PLAN-ONLY line confirmed

---

## Section F — Live XDP Attach (Requires Root + Real NIC)

**What this proves:** The XDP program loads and attaches to a real network
interface without kernel errors. Does NOT prove any throughput figure.

**Prerequisites:**
- Root access (`sudo`)
- Physical or virtual NIC (not a loopback)
- `IFACE` set to the correct interface name

**Command:**
```bash
sudo -E IFACE=eth0 ebpf/prod/verify-local.sh --iface eth0 --live-attach
```

**Pass criterion:** Output contains `local eBPF verification completed` with
no kernel error messages. Check `dmesg` for any BPF verifier rejections.

**Blocked in most environments:** Requires root + real NIC. Do not substitute
a loopback interface — XDP does not attach to loopback.

- [ ] Environment prepared (root + NIC confirmed)
- [ ] Command executed
- [ ] `local eBPF verification completed` in output
- [ ] `dmesg` checked for BPF errors: none found
- [ ] Interface name used: _______________
- [ ] Kernel version confirmed: _______________

---

## Section G — PPS Benchmark (Requires Root + pktgen)

**What this proves:** The XDP program forwarded traffic at a measured rate
under synthetic load from Linux pktgen. The measured PPS was recorded in a
timestamped JSON file.

**IMPORTANT:** This is the ONLY section that produces a valid throughput figure.
Do not cite `>5M pps` or any PPS number unless this section completed and
the result JSON shows `"pass": true`.

**Prerequisites:**
- Section F must complete first (XDP attached)
- Root access
- `modprobe pktgen` succeeds
- `IFACE` set to the same interface

**Command:**
```bash
modprobe pktgen
RUN_BENCH=1 sudo -E IFACE=eth0 DURATION=30 ebpf/prod/benchmark-harness.sh
```

**Expected output file:**
```
ebpf/prod/results/benchmark-<timestamp>.json
```

**Pass criterion:** JSON file exists, `"pass": true`, `"measured_pps"` >= `"target_pps"`.

- [ ] pktgen loaded
- [ ] Command executed for full DURATION
- [ ] `ebpf/prod/results/benchmark-<timestamp>.json` exists
- [ ] `"pass": true` in JSON
- [ ] `measured_pps` value recorded: _______________
- [ ] JSON file preserved as release evidence artifact

---

## Section H — Multi-Tenant Cluster Isolation (Requires Kubernetes Cluster)

**What this proves:** Tenant namespaces exist, NetworkPolicies are enforced by the
CNI plugin, and ResourceQuotas are active. Helm render proves template syntax only.

**Prerequisites:**
- `kubectl` access to a Kubernetes cluster with a NetworkPolicy-capable CNI
  (Cilium, Calico, or Flannel with NetworkPolicy support)
- Chart deployed via `helm upgrade --install`

**Commands:**
```bash
# Deploy with enterprise values
helm upgrade --install x0tta-mesh charts/x0tta6bl4-commercial \
  -f charts/x0tta6bl4-commercial/values-enterprise.yaml

# Verify isolation resources exist in cluster
kubectl get networkpolicy -A | grep tenant-isolation
kubectl get resourcequota -A | grep -quota
kubectl get namespace -l x0tta.io/tenant
```

**Pass criterion:** NetworkPolicy `tenant-isolation` present in each tenant namespace.
ResourceQuota present and showing usage. Cross-tenant ping test fails (expected).

- [ ] Chart deployed to cluster
- [ ] NetworkPolicies confirmed present per tenant namespace
- [ ] ResourceQuotas confirmed present
- [ ] Cross-tenant connectivity test confirms isolation
- [ ] Cluster name / environment recorded: _______________

---

## Final Gate — What Must Be True Before Claiming "Production-Ready"

| # | Check | Status |
|---|-------|--------|
| A | Helm render passes for all 4 charts | [ ] |
| B | SBOM generated, CVE gate passes | [ ] |
| C | Mock signing rehearsed | [ ] |
| D | Rekor transparency-log entry exists (CI run) | [ ] |
| E | eBPF plan+build verified | [ ] |
| F | XDP live-attach confirmed on target NIC | [ ] |
| G | PPS benchmark result JSON with `"pass": true` | [ ] |
| H | Multi-tenant isolation confirmed in cluster | [ ] |

**Current state of this branch:** Sections A–E are evidence-driven and
script-backed, but some local paths are still environment-blocked here
(Docker, root, real NIC, real cluster).
Sections F–H still require hardware/cluster access.

Do not declare production readiness until all 8 rows are checked.
