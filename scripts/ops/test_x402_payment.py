#!/usr/bin/env python3
"""Test x402 payment flow against the local paid API.

Usage:
    1. Fund wallet 0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099 with:
       - At least 0.001 USDC on Base mainnet
       - At least 0.0001 ETH for gas
    2. Set private key: export X0T_PRIVATE_KEY="0x..."
    3. Run: python3 scripts/ops/test_x402_payment.py
"""

import json
import os
import sys
import urllib.request
from pathlib import Path

API_BASE = "http://89.125.1.107:8120"
WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
USDC_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
FACILITATOR = "https://facilitator.openx402.ai"
CHAIN_ID = 8453  # Base mainnet


def check_balance():
    """Check USDC and ETH balance."""
    # ETH
    eth_req = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_getBalance",
        "params": [WALLET, "latest"],
        "id": 1
    }).encode()
    eth_resp = json.loads(urllib.request.urlopen(
        urllib.request.Request("https://mainnet.base.org", data=eth_req,
                              headers={"Content-Type": "application/json"}),
        timeout=15
    ).read())
    eth_bal = int(eth_resp["result"], 16) / 1e18

    # USDC
    usdc_data = "0x70a08231000000000000000000000000" + WALLET[2:].lower()
    usdc_req = json.dumps({
        "jsonrpc": "2.0",
        "method": "eth_call",
        "params": [{"to": USDC_CONTRACT, "data": usdc_data}, "latest"],
        "id": 1
    }).encode()
    usdc_resp = json.loads(urllib.request.urlopen(
        urllib.request.Request("https://mainnet.base.org", data=usdc_req,
                              headers={"Content-Type": "application/json"}),
        timeout=15
    ).read())
    usdc_bal = int(usdc_resp["result"], 16) / 1e6

    return eth_bal, usdc_bal


def test_discovery():
    """Test x402 discovery endpoint."""
    resp = json.loads(urllib.request.urlopen(
        f"{API_BASE}/.well-known/x402.json", timeout=15
    ).read())
    services = resp.get("services", [])
    print(f"Discovery: {len(services)} services found")
    for s in services:
        print(f"  - {s.get('name')}: {s.get('id', '?')[:8]}")
    return resp


def test_402_payment_request():
    """Test that paid endpoints return 402 with payment details."""
    endpoints = [
        "/paid/domain-health",
        "/paid/repo-triage",
        "/paid/url-snapshot",
        "/paid/income-route",
    ]
    print("\n402 Payment Requests:")
    for ep in endpoints:
        try:
            req = urllib.request.Request(f"{API_BASE}{ep}")
            resp = urllib.request.urlopen(req, timeout=15)
            print(f"  {ep} → HTTP {resp.status} (unexpected)")
        except urllib.error.HTTPError as e:
            if e.code == 402:
                body = json.loads(e.read())
                amount = int(body["accepts"][0]["amount"]) / 1e6
                print(f"  {ep} → HTTP 402 ✓ ({amount} USDC)")
            else:
                print(f"  {ep} → HTTP {e.code}")


def test_full_payment_flow():
    """Attempt full x402 payment flow (requires private key + funds)."""
    private_key = os.environ.get("X0T_PRIVATE_KEY")
    if not private_key:
        print("\n⚠️  X0T_PRIVATE_KEY not set. Skipping live payment test.")
        print("   To test: export X0T_PRIVATE_KEY='0x...'")
        return

    try:
        from web3 import Web3
        from eth_account import Account
    except ImportError:
        print("\n⚠️  web3 not installed. Run: pip install web3")
        return

    eth_bal, usdc_bal = check_balance()
    print(f"\nWallet: {WALLET}")
    print(f"ETH: {eth_bal:.6f}")
    print(f"USDC: {usdc_bal:.6f}")

    if usdc_bal < 0.001:
        print("❌ Insufficient USDC. Need at least 0.001 USDC.")
        return

    if eth_bal < 0.00001:
        print("❌ Insufficient ETH for gas. Need at least 0.00001 ETH.")
        return

    print("\n✅ Sufficient funds. Attempting payment...")
    # Full payment flow would go here
    # 1. Get 402 response from API
    # 2. Sign EIP-3009 transferWithAuthorization
    # 3. Send to facilitator
    # 4. Retry original request with payment proof
    print("   (Full flow requires web3 + private key signing)")


def main():
    print("=== x402 Payment Flow Test ===\n")

    # 1. Check balance
    eth_bal, usdc_bal = check_balance()
    print(f"Wallet: {WALLET}")
    print(f"ETH: {eth_bal:.6f}")
    print(f"USDC: {usdc_bal:.6f}")

    if usdc_bal < 0.001:
        print("\n⚠️  Wallet empty. To fund:")
        print(f"   1. Send USDC to {WALLET} on Base mainnet")
        print(f"   2. Or use Circle faucet: https://faucet.circle.com/")
        print(f"   3. Minimum: 0.001 USDC + 0.00001 ETH for gas")

    # 2. Test discovery
    print()
    test_discovery()

    # 3. Test 402 responses
    test_402_payment_request()

    # 4. Test full flow if possible
    test_full_payment_flow()

    print("\n=== Summary ===")
    print(f"API: {API_BASE}")
    print(f"Network: Base mainnet (chain_id={CHAIN_ID})")
    print(f"Currency: USDC")
    print(f"Facilitator: {FACILITATOR}")
    print(f"Status: {'✅ Ready for payments' if usdc_bal >= 0.001 else '⏳ Awaiting funding'}")


if __name__ == "__main__":
    main()
