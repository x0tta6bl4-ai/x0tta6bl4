import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv
from web3 import Web3
try:
    from web3.middleware import ExtraDataToPOAMiddleware # Web3.py v7
    geth_poa_middleware = ExtraDataToPOAMiddleware
except ImportError:
    from web3.middleware import geth_poa_middleware # Web3.py v6

# Load environment
load_dotenv(Path(__file__).parent / "contracts" / ".env")
# Also load root .env if not found
load_dotenv(Path(__file__).parent.parent.parent / ".env")

RPC_URL = os.getenv("POLYGON_RPC", "http://127.0.0.1:8545")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
POLYGONSCAN_API_KEY = os.getenv("POLYGONSCAN_API_KEY")

# Default Hardhat Key for Localhost if not set
if not PRIVATE_KEY and ("127.0.0.1" in RPC_URL or "localhost" in RPC_URL):
    print("⚠️ Using default Hardhat Private Key for Localhost")
    PRIVATE_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"

ARTIFACTS_DIR = Path(__file__).parent / "contracts" / "artifacts" / "contracts"
DEPLOYMENTS_DIR = Path(__file__).parent / "deployments"
DEPLOYMENTS_DIR.mkdir(exist_ok=True)

def load_contract(name: str):
    """Load contract ABI and Bytecode from Hardhat artifacts."""
    artifact_path = ARTIFACTS_DIR / f"{name}.sol" / f"{name}.json"
    if not artifact_path.exists():
        raise FileNotFoundError(f"Artifact not found: {artifact_path}")
    
    with open(artifact_path) as f:
        data = json.load(f)
    return data["abi"], data["bytecode"]

def main():
    print(f"🚀 Deploying to {RPC_URL}...")
    
    if not PRIVATE_KEY:
        print("❌ PRIVATE_KEY not set!")
        sys.exit(1)

    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("❌ Cannot connect to RPC")
        sys.exit(1)
        
    # Polygon/Mumbai PoA middleware
    w3.middleware_onion.inject(geth_poa_middleware, layer=0)
    
    account = w3.eth.account.from_key(PRIVATE_KEY)
    print(f"📝 Deployer: {account.address}")
    balance = w3.eth.get_balance(account.address)
    print(f"💰 Balance: {w3.from_wei(balance, 'ether')} ETH/MATIC")
    
    if balance == 0:
        print("⚠️ Warning: Balance is 0!")

    # 1. Deploy GovernanceToken
    print("\n📦 Deploying GovernanceToken...")
    abi, bytecode = load_contract("GovernanceToken")
    Token = w3.eth.contract(abi=abi, bytecode=bytecode)
    
    tx = Token.constructor().build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price,
    })
    
    # Estimate gas
    try:
        gas = w3.eth.estimate_gas(tx)
        tx["gas"] = int(gas * 1.1)
    except Exception as e:
        print(f"Gas estimation failed: {e}. Using default.")
        tx["gas"] = 3000000

    signed = account.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed.rawTransaction)
    print(f"   Tx sent: {tx_hash.hex()}")
    
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    token_address = receipt.contractAddress
    print(f"✅ GovernanceToken deployed to: {token_address}")

    # 2. Deploy Timelock
    print("\n⏳ Deploying X0TTA6BL4Timelock...")
    tl_abi, tl_bytecode = load_contract("X0TTA6BL4Timelock")
    Timelock = w3.eth.contract(abi=tl_abi, bytecode=tl_bytecode)
    
    # proposers = [], executors = [], admin = deployer
    tx_tl = Timelock.constructor([], [], account.address).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price,
    })
    
    try:
        gas = w3.eth.estimate_gas(tx_tl)
        tx_tl["gas"] = int(gas * 1.1)
    except Exception:
        tx_tl["gas"] = 4000000

    signed_tl = account.sign_transaction(tx_tl)
    tx_hash_tl = w3.eth.send_raw_transaction(signed_tl.rawTransaction)
    print(f"   Tx sent: {tx_hash_tl.hex()}")
    
    receipt_tl = w3.eth.wait_for_transaction_receipt(tx_hash_tl)
    timelock_address = receipt_tl.contractAddress
    print(f"✅ Timelock deployed to: {timelock_address}")

    # 3. Deploy Governor
    print("\n🏛  Deploying X0TTA6BL4Governor...")
    gov_abi, gov_bytecode = load_contract("X0TTA6BL4Governor")
    Gov = w3.eth.contract(abi=gov_abi, bytecode=gov_bytecode)
    
    tx_gov = Gov.constructor(token_address, timelock_address).build_transaction({
        "from": account.address,
        "nonce": w3.eth.get_transaction_count(account.address),
        "gasPrice": w3.eth.gas_price,
    })
    
    try:
        gas = w3.eth.estimate_gas(tx_gov)
        tx_gov["gas"] = int(gas * 1.1)
    except Exception:
        tx_gov["gas"] = 5000000

    signed_gov = account.sign_transaction(tx_gov)
    tx_hash_gov = w3.eth.send_raw_transaction(signed_gov.rawTransaction)
    print(f"   Tx sent: {tx_hash_gov.hex()}")
    
    receipt_gov = w3.eth.wait_for_transaction_receipt(tx_hash_gov)
    gov_address = receipt_gov.contractAddress
    print(f"✅ X0TTA6BL4Governor deployed to: {gov_address}")
    
    # Save deployment info
    info = {
        "network": RPC_URL,
        "chain_id": w3.eth.chain_id,
        "deployer": account.address,
        "contracts": {
            "GovernanceToken": token_address,
            "Timelock": timelock_address,
            "Governor": gov_address
        },
        "timestamp": time.time()
    }
    
    outfile = DEPLOYMENTS_DIR / f"polygon_deployment_{int(time.time())}.json"
    with open(outfile, "w") as f:
        json.dump(info, f, indent=2)
    print(f"\n📁 Deployment saved to {outfile}")

if __name__ == "__main__":
    main()
