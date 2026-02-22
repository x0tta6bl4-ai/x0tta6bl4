"""
Unit tests for MaaSAnalyticsService — x0tta6bl4
Covers: health scores, summary calculation, time-series aggregation, and ROI.
"""

import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch
from sqlalchemy import func

from src.services.maas_analytics_service import MaaSAnalyticsService, HEALTHY_THRESHOLD
from src.database import MeshNode, MeshInstance, Invoice, MarketplaceListing

class TestMaaSAnalyticsService(unittest.TestCase):
    def setUp(self):
        self.db = MagicMock()
        self.redis = MagicMock()
        self.service = MaaSAnalyticsService(self.db, self.redis)
        self.owner_id = "user-123"
        self.mesh_id = "mesh-456"

    def test_node_health_score_all_healthy(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        nodes = [
            MeshNode(id="n1", status="healthy", last_seen=now - timedelta(minutes=1)),
            MeshNode(id="n2", status="approved", last_seen=now - timedelta(minutes=4)),
        ]
        score = self.service._node_health_score(nodes)
        self.assertEqual(score, 1.0)

    def test_node_health_score_mixed(self):
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        nodes = [
            MeshNode(id="n1", status="healthy", last_seen=now - timedelta(minutes=1)),
            MeshNode(id="n2", status="offline", last_seen=now - timedelta(minutes=10)), # stale
            MeshNode(id="n3", status="approved", last_seen=None), # never seen
        ]
        score = self.service._node_health_score(nodes)
        self.assertEqual(score, 0.667)

    def test_node_health_score_legacy_online_without_last_seen(self):
        nodes = [
            MeshNode(id="n1", status="healthy", last_seen=None),
            MeshNode(id="n2", status="approved", last_seen=None),
            MeshNode(id="n3", status="offline", last_seen=None),
        ]
        score = self.service._node_health_score(nodes)
        self.assertEqual(score, 0.667)

    def test_get_mesh_summary_not_found(self):
        self.db.query().filter().first.return_value = None
        result = self.service.get_mesh_summary(self.mesh_id, self.owner_id)
        self.assertIsNone(result)

    def test_get_mesh_summary_success(self):
        # Mock MeshInstance
        instance = MeshInstance(id=self.mesh_id, owner_id=self.owner_id, pqc_enabled=True)
        self.db.query(MeshInstance).filter().first.return_value = instance
        
        # Mock Nodes
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        nodes = [MeshNode(id="n1", last_seen=now)]
        self.db.query(MeshNode).filter().all.return_value = nodes
        
        # Mock Invoices
        self.db.query(func.sum(Invoice.total_amount)).filter().scalar.return_value = 1500 # $15.00
        
        # We need func from sqlalchemy for the mock to work if it's imported
        with patch('src.services.maas_analytics_service.func') as mock_func:
            mock_func.sum.return_value = "sum_op"
            self.db.query().filter().scalar.return_value = 1500
            
            result = self.service.get_mesh_summary(self.mesh_id, self.owner_id)
            
        self.assertIsNotNone(result)
        self.assertEqual(result["cost_maas_total"], 15.0)
        self.assertEqual(result["nodes_total"], 1)
        self.assertEqual(result["nodes_online"], 1)
        self.assertTrue(result["pqc_status"])

    def test_get_mesh_summary_legacy_nodes_without_last_seen_are_online(self):
        instance = MeshInstance(id=self.mesh_id, owner_id=self.owner_id, pqc_enabled=True)
        self.db.query(MeshInstance).filter().first.return_value = instance

        nodes = [
            MeshNode(id="n1", status="healthy", last_seen=None),
            MeshNode(id="n2", status="approved", last_seen=None),
            MeshNode(id="n3", status="offline", last_seen=None),
        ]
        self.db.query(MeshNode).filter().all.return_value = nodes

        with patch('src.services.maas_analytics_service.func') as mock_func:
            mock_func.sum.return_value = "sum_op"
            self.db.query().filter().scalar.return_value = 0
            result = self.service.get_mesh_summary(self.mesh_id, self.owner_id)

        self.assertIsNotNone(result)
        self.assertEqual(result["nodes_total"], 3)
        self.assertEqual(result["nodes_online"], 2)

    def test_get_redis_telemetry_decodes_bytes_payload(self):
        redis_client = MagicMock()
        redis_client.get.return_value = b'{"traffic_mbps": 12.5, "latency_ms": 21}'
        service = MaaSAnalyticsService(self.db, redis_client)

        telemetry = service._get_redis_telemetry("node-1")
        self.assertEqual(telemetry["traffic_mbps"], 12.5)
        self.assertEqual(telemetry["latency_ms"], 21)

    def test_aggregate_realtime_telemetry_uses_numeric_values(self):
        redis_client = MagicMock()
        service = MaaSAnalyticsService(self.db, redis_client)
        redis_client.get.side_effect = [
            '{"traffic_mbps": "10.5", "latency_ms": "20"}',
            '{"traffic_mbps": 5, "latency_ms": 40}',
            '{"traffic_mbps": "bad", "latency_ms": null}',
        ]
        nodes = [
            MeshNode(id="n1", status="healthy", last_seen=None),
            MeshNode(id="n2", status="healthy", last_seen=None),
            MeshNode(id="n3", status="healthy", last_seen=None),
        ]

        aggregated = service._aggregate_realtime_telemetry(nodes)
        self.assertIsNotNone(aggregated)
        self.assertEqual(round(aggregated["traffic_mbps_total"], 1), 15.5)
        self.assertEqual(round(aggregated["latency_ms_avg"], 1), 30.0)

    def test_get_redis_telemetry_history_parses_valid_items(self):
        redis_client = MagicMock()
        redis_client.lrange.return_value = [
            '{"timestamp": "2026-02-21T12:05:00", "traffic_mbps": 12.0, "latency_ms": 21.0}',
            b'{"last_seen": "2026-02-21T12:10:00", "traffic_mbps": 8.0, "latency_ms": 19.0}',
            "not-json",
            "[]",
        ]
        service = MaaSAnalyticsService(self.db, redis_client)

        history = service._get_redis_telemetry_history("node-1", max_items=20)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["traffic_mbps"], 12.0)
        self.assertEqual(history[1]["latency_ms"], 19.0)

    def test_aggregate_hourly_telemetry_from_history_groups_by_hour(self):
        redis_client = MagicMock()
        service = MaaSAnalyticsService(self.db, redis_client)

        def _history_side_effect(node_id: str, max_items: int):
            if node_id == "n1":
                return [
                    {"timestamp": "2026-02-21T12:10:00", "traffic_mbps": 10, "latency_ms": 20},
                    {"timestamp": "2026-02-21T12:20:00", "traffic_mbps": 5, "latency_ms": 40},
                    {"timestamp": "2026-02-21T13:05:00", "traffic_mbps": 7, "latency_ms": 30},
                ]
            return [
                {"timestamp": "2026-02-21T12:40:00", "traffic_mbps": 8, "latency_ms": 50},
                {"timestamp": "2026-02-21T10:40:00", "traffic_mbps": 99, "latency_ms": 99},  # out of range
            ]

        service._get_redis_telemetry_history = MagicMock(side_effect=_history_side_effect)
        now = datetime(2026, 2, 21, 13, 30, 0)
        since = now - timedelta(hours=2)
        nodes = [MeshNode(id="n1", status="healthy"), MeshNode(id="n2", status="healthy")]

        hourly = service._aggregate_hourly_telemetry_from_history(
            nodes=nodes,
            since=since,
            now=now,
            hours_count=2,
        )
        self.assertIn("2026-02-21T12:00:00", hourly)
        self.assertIn("2026-02-21T13:00:00", hourly)
        self.assertEqual(hourly["2026-02-21T12:00:00"]["traffic_mbps_total"], 23.0)
        self.assertEqual(round(hourly["2026-02-21T12:00:00"]["latency_ms_avg"], 1), 36.7)
        self.assertEqual(hourly["2026-02-21T13:00:00"]["traffic_mbps_total"], 7.0)

    def test_get_mesh_timeseries_prefers_history_for_matching_hour(self):
        now = datetime(2026, 2, 21, 13, 30, 0)
        instance = MeshInstance(id=self.mesh_id, owner_id=self.owner_id, pqc_enabled=True)
        nodes = [MeshNode(id="n1", status="healthy", last_seen=now)]

        q_instance = MagicMock()
        q_instance.filter.return_value.first.return_value = instance

        q_nodes = MagicMock()
        q_nodes.filter.return_value.all.return_value = nodes

        q_health = MagicMock()
        q_health.filter.return_value.group_by.return_value.all.return_value = []

        q_traffic = MagicMock()
        q_traffic.join.return_value.filter.return_value.scalar.return_value = 0.0

        def _query_side_effect(*args, **kwargs):
            if args and args[0] is MeshInstance:
                return q_instance
            if args and args[0] is MeshNode:
                return q_nodes
            if args and len(args) == 2:
                return q_health
            return q_traffic

        self.db.query.side_effect = _query_side_effect
        service = MaaSAnalyticsService(self.db, self.redis)
        service._utcnow_naive = MagicMock(return_value=now)
        service._aggregate_hourly_telemetry_from_history = MagicMock(return_value={
            "2026-02-21T13:00:00": {
                "traffic_mbps_total": 55.5,
                "latency_ms_avg": 17.2,
            }
        })
        service._aggregate_realtime_telemetry = MagicMock(return_value={
            "traffic_mbps_total": 5.0,
            "latency_ms_avg": 99.0,
        })

        result = service.get_mesh_timeseries(self.mesh_id, self.owner_id, time_range="1h")
        self.assertIsNotNone(result)
        self.assertEqual(len(result["data"]), 1)
        point = result["data"][0]
        self.assertEqual(point["traffic_mbps"], 55.5)
        self.assertEqual(point["latency_ms"], 17.2)

    def test_get_marketplace_roi(self):
        listings = [
            MarketplaceListing(status="available", price_per_hour=10),
            MarketplaceListing(status="rented", price_per_hour=20),
            MarketplaceListing(status="escrow", price_per_hour=30),
        ]
        self.db.query().filter().all.return_value = listings
        
        result = self.service.get_marketplace_roi(self.mesh_id, self.owner_id)
        
        self.assertEqual(result["listings"]["total"], 3)
        self.assertEqual(result["listings"]["rented"], 1)
        self.assertEqual(result["revenue"]["hourly_cents"], 50) # 20 + 30
        self.assertEqual(result["revenue"]["hourly_usd"], 0.5)

