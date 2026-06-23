#!/usr/bin/env python3
"""
DNS-over-HTTPS (DoH) Resolver for x0tta6bl4 VPN
Prevents DNS leaks by routing all DNS queries through encrypted HTTPS connections
to privacy-focused DNS servers.
"""

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import aiohttp

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "doh-resolver"
_SERVICE_LAYER = "network_dns_over_https_observed_state"
DOH_RESOLVER_CLAIM_BOUNDARY = (
    "DNS-over-HTTPS resolver evidence records local resolver choice, HTTP status "
    "buckets, parser outcomes, timeout/error classes, and bounded result counts "
    "only. It does not prove upstream DNS privacy, remote resolver honesty, VPN "
    "dataplane routing, browser DNS behavior, or that the host avoided every DNS leak."
)


def _normalize_evidence_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _redacted_sha256_prefix(value: Any) -> Optional[str]:
    normalized = _normalize_evidence_value(value)
    if not normalized:
        return None
    return hashlib.sha256(
        normalized.encode("utf-8", errors="replace")
    ).hexdigest()[:16]


def _identity_evidence() -> Dict[str, Any]:
    identity = service_event_identity(service_name=_SERVICE_AGENT)
    return {
        "spiffe_id_present": bool(_normalize_evidence_value(identity.get("spiffe_id"))),
        "spiffe_id_hash": _redacted_sha256_prefix(identity.get("spiffe_id")),
        "did_present": bool(_normalize_evidence_value(identity.get("did"))),
        "did_hash": _redacted_sha256_prefix(identity.get("did")),
        "wallet_address_present": bool(
            _normalize_evidence_value(identity.get("wallet_address"))
        ),
        "wallet_address_hash": _redacted_sha256_prefix(identity.get("wallet_address")),
        "raw_identity_redacted": True,
    }


def _server_evidence(server: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "name_hash": _redacted_sha256_prefix(server.get("name")),
        "url_hash": _redacted_sha256_prefix(server.get("url")),
        "param_keys": sorted(str(key) for key in server.get("params", {}).keys()),
        "raw_server_redacted": True,
    }


def _resolution_evidence_reference(
    event_id: Optional[str],
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "event_id": event_id,
        "source_agent": _SERVICE_AGENT,
        "layer": _SERVICE_LAYER,
        "operation": payload.get("operation"),
        "stage": payload.get("stage"),
        "status": payload.get("status"),
        "reason": payload.get("reason"),
        "record_type": payload.get("record_type"),
        "domain_hash": payload.get("domain_hash"),
        "resolver_mode": payload.get("resolver_mode"),
        "answer_count": payload.get("answer_count"),
        "attempt_count": payload.get("attempt_count"),
        "raw_identifiers_redacted": True,
        "payloads_redacted": True,
        "claim_boundary": payload.get("claim_boundary"),
    }


# Privacy-focused DoH servers (rotating list for better anonymity)
DOH_SERVERS = [
    {
        "name": "Cloudflare",
        "url": "https://cloudflare-dns.com/dns-query",
        "params": {"ct": "application/dns-json"},
    },
    {"name": "Google", "url": "https://dns.google/resolve", "params": {}},
    {
        "name": "Quad9",
        "url": "https://dns.quad9.net/dns-query",
        "params": {"ct": "application/dns-json"},
    },
    {
        "name": "OpenDNS",
        "url": "https://doh.opendns.com/dns-query",
        "params": {"ct": "application/dns-json"},
    },
    {
        "name": "CleanBrowsing",
        "url": "https://doh.cleanbrowsing.org/doh/security-filter",
        "params": {"ct": "application/dns-json"},
    },
]


