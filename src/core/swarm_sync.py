import json
import os
import time

STATE_FILE = "/mnt/projects/swarm_state.json"
ARCHIVE_ROOT = "/mnt/projects/СЕМЕЙНЫЙ_АРХИВ_ИТОГ"

def get_state():
    with open(STATE_FILE, 'r') as f:
        return json.load(f)

def save_state(state):
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)

def sync_recovery(state):
    # Узнаем сколько файлов реально спасено
    try:
        count = sum(
            1 for entry in os.scandir(ARCHIVE_ROOT)
            if not entry.name.startswith(".")
        )
        organized = 0
        root_abs = os.path.abspath(ARCHIVE_ROOT)
        for dirpath, _dirnames, filenames in os.walk(ARCHIVE_ROOT):
            if os.path.abspath(dirpath) == root_abs:
                continue
            organized += len(filenames)

        recovery_stream = state.setdefault("recovery_stream", {})
        recovery_stream["files_rescued"] = count
        recovery_stream["organized_count"] = organized
    except (FileNotFoundError, PermissionError, OSError, TypeError, ValueError):
        pass

def sync_tech_to_business(state):
    # Если в тех-стриме готов гибридный роутинг, сообщаем бизнесу, что пора обновлять офер
    if state["technical_stream"]["routing_mode"] == "hybrid_ml":
        state["business_stream"]["offer_ready"] = True

def main():
    while True:
        try:
            state = get_state()
            sync_recovery(state)
            sync_tech_to_business(state)
            save_state(state)
            # Выводим краткий отчет в лог
            print(f"Sync: {state['recovery_stream']['files_rescued']} rescued, {state['recovery_stream']['organized_count']} organized. Tech stable.")
        except Exception as e:
            print(f"Sync error: {e}")
        time.sleep(30)

if __name__ == "__main__":
    main()
