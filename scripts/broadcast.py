import sqlite3
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv("/opt/ghost-access-bot/shared/.env")
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DB_PATH = os.environ.get("GHOST_ACCESS_DB_PATH", "/opt/ghost-access-bot/shared/x0tta6bl4.db")

msg = """⚠️ **Важное техническое обновление** ⚠️

Уважаемые пользователи, мы провели чистку и оптимизацию конфигураций для повышения стабильности. Старые нерабочие запасные конфигурации были удалены.

🔄 **Пожалуйста, обновите подписку в вашем приложении (v2rayN, v2rayNG, Streisand, Shadowrocket и т.д.).**
После обновления в списке останутся только стабильные и рабочие серверы.

Спасибо, что остаетесь с нами!
"""

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()
cursor.execute("SELECT user_id FROM users WHERE expires_at > CURRENT_TIMESTAMP OR expires_at IS NULL")
users = [r[0] for r in cursor.fetchall()]

print(f"Sending message to {len(users)} users...")

success = 0
for uid in users:
    resp = requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        json={"chat_id": uid, "text": msg, "parse_mode": "Markdown"}
    )
    if resp.status_code == 200:
        success += 1
    else:
        print(f"Failed for {uid}: {resp.text}")
    time.sleep(0.05)

print(f"Successfully sent to {success} users.")