class TestSafeFloat(unittest.TestCase):
    """Unit tests for MaaSAnalyticsService._safe_float()."""

    def test_none_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._safe_float(None))

    def test_valid_int(self):
        self.assertEqual(MaaSAnalyticsService._safe_float(42), 42.0)

    def test_valid_float(self):
        self.assertAlmostEqual(MaaSAnalyticsService._safe_float(3.14), 3.14)

    def test_valid_string(self):
        self.assertAlmostEqual(MaaSAnalyticsService._safe_float("2.5"), 2.5)

    def test_invalid_string_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._safe_float("not-a-number"))

    def test_empty_string_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._safe_float(""))

    def test_zero(self):
        self.assertEqual(MaaSAnalyticsService._safe_float(0), 0.0)


class TestParseTelemetryTimestamp(unittest.TestCase):
    """Unit tests for MaaSAnalyticsService._parse_telemetry_timestamp()."""

    def test_none_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp(""))

    def test_non_string_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp(12345))

    def test_invalid_format_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp("not-a-date"))

    def test_naive_iso_string(self):
        result = MaaSAnalyticsService._parse_telemetry_timestamp("2026-02-21T12:00:00")
        self.assertIsNotNone(result)
        self.assertEqual(result.hour, 12)
        self.assertIsNone(result.tzinfo)

    def test_z_suffix_strips_timezone(self):
        result = MaaSAnalyticsService._parse_telemetry_timestamp("2026-02-21T12:00:00Z")
        self.assertIsNotNone(result)
        self.assertIsNone(result.tzinfo)  # tz stripped to naive

    def test_tz_aware_string_strips_timezone(self):
        result = MaaSAnalyticsService._parse_telemetry_timestamp("2026-02-21T12:00:00+03:00")
        self.assertIsNotNone(result)
        self.assertIsNone(result.tzinfo)


