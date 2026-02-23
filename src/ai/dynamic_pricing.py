"""
MaaS AI Dynamic Pricing — x0tta6bl4
====================================

Swarm-based intelligence for autonomous market regulation.
Analyzes network load and proposes price adjustments to the DAO.
"""

import logging
import math
from datetime import datetime
from typing import Dict, Any

from sqlalchemy.orm import Session
from src.database import MeshNode, MeshInstance, MarketplaceListing, get_db
from src.api.maas_telemetry import _get_telemetry

try:
    from src.api.maas_governance import _gov_engine
except Exception:  # pragma: no cover - compatibility fallback
    class _FallbackGovEngine:
        def __init__(self) -> None:
            self.proposals = {}

        def create_proposal(self, **_kwargs: Any) -> None:
            logger.warning("Governance engine unavailable; proposal skipped")

    _gov_engine = _FallbackGovEngine()

logger = logging.getLogger(__name__)

class PricingAgent:
    """
    Autonomous agent that monitors the marketplace and network health.
    """
    
    def __init__(self, target_utilization: float = 0.7):
        self.target_utilization = target_utilization # Goal: 70% of network busy

    def analyze_and_propose(self, db: Session):
        """
        Scan all meshes and propose price changes if needed.
        """
        # 1. Calculate Global Utilization
        total_listings = db.query(MarketplaceListing).count()
        rented_listings = db.query(MarketplaceListing).filter(MarketplaceListing.status == "rented").count()
        
        utilization = rented_listings / total_listings if total_listings > 0 else 0
        
        logger.info(f"🤖 AI Pricing: Current network utilization: {utilization:.1%}")
        
        # 2. Decide on proposal
        if utilization > self.target_utilization:
            # Demand is high -> Propose 10% price increase
            self._create_dao_proposal(
                title="Dynamic Price Adjustment: INCREASE",
                description=f"Network utilization is at {utilization:.1%}, exceeding target {self.target_utilization:.1%}. Proposing 10% increase to incentivize new node owners.",
                change_pct=10.0
            )
        elif utilization < 0.3 and total_listings > 10:
            # Demand is low -> Propose 10% price decrease
            self._create_dao_proposal(
                title="Dynamic Price Adjustment: DECREASE",
                description=f"Network utilization is low ({utilization:.1%}). Proposing 10% decrease to attract more mesh tenants.",
                change_pct=-10.0
            )

    def _create_dao_proposal(self, title: str, description: str, change_pct: float):
        """
        Interface with the Governance Engine to create a proposal.
        """
        # Prevent spam: check if a similar proposal is already active
        for p in _gov_engine.proposals.values():
            if p.title == title and p.state.value == "active":
                return

        _gov_engine.create_proposal(
            title=title,
            description=description,
            duration_seconds=3600 * 12, # 12 hour voting window
            actions=[
                {
                    "type": "update_config",
                    "key": "global_price_multiplier",
                    "value": 1.0 + (change_pct / 100.0)
                }
            ]
        )
        logger.info(f"📜 AI Agent created DAO Proposal: {title}")

# Global singleton
pricing_agent = PricingAgent()
