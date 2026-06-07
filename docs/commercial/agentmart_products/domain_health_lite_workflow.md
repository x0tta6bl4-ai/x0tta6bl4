# Domain Health Lite Workflow

## What This Is

This workflow gives agents a cheap first-pass check for public domains and URLs.

It is useful before:

- Paying an unknown x402 endpoint
- Listing a marketplace service
- Trusting a public API
- Debugging buyer reports about a dead link
- Checking whether a seller endpoint looks reachable

## Input

```json
{
  "target": "https://example.com",
  "fetch_http": true,
  "check_tls": true
}
```

## Checks

1. Normalize the target to HTTP or HTTPS.
2. Resolve DNS.
3. Reject private or local IP addresses.
4. Fetch HTTP without following redirects.
5. Check TLS expiry for HTTPS targets.
6. Return a compact JSON verdict.

## Output Contract

```json
{
  "schema": "paid_domain_health_report.v1",
  "verdict": "ok|review|reject",
  "hostname": "example.com",
  "addresses": ["93.184.216.34"],
  "http": {
    "fetched": true,
    "status": 200,
    "content_type": "text/html"
  },
  "tls": {
    "checked": true,
    "valid_now": true,
    "days_left": 90
  },
  "signals": {
    "public_dns": true,
    "http_checked": true,
    "tls_checked": true
  },
  "risks": []
}
```

## Buyer Prompt

Use this before paying a new endpoint. If DNS is private, reject. If TLS is expired or HTTP returns 5xx, do not spend on higher-cost calls until the seller fixes the endpoint.
