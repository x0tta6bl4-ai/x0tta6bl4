"""
Geo-Fencing for x0tta6bl4 Mesh.
===============================

Enforces DAO-governed transit rules based on node geographic jurisdiction.
Prevents traffic from transiting through restricted countries.
"""

import logging
from typing import List, Dict, Optional, Set

logger = logging.getLogger(__name__)

class GeoFencer:
    """
    Validates traffic transit against geographic restrictions.
    """
    
    def __init__(self, restricted_countries: Optional[Set[str]] = None):
        self.restricted_countries = restricted_countries or set()
        # Mock GeoIP cache: IP -> Country Code
        self._geo_cache: Dict[str, str] = {
            "8.8.8.8": "US",
            "1.1.1.1": "US",
            "89.125.1.107": "UA",
            "185.199.108.153": "NL",
            "95.161.224.1": "RU"
        }

    def set_restrictions(self, countries: List[str]):
        """Update restricted country list (DAO governed)."""
        self.restricted_countries = set(countries)
        logger.info(f"🛡️ Geo-Fencing updated. Restricted: {self.restricted_countries}")

    def get_country(self, ip_address: str) -> str:
        """Resolves country code for an IP (Mock/Cache)."""
        # In production, uses MaxMind/ip-api
        return self._geo_cache.get(ip_address, "UNKNOWN")

    def is_transit_allowed(self, source_ip: str, dest_ip: str) -> bool:
        """
        Checks if traffic between two IPs is allowed to transit 
        based on current restrictions.
        """
        src_country = self.get_country(source_ip)
        dst_country = self.get_country(dest_ip)
        
        if src_country in self.restricted_countries or dst_country in self.restricted_countries:
            logger.warning(f"🛑 Geo-Fence BLOCK: Transit between {src_country} and {dst_country} restricted.")
            return False
            
        return True

    def validate_node(self, ip_address: str) -> bool:
        """Check if a node's location is restricted."""
        country = self.get_country(ip_address)
        return country not in self.restricted_countries
