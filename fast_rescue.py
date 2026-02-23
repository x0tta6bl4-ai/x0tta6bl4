#!/usr/bin/env python3
import os
import shutil
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SOURCE = "/mnt/projects/recovered_photos"
TARGET = "/mnt/projects/СЕМЕЙНЫЙ_АРХИВ_ИТОГ"

def rescue():
    # Получаем список папок
    dirs = sorted([d for d in os.listdir(SOURCE) if d.startswith("photorec_out.")])
    print(f"Total dirs to process: {len(dirs)}")
    
    for d_name in dirs:
        src_dir = os.path.join(SOURCE, d_name)
        # Если в папке есть файл .done, мы её уже обработали
        if os.path.exists(os.path.join(src_dir, ".done")):
            continue
            
        print(f"Rescuing from {d_name}...")
        for file in os.listdir(src_dir):
            if file.lower().endswith((".jpg", ".jpeg", ".png")):
                src_path = os.path.join(src_dir, file)
                # Пропускаем совсем мелкие мусорные файлы (иконки)
                if os.path.getsize(src_path) > 50000: 
                    # Новое имя, чтобы не было конфликтов (имя_папки + имя_файла)
                    dst_path = os.path.join(TARGET, f"{d_name}_{file}")
                    try:
                        shutil.copy2(src_path, dst_path)
                    except (IOError, OSError) as e:
                        logger.warning(f"Failed to copy {src_path}: {e}")
        
        # Помечаем папку как готовую
        Path(os.path.join(src_dir, ".done")).touch()

if __name__ == "__main__":
    rescue()
