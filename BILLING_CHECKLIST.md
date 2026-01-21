# Billing Integration Checklist - x0tta6bl4

## ✅ Pre-Deployment Setup

### 1. Stripe Dashboard Configuration
- [ ] Create Stripe account (if not exists)
- [ ] Switch to Test Mode
- [ ] Create Product: "x0tta6bl4 Pro"
- [ ] Create Price: Subscription $9.99/month (or your pricing)
- [ ] Note down: `STRIPE_PRICE_ID = price_...`

### 2. API Keys
- [ ] Get `STRIPE_SECRET_KEY = sk_test_...`
- [ ] Get `STRIPE_PUBLISHABLE_KEY = pk_test_...`

### 3. Webhook Setup
- [ ] Add webhook endpoint: `http://<YOUR_PUBLIC_IP>:8080/api/v1/billing/webhook`
- [ ] Select events: `checkout.session.completed`, `invoice.paid`
- [ ] Note down: `STRIPE_WEBHOOK_SECRET = whsec_...`

### 4. Environment Variables
Set these in your server environment:
```bash
export STRIPE_SECRET_KEY='sk_test_...'
export STRIPE_PUBLISHABLE_KEY='pk_test_...'
export STRIPE_PRICE_ID='price_...'
export STRIPE_WEBHOOK_SECRET='whsec_...'
export STRIPE_SUCCESS_URL='http://localhost:8080/?success=1'
export STRIPE_CANCEL_URL='http://localhost:8080/?canceled=1'
```

## ✅ Runtime Verification

### 1. Server Startup
- [ ] Start server: `uvicorn src.core.app:app --host 0.0.0.0 --port 8080`
- [ ] Check logs: "✅ Billing API endpoints включены"

### 2. Config Endpoint Test
```bash
curl http://localhost:8080/api/v1/billing/config
```
Expected response:
```json
{
  "configured": true,
  "publishable_key": "pk_test_...",
  "price_id": "price_..."
}
```

### 3. Checkout Session Creation
```bash
curl -X POST http://localhost:8080/api/v1/billing/checkout-session \
  -H "Content-Type: application/json" \
  -d '{"email":"test@x0tta6bl4.com","plan":"pro","quantity":1}'
```
Expected response:
```json
{
  "id": "cs_test_...",
  "url": "https://checkout.stripe.com/pay/cs_test_..."
}
```

### 4. Stripe Checkout Flow
- [ ] Open the `url` in browser
- [ ] Use test card: `4242 4242 4242 4242`
- [ ] Complete checkout
- [ ] Verify redirect to success URL

### 5. Webhook Verification
- [ ] Check server logs for webhook receipt
- [ ] Verify HMAC signature validation
- [ ] Check user plan update in database/memory

### 6. User Plan Verification
```bash
# Assuming you have user lookup endpoint
curl http://localhost:8080/api/v1/users/test@x0tta6bl4.com
```
Expected: `"plan": "pro"`

## ✅ Production Readiness

### Security
- [ ] Webhook secret properly secured
- [ ] No secrets in logs
- [ ] HTTPS in production (webhook endpoint)

### Error Handling
- [ ] Invalid email rejection
- [ ] Missing env vars → 503 error
- [ ] Stripe API errors → proper HTTP codes

### Monitoring
- [ ] Stripe webhook events logged
- [ ] Failed payments tracked
- [ ] Subscription lifecycle monitored

## 🚨 Troubleshooting

### Common Issues
1. **Webhook not received**: Check public IP accessibility
2. **HMAC validation fails**: Verify `STRIPE_WEBHOOK_SECRET`
3. **Checkout session fails**: Check `STRIPE_SECRET_KEY` and `STRIPE_PRICE_ID`
4. **User plan not updated**: Check webhook event parsing

### Logs to Check
- Server startup: Billing router inclusion
- Checkout creation: Stripe API response
- Webhook receipt: Event type and signature validation
- User update: Plan change confirmation

## 📋 Final Go/No-Go Criteria

- [ ] All endpoints respond correctly
- [ ] Stripe checkout flow works end-to-end
- [ ] Webhook processes successfully
- [ ] User plan updates after payment
- [ ] No security vulnerabilities
- [ ] Error handling robust

**Status:** ⏳ Ready for testing</content>
<parameter name="filePath">/mnt/AC74CC2974CBF3DC/BILLING_CHECKLIST.md