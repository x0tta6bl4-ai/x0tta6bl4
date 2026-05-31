# Green Baseline

This is the minimal reproducible baseline for a fresh `main` checkout. It is
not a full release certification; it is the first pass that should stay green
before feature work or larger refactors.

## Current Baseline

- Branch: `main`
- Root dependency security pins are guarded by
  `tests/unit/security/test_dependency_security_pins_unit.py`.
- The legacy manifest `другие проекты/базис-веб/requirements-neural.txt` is not
  present in the current tree. If a neural requirements manifest is restored,
  it must be added to the dependency security pin guard before merge.
- `paramiko` is not part of the runtime dependency baseline because the current
  tree has no runtime imports for it and GHSA-r374-rxx8-8654 has no patched
  release in Dependabot metadata.

## Local Checks

Run these from the repository root:

```bash
python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q -o addopts=''
python3 scripts/check_requirements_lock_sync.py
git diff --check
```

The dependency security test verifies that:

- core dependency manifests parse as Python requirements;
- `requirements.lock` carries the same direct pins as `requirements.txt`;
- root pinned packages stay at or above known Dependabot patched versions;
- staging and `pyproject.toml` floors match the security baseline;
- removed Dependabot manifests and unpatched unused dependencies stay absent
  unless they are intentionally reintroduced with security pins.

## GitHub Checks

The local baseline checks are enforced by the `Green Baseline` workflow in
`.github/workflows/green-baseline.yml`.

For PRs that touch dependencies or baseline documentation, wait for:

- `Green Baseline`
- `dependency-review`
- `Analyze (python)`
- `submit-pypi`
- `CodeQL` if it runs for the change set

## Known Remaining Security State

As of 2026-05-29, GitHub Dependabot state was cleaned as follows:

- Deleted neural manifest alerts were stale because the manifest is absent from
  `main`; they can be dismissed with evidence from the Git tree and GitHub
  Contents API.
- The low-severity `paramiko` alert has no patched version in Dependabot
  metadata. The package is removed from the runtime baseline instead of pinned
  to another vulnerable release.
