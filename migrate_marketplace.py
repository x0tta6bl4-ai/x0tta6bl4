import asyncio
from sqlalchemy import create_engine, text
import os

DB_URL = "postgresql://x0ttta6bl4:x0t_pass@localhost:5432/x0tta6bl4_db"

async def run_migration():
    engine = create_engine(DB_URL)
    with engine.connect() as conn:
        print("Starting Marketplace Migration...")
        
        # 1. Create Wallets table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS user_wallets (
                user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                username VARCHAR(50) UNIQUE NOT NULL,
                balance DECIMAL(18, 8) DEFAULT 0.0,
                currency VARCHAR(10) DEFAULT 'X0T',
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """))
        
        # 2. Add Price to mesh_nodes if not exists
        try:
            conn.execute(text("ALTER TABLE mesh_nodes ADD COLUMN rental_price DECIMAL(10, 4) DEFAULT 0.05;"))
            conn.execute(text("ALTER TABLE mesh_nodes ADD COLUMN region VARCHAR(50) DEFAULT 'Global';"))
        except Exception as e:
            print(f"Skipping alter mesh_nodes: {e}")

        # 3. Create Rentals table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS node_rentals (
                id SERIAL PRIMARY KEY,
                user_id UUID REFERENCES user_wallets(user_id),
                node_id VARCHAR REFERENCES mesh_nodes(id),
                start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                end_time TIMESTAMP,
                status VARCHAR(20) DEFAULT 'active'
            );
        """))
        
        # 4. Seed some initial data for testing
        conn.execute(text("""
            INSERT INTO user_wallets (username, balance) 
            VALUES ('x0tta6bl4', 42.08) 
            ON CONFLICT (username) DO NOTHING;
        """))
        
        conn.commit()
        print("Marketplace Migration Completed Successfully!")

if __name__ == "__main__":
    asyncio.run(run_migration())
