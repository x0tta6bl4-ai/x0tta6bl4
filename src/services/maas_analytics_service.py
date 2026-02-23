"""
MaaS Analytics Service — x0tta6bl4
==================================

Business logic for calculating mesh health, costs, and marketplace ROI.
Isolated from API layer for better testability and performance optimization.
"""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import Invoice, MarketplaceListing, MeshInstance, MeshNode, User

logger = logging.getLogger(__name__)

# Constants
HEALTHY_THRESHOLD = timedelta(minutes=5)

class MaaSAnalyticsService:
    def __init__(self, db: Session, redis_client: Any = None):
        self.db = db
        self.redis = redis_client
        self._redis_ok = redis_client is not None and not isinstance(redis_client, dict)

    @staticmethod
    def _utcnow_naive() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)

    @staticmethod
    def _normalize_dt(dt: Optional[datetime]) -> Optional[datetime]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            return dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    def _is_node_online(self, node: MeshNode, now: Optional[datetime] = None) -> bool:
        """
        A node is considered online when:
        - status is healthy/approved and last_seen is recent, or
        - status is healthy/approved and last_seen is missing (legacy compatibility), or
        - status is empty/null for legacy rows and last_seen is recent.
        """
        status = (node.status or "").strip().lower()
        status_is_online_candidate = status in ("approved", "healthy") or not status
        if not status_is_online_candidate:
            return False
        if node.last_seen is None:
            return True
        now_ts = now or self._utcnow_naive()
        last_seen = self._normalize_dt(node.last_seen)
        if last_seen is None:
            return False
        return (now_ts - last_seen) <= HEALTHY_THRESHOLD

    @staticmethod
    def _safe_float(value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_telemetry_timestamp(value: Any) -> Optional[datetime]:
        if not isinstance(value, str) or not value:
            return None
        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _decode_redis_payload(raw: Any) -> Optional[Dict[str, Any]]:
        try:
            payload_raw = raw
            if isinstance(payload_raw, bytes):
                payload_raw = payload_raw.decode("utf-8", errors="ignore")
            if isinstance(payload_raw, str):
                payload = json.loads(payload_raw)
            elif isinstance(payload_raw, dict):
                payload = payload_raw
            else:
                return None
            if isinstance(payload, dict):
                return payload
        except Exception:
            return None
        return None

    def _parse_redis_history_items(self, raw_items: Any) -> List[Dict[str, Any]]:
        parsed_items: List[Dict[str, Any]] = []
        for raw in raw_items or []:
            payload = self._decode_redis_payload(raw)
            if payload is not None:
                parsed_items.append(payload)
        return parsed_items

    def _node_health_score(self, nodes: List[MeshNode]) -> float:
        if not nodes:
            return 1.0
        now = self._utcnow_naive()
        healthy = sum(1 for n in nodes if self._is_node_online(n, now=now))
        return round(healthy / len(nodes), 3)

    def _get_redis_telemetry(self, node_id: str) -> Dict[str, Any]:
        if self._redis_ok:
            key = f"maas:telemetry:{node_id}"
            try:
                raw = self.redis.get(key)
                if raw:
                    payload = self._decode_redis_payload(raw)
                    if payload is not None:
                        return payload
            except Exception as exc:
                logger.warning("Failed to read telemetry from Redis for node %s: %s", node_id, exc)
        return {}

    def _get_redis_telemetry_history(self, node_id: str, max_items: int) -> List[Dict[str, Any]]:
        if not self._redis_ok or max_items <= 0:
            return []
        if not hasattr(self.redis, "lrange"):
            return []

        key = f"maas:telemetry:{node_id}:history"
        try:
            raw_items = self.redis.lrange(key, 0, max_items - 1)
        except Exception as exc:
            logger.warning("Failed to read telemetry history from Redis for node %s: %s", node_id, exc)
            return []

        return self._parse_redis_history_items(raw_items)

    def _get_redis_telemetry_bulk(self, node_ids: List[str]) -> Dict[str, Dict[str, Any]]:
        if not self._redis_ok or not node_ids:
            return {}

        keys = [f"maas:telemetry:{node_id}" for node_id in node_ids]
        results: Dict[str, Dict[str, Any]] = {}

        if hasattr(self.redis, "mget"):
            try:
                raw_values = self.redis.mget(keys)
                if not isinstance(raw_values, (list, tuple)):
                    raise TypeError("redis.mget returned unexpected payload type")
                for node_id, raw in zip(node_ids, raw_values or []):
                    payload = self._decode_redis_payload(raw)
                    if payload is not None:
                        results[node_id] = payload
                return results
            except Exception as exc:
                logger.warning("Failed bulk telemetry read from Redis: %s", exc)

        for node_id in node_ids:
            payload = self._get_redis_telemetry(node_id)
            if payload:
                results[node_id] = payload
        return results

    def _get_redis_telemetry_history_bulk(
        self,
        node_ids: List[str],
        max_items: int,
    ) -> Dict[str, List[Dict[str, Any]]]:
        if not self._redis_ok or not node_ids or max_items <= 0:
            return {}

        results: Dict[str, List[Dict[str, Any]]] = {}
        if hasattr(self.redis, "pipeline"):
            try:
                try:
                    pipe = self.redis.pipeline(transaction=False)
                except TypeError:
                    pipe = self.redis.pipeline()
                for node_id in node_ids:
                    pipe.lrange(f"maas:telemetry:{node_id}:history", 0, max_items - 1)
                raw_batches = pipe.execute()
                if not isinstance(raw_batches, (list, tuple)):
                    raise TypeError("redis pipeline returned unexpected payload type")
                for node_id, raw_items in zip(node_ids, raw_batches or []):
                    parsed = self._parse_redis_history_items(raw_items)
                    if parsed:
                        results[node_id] = parsed
                return results
            except Exception as exc:
                logger.warning("Failed bulk telemetry history read from Redis: %s", exc)

        for node_id in node_ids:
            parsed = self._get_redis_telemetry_history(node_id, max_items=max_items)
            if parsed:
                results[node_id] = parsed
        return results

    def _aggregate_hourly_telemetry_from_history(
        self,
        nodes: List[MeshNode],
        since: datetime,
        now: datetime,
        hours_count: int,
    ) -> Dict[str, Dict[str, float]]:
        if not nodes or not self._redis_ok:
            return {}

        max_items_per_node = max(24, hours_count * 12)  # ~5 minute heartbeat cadence
        buckets: Dict[str, Dict[str, List[float]]] = {}
        node_histories = self._get_redis_telemetry_history_bulk(
            node_ids=[node.id for node in nodes],
            max_items=max_items_per_node,
        )

        for node in nodes:
            history = node_histories.get(node.id, [])
            for sample in history:
                timestamp = self._parse_telemetry_timestamp(
                    sample.get("timestamp") or sample.get("last_seen")
                )
                if timestamp is None or timestamp < since or timestamp > now:
                    continue
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0).strftime(
                    "%Y-%m-%dT%H:00:00"
                )
                bucket = buckets.setdefault(hour_key, {"traffic": [], "latency": []})

                traffic = self._safe_float(sample.get("traffic_mbps"))
                if traffic is not None and traffic >= 0:
                    bucket["traffic"].append(traffic)

                latency = self._safe_float(sample.get("latency_ms"))
                if latency is not None and latency >= 0:
                    bucket["latency"].append(latency)

        aggregated: Dict[str, Dict[str, float]] = {}
        for hour_key, values in buckets.items():
            if not values["traffic"] and not values["latency"]:
                continue
            aggregated[hour_key] = {
                "traffic_mbps_total": sum(values["traffic"]) if values["traffic"] else 0.0,
                "latency_ms_avg": (
                    sum(values["latency"]) / len(values["latency"])
                ) if values["latency"] else 0.0,
            }
        return aggregated

    def _aggregate_realtime_telemetry(self, nodes: List[MeshNode]) -> Optional[Dict[str, float]]:
        if not self._redis_ok or not nodes:
            return None

        traffic_values: List[float] = []
        latency_values: List[float] = []
        node_telemetry = self._get_redis_telemetry_bulk([node.id for node in nodes])
        for node in nodes:
            telemetry = node_telemetry.get(node.id, {})
            traffic = self._safe_float(telemetry.get("traffic_mbps"))
            if traffic is not None and traffic >= 0:
                traffic_values.append(traffic)

            latency = self._safe_float(telemetry.get("latency_ms"))
            if latency is not None and latency >= 0:
                latency_values.append(latency)

        if not traffic_values and not latency_values:
            return None

        return {
            "traffic_mbps_total": sum(traffic_values) if traffic_values else 0.0,
            "latency_ms_avg": (sum(latency_values) / len(latency_values)) if latency_values else 0.0,
        }

    def get_mesh_summary(self, mesh_id: str, owner_id: str) -> Optional[Dict[str, Any]]:
        instance = self.db.query(MeshInstance).filter(
            MeshInstance.id == mesh_id,
            MeshInstance.owner_id == owner_id,
        ).first()
        if not instance:
            return None

        nodes = self.db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
        now = self._utcnow_naive()
        nodes_online = sum(1 for n in nodes if self._is_node_online(n, now=now))
        health = self._node_health_score(nodes)

        total_cents = self.db.query(func.sum(Invoice.total_amount)).filter(
            Invoice.mesh_id == mesh_id,
            Invoice.issued_at >= now - timedelta(days=30),
        ).scalar() or 0
        cost_maas = round(float(total_cents) / 100.0, 2)

        cost_aws = round(float(len(nodes)) * 45.0, 2)
        savings = round(((cost_aws - cost_maas) / cost_aws) * 100, 1) if cost_aws > 0 else 0.0

        return {
            "mesh_id": mesh_id,
            "cost_maas_total": cost_maas,
            "cost_aws_estimate": cost_aws,
            "savings_pct": savings,
            "pqc_status": bool(instance.pqc_enabled),
            "nodes_total": len(nodes),
            "nodes_online": nodes_online,
            "health_score": health,
        }

    def get_mesh_timeseries(self, mesh_id: str, owner_id: str, time_range: str = "24h") -> Optional[Dict[str, Any]]:
        instance = self.db.query(MeshInstance).filter(
            MeshInstance.id == mesh_id,
            MeshInstance.owner_id == owner_id,
        ).first()
        if not instance:
            return None

        hours_count = {"1h": 1, "6h": 6, "24h": 24, "7d": 168}.get(time_range, 24)
        now = self._utcnow_naive()
        since = now - timedelta(hours=hours_count)

        nodes = self.db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id).all()
        node_count = len(nodes)

        # Optimization: Group nodes by hour of last_seen in one query
        # SQLite syntax for grouping by hour
        health_stats = self.db.query(
            func.strftime('%Y-%m-%dT%H:00:00', MeshNode.last_seen).label('hour'),
            func.count(MeshNode.id).label('count')
        ).filter(
            MeshNode.mesh_id == mesh_id,
            MeshNode.last_seen >= since
        ).group_by('hour').all()
        
        health_map = {row.hour: row.count for row in health_stats}

        # Aggregate traffic baseline (still needs Redis or Marketplace metadata)
        total_traffic_base = self.db.query(func.sum(MarketplaceListing.bandwidth_mbps)).join(
            MeshNode, MeshNode.id == MarketplaceListing.node_id
        ).filter(MeshNode.mesh_id == mesh_id).scalar() or 0.0

        current_health = self._node_health_score(nodes)
        realtime_telemetry = self._aggregate_realtime_telemetry(nodes)
        history_telemetry = self._aggregate_hourly_telemetry_from_history(
            nodes=nodes,
            since=since,
            now=now,
            hours_count=hours_count,
        )
        current_hour_key = now.strftime('%Y-%m-%dT%H:00:00')

        history: List[Dict[str, Any]] = []
        for i in range(hours_count):
            t = now - timedelta(hours=(hours_count - 1 - i))
            t_str = t.strftime('%Y-%m-%dT%H:00:00')
            
            alive_in_hour = health_map.get(t_str, 0)
            health_val = round(alive_in_hour / node_count * 100, 1) if node_count > 0 else 0.0

            bucket = history_telemetry.get(t_str)
            if bucket:
                traffic_val = round(bucket["traffic_mbps_total"], 1)
                latency_val = round(max(0.0, bucket["latency_ms_avg"]), 1)
            elif realtime_telemetry and t_str == current_hour_key:
                traffic_val = round(realtime_telemetry["traffic_mbps_total"], 1)
                latency_val = round(max(0.0, realtime_telemetry["latency_ms_avg"]), 1)
            else:
                # Fallback simulation if no telemetry in Redis is available.
                hour_factor = 1.4 if 8 <= t.hour <= 20 else 0.7
                traffic_val = round(float(total_traffic_base) * 0.1 * hour_factor, 1)
                latency_val = round(25.0 * (2.0 - current_health), 1)

            history.append({
                "timestamp": t.isoformat(),
                "health": health_val,
                "traffic_mbps": traffic_val,
                "latency_ms": latency_val,
            })

        return {
            "mesh_id": mesh_id,
            "range": time_range,
            "nodes_total": node_count,
            "data": history,
        }

    def get_marketplace_roi(self, mesh_id: str, owner_id: str) -> Dict[str, Any]:
        # Implementation moved from API
        listings = self.db.query(MarketplaceListing).filter(
            MarketplaceListing.owner_id == owner_id,
        ).all()

        available = sum(1 for l in listings if l.status == "available")
        rented = sum(1 for l in listings if l.status == "rented")
        in_escrow = sum(1 for l in listings if l.status == "escrow")
        hourly_revenue_cents = sum(
            l.price_per_hour for l in listings if l.status in ("rented", "escrow")
        )

        return {
            "mesh_id": mesh_id,
            "listings": {
                "total": len(listings),
                "available": available,
                "rented": rented,
                "in_escrow": in_escrow,
            },
            "revenue": {
                "hourly_cents": hourly_revenue_cents,
                "hourly_usd": round(hourly_revenue_cents / 100.0, 2),
                "monthly_estimate_usd": round(hourly_revenue_cents / 100.0 * 24 * 30, 2),
            },
        }
