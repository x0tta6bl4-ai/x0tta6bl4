#!/usr/bin/env python3
"""
Check database content
==============================================
Simple script to verify the database contains expected data.
"""
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import SessionLocal, User, License, Payment

def check_database():
    """Check if the database contains expected data."""
    db = SessionLocal()
    
    print("=== Database Status ===")
    
    # Check users
    users = db.query(User).all()
    print(f"\nUsers: {len(users)}")
    for user in users:
        print(f"  - {user.email} ({user.plan})")
        
    # Check licenses
    licenses = db.query(License).all()
    print(f"\nLicenses: {len(licenses)}")
    for license in licenses:
        print(f"  - {license.token} ({license.tier}, active: {license.is_active})")
        
    # Check payments
    payments = db.query(Payment).all()
    print(f"\nPayments: {len(payments)}")
    for payment in payments:
        print(f"  - {payment.order_id} ({payment.payment_method} - {payment.status})")
        
    db.close()
    
    return len(users) > 0 and len(licenses) > 0

if __name__ == "__main__":
    success = check_database()
    if not success:
        print("\n❌ Database initialization failed - no data found")
        sys.exit(1)
    print("\n✅ Database check passed")
    sys.exit(0)