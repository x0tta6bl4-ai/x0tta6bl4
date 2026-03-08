"""Unit tests for src/utils/notifications.py — Notifier."""

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.utils.notifications import Notifier, notifier


# ---------------------------------------------------------------------------
# Notifier.__init__
# ---------------------------------------------------------------------------


class TestNotifierInit:
    def test_explicit_webhook_url(self):
        n = Notifier(webhook_url="https://hooks.example.com/abc")
        assert n.webhook_url == "https://hooks.example.com/abc"

    def test_falls_back_to_env_var(self):
        with patch.dict(os.environ, {"WEBHOOK_URL": "https://env.example.com/hook"}):
            n = Notifier()
            assert n.webhook_url == "https://env.example.com/hook"

    def test_none_when_no_url_and_no_env(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WEBHOOK_URL", None)
            n = Notifier()
            assert n.webhook_url is None


# ---------------------------------------------------------------------------
# Notifier.send — no webhook configured
# ---------------------------------------------------------------------------


class TestNotifierSendNoWebhook:
    def test_send_with_no_url_does_not_raise(self):
        n = Notifier(webhook_url=None)
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WEBHOOK_URL", None)
            n2 = Notifier()
            n2.send("Title", "Body")  # should not raise

    def test_send_with_no_url_logs_warning(self, caplog):
        import logging
        n = Notifier(webhook_url=None)
        with caplog.at_level(logging.WARNING, logger="src.utils.notifications"):
            n.send("Test", "msg")
        assert any("No webhook URL" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# Notifier.send — with webhook
# ---------------------------------------------------------------------------


class TestNotifierSendWithWebhook:
    def _make_response(self, status=200):
        resp = MagicMock()
        resp.raise_for_status = MagicMock()
        resp.status_code = status
        return resp

    def test_sends_post_request(self):
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("Alert", "Something happened")
        mock_post.assert_called_once()

    def test_payload_contains_title_and_message(self):
        import json
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("My Title", "My Message", color="#ff0000")
        call_kwargs = mock_post.call_args
        sent_data = json.loads(call_kwargs.kwargs.get("data", call_kwargs[1].get("data", "{}")))
        attachment = sent_data["attachments"][0]
        assert attachment["title"] == "My Title"
        assert attachment["text"] == "My Message"
        assert attachment["color"] == "#ff0000"

    def test_content_type_header_set(self):
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("T", "M")
        headers = mock_post.call_args.kwargs.get("headers", mock_post.call_args[1].get("headers"))
        assert headers["Content-Type"] == "application/json"

    def test_timeout_is_set(self):
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("T", "M")
        timeout = mock_post.call_args.kwargs.get("timeout", mock_post.call_args[1].get("timeout"))
        assert timeout == 5

    def test_discord_webhook_adds_username(self):
        import json
        n = Notifier(webhook_url="https://discord.com/api/webhooks/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("T", "M")
        sent_data = json.loads(mock_post.call_args.kwargs.get("data", mock_post.call_args[1].get("data", "{}")))
        assert sent_data.get("username") == "X0T Bot"

    def test_non_discord_webhook_no_username(self):
        import json
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("T", "M")
        sent_data = json.loads(mock_post.call_args.kwargs.get("data", mock_post.call_args[1].get("data", "{}")))
        assert "username" not in sent_data

    def test_http_error_does_not_raise(self):
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 500")
        with patch("src.utils.notifications.requests.post", return_value=mock_resp):
            n.send("T", "M")  # should not propagate

    def test_connection_error_does_not_raise(self):
        import requests as req
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        with patch("src.utils.notifications.requests.post", side_effect=req.exceptions.ConnectionError("refused")):
            n.send("T", "M")  # should not propagate

    def test_footer_contains_project_name(self):
        import json
        n = Notifier(webhook_url="https://hooks.slack.com/test")
        mock_resp = self._make_response()
        with patch("src.utils.notifications.requests.post", return_value=mock_resp) as mock_post:
            n.send("T", "M")
        sent_data = json.loads(mock_post.call_args.kwargs.get("data", mock_post.call_args[1].get("data", "{}")))
        assert "x0tta6bl4" in sent_data["attachments"][0]["footer"]


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------


def test_global_notifier_is_notifier_instance():
    assert isinstance(notifier, Notifier)
