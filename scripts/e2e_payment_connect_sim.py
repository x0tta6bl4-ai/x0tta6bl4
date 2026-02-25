"""
E2E Product Flow Simulator: x0tta6bl4 MaaS
==========================================

Automated test covering the full user journey:
1. User Registration in Database
2. Subscription Payment (Webhook Simulation)
3. ZKP Identity Verification
4. Ghost Protocol Connection (Bypassing DPI)
"""

import asyncio
import logging
import json
import uuid
from datetime import datetime, timedelta

from database import init_database, create_user, get_user, is_user_active
from src.api.vpn import authenticate_client, ZKPAuthRequest
from src.client.engine import QuantumShieldClient
from src.api.billing_api import stripe_webhook

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("e2e-tester")

class MockRequest:
    """Mocks a FastAPI request for webhook testing."""
    def __init__(self, body: bytes):
        self._body = body
    async def body(self):
        return self._body

async def run_e2e_test():
    logger.info("🚀 Starting E2E 'Payment -> Connect' Simulation")
    init_database()
    
    user_id = 777
    node_id = f"node-{user_id}"
    api_url = "http://localhost:8000" # Simulated
    
    # --- Step 1: Registration ---
    logger.info(f"Step 1: Registering user {user_id}...")
    user = create_user(user_id, username="tester_alpha", plan="trial")
    logger.info(f"User created. Current plan: {user['plan']}, Active: {is_user_active(user_id)}")

    # --- Step 2: Ghost Client Initialization ---
    client = QuantumShieldClient(api_url, node_id=str(user_id))
    
    # --- Step 3: Attempt connection BEFORE payment ---
    logger.info("Step 3: Attempting ZKP Auth BEFORE payment (should fail)...")
    auth_success = await client.authenticate()
    if not auth_success:
        logger.info("✅ Correct: Auth failed as expected (No active subscription)")
    else:
        logger.error("❌ Bug: Auth succeeded for unpaid user")
        return False

    # --- Step 4: Simulate Stripe Payment Webhook ---
    logger.info("Step 4: Simulating successful Stripe Payment ($5.00 Pro)...")
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": str(user_id),
                "amount_total": 500,
                "currency": "usd",
                "metadata": {"plan": "pro"}
            }
        }
    }
    # Mocking the call to billing_api logic directly since we can't run a real server here
    await stripe_webhook(MockRequest(json.dumps(webhook_payload).encode()), stripe_signature="mock_sig")
    
    # Verify DB update
    updated_user = get_user(user_id)
    logger.info(f"Payment processed. New plan: {updated_user['plan']}, Active: {is_user_active(user_id)}")
    assert updated_user['plan'] == "pro"
    assert is_user_active(user_id) == True

    # --- Step 5: Final ZKP Auth & Connect ---
    logger.info("Step 5: Final ZKP Auth & Ghost Protocol Connect...")
    auth_success = await client.authenticate()
    if auth_success:
        logger.info("✅ ZKP Authentication successful with Pro token")
        
        # Connect to Ghost Tunnel
        tunnel_success = await client.connect()
        if tunnel_success:
            logger.info("✅ SUCCESS: Ghost Protocol Tunnel Established (WebRTC Mimic)")
            logger.info(f"Connection Status: {client.get_status()}")
        else:
            logger.error("❌ Tunnel failed")
            return False
    else:
        logger.error("❌ Auth failed after payment")
        return False

    logger.info("========================================")
    logger.info("🏆 E2E TEST PASSED: Full Commercial Cycle Verified")
    logger.info("========================================")
    return True

if __name__ == "__main__":
    asyncio.run(run_e2e_test())
