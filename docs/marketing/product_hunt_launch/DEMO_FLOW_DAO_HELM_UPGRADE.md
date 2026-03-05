# Demo Flow | DAO Vote To Helm Upgrade (MaaS v3.4.0)
Date: 2026-03-05

This flow is optimized for Product Hunt technical demos.

## 1. Pre-demo Setup

### Environment variables

```bash
export BASE_SEPOLIA_RPC="https://sepolia.base.org"
export MESH_GOVERNANCE_ADDRESS="<mesh_governance_contract>"
export X0T_TOKEN_ADDRESS="<x0t_token_contract>"
export OPERATOR_PRIVATE_KEY="<hex_private_key>"
```

### Persist deployment addresses

```bash
python src/dao/governance_script.py set-deployment \
  "$MESH_GOVERNANCE_ADDRESS" "$X0T_TOKEN_ADDRESS"
```

Note:
- `src/dao/deployments/base_sepolia.json` may not exist before this step.

## 2. Create Proposal

```bash
python src/dao/governance_script.py propose \
  --title "Upgrade mesh-operator to v3.4.0 with on-chain governance defaults" \
  --description "Production rollout proposal for MaaS v3.4.0 launch window" \
  --duration 3600
```

Capture:
- Proposal ID
- Tx hash
- Block number

## 3. Cast Vote

```bash
python src/dao/governance_script.py vote <proposal_id> for
```

Optional:
- Collect votes from multiple wallets for quorum demonstration.

## 4. Check Status Until Executable

```bash
python src/dao/governance_script.py status <proposal_id>
```

Expected:
- Proposal reaches executable state (`canExecute=true`).

## 5. Execute Proposal

```bash
python src/dao/governance_script.py execute <proposal_id>
```

Capture:
- Execution tx hash
- Receipt block
- Audit line in `src/dao/deployments/audit.jsonl`

## 6. Controlled Helm Upgrade Step

Current phase note:
- Event-driven auto executor webhook is planned in next phase.
- For P2 demo, run controlled operator action after on-chain execution.

```bash
helm upgrade mesh-op charts/x0tta-mesh-operator/ \
  --set meshDefaults.dao.governance.onChain.enabled=true \
  --set meshDefaults.dao.governance.onChain.chainId=84532 \
  --set meshDefaults.dao.governance.onChain.governanceAddress="$MESH_GOVERNANCE_ADDRESS" \
  --set meshDefaults.dao.governance.onChain.tokenAddress="$X0T_TOKEN_ADDRESS"
```

## 7. Post-upgrade Verification

```bash
kubectl get pods -n default
kubectl get meshclusters
python src/dao/governance_script.py list --limit 5
```

Demo proof bundle:
- Terminal recording (proposal/vote/execute/upgrade).
- `audit.jsonl` excerpt.
- Helm values snapshot used during upgrade.

