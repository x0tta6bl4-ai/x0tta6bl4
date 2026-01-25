#!/usr/bin/env python3
import json
import time
import hmac
import hashlib
import httpx

WEBHOOK_SECRET = "whsec_test_secret_key_for_testing_only"
WEBHOOK_URL = "http://localhost:8080/api/v1/billing/webhook"

def generate_signature(payload: bytes, secret: str) -> str:
    timestamp = str(int(time.time()))
    signed = f"{timestamp}.".encode("utf-8") + payload
    sig = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"

def test_webhook():
    test_payload = {
        "id": "evt_test_12345",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_12345",
                "object": "checkout.session",
                "customer": "cus_test_12345",
                "subscription": "sub_test_12345",
                "customer_details": {
                    "email": "demo@x0tta6bl4.com"
                },
                "metadata": {
                    "user_email": "demo@x0tta6bl4.com",
                    "plan": "pro"
                }
            }
        }
    }
    
    payload_bytes = json.dumps(test_payload).encode("utf-8")
    signature = generate_signature(payload_bytes, WEBHOOK_SECRET)
    
    headers = {
        "Content-Type": "application/json",
        "Stripe-Signature": signature
    }
    
    print("Sending webhook payload...")
    print(f"Event type: {test_payload['type']}")
    print(f"User email: {test_payload['data']['object']['customer_details']['email']}")
    
    response = httpx.post(WEBHOOK_URL, content=payload_bytes, headers=headers)
    
    print(f"\nResponse status: {response.status_code}")
    print(f"Response body: {response.text}")
    
    if response.status_code == 200:
        print("\n✅ Webhook received successfully!")
        print("Now checking if user plan was updated...")
        
        # Check user stats
        stats_response = httpx.get("http://localhost:8080/api/v1/users/stats")
        stats = stats_response.json()
        print(f"\nUser stats: {json.dumps(stats, indent=2)}")
        
        if stats.get("plans", {}).get("pro", 0) > 0:
            print("\n✅ User plan updated to pro!")
        else:
            print("\n⚠️ User plan not updated yet")
    else:
        print(f"\n❌ Webhook failed with status {response.status_code}")

if __name__ == "__main__":
    test_webhook()
