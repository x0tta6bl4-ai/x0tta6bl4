import asyncio
import os
import sys
from src.api.maas.services import BillingService
from src.core.settings import settings

async def main():
    print("Testing Real Verification Logic...")
    # Force production mode for test
    os.environ["X0TTA6BL4_PRODUCTION"] = "true"
    os.environ["STUB_CRYPTO_ENABLED"] = "false"
    os.environ["CRYPTO_DEPOSIT_ADDRESS"] = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
    
    service = BillingService()
    
    # This hash is valid format but likely doesn't exist or is not a USDC transfer to us
    fake_hash = "0x" + "a" * 64
    
    print(f"Verifying fake hash: {fake_hash}")
    try:
        res = await service.verify_crypto_payment(fake_hash, 0.02)
        print(f"Result: {res}")
        if res == False:
            print("✅ SUCCESS: Real verification rejected the fake hash.")
        else:
            print("❌ FAILURE: Real verification accepted a fake hash (STUB still active?)")
    except Exception as e:
        print(f"Caught expected or unexpected error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
