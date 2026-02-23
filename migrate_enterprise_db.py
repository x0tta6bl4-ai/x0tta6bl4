
import sqlite3
db_path = "x0tta6bl4_enterprise.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()
try:
    cursor.execute("ALTER TABLE mesh_nodes ADD COLUMN last_seen DATETIME")
    print("✅ Added last_seen to mesh_nodes in enterprise DB")
except sqlite3.OperationalError as e:
    print(f"ℹ️ {e}")
conn.commit()
conn.close()
