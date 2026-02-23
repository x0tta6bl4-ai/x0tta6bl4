"""Unit tests for src/utils/audit.py."""

import json
import logging
from types import SimpleNamespace
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from starlette.requests import Request

from src.utils.audit import record_audit_log, _audit


def _make_request(
    app: FastAPI,
    path: str = "/api/v1/test",
    method: str = "POST",
    client_host: Optional[str] = "192.168.1.1",
) -> Request:
    """Create a mock FastAPI request for testing."""
    raw_headers = []
    scope: Dict[str, Any] = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": method,
        "scheme": "http",
        "path": path,
        "raw_path": path.encode("latin-1"),
        "query_string": b"",
        "headers": raw_headers,
        "client": (client_host, 50000) if client_host else None,
        "server": ("testserver", 80),
        "app": app,
    }
    return Request(scope)


class _MockAuditLog:
    """Mock AuditLog model for testing."""

    def __init__(
        self,
        user_id: Optional[str] = None,
        action: Optional[str] = None,
        method: Optional[str] = None,
        path: Optional[str] = None,
        payload: Optional[str] = None,
        status_code: Optional[int] = None,
        ip_address: Optional[str] = None,
    ):
        self.user_id = user_id
        self.action = action
        self.method = method
        self.path = path
        self.payload = payload
        self.status_code = status_code
        self.ip_address = ip_address


class _MockDB:
    """Mock database session for testing."""

    def __init__(self, flush_error: Optional[Exception] = None):
        self._flush_error = flush_error
        self.added_entries: list = []
        self.flush_calls: int = 0

    def add(self, entry: Any) -> None:
        self.added_entries.append(entry)

    def flush(self) -> None:
        self.flush_calls += 1
        if self._flush_error:
            raise self._flush_error


@pytest.fixture
def app() -> FastAPI:
    return FastAPI()


@pytest.fixture
def mock_db() -> _MockDB:
    return _MockDB()


@pytest.fixture
def mock_audit_log_class():
    """Patch AuditLog with mock class."""
    with patch("src.utils.audit.AuditLog", _MockAuditLog):
        yield _MockAuditLog


class TestRecordAuditLog:
    """Tests for record_audit_log function."""

    def test_basic_audit_log_with_request(
        self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class, caplog
    ):
        """Test basic audit logging with a valid request."""
        request = _make_request(app, "/api/v1/test", "POST", "10.0.0.1")

        with caplog.at_level(logging.INFO):
            record_audit_log(
                db=mock_db,
                request=request,
                action="TEST_ACTION",
                user_id="user-123",
                payload={"key": "value"},
                status_code=200,
            )

        # Verify DB entry was added
        assert len(mock_db.added_entries) == 1
        entry = mock_db.added_entries[0]
        assert entry.user_id == "user-123"
        assert entry.action == "TEST_ACTION"
        assert entry.method == "POST"
        assert entry.path == "/api/v1/test"
        assert entry.ip_address == "10.0.0.1"
        assert entry.status_code == 200
        assert json.loads(entry.payload) == {"key": "value"}

        # Verify flush was called (not commit)
        assert mock_db.flush_calls == 1

        # Verify logging
        assert "AUDIT TEST_ACTION" in caplog.text

    def test_audit_log_with_none_request(
        self, mock_db: _MockDB, mock_audit_log_class, caplog
    ):
        """Test audit logging when request is None (background task)."""
        with caplog.at_level(logging.INFO):
            record_audit_log(
                db=mock_db,
                request=None,
                action="BACKGROUND_TASK",
                user_id="user-456",
                status_code=200,
            )

        assert len(mock_db.added_entries) == 1
        entry = mock_db.added_entries[0]
        # Note: Starlette Request with None scope may have INTERNAL method
        # The important thing is that ip_address is "unknown" when request is None
        assert entry.ip_address == "unknown"
        assert mock_db.flush_calls == 1

    def test_audit_log_with_no_client(
        self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class, caplog
    ):
        """Test audit logging when request has no client (IP unknown)."""
        request = _make_request(app, "/api/v1/test", "GET", client_host=None)

        with caplog.at_level(logging.INFO):
            record_audit_log(
                db=mock_db,
                request=request,
                action="NO_CLIENT_TEST",
                user_id="user-789",
            )

        entry = mock_db.added_entries[0]
        assert entry.ip_address == "unknown"
        assert entry.method == "GET"

    def test_audit_log_without_payload(
        self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class
    ):
        """Test audit logging without payload."""
        request = _make_request(app)

        record_audit_log(
            db=mock_db,
            request=request,
            action="NO_PAYLOAD",
            user_id="user-000",
        )

        entry = mock_db.added_entries[0]
        assert entry.payload is None

    def test_audit_log_handles_flush_error_gracefully(
        self, app: FastAPI, mock_audit_log_class, caplog
    ):
        """Test that flush errors are caught and logged, not raised."""
        mock_db = _MockDB(flush_error=RuntimeError("DB connection lost"))
        request = _make_request(app)

        with caplog.at_level(logging.ERROR):
            # Should not raise
            record_audit_log(
                db=mock_db,
                request=request,
                action="ERROR_TEST",
                user_id="user-err",
            )

        # Verify error was logged
        assert "Failed to record audit log" in caplog.text
        assert "DB connection lost" in caplog.text

        # Entry was added but flush failed
        assert len(mock_db.added_entries) == 1
        assert mock_db.flush_calls == 1

    def test_audit_log_with_complex_payload(
        self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class
    ):
        """Test audit logging with nested payload."""
        request = _make_request(app)
        complex_payload = {
            "nested": {"key": "value"},
            "list": [1, 2, 3],
            "unicode": "привет мир",
        }

        record_audit_log(
            db=mock_db,
            request=request,
            action="COMPLEX_PAYLOAD",
            payload=complex_payload,
        )

        entry = mock_db.added_entries[0]
        parsed = json.loads(entry.payload)
        assert parsed == complex_payload
        assert parsed["unicode"] == "привет мир"


