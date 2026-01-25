"""
eBPF Security Enhancements Module

Provides security hardening features for eBPF programs:
- Noise injection configuration for timing attack mitigation
- LRU map management for high concurrency
- Security monitoring and alerting
"""

import logging
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class NoiseLevel(Enum):
    """Noise injection levels for timing attack mitigation"""
    NONE = "none"           # No noise (not recommended for production)
    LOW = "low"             # 50-100ns noise
    MEDIUM = "medium"       # 50-200ns noise (recommended)
    HIGH = "high"           # 100-500ns noise (maximum security)


@dataclass
class NoiseConfig:
    """Configuration for noise injection"""
    enabled: bool = True
    min_ns: int = 50        # Minimum noise in nanoseconds
    max_ns: int = 200       # Maximum noise in nanoseconds
    level: NoiseLevel = NoiseLevel.MEDIUM


@dataclass
class LRUConfig:
    """Configuration for LRU maps"""
    max_entries: int = 1024
    eviction_threshold: float = 0.9  # Evict when 90% full
    monitoring_enabled: bool = True


class SecurityEnhancements:
    """
    Manages security enhancements for eBPF programs.
    
    Features:
    - Noise injection configuration
    - LRU map management
    - Security monitoring
    - Timing attack mitigation
    """
    
    def __init__(
        self,
        noise_config: Optional[NoiseConfig] = None,
        lru_config: Optional[LRUConfig] = None
    ):
        self.noise_config = noise_config or NoiseConfig()
        self.lru_config = lru_config or LRUConfig()
        self._map_usage_stats: Dict[str, Dict[str, int]] = {}
        
        logger.info(
            f"Security Enhancements initialized: "
            f"noise={self.noise_config.level.value}, "
            f"lru_max_entries={self.lru_config.max_entries}"
        )
    
    def get_noise_range(self) -> Tuple[int, int]:
        """
        Get noise injection range based on configured level.
        
        Returns:
            (min_ns, max_ns) tuple
        """
        if not self.noise_config.enabled:
            return (0, 0)
        
        level_ranges = {
            NoiseLevel.NONE: (0, 0),
            NoiseLevel.LOW: (50, 100),
            NoiseLevel.MEDIUM: (50, 200),
            NoiseLevel.HIGH: (100, 500),
        }
        
        if self.noise_config.level in level_ranges:
            return level_ranges[self.noise_config.level]
        
        # Use custom range if specified
        return (self.noise_config.min_ns, self.noise_config.max_ns)
    
    def configure_noise(self, level: NoiseLevel, min_ns: Optional[int] = None, max_ns: Optional[int] = None):
        """
        Configure noise injection level.
        
        Args:
            level: Noise level (LOW, MEDIUM, HIGH)
            min_ns: Optional custom minimum noise
            max_ns: Optional custom maximum noise
        """
        self.noise_config.level = level
        if min_ns is not None:
            self.noise_config.min_ns = min_ns
        if max_ns is not None:
            self.noise_config.max_ns = max_ns
        
        logger.info(f"Noise injection configured: {level.value} ({self.noise_config.min_ns}-{self.noise_config.max_ns}ns)")
    
    def check_lru_eviction(self, map_name: str, current_entries: int) -> bool:
        """
        Check if LRU map should trigger eviction.
        
        Args:
            map_name: Name of the map
            current_entries: Current number of entries
            
        Returns:
            True if eviction threshold exceeded
        """
        if map_name not in self._map_usage_stats:
            self._map_usage_stats[map_name] = {
                "max_entries": self.lru_config.max_entries,
                "current": 0,
                "evictions": 0
            }
        
        stats = self._map_usage_stats[map_name]
        stats["current"] = current_entries
        
        threshold = int(self.lru_config.max_entries * self.lru_config.eviction_threshold)
        
        if current_entries >= threshold:
            stats["evictions"] += 1
            if self.lru_config.monitoring_enabled:
                logger.warning(
                    f"⚠️ LRU map '{map_name}' near capacity: "
                    f"{current_entries}/{self.lru_config.max_entries} entries "
                    f"({current_entries/self.lru_config.max_entries*100:.1f}%)"
                )
            return True
        
        return False
    
    def get_map_stats(self, map_name: str) -> Optional[Dict[str, int]]:
        """
        Get statistics for a specific map.
        
        Args:
            map_name: Name of the map
            
        Returns:
            Dictionary with map statistics or None if not found
        """
        return self._map_usage_stats.get(map_name)
    
    def get_security_status(self) -> Dict[str, any]:
        """
        Get overall security status.
        
        Returns:
            Dictionary with security status information
        """
        noise_min, noise_max = self.get_noise_range()
        
        return {
            "noise_injection": {
                "enabled": self.noise_config.enabled,
                "level": self.noise_config.level.value,
                "range_ns": f"{noise_min}-{noise_max}",
            },
            "lru_maps": {
                "max_entries": self.lru_config.max_entries,
                "eviction_threshold": self.lru_config.eviction_threshold,
                "monitoring_enabled": self.lru_config.monitoring_enabled,
                "maps_tracked": len(self._map_usage_stats),
            },
            "map_stats": {
                name: stats for name, stats in self._map_usage_stats.items()
            }
        }


# Global instance
_security_enhancements: Optional[SecurityEnhancements] = None


def get_security_enhancements() -> SecurityEnhancements:
    """Get global SecurityEnhancements instance."""
    global _security_enhancements
    if _security_enhancements is None:
        _security_enhancements = SecurityEnhancements()
    return _security_enhancements


def configure_security(noise_level: NoiseLevel = NoiseLevel.MEDIUM):
    """
    Configure security enhancements globally.
    
    Args:
        noise_level: Noise injection level
    """
    enhancements = get_security_enhancements()
    enhancements.configure_noise(noise_level)
    logger.info(f"Global security configuration updated: noise={noise_level.value}")

