"""
Unit tests for src/api/middleware/auth.py
Covers admin token verification, error handling, and AdminAuthMiddleware.
"""

import os

import pytest
from fastapi import Header, HTTPException, status

from src.api.middleware.auth import (AdminAuthMiddleware, get_current_admin,
                                     verify_admin_token)


def test_verify_admin_token_success(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    # Should not raise
    AdminAuthMiddleware()  # init ok
    AdminAuthMiddleware().verify("testtoken")
    # Function version
    try:
        verify_admin_token(x_admin_token="testtoken")
    except Exception:
        pytest.fail("verify_admin_token raised unexpectedly!")


def test_verify_admin_token_missing_env(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(HTTPException) as exc:
        verify_admin_token(x_admin_token="testtoken")
    assert exc.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    with pytest.raises(RuntimeError):
        AdminAuthMiddleware()


def test_verify_admin_token_missing_header(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    with pytest.raises(HTTPException) as exc:
        verify_admin_token(x_admin_token=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_verify_admin_token_invalid(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    with pytest.raises(HTTPException) as exc:
        verify_admin_token(x_admin_token="wrong")
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_get_current_admin_success(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    result = get_current_admin(x_admin_token="testtoken")
    assert result == "admin"


def test_get_current_admin_invalid(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    result = get_current_admin(x_admin_token="wrong")
    assert result is None


def test_get_current_admin_missing_env(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(HTTPException):
        get_current_admin(x_admin_token="testtoken")


def test_admin_auth_middleware_call_valid(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    mw = AdminAuthMiddleware()
    # Should not raise
    mw.__call__(x_admin_token="testtoken")


def test_admin_auth_middleware_call_invalid(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    mw = AdminAuthMiddleware()
    with pytest.raises(HTTPException) as exc:
        mw.__call__(x_admin_token="wrong")
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED


def test_admin_auth_middleware_call_missing(monkeypatch):
    monkeypatch.setenv("ADMIN_TOKEN", "testtoken")
    mw = AdminAuthMiddleware()
    with pytest.raises(HTTPException) as exc:
        mw.__call__(x_admin_token=None)
    assert exc.value.status_code == status.HTTP_401_UNAUTHORIZED
