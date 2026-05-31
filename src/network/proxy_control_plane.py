"""
Control Plane API for Residential Proxy Management.

Provides REST API for:
- Dynamic proxy selection
- Health monitoring
- Domain reputation scoring
- Geographic rotation control
- Real-time metrics
"""

import asyncio
import hashlib
import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

import aiohttp_cors
from aiohttp import web

from src.coordination.events import EventBus, EventType, get_event_bus
from src.network.residential_proxy_manager import (
    ProxyStatus, ResidentialProxyManager,
    create_proxy_pool_from_provider)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "proxy-control-plane"
_SERVICE_LAYER = "network_proxy_control_plane_observed_state"
PROXY_CONTROL_PLANE_CLAIM_BOUNDARY = (
    "Local proxy control-plane API observed-state evidence only. It records "
    "redacted route, status, count, and mutation-attempt metadata for the "
    "residential proxy API. It does not copy proxy hosts, credentials, target "
    "URLs, request headers, request bodies, response bodies, or Xray config "
    "contents, and it does not prove external provider reachability, customer "
    "traffic delivery, or successful downstream Xray reload."
)


def _hash_value(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


class ProxyControlPlane:
    """
    REST API control plane for residential proxy management.
    """

    def __init__(
        self,
        proxy_manager: ResidentialProxyManager,
        host: str = "0.0.0.0",  # nosec B104
        port: int = 8081,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.proxy_manager = proxy_manager
        self.host = host
        self.port = port
        self.event_bus = event_bus or getattr(proxy_manager, "event_bus", None)
        self.event_project_root = (
            event_project_root
            if event_project_root is not None
            else getattr(proxy_manager, "event_project_root", None)
        )
        self.app = web.Application()
        self._setup_routes()
        self._setup_cors()

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize proxy-control-plane EventBus: %s", exc)
            return None

    def _service_identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {field: bool(value) for field, value in identity.items()}

    def _proxy_status_counts(self) -> Dict[str, int]:
        return {
            "total": len(self.proxy_manager.proxies),
            "healthy": sum(
                1 for p in self.proxy_manager.proxies if p.status == ProxyStatus.HEALTHY
            ),
            "degraded": sum(
                1
                for p in self.proxy_manager.proxies
                if p.status == ProxyStatus.DEGRADED
            ),
            "unhealthy": sum(
                1
                for p in self.proxy_manager.proxies
                if p.status == ProxyStatus.UNHEALTHY
            ),
            "banned": sum(
                1 for p in self.proxy_manager.proxies if p.status == ProxyStatus.BANNED
            ),
        }

    def _publish_api_evidence(
        self,
        *,
        operation: str,
        http_status: int,
        success: bool,
        duration_ms: float,
        payload: Dict[str, Any],
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None
        event_payload = {
            "component": "network.proxy_control_plane",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": "api_success" if success else "api_failure",
            "success": bool(success),
            "http_status": int(http_status),
            "duration_ms": round(float(duration_ms), 3),
            "service_identity_present": self._service_identity_presence(),
            "raw_identifiers_redacted": True,
            "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
            **payload,
        }
        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                _SERVICE_AGENT,
                event_payload,
                priority=4,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish proxy control-plane evidence: %s", exc)
            return None

    def _setup_routes(self):
        """Setup API routes."""
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/proxies", self.list_proxies)
        self.app.router.add_get("/proxies/{proxy_id}", self.get_proxy)
        self.app.router.add_post(
            "/proxies/{proxy_id}/health-check", self.check_proxy_health
        )
        self.app.router.add_get("/domains", self.list_domains)
        self.app.router.add_get("/domains/{domain}", self.get_domain_reputation)
        self.app.router.add_post("/request", self.proxy_request)
        self.app.router.add_post("/proxies/pool", self.add_proxy_pool)
        self.app.router.add_get("/metrics", self.get_metrics)
        self.app.router.add_post("/xray/sync", self.sync_xray_config)

    def _setup_cors(self):
        """Setup CORS for API endpoints."""
        cors = aiohttp_cors.setup(
            self.app,
            defaults={
                "*": aiohttp_cors.ResourceOptions(
                    allow_credentials=True,
                    expose_headers="*",
                    allow_headers="*",
                    allow_methods="*",
                )
            },
        )

        for route in list(self.app.router.routes()):
            cors.add(route)

    async def health_check(self, request: web.Request) -> web.Response:
        """Health check endpoint."""
        started = time.perf_counter()
        proxy_counts = self._proxy_status_counts()
        healthy_count = proxy_counts["healthy"]
        evidence_event_id = self._publish_api_evidence(
            operation="health_check",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "GET /health",
                "proxy_counts": proxy_counts,
            },
        )

        return web.json_response(
            {
                "status": "healthy" if healthy_count > 0 else "degraded",
                "proxies": {
                    "total": proxy_counts["total"],
                    "healthy": healthy_count,
                    "unhealthy": proxy_counts["unhealthy"],
                    "banned": proxy_counts["banned"],
                },
                "timestamp": datetime.utcnow().isoformat(),
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def list_proxies(self, request: web.Request) -> web.Response:
        """List all proxy endpoints."""
        started = time.perf_counter()
        status_filter = request.query.get("status")
        region_filter = request.query.get("region")

        proxies = self.proxy_manager.proxies

        if status_filter:
            proxies = [p for p in proxies if p.status.value == status_filter]

        if region_filter:
            proxies = [p for p in proxies if p.region == region_filter]

        evidence_event_id = self._publish_api_evidence(
            operation="list_proxies",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "GET /proxies",
                "status_filter": status_filter,
                "region_filter_hash": _hash_value(region_filter),
                "returned_count": len(proxies),
                "proxy_counts": self._proxy_status_counts(),
            },
        )
        return web.json_response(
            {
                "proxies": [
                    {
                        "id": p.id,
                        "host": p.host,
                        "port": p.port,
                        "region": p.region,
                        "country_code": p.country_code,
                        "status": p.status.value,
                        "response_time_ms": p.response_time_ms,
                        "success_count": p.success_count,
                        "failure_count": p.failure_count,
                        "ban_count": p.ban_count,
                        "last_check": p.last_check,
                        "requests_per_minute": p.get_requests_in_last_minute(),
                    }
                    for p in proxies
                ],
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def get_proxy(self, request: web.Request) -> web.Response:
        """Get specific proxy details."""
        started = time.perf_counter()
        proxy_id = request.match_info["proxy_id"]

        proxy = next((p for p in self.proxy_manager.proxies if p.id == proxy_id), None)

        if not proxy:
            evidence_event_id = self._publish_api_evidence(
                operation="get_proxy",
                http_status=404,
                success=False,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "GET /proxies/{proxy_id}",
                    "proxy_id_hash": _hash_value(proxy_id),
                    "proxy_found": False,
                },
            )
            return web.json_response(
                {
                    "error": "Proxy not found",
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                },
                status=404,
            )

        evidence_event_id = self._publish_api_evidence(
            operation="get_proxy",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "GET /proxies/{proxy_id}",
                "proxy_id_hash": _hash_value(proxy_id),
                "proxy_found": True,
                "proxy_status": proxy.status.value,
                "region_hash": _hash_value(proxy.region),
                "country_code": proxy.country_code,
            },
        )
        return web.json_response(
            {
                "id": proxy.id,
                "host": proxy.host,
                "port": proxy.port,
                "region": proxy.region,
                "country_code": proxy.country_code,
                "city": proxy.city,
                "isp": proxy.isp,
                "status": proxy.status.value,
                "response_time_ms": proxy.response_time_ms,
                "success_count": proxy.success_count,
                "failure_count": proxy.failure_count,
                "ban_count": proxy.ban_count,
                "last_check": proxy.last_check,
                "requests_per_minute": proxy.get_requests_in_last_minute(),
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def check_proxy_health(self, request: web.Request) -> web.Response:
        """Trigger health check for a specific proxy."""
        started = time.perf_counter()
        proxy_id = request.match_info["proxy_id"]

        proxy = next((p for p in self.proxy_manager.proxies if p.id == proxy_id), None)

        if not proxy:
            evidence_event_id = self._publish_api_evidence(
                operation="check_proxy_health",
                http_status=404,
                success=False,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /proxies/{proxy_id}/health-check",
                    "proxy_id_hash": _hash_value(proxy_id),
                    "proxy_found": False,
                },
            )
            return web.json_response(
                {
                    "error": "Proxy not found",
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                },
                status=404,
            )

        await self.proxy_manager._check_proxy_health(proxy)
        evidence_event_id = self._publish_api_evidence(
            operation="check_proxy_health",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "POST /proxies/{proxy_id}/health-check",
                "proxy_id_hash": _hash_value(proxy_id),
                "proxy_found": True,
                "proxy_status": proxy.status.value,
                "response_time_ms": round(float(proxy.response_time_ms), 3),
            },
        )

        return web.json_response(
            {
                "proxy_id": proxy_id,
                "status": proxy.status.value,
                "response_time_ms": proxy.response_time_ms,
                "checked_at": datetime.utcnow().isoformat(),
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def list_domains(self, request: web.Request) -> web.Response:
        """List all tracked domains with reputation scores."""
        started = time.perf_counter()
        min_score = float(request.query.get("min_score", 0.0))

        domains = [
            {
                "domain": d.domain,
                "score": d.score,
                "block_count": d.block_count,
                "success_count": d.success_count,
                "last_access": d.last_access,
            }
            for d in self.proxy_manager.domain_reputations.values()
            if d.score >= min_score
        ]
        evidence_event_id = self._publish_api_evidence(
            operation="list_domains",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "GET /domains",
                "min_score": float(min_score),
                "tracked_domains": len(self.proxy_manager.domain_reputations),
                "returned_count": len(domains),
            },
        )

        return web.json_response(
            {
                "domains": sorted(domains, key=lambda d: d["score"], reverse=True),
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def get_domain_reputation(self, request: web.Request) -> web.Response:
        """Get reputation for a specific domain."""
        started = time.perf_counter()
        domain = request.match_info["domain"]

        reputation = self.proxy_manager.get_domain_reputation(domain)
        evidence_event_id = self._publish_api_evidence(
            operation="get_domain_reputation",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "GET /domains/{domain}",
                "domain_hash": _hash_value(domain),
                "score_bucket": "low" if reputation.score < 0.5 else "normal",
                "block_count": int(reputation.block_count),
                "success_count": int(reputation.success_count),
            },
        )

        return web.json_response(
            {
                "domain": reputation.domain,
                "score": reputation.score,
                "block_count": reputation.block_count,
                "success_count": reputation.success_count,
                "last_access": reputation.last_access,
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def proxy_request(self, request: web.Request) -> web.Response:
        """Make a request through the proxy pool."""
        started = time.perf_counter()
        try:
            data = await request.json()

            url = data.get("url")
            method = data.get("method", "GET")
            headers = data.get("headers", {})
            body = data.get("body")
            target_domain = data.get("target_domain")
            preferred_region = data.get("preferred_region")

            if not url:
                evidence_event_id = self._publish_api_evidence(
                    operation="proxy_request",
                    http_status=400,
                    success=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "route": "POST /request",
                        "url_present": False,
                        "method": str(method).upper(),
                        "headers_present": bool(headers),
                        "body_present": body is not None,
                        "target_domain_hash": _hash_value(target_domain),
                        "preferred_region_hash": _hash_value(preferred_region),
                        "validation_error": "url_required",
                    },
                )
                return web.json_response(
                    {
                        "error": "URL required",
                        "evidence": {
                            "event_id": evidence_event_id,
                            "source_agent": (
                                _SERVICE_AGENT if evidence_event_id else None
                            ),
                            "layer": _SERVICE_LAYER if evidence_event_id else None,
                            "payload_redacted": True,
                            "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                        },
                    },
                    status=400,
                )

            response = await self.proxy_manager.request(
                url=url,
                method=method,
                headers=headers,
                data=body,
                target_domain=target_domain,
                preferred_region=preferred_region,
            )

            response_body = await response.text()
            evidence_event_id = self._publish_api_evidence(
                operation="proxy_request",
                http_status=200,
                success=True,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /request",
                    "url_present": True,
                    "url_hash": _hash_value(url),
                    "method": str(method).upper(),
                    "headers_present": bool(headers),
                    "body_present": body is not None,
                    "target_domain_hash": _hash_value(target_domain),
                    "preferred_region_hash": _hash_value(preferred_region),
                    "response": {
                        "status_code": int(response.status),
                        "headers_count": len(getattr(response, "headers", {}) or {}),
                        "body_truncated_to": 10000,
                        "body_returned_chars": len(response_body[:10000]),
                    },
                    "proxy_used_hash": _hash_value(
                        getattr(response, "proxy_id", "unknown")
                    ),
                },
            )

            return web.json_response(
                {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response_body[:10000],  # Limit response size
                    "proxy_used": getattr(response, "proxy_id", "unknown"),
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Proxy request failed: {e}")
            evidence_event_id = self._publish_api_evidence(
                operation="proxy_request",
                http_status=500,
                success=False,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /request",
                    "error_type": type(e).__name__,
                },
            )
            return web.json_response(
                {
                    "error": str(e),
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                },
                status=500,
            )

    async def add_proxy_pool(self, request: web.Request) -> web.Response:
        """Add a pool of proxies from a provider."""
        started = time.perf_counter()
        try:
            data = await request.json()

            provider = data.get("provider")
            username = data.get("username")
            password = data.get("password")
            regions = data.get("regions")

            if not all([provider, username, password]):
                evidence_event_id = self._publish_api_evidence(
                    operation="add_proxy_pool",
                    http_status=400,
                    success=False,
                    duration_ms=(time.perf_counter() - started) * 1000,
                    payload={
                        "route": "POST /proxies/pool",
                        "provider_hash": _hash_value(provider),
                        "username_present": bool(username),
                        "password_present": bool(password),
                        "regions_count": len(regions or []),
                        "validation_error": "provider_username_password_required",
                    },
                )
                return web.json_response(
                    {
                        "error": "provider, username, and password required",
                        "evidence": {
                            "event_id": evidence_event_id,
                            "source_agent": (
                                _SERVICE_AGENT if evidence_event_id else None
                            ),
                            "layer": _SERVICE_LAYER if evidence_event_id else None,
                            "payload_redacted": True,
                            "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                        },
                    },
                    status=400,
                )

            proxies = create_proxy_pool_from_provider(
                provider=provider, username=username, password=password, regions=regions
            )

            for proxy in proxies:
                self.proxy_manager.add_proxy(proxy)

            evidence_event_id = self._publish_api_evidence(
                operation="add_proxy_pool",
                http_status=200,
                success=True,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /proxies/pool",
                    "provider_hash": _hash_value(provider),
                    "username_present": bool(username),
                    "password_present": bool(password),
                    "regions_count": len(regions or []),
                    "added_count": len(proxies),
                    "added_proxy_id_hashes": [_hash_value(p.id) for p in proxies],
                },
            )
            return web.json_response(
                {
                    "added": len(proxies),
                    "proxies": [{"id": p.id, "region": p.region} for p in proxies],
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Failed to add proxy pool: {e}")
            evidence_event_id = self._publish_api_evidence(
                operation="add_proxy_pool",
                http_status=500,
                success=False,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /proxies/pool",
                    "error_type": type(e).__name__,
                },
            )
            return web.json_response(
                {
                    "error": str(e),
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                },
                status=500,
            )

    async def get_metrics(self, request: web.Request) -> web.Response:
        """Get comprehensive metrics."""
        started = time.perf_counter()
        total_requests = sum(
            p.success_count + p.failure_count for p in self.proxy_manager.proxies
        )
        total_successes = sum(p.success_count for p in self.proxy_manager.proxies)

        avg_response_time = 0.0
        if self.proxy_manager.proxies:
            avg_response_time = sum(
                p.response_time_ms for p in self.proxy_manager.proxies
            ) / len(self.proxy_manager.proxies)

        proxy_counts = self._proxy_status_counts()
        evidence_event_id = self._publish_api_evidence(
            operation="get_metrics",
            http_status=200,
            success=True,
            duration_ms=(time.perf_counter() - started) * 1000,
            payload={
                "route": "GET /metrics",
                "proxy_counts": proxy_counts,
                "requests": {
                    "total": int(total_requests),
                    "successes": int(total_successes),
                    "failures": int(total_requests - total_successes),
                },
                "tracked_domains": len(self.proxy_manager.domain_reputations),
            },
        )
        return web.json_response(
            {
                "proxies": proxy_counts,
                "requests": {
                    "total": total_requests,
                    "successes": total_successes,
                    "failures": total_requests - total_successes,
                    "success_rate": (
                        total_successes / total_requests if total_requests > 0 else 0.0
                    ),
                },
                "performance": {
                    "avg_response_time_ms": avg_response_time,
                    "min_response_time_ms": min(
                        (p.response_time_ms for p in self.proxy_manager.proxies),
                        default=0,
                    ),
                    "max_response_time_ms": max(
                        (p.response_time_ms for p in self.proxy_manager.proxies),
                        default=0,
                    ),
                },
                "domains": {
                    "tracked": len(self.proxy_manager.domain_reputations),
                    "high_risk": sum(
                        1
                        for d in self.proxy_manager.domain_reputations.values()
                        if d.score < 0.3
                    ),
                },
                "timestamp": datetime.utcnow().isoformat(),
                "evidence": {
                    "event_id": evidence_event_id,
                    "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                    "layer": _SERVICE_LAYER if evidence_event_id else None,
                    "payload_redacted": True,
                    "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                },
            }
        )

    async def sync_xray_config(self, request: web.Request) -> web.Response:
        """Sync proxy configuration with Xray."""
        started = time.perf_counter()
        try:
            data = await request.json()
            target_domains = data.get("target_domains", [])

            from src.network.residential_proxy_manager import \
                XrayResidentialIntegration

            integration = XrayResidentialIntegration(proxy_manager=self.proxy_manager)

            await integration.update_xray_config(target_domains)

            proxies_used = len(
                [
                    p
                    for p in self.proxy_manager.proxies
                    if p.status == ProxyStatus.HEALTHY
                ]
            )
            evidence_event_id = self._publish_api_evidence(
                operation="sync_xray_config",
                http_status=200,
                success=True,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /xray/sync",
                    "target_domains_count": len(target_domains),
                    "target_domain_hashes": [
                        _hash_value(domain) for domain in target_domains[:20]
                    ],
                    "target_domains_truncated": len(target_domains) > 20,
                    "healthy_proxies_used": proxies_used,
                },
            )
            return web.json_response(
                {
                    "status": "synced",
                    "domains": target_domains,
                    "proxies_used": proxies_used,
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                }
            )

        except Exception as e:
            logger.error(f"Xray sync failed: {e}")
            evidence_event_id = self._publish_api_evidence(
                operation="sync_xray_config",
                http_status=500,
                success=False,
                duration_ms=(time.perf_counter() - started) * 1000,
                payload={
                    "route": "POST /xray/sync",
                    "error_type": type(e).__name__,
                },
            )
            return web.json_response(
                {
                    "error": str(e),
                    "evidence": {
                        "event_id": evidence_event_id,
                        "source_agent": _SERVICE_AGENT if evidence_event_id else None,
                        "layer": _SERVICE_LAYER if evidence_event_id else None,
                        "payload_redacted": True,
                        "claim_boundary": PROXY_CONTROL_PLANE_CLAIM_BOUNDARY,
                    },
                },
                status=500,
            )

    async def start(self):
        """Start the control plane API."""
        runner = web.AppRunner(self.app)
        await runner.setup()

        site = web.TCPSite(runner, self.host, self.port)
        await site.start()

        logger.info(f"Proxy Control Plane API started on {self.host}:{self.port}")

    async def stop(self):
        """Stop the control plane API."""
        await self.app.shutdown()
        await self.app.cleanup()
        logger.info("Proxy Control Plane API stopped")


async def main():
    """Main entry point for running the control plane standalone."""
    # Create proxy manager
    manager = ResidentialProxyManager(event_project_root=".")

    # Add some example proxies (in production, load from config)
    # manager.add_proxies_from_config([...])

    # Start manager
    await manager.start()

    # Create and start control plane
    control_plane = ProxyControlPlane(manager)
    await control_plane.start()

    try:
        # Keep running
        while True:
            await asyncio.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        await control_plane.stop()
        await manager.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