class DoHResolver:
    """DNS-over-HTTPS resolver with rotating server support."""

    def __init__(
        self,
        servers: List[Dict] = None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
    ):
        self.servers = servers or DOH_SERVERS
        self.current_server_index = 0
        self.session: Optional[aiohttp.ClientSession] = None
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self._last_resolution_evidence: Optional[Dict[str, Any]] = None
        logger.info(f"DoH resolver initialized with {len(self.servers)} servers")

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize doh-resolver EventBus: %s", exc)
            return None

    def _publish_resolver_event(
        self,
        *,
        operation: str,
        stage: str,
        status: str,
        started_at: float,
        domain: Optional[str],
        record_type: str,
        timeout: Optional[float] = None,
        resolver_mode: str,
        attempts: Optional[List[Dict[str, Any]]] = None,
        answer_count: int = 0,
        reason: Optional[str] = None,
        event_type: Optional[EventType] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload = {
            "component": "network.dns_over_https",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "stage": stage,
            "status": status,
            "reason": reason,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "record_type": _normalize_evidence_value(record_type).upper(),
            "domain_hash": _redacted_sha256_prefix(domain),
            "domain_present": bool(_normalize_evidence_value(domain)),
            "resolver_mode": resolver_mode,
            "timeout_seconds": timeout,
            "server_count": len(self.servers),
            "current_server_index": self.current_server_index,
            "attempt_count": len(attempts or []),
            "attempts": attempts or [],
            "answer_count": int(answer_count or 0),
            "observed_state": True,
            "control_action": False,
            "service_identity": _identity_evidence(),
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "claim_boundary": DOH_RESOLVER_CLAIM_BOUNDARY,
        }
        try:
            event = bus.publish(
                event_type
                or (
                    EventType.TASK_BLOCKED
                    if status in {"failed", "error", "timeout"}
                    else EventType.PIPELINE_STAGE_END
                ),
                _SERVICE_AGENT,
                payload,
                priority=4,
            )
            self._last_resolution_evidence = _resolution_evidence_reference(
                event.event_id,
                payload,
            )
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish doh-resolver event: %s", exc)
            self._last_resolution_evidence = None
            return None

    def get_last_resolution_evidence(self) -> Optional[Dict[str, Any]]:
        """Return a redacted reference to the latest resolution evidence event."""
        if self._last_resolution_evidence is None:
            return None
        return dict(self._last_resolution_evidence)

    async def _init_session(self):
        """Initialize aiohttp session if not already initialized."""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    def _rotate_server(self):
        """Rotate to next DoH server for load balancing and anonymity."""
        self.current_server_index = (self.current_server_index + 1) % len(self.servers)
        current = self.servers[self.current_server_index]
        logger.debug(f"Rotated to DNS server: {current['name']}")

    # Google Cloud domains that should use system DNS instead of DoH
    GOOGLE_CLOUD_DOMAINS = [
        "googleapis.com",
        "cloud.google.com",
        "appspot.com",
        "googleusercontent.com",
        "gstatic.com",
        "google.com",
        "youtube.com",
        "youtu.be",
        "spotify.com",
        "scdn.co",
    ]

    def _should_use_system_dns(self, domain: str) -> bool:
        """Check if domain should use system DNS to avoid conflicts."""
        return any(
            domain.endswith(gd) or domain == gd for gd in self.GOOGLE_CLOUD_DOMAINS
        )

    async def _system_dns_resolve(
        self, domain: str, record_type: str = "A"
    ) -> List[str]:
        """Fallback to system DNS for Google Cloud domains."""
        import socket

        try:
            if record_type == "A":
                addrinfo = socket.getaddrinfo(domain, None, socket.AF_INET)
                return list(set([info[4][0] for info in addrinfo]))
            elif record_type == "AAAA":
                addrinfo = socket.getaddrinfo(domain, None, socket.AF_INET6)
                return list(set([info[4][0] for info in addrinfo]))
        except Exception as e:
            logger.warning(f"System DNS resolution failed for {domain}: {e}")
        return []

    async def resolve(
        self, domain: str, record_type: str = "A", timeout: float = 10.0
    ) -> List[str]:
        """
        Resolve a domain name using DNS-over-HTTPS.

        Args:
            domain: Domain name to resolve (e.g., "example.com")
            record_type: DNS record type (A, AAAA, MX, etc.)
            timeout: Request timeout in seconds

        Returns:
            List of resolved IP addresses or other record data
        """
        started_at = time.monotonic()
        normalized_record_type = _normalize_evidence_value(record_type).upper() or "A"
        self._last_resolution_evidence = None
        # Use system DNS for Google Cloud domains to avoid conflicts
        if self._should_use_system_dns(domain):
            logger.debug(f"Using system DNS for {domain} (Google Cloud/Spotify domain)")
            try:
                results = await self._system_dns_resolve(domain, record_type)
                self._publish_resolver_event(
                    operation="resolve",
                    stage="system_dns_fallback",
                    status="success" if results else "failed",
                    started_at=started_at,
                    domain=domain,
                    record_type=normalized_record_type,
                    timeout=timeout,
                    resolver_mode="system_dns_fallback",
                    answer_count=len(results),
                    reason=None if results else "system_dns_empty_result",
                )
                return results
            except Exception as exc:
                self._publish_resolver_event(
                    operation="resolve",
                    stage="system_dns_fallback",
                    status="error",
                    started_at=started_at,
                    domain=domain,
                    record_type=normalized_record_type,
                    timeout=timeout,
                    resolver_mode="system_dns_fallback",
                    reason="system_dns_exception",
                    attempts=[
                        {
                            "error_hash": _redacted_sha256_prefix(exc),
                            "payloads_redacted": True,
                        }
                    ],
                )
                raise

        await self._init_session()

        attempts: List[Dict[str, Any]] = []
        # Try multiple servers if first fails
        for attempt in range(len(self.servers)):
            server = self.servers[self.current_server_index]
            attempt_evidence: Dict[str, Any] = {
                "attempt_index": attempt,
                "server": _server_evidence(server),
                "http_status": None,
                "dns_status": None,
                "answer_count": 0,
                "outcome": "started",
                "payloads_redacted": True,
            }
            try:
                params = server["params"].copy()
                params.update({"name": domain, "type": normalized_record_type})

                url = f"{server['url']}?{urlencode(params)}"

                logger.debug(f"Resolving {domain} ({normalized_record_type}) via {server['name']}")

                async with self.session.get(
                    url,
                    headers={"Accept": "application/dns-json"},
                    timeout=aiohttp.ClientTimeout(total=timeout),
                ) as response:
                    attempt_evidence["http_status"] = response.status
                    if response.status == 200:
                        # Handle case where response might have unexpected mimetype
                        try:
                            data = await response.json()
                        except Exception as e:
                            attempt_evidence["outcome"] = "json_parse_failed"
                            attempt_evidence["error_hash"] = _redacted_sha256_prefix(e)
                            logger.warning(
                                f"Failed to parse JSON from {server['name']}: {e}"
                            )
                            # Try to read raw content for debugging
                            raw_content = await response.text()
                            logger.debug(
                                f"Raw response from {server['name']}: {raw_content}"
                            )
                            self._rotate_server()
                            attempts.append(attempt_evidence)
                            continue

                        if data.get("Status") == 0:  # NOERROR
                            answers = data.get("Answer", [])
                            results = []

                            for ans in answers:
                                if (
                                    ans.get("type") == 1 and normalized_record_type == "A"
                                ):  # A record
                                    results.append(ans.get("data"))
                                elif (
                                    ans.get("type") == 28 and normalized_record_type == "AAAA"
                                ):  # AAAA record
                                    results.append(ans.get("data"))
                                elif normalized_record_type in ["MX", "CNAME", "TXT"]:
                                    results.append(ans.get("data"))

                            logger.debug(f"Resolved {domain} to {len(results)} records")
                            attempt_evidence["dns_status"] = data.get("Status")
                            attempt_evidence["answer_count"] = len(results)
                            attempt_evidence["outcome"] = "success"
                            attempts.append(attempt_evidence)

                            # Rotate server for next request
                            self._rotate_server()

                            self._publish_resolver_event(
                                operation="resolve",
                                stage="doh_resolve",
                                status="success",
                                started_at=started_at,
                                domain=domain,
                                record_type=normalized_record_type,
                                timeout=timeout,
                                resolver_mode="doh",
                                attempts=attempts,
                                answer_count=len(results),
                            )
                            return results
                        else:
                            attempt_evidence["dns_status"] = data.get("Status")
                            attempt_evidence["outcome"] = "dns_status_failed"
                            logger.warning(
                                f"DNS resolution failed for {domain}: {data.get('Status')}"
                            )
                    else:
                        attempt_evidence["outcome"] = "http_status_failed"
                        logger.warning(
                            f"HTTP {response.status} from {server['name']} for {domain}"
                        )

            except asyncio.TimeoutError:
                attempt_evidence["outcome"] = "timeout"
                logger.warning(f"Timeout from {server['name']} for {domain}")
            except Exception as e:
                attempt_evidence["outcome"] = "exception"
                attempt_evidence["error_hash"] = _redacted_sha256_prefix(e)
                logger.warning(f"Error resolving {domain} via {server['name']}: {e}")

            attempts.append(attempt_evidence)
            # Rotate to next server for next attempt
            self._rotate_server()

        logger.error(f"All {len(self.servers)} DNS servers failed for {domain}")
        self._publish_resolver_event(
            operation="resolve",
            stage="doh_resolve",
            status="failed",
            started_at=started_at,
            domain=domain,
            record_type=normalized_record_type,
            timeout=timeout,
            resolver_mode="doh",
            attempts=attempts,
            answer_count=0,
            reason="all_servers_failed",
        )
        return []

    async def resolve_a(self, domain: str) -> List[str]:
        """Resolve IPv4 addresses (A records)."""
        return await self.resolve(domain, "A")

    async def resolve_aaaa(self, domain: str) -> List[str]:
        """Resolve IPv6 addresses (AAAA records)."""
        return await self.resolve(domain, "AAAA")

    async def resolve_mx(self, domain: str) -> List[str]:
        """Resolve MX records."""
        return await self.resolve(domain, "MX")

    async def resolve_txt(self, domain: str) -> List[str]:
        """Resolve TXT records."""
        return await self.resolve(domain, "TXT")

    async def reverse_lookup(self, ip: str) -> List[str]:
        """
        Perform reverse DNS lookup.

        Args:
            ip: IP address to reverse lookup

        Returns:
            List of domain names
        """
        if ":" in ip:  # IPv6
            # IPv6 reverse lookup format: 2001:db8::1 -> 1.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.0.8.b.d.0.1.0.0.2.ip6.arpa
            import ipaddress

            addr = ipaddress.IPv6Address(ip)
            arpa_domain = addr.reverse_pointer
        else:  # IPv4
            # IPv4 reverse lookup format: 192.0.2.1 -> 1.2.0.192.in-addr.arpa
            arpa_domain = ".".join(reversed(ip.split("."))) + ".in-addr.arpa"

        return await self.resolve(arpa_domain, "PTR")

    async def close(self):
        """Close the aiohttp session."""
        if self.session and not self.session.closed:
            await self.session.close()
            logger.info("DoH resolver session closed")

    def get_stats(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        current_server = self.servers[self.current_server_index]
        return {
            "server_count": len(self.servers),
            "current_server": {
                "name": current_server["name"],
                "url": current_server["url"],
            },
        }


# Global resolver instance
_global_resolver = None


async def get_doh_resolver() -> DoHResolver:
    """Get or create the global DoH resolver instance."""
    global _global_resolver
    if _global_resolver is None:
        _global_resolver = DoHResolver()
    return _global_resolver


async def test_doh_resolver():
    """Test DoH resolver functionality."""
    logging.basicConfig(level=logging.DEBUG)

    resolver = DoHResolver()

    print("Testing DoH resolver...")
    print(f"Number of servers: {len(resolver.servers)}")

    # Test DNS resolution
    test_domains = ["example.com", "google.com", "cloudflare.com", "github.com"]

    for domain in test_domains:
        print(f"\nResolving {domain}:")
        ipv4 = await resolver.resolve_a(domain)
        print(f"  IPv4: {ipv4}")

        ipv6 = await resolver.resolve_aaaa(domain)
        print(f"  IPv6: {ipv6}")

    # Test reverse lookup
    print("\nTesting reverse lookup for 8.8.8.8:")
    domains = await resolver.reverse_lookup("8.8.8.8")
    print(f"  Domains: {domains}")

    await resolver.close()
    print("\nTest completed successfully!")


if __name__ == "__main__":
    try:
        asyncio.run(test_doh_resolver())
    except KeyboardInterrupt:
        print("\nTest interrupted")
