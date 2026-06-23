# Packet: security_identity_runtime

## Objective

Verify the PQC compatibility refactor and prevent regressions in legacy import
behavior.

## Context

The current roadmaps require namespace/import convergence and evidence-backed
PQC claims. Older `src.libx0t.security.post_quantum` imports must continue to
work as compatibility surfaces without keeping a duplicated legacy
implementation as the source of truth.

## Files

- `src/libx0t/security/post_quantum.py`
- `src/libx0t/security/pqc_core.py`
- `src/security/pqc/compat.py`
- `tests/unit/security/test_pqc_compat_unit.py`

## Do

- Keep compatibility exports stable.
- Keep new code pointed at `src.security.pqc`.
- Run compile and focused unit tests.

## Do Not

- Restore the old duplicated implementation as the canonical runtime path.
- Weaken fail-closed PQC availability behavior.
- Make production, SPIRE/PQ leaf, or ML-KEM TLS claims from local import tests.

## Verification

- `find src/security src/libx0t/security -name '*.py' -not -path '*/__pycache__/*' -print0 | xargs -0 python3 -m py_compile`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/security/test_pqc_compat_unit.py -q --no-cov`
