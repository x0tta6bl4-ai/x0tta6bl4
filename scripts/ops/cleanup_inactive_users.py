#!/usr/bin/env python3
import sqlite3
import json
import os
import time

DB_PATH = "/etc/x-ui/x-ui.db"
# 60 days in milliseconds
INACTIVE_THRESHOLD_MS = 60 * 24 * 3600 * 1000
NOW_MS = int(time.time() * 1000)

def cleanup_inactive():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Identify emails to delete:
    # - last_online is more than 60 days ago
    # - OR last_online is 0 but created_at (if exists in JSON) is more than 60 days ago? 
    # Actually, let's stick to the explicit last_online check for safety.
    
    threshold_time = NOW_MS - INACTIVE_THRESHOLD_MS
    cursor.execute("SELECT email, last_online FROM client_traffics WHERE last_online > 0 AND last_online < ?", (threshold_time,))
    inactive_clients = cursor.fetchall()
    
    inactive_emails = [row['email'] for row in inactive_clients]
    
    if not inactive_emails:
        print("No inactive clients found (using 60-day threshold).")
        conn.close()
        return

    print(f"Found {len(inactive_emails)} clients inactive for > 2 months.")
    for email in inactive_emails:
        print(f"  - {email}")

    # 2. Remove from inbounds settings
    cursor.execute("SELECT id, settings FROM inbounds")
    inbounds = cursor.fetchall()
    
    removed_count = 0
    for inbound in inbounds:
        inbound_id = inbound['id']
        settings = json.loads(inbound['settings'])
        clients = settings.get("clients", [])
        
        new_clients = [c for c in clients if c.get("email") not in inactive_emails]
        
        if len(new_clients) != len(clients):
            diff = len(clients) - len(new_clients)
            print(f"Removing {diff} inactive clients from inbound {inbound_id}")
            settings["clients"] = new_clients
            cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", (json.dumps(settings, ensure_ascii=False), inbound_id))
            removed_count += diff

    # 3. Delete from client_traffics
    for email in inactive_emails:
        cursor.execute("DELETE FROM client_traffics WHERE email = ?", (email,))
    
    conn.commit()
    conn.close()
    print(f"✅ Successfully cleaned up {removed_count} inactive client entries.")

if __name__ == "__main__":
    cleanup_inactive()
