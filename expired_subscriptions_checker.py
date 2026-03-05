#!/usr/bin/env python3
"""
x0tta6bl4 Subscription & Invoice Manager
========================================
1. Detects expired subscriptions.
2. Generates monthly invoices for Enterprise nodes.
3. Triggers soft-lock for non-paying users.
"""

import logging
import os
import sys
from datetime import datetime, timedelta

# Add src to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from src.database import SessionLocal, User, MeshInstance, Invoice
from src.api.maas.services import BillingService

logging.basicConfig(level=logging.INFO, format='[BILLING-CHECK] %(message)s')
logger = logging.getLogger(__name__)

def process_subscriptions():
    db = SessionLocal()
    billing = BillingService()
    now = datetime.utcnow()
    
    try:
        # 1. Check for expired subscriptions
        expired_users = db.query(User).filter(
            User.expires_at < now,
            User.plan != "starter" # Free/Starter doesn't expire in this context
        ).all()
        
        for user in expired_users:
            logger.warning(f"🚫 Subscription expired for {user.id} ({user.email})")
            # Downgrade or mark as overdue
            user.plan = "overdue"
            # In a real scenario, we'd trigger a webhook to MAPE-K to rate-limit this user
        
        # 2. Monthly Invoicing for Enterprise (if it's the 1st day of month)
        # OR run manually. For Utrecht pilot, we run it if user has no recent invoice.
        enterprise_users = db.query(User).filter(User.plan == "enterprise").all()
        for user in enterprise_users:
            # Check if invoice for this month exists
            last_invoice = db.query(Invoice).filter(
                Invoice.user_id == user.id,
                Invoice.issued_at > now - timedelta(days=28)
            ).first()
            
            if not last_invoice:
                import asyncio
                # Run async invoice generation in sync context
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(billing.generate_monthly_invoice(user.id))
                if result.get("status") == "success":
                    logger.info(f"✅ Auto-generated Enterprise invoice for {user.id}")

        db.commit()
        logger.info("Subscription check cycle complete.")
        
    except Exception as e:
        logger.error(f"❌ Error in billing cycle: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    process_subscriptions()
