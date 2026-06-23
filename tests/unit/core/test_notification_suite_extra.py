from importlib.machinery import SourceFileLoader

notif = SourceFileLoader(
    "notification_suite_orig", "src/core/notification_suite.py"
).load_module()
notif_libx0t = SourceFileLoader(
    "notification_suite_libx0t", "src/libx0t/core/notification_suite.py"
).load_module()


class DummyResp:
    def __init__(self, status=200, body=b"OK"):
        self.status = status
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_send_slack_success(monkeypatch):
    def fake_urlopen(req, timeout=5):
        return DummyResp(status=201, body=b'{"ok":true}')

    monkeypatch.setattr(notif.urllib.request, "urlopen", fake_urlopen)
    rc = notif.send_slack("https://hooks.slack.test/AAA", "Hello World")
    assert rc == 0


def test_kubectl_get_pods_error(monkeypatch):
    class FakeResult:
        def __init__(self):
            self.returncode = 1
            self.stderr = "error"
            self.stdout = ""

    monkeypatch.setattr(notif.subprocess, "run", lambda *a, **k: FakeResult())
    pods = notif.kubectl_get_pods("ns1", "app=x")
    assert pods is None


def test_kubectl_get_pods_error_redacts_secret_text(monkeypatch, capsys):
    class FakeResult:
        def __init__(self):
            self.returncode = 1
            self.stderr = "failed token=raw-token api_key:raw-api-key"
            self.stdout = ""

    monkeypatch.setattr(notif.subprocess, "run", lambda *a, **k: FakeResult())
    pods = notif.kubectl_get_pods("ns1", "app=x")

    assert pods is None
    output = capsys.readouterr().out
    assert "raw-token" not in output
    assert "raw-api-key" not in output
    assert "token=[REDACTED]" in output
    assert "api_key:[REDACTED]" in output


def test_libx0t_notification_redactor_masks_webhooks_and_tokens():
    text = notif_libx0t._redact_sensitive_text(
        "url=https://hooks.slack.com/services/T000/B000/raw-secret token=raw-token"
    )

    assert "raw-secret" not in text
    assert "raw-token" not in text
    assert "https://hooks.slack.com/services/[REDACTED]" in text
    assert "token=[REDACTED]" in text


def test_watch_timeout(monkeypatch):
    # Make kubectl always return pods not running
    fake_pods = {"items": [{"status": {"phase": "Pending", "conditions": []}}]}

    def fake_get(namespace, label=None):
        return fake_pods

    monkeypatch.setattr(notif, "kubectl_get_pods", fake_get)
    # Use tiny timeout/interval
    rc = notif.watch("ns1", ["app=x"], timeout=1, interval=0)
    assert rc == 2
