import os
import subprocess
import logging
import time
from datetime import datetime
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler("/mnt/projects/recovery_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("RecoveryAgent")

class PhotoRecoveryAgent:
    """
    Автономный агент для глубокого восстановления фотографий из NTFS/EXT4.
    """
    def __init__(self, device="/dev/sdb1", output_dir="/mnt/projects/recovered_photos/agent_out"):
        self.device = device
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.log_file = "/mnt/projects/recovery_agent.log"

    def run_command(self, cmd, timeout=3600):
        """Запуск системной команды с логированием."""
        logger.info(f"Выполнение команды: {' '.join(cmd)}")
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            output = []
            for line in process.stdout:
                line = line.strip()
                if line:
                    logger.info(line)
                    output.append(line)
            
            process.wait(timeout=timeout)
            return "
".join(output)
        except Exception as e:
            logger.error(f"Ошибка при выполнении команды: {e}")
            return str(e)

    def start_recovery(self):
        """Запуск процесса восстановления."""
        logger.info("--- СТАРТ ПРОЦЕССА ВОССТАНОВЛЕНИЯ ---")
        
        # 1. Поиск крупных удаленных файлов через ntfsundelete
        logger.info("Шаг 1: Поиск крупных удаленных файлов через ntfsundelete...")
        ntfs_cmd = ["sudo", "ntfsundelete", "-f", "-s", self.device, "-S", "1000000-500000000", "-p", "100"]
        self.run_command(ntfs_cmd)

        # 2. Запуск PhotoRec в пакетном режиме (если установлен)
        logger.info("Шаг 2: Глубокое сканирование через PhotoRec...")
        photorec_cmd = [
            "sudo", "photorec", 
            "/d", str(self.output_dir), 
            "/cmd", self.device, 
            "partition_none,search,file_jpg,file_png,file_webp,free"
        ]
        # PhotoRec может работать долго, запускаем с большим таймаутом
        self.run_command(photorec_cmd, timeout=86400)

        logger.info("--- ПРОЦЕСС ВОССТАНОВЛЕНИЯ ЗАВЕРШЕН ---")

if __name__ == "__main__":
    agent = PhotoRecoveryAgent()
    agent.start_recovery()
