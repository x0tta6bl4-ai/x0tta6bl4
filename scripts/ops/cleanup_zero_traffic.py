#!/usr/bin/env python3
import sqlite3
import json
import os
import sys

DB_PATH = "/etc/x-ui/x-ui.db"

def cleanup():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # 1. Get emails with zero traffic
    cursor.execute("SELECT email FROM client_traffics WHERE up = 0 AND down = 0 AND total = 0")
    zero_traffic_emails = [row['email'] for row in cursor.fetchall()]
    
    if not zero_traffic_emails:
        print("No zero-traffic clients found.")
        conn.close()
        return

    print(f"Found {len(zero_traffic_emails)} zero-traffic clients.")

    # 2. Update inbounds settings
    cursor.execute("SELECT id, settings FROM inbounds")
    inbounds = cursor.fetchall()
    
    removed_count = 0
    for inbound in inbounds:
        inbound_id = inbound['id']
        settings = json.loads(inbound['settings'])
        clients = settings.get("clients", [])
        
        new_clients = [c for c in clients if c.get("email") not in zero_traffic_emails]
        
        if len(new_clients) != len(clients):
            diff = len(clients) - len(new_clients)
            print(f"Removing {diff} clients from inbound {inbound_id}")
            settings["clients"] = new_clients
            cursor.execute("UPDATE inbounds SET settings = ? WHERE id = ?", (json.dumps(settings, ensure_ascii=False), inbound_id))
            removed_count += diff

    # 3. Delete from client_traffics
    cursor.execute("DELETE FROM client_traffics WHERE up = 0 AND down = 0 AND total = 0")
    
    conn.commit()
    conn.close()
    print(f"Cleaned up {removed_count} entries from inbounds and {len(zero_traffic_emails)} from client_traffics.")

if __name__ == "__main__":
    cleanup()
