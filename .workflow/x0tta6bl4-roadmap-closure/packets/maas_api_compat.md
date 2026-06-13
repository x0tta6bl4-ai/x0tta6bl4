# Packet: maas_api_compat

## Objective

Verify the MaaS governance endpoint type cleanup without changing behavior.

## Context

The active roadmap includes MaaS API compatibility and route stability. This
packet is intentionally narrow: endpoint signatures and return annotations
only.

## Files

- `src/api/maas/endpoints/governance.py`

## Do

- Compile the touched endpoint and nearby MaaS compatibility modules.
- Run the package compatibility test.

## Do Not

- Change auth semantics.
- Change route order or route paths.
- Change database models or migrations.

## Verification

- `python3 -m py_compile src/api/maas/endpoints/governance.py src/api/maas_auth.py src/api/maas_legacy.py src/api/maas_compat.py src/api/maas_billing.py`
- `PYTHONPATH=. ./.venv/bin/pytest tests/unit/api/test_maas_package_compat_unit.py -q --no-cov`
