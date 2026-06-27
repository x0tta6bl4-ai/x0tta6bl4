# X0T Token Smart Contracts

ERC-20 токен для mesh-сети x0tta6bl4.

## Quick Start

```bash
cd src/dao/contracts

# Use the Hardhat-supported Node runtime from .nvmrc
nvm use

# Install dependencies
npm ci

# Compile contracts
npm run compile

# Run tests
npm test

# Repo-level readiness evidence: run compile/test under Node 22 and retain artifacts
cd ../../..
python3 scripts/ops/verify_x0t_contract_build.py --write-json --write-md --require-verified
python3 scripts/ops/check_x0t_contract_readiness.py --write-json --write-md

# Start local node
cd src/dao/contracts
npm run node

# Deploy to local node (in another terminal)
npm run deploy:local
```

## Bridge Deployment

`X0TBridge` escrows X0T on Base Sepolia for mesh deposits and releases escrowed
X0T after operator-verified off-chain settlement. The deploy script is
fail-closed for Base Sepolia and requires an explicit approval environment
value before it can submit a transaction.

```bash
cd src/dao/contracts

# Local Hardhat node
X0T_TOKEN_ADDRESS=0x... npm run deploy:bridge:local

# Base Sepolia; requires explicit operator approval and a real deployer key
X0T_DEPLOY_BRIDGE_APPROVAL=deploy-bridge-base-sepolia \
X0T_TOKEN_ADDRESS=0x... \
X0T_BRIDGE_OPERATOR_ADDRESS=0x... \
PRIVATE_KEY=0x... \
npm run deploy:bridge:base-testnet
```

## Deployment

### Testnet (recommended for testing)

```bash
# 1. Copy .env.example to .env
cp .env.example .env

# 2. Add your private key to .env
# PRIVATE_KEY=your_private_key_here

# 3. Get testnet tokens:
#    - Polygon Mumbai: https://faucet.polygon.technology/
#    - Base Sepolia: https://www.coinbase.com/faucets/base-ethereum-sepolia-faucet

# 4. Deploy
npm run deploy:mumbai      # Polygon Mumbai testnet
npm run deploy:base-testnet # Base Sepolia testnet
```

### Mainnet

```bash
npm run deploy:polygon  # Polygon mainnet (~$0.01 deploy cost)
npm run deploy:base     # Base mainnet (~$0.001 deploy cost)
```

## Contract: X0TToken

### Economics

| Parameter | Value |
|-----------|-------|
| Symbol | X0T |
| Total Supply | 1,000,000,000 |
| Min Stake | 100 X0T |
| Stake Lock | 24 hours |
| Reward Pool | 10,000 X0T/epoch |
| Epoch Duration | 1 hour |
| Relay Price | 0.0001 X0T |
| Fee (burned) | 1% |

### Functions

#### Staking
```solidity
// Stake tokens for voting power + rewards
function stake(uint256 amount) external;

// Unstake after lock period
function unstake(uint256 amount) external;

// Get voting power
function votingPower(address user) external view returns (uint256);
```

#### Relay Rewards
```solidity
// Authorize relay node (owner only)
function setRelayerAuthorized(address relayer, bool authorized) external;

// Pay for relay (called by authorized relayer)
function payForRelay(address payer, uint256 relayCount) external;
```

#### Resource Payments
```solidity
// Pay for resources (bandwidth, storage, compute)
function payForResource(address provider, uint256 amount, string resourceType) external;
```

#### Epoch Rewards
```solidity
// Distribute rewards (owner/scheduler)
function distributeEpochRewards(address[] recipients, uint256[] uptimes) external;

// Check if epoch complete
function canDistributeRewards() external view returns (bool);
```

## Integration with Python

```python
from web3 import Web3

# Connect to network
w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))

# Load contract
with open("artifacts/X0TToken.sol/X0TToken.json") as f:
    abi = json.load(f)["abi"]

token = w3.eth.contract(address="0x...", abi=abi)

# Check balance
balance = token.functions.balanceOf(address).call()

# Stake tokens
tx = token.functions.stake(amount).build_transaction({
    "from": address,
    "nonce": w3.eth.get_transaction_count(address),
})
signed = w3.eth.account.sign_transaction(tx, private_key)
w3.eth.send_raw_transaction(signed.rawTransaction)
```

## Networks

| Network | Chain ID | RPC | Explorer |
|---------|----------|-----|----------|
| Polygon Mumbai | 80001 | https://rpc-mumbai.maticvigil.com | https://mumbai.polygonscan.com |
| Polygon | 137 | https://polygon-rpc.com | https://polygonscan.com |
| Base Sepolia | 84532 | https://sepolia.base.org | https://sepolia.basescan.org |
| Base | 8453 | https://mainnet.base.org | https://basescan.org |

## Security

- ✅ ReentrancyGuard on all state-changing functions
- ✅ OpenZeppelin battle-tested contracts
- ✅ 1% fee burned (deflationary)
- ✅ Stake lock period prevents flash loan attacks
- ✅ Only authorized relayers can claim relay payments

## License

MIT
