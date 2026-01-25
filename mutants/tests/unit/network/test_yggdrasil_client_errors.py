import subprocess
from src.network import yggdrasil_client
from unittest.mock import MagicMock


def test_get_yggdrasil_peers_called_process_error(monkeypatch):
    mock_run = MagicMock(side_effect=subprocess.CalledProcessError(returncode=1, cmd='yggdrasilctl getPeers', stderr='boom'))
    monkeypatch.setattr(subprocess, 'run', mock_run)
    res = yggdrasil_client.get_yggdrasil_peers()
    assert res['status'] == 'error'
    assert res['count'] == 0
    assert 'boom' in res['error']


def test_get_yggdrasil_status_timeout(monkeypatch):
    mock_run = MagicMock(side_effect=subprocess.TimeoutExpired(cmd='yggdrasilctl getSelf', timeout=5))
    monkeypatch.setattr(subprocess, 'run', mock_run)
    res = yggdrasil_client.get_yggdrasil_status()
    assert res['status'] == 'error'
    assert 'timeout' in res['error'].lower()
