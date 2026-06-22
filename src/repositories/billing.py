"""
Repository implementations for billing and audit database models.
"""

from datetime import datetime
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import AuditLog, BillingWebhookEvent, Invoice
from src.repositories.base import BaseRepository


class InvoiceRepository(BaseRepository[Invoice]):
    """Repository for Invoice entity operations."""

    def get_by_id(self, id: str) -> Optional[Invoice]:
        return self.db.query(Invoice).filter(Invoice.id == id).first()

    def get_by_user(self, user_id: str) -> List[Invoice]:
        return (
            self.db.query(Invoice)
            .filter(Invoice.user_id == user_id)
            .order_by(Invoice.created_at.desc())
            .all()
        )

    def get_by_status(self, status: str) -> List[Invoice]:
        return (
            self.db.query(Invoice)
            .filter(Invoice.status == status)
            .order_by(Invoice.created_at.desc())
            .all()
        )

    def get_total_paid_amount(self) -> float:
        result = self.db.query(func.coalesce(func.sum(Invoice.total_amount), 0.0)).filter(
            Invoice.status == "paid"
        ).scalar()
        return float(result)

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Invoice]:
        return self.db.query(Invoice).offset(skip).limit(limit).all()

    def create(self, entity: Invoice) -> Invoice:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: str, **kwargs) -> Optional[Invoice]:
        entity = self.get_by_id(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
        return entity

    def delete(self, id: str) -> bool:
        entity = self.get_by_id(id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        return self.db.query(func.count(Invoice.id)).scalar()


class AuditLogRepository:
    """Repository for AuditLog entity operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_recent(self, limit: int = 20, user_id: Optional[str] = None) -> List[AuditLog]:
        query = self.db.query(AuditLog)
        if user_id:
            query = query.filter(AuditLog.user_id == user_id)
        return query.order_by(AuditLog.created_at.desc()).limit(limit).all()

    def get_by_correlation(self, correlation_id: str) -> List[AuditLog]:
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.correlation_id == correlation_id)
            .order_by(AuditLog.created_at.desc())
            .all()
        )

    def create(
        self,
        action: str,
        user_id: Optional[str] = None,
        details: Optional[dict] = None,
        correlation_id: Optional[str] = None,
    ) -> AuditLog:
        log = AuditLog(
            action=action,
            user_id=user_id,
            details=str(details) if details else None,
            correlation_id=correlation_id,
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def count(self) -> int:
        return self.db.query(func.count(AuditLog.id)).scalar()


class BillingWebhookEventRepository:
    """Repository for BillingWebhookEvent entity operations."""

    def __init__(self, db: Session):
        self.db = db

    def get_by_stripe_id(self, stripe_event_id: str) -> Optional[BillingWebhookEvent]:
        return (
            self.db.query(BillingWebhookEvent)
            .filter(BillingWebhookEvent.stripe_event_id == stripe_event_id)
            .first()
        )

    def exists(self, stripe_event_id: str) -> bool:
        return self.get_by_stripe_id(stripe_event_id) is not None

    def create(self, stripe_event_id: str, event_type: str) -> BillingWebhookEvent:
        event = BillingWebhookEvent(
            stripe_event_id=stripe_event_id,
            event_type=event_type,
        )
        self.db.add(event)
        self.db.commit()
        self.db.refresh(event)
        return event
