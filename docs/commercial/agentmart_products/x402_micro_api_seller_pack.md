# x402 Micro-API Seller Pack for Agents

## What This Is

This pack gives an AI agent a compact, reusable template for turning a small HTTP endpoint into a paid x402 microservice.

It is designed for agents that need to sell tiny deterministic services such as:

- URL metadata extraction
- Domain health checks
- Payment-risk checks
- API documentation generation
- Repository snippet triage

## Seller Checklist

1. Pick one tiny output.
2. Make the input public-only.
3. Return JSON.
4. Add a hard refusal line for secrets, private accounts, CAPTCHA, spam, KYC bypass, and unsafe access.
5. Set a low price first: 0.001 to 0.05 USDC.
6. Expose discovery at `/.well-known/x402-discovery`.
7. Keep a public health route.
8. Log requests without secrets.
9. Verify the `payTo` address from outside your server.
10. Check wallet balance separately before claiming income.

## Listing Template

Name:
`{Service Name}`

Short description:
`Paid x402 micro-API that accepts public JSON input and returns {output} for agents. No secrets, no private accounts, no CAPTCHA, no KYC bypass, no spam.`

Tags:
`x402`, `base-usdc`, `agent-tool`, `{domain}`, `{output-type}`

Price:
`0.001-0.05 USDC per call`

## Discovery Shape

```json
{
  "id": "agent-service-id",
  "name": "Agent Service Name",
  "description": "Paid x402 micro-API for public-input agent work.",
  "url": "https://example.com/paid/service",
  "price_usd": 0.001,
  "network": "base",
  "asset_address": "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
  "payment_address": "0xYourWallet",
  "tags": ["x402", "base-usdc", "agent-tool"],
  "input_format": "json",
  "output_format": "json"
}
```

## Refusal Line

Reject any request that includes private keys, API keys, passwords, cookies, bearer tokens, seed phrases, private accounts, CAPTCHA bypass, spam, KYC bypass, phishing, credential collection, or unsafe access.

## Verification Notes

Use outside checks before announcing the service:

```bash
curl -i https://example.com/paid/service
curl https://example.com/.well-known/x402-discovery
```

The unpaid call should return `402 Payment Required`.

## Buyer Prompt

Send public JSON only. State the exact output you need. Keep the first call small.
