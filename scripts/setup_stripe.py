import os
import getpass

def setup_stripe():
    print("--- x0tta6bl4: Stripe Integration Setup ---")
    
    api_key = getpass.getpass("Enter your Stripe Secret Key (sk_...): ")
    webhook_secret = getpass.getpass("Enter your Stripe Webhook Secret (whsec_...): ")
    publishable_key = input("Enter your Stripe Publishable Key (pk_...): ")

    missing = [
        name
        for name, value in (
            ("STRIPE_API_KEY", api_key),
            ("STRIPE_WEBHOOK_SECRET", webhook_secret),
            ("STRIPE_PUBLISHABLE_KEY", publishable_key),
        )
        if not value.strip()
    ]
    if missing:
        raise ValueError(f"Missing required values: {', '.join(missing)}")

    print("✅ Stripe credentials collected in memory.")
    print("🔐 This helper no longer writes secrets to .env.production.")
    print("Next step: store the values in your secret manager or deployment environment.")
    print("Expected keys: STRIPE_API_KEY, STRIPE_WEBHOOK_SECRET, STRIPE_PUBLISHABLE_KEY")
    print("Then restart maas-api so it loads the updated environment.")

if __name__ == "__main__":
    setup_stripe()
