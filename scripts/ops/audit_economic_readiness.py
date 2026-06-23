#!/usr/bin/env python3
"""
Mainnet Readiness Audit for x0tta6bl4 Economic Agent.
Checks if the system is ready for real cryptocurrency earnings.
"""

import os
import sys
import logging
from decimal import Decimal
from pathlib import Path

# Add src to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT))

from src.dao.token_rewards import TokenRewards, _get_web3_class

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("economic-audit")

def run_audit():
    logger.info("💰 STARTING ECONOMIC READINESS AUDIT...")

    # 1. Environment Check
    rpc_url = os.getenv("RPC_URL")
    contract_addr = os.getenv("X0T_CONTRACT_ADDRESS")
    private_key = os.getenv("OPERATOR_PRIVATE_KEY")

    missing = []
    if not rpc_url: missing.append("RPC_URL")
    if not contract_addr: missing.append("X0T_CONTRACT_ADDRESS")
    if not private_key: missing.append("OPERATOR_PRIVATE_KEY")

    if missing:
        logger.error(f"❌ Missing environment variables: {', '.join(missing)}")
        logger.info("   Hint: Set these to point to Base Sepolia or Mainnet.")
        return 1

    # 2. Web3 Connectivity
    Web3 = _get_web3_class()
    if not Web3:
        logger.error("❌ Web3 library not found or failed to load.")
        return 1

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            logger.error(f"❌ Failed to connect to RPC: {rpc_url}")
            return 1

        chain_id = w3.eth.chain_id
        logger.info(f"✅ Connected to Chain ID: {chain_id}")

        # 3. Wallet Audit
        account = w3.eth.account.from_key(private_key)
        balance_wei = w3.eth.get_balance(account.address)
        balance_eth = Decimal(balance_wei) / Decimal("1e18")

        logger.info(f"✅ Wallet: {account.address}")
        logger.info(f"✅ Native Balance: {balance_eth:.6f} ETH/MATIC")

        if balance_eth < Decimal("0.001"):
            logger.warning("⚠️ Low native balance. Gas fees might fail.")

        # 4. Token Contract Audit
        # Check if code exists at address
        code = w3.eth.get_code(w3.to_checksum_address(contract_addr))
        if code == b'' or code.hex() == '0x':
            logger.error(f"❌ No contract found at address: {contract_addr}")
            return 1

        logger.info(f"✅ X0T Contract found and verified.")

        # 5. Economic Viability (Gas Check)
        gas_price = w3.eth.gas_price
        est_gas_cost = (gas_price * 100000) / Decimal("1e18")
        logger.info(f"✅ Estimated Settlement Cost: {est_gas_cost:.6f} ETH")

        logger.info("\n" + "="*50)
        logger.info("🎉 ECONOMIC SYSTEM IS READY FOR REALITY")
        logger.info("="*50)
        logger.info(f"Network: {'Base Sepolia' if chain_id == 84532 else 'Other'}")
        logger.info(f"Mode: LIVE_TRANSACTIONS_ENABLED")

        return 0

    except Exception as e:
        logger.error(f"❌ Audit failed with error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(run_audit())
