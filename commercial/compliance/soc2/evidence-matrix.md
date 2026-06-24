# SOC2 Evidence Matrix

Last updated: 2026-03-08 (v1.1 GA hardening pass)

Every control maps to: command, artifact path, owner, and evidence state.

Evidence states:
- **VERIFIED HERE** — executed in this environment; output confirmed
- **VERIFIED VIA SCRIPT/CI** — script exists and is reproducible; not run here
- **NOT VERIFIED YET** — blocked by hardware, credentials, or environment

| Control | Artifact | Command | Owner | Evidence state |
|---------|----------|---------|-------|----------------|
| YAML syntax: .gitlab-ci.yml | `.gitlab-ci.yml` | `python3 -c 'import yaml; yaml.safe_load(open(".gitlab-ci.yml")); print("ok")'` | DevSecOps | VERIFIED HERE |
| YAML syntax: gitlab-ci-sbom.yml | `security/sbom/gitlab-ci-sbom.yml` | `python3 -c 'import yaml; yaml.safe_load(open("security/sbom/gitlab-ci-sbom.yml")); print("ok")'` | DevSecOps | VERIFIED HERE |
| YAML syntax: multi-tenant values | `charts/multi-tenant/values-enterprise.yaml` | `python3 -c 'import yaml; yaml.safe_load(open("charts/multi-tenant/values-enterprise.yaml")); print("ok")'` | Platform Engineering | VERIFIED HERE |
| YAML syntax: commercial values | `charts/x0tta6bl4-commercial/values-enterprise.yaml` | `python3 -c 'import yaml; yaml.safe_load(open("charts/x0tta6bl4-commercial/values-enterprise.yaml")); print("ok")'` | Platform Engineering | VERIFIED HERE |
| CO-RE eBPF loader build | `ebpf/prod/loader.go` | `GO111MODULE=off go build ./ebpf/prod` | Platform Engineering | VERIFIED HERE |
| CO-RE object generation path wired | `ebpf/prod/Makefile.bpf` | `make -n -f ebpf/prod/Makefile.bpf generate 2>&1 \| grep bpf2go` | Platform Engineering | VERIFIED HERE |
| Kernel >= 6.1 | `/proc/version` | `uname -r` (actual: 6.14.0-37-generic) | Platform Engineering | VERIFIED HERE |
| BTF present | `/sys/kernel/btf/vmlinux` | `test -f /sys/kernel/btf/vmlinux` | Platform Engineering | VERIFIED HERE |
| Python unit tests — 63 pass | `tests/unit/`, `tests/benchmarks/` | `python3 -m pytest tests/unit/dao/test_governance.py tests/unit/scripts/test_validate_enterprise_workflows_unit.py tests/unit/mesh/test_telemetry_collector_unit.py tests/benchmarks/test_api_memory_profile.py --no-cov -q` | Engineering | VERIFIED HERE |
| Helm lint — api-gateway | `charts/api-gateway/` | `helm lint charts/api-gateway --quiet` | Platform Engineering | VERIFIED HERE |
| Helm lint — observability | `charts/observability/` | `helm lint charts/observability --quiet` | Platform Engineering | VERIFIED HERE |
| Helm lint — x0tta6bl4-commercial | `charts/x0tta6bl4-commercial/` | `helm lint charts/x0tta6bl4-commercial --quiet` | Platform Engineering | VERIFIED HERE |
| SOC2 incident procedure (SEV-1 defined) | `compliance/soc2/playbook.md` | `grep -q "SEV-1" compliance/soc2/playbook.md` | Compliance | VERIFIED HERE |
| Evidence matrix exists | `compliance/soc2/evidence-matrix.md` | `test -f compliance/soc2/evidence-matrix.md` | Compliance | VERIFIED HERE |
| Alembic offline SQL generation | `alembic/versions/` (17 migrations) | `python3 -m alembic upgrade head --sql` → EXIT 0, 17/17 migrations 2026-03-06 | Engineering | VERIFIED HERE |
| Helm lint — multi-tenant | `charts/multi-tenant/` | `helm lint charts/multi-tenant --quiet` → 0 failures (added missing values.yaml) 2026-03-06 | Platform Engineering | VERIFIED HERE |
| Helm lint — all 5 charts | `charts/` (5 charts) | `helm lint` each → 5/5 OK 2026-03-06 | Platform Engineering | VERIFIED HERE |
| verify-v1.1.sh --fast | `scripts/verify-v1.1.sh` | 17 PASS, 0 FAIL (fixed: coordination drift + multi-tenant values.yaml) 2026-03-06 | Platform Engineering | VERIFIED HERE |
| Verification entrypoint — 17 checks pass | `scripts/verify-v1.1.sh` | `bash scripts/verify-v1.1.sh --fast` → 17 PASS, 0 FAIL | Platform Engineering | VERIFIED HERE |
| Containerized Helm render script | `charts/render-in-docker.sh` | `test -x charts/render-in-docker.sh` | Platform Engineering | VERIFIED HERE |
| eBPF benchmark harness (plan-only) | `ebpf/prod/benchmark-harness.sh` | `bash ebpf/prod/benchmark-harness.sh` (no RUN_BENCH) | Platform Engineering | VERIFIED HERE |
| Operator live-validation checklist | `docs/verification/operator-live-validation-checklist.md` | `test -f docs/verification/operator-live-validation-checklist.md` | Platform Engineering | VERIFIED HERE |
| SBOM agent/ directory guard | `security/sbom/run-local-sbom-check.sh` | WARNING emitted gracefully when agent/ missing | DevSecOps | VERIFIED HERE |
| Cosign mock-mode output is unambiguous | `security/sbom/verify-cosign-rekor.sh` | `mock-signing-status.txt` contains `rekor=skipped` + `does_not_prove` field | DevSecOps | VERIFIED VIA SCRIPT/CI |
| Docker daemon reachable | (system) | `docker info` (actual: Docker 29.2.1) | DevSecOps | VERIFIED HERE |
| SBOM generation (Go + repo) | `security/sbom/run-local-sbom-check.sh` | `run-local-sbom-check.sh generate --tool-mode docker` → agent.cdx.json 5.5K + repo.cdx.json 583K + repo.spdx.json 973K 2026-03-06 | DevSecOps | VERIFIED HERE |
| CVE gate HIGH/CRITICAL/CVSS>=7.0 | `security/sbom/run-local-sbom-check.sh` | `run-local-sbom-check.sh gate --tool-mode docker` → gate functional; 6 HIGH/CRITICAL CVEs found; dep upgrades required 2026-03-06 | DevSecOps | VERIFIED HERE |
| Local mock cosign signing | `security/sbom/verify-cosign-rekor.sh` | `verify-cosign-rekor.sh --mode mock --tool-mode docker` → 3 blobs signed+verified locally; tlog-upload=false confirmed 2026-03-06 | DevSecOps | VERIFIED HERE |
| Containerized Helm render (all charts) | `charts/render-in-docker.sh` | `charts/render-in-docker.sh` → 4/4 PASS 2026-03-06; fix: added ClusterRoleBinding to x0tta6bl4-commercial | Platform Engineering | VERIFIED HERE |
| Local eBPF verification harness | `ebpf/prod/verify-local.sh` | `ebpf/prod/verify-local.sh --iface eth0` | Platform Engineering | VERIFIED VIA SCRIPT/CI |
| Keyless cosign + Rekor upload | `docs/release/provenance/*.crt` | GitHub Actions CI run `22822503867` on `release/rc1` (2026-03-08); OIDC issuer `token.actions.githubusercontent.com`; 7 certs committed to `docs/release/provenance/` | Release Engineering | VERIFIED VIA SCRIPT/CI |
| Live XDP attach (real NIC) | `ebpf/prod/results/benchmark-live.json` | Verified XDP prog `id 613` attached to `enp8s0`; `bpftool prog show` confirmed; 142k TX PPS baseline on 2026-03-07 | Platform Engineering | VERIFIED HERE |
| Live Open5GS UPF session (5G data plane) | VPS `89.125.1.107` | `nr-binder 10.45.0.4 ping -c4 8.8.8.8` → 4/4, RTT ~0.8 ms; `curl --interface uesimtun0 ifconfig.me` → `89.125.1.107` on 2026-03-08 | Platform Engineering | VERIFIED HERE |
| PPS benchmark >= 5M (live, with pktgen) | `ebpf/prod/benchmark-harness.sh` | `RUN_BENCH=1 sudo -E IFACE=eth0 ebpf/prod/benchmark-harness.sh` | Platform Engineering | NOT VERIFIED YET |
| Multi-tenant namespace isolation (live cluster) | `charts/x0tta6bl4-commercial/`, `charts/multi-tenant/` | `kubectl get networkpolicy,resourcequota -A` | Platform Engineering | NOT VERIFIED YET |
| Blue-green deploy slot switch | `release/v1.0.0.sh` | `release/v1.0.0.sh` (requires cluster) | Release Engineering | NOT VERIFIED YET |
| Chaos gate (Litmus) | `.gitlab-ci.yml` `release:chaos-gate` | GitLab CI only | Platform Engineering | NOT VERIFIED YET |

---

## Notes

**PPS throughput figures**: The `>5M pps` target is a design target. It is
only valid evidence when `RUN_BENCH=1 ebpf/prod/benchmark-harness.sh` completes
and writes `ebpf/prod/results/benchmark-<timestamp>.json` with `"pass": true`.
Do not cite PPS numbers from plan-only runs.

**Uptime and MTTR**: 98.5% uptime and 1.8s MTTR are SLA targets derived from
simulated self-healing runs, not measured from production traffic. They must not
be presented as independently verified production metrics.

**GNN accuracy**: The 94% figure is a training-set accuracy result.
Production anomaly detection accuracy has not been measured from live traffic.
