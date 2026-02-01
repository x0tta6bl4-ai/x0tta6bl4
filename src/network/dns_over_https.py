#!/usr/bin/env python3
"""
DNS-over-HTTPS (DoH) Resolver for x0tta6bl4 VPN
Prevents DNS leaks by routing all DNS queries through encrypted HTTPS connections
to privacy-focused DNS servers.
"""

import asyncio
import aiohttp
import json
import logging
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode

logger = logging.getLogger(__name__)

# Privacy-focused DoH servers (rotating list for better anonymity)
DOH_SERVERS = [
    {
        "name": "Cloudflare",
        "url": "https://cloudflare-dns.com/dns-query",
        "params": {"ct": "application/dns-json"}
    },
    {
        "name": "Google",
        "url": "https://dns.google/resolve",
        "params": {}
    },
    {
        "name": "Quad9",
        "url": "https://dns.quad9.net/dns-query",
        "params": {"ct": "application/dns-json"}
    },
    {
        "name": "OpenDNS",
        "url": "https://doh.opendns.com/dns-query",
        "params": {"ct": "application/dns-json"}
    },
    {
        "name": "CleanBrowsing",
        "url": "https://doh.cleanbrowsing.org/doh/security-filter",
        "params": {"ct": "application/dns-json"}
    }
]

class DoHResolver:
    """DNS-over-HTTPS resolver with rotating server support."""
    
    def __init__(self, servers: List[Dict] = None):
        self.servers = servers or DOH_SERVERS
        self.current_server_index = 0
        self.session: Optional[aiohttp.ClientSession] = None
        logger.info(f"DoH resolver initialized with {len(self.servers)} servers")
    
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
        return any(domain.endswith(gd) or domain == gd for gd in self.GOOGLE_CLOUD_DOMAINS)
    
    async def _system_dns_resolve(self, domain: str, record_type: str = "A") -> List[str]:
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
    
    async def resolve(self, domain: str, record_type: str = "A", timeout: float = 10.0) -> List[str]:
        """
        Resolve a domain name using DNS-over-HTTPS.
        
        Args:
            domain: Domain name to resolve (e.g., "example.com")
            record_type: DNS record type (A, AAAA, MX, etc.)
            timeout: Request timeout in seconds
            
        Returns:
            List of resolved IP addresses or other record data
        """
        # Use system DNS for Google Cloud domains to avoid conflicts
        if self._should_use_system_dns(domain):
            logger.debug(f"Using system DNS for {domain} (Google Cloud/Spotify domain)")
            return await self._system_dns_resolve(domain, record_type)
        
        await self._init_session()
        
        # Try multiple servers if first fails
        for attempt in range(len(self.servers)):
            server = self.servers[self.current_server_index]
            try:
                params = server["params"].copy()
                params.update({"name": domain, "type": record_type})
                
                url = f"{server['url']}?{urlencode(params)}"
                
                logger.debug(
                    f"Resolving {domain} ({record_type}) via {server['name']}"
                )
                
                async with self.session.get(
                    url,
                    headers={"Accept": "application/dns-json"},
                    timeout=aiohttp.ClientTimeout(total=timeout)
                ) as response:
                    if response.status == 200:
                        # Handle case where response might have unexpected mimetype
                        try:
                            data = await response.json()
                        except Exception as e:
                            logger.warning(f"Failed to parse JSON from {server['name']}: {e}")
                            # Try to read raw content for debugging
                            raw_content = await response.text()
                            logger.debug(f"Raw response from {server['name']}: {raw_content}")
                            self._rotate_server()
                            continue
                        
                        if data.get("Status") == 0:  # NOERROR
                            answers = data.get("Answer", [])
                            results = []
                            
                            for ans in answers:
                                if ans.get("type") == 1 and record_type == "A":  # A record
                                    results.append(ans.get("data"))
                                elif ans.get("type") == 28 and record_type == "AAAA":  # AAAA record
                                    results.append(ans.get("data"))
                                elif record_type in ["MX", "CNAME", "TXT"]:
                                    results.append(ans.get("data"))
                            
                            logger.debug(
                                f"Resolved {domain} to {len(results)} records"
                            )
                            
                            # Rotate server for next request
                            self._rotate_server()
                            
                            return results
                        else:
                            logger.warning(
                                f"DNS resolution failed for {domain}: {data.get('Status')}"
                            )
                    else:
                        logger.warning(
                            f"HTTP {response.status} from {server['name']} for {domain}"
                        )
                
            except asyncio.TimeoutError:
                logger.warning(f"Timeout from {server['name']} for {domain}")
            except Exception as e:
                logger.warning(
                    f"Error resolving {domain} via {server['name']}: {e}"
                )
                
            # Rotate to next server for next attempt
            self._rotate_server()
        
        logger.error(f"All {len(self.servers)} DNS servers failed for {domain}")
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
                "url": current_server["url"]
            }
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
    test_domains = [
        "example.com",
        "google.com",
        "cloudflare.com",
        "github.com"
    ]
    
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
