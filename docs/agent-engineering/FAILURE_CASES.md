# Agent Work Receipt Gate Failure Cases

The gate keeps common handoff failures explicit and machine-readable.

## Missing Verification

Fixture: `products/agent-work-receipt-gate/receipts/invalid-missing-verification.json`

Expected signature: `handoff.invalid.missing_verification`

## Forbidden Claim

Fixture: `products/agent-work-receipt-gate/receipts/invalid-forbidden-claim.json`

Expected signature: `receipt.invalid.forbidden_claim`

## Missing Source Truth

Fixture: `products/agent-work-receipt-gate/receipts/invalid-missing-source-truth.json`

Expected signature: `receipt.invalid.missing_source_of_truth`
