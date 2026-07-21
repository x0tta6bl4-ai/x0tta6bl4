# Validation Framework — Versioning Policy

## Version Format

`v{MAJOR}.{MINOR}.{PATCH}`

## Change Types

### Patch (v1.0.x)

- Bug fixes without behavior change
- Documentation improvements
- Test updates for existing checks
- Typo fixes in specs

**Does NOT require:** re-validation of past results.

### Minor (v1.1)

- New invariant checks
- New failure types (F11+)
- New test suites (V8+)
- Additional SLA rules
- Backward-compatible artifact format changes

**Requires:** new validation run to verify new checks pass.

### Major (v2.0)

- Changed SLA thresholds
- Changed PASS/FAIL criteria
- Changed artifact JSON schema
- Changed invariant definitions
- Changed failure taxonomy structure

**Requires:** full re-validation, baseline reset,历史 results marked as v1.x.

## Rules

1. **Specification changes** (`BENCHMARK_SPEC.md`) MUST be accompanied by test and documentation updates.
2. **Validation logic changes** SHOULD be accompanied by a new milestone.
3. **Past results** are immutable — they reflect the spec version at time of generation.
4. **Comparisons** across major versions require explicit mapping (v1.x → v2.0 baseline adjustment).
