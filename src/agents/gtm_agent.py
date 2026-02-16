import asyncio
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import func

from src.dao.token import MeshToken
from src.database import License, Payment, SessionLocal, User
from src.monitoring.production_monitoring import get_production_monitor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("GTM-Agent")


class GTMAgent:
    """
    Go-To-Market Agent for x0tta6bl4.
    Monitors sales, registrations, and conversion metrics.
    """

    def __init__(
        self, bot_token: Optional[str] = None, report_chat_id: Optional[str] = None
    ):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.report_chat_id = report_chat_id or os.getenv("ADMIN_CHAT_ID")
        self.db = SessionLocal()
        self.monitor = get_production_monitor()
        self.token = (
            MeshToken()
        )  # In real app, this should be accessed from a global manager

    def get_kpi_stats(self) -> Dict[str, Any]:
        """Fetch current KPI from database."""
        try:
            total_users = self.db.query(func.count(User.id)).scalar()
            total_payments = self.db.query(func.count(Payment.id)).scalar()
            total_revenue = self.db.query(func.sum(Payment.amount)).scalar() or 0
            active_licenses = (
                self.db.query(func.count(License.token))
                .filter(License.is_active == True)
                .scalar()
            )

            # New users in last 24h
            day_ago = datetime.utcnow() - timedelta(days=1)
            new_users_24h = (
                self.db.query(func.count(User.id))
                .filter(User.created_at >= day_ago)
                .scalar()
            )

            # Expiring licenses in next 48h
            soon = datetime.utcnow() + timedelta(days=2)
            expiring_soon = (
                self.db.query(func.count(License.token))
                .filter(
                    License.is_active == True,
                    License.expires_at <= soon,
                    License.expires_at >= datetime.utcnow(),
                )
                .scalar()
            )

            # Conversion rate
            conversion_rate = (
                (total_payments / total_users * 100) if total_users > 0 else 0
            )

            # Get DAO stats
            dao_summary = self.token.get_dao_summary()

            return {
                "total_users": total_users,
                "new_users_24h": new_users_24h,
                "total_payments": total_payments,
                "total_revenue": total_revenue,
                "active_licenses": active_licenses,
                "expiring_soon": expiring_soon,
                "conversion_rate": round(conversion_rate, 2),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "dao_stats": dao_summary,
            }
        except Exception as e:
            logger.error(f"Error fetching KPI: {e}")
            return {}

    def format_report(self, stats: Dict[str, Any]) -> str:
        """Format stats into a readable Telegram message."""
        if not stats:
            return "❌ Ошибка при получении статистики."

        return (
            f"📊 *X0TTA6BL4 GTM REPORT*\n"
            f"_{stats['timestamp']}_\n\n"
            f"👤 *Пользователи:* {stats['total_users']} (+{stats['new_users_24h']} за 24ч)\n"
            f"🎫 *Активные лицензии:* {stats['active_licenses']}\n"
            f"⚠️ *Истекают скоро:* {stats.get('expiring_soon', 0)} (в ближ. 48ч)\n"
            f"💳 *Платежи:* {stats['total_payments']}\n"
            f"💰 *Выручка:* {stats['total_revenue']} RUB\n"
            f"📈 *Конверсия:* {stats['conversion_rate']}%\n\n"
            f"🏛 *DAO ECONOMY (X0T):*\n"
            f"🥩 *В стейке:* {stats['dao_stats']['total_staked']} X0T\n"
            f"👥 *Стейкеры:* {stats['dao_stats']['active_stakers']}\n"
            f"🤝 *Рефералы:* {stats['dao_stats'].get('total_referrals', 0)}\n"
            f"💸 *Распределено:* {stats['dao_stats']['distributed_x0t']} X0T\n\n"
            f"🚀 [MVP Status: ACTIVE]"
        )

    async def send_to_telegram(self, message: str):
        """Send message via Telegram Bot API."""
        if not self.bot_token or not self.report_chat_id:
            logger.warning("Telegram configuration missing. Skipping send.")
            print(f"\n--- DRY RUN REPORT ---\n{message}\n----------------------")
            return

        import requests

        url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
        payload = {
            "chat_id": self.report_chat_id,
            "text": message,
            "parse_mode": "Markdown",
        }
        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            logger.info("Report sent to Telegram successfully.")
        except Exception as e:
            logger.error(f"Failed to send Telegram report: {e}")

    async def run_monitoring_loop(self, interval_seconds: int = 3600):
        """Main loop for periodic reporting."""
        logger.info(f"GTM Agent started. Interval: {interval_seconds}s")
        while True:
            stats = self.get_kpi_stats()
            # Record metrics to Prometheus
            if stats:
                self.monitor.record_gtm_stats(stats)

            report = self.format_report(stats)
            await self.send_to_telegram(report)
            await asyncio.sleep(interval_seconds)


if __name__ == "__main__":
    agent = GTMAgent()
    # For one-off manual run:
    stats = agent.get_kpi_stats()
    print(agent.format_report(stats))
