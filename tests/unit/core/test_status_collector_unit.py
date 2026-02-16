"""Unit tests for status collector and health aggregation."""

from src.core import status_collector


class _FakeSystemMetrics:
    def __init__(self, cpu=10, mem=20, disk=30, packet_loss=0):
        self.cpu = cpu
        self.mem = mem
        self.disk = disk
        self.packet_loss = packet_loss

    def get_cpu_metrics(self):
        return {"percent": self.cpu}

    def get_memory_metrics(self):
        return {"percent": self.mem}

    def get_disk_metrics(self):
        return {"percent": self.disk}

    def get_network_metrics(self):
        return {"packet_loss_percent": self.packet_loss}

    def get_process_count(self):
        return {"total": 10, "running": 3}

    def get_uptime_seconds(self):
        return 12.34


class _FakeMeshMetrics:
    def __init__(self, peers=1):
        self.connected_peers = peers

    def update_from_batman_adv(self):
        return None

    def get_metrics(self):
        return {"connected_peers": self.connected_peers}


def test_get_status_data_singleton():
    status_collector._status_data = None
    s1 = status_collector.get_status_data()
    s2 = status_collector.get_status_data()
    assert s1 is s2


def test_status_data_healthy_status():
    s = status_collector.StatusData()
    s.system_metrics = _FakeSystemMetrics(cpu=20, mem=30, disk=40, packet_loss=1)
    s.mesh_metrics = _FakeMeshMetrics(peers=2)

    data = s.get_status()
    assert data["status"] == "healthy"
    assert data["health"]["mesh_connected"] is True


def test_status_data_warning_status():
    s = status_collector.StatusData()
    s.system_metrics = _FakeSystemMetrics(cpu=85, mem=50, disk=40, packet_loss=1)
    s.mesh_metrics = _FakeMeshMetrics(peers=1)

    data = s.get_status()
    assert data["status"] == "warning"


def test_status_data_critical_status():
    s = status_collector.StatusData()
    s.system_metrics = _FakeSystemMetrics(cpu=95, mem=50, disk=40, packet_loss=1)
    s.mesh_metrics = _FakeMeshMetrics(peers=0)

    data = s.get_status()
    assert data["status"] == "critical"
    assert data["health"]["mesh_connected"] is False
