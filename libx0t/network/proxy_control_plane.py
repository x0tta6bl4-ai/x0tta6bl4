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
import json
import logging
from dataclasses import asdict
from datetime import datetime
from typing import Any, Dict, List, Optional

from aiohttp import web
try:
    import aiohttp_cors
except ImportError:  # pragma: no cover - optional dependency
    aiohttp_cors = None

from .residential_proxy_manager import (
    ProxyEndpoint,
    ProxyStatus,
    ResidentialProxyManager,
    create_proxy_pool_from_provider,
)

logger = logging.getLogger(__name__)


class ProxyControlPlane:
    """
    REST API control plane for residential proxy management.
    """

    def __init__(
        self,
        proxy_manager: ResidentialProxyManager,
        host: str = "0.0.0.0",  # nosec B104
        port: int = 8081,
    ):
        self.proxy_manager = proxy_manager
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        self._setup_cors()

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
        if aiohttp_cors is None:
            logger.warning("aiohttp_cors is not installed; control plane CORS is disabled")
            return

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
        healthy_count = sum(
            1 for p in self.proxy_manager.proxies if p.status == ProxyStatus.HEALTHY
        )

        return web.json_response(
            {
                "status": "healthy" if healthy_count > 0 else "degraded",
                "proxies": {
                    "total": len(self.proxy_manager.proxies),
                    "healthy": healthy_count,
                    "unhealthy": sum(
                        1
                        for p in self.proxy_manager.proxies
                        if p.status == ProxyStatus.UNHEALTHY
                    ),
                    "banned": sum(
                        1
                        for p in self.proxy_manager.proxies
                        if p.status == ProxyStatus.BANNED
                    ),
                },
                "timestamp": datetime.utcnow().isoformat(),
            }
        )

    async def list_proxies(self, request: web.Request) -> web.Response:
        """List all proxy endpoints."""
        status_filter = request.query.get("status")
        region_filter = request.query.get("region")

        proxies = self.proxy_manager.proxies

        if status_filter:
            proxies = [p for p in proxies if p.status.value == status_filter]

        if region_filter:
            proxies = [p for p in proxies if p.region == region_filter]

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
                ]
            }
        )

    async def get_proxy(self, request: web.Request) -> web.Response:
        """Get specific proxy details."""
        proxy_id = request.match_info["proxy_id"]

        proxy = next((p for p in self.proxy_manager.proxies if p.id == proxy_id), None)

        if not proxy:
            return web.json_response({"error": "Proxy not found"}, status=404)

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
            }
        )

    async def check_proxy_health(self, request: web.Request) -> web.Response:
        """Trigger health check for a specific proxy."""
        proxy_id = request.match_info["proxy_id"]

        proxy = next((p for p in self.proxy_manager.proxies if p.id == proxy_id), None)

        if not proxy:
            return web.json_response({"error": "Proxy not found"}, status=404)

        await self.proxy_manager._check_proxy_health(proxy)

        return web.json_response(
            {
                "proxy_id": proxy_id,
                "status": proxy.status.value,
                "response_time_ms": proxy.response_time_ms,
                "checked_at": datetime.utcnow().isoformat(),
            }
        )

    async def list_domains(self, request: web.Request) -> web.Response:
        """List all tracked domains with reputation scores."""
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

        return web.json_response(
            {"domains": sorted(domains, key=lambda d: d["score"], reverse=True)}
        )

    async def get_domain_reputation(self, request: web.Request) -> web.Response:
        """Get reputation for a specific domain."""
        domain = request.match_info["domain"]

        reputation = self.proxy_manager.get_domain_reputation(domain)

        return web.json_response(
            {
                "domain": reputation.domain,
                "score": reputation.score,
                "block_count": reputation.block_count,
                "success_count": reputation.success_count,
                "last_access": reputation.last_access,
            }
        )

    async def proxy_request(self, request: web.Request) -> web.Response:
        """Make a request through the proxy pool."""
        try:
            data = await request.json()

            url = data.get("url")
            method = data.get("method", "GET")
            headers = data.get("headers", {})
            body = data.get("body")
            target_domain = data.get("target_domain")
            preferred_region = data.get("preferred_region")

            if not url:
                return web.json_response({"error": "URL required"}, status=400)

            response = await self.proxy_manager.request(
                url=url,
                method=method,
                headers=headers,
                data=body,
                target_domain=target_domain,
                preferred_region=preferred_region,
            )

            response_body = await response.text()

            return web.json_response(
                {
                    "status": response.status,
                    "headers": dict(response.headers),
                    "body": response_body[:10000],  # Limit response size
                    "proxy_used": getattr(response, "proxy_id", "unknown"),
                }
            )

        except Exception as e:
            logger.error(f"Proxy request failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def add_proxy_pool(self, request: web.Request) -> web.Response:
        """Add a pool of proxies from a provider."""
        try:
            data = await request.json()

            provider = data.get("provider")
            username = data.get("username")
            password = data.get("password")
            regions = data.get("regions")

            if not all([provider, username, password]):
                return web.json_response(
                    {"error": "provider, username, and password required"}, status=400
                )

            proxies = create_proxy_pool_from_provider(
                provider=provider, username=username, password=password, regions=regions
            )

            for proxy in proxies:
                self.proxy_manager.add_proxy(proxy)

            return web.json_response(
                {
                    "added": len(proxies),
                    "proxies": [{"id": p.id, "region": p.region} for p in proxies],
                }
            )

        except Exception as e:
            logger.error(f"Failed to add proxy pool: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def get_metrics(self, request: web.Request) -> web.Response:
        """Get comprehensive metrics."""
        total_requests = sum(
            p.success_count + p.failure_count for p in self.proxy_manager.proxies
        )
        total_successes = sum(p.success_count for p in self.proxy_manager.proxies)

        avg_response_time = 0.0
        if self.proxy_manager.proxies:
            avg_response_time = sum(
                p.response_time_ms for p in self.proxy_manager.proxies
            ) / len(self.proxy_manager.proxies)

        return web.json_response(
            {
                "proxies": {
                    "total": len(self.proxy_manager.proxies),
                    "healthy": sum(
                        1
                        for p in self.proxy_manager.proxies
                        if p.status == ProxyStatus.HEALTHY
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
                        1
                        for p in self.proxy_manager.proxies
                        if p.status == ProxyStatus.BANNED
                    ),
                },
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
            }
        )

    async def sync_xray_config(self, request: web.Request) -> web.Response:
        """Sync proxy configuration with Xray."""
        try:
            data = await request.json()
            target_domains = data.get("target_domains", [])

            from .residential_proxy_manager import XrayResidentialIntegration

            integration = XrayResidentialIntegration(proxy_manager=self.proxy_manager)

            await integration.update_xray_config(target_domains)

            return web.json_response(
                {
                    "status": "synced",
                    "domains": target_domains,
                    "proxies_used": len(
                        [
                            p
                            for p in self.proxy_manager.proxies
                            if p.status == ProxyStatus.HEALTHY
                        ]
                    ),
                }
            )

        except Exception as e:
            logger.error(f"Xray sync failed: {e}")
            return web.json_response({"error": str(e)}, status=500)

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
    manager = ResidentialProxyManager()

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