class TestNormalizeDt(unittest.TestCase):
    """Unit tests for MaaSAnalyticsService._normalize_dt()."""

    def test_none_returns_none(self):
        self.assertIsNone(MaaSAnalyticsService._normalize_dt(None))

    def test_naive_datetime_unchanged(self):
        dt = datetime(2026, 2, 21, 12, 0, 0)
        result = MaaSAnalyticsService._normalize_dt(dt)
        self.assertEqual(result, dt)
        self.assertIsNone(result.tzinfo)

    def test_tz_aware_strips_tzinfo(self):
        dt = datetime(2026, 2, 21, 12, 0, 0, tzinfo=timezone.utc)
        result = MaaSAnalyticsService._normalize_dt(dt)
        self.assertIsNone(result.tzinfo)


class TestIsNodeOnline(unittest.TestCase):
    """Unit tests for MaaSAnalyticsService._is_node_online()."""

    def setUp(self):
        self.service = MaaSAnalyticsService(MagicMock(), None)
        self.now = datetime.now(timezone.utc).replace(tzinfo=None)

    def test_healthy_recent_is_online(self):
        node = MeshNode(status="healthy", last_seen=self.now - timedelta(minutes=2))
        self.assertTrue(self.service._is_node_online(node, now=self.now))

    def test_healthy_stale_is_offline(self):
        node = MeshNode(status="healthy", last_seen=self.now - timedelta(minutes=10))
        self.assertFalse(self.service._is_node_online(node, now=self.now))

    def test_offline_status_no_last_seen_is_offline(self):
        node = MeshNode(status="offline", last_seen=None)
        self.assertFalse(self.service._is_node_online(node, now=self.now))

    def test_offline_status_recent_still_offline(self):
        node = MeshNode(status="offline", last_seen=self.now - timedelta(minutes=1))
        self.assertFalse(self.service._is_node_online(node, now=self.now))

    def test_approved_recent_is_online(self):
        node = MeshNode(status="approved", last_seen=self.now - timedelta(minutes=3))
        self.assertTrue(self.service._is_node_online(node, now=self.now))

    def test_empty_status_recent_is_online(self):
        node = MeshNode(status="", last_seen=self.now - timedelta(minutes=1))
        self.assertTrue(self.service._is_node_online(node, now=self.now))

    def test_none_status_no_last_seen_is_online(self):
        """Legacy row: status=None + last_seen=None → treated as online."""
        node = MeshNode(status=None, last_seen=None)
        self.assertTrue(self.service._is_node_online(node, now=self.now))


