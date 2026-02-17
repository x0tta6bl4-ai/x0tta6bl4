from __future__ import annotations

import builtins
import runpy
from types import SimpleNamespace
from pathlib import Path

import pytest

import src.repositories.base as mod


class _Field:
    def __init__(self, name: str):
        self.name = name

    def __eq__(self, other):
        return ("eq", self.name, other)

    def __lt__(self, other):
        return ("lt", self.name, other)

    def desc(self):
        return ("desc", self.name)


class _Func:
    @staticmethod
    def count(arg):
        return ("count", arg)

    @staticmethod
    def sum(arg):
        return ("sum", arg)


class _User:
    id = _Field("id")
    email = _Field("email")
    username = _Field("username")
    is_active = _Field("is_active")
    is_admin = _Field("is_admin")


class _SessionModel:
    id = _Field("id")
    session_token = _Field("session_token")
    user_id = _Field("user_id")
    is_active = _Field("is_active")
    expires_at = _Field("expires_at")


class _Payment:
    id = _Field("id")
    user_id = _Field("user_id")
    status = _Field("status")
    amount = _Field("amount")
    created_at = _Field("created_at")


class _License:
    id = _Field("id")
    license_key = _Field("license_key")
    user_id = _Field("user_id")
    is_active = _Field("is_active")
    expires_at = _Field("expires_at")


class _Query:
    def __init__(self, db):
        self.db = db
        self.filters = []
        self.offset_value = None
        self.limit_value = None
        self.order_by_value = None

    def filter(self, *conditions):
        self.filters.extend(conditions)
        return self

    def offset(self, value):
        self.offset_value = value
        return self

    def limit(self, value):
        self.limit_value = value
        return self

    def order_by(self, value):
        self.order_by_value = value
        return self

    def all(self):
        return self.db.all_result

    def first(self):
        return self.db.first_result

    def count(self):
        return self.db.count_result

    def scalar(self):
        return self.db.scalar_result

    def delete(self):
        self.db.query_delete_calls += 1
        return None

    def update(self, values):
        self.db.query_updates.append(values)
        return None


class _DB:
    def __init__(self):
        self.first_result = None
        self.all_result = []
        self.count_result = 0
        self.scalar_result = 0

        self.queries = []
        self.added = []
        self.deleted = []
        self.refreshed = []
        self.commits = 0
        self.query_delete_calls = 0
        self.query_updates = []

    def query(self, *_args, **_kwargs):
        q = _Query(self)
        self.queries.append(q)
        return q

    def add(self, entity):
        self.added.append(entity)

    def commit(self):
        self.commits += 1

    def refresh(self, entity):
        self.refreshed.append(entity)

    def delete(self, entity):
        self.deleted.append(entity)


def _patch_models(monkeypatch):
    monkeypatch.setattr(mod, "func", _Func())
    monkeypatch.setattr(mod, "User", _User)
    monkeypatch.setattr(mod, "Session", _SessionModel)
    monkeypatch.setattr(mod, "Payment", _Payment)
    monkeypatch.setattr(mod, "License", _License)


def test_user_repository_methods(monkeypatch):
    _patch_models(monkeypatch)

    db = _DB()
    repo = mod.UserRepository(db)

    user = SimpleNamespace(id=1, email="a@b.c", username="u1", is_active=True, is_admin=False)
    db.first_result = user
    db.all_result = [user]

    assert repo.get_by_id(1) is user
    assert repo.get_by_email("a@b.c") is user
    assert repo.get_by_username("u1") is user
    assert repo.get_all(skip=2, limit=3) == [user]
    assert repo.get_active_users() == [user]
    assert repo.get_admin_users() == [user]

    assert repo.create(user) is user
    assert db.added[-1] is user

    updated = repo.update(1, email="new@b.c", missing="x")
    assert updated is user
    assert user.email == "new@b.c"
    assert not hasattr(user, "missing")

    assert repo.delete(1) is True
    assert db.deleted[-1] is user

    db.first_result = None
    assert repo.update(1, email="x") is None
    assert repo.delete(1) is False

    db.scalar_result = 5
    assert repo.count() == 5
    assert repo.count_active() == 5