class TestAuditShorthand:
    """Tests for _audit shorthand function."""

    def test_shorthand_calls_record_audit_log(
        self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class
    ):
        """Test that _audit correctly forwards to record_audit_log."""
        request = _make_request(app)

        _audit(
            db=mock_db,
            request=request,
            action="SHORTHAND_TEST",
            user_id="user-short",
            payload={"test": True},
            status_code=201,
        )

        assert len(mock_db.added_entries) == 1
        entry = mock_db.added_entries[0]
        assert entry.action == "SHORTHAND_TEST"
        assert entry.user_id == "user-short"
        assert entry.status_code == 201


class TestEdgeCases:
    """Edge case tests for audit module."""

    def test_empty_action_string(self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class):
        """Test with empty action string."""
        request = _make_request(app)

        record_audit_log(db=mock_db, request=request, action="")

        entry = mock_db.added_entries[0]
        assert entry.action == ""

    def test_none_user_id(self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class):
        """Test with None user_id (anonymous action)."""
        request = _make_request(app)

        record_audit_log(
            db=mock_db,
            request=request,
            action="ANONYMOUS_ACTION",
            user_id=None,
        )

        entry = mock_db.added_entries[0]
        assert entry.user_id is None

    def test_none_status_code(self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class):
        """Test with None status_code."""
        request = _make_request(app)

        record_audit_log(
            db=mock_db,
            request=request,
            action="NO_STATUS",
            status_code=None,
        )

        entry = mock_db.added_entries[0]
        assert entry.status_code is None

    def test_unicode_in_path(self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class):
        """Test with unicode characters in path."""
        # Use utf-8 encoding for unicode path
        unicode_path = "/api/тест/путь"
        raw_headers = []
        scope: Dict[str, Any] = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": unicode_path,
            "raw_path": unicode_path.encode("utf-8"),
            "query_string": b"",
            "headers": raw_headers,
            "client": ("192.168.1.1", 50000),
            "server": ("testserver", 80),
            "app": app,
        }
        request = Request(scope)

        record_audit_log(
            db=mock_db,
            request=request,
            action="UNICODE_PATH",
        )

        entry = mock_db.added_entries[0]
        assert entry.path == unicode_path

    def test_very_long_action_name(self, app: FastAPI, mock_db: _MockDB, mock_audit_log_class):
        """Test with very long action name."""
        request = _make_request(app)
        long_action = "A" * 500

        record_audit_log(
            db=mock_db,
            request=request,
            action=long_action,
        )

        entry = mock_db.added_entries[0]
        assert entry.action == long_action
