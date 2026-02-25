"""
Database Deadlock & Lock Fix
=============================

Cleans up potential SQLite locks and ensures fresh state for E2E tests.
"""

import sqlite3
import os

DB_PATH = "x0tta6bl4_users.db"

def fix_locks():
    if os.path.exists(DB_PATH):
        try:
            # Force remove WAL/SHM files which might cause issues
            for suffix in ["-wal", "-shm"]:
                if os.path.exists(DB_PATH + suffix):
                    os.remove(DB_PATH + suffix)
            os.remove(DB_PATH)
            print("✅ Database files removed for clean start.")
        except Exception as e:
            print(f"⚠️ Error removing DB: {e}")

if __name__ == "__main__":
    fix_locks()
