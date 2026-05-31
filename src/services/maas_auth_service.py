"""Shared authentication service for MaaS API modules."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.maas_auth_models import UserLoginRequest, UserRegisterRequest
from src.api.maas_security import ApiKeyManager
from src.database import User
from src.security.password_auth import hash_password, verify_password


def find_user_by_api_key(db: Session, api_key: str | None) -> User | None:
    if not api_key:
        return None
    api_key = api_key.strip()
    if not api_key:
        return None
    return db.query(User).filter(User.api_key_hash == ApiKeyManager.hash_key(api_key)).first()


class MaaSAuthService:
    """Reusable register/login logic for MaaS auth endpoints."""

    def __init__(
        self,
        *,
        api_key_factory: Callable[[], str],
        default_plan: str,
    ) -> None:
        self._api_key_factory = api_key_factory
        self._default_plan = default_plan

    @staticmethod
    def _normalize_email(email: str) -> str:
        return (email or "").strip().lower()

    @staticmethod
    def issued_api_key(user: User) -> str | None:
        return getattr(user, "_issued_api_key", None)

    def issue_api_key(self, db: Session, user: User, *, commit: bool = True) -> str:
        api_key = self._api_key_factory()
        user.api_key = None
        user.api_key_hash = ApiKeyManager.hash_key(api_key)
        user._issued_api_key = api_key
        if commit:
            db.commit()
        return api_key

    def register(self, db: Session, req: UserRegisterRequest) -> User:
        normalized_email = self._normalize_email(req.email)
        if not normalized_email:
            raise HTTPException(status_code=400, detail="Email is required")

        if db.query(User).filter(func.lower(User.email) == normalized_email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        api_key = self._api_key_factory()
        user = User(
            id=str(uuid.uuid4()),
            email=normalized_email,
            password_hash=hash_password(req.password),
            full_name=req.full_name,
            company=req.company,
            api_key=None,
            api_key_hash=ApiKeyManager.hash_key(api_key),
            role="user",
            plan=self._default_plan,
        )
        user._issued_api_key = api_key
        db.add(user)
        db.commit()
        db.refresh(user)
        user._issued_api_key = api_key
        return user

    def login(self, db: Session, req: UserLoginRequest) -> str:
        normalized_email = self._normalize_email(req.email)
        user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        valid, should_rehash = verify_password(req.password, user.password_hash)
        # NOTE: plaintext fallback removed — CVE: accounts with non-bcrypt hashes
        # must go through password reset; they do not grant login access.
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if should_rehash:
            user.password_hash = hash_password(req.password)

        return self.issue_api_key(db, user)

    def rotate_api_key(self, db: Session, user: User) -> tuple[str, datetime]:
        """Rotate user's API key and return (new_key, rotated_at)."""
        rotated_at = datetime.utcnow()
        new_key = self.issue_api_key(db, user)
        return new_key, rotated_at
