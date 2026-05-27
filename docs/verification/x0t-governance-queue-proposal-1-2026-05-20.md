# X0T Governance Queue Proposal 1

Status: VERIFIED HERE

This document records the read-only verification for the already-submitted
`queueProposal(1)` transaction on Base Sepolia. It is governance queue evidence,
not external settlement evidence.

## Verified Transaction

- Chain: Base Sepolia (`84532`)
- Governance contract: `0xf1B0086962e41710968D81F099c8ced23b97D2d2`
- Operator: `0x870B8b23F431c140FDf5c7b96987306a327AFF96`
- Transaction: `0x17162989436336d7f1cbfa13f77e3f06520234f9f957cfa89d8d8485bed8ae61`
- Explorer: `https://sepolia.basescan.org/tx/0x17162989436336d7f1cbfa13f77e3f06520234f9f957cfa89d8d8485bed8ae61`
- Block: `41742017`
- Block timestamp: `2026-05-20T04:45:22Z`
- Receipt status: `0x1`
- Decoded call: `queueProposal(1)`

## Queue Event

- Event: `ProposalQueued(uint256,uint256)`
- Proposal id: `1`
- Earliest execution: `2026-05-21T04:45:22Z`

## Current Proposal State

Read-only `state(1)` and `getProposal(1)` calls against Base Sepolia returned:

- State: `4` (`Queued`)
- `queued`: `true`
- `executed`: `false`
- `vetoed`: `false`

`execute(1)` must wait until the timelock passes and the proposal state becomes
ready. This queue proof does not satisfy `.tmp/external-settlement-evidence`.

Machine-readable shard:

- `.tmp/validation-shards/x0t-governance-queue-proposal-1-current.json`
