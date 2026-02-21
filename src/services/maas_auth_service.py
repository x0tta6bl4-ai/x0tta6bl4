"""Shared authentication service for MaaS API modules."""

from __future__ import annotations

from datetime import datetime
import uuid
from typing import Callable

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.api.maas_auth_models import UserLoginRequest, UserRegisterRequest
from src.database import User
from src.security.password_auth import hash_password, verify_password


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

    def register(self, db: Session, req: UserRegisterRequest) -> User:
        normalized_email = self._normalize_email(req.email)
        if not normalized_email:
            raise HTTPException(status_code=400, detail="Email is required")

        if db.query(User).filter(func.lower(User.email) == normalized_email).first():
            raise HTTPException(status_code=400, detail="Email already registered")

        user = User(
            id=str(uuid.uuid4()),
            email=normalized_email,
            password_hash=hash_password(req.password),
            full_name=req.full_name,
            company=req.company,
            api_key=self._api_key_factory(),
            role="user",
            plan=self._default_plan,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    def login(self, db: Session, req: UserLoginRequest) -> str:
        normalized_email = self._normalize_email(req.email)
        user = db.query(User).filter(func.lower(User.email) == normalized_email).first()
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        valid, should_rehash = verify_password(req.password, user.password_hash)
        if not valid and user.password_hash == req.password:
            # Backward-compatible migration path for legacy plaintext rows.
            valid = True
            should_rehash = True
        if not valid:
            raise HTTPException(status_code=401, detail="Invalid credentials")

        if should_rehash:
            user.password_hash = hash_password(req.password)
            db.commit()

        return user.api_key

    def rotate_api_key(self, db: Session, user: User) -> tuple[str, datetime]:
        """Rotate user's API key and return (new_key, rotated_at)."""
        new_key = self._api_key_factory()
        rotated_at = datetime.utcnow()
        user.api_key = new_key
        db.commit()
        return new_key, rotated_at
