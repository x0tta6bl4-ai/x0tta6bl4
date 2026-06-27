
import sqlite3
import os

db_path = "x0tta6bl4_enterprise.db"

def check():
    if not os.path.exists(db_path):
        print(f"File {db_path} not found!")
        return
        
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(mesh_nodes)")
    cols = cursor.fetchall()
    print(f"Columns in mesh_nodes:")
    for c in cols:
        print(f"  - {c[1]} ({c[2]})")
    conn.close()

if __name__ == "__main__":
    check()