def test_session_repository_methods(monkeypatch):
    _patch_models(monkeypatch)

    db = _DB()
    repo = mod.SessionRepository(db)

    session = SimpleNamespace(
        id=1,
        session_token="tok",
        user_id=7,
        is_active=True,
        expires_at=0,
    )

    db.first_result = session
    db.all_result = [session]

    assert repo.get_by_id(1) is session
    assert repo.get_by_token("tok") is session
    assert repo.get_by_user_id(7, active_only=True) == [session]
    assert repo.get_by_user_id(7, active_only=False) == [session]
    assert repo.get_all(skip=1, limit=2) == [session]

    assert repo.create(session) is session
    assert repo.update(1, session_token="new") is session
    assert session.session_token == "new"
    assert repo.delete(1) is True

    db.first_result = None
    assert repo.update(1, session_token="x") is None
    assert repo.delete(1) is False

    db.count_result = 2
    assert repo.delete_by_user_id(7) == 2
    assert repo.delete_expired() == 2

    db.scalar_result = 9
    assert repo.count() == 9
    assert repo.count_active() == 9


def test_payment_repository_methods(monkeypatch):
    _patch_models(monkeypatch)

    db = _DB()
    repo = mod.PaymentRepository(db)

    payment = SimpleNamespace(id=1, user_id=7, status="ok", amount=12.5, created_at=0)
    db.first_result = payment
    db.all_result = [payment]

    assert repo.get_by_id(1) is payment
    assert repo.get_by_user_id(7, skip=1, limit=3) == [payment]
    assert repo.get_by_status("ok", skip=1, limit=3) == [payment]
    assert repo.get_all(skip=1, limit=3) == [payment]

    assert repo.create(payment) is payment
    assert repo.update(1, status="done") is payment
    assert payment.status == "done"
    assert repo.delete(1) is True

    db.first_result = None
    assert repo.update(1, status="x") is None
    assert repo.delete(1) is False

    db.scalar_result = 4
    assert repo.count() == 4
    assert repo.count_by_user_id(7) == 4

    db.scalar_result = 123.4
    assert repo.get_total_amount() == 123.4
    assert repo.get_total_amount(user_id=7) == 123.4

    db.scalar_result = None
    assert repo.get_total_amount() == 0.0


def test_license_repository_methods_and_factory(monkeypatch):
    _patch_models(monkeypatch)

    db = _DB()
    repo = mod.LicenseRepository(db)

    lic = SimpleNamespace(
        id=1,
        license_key="LIC-1",
        user_id=7,
        is_active=True,
        expires_at=0,
    )

    db.first_result = lic
    db.all_result = [lic]

    assert repo.get_by_id(1) is lic
    assert repo.get_by_key("LIC-1") is lic
    assert repo.get_by_user_id(7, active_only=True) == [lic]
    assert repo.get_by_user_id(7, active_only=False) == [lic]
    assert repo.get_all(skip=3, limit=4) == [lic]

    assert repo.create(lic) is lic
    assert repo.update(1, is_active=False) is lic
    assert lic.is_active is False
    assert repo.delete(1) is True

    db.first_result = None
    assert repo.update(1, is_active=True) is None
    assert repo.delete(1) is False

    db.scalar_result = 11
    assert repo.count() == 11
    assert repo.count_active() == 11

    db.all_result = [lic]
    assert repo.get_expired() == [lic]

    db.count_result = 6
    assert repo.deactivate_expired() == 6
    assert db.query_updates[-1] == {"is_active": False}

    factory_repo = mod.get_repository(mod.LicenseRepository, db)
    assert isinstance(factory_repo, mod.LicenseRepository)
    assert factory_repo.db is db


def test_base_repository_abstract_method_bodies_are_noop():
    assert mod.BaseRepository.get_by_id(None, 1) is None
    assert mod.BaseRepository.get_all(None) is None
    assert mod.BaseRepository.create(None, object()) is None
    assert mod.BaseRepository.update(None, 1) is None
    assert mod.BaseRepository.delete(None, 1) is None
    assert mod.BaseRepository.count(None) is None


def test_importerror_branch_marks_models_unavailable(monkeypatch):
    path = Path(__file__).resolve().parents[2] / "src" / "repositories" / "base.py"
    original_import = builtins.__import__

    def _fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "src.database":
            raise ImportError("forced missing src.database")
        return original_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", _fake_import)
    with pytest.raises(NameError):
        runpy.run_path(str(path))
