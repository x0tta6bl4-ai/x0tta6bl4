"""Unit tests for marketplace fail-closed DB write guard."""

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.maas_marketplace import _ensure_write_db_ready


def test_ensure_write_db_ready_accepts_session_like_object():
    db = SimpleNamespace(query=lambda *_args, **_kwargs: None, commit=lambda: None)
    _ensure_write_db_ready(db)


def test_ensure_write_db_ready_raises_503_and_marks_degraded():
    request = SimpleNamespace(state=SimpleNamespace())

    with pytest.raises(HTTPException) as exc:
        _ensure_write_db_ready({}, request=request)

    assert exc.value.status_code == 503
    assert "database" in request.state.degraded_dependencies
