#!/usr/bin/env python3
"""
Database initialization script for x0tta6bl4
==============================================
Creates all database tables and initializes with default data.
"""
import logging
import sys
import os

# Add the project root to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.database import create_tables, SessionLocal, User, License

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def init_database():
    """Initialize the database with required tables and default data."""
    logger.info("📦 Initializing x0tta6bl4 database...")
    
    try:
        # Create all tables
        create_tables()
        logger.info("✅ Database tables created successfully")
        
        # Initialize session
        db = SessionLocal()
        
        # Check if default user exists
        default_user = db.query(User).filter(User.email == "demo@x0tta6bl4.com").first()
        
        if not default_user:
            logger.info("Creating default demo user...")
            # Create demo user (will be in free tier by default)
            from src.api.users import generate_api_key, hash_password
            
            demo_user = User(
                id="demo-user-1",
                email="demo@x0tta6bl4.com",
                password_hash=hash_password("demo1234"),
                full_name="Demo User",
                company="x0tta6bl4 Inc.",
                api_key=generate_api_key(),
                requests_count=0,
                requests_limit=10000
            )
            db.add(demo_user)
            
            # Create a default license for demo user
            from src.sales.telegram_bot import TokenGenerator
            demo_license = License(
                token=TokenGenerator.generate(tier="basic"),
                user_id=demo_user.id,
                tier="basic",
                is_active=True
            )
            db.add(demo_license)
            
            db.commit()
            logger.info("✅ Demo user and license created successfully")
        else:
            logger.info("Demo user already exists")
        
        # Check if we have any licenses
        license_count = db.query(License).count()
        logger.info(f"Total licenses: {license_count}")
        
        # Check if we have any users
        user_count = db.query(User).count()
        logger.info(f"Total users: {user_count}")
        
        db.close()
        
        logger.info("✅ Database initialization complete!")
        return True
        
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


if __name__ == "__main__":
    success = init_database()
    sys.exit(0 if success else 1)