# src/sales/payment_verification.py

import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Optional, Any

import requests

logger = logging.getLogger(__name__)

class TronScanVerifier:
    """TronScan API integration for USDT payment verification"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://api.trongrid.io/v1"
        self.timeout = 30  # seconds

    def verify_payment(
        self,
        wallet_address: str,
        expected_amount: float,
        order_id: str,
        amount_tolerance: float = 0.01,
    ) -> Dict[str, Any]:
        try:
            headers = {"TRON-PRO-API-KEY": self.api_key} if self.api_key else {}
            params = {
                "only_to": "true",
                "only_confirmed": "true",
                "limit": 200,
                "token_id": "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT TRC20 Token ID
            }

            response = requests.get(
                f"{self.base_url}/accounts/{wallet_address}/transactions/trc20",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("data"):
                return {"verified": False, "error": "No transactions found"}

            for tx in data["data"]:
                is_recent = datetime.now() - datetime.fromtimestamp(
                    tx["block_timestamp"] / 1000
                ) < timedelta(hours=24)

                if not is_recent:
                    continue

                memo = tx.get("memo", "")
                if order_id not in memo:
                    continue

                amount = int(tx["value"]) / 1e6  # USDT has 6 decimal places

                lower_bound = expected_amount * (1 - amount_tolerance)
                upper_bound = expected_amount * (1 + amount_tolerance)

                if lower_bound <= amount <= upper_bound:
                    return {
                        "verified": True,
                        "transaction_hash": tx["transaction_id"],
                        "amount": amount,
                        "timestamp": tx["block_timestamp"],
                        "error": None,
                    }

            return {"verified": False, "error": "No matching transaction found"}

        except requests.exceptions.RequestException as e:
            return {"verified": False, "error": f"API request failed: {e}"}
        except (KeyError, ValueError) as e:
            return {"verified": False, "error": f"Failed to parse API response: {e}"}


class BaseUSDCVerifier:
    """Base Network USDC payment verification using Web3"""

    USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
    DECIMALS = 6
    DEFAULT_RPC = "https://mainnet.base.org"

    def __init__(self, rpc_url: Optional[str] = None):
        self.rpc_url = rpc_url or os.getenv("BASE_RPC_URL", self.DEFAULT_RPC)
        self._w3 = None

    @property
    def w3(self):
        if self._w3 is None:
            try:
                from web3 import Web3
                self._w3 = Web3(Web3.HTTPProvider(self.rpc_url))
            except ImportError:
                logger.error("web3 package not installed")
        return self._w3

    def verify_payment(
        self,
        tx_hash: str,
        expected_amount: float,
        expected_recipient: str,
        min_confirmations: int = 2,
    ) -> Dict[str, Any]:
        """
        Verify a USDC payment on Base network.
        """
        w3 = self.w3
        if not w3:
            return {"verified": False, "error": "Web3 not available"}

        try:
            # 1. Fetch transaction and receipt
            # Use w3.to_hex and other helpers if needed, but strings are usually fine
            receipt = w3.eth.get_transaction_receipt(tx_hash)

            if not receipt:
                return {"verified": False, "error": "Transaction not found"}

            # 2. Check status
            if receipt["status"] != 1:
                return {"verified": False, "error": "Transaction failed"}

            # 3. Check confirmations
            latest_block = w3.eth.block_number
            confirmations = latest_block - receipt["blockNumber"]
            if confirmations < min_confirmations:
                return {
                    "verified": False, 
                    "error": f"Insufficient confirmations ({confirmations}/{min_confirmations})"
                }

            # 4. Parse ERC-20 Transfer event
            transfer_topic = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
            
            usdc_transfers = []
            for log in receipt["logs"]:
                if (log["address"].lower() == self.USDC_CONTRACT.lower() and 
                    len(log["topics"]) >= 3 and
                    log["topics"][0].hex() == transfer_topic):
                    
                    to_address = "0x" + log["topics"][2].hex()[-40:]
                    amount_raw = int(log["data"].hex(), 16)
                    amount = amount_raw / (10 ** self.DECIMALS)
                    
                    usdc_transfers.append({
                        "to": to_address.lower(),
                        "amount": amount
                    })

            # 5. Validate recipient and amount
            for transfer in usdc_transfers:
                if transfer["to"] == expected_recipient.lower():
                    if abs(transfer["amount"] - expected_amount) < 0.000001:
                        return {
                            "verified": True,
                            "transaction_hash": tx_hash,
                            "amount": transfer["amount"],
                            "confirmations": confirmations,
                            "error": None
                        }

            return {
                "verified": False, 
                "error": f"No valid USDC transfer to {expected_recipient} found in transaction",
                "detected_transfers": usdc_transfers
            }

        except Exception as e:
            return {"verified": False, "error": f"Blockchain verification error: {str(e)}"}
