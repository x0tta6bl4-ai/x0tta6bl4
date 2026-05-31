# Current Active Goal Gap Audit

Status: working companion for `CURRENT_CROSS_PLANE_EVIDENCE_MAP.json`.

This document is a current gate companion, not a production-completion claim.
It records which gaps are blocking real-readiness and which residual risks are
tracked without blocking the local gate.

## Blocking Gaps

| gap id | status | reason |
|---|---|---|
| `current-evidence-dpi-json-missing` | `BLOCKED_BY_GATE` | The working map records the bounded DPI/proxy subclaim from retained local summary evidence, but `check_real_readiness` now requires the machine-readable `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.json` artifact before the current evidence context can pass. |

## Cleared Evidence

| gap id | status | boundary |
|---|---|---|
| `external-dpi-proof-missing` | `CLEARED_BY_RETAINED_SUMMARY_ONLY` | `docs/verification/GHOST_PULSE_DPI_LAB_LATEST.md` states that the `dpi_lab` evidence was `VERIFIED` with authorized lab, baseline, pulse result, and conclusion measurements. This does not by itself restore the missing machine-readable JSON artifact, does not prove production readiness, durable censorship resistance, anonymity, provider health, customer traffic, settlement finality, or production SLOs. |

## Non-Blocking Tracked Risks

| gap id | status |
|---|---|
| `cross-plane-proof-gate-wiring-incomplete` | `NON_BLOCKING_TRACKED_RISK` |
| `post-action-dataplane-probe-operationalization` | `NON_BLOCKING_TRACKED_RISK` |
| `economy-dataplane-separation-still-manual` | `NON_BLOCKING_TRACKED_RISK` |
| `historical-doc-claim-ingestion-risk` | `NON_BLOCKING_TRACKED_RISK` |

## Operator Safety

Do not paste private target URLs, proxy endpoints, operator IDs, scope IDs,
subscriber data, tokens, or packet captures into chat. Use local collector and
import scripts only inside an authorized environment.
