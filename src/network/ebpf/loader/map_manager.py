"""
eBPF Map Manager - Map operations and statistics

Handles:
- Reading eBPF maps via bpftool
- Updating map entries
- Collecting statistics
"""

import json
import logging
import subprocess
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class EBPFMapManager:
    """
    eBPF Map Manager - handles map operations.
    
    Responsibilities:
    - Read map entries via bpftool
    - Update map entries
    - Collect statistics from maps
    
    Example:
        >>> manager = EBPFMapManager()
        >>> stats = manager.get_stats("packet_stats")
    """
    
    def __init__(self):
        """Initialize the map manager."""
        self._bpftool_available = self._check_bpftool()
        logger.info(f"EBPFMapManager initialized (bpftool={self._bpftool_available})")
    
    def _check_bpftool(self) -> bool:
        """Check if bpftool is available."""
        try:
            result = subprocess.run(
                ["bpftool", "version"],
                capture_output=True,
                timeout=2
            )
            return result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False
    
    def read_map(self, map_name: str) -> Dict[str, any]:
        """
        Read eBPF map entries.
        
        Args:
            map_name: Name of the map to read
            
        Returns:
            Dict with map data
        """
        if not self._bpftool_available:
            logger.warning("bpftool not available, cannot read map")
            return {}
        
        try:
            result = subprocess.run(
                ["bpftool", "map", "dump", "name", map_name, "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                logger.warning(f"bpftool map dump failed: {result.stderr}")
                return {}
            
            data = json.loads(result.stdout)
            
            # Parse map data
            parsed = {}
            if isinstance(data, list):
                for entry in data:
                    key = entry.get("key")
                    value = entry.get("value")
                    
                    # Convert key to string
                    if isinstance(key, list):
                        key_str = "_".join(str(k) for k in key)
                    else:
                        key_str = str(key)
                    
                    parsed[key_str] = value
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse bpftool output: {e}")
            return {}
        except subprocess.TimeoutExpired:
            logger.error(f"bpftool map dump timed out for {map_name}")
            return {}
        except Exception as e:
            logger.error(f"Error reading map {map_name}: {e}")
            return {}
    
    def update_entry(
        self, 
        map_name: str, 
        key: str, 
        value: str
    ) -> bool:
        """
        Update an entry in an eBPF map.
        
        Args:
            map_name: Name of the map
            key: Entry key
            value: Entry value
            
        Returns:
            True if update successful
        """
        if not self._bpftool_available:
            logger.warning("bpftool not available, cannot update map")
            return False
        
        try:
            cmd = [
                "bpftool", "map", "update",
                "name", map_name,
                "key", key,
                "value", value,
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode == 0:
                logger.debug(f"Updated map {map_name}: {key} -> {value}")
                return True
            else:
                logger.warning(f"Failed to update map: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error(f"bpftool map update timed out")
            return False
        except Exception as e:
            logger.error(f"Error updating map {map_name}: {e}")
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get packet statistics from eBPF maps.
        
        Reads from packet_stats map if available.
        
        Returns:
            Dict with keys: total_packets, passed_packets, dropped_packets, forwarded_packets
        """
        stats = {
            "total_packets": 0,
            "passed_packets": 0,
            "dropped_packets": 0,
            "forwarded_packets": 0,
        }
        
        map_data = self.read_map("packet_stats")
        
        for key, value in map_data.items():
            try:
                key_int = int(key) if isinstance(key, (int, str)) else 0
                value_int = int(value) if isinstance(value, (int, str)) else 0
                
                if key_int == 0:
                    stats["total_packets"] = value_int
                elif key_int == 1:
                    stats["passed_packets"] = value_int
                elif key_int == 2:
                    stats["dropped_packets"] = value_int
                elif key_int == 3:
                    stats["forwarded_packets"] = value_int
            except (ValueError, TypeError):
                continue
        
        return stats
    
    def update_routes(self, routes: Dict[str, str]) -> bool:
        """
        Update mesh routing table in eBPF map.
        
        Args:
            routes: Dict mapping destination IP to next hop interface index
            
        Returns:
            True if all updates successful
        """
        if not self._bpftool_available:
            logger.warning("bpftool not available, cannot update routes")
            return False
        
        success = True
        for dest_ip, next_hop_if in routes.items():
            if not self.update_entry("mesh_routes", dest_ip, next_hop_if):
                success = False
        
        if success:
            logger.info(f"Updated {len(routes)} routes in eBPF map")
        
        return success
    
    def list_maps(self) -> List[Dict]:
        """
        List all eBPF maps.
        
        Returns:
            List of map information dicts
        """
        if not self._bpftool_available:
            return []
        
        try:
            result = subprocess.run(
                ["bpftool", "map", "list", "--json"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            
            if result.returncode != 0:
                return []
            
            return json.loads(result.stdout)
            
        except (json.JSONDecodeError, subprocess.TimeoutExpired):
            return []
