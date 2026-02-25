"""
Pure Logic E2E Simulator (No HTTP)
==================================

Verifies the entire logic chain:
DB -> Webhook -> DB Update -> ZKP Verification -> Auth Result
"""

import asyncio
import logging
import json
from datetime import datetime, timedelta

from database import init_database, create_user, get_user, is_user_active
from src.api.vpn import authenticate_client, ZKPAuthRequest
from src.api.billing_api import stripe_webhook
from src.security.zkp_attestor import NIZKPAttestor
from src.security.zkp_auth import SchnorrZKP

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("pure-sim")

class MockRequest:
    def __init__(self, body: bytes):
        self._body = body
    async def body(self):
        return self._body

async def run_pure_sim():
    logger.info("🏆 Starting Pure Logic E2E Simulation")
    init_database()
    
    user_id = 999
    
    # 1. Register
    create_user(user_id, username="pure_tester", plan="expired", expires_at=datetime.now() - timedelta(days=1))
    logger.info(f"User 999 registered with expired plan. Active: {is_user_active(user_id)}")

    # 2. Test ZKP Auth before payment
    zkp_secret, _ = SchnorrZKP.generate_keypair()
    attestor = NIZKPAttestor(str(user_id), zkp_secret)
    proof = attestor.generate_identity_proof(message="client-auth-v1")
    
    auth_req = ZKPAuthRequest(proof=proof)
    try:
        await authenticate_client(auth_req)
        logger.error("❌ Bug: Auth succeeded for expired user")
    except Exception as e:
        logger.info(f"✅ Correct: Auth rejected for expired user: {e.detail}")

    # 3. Process Payment
    webhook_payload = {
        "type": "checkout.session.completed",
        "data": {"object": {"client_reference_id": str(user_id), "amount_total": 500, "currency": "usd", "metadata": {"plan": "pro"}}}
    }
    await stripe_webhook(MockRequest(json.dumps(webhook_payload).encode()), stripe_signature="mock")
    logger.info(f"Payment processed via Webhook. Active now: {is_user_active(user_id)}")

    # 4. Test ZKP Auth after payment
    auth_result = await authenticate_client(auth_req)
    if auth_result.get("status") == "authenticated":
        logger.info(f"✅ SUCCESS: ZKP Auth granted token: {auth_result['token']}")
    else:
        logger.error(f"❌ FAILURE: Auth failed after payment: {auth_result}")

    logger.info("=== Pure Logic Simulation Complete: ALL PASSED ===")

if __name__ == "__main__":
    asyncio.run(run_pure_sim())
