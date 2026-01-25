# Security Policy

The x0tta6bl4 project treats security as a first‑class, continuous discipline across identity, transport integrity, and execution boundaries.

---
## 🔐 Supported Versions
Only the latest minor release receives security fixes. Patch releases may be issued promptly for HIGH/CRITICAL vulnerabilities.

| Version | Status |
|---------|--------|
| 1.0.x   | ✅ Active |
| <1.0    | ❌ Unsupported (migrate to ≥1.0.0) |

---
## 📣 Reporting a Vulnerability
Please DO NOT open a public issue for suspected vulnerabilities.

1. Collect reproduction details (input, expected vs actual behavior, environment).  
2. Provide impact assessment (confidentiality / integrity / availability).  
3. Email: `security@x0tta6bl4.local` (placeholder — configure real alias).  
4. Encrypt if needed (PGP key: TODO ‑ to be published).  
5. Expect initial acknowledgement within **72h**, triage assignment within **5 business days**.

We follow a coordinated disclosure timeline unless:
- Active exploitation is confirmed
- Third‑party dependency disclosure window constrains timing

---
## 🧪 Security Testing
| Layer | Mechanism | Notes |
|-------|-----------|-------|
| Static | Bandit | CI weekly scheduled + PR gating (future) |
| Dependencies | Safety | Weekly scan + on‑demand for high‑risk merges |
| Auth / Identity | SPIFFE/SPIRE validation | Enforce SVID lifetime + audience |
| Transport | mTLS (TLS 1.3) | Short‑lived cert rotation policy (roadmap automation) |
| Input Fuzz | Hypothesis tests | Located in `tests/security/` |
| Performance Abuse | Rate / load tests | Guard rails for resource exhaustion |

---
## 🛡 Threat Model (High Level)
| Vector | Mitigation |
|--------|-----------|
| Identity spoofing | SPIFFE/SPIRE SVID validation + trust bundle pinning |
| Man‑in‑the‑middle | TLS 1.3 mutual auth + strict cipher policies |
| Replay attacks | Nonces / short‑lived credentials (roadmap) |
| Lateral movement | Least privilege identity scoping |
| Supply chain | Pinned major versions + weekly scan pipeline |
| Data poisoning (ML) | Input provenance tagging (roadmap) |
| Resource exhaustion | Quotas + adaptive backoff (planned) |

---
## 🔁 Vulnerability Response Process
1. Receive & acknowledge (≤72h)  
2. Reproduce & score severity (CVSS‑like)  
3. Assign mitigation owner  
4. Develop + test patch  
5. Issue private pre‑advisory (if coordinated)  
6. Release patched version (tag & CHANGELOG)  
7. Publish advisory summary  
8. Post‑mortem (if SEV ≥ HIGH)

---
## 📦 Dependency Hygiene
- Centralized management via `pyproject.toml`
- Periodic review cadence: weekly (automated scan), monthly (curated audit)
- Avoid unmaintained packages; replace or sandbox
- Cryptographic libs: use only vetted implementations

---
## 🔭 Roadmap (Security Enhancements)
| Milestone | Target |
|----------|--------|
| Short Term | Automated cert rotation operator |
| Short Term | Enforce failing closed on SPIFFE resolver timeout |
| Mid Term | Signed artifact attestations (SLSA‑inspired) |
| Mid Term | Runtime anomaly detection (eBPF‑based) |
| Mid Term | RAG input source validation + provenance graph |
| Long Term | Differential privacy for federated updates |
| Long Term | Hardware root of trust integration |

---
## 📝 Responsible Use
This software may facilitate distributed computation. Operators are responsible for ensuring deployments comply with local law and ethical data handling standards.

---
## 🤝 Contact
| Purpose | Channel |
|---------|---------|
| Vulnerability report | `security@x0tta6bl4.local` (placeholder) |
| General questions | Issues with `area:security` label |
| Private coordination | (PGP key – pending publication) |

---
**Thank you for helping keep the mesh trustworthy.**
