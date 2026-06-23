import os
import time
import subprocess
import json
from pathlib import Path

PROJECT_ROOT = Path("/mnt/projects")
INBOX_DIR = PROJECT_ROOT / ".agent-coord" / "inbox"
ROADMAP_FILE = PROJECT_ROOT / "plans" / "ROADMAP_AGENT_QUEUE.json"

def get_pending_tasks():
    if not ROADMAP_FILE.exists(): return []
    with open(ROADMAP_FILE) as f:
        data = json.load(f)
        return [t for t in data.get("tasks", []) if t.get("status") == "ready"]

def run_swarm_cycle():
    print(f"[{time.ctime()}] Swarm cycle heartbeat...")
    
    # Проверка входящих
    for inbox in INBOX_DIR.glob("*.jsonl"):
        if os.path.getsize(inbox) > 0:
            print(f"New messages in {inbox.name}! Dispatching...")
            
    # Проверка очереди задач
    tasks = get_pending_tasks()
    if tasks:
        print(f"Found {len(tasks)} tasks ready for execution. System is primed.")

if __name__ == "__main__":
    while True:
        run_swarm_cycle()
        time.sleep(300) # 5 минут
