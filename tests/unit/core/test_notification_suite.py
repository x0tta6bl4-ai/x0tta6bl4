import pathlib
from importlib.machinery import SourceFileLoader

# Load current module path (legacy hyphenated filename was removed).
_notif_path = pathlib.Path("src/core/notification_suite.py")
notif = SourceFileLoader("notification_suite_orig", str(_notif_path)).load_module()


def test_pods_all_running_true():
    pods = {
        "items": [
            {
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                }
            },
            {
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "True"}],
                }
            },
        ]
    }
    assert notif.pods_all_running(pods) is True


def test_pods_all_running_false_missing_ready():
    pods = {
        "items": [
            {
                "status": {
                    "phase": "Running",
                    "conditions": [{"type": "Ready", "status": "False"}],
                }
            },
        ]
    }
    assert notif.pods_all_running(pods) is False


def test_send_email_failure(monkeypatch):
    # Force socket connection failure by using unreachable host name
    rc = notif.send_email(
        "Subject", "Body", ["user@example.com"], "invalid.local.domain", 25
    )
    assert rc == 1


def test_send_slack_error_redacts_webhook(monkeypatch, capsys):
    class FakeRequest:
        pass

    def fake_urlopen(req, timeout=5):
        raise RuntimeError(
            "boom https://hooks.slack.com/services/T000/B000/raw-secret token=raw-token"
        )

    monkeypatch.setattr(notif.urllib.request, "urlopen", fake_urlopen)
    rc = notif.send_slack("https://hooks.slack.test/AAA", "Hello")
    assert rc == 1
    output = capsys.readouterr().out
    assert "raw-secret" not in output
    assert "raw-token" not in output
    assert "https://hooks.slack.com/services/[REDACTED]" in output
    assert "token=[REDACTED]" in output
