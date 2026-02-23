import os
import shutil
import subprocess
from typing import Tuple

SOURCE = "/mnt/projects/recovered_photos"
TARGET = "/mnt/projects/FAMILY_FINAL_SORTED"
UNKNOWN_DATE = ("UNKNOWN", "UNKNOWN")


def get_exif_date(file_path: str) -> Tuple[str, str]:
    try:
        result = subprocess.run(
            ["exiftool", "-T", "-CreateDate", "-DateTimeOriginal", "-FileModifyDate", file_path],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return UNKNOWN_DATE

        # Выбираем первую валидную дату
        for date_str in result.stdout.strip().split("\t"):
            if date_str and date_str != "-" and len(date_str) > 4:
                parts = date_str.split(":")
                if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
                    return parts[0], parts[1]  # Year, Month
    except (subprocess.SubprocessError, OSError, ValueError):
        return UNKNOWN_DATE
    return UNKNOWN_DATE

def main():
    os.makedirs(TARGET, exist_ok=True)
    count = 0
    
    # Рекурсивно ищем все JPG
    for root, dirs, files in os.walk(SOURCE):
        for file in files:
            if file.lower().endswith(('.jpg', '.jpeg', '.png')):
                file_path = os.path.join(root, file)
                year, month = get_exif_date(file_path)
                
                dest_dir = os.path.join(TARGET, year, month)
                os.makedirs(dest_dir, exist_ok=True)
                
                shutil.copy2(file_path, os.path.join(dest_dir, file))
                count += 1
                if count % 10 == 0:
                    print(f"Recovered {count} family photos...")

if __name__ == "__main__":
    main()
