"""
Repository Pattern Implementation for x0tta6bl4
Provides abstraction layer for database operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, Type, TypeVar

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

# Import models
try:
    from src.database import License, Payment, Session, User

    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False


T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository for database operations.

    Provides common CRUD operations and can be extended
    for specific entity types.
    """

    def __init__(self, db: Session):
        """
        Initialize repository with database session.

        Args:
            db: SQLAlchemy session
        """
        self.db = db

    @abstractmethod
    def get_by_id(self, id: int) -> Optional[T]:
        """
        Get entity by ID.

        Args:
            id: Entity ID

        Returns:
            Entity or None if not found
        """
        pass

    @abstractmethod
    def get_all(self, skip: int = 0, limit: int = 100) -> List[T]:
        """
        Get all entities with pagination.

        Args:
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of entities
        """
        pass

    @abstractmethod
    def create(self, entity: T) -> T:
        """
        Create new entity.

        Args:
            entity: Entity to create

        Returns:
            Created entity
        """
        pass

    @abstractmethod
    def update(self, id: int, **kwargs) -> Optional[T]:
        """
        Update entity by ID.

        Args:
            id: Entity ID
            **kwargs: Fields to update

        Returns:
            Updated entity or None if not found
        """
        pass

    @abstractmethod
    def delete(self, id: int) -> bool:
        """
        Delete entity by ID.

        Args:
            id: Entity ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def count(self) -> int:
        """
        Count all entities.

        Returns:
            Number of entities
        """
        pass


class UserRepository(BaseRepository[User]):
    """Repository for User entity operations."""

    def get_by_id(self, id: int) -> Optional[User]:
        """Get user by ID."""
        return self.db.query(User).filter(User.id == id).first()

    def get_by_email(self, email: str) -> Optional[User]:
        """Get user by email."""
        return self.db.query(User).filter(User.email == email).first()

    def get_by_username(self, username: str) -> Optional[User]:
        """Get user by username."""
        return self.db.query(User).filter(User.username == username).first()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all users with pagination."""
        return self.db.query(User).offset(skip).limit(limit).all()

    def get_active_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all active users."""
        return (
            self.db.query(User)
            .filter(User.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_admin_users(self, skip: int = 0, limit: int = 100) -> List[User]:
        """Get all admin users."""
        return (
            self.db.query(User)
            .filter(User.is_admin == True)
            .offset(skip)
            .limit(limit)
            .all()
        )

    def create(self, entity: User) -> User:
        """Create new user."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: int, **kwargs) -> Optional[User]:
        """Update user by ID."""
        user = self.get_by_id(id)
        if user:
            for key, value in kwargs.items():
                if hasattr(user, key):
                    setattr(user, key, value)
            self.db.commit()
            self.db.refresh(user)
        return user

    def delete(self, id: int) -> bool:
        """Delete user by ID."""
        user = self.get_by_id(id)
        if user:
            self.db.delete(user)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """Count all users."""
        return self.db.query(func.count(User.id)).scalar()

    def count_active(self) -> int:
        """Count active users."""
        return (
            self.db.query(func.count(User.id)).filter(User.is_active == True).scalar()
        )


