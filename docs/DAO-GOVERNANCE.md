# DAO Governance

The governance stack is split across three contracts:

- [Voting.sol](/mnt/projects/src/dao/contracts/contracts/Voting.sol): proposal lifecycle with `7 days` discussion and `3 days` voting, quadratic voting power sourced from `X0TToken.votingPower()`
- [Governance.sol](/mnt/projects/src/dao/contracts/contracts/Governance.sol): stores execution plans, hashes them, and dispatches on-chain calls only after the voting contract reports `Succeeded`
- [Treasury.sol](/mnt/projects/src/dao/contracts/contracts/Treasury.sol): 3-of-5 multisig wallet for fund movements

## Proposal workflow

1. A staked proposer submits a title, description, and execution bundle through `Governance.submitProposal()`.
2. `Voting.createProposal()` records the execution hash and starts the `7 day` discussion period.
3. After discussion ends, token holders vote during the `3 day` window using quadratic voting power.
4. Once quorum and majority are met, `Governance.executeProposal()` rechecks the execution hash and dispatches the stored calls.
5. Treasury transfers remain separately gated by 3-of-5 confirmations.

## L2 posture

- Contracts are Solidity `0.8.20` and optimized for low-fee L2 deployment
- Event logs provide the on-chain audit trail needed for Arbitrum or Optimism
- The recommended production hardening is a timelock in front of `executeProposal()` plus an allowlist of callable targets
