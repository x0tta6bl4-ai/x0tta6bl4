
import sqlite3
import os

db_path = "x0tta6bl4.db"

def migrate():
    if not os.path.exists(db_path):
        print(f"Database {db_path} not found. Skipping manual migration.")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Add last_seen to mesh_nodes if missing
    try:
        cursor.execute("ALTER TABLE mesh_nodes ADD COLUMN last_seen DATETIME")
        print("✅ Added last_seen to mesh_nodes")
    except sqlite3.OperationalError:
        print("ℹ️ Column last_seen already exists in mesh_nodes")

    # 2. Add renter_id and mesh_id to marketplace_listings if missing
    for col in ["renter_id", "mesh_id"]:
        try:
            cursor.execute(f"ALTER TABLE marketplace_listings ADD COLUMN {col} VARCHAR")
            print(f"✅ Added {col} to marketplace_listings")
        except sqlite3.OperationalError:
            print(f"ℹ️ Column {col} already exists in marketplace_listings")

    conn.commit()
    conn.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