class SessionRepository(BaseRepository[Session]):
    """Repository for Session entity operations."""

    def get_by_id(self, id: int) -> Optional[Session]:
        """Get session by ID."""
        return self.db.query(Session).filter(Session.id == id).first()

    def get_by_token(self, token: str) -> Optional[Session]:
        """Get session by token."""
        return self.db.query(Session).filter(Session.session_token == token).first()

    def get_by_user_id(self, user_id: int, active_only: bool = True) -> List[Session]:
        """Get all sessions for a user."""
        query = self.db.query(Session).filter(Session.user_id == user_id)
        if active_only:
            query = query.filter(Session.is_active == True)
        return query.all()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Session]:
        """Get all sessions with pagination."""
        return self.db.query(Session).offset(skip).limit(limit).all()

    def create(self, entity: Session) -> Session:
        """Create new session."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: int, **kwargs) -> Optional[Session]:
        """Update session by ID."""
        session = self.get_by_id(id)
        if session:
            for key, value in kwargs.items():
                if hasattr(session, key):
                    setattr(session, key, value)
            self.db.commit()
            self.db.refresh(session)
        return session

    def delete(self, id: int) -> bool:
        """Delete session by ID."""
        session = self.get_by_id(id)
        if session:
            self.db.delete(session)
            self.db.commit()
            return True
        return False

    def delete_by_user_id(self, user_id: int) -> int:
        """Delete all sessions for a user."""
        count = self.db.query(Session).filter(Session.user_id == user_id).count()
        self.db.query(Session).filter(Session.user_id == user_id).delete()
        self.db.commit()
        return count

    def delete_expired(self) -> int:
        """Delete all expired sessions."""
        now = datetime.utcnow()
        count = self.db.query(Session).filter(Session.expires_at < now).count()
        self.db.query(Session).filter(Session.expires_at < now).delete()
        self.db.commit()
        return count

    def count(self) -> int:
        """Count all sessions."""
        return self.db.query(func.count(Session.id)).scalar()

    def count_active(self) -> int:
        """Count active sessions."""
        return (
            self.db.query(func.count(Session.id))
            .filter(Session.is_active == True)
            .scalar()
        )


class PaymentRepository(BaseRepository[Payment]):
    """Repository for Payment entity operations."""

    def get_by_id(self, id: int) -> Optional[Payment]:
        """Get payment by ID."""
        return self.db.query(Payment).filter(Payment.id == id).first()

    def get_by_user_id(
        self, user_id: int, skip: int = 0, limit: int = 100
    ) -> List[Payment]:
        """Get all payments for a user."""
        return (
            self.db.query(Payment)
            .filter(Payment.user_id == user_id)
            .order_by(Payment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_by_status(
        self, status: str, skip: int = 0, limit: int = 100
    ) -> List[Payment]:
        """Get payments by status."""
        return (
            self.db.query(Payment)
            .filter(Payment.status == status)
            .order_by(Payment.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[Payment]:
        """Get all payments with pagination."""
        return self.db.query(Payment).offset(skip).limit(limit).all()

    def create(self, entity: Payment) -> Payment:
        """Create new payment."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: int, **kwargs) -> Optional[Payment]:
        """Update payment by ID."""
        payment = self.get_by_id(id)
        if payment:
            for key, value in kwargs.items():
                if hasattr(payment, key):
                    setattr(payment, key, value)
            self.db.commit()
            self.db.refresh(payment)
        return payment

    def delete(self, id: int) -> bool:
        """Delete payment by ID."""
        payment = self.get_by_id(id)
        if payment:
            self.db.delete(payment)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """Count all payments."""
        return self.db.query(func.count(Payment.id)).scalar()

    def count_by_user_id(self, user_id: int) -> int:
        """Count payments for a user."""
        return (
            self.db.query(func.count(Payment.id))
            .filter(Payment.user_id == user_id)
            .scalar()
        )

    def get_total_amount(self, user_id: Optional[int] = None) -> float:
        """Get total payment amount."""
        query = self.db.query(func.sum(Payment.amount))
        if user_id is not None:
            query = query.filter(Payment.user_id == user_id)
        result = query.scalar()
        return float(result) if result else 0.0


class LicenseRepository(BaseRepository[License]):
    """Repository for License entity operations."""

    def get_by_id(self, id: int) -> Optional[License]:
        """Get license by ID."""
        return self.db.query(License).filter(License.id == id).first()

    def get_by_key(self, key: str) -> Optional[License]:
        """Get license by key."""
        return self.db.query(License).filter(License.license_key == key).first()

    def get_by_user_id(self, user_id: int, active_only: bool = True) -> List[License]:
        """Get all licenses for a user."""
        query = self.db.query(License).filter(License.user_id == user_id)
        if active_only:
            query = query.filter(License.is_active == True)
        return query.all()

    def get_all(self, skip: int = 0, limit: int = 100) -> List[License]:
        """Get all licenses with pagination."""
        return self.db.query(License).offset(skip).limit(limit).all()

    def create(self, entity: License) -> License:
        """Create new license."""
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: int, **kwargs) -> Optional[License]:
        """Update license by ID."""
        license = self.get_by_id(id)
        if license:
            for key, value in kwargs.items():
                if hasattr(license, key):
                    setattr(license, key, value)
            self.db.commit()
            self.db.refresh(license)
        return license

    def delete(self, id: int) -> bool:
        """Delete license by ID."""
        license = self.get_by_id(id)
        if license:
            self.db.delete(license)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        """Count all licenses."""
        return self.db.query(func.count(License.id)).scalar()

    def count_active(self) -> int:
        """Count active licenses."""
        return (
            self.db.query(func.count(License.id))
            .filter(License.is_active == True)
            .scalar()
        )

    def get_expired(self) -> List[License]:
        """Get all expired licenses."""
        now = datetime.utcnow()
        return self.db.query(License).filter(License.expires_at < now).all()

    def deactivate_expired(self) -> int:
        """Deactivate all expired licenses."""
        now = datetime.utcnow()
        count = (
            self.db.query(License)
            .filter(License.expires_at < now, License.is_active == True)
            .count()
        )

        self.db.query(License).filter(
            License.expires_at < now, License.is_active == True
        ).update({"is_active": False})

        self.db.commit()
        return count


# Repository factory function
def get_repository(
    repository_class: Type[BaseRepository], db: Session
) -> BaseRepository:
    """
    Factory function to create repository instance.

    Args:
        repository_class: Repository class to instantiate
        db: Database session

    Returns:
        Repository instance
    """
    return repository_class(db)
