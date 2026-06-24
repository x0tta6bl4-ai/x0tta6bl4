"""x402 payment settings and constants."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_RECEIVER_WALLET = "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
DEFAULT_FACILITATOR_URL = "https://facilitator.openx402.ai"
DEFAULT_NETWORK = "eip155:8453"
USDC_ASSET_ADDRESS = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
DEFAULT_REPO_TRIAGE_PRICE = "$0.02"
DEFAULT_API_DOCS_PRICE = "$0.03"
DEFAULT_LISTING_AUDIT_PRICE = "$0.02"
DEFAULT_PAYMENT_RISK_PRICE = "$0.02"
DEFAULT_INCOME_ROUTE_PRICE = "$0.02"
DEFAULT_X402_VALIDATE_PRICE = "$0.01"
DEFAULT_URL_SNAPSHOT_PRICE = "$0.01"
DEFAULT_DOMAIN_HEALTH_PRICE = "$0.001"
DEFAULT_BOTHIRE_API_BASE = "https://www.bothire.io"
WEBHOOK_EVENT_DIR = Path(".tmp/non-bounty/webhooks")
WORKPROTOCOL_DELIVERABLE_DIR = Path(".tmp/non-bounty/workprotocol_deliverables")

AGENTMART_PRODUCT_FILES = {
    "x402_micro_api_seller_pack.md": Path("docs/commercial/agentmart_products/x402_micro_api_seller_pack.md"),
    "public_url_snapshot_buyer_kit.md": Path("docs/commercial/agentmart_products/public_url_snapshot_buyer_kit.md"),
    "domain_health_lite_workflow.md": Path("docs/commercial/agentmart_products/domain_health_lite_workflow.md"),
}

SECRET_PATTERN = r"(api[_-]?key|private[_-]?key|secret|token|password|bearer\s+[a-z0-9._-]+)"


@dataclass(frozen=True)
class PaidApiSettings:
    pay_to: str = DEFAULT_RECEIVER_WALLET
    facilitator_url: str = DEFAULT_FACILITATOR_URL
    network: str = DEFAULT_NETWORK
    asset_address: str = USDC_ASSET_ADDRESS
    bothire_api_base: str = DEFAULT_BOTHIRE_API_BASE
    allow_unpaid_dev: bool = False
    verify_access: bool = False

    @classmethod
    def from_env(cls) -> "PaidApiSettings":
        return cls(
            pay_to=os.getenv("X402_PAY_TO", DEFAULT_RECEIVER_WALLET),
            facilitator_url=os.getenv("X402_FACILITATOR_URL", DEFAULT_FACILITATOR_URL),
            allow_unpaid_dev=os.getenv("X402_ALLOW_UNPAID_DEV", "").lower() in ("1", "true", "yes"),
            verify_access=os.getenv("X402_VERIFY_ACCESS", "").lower() in ("1", "true", "yes"),
        )
