# stripe_integration_backend.py

import os
from fastapi import FastAPI, Request, HTTPException, Body, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import stripe
import json # For webhook example

# --- Configuration ---
# Load Stripe API keys from environment variables for security
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY") # Only needed for frontend

if not STRIPE_SECRET_KEY:
    raise ValueError("STRIPE_SECRET_KEY environment variable not set.")
if not STRIPE_WEBHOOK_SECRET:
    raise ValueError("STRIPE_WEBHOOK_SECRET environment variable not set.")

stripe.api_key = STRIPE_SECRET_KEY

# Replace with your actual domain for success/cancel redirects
YOUR_DOMAIN = os.getenv("APP_DOMAIN", "http://localhost:8000") 

# --- FastAPI App Setup ---
app = FastAPI(
    title="x0tta6bl4 Stripe Payments Backend",
    description="Backend for handling Stripe payments for x0tta6bl4 subscriptions.",
    version="1.0.0"
)

# Add CORS middleware if your frontend is on a different origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust this to your frontend domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Helper Functions (e.g., for user management, plan activation) ---
def activate_user_subscription(customer_id: str, subscription_id: str, plan_id: str):
    """
    Simulates activating a user's subscription in your database.
    In a real application, you would update your user database here.
    """
    print(f"DEBUG: Activating subscription for customer {customer_id} "
          f"with subscription ID {subscription_id} on plan {plan_id}")
    # Example: database.update_user(customer_id, is_active=True, plan=plan_id)
    pass

def handle_successful_checkout(session: stripe.checkout.Session):
    """
    Handles a successful checkout session.
    Retrieves customer and subscription details and activates the user.
    """
    customer_id = session.customer
    subscription_id = session.subscription
    
    if not customer_id or not subscription_id:
        print("ERROR: Missing customer_id or subscription_id in checkout session.")
        return

    # Retrieve the subscription to get plan details
    subscription = stripe.Subscription.retrieve(subscription_id)
    plan_id = subscription.items.data[0].price.id if subscription.items.data else "unknown"

    # Activate user's access
    activate_user_subscription(customer_id, subscription_id, plan_id)
    print(f"INFO: Successfully handled successful checkout for customer {customer_id}.")

def handle_canceled_checkout(session: stripe.checkout.Session):
    """
    Handles a canceled checkout session.
    No action usually needed here, but you might log it.
    """
    print(f"INFO: Checkout session {session.id} was canceled.")
    pass


# --- Endpoints ---

@app.get("/")
async def read_root():
    return HTMLResponse("<h1>x0tta6bl4 Stripe Backend is running!</h1><p>Visit /create-checkout-session to test.</p>")


@app.post("/create-checkout-session")
async def create_checkout_session(price_id: str = "price_12345"): # Example: replace with actual price ID
    """
    Creates a new Stripe Checkout Session for a one-time payment or subscription.
    The 'price_id' should correspond to a Price object configured in your Stripe Dashboard.
    """
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': price_id, # e.g., 'price_1HPuVf2eZvKYlo2CcGq8Bf9B' for a monthly subscription
                    'quantity': 1,
                },
            ],
            mode='subscription', # Or 'payment' for one-time purchases
            success_url=YOUR_DOMAIN + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + '/cancel',
            # You can pass client_reference_id to link this session to a user in your system
            # client_reference_id="user_123",
        )
        return {"url": checkout_session.url}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


@app.post("/stripe-webhook")
async def stripe_webhook(request: Request):
    """
    Endpoint for Stripe webhooks.
    Stripe sends events here (e.g., checkout.session.completed, invoice.payment_succeeded).
    """
    payload = await request.body()
    sig_header = request.headers.get('stripe-signature')

    event = None
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError as e:
        # Invalid payload
        raise HTTPException(status_code=400, detail=f"Invalid payload: {e}")
    except stripe.error.SignatureVerificationError as e:
        # Invalid signature
        raise HTTPException(status_code=400, detail=f"Invalid signature: {e}")

    # Handle the event
    if event['type'] == 'checkout.session.completed':
        session = event['data']['object']
        if session.payment_status == 'paid':
            handle_successful_checkout(session)
        else:
            handle_canceled_checkout(session)
    elif event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        print(f"INFO: New subscription created: {subscription.id} for customer {subscription.customer}")
        # Potentially update user status or sync with your system
    elif event['type'] == 'customer.subscription.updated':
        subscription = event['data']['object']
        print(f"INFO: Subscription updated: {subscription.id} for customer {subscription.customer}")
        # Handle plan changes, cancellations, etc.
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        print(f"INFO: Subscription deleted: {subscription.id} for customer {subscription.customer}")
        # Deactivate user access in your system
    # ... handle other event types as needed

    return {"status": "success"}

@app.post("/signup/email")
async def email_signup(email: str = Body(..., embed=True)):
    """
    Handles email signups for newsletters or beta access.
    In a real app, this would save the email to a database or send to an email marketing service.
    """
    print(f"INFO: Received signup email: {email}")
    # Here you would save the email to your database or an email marketing service
    # For example: db.save_email(email)
    return {"message": "Email received successfully!", "email": email}

# To run this file:
# 1. pip install fastapi uvicorn python-dotenv stripe
# 2. Create a .env file with:
#    STRIPE_SECRET_KEY=sk_test_...
#    STRIPE_WEBHOOK_SECRET=whsec_...
#    APP_DOMAIN=http://localhost:8000 # Or your deployed domain
# 3. uvicorn stripe_integration_backend:app --reload --port 8000
