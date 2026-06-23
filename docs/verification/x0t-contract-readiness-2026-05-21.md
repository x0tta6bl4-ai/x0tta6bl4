# X0T Contract Readiness

Generated: `2026-05-21T15:45:18Z`
Decision: `BLOCKED_ON_DEPLOYMENT_CONFIG`
Contract readiness clear: `False`
Goal can be marked complete: `False`

## Summary

- build env ready: `True`
- node runtime ready: `False`
- effective node runtime ready: `True`
- node runtime ready source: `contract_build_verification`
- contract build verification ready: `True`
- contract dependencies ready: `True`
- missing contract dependencies: `0`
- invalid contract dependencies: `0`
- deployment config ready: `False`
- base sepolia manifest ready: `True`
- operator configs ready: `False`
- legacy contract surface ready: `True`
- bridge contract source ready: `True`

## Missing Inputs

- `operator_contract_addresses`: `OPERATOR_INPUT_REQUIRED` - operator bridge config still needs its own deployed bridge contract address; do not substitute X0TToken or MeshGovernance
  - command: `export X0T_BRIDGE_CONTRACT_ADDRESS="<deployed Base Sepolia bridge contract address>"`
  - command: `python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-json --write-md --require-input-ready`
  - command: `X0T_APPLY_BRIDGE_ADDRESS_APPROVAL=apply-bridge-address-base-sepolia python3 scripts/ops/apply_x0t_bridge_contract_address.py --bridge-address "$X0T_BRIDGE_CONTRACT_ADDRESS" --write-config --write-json --write-md --require-ready`
  - command: `python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md`
