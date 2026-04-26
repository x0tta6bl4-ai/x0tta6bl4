# x0tta6bl4

Experimental monorepo for mesh networking, post-quantum transport, eBPF dataplane work, identity experiments, and operational tooling.

This public branch is a **curated research surface**, not a promise of production readiness, uptime, or benchmark guarantees.

## What this repo is

- A working monorepo with real code, scripts, and verification notes.
- A place for transport, security, and resilience experiments.
- A public snapshot of selected work around:
  - post-quantum cryptography
  - eBPF/XDP and dataplane tooling
  - SPIFFE/SPIRE identity
  - verification and operator runbooks

## What this repo is not

- Not a turnkey production deployment.
- Not a contractual SLA surface.
- Not a claim that every directory here is equally mature.

## Good places to start

- `src/security/pqc/` — post-quantum and hybrid TLS work
- `src/network/ebpf/` — eBPF/XDP experiments and loaders
- `edge/5g/` — 5G transport and adapter work
- `docs/verification/` — evidence, validation notes, and reality checks
- `docs/operations/` — operator-facing runbooks

## Related public repos

- `x0tta6bl4-ai/x0tta6bl4-ai` — profile README and public entry point
- `x0tta6bl4-ai/x0tta6bl4-mesh-mvp` — smaller mesh-focused MVP surface

## Public branch policy

This repository has grown organically and contains both stronger and weaker areas.
To keep the public surface honest:

- heavy or environment-specific workflows are manual-first
- stale live-deployment automation is removed from the public branch when it stops reflecting a real maintained environment
- public documentation should prefer verified facts over aspirational claims
- experimental folders may exist without being presented as product-ready
- customer scratchpads and local debug files are intentionally kept out of public `main`

## Minimal local setup

```bash
git clone https://github.com/x0tta6bl4-ai/x0tta6bl4.git
cd x0tta6bl4
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## License

Apache-2.0. See [LICENSE](LICENSE).
