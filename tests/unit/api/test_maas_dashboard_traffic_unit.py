from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch


def _load_dashboard():
    key = "src.api.maas_dashboard"
    original_module = sys.modules.get(key)
    stubs = {
        "redis": MagicMock(),
        "src.database": MagicMock(),
        "src.api.maas_auth": MagicMock(),
        "src.resilience.advanced_patterns": MagicMock(),
        "src.core.cache": MagicMock(),
        "src.services.maas_analytics_service": MagicMock(),
    }
    if key in sys.modules:
        del sys.modules[key]
    with patch.dict("sys.modules", stubs):
        mod = importlib.import_module(key)
    if original_module is None:
        sys.modules.pop(key, None)
    else:
        sys.modules[key] = original_module
    return mod


def test_dashboard_traffic_by_bucket_sums_analytics_series(monkeypatch):
    mod = _load_dashboard()
    calls = []

    class _Analytics:
        def __init__(self, db, redis_client):
            calls.append(("init", db, redis_client))

        def get_mesh_timeseries(self, mesh_id, owner_id, time_range):
            calls.append((mesh_id, owner_id, time_range))
            if mesh_id == "mesh-a":
                return {"data": [{"traffic_mbps": 1.25}, {"traffic_mbps": "2.5"}]}
            return {"data": [{"traffic_mbps": 3.0}, {"traffic_mbps": "bad"}]}

    monkeypatch.setattr(mod, "MaaSAnalyticsService", _Analytics)

    traffic = mod._dashboard_traffic_by_bucket(
        db="db-session",
        mesh_ids=["mesh-a", "mesh-b"],
        owner_id="user-1",
        buckets=2,
    )

    assert traffic == [4.2, 2.5]
    assert calls[0] == ("init", "db-session", None)
    assert ("mesh-a", "user-1", "24h") in calls
    assert ("mesh-b", "user-1", "24h") in calls


def test_dashboard_traffic_by_bucket_returns_zeroes_without_meshes():
    mod = _load_dashboard()

    assert mod._dashboard_traffic_by_bucket("db-session", [], "user-1", buckets=3) == [
        0.0,
        0.0,
        0.0,
    ]
