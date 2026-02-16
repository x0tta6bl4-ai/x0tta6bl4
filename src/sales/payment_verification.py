# src/sales/payment_verification.py

from datetime import datetime, timedelta
from typing import Dict, Optional

import requests


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
    ) -> Dict[str, any]:
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


class TONVerifier:
    """TON API integration for TON payment verification"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self.base_url = "https://tonapi.io/v2"
        self.timeout = 30

    def verify_payment(
        self,
        wallet_address: str,
        expected_amount: float,
        order_id: str,
        amount_tolerance: float = 0.01,
    ) -> Dict[str, any]:
        """Verify TON payment via TON API"""
        try:
            headers = (
                {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
            )
            params = {"limit": 100}

            response = requests.get(
                f"{self.base_url}/accounts/{wallet_address}/transactions",
                headers=headers,
                params=params,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("transactions"):
                return {"verified": False, "error": "No transactions found"}

            for tx in data["transactions"]:
                if not tx.get("success"):
                    continue

                is_recent = datetime.now() - datetime.fromtimestamp(
                    tx["utime"]
                ) < timedelta(hours=24)
                if not is_recent:
                    continue

                in_msg = tx.get("in_msg")
                if not in_msg:
                    continue

                # Check destination
                if in_msg.get("destination", {}).get("address") != wallet_address:
                    continue

                comment = in_msg.get("message")
                if not comment or order_id not in comment:
                    continue

                amount = int(in_msg["value"]) / 1e9  # TON has 9 decimal places

                lower_bound = expected_amount * (1 - amount_tolerance)
                upper_bound = expected_amount * (1 + amount_tolerance)

                if lower_bound <= amount <= upper_bound:
                    return {
                        "verified": True,
                        "transaction_hash": tx["hash"],
                        "amount": amount,
                        "timestamp": tx["utime"],
                        "error": None,
                    }

            return {"verified": False, "error": "No matching transaction found"}

        except requests.exceptions.RequestException as e:
            return {"verified": False, "error": f"API request failed: {e}"}
        except (KeyError, ValueError) as e:
            return {"verified": False, "error": f"Failed to parse API response: {e}"}
