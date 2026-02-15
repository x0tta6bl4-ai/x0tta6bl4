import os

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from unittest.mock import MagicMock

import src.security.pqc_fallback as pqc_fallback
from src.security.pqc_fallback import PQCFallbackHandler


def test_init_sets_default_ttl() -> None:
    handler = PQCFallbackHandler()
    assert handler.fallback_ttl == 3600


def test_handle_fallback_enables_and_records_when_disabled(monkeypatch) -> None:
    calls = {"enable": 0, "record": 0}
    monkeypatch.setattr(pqc_fallback, "is_fallback_enabled", lambda: False)
    monkeypatch.setattr(
        pqc_fallback,
        "enable_fallback",
        lambda reason: calls.__setitem__("enable", calls["enable"] + 1),
    )
    monkeypatch.setattr(
        pqc_fallback,
        "record_handshake_failure",
        lambda reason: calls.__setitem__("record", calls["record"] + 1),
    )
    handler = PQCFallbackHandler()
    handler.handle_fallback("liboqs_error", "backend unavailable")
    assert calls["enable"] == 1
    assert calls["record"] == 1


def test_handle_fallback_does_not_reenable_when_already_active(monkeypatch) -> None:
    mock_enable = MagicMock()
    mock_record = MagicMock()
    monkeypatch.setattr(pqc_fallback, "is_fallback_enabled", lambda: True)
    monkeypatch.setattr(pqc_fallback, "enable_fallback", mock_enable)
    monkeypatch.setattr(pqc_fallback, "record_handshake_failure", mock_record)
    handler = PQCFallbackHandler()
    handler.handle_fallback("timeout", "slow response")
    mock_enable.assert_not_called()
    mock_record.assert_not_called()


def test_check_ttl_proxies_metric_function(monkeypatch) -> None:
    monkeypatch.setattr(pqc_fallback, "check_fallback_ttl", lambda: True)
    assert PQCFallbackHandler().check_ttl() is True
    monkeypatch.setattr(pqc_fallback, "check_fallback_ttl", lambda: False)
    assert PQCFallbackHandler().check_ttl() is False


def test_restore_normal_disables_only_if_enabled(monkeypatch) -> None:
    mock_disable = MagicMock()
    monkeypatch.setattr(pqc_fallback, "disable_fallback", mock_disable)
    monkeypatch.setattr(pqc_fallback, "is_fallback_enabled", lambda: True)
    handler = PQCFallbackHandler()
    handler.restore_normal()
    mock_disable.assert_called_once()

    mock_disable.reset_mock()
    monkeypatch.setattr(pqc_fallback, "is_fallback_enabled", lambda: False)
    handler.restore_normal()
    mock_disable.assert_not_called()
