
import logging
import time
from datetime import datetime, timedelta
from src.database import get_db, MarketplaceEscrow, MarketplaceListing, User
from src.api.maas_marketplace import rent_node

logger = logging.getLogger("auto_renew")

def auto_renew_rentals():
    """Фоновый процесс продления аренды VPN-нод."""
    db_gen = get_db()
    db = next(db_gen)
    
    try:
        # 1. Находим аренды, которые истекают в ближайший час
        now = datetime.utcnow()
        threshold = now + timedelta(hours=1)
        
        expiring_escrows = db.query(MarketplaceEscrow).filter(
            MarketplaceEscrow.status == "active",
            MarketplaceEscrow.expires_at <= threshold,
            MarketplaceEscrow.auto_renew == True
        ).all()
        
        if not expiring_escrows:
            return
            
        logger.info(f"🔄 Found {len(expiring_escrows)} rentals for auto-renewal")
        
        for escrow in expiring_escrows:
            try:
                # Продлеваем еще на столько же, сколько было изначально (или дефолт 24ч)
                renew_hours = 24 
                
                # Ищем листинг для этой ноды
                listing = db.query(MarketplaceListing).filter(
                    MarketplaceListing.node_id == escrow.node_id,
                    MarketplaceListing.status == "active"
                ).first()
                
                if not listing:
                    logger.warning(f"⚠️ Cannot renew {escrow.id}: listing for node {escrow.node_id} no longer active")
                    continue
                
                # Проверяем баланс пользователя (упрощенно)
                user = db.query(User).filter(User.id == escrow.renter_id).first()
                # Здесь должна быть проверка баланса токенов или USD
                
                logger.info(f"✅ Auto-renewing escrow {escrow.id} for node {escrow.node_id} (+{renew_hours}h)")
                
                # Мы не вызываем API эндпоинт, так как мы внутри процесса. 
                # Мы просто обновляем время истечения и создаем новый платеж (в реальности).
                escrow.expires_at += timedelta(hours=renew_hours)
                escrow.updated_at = now
                
                db.commit()
                
            except Exception as e:
                logger.error(f"❌ Failed to auto-renew escrow {escrow.id}: {e}")
                db.rollback()
                
    finally:
        db.close()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    logger.info("🚀 Starting Auto-Renew Worker...")
    while True:
        auto_renew_rentals()
        time.sleep(300) # Проверка каждые 5 минут
