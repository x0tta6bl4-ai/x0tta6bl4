"""
Demo: Congestion-based Dynamic Pricing
======================================

This script demonstrates how x0tta6bl4 increases rental prices 
automatically when a mesh segment becomes crowded.
"""

import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.append(os.getcwd())

from src.api.maas_marketplace import rent_node
from src.database import MarketplaceListing, User, MeshNode

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Congestion-Pricing-Demo")

async def run_demo():
    logger.info("🚀 Starting Congestion Pricing Demo")
    
    # 1. Setup Mock DB and Data
    db = MagicMock()
    
    mock_listing = {
        "listing_id": "lst-01",
        "node_id": "agent-01",
        "price_per_hour": 1.0,
        "currency": "USD",
        "status": "available"
    }
    
    mock_row = MagicMock(spec=MarketplaceListing)
    mock_row.price_per_hour = 100 # cents
    mock_row.currency = "USD"
    mock_row.node_id = "agent-01"
    mock_row.status = "available"
    
    mock_user = MagicMock(spec=User)
    mock_user.id = "buyer-01"
    mock_user.role = "user"
    
    # Configure first query for listing
    db.query.return_value.filter.return_value.first.return_value = mock_row

    # 2. Case 1: Empty Mesh (No congestion)
    logger.info("🟢 Case 1: Renting into an EMPTY mesh...")
    db.query.return_value.filter.return_value.count.return_value = 0
    
    with patch("src.api.maas_marketplace._get_listing_from_cache_or_db", return_value=mock_listing):
        result = await rent_node("lst-01", "mesh-empty", current_user=mock_user, db=db)
        logger.info(f"💰 Normal Price: {result['amount_held_cents']} cents")

    # 3. Case 2: Crowded Mesh (Congestion)
    logger.info("🔴 Case 2: Renting into a CROWDED mesh (10 nodes)...")
    # Reset status for second attempt
    mock_row.status = "available"
    mock_listing["status"] = "available"
    
    # 10 nodes > 5 threshold -> multiplier = 1.0 + (10-5)*0.1 = 1.5x
    db.query.return_value.filter.return_value.count.return_value = 10
    
    with patch("src.api.maas_marketplace._get_listing_from_cache_or_db", return_value=mock_listing):
        result = await rent_node("lst-01", "mesh-crowded", current_user=mock_user, db=db)
        logger.info(f"📈 Congested Price (1.5x): {result['amount_held_cents']} cents")
        assert result['amount_held_cents'] > 100

    logger.info("✅ Congestion Pricing Demo Complete. Market is now self-balancing.")

if __name__ == "__main__":
    asyncio.run(run_demo())
