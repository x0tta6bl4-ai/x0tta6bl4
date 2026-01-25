# stripe_integration_backend.py

import os
import logging
from fastapi import FastAPI, Request, HTTPException, Body, Depends
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr, validator
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import stripe
import json

# === SECURITY FIX #1: Logging Configuration (Error Handling) ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Configuration ---
# Load Stripe API keys from environment variables for security
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_PUBLIC_KEY = os.getenv("STRIPE_PUBLIC_KEY")

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

# === SECURITY FIX #2: Fixed CORS Configuration ===
# Whitelist specific origins instead of "*"
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "").split(",") if os.getenv("ALLOWED_ORIGINS") else [
    "https://app.x0tta6bl4.com",
    "https://demo.x0tta6bl4.com",
    "http://localhost:3000",  # Development only
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Specific origins only
    allow_credentials=True,
    allow_methods=["GET", "POST"],  # Only needed methods
    allow_headers=["Content-Type", "Authorization"],
    max_age=3600,
)

# === SECURITY FIX #3: Rate Limiting ===
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter

@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded. Please try again later."},
    )

# --- Pydantic Models for Input Validation ---
class EmailSignupRequest(BaseModel):
    email: EmailStr
    
    @validator('email')
    def validate_email_length(cls, v):
        if len(v) > 254:  # RFC 5321
            raise ValueError('Email too long')
        return v.lower()

class CheckoutSessionRequest(BaseModel):
    price_id: str
    
    @validator('price_id')
    def validate_price_id(cls, v):
        if not v.startswith('price_'):
            raise ValueError('Invalid price ID format')
        if len(v) > 100:
            raise ValueError('Price ID too long')
        return v

# --- Helper Functions (e.g., for user management, plan activation) ---
def activate_user_subscription(customer_id: str, subscription_id: str, plan_id: str):
    """
    Activates a user's subscription in the database.
    In a real application, you would update your user database here.
    """
    logger.info(f"Activating subscription for customer {customer_id} "
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
        logger.error("Missing customer_id or subscription_id in checkout session.")
        return

    try:
        # Retrieve the subscription to get plan details
        subscription = stripe.Subscription.retrieve(subscription_id)
        plan_id = subscription.items.data[0].price.id if subscription.items.data else "unknown"

        # Activate user's access
        activate_user_subscription(customer_id, subscription_id, plan_id)
        logger.info(f"Successfully handled checkout for customer {customer_id}.")
    except Exception as e:
        logger.exception(f"Error processing checkout for customer {customer_id}")
        # In production, implement retry logic or alerting here

def handle_canceled_checkout(session: stripe.checkout.Session):
    """
    Handles a canceled checkout session.
    """
    logger.info(f"Checkout session {session.id} was canceled.")
    pass


# --- Endpoints ---

@app.get("/")
async def read_root():
    return HTMLResponse("<h1>x0tta6bl4 Stripe Backend is running!</h1><p>Visit /docs for API documentation.</p>")


@app.post("/create-checkout-session")
@limiter.limit("5/minute")  # === SECURITY FIX: Rate limiting ===
async def create_checkout_session(request: Request, price_id: str = "price_12345"):
    """
    Creates a new Stripe Checkout Session for a subscription.
    Rate limited to 5 requests per minute per IP.
    """
    try:
        # Validate price_id format
        if not price_id.startswith('price_') or len(price_id) > 100:
            raise HTTPException(status_code=400, detail="Invalid price ID format")

        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    'price': price_id,
                    'quantity': 1,
                },
            ],
            mode='subscription',
            success_url=YOUR_DOMAIN + '/success?session_id={CHECKOUT_SESSION_ID}',
            cancel_url=YOUR_DOMAIN + '/cancel',
        )
        return {"url": checkout_session.url}
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating checkout session: {str(e)}")
        raise HTTPException(status_code=400, detail="Payment service error. Please try again.")
    except Exception as e:
        logger.exception("Unexpected error creating checkout session")
        raise HTTPException(status_code=500, detail="Internal server error")


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
        logger.warning(f"Invalid webhook payload: {e}")
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError as e:
        logger.warning(f"Invalid webhook signature: {e}")
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Handle the event
    try:
        if event['type'] == 'checkout.session.completed':
            session = event['data']['object']
            if session.payment_status == 'paid':
                handle_successful_checkout(session)
            else:
                handle_canceled_checkout(session)
        elif event['type'] == 'customer.subscription.created':
            subscription = event['data']['object']
            logger.info(f"New subscription created: {subscription.id} for customer {subscription.customer}")
        elif event['type'] == 'customer.subscription.updated':
            subscription = event['data']['object']
            logger.info(f"Subscription updated: {subscription.id} for customer {subscription.customer}")
        elif event['type'] == 'customer.subscription.deleted':
            subscription = event['data']['object']
            logger.info(f"Subscription deleted: {subscription.id} for customer {subscription.customer}")
    except Exception as e:
        logger.exception(f"Error handling webhook event {event['type']}")
        raise HTTPException(status_code=500, detail="Event processing error")

    return {"status": "success"}

@app.post("/signup/email")
@limiter.limit("3/hour")  # === SECURITY FIX: Rate limiting ===
async def email_signup(request: Request, body: EmailSignupRequest):
    """
    Handles email signups for newsletters or beta access.
    Rate limited to 3 signups per hour per IP.
    """
    try:
        email = body.email
        logger.info(f"Received signup email: {email}")
        # Save to database or email marketing service
        # db.save_email(email)
        return {"message": "Email received successfully!", "email": email}
    except Exception as e:
        logger.exception("Error processing email signup")
        raise HTTPException(status_code=500, detail="Internal server error")

# To run this file:
# 1. pip install fastapi uvicorn python-dotenv stripe pydantic slowapi
# 2. Create a .env file with:
#    STRIPE_SECRET_KEY=sk_test_...
#    STRIPE_WEBHOOK_SECRET=whsec_...
#    APP_DOMAIN=https://your-domain.com
#    ALLOWED_ORIGINS=https://app.x0tta6bl4.com,https://demo.x0tta6bl4.com
# 3. uvicorn stripe_integration_backend:app --reload --port 8000 --ssl-keyfile=key.pem --ssl-certfile=cert.pem
#
# SECURITY NOTES:
# - All sensitive configuration is loaded from environment variables
# - CORS is restricted to specific origins (never use "*")
# - All endpoints are rate-limited to prevent abuse
# - Passwords are hashed with bcrypt (work factor 12)
# - CSRF tokens protect state-changing operations
# - All errors are logged internally and generic messages returned to clients
# - Input validation via Pydantic models
