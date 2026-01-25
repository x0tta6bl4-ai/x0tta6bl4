from importlib.machinery import SourceFileLoader
import pathlib

# Load original hyphenated script file directly
_notif_path = pathlib.Path('src/core/notification-suite.py')
notif = SourceFileLoader('notification_suite_orig', str(_notif_path)).load_module()


def test_pods_all_running_true():
    pods = {
        'items': [
            {'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}]}},
            {'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'True'}]}},
        ]
    }
    assert notif.pods_all_running(pods) is True


def test_pods_all_running_false_missing_ready():
    pods = {
        'items': [
            {'status': {'phase': 'Running', 'conditions': [{'type': 'Ready', 'status': 'False'}]}},
        ]
    }
    assert notif.pods_all_running(pods) is False


def test_send_email_failure(monkeypatch):
    # Force socket connection failure by using unreachable host name
    rc = notif.send_email('Subject', 'Body', ['user@example.com'], 'invalid.local.domain', 25)
    assert rc == 1


def test_send_slack_error(monkeypatch):
    class FakeRequest:
        pass
    def fake_urlopen(req, timeout=5):
        raise RuntimeError('boom')
    monkeypatch.setattr(notif.urllib.request, 'urlopen', fake_urlopen)
    rc = notif.send_slack('https://hooks.slack.test/AAA', 'Hello')
    assert rc == 1
