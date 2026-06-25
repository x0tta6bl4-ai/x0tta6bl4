"""Public sales and commercialization helpers for x0tta6bl4.

The package keeps imports lazy so lightweight product/readiness code does not
load the paid x402 FastAPI surface unless a caller explicitly asks for it.
"""

from __future__ import annotations

from importlib import import_module
import sys
from typing import Any


_LAZY_EXPORTS = {
    "PRODUCT_IDEAS": "src.sales.product_ideas",
    "ProductIdea": "src.sales.product_ideas",
    "build_product_idea_portfolio": "src.sales.product_ideas",
    "get_product_idea": "src.sales.product_ideas",
    "PRIMARY_IDEA_ID": "src.sales.pilot_package",
    "OFFER_NAME": "src.sales.pilot_package",
    "build_pilot_package": "src.sales.pilot_package",
    "TARGET_WALLET_ADDRESS": "src.sales.wallet_payment_intake",
    "build_wallet_payment_intake": "src.sales.wallet_payment_intake",
    "is_evm_address_shape": "src.sales.wallet_payment_intake",
    "mask_wallet": "src.sales.wallet_payment_intake",
    "TASK_SOURCES": "src.sales.paid_task_pipeline",
    "TASK_TYPES": "src.sales.paid_task_pipeline",
    "build_paid_task_pipeline": "src.sales.paid_task_pipeline",
    "OPPORTUNITIES": "src.sales.non_bounty_income",
    "build_non_bounty_income_map": "src.sales.non_bounty_income",
    "score_opportunity": "src.sales.non_bounty_income",
    "score_paid_task_listing": "src.sales.paid_task_selector",
    "score_paid_task_listings": "src.sales.paid_task_selector",
    "rank_needs": "src.sales.agentpact_needs",
    "build_deal_proposal": "src.sales.agentpact_needs",
    "build_selection_packet": "src.sales.agentpact_needs",
    "summarize_wallet_market_state": "src.sales.agentpact_market_watch",
    "TELEGRAM_AVAILABLE": "src.sales.telegram_bot_v2",
    "generate_code": "src.sales.telegram_bot_v2",
    "generate_ref_link": "src.sales.telegram_bot_v2",
}

__all__ = sorted(_LAZY_EXPORTS)


def _import_lazy_module(module_name: str):
    module = sys.modules.get(module_name)
    if module is not None:
        return module

    package_name, _, attr_name = module_name.rpartition(".")
    package = sys.modules.get(package_name)
    existing = getattr(package, attr_name, None) if package is not None else None
    if getattr(existing, "__name__", None) == module_name:
        sys.modules[module_name] = existing
        return existing

    return import_module(module_name)


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module 'src.sales' has no attribute {name!r}")
    module = _import_lazy_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
