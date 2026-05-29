# Green Baseline

This is the minimal reproducible baseline for a fresh `main` checkout. It is
not a full release certification; it is the first pass that should stay green
before feature work or larger refactors.

## Current Baseline

- Branch: `main`
- Baseline commit after dependency cleanup: `efad70e0743ecf6fd807828a65e20138fb4f5783`
- Root dependency security pins are guarded by
  `tests/unit/security/test_dependency_security_pins_unit.py`.
- The legacy manifest `другие проекты/базис-веб/requirements-neural.txt` is not
  present in the current tree. If a neural requirements manifest is restored,
  it must be added to the dependency security pin guard before merge.

## Local Checks

Run these from the repository root:

```bash
python3 -m pytest tests/unit/security/test_dependency_security_pins_unit.py -q -o addopts=''
git diff --check
```

The dependency security test verifies that:

- core dependency manifests parse as Python requirements;
- root pinned packages stay at or above known Dependabot patched versions;
- staging and `pyproject.toml` floors match the security baseline;
- removed Dependabot manifests stay absent unless they are intentionally
  reintroduced with security pins.

## GitHub Checks

For PRs that touch dependencies or baseline documentation, wait for:

- `dependency-review`
- `Analyze (python)`
- `submit-pypi`
- `CodeQL` if it runs for the change set

## Known Remaining Security State

As of 2026-05-29, GitHub Dependabot still reports:

- `requirements.txt`: one low-severity `paramiko` alert with no patched version
  in the Dependabot metadata.
- Deleted neural manifest alerts may remain visible until GitHub's dependency
  graph refreshes or the stale alerts are dismissed with evidence that the
  manifest is absent from `main`.

