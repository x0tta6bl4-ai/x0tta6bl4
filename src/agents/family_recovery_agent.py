import os
import subprocess
import json
import time
from pathlib import Path

# Конфигурация
SOURCE_BASE = "/mnt/projects/recovered_photos"
TARGET_BASE = "/mnt/projects/ГЛАВНЫЙ_СЕМЕЙНЫЙ_АРХИВ"
STATE_FILE = "/mnt/projects/recovery_progress_state.json"
LOG_FILE = "/mnt/projects/FAMILY_RECOVERY_LIVE.log"

def log(message):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {message}
")
    print(message)

def organize_directory(dir_path):
    # Команда для сортировки фото и видео по датам EXIF
    # -r: рекурсивно
    # -d: формат папок (Год/Месяц)
    # -ext: расширения
    # -overwrite_original: не создавать копии
    cmd = [
        "exiftool", "-r", "-overwrite_original", "-q",
        "-d", f"{TARGET_BASE}/%Y/%m",
        "-directory<CreateDate", "-directory<DateTimeOriginal", "-directory<FileModifyDate",
        dir_path,
        "-ext", "jpg", "-ext", "jpeg", "-ext", "png", "-ext", "heic",
        "-ext", "mp4", "-ext", "mov", "-ext", "3gp", "-ext", "avi"
    ]
    try:
        subprocess.run(cmd, check=True)
        return True
    except Exception as e:
        log(f"Error processing {dir_path}: {e}")
        return False

def main():
    if not os.path.exists(TARGET_BASE):
        os.makedirs(TARGET_BASE, exist_ok=True)
    
    # Загрузка состояния
    processed_dirs = set()
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                processed_dirs = set(json.load(f))
        except:
            pass

    # Поиск всех папок PhotoRec
    all_dirs = sorted([
        os.path.join(SOURCE_BASE, d) 
        for d in os.listdir(SOURCE_BASE) 
        if d.startswith("photorec_out.") and os.path.isdir(os.path.join(SOURCE_BASE, d))
    ])

    log(f"Starting recovery. Found {len(all_dirs)} total directories.")
    
    count = 0
    for d in all_dirs:
        d_name = os.path.basename(d)
        if d_name in processed_dirs:
            continue
            
        log(f"Processing batch {d_name}...")
        if organize_directory(d):
            processed_dirs.add(d_name)
            # Сохраняем прогресс после каждой папки
            with open(STATE_FILE, "w") as f:
                json.dump(list(processed_dirs), f)
            count += 1
            if count % 10 == 0:
                log(f"Progress: {len(processed_dirs)}/{len(all_dirs)} directories organized.")

    log("--- RECOVERY COMPLETE! All family photos are in ГЛАВНЫЙ_СЕМЕЙНЫЙ_АРХИВ ---")

if __name__ == "__main__":
    main()
