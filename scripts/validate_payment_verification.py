# scripts/validate_payment_verification.py
import asyncio
import os
import sys
from datetime import datetime
from unittest.mock import AsyncMock, patch

from dotenv import load_dotenv

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.sales.payment_verification import TONVerifier, TronScanVerifier
from src.sales.telegram_bot import (Config,  # Import necessary functions
                                    TokenGenerator, confirm_payment)

# Load environment variables for API keys and wallet addresses
load_dotenv()


async def simulate_payment_verification():
    """Simulates the payment verification process for testing."""
    print("--- Starting Payment Verification Validation Script ---")

    # --- Configuration ---
    # Use actual config from telegram_bot
    Config.USDT_TRC20_WALLET = os.getenv("USDT_TRC20_WALLET", "TYourWalletAddressHere")
    Config.TON_WALLET = os.getenv("TON_WALLET", "UQYourTonWalletAddressHere")

    print(f"USDT TRC20 Wallet: {Config.USDT_TRC20_WALLET}")
    print(f"TON Wallet: {Config.TON_WALLET}")
    print(f"TRON_API_KEY: {'****' if os.getenv('TRON_API_KEY') else 'Not Set'}")
    print(f"TON_API_KEY: {'****' if os.getenv('TON_API_KEY') else 'Not Set'}")

    if (
        Config.USDT_TRC20_WALLET == "TYourWalletAddressHere"
        and Config.TON_WALLET == "UQYourTonWalletAddressHere"
    ):
        print(
            "⚠️ Warning: Wallet addresses are default placeholders. Please set USDT_TRC20_WALLET and TON_WALLET env vars."
        )
        return

    # --- Simulate a test purchase ---
    test_tier = "solo"
    test_order_id = TokenGenerator.generate_order_id()
    test_price_rub = 100  # Example price
    amount_usdt = float(test_price_rub)  # 1 USDT = 1 RUB for simplicity in test
    amount_ton = float(test_price_rub) / 2  # 1 TON = 2 RUB for simplicity in test

    print(
        f"\nSimulating purchase for Order ID: {test_order_id}, Tier: {test_tier}, Price: {test_price_rub}₽"
    )
    print(f"Expected USDT amount: {amount_usdt}, Expected TON amount: {amount_ton}")

    # --- Test TronScanVerifier directly ---
    print("\n--- Testing TronScanVerifier Directly (Mocked) ---")
    mock_tronscan_result = {"verified": False, "error": "Mocked error"}
    with patch("src.sales.payment_verification.requests.get") as mock_get:
        # Simulate a successful TronScan response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "transaction_id": "mock_tx_tron_123",
                    "value": str(int(amount_usdt * 1e6)),  # Convert to smallest unit
                    "block_timestamp": int(datetime.now().timestamp() * 1000),
                    "memo": f"Payment for {test_order_id}",
                    "to": Config.USDT_TRC20_WALLET,
                }
            ]
        }
        mock_get.return_value = mock_response

        verifier = TronScanVerifier(api_key=os.getenv("TRON_API_KEY", "mock-tron-key"))
        result = verifier.verify_payment(
            Config.USDT_TRC20_WALLET, amount_usdt, test_order_id
        )

        if result["verified"]:
            print(
                f"✅ TronScanVerifier direct test: Payment verified! TX: {result['transaction_hash']}"
            )
        else:
            print(
                f"❌ TronScanVerifier direct test: Verification failed. Error: {result['error']}"
            )
        mock_tronscan_result = result  # Store for later

    # --- Test TONVerifier directly ---
    print("\n--- Testing TONVerifier Directly (Mocked) ---")
    mock_ton_result = {"verified": False, "error": "Mocked error"}
    with patch("src.sales.payment_verification.requests.get") as mock_get:
        # Simulate a successful TON response
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "transactions": [
                {
                    "hash": "mock_tx_ton_456",
                    "utime": int(datetime.now().timestamp()),
                    "success": True,
                    "in_msg": {
                        "value": str(int(amount_ton * 1e9)),  # Convert to nanoTON
                        "source": "UQ_mock_source",
                        "destination": {"address": Config.TON_WALLET},
                        "message": test_order_id,
                    },
                }
            ]
        }
        mock_get.return_value = mock_response

        verifier = TONVerifier(api_key=os.getenv("TON_API_KEY", "mock-ton-key"))
        result = verifier.verify_payment(Config.TON_WALLET, amount_ton, test_order_id)

        if result["verified"]:
            print(
                f"✅ TONVerifier direct test: Payment verified! TX: {result['transaction_hash']}"
            )
        else:
            print(
                f"❌ TONVerifier direct test: Verification failed. Error: {result['error']}"
            )
        mock_ton_result = result  # Store for later

    # --- Simulate Telegram Bot confirm_payment handler ---
    print("\n--- Simulating Telegram Bot confirm_payment handler ---")

    # Mock Telegram Update and Context objects
    mock_update = AsyncMock()
    mock_update.callback_query.data = f"paid_{test_tier}_{test_order_id}"
    mock_context = AsyncMock()

    # Patch the verifier calls within the telegram_bot handler
    # Use the results from our direct tests
    with (
        patch("src.sales.telegram_bot.TronScanVerifier") as MockTronScanVerifier,
        patch("src.sales.telegram_bot.TONVerifier") as MockTONVerifier,
    ):

        # Configure MockTronScanVerifier
        mock_tron_instance = AsyncMock()
        MockTronScanVerifier.return_value = mock_tron_instance
        mock_tron_instance.verify_payment.return_value = mock_tronscan_result

        # Configure MockTONVerifier
        mock_ton_instance = AsyncMock()
        MockTONVerifier.return_value = mock_ton_instance
        mock_ton_instance.verify_payment.return_value = mock_ton_result

        # Call the actual handler
        await confirm_payment(mock_update, mock_context)

        # Check output messages
        if mock_tronscan_result["verified"] or mock_ton_result["verified"]:
            mock_update.callback_query.edit_message_text.assert_called_once()
            args, kwargs = mock_update.callback_query.edit_message_text.call_args
            message = args[0]
            if "ПЛАТЕЖ ПОДТВЕРЖДЁН!" in message:
                print(
                    "✅ Telegram bot simulation: Payment confirmed message displayed."
                )
            else:
                print(
                    f"❌ Telegram bot simulation: Unexpected message on payment confirmed: {message}"
                )
        else:
            mock_update.callback_query.edit_message_text.assert_called_once()
            args, kwargs = mock_update.callback_query.edit_message_text.call_args
            message = args[0]
            if "ПЛАТЕЖ НЕ НАЙДЕН" in message:
                print(
                    "✅ Telegram bot simulation: Payment not found message displayed."
                )
            else:
                print(
                    f"❌ Telegram bot simulation: Unexpected message on payment not found: {message}"
                )

    print("\n--- Payment Verification Validation Script Finished ---")


if __name__ == "__main__":
    asyncio.run(simulate_payment_verification())
