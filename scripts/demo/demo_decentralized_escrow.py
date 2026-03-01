"""
Demo: Decentralized Escrow via Token Bridge
==========================================

This script demonstrates how x0tta6bl4 locks X0T tokens in a 
smart-contract-based escrow during node rentals.
"""

import asyncio
import logging
import sys
import os
from unittest.mock import MagicMock, patch, AsyncMock

# Add project root to path
sys.path.append(os.getcwd())

from src.api.maas_marketplace import rent_node, release_escrow
from src.database import MarketplaceListing, MarketplaceEscrow, User

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("Decentralized-Escrow-Demo")

async def run_demo():
    logger.info("🚀 Starting Decentralized Escrow Demo")
    
    # 1. Setup Mock DB
    db = MagicMock()
    
    # Mock X0T Listing
    mock_listing = {
        "listing_id": "lst-x0t-01",
        "node_id": "agent-node-01",
        "price_token_per_hour": 10.0,
        "currency": "X0T",
        "status": "available",
        "owner_id": "seller-id"
    }
    
    mock_row = MagicMock(spec=MarketplaceListing)
    mock_row.id = "lst-x0t-01"
    mock_row.node_id = "agent-node-01"
    mock_row.price_token_per_hour = 10.0
    mock_row.currency = "X0T"
    mock_row.status = "available"
    
    mock_user = MagicMock(spec=User)
    mock_user.id = "buyer-id"
    mock_user.role = "user"
    
    # Mock Escrow row
    mock_escrow = MagicMock(spec=MarketplaceEscrow)
    mock_escrow.id = "esc-test-01"
    mock_escrow.currency = "X0T"
    mock_escrow.status = "held"
    
    # Configure DB queries
    db.query.return_value.filter.return_value.first.side_effect = [
        mock_row,    # rent_node: fetch listing row
        mock_row,    # release_escrow: fetch listing row
        mock_escrow  # release_escrow: fetch escrow row
    ]
    
    # 2. Simulate Renting with X0T
    logger.info("💰 Step 1: Renting node with X0T tokens...")
    
    with patch("src.api.maas_marketplace._get_listing_from_cache_or_db", return_value=mock_listing), \
         patch("src.api.maas_marketplace._get_token_bridge") as mock_bridge_getter:
        
        mock_bridge = MagicMock()
        mock_bridge.lock_escrow_on_chain = AsyncMock(return_value="0x_mock_tx_hash")
        mock_bridge_getter.return_value = mock_bridge
        
        result = await rent_node("lst-x0t-01", "mesh-01", hours=2, current_user=mock_user, db=db)
        
        logger.info(f"✅ Escrow initiated: {result['status']}")
        logger.info(f"🔗 On-chain TX: {result.get('amount_held_token')} X0T locked.")
        mock_bridge.lock_escrow_on_chain.assert_called_once()

    # 3. Simulate Escrow Release
    logger.info("\n🔓 Step 2: Releasing escrow after healthy heartbeat...")
    
    # Reset side effect for second phase
    db.query.return_value.filter.return_value.first.side_effect = [mock_row, mock_escrow]
    
    with patch("src.api.maas_marketplace._get_listing_from_cache_or_db", return_value=mock_listing), \
         patch("src.api.maas_marketplace._get_token_bridge") as mock_bridge_getter:
        
        mock_bridge = MagicMock()
        mock_bridge.release_escrow_on_chain = AsyncMock(return_value=True)
        mock_bridge_getter.return_value = mock_bridge
        
        await release_escrow("lst-x0t-01", current_user=mock_user, db=db)
        
        logger.info("✨ On-chain Release signal sent successfully!")
        mock_bridge.release_escrow_on_chain.assert_called_once()

    logger.info("\n✅ Decentralized Escrow Demo Complete.")

if __name__ == "__main__":
    asyncio.run(run_demo())