class TestGetRedisTelemetry(unittest.TestCase):
    """Edge cases for _get_redis_telemetry when redis is unavailable."""

    def test_no_redis_returns_empty(self):
        """Redis client is None → _redis_ok=False → empty dict."""
        service = MaaSAnalyticsService(MagicMock(), None)
        self.assertEqual(service._get_redis_telemetry("node-1"), {})

    def test_redis_get_returns_none_gives_empty(self):
        redis_client = MagicMock()
        redis_client.get.return_value = None
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        self.assertEqual(service._get_redis_telemetry("node-1"), {})

    def test_redis_get_invalid_json_gives_empty(self):
        redis_client = MagicMock()
        redis_client.get.return_value = b"not-json{"
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry("node-1")
        self.assertEqual(result, {})


class TestGetRedisTelemetryHistory(unittest.TestCase):
    """Edge cases for _get_redis_telemetry_history."""

    def test_no_redis_returns_empty_list(self):
        service = MaaSAnalyticsService(MagicMock(), None)
        self.assertEqual(service._get_redis_telemetry_history("node-1", 10), [])

    def test_max_items_zero_returns_empty_list(self):
        redis_client = MagicMock()
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        self.assertEqual(service._get_redis_telemetry_history("node-1", 0), [])


class TestGetMeshTimeseriesEdgeCases(unittest.TestCase):
    """Edge cases for get_mesh_timeseries."""

    def test_mesh_not_found_returns_none(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.first.return_value = None
        service = MaaSAnalyticsService(db, None)
        result = service.get_mesh_timeseries("nonexistent-mesh", "user-1", "24h")
        self.assertIsNone(result)

    def test_unknown_time_range_defaults_to_24h(self):
        """Unrecognized time_range string defaults to 24 hours."""
        db = MagicMock()
        instance = MeshInstance(id="mesh-1", owner_id="user-1", pqc_enabled=False)
        db.query.return_value.filter.return_value.first.return_value = instance
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        db.query.return_value.join.return_value.filter.return_value.scalar.return_value = 0.0

        service = MaaSAnalyticsService(db, None)
        result = service.get_mesh_timeseries("mesh-1", "user-1", "unknown-range")
        self.assertIsNotNone(result)
        self.assertEqual(len(result["data"]), 24)  # defaults to 24h

    def test_7d_time_range_returns_168_points(self):
        db = MagicMock()
        instance = MeshInstance(id="mesh-1", owner_id="user-1", pqc_enabled=False)
        db.query.return_value.filter.return_value.first.return_value = instance
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.group_by.return_value.all.return_value = []
        db.query.return_value.join.return_value.filter.return_value.scalar.return_value = 0.0

        service = MaaSAnalyticsService(db, None)
        result = service.get_mesh_timeseries("mesh-1", "user-1", "7d")
        self.assertEqual(len(result["data"]), 168)


class TestGetMarketplaceRoiEdgeCases(unittest.TestCase):
    """Edge cases for get_marketplace_roi."""

    def test_empty_listings(self):
        db = MagicMock()
        db.query.return_value.filter.return_value.all.return_value = []
        service = MaaSAnalyticsService(db, None)
        result = service.get_marketplace_roi("mesh-1", "user-1")
        self.assertEqual(result["listings"]["total"], 0)
        self.assertEqual(result["revenue"]["hourly_cents"], 0)
        self.assertEqual(result["revenue"]["hourly_usd"], 0.0)

    def test_monthly_estimate_calculation(self):
        db = MagicMock()
        listings = [MarketplaceListing(status="rented", price_per_hour=100)]  # $1/hr
        db.query.return_value.filter.return_value.all.return_value = listings
        service = MaaSAnalyticsService(db, None)
        result = service.get_marketplace_roi("mesh-1", "user-1")
        # monthly = 1.00 USD/hr * 24 * 30 = 720 USD
        self.assertAlmostEqual(result["revenue"]["monthly_estimate_usd"], 720.0)

    def test_all_available_no_revenue(self):
        db = MagicMock()
        listings = [
            MarketplaceListing(status="available", price_per_hour=50),
            MarketplaceListing(status="available", price_per_hour=100),
        ]
        db.query.return_value.filter.return_value.all.return_value = listings
        service = MaaSAnalyticsService(db, None)
        result = service.get_marketplace_roi("mesh-1", "user-1")
        self.assertEqual(result["revenue"]["hourly_cents"], 0)
        self.assertEqual(result["listings"]["available"], 2)


class TestGetRedisTelemetryEdgeCases(unittest.TestCase):
    """Cover exception path in _get_redis_telemetry."""

    def test_redis_get_raises_returns_empty(self):
        """redis.get() raises an exception → logger.warning → return {}."""
        import json
        redis_client = MagicMock()
        redis_client.get.side_effect = Exception("connection refused")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry("node-exc")
        self.assertEqual(result, {})


class TestGetRedisTelemetryHistoryEdgeCases(unittest.TestCase):
    """Cover no-lrange, lrange exception, dict payload, and invalid payload paths."""

    def test_redis_without_lrange_returns_empty(self):
        """redis client without lrange attribute → return []."""
        redis_client = MagicMock(spec=[])  # object with no attributes
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry_history("node-1", 10)
        self.assertEqual(result, [])

    def test_lrange_raises_returns_empty(self):
        """redis.lrange() raises → logger.warning → return []."""
        redis_client = MagicMock()
        redis_client.lrange.side_effect = Exception("lrange error")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry_history("node-err", 5)
        self.assertEqual(result, [])

    def test_lrange_dict_payload_included(self):
        """Dict item in lrange result → parsed and included."""
        import json as _json
        redis_client = MagicMock()
        redis_client.lrange.return_value = [{"traffic_mbps": 10.0, "latency_ms": 5.0}]
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry_history("node-dict", 5)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["traffic_mbps"], 10.0)

    def test_lrange_invalid_type_skipped(self):
        """Non-str/bytes/dict item (int) in lrange → continue → skipped."""
        redis_client = MagicMock()
        redis_client.lrange.return_value = [42, None]
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry_history("node-invalid", 5)
        self.assertEqual(result, [])


