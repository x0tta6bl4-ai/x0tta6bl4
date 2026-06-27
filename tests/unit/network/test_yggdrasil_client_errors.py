import subprocess
from unittest.mock import MagicMock

from src.coordination.events import EventBus
from src.network import yggdrasil_client


def test_get_yggdrasil_peers_called_process_error(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    mock_run = MagicMock(
        side_effect=subprocess.CalledProcessError(
            returncode=1, cmd="yggdrasilctl getPeers", stderr="boom"
        )
    )
    monkeypatch.setattr(subprocess, "run", mock_run)
    res = yggdrasil_client.get_yggdrasil_peers(event_bus=bus)
    assert res["status"] == "error"
    assert res["count"] == 0
    assert "non-zero exit status 1" in res["error"]


def test_get_yggdrasil_status_timeout(monkeypatch, tmp_path):
    bus = EventBus(project_root=str(tmp_path))
    mock_run = MagicMock(
        side_effect=subprocess.TimeoutExpired(cmd="yggdrasilctl getSelf", timeout=5)
    )
    monkeypatch.setattr(subprocess, "run", mock_run)
    res = yggdrasil_client.get_yggdrasil_status(event_bus=bus)
    assert res["status"] == "offline"
    assert "timed out" in res["error"].lower()