class TestAggregateRealtimeTelemetryEdgeCases(unittest.TestCase):
    """Cover empty-values → None branch in _aggregate_realtime_telemetry."""

    def test_all_negative_values_returns_none(self):
        """Nodes with negative traffic AND latency → nothing appended → return None."""
        import json as _json
        redis_client = MagicMock()
        redis_client.get.return_value = _json.dumps({"traffic_mbps": -1.0, "latency_ms": -2.0})
        node = MeshNode(id="n1", mesh_id="m1", status="approved")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._aggregate_realtime_telemetry([node])
        self.assertIsNone(result)

    def test_no_nodes_returns_none(self):
        """Empty node list → return None immediately."""
        redis_client = MagicMock()
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._aggregate_realtime_telemetry([])
        self.assertIsNone(result)


class TestAggregateHourlyTelemetryEdgeCases(unittest.TestCase):
    """Cover bucket exclusion when all values are negative/invalid."""

    def test_bucket_with_no_valid_values_excluded(self):
        """Samples whose traffic AND latency are negative → bucket not in result."""
        import json as _json
        redis_client = MagicMock()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        since = now - timedelta(hours=1)
        sample = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "traffic_mbps": -5.0,
            "latency_ms": -2.0,
        }
        redis_client.lrange.return_value = [_json.dumps(sample)]
        node = MeshNode(id="n-bad", mesh_id="m1", status="approved")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._aggregate_hourly_telemetry_from_history(
            nodes=[node], since=since, now=now, hours_count=1
        )
        self.assertEqual(result, {})

    def test_timestamp_out_of_range_excluded(self):
        """Sample timestamp before 'since' → skipped (not added to buckets)."""
        import json as _json
        redis_client = MagicMock()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        since = now - timedelta(hours=1)
        # Timestamp 3 hours ago — outside the window
        old_ts = (now - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%S")
        sample = {"timestamp": old_ts, "traffic_mbps": 50.0, "latency_ms": 10.0}
        redis_client.lrange.return_value = [_json.dumps(sample)]
        node = MeshNode(id="n-old", mesh_id="m1", status="approved")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._aggregate_hourly_telemetry_from_history(
            nodes=[node], since=since, now=now, hours_count=1
        )
        self.assertEqual(result, {})


class TestGetMeshSummaryEdgeCases(unittest.TestCase):
    """Cover savings_pct=0 when no nodes (cost_aws=0)."""

    def test_savings_zero_when_no_nodes(self):
        """No nodes → cost_aws=0 → savings_pct=0.0 (no division by zero)."""
        db = MagicMock()
        instance = MeshInstance(id="mesh-1", owner_id="user-1", pqc_enabled=True)
        db.query.return_value.filter.return_value.first.return_value = instance
        db.query.return_value.filter.return_value.all.return_value = []
        db.query.return_value.filter.return_value.scalar.return_value = None
        service = MaaSAnalyticsService(db, None)
        result = service.get_mesh_summary("mesh-1", "user-1")
        self.assertIsNotNone(result)
        self.assertEqual(result["savings_pct"], 0.0)
        self.assertEqual(result["nodes_total"], 0)
        self.assertEqual(result["cost_aws_estimate"], 0.0)


class TestNodeHealthScoreEdgeCases(unittest.TestCase):
    """Cover the empty-nodes → 1.0 branch in _node_health_score."""

    def test_empty_nodes_returns_one(self):
        """_node_health_score([]) → 1.0 (line 84-85 branch)."""
        service = MaaSAnalyticsService(MagicMock(), None)
        score = service._node_health_score([])
        self.assertEqual(score, 1.0)


class TestGetRedisTelemetryHistoryBytesPath(unittest.TestCase):
    """Cover bytes-decoding path in _get_redis_telemetry_history (line 120-121)."""

    def test_bytes_items_decoded_and_parsed(self):
        """lrange returns bytes items → decoded to str → parsed as JSON."""
        import json as _json
        redis_client = MagicMock()
        payload = {"traffic_mbps": 77.7, "latency_ms": 3.3}
        redis_client.lrange.return_value = [_json.dumps(payload).encode("utf-8")]
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry_history("bytes-node", 5)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(result[0]["traffic_mbps"], 77.7)


class TestGetMeshTimeseriesRealtimePath(unittest.TestCase):
    """Cover realtime telemetry fallback path in get_mesh_timeseries (lines 291-293)."""

    def setUp(self):
        self.db = MagicMock()
        self.redis = MagicMock()
        self.mesh_id = "mesh-realtime-test"
        self.owner_id = "owner-realtime"

    def test_realtime_telemetry_used_for_current_hour_when_no_history(self):
        """When history has no bucket for the current hour, realtime telemetry is used."""
        now = datetime(2026, 2, 22, 15, 45, 0)  # fixed for reproducibility
        instance = MeshInstance(id=self.mesh_id, owner_id=self.owner_id, pqc_enabled=False)
        nodes = [MeshNode(id="n1", status="healthy", last_seen=now)]

        q_instance = MagicMock()
        q_instance.filter.return_value.first.return_value = instance
        q_nodes = MagicMock()
        q_nodes.filter.return_value.all.return_value = nodes
        q_health = MagicMock()
        q_health.filter.return_value.group_by.return_value.all.return_value = []
        q_traffic = MagicMock()
        q_traffic.join.return_value.filter.return_value.scalar.return_value = 0.0

        def _query_side_effect(*args, **kwargs):
            if args and args[0] is MeshInstance:
                return q_instance
            if args and args[0] is MeshNode:
                return q_nodes
            if args and len(args) == 2:
                return q_health
            return q_traffic

        self.db.query.side_effect = _query_side_effect
        service = MaaSAnalyticsService(self.db, self.redis)
        service._utcnow_naive = MagicMock(return_value=now)
        # No history buckets at all
        service._aggregate_hourly_telemetry_from_history = MagicMock(return_value={})
        # Realtime has data
        service._aggregate_realtime_telemetry = MagicMock(return_value={
            "traffic_mbps_total": 42.0,
            "latency_ms_avg": 8.5,
        })

        result = service.get_mesh_timeseries(self.mesh_id, self.owner_id, time_range="1h")
        self.assertIsNotNone(result)
        # The single data point should use realtime telemetry
        point = result["data"][0]
        self.assertEqual(point["traffic_mbps"], 42.0)
        self.assertEqual(point["latency_ms"], 8.5)


class TestAggregateHourlyBucketPartialData(unittest.TestCase):
    """Cover bucket with only latency (no valid traffic) → traffic_mbps_total is 0.0."""

    def test_bucket_only_latency_valid_traffic_zero(self):
        """Negative traffic + positive latency → bucket included with traffic=0.0."""
        import json as _json
        redis_client = MagicMock()
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        since = now - timedelta(hours=1)
        sample = {
            "timestamp": now.strftime("%Y-%m-%dT%H:%M:%S"),
            "traffic_mbps": -1.0,   # negative → excluded from traffic list
            "latency_ms": 12.5,     # positive → included in latency list
        }
        redis_client.lrange.return_value = [_json.dumps(sample)]
        node = MeshNode(id="n-latency-only", mesh_id="m1", status="approved")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._aggregate_hourly_telemetry_from_history(
            nodes=[node], since=since, now=now, hours_count=1
        )
        # Bucket should exist (latency is valid)
        self.assertEqual(len(result), 1)
        hour_key = list(result.keys())[0]
        self.assertEqual(result[hour_key]["traffic_mbps_total"], 0.0)
        self.assertAlmostEqual(result[hour_key]["latency_ms_avg"], 12.5)


class TestNormalizeDt(unittest.TestCase):
    """Cover all branches of the _normalize_dt static method."""

    def test_normalize_dt_none_returns_none(self):
        """None input → None output (line 36-37)."""
        self.assertIsNone(MaaSAnalyticsService._normalize_dt(None))

    def test_normalize_dt_naive_returns_unchanged(self):
        """Naive datetime → returned as-is (line 40)."""
        dt = datetime(2026, 2, 22, 12, 0, 0)
        result = MaaSAnalyticsService._normalize_dt(dt)
        self.assertEqual(result, dt)
        self.assertIsNone(result.tzinfo)

    def test_normalize_dt_aware_strips_tzinfo(self):
        """Timezone-aware datetime → converted to naive UTC (lines 38-39)."""
        dt = datetime(2026, 2, 22, 12, 0, 0, tzinfo=timezone.utc)
        result = MaaSAnalyticsService._normalize_dt(dt)
        self.assertIsNotNone(result)
        self.assertIsNone(result.tzinfo)
        self.assertEqual(result, datetime(2026, 2, 22, 12, 0, 0))


class TestParseTelemetryTimestamp(unittest.TestCase):
    """Cover all branches of the _parse_telemetry_timestamp static method."""

    def test_non_string_returns_none(self):
        """Non-string input → None (line 72-73 isinstance check)."""
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp(12345))
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp(None))
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp([]))

    def test_empty_string_returns_none(self):
        """Empty string → None (line 72 `not value` guard)."""
        self.assertIsNone(MaaSAnalyticsService._parse_telemetry_timestamp(""))

    def test_invalid_format_raises_value_error_returns_none(self):
        """Invalid ISO format string → ValueError → None (lines 76-78)."""
        result = MaaSAnalyticsService._parse_telemetry_timestamp("not-a-date")
        self.assertIsNone(result)

    def test_utc_z_suffix_returns_naive_utc(self):
        """ISO string with 'Z' suffix → naive UTC datetime (lines 74-80)."""
        result = MaaSAnalyticsService._parse_telemetry_timestamp("2026-02-22T12:30:00Z")
        self.assertIsNotNone(result)
        self.assertIsNone(result.tzinfo)
        self.assertEqual(result, datetime(2026, 2, 22, 12, 30, 0))


class TestGetRedisTelemetryBytesHappyPath(unittest.TestCase):
    """Cover bytes → valid JSON success path in _get_redis_telemetry (lines 96-98)."""

    def test_bytes_valid_json_decoded_and_returned(self):
        """redis.get() returns bytes with valid JSON → decoded and returned as dict."""
        import json as _json
        redis_client = MagicMock()
        payload = {"traffic_mbps": 99.1, "latency_ms": 4.4}
        redis_client.get.return_value = _json.dumps(payload).encode("utf-8")
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        result = service._get_redis_telemetry("node-bytes-ok")
        self.assertEqual(result["traffic_mbps"], 99.1)
        self.assertEqual(result["latency_ms"], 4.4)


class TestAggregateHourlyTelemetryEmptyNodes(unittest.TestCase):
    """Cover `not nodes` early-return path in _aggregate_hourly_telemetry_from_history."""

    def test_empty_nodes_with_live_redis_returns_empty_dict(self):
        """nodes=[] with valid redis client → {} via `not nodes` short-circuit (line 141)."""
        redis_client = MagicMock()
        service = MaaSAnalyticsService(MagicMock(), redis_client)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        since = now - timedelta(hours=1)
        result = service._aggregate_hourly_telemetry_from_history(
            nodes=[], since=since, now=now, hours_count=1
        )
        self.assertEqual(result, {})
        # lrange should NOT be called since we return early
        redis_client.lrange.assert_not_called()


if __name__ == "__main__":
    unittest.main()
