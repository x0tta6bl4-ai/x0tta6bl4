"""
Distributed Threat Intelligence Module for x0tta6bl4 Mesh.
Share and aggregate threat information across mesh nodes.

Implements:
- Threat Indicator sharing (IOCs)
- Reputation scoring
- Attack pattern detection
- Collaborative defense
- Privacy-preserving threat sharing (bloom filters)

Standards: STIX 2.1, TAXII 2.1 concepts
"""
import hashlib
import json
import time
import logging
from typing import Dict, List, Optional, Set, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class ThreatType(Enum):
    """Types of threats."""
    MALICIOUS_NODE = "malicious_node"
    DPI_BLOCK = "dpi_block"
    SYBIL_ATTACK = "sybil_attack"
    REPLAY_ATTACK = "replay_attack"
    DOS_ATTACK = "dos_attack"
    MITM_ATTEMPT = "mitm_attempt"
    CREDENTIAL_THEFT = "credential_theft"
    TRAFFIC_ANALYSIS = "traffic_analysis"
    NETWORK_PROBE = "network_probe"
    PROTOCOL_VIOLATION = "protocol_violation"


class ThreatSeverity(Enum):
    """Severity levels."""
    INFO = 1
    LOW = 2
    MEDIUM = 3
    HIGH = 4
    CRITICAL = 5


class IndicatorType(Enum):
    """Types of Indicators of Compromise (IOCs)."""
    IP_ADDRESS = "ip"
    NODE_ID = "node_id"
    PUBLIC_KEY = "public_key"
    PATTERN = "pattern"
    BEHAVIOR = "behavior"
    DID = "did"


@dataclass
class ThreatIndicator:
    """Indicator of Compromise (IOC)."""
    id: str
    type: IndicatorType
    value: str
    threat_type: ThreatType
    severity: ThreatSeverity
    confidence: float  # 0.0 - 1.0
    first_seen: float
    last_seen: float
    reporter_id: str
    description: str = ""
    ttl: int = 86400  # 24 hours default
    corroborations: int = 0  # Number of confirmations
    
    def is_expired(self) -> bool:
        """Check if indicator is expired."""
        return time.time() > self.first_seen + self.ttl
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "value": self.value,
            "threat_type": self.threat_type.value,
            "severity": self.severity.value,
            "confidence": self.confidence,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "reporter_id": self.reporter_id,
            "description": self.description,
            "corroborations": self.corroborations
        }


@dataclass
class ThreatReport:
    """Aggregated threat report."""
    id: str
    title: str
    threat_type: ThreatType
    severity: ThreatSeverity
    indicators: List[ThreatIndicator]
    affected_nodes: List[str]
    mitigation: str
    created: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "threat_type": self.threat_type.value,
            "severity": self.severity.value,
            "indicators": [i.to_dict() for i in self.indicators],
            "affected_nodes": self.affected_nodes,
            "mitigation": self.mitigation,
            "created": self.created
        }


class BloomFilter:
    """
    Privacy-preserving Bloom Filter for sharing threat indicators.
    Allows checking membership without revealing the set.
    """
    
    def __init__(self, size: int = 10000, num_hashes: int = 7):
        self.size = size
        self.num_hashes = num_hashes
        self.bits = [False] * size
    
    def _hashes(self, item: str) -> List[int]:
        """Generate multiple hash indices for item."""
        indices = []
        for i in range(self.num_hashes):
            h = hashlib.sha256(f"{item}:{i}".encode()).digest()
            idx = int.from_bytes(h[:4], 'big') % self.size
            indices.append(idx)
        return indices
    
    def add(self, item: str) -> None:
        """Add item to filter."""
        for idx in self._hashes(item):
            self.bits[idx] = True
    
    def contains(self, item: str) -> bool:
        """Check if item might be in filter (may have false positives)."""
        return all(self.bits[idx] for idx in self._hashes(item))
    
    def merge(self, other: 'BloomFilter') -> None:
        """Merge another bloom filter into this one."""
        if self.size != other.size:
            raise ValueError("Cannot merge filters of different sizes")
        for i in range(self.size):
            self.bits[i] = self.bits[i] or other.bits[i]
    
    def to_bytes(self) -> bytes:
        """Serialize to bytes for transmission."""
        byte_array = bytearray((self.size + 7) // 8)
        for i, bit in enumerate(self.bits):
            if bit:
                byte_array[i // 8] |= (1 << (i % 8))
        return bytes(byte_array)
    
    @classmethod
    def from_bytes(cls, data: bytes, size: int = 10000, num_hashes: int = 7) -> 'BloomFilter':
        """Deserialize from bytes."""
        bf = cls(size, num_hashes)
        for i in range(min(size, len(data) * 8)):
            if data[i // 8] & (1 << (i % 8)):
                bf.bits[i] = True
        return bf


class ThreatIntelligenceEngine:
    """
    Core threat intelligence engine for mesh node.
    Collects, shares, and acts on threat information.
    """
    
    def __init__(self, node_id: str):
        self.node_id = node_id
        self.indicators: Dict[str, ThreatIndicator] = {}
        self.reports: Dict[str, ThreatReport] = {}
        self.blocked_entities: Set[str] = set()
        self.reputation_scores: Dict[str, float] = defaultdict(lambda: 0.5)
        self.bloom_filter = BloomFilter()
        self._lock = threading.RLock()
        
        # Attack detection state
        self.connection_counts: Dict[str, List[float]] = defaultdict(list)
        self.failed_auths: Dict[str, List[float]] = defaultdict(list)
        
        logger.info(f"ThreatIntelligenceEngine initialized for {node_id}")
    
    def report_indicator(
        self,
        indicator_type: IndicatorType,
        value: str,
        threat_type: ThreatType,
        severity: ThreatSeverity,
        confidence: float = 0.7,
        description: str = "",
        ttl: int = 86400
    ) -> ThreatIndicator:
        """
        Report a new threat indicator.
        
        Args:
            indicator_type: Type of indicator
            value: The indicator value
            threat_type: Type of threat
            severity: Severity level
            confidence: Confidence score (0-1)
            description: Human-readable description
            ttl: Time to live in seconds
        """
        with self._lock:
            indicator_id = hashlib.sha256(
                f"{indicator_type.value}:{value}:{threat_type.value}".encode()
            ).hexdigest()[:16]
            
            now = time.time()
            
            if indicator_id in self.indicators:
                # Update existing indicator
                existing = self.indicators[indicator_id]
                existing.last_seen = now
                existing.corroborations += 1
                existing.confidence = min(1.0, existing.confidence + 0.1)
                logger.info(f"Updated indicator {indicator_id}, corroborations: {existing.corroborations}")
                return existing
            
            indicator = ThreatIndicator(
                id=indicator_id,
                type=indicator_type,
                value=value,
                threat_type=threat_type,
                severity=severity,
                confidence=confidence,
                first_seen=now,
                last_seen=now,
                reporter_id=self.node_id,
                description=description,
                ttl=ttl
            )
            
            self.indicators[indicator_id] = indicator
            self.bloom_filter.add(value)
            
            # Auto-block high severity threats
            if severity.value >= ThreatSeverity.HIGH.value and confidence >= 0.8:
                self._auto_block(indicator)
            
            logger.info(f"New indicator reported: {indicator_id} ({threat_type.value})")
            return indicator
    
    def _auto_block(self, indicator: ThreatIndicator) -> None:
        """Automatically block entity based on indicator."""
        self.blocked_entities.add(indicator.value)
        self.reputation_scores[indicator.value] = 0.0
        logger.warning(f"Auto-blocked entity: {indicator.value}")
    
    def is_blocked(self, entity: str) -> bool:
        """Check if entity is blocked."""
        return entity in self.blocked_entities
    
    def check_indicator(self, value: str) -> bool:
        """
        Quick check if value might be a known threat indicator.
        Uses bloom filter for O(1) check with possible false positives.
        """
        return self.bloom_filter.contains(value)
    
    def get_indicator(self, value: str) -> Optional[ThreatIndicator]:
        """Get full indicator details if exists."""
        for indicator in self.indicators.values():
            if indicator.value == value and not indicator.is_expired():
                return indicator
        return None
    
    def receive_indicators(self, indicators: List[Dict[str, Any]], source_node: str) -> int:
        """
        Receive threat indicators from peer node.
        
        Args:
            indicators: List of indicator dicts
            source_node: Node that sent the indicators
            
        Returns:
            Number of new indicators added
        """
        added = 0
        source_reputation = self.reputation_scores[source_node]
        
        for ind_dict in indicators:
            try:
                # Adjust confidence based on source reputation
                confidence = ind_dict.get("confidence", 0.5) * source_reputation
                
                indicator = self.report_indicator(
                    indicator_type=IndicatorType(ind_dict["type"]),
                    value=ind_dict["value"],
                    threat_type=ThreatType(ind_dict["threat_type"]),
                    severity=ThreatSeverity(ind_dict["severity"]),
                    confidence=confidence,
                    description=ind_dict.get("description", f"From {source_node}"),
                    ttl=ind_dict.get("ttl", 86400)
                )
                
                if indicator.corroborations == 0:
                    added += 1
                    
            except Exception as e:
                logger.error(f"Failed to process indicator: {e}")
        
        logger.info(f"Received {len(indicators)} indicators from {source_node}, added {added} new")
        return added
    
    def get_shareable_indicators(self, max_count: int = 100) -> List[Dict[str, Any]]:
        """
        Get indicators to share with peers.
        Only shares high-confidence, non-expired indicators.
        """
        with self._lock:
            shareable = []
            for indicator in sorted(
                self.indicators.values(),
                key=lambda x: (x.severity.value, x.confidence),
                reverse=True
            ):
                if not indicator.is_expired() and indicator.confidence >= 0.6:
                    shareable.append(indicator.to_dict())
                    if len(shareable) >= max_count:
                        break
            return shareable
    
    def get_bloom_filter(self) -> bytes:
        """Get serialized bloom filter for efficient sharing."""
        return self.bloom_filter.to_bytes()
    
    def merge_bloom_filter(self, filter_bytes: bytes) -> None:
        """Merge received bloom filter."""
        other = BloomFilter.from_bytes(filter_bytes)
        self.bloom_filter.merge(other)
    
    def detect_dos_attack(self, source: str) -> Optional[ThreatIndicator]:
        """
        Detect DoS attack based on connection rate.
        
        Args:
            source: Source identifier
            
        Returns:
            ThreatIndicator if attack detected
        """
        now = time.time()
        window = 60  # 1 minute window
        threshold = 100  # connections per minute
        
        # Clean old entries
        self.connection_counts[source] = [
            t for t in self.connection_counts[source] 
            if now - t < window
        ]
        self.connection_counts[source].append(now)
        
        count = len(self.connection_counts[source])
        
        if count > threshold:
            return self.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value=source,
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=min(1.0, count / threshold / 2),
                description=f"DoS detected: {count} connections in {window}s"
            )
        return None
    
    def detect_brute_force(self, source: str) -> Optional[ThreatIndicator]:
        """
        Detect brute force attack based on failed authentication attempts.
        
        Args:
            source: Source identifier
            
        Returns:
            ThreatIndicator if attack detected
        """
        now = time.time()
        window = 300  # 5 minute window
        threshold = 10  # failed attempts
        
        # Clean old entries
        self.failed_auths[source] = [
            t for t in self.failed_auths[source]
            if now - t < window
        ]
        self.failed_auths[source].append(now)
        
        count = len(self.failed_auths[source])
        
        if count >= threshold:
            return self.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value=source,
                threat_type=ThreatType.CREDENTIAL_THEFT,
                severity=ThreatSeverity.HIGH,
                confidence=0.9,
                description=f"Brute force detected: {count} failed auths in {window}s"
            )
        return None
    
    def update_reputation(self, entity: str, delta: float) -> float:
        """
        Update entity reputation score.
        
        Args:
            entity: Entity identifier
            delta: Change in reputation (-1.0 to 1.0)
            
        Returns:
            New reputation score
        """
        with self._lock:
            current = self.reputation_scores[entity]
            new_score = max(0.0, min(1.0, current + delta))
            self.reputation_scores[entity] = new_score
            
            # Auto-block if reputation drops too low
            if new_score < 0.1:
                self.blocked_entities.add(entity)
                logger.warning(f"Entity {entity} blocked due to low reputation: {new_score}")
            
            return new_score
    
    def get_reputation(self, entity: str) -> float:
        """Get reputation score for entity."""
        return self.reputation_scores[entity]
    
    def create_report(
        self,
        title: str,
        threat_type: ThreatType,
        severity: ThreatSeverity,
        indicator_ids: List[str],
        affected_nodes: List[str],
        mitigation: str
    ) -> ThreatReport:
        """Create aggregated threat report."""
        report_id = hashlib.sha256(
            f"{title}:{time.time()}".encode()
        ).hexdigest()[:16]
        
        indicators = [
            self.indicators[iid] 
            for iid in indicator_ids 
            if iid in self.indicators
        ]
        
        report = ThreatReport(
            id=report_id,
            title=title,
            threat_type=threat_type,
            severity=severity,
            indicators=indicators,
            affected_nodes=affected_nodes,
            mitigation=mitigation
        )
        
        self.reports[report_id] = report
        logger.info(f"Created threat report: {report_id}")
        return report
    
    def cleanup_expired(self) -> int:
        """Remove expired indicators."""
        with self._lock:
            expired = [
                iid for iid, ind in self.indicators.items()
                if ind.is_expired()
            ]
            for iid in expired:
                del self.indicators[iid]
            
            if expired:
                logger.info(f"Cleaned up {len(expired)} expired indicators")
            return len(expired)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get threat intelligence statistics."""
        with self._lock:
            by_severity = defaultdict(int)
            by_type = defaultdict(int)
            
            for ind in self.indicators.values():
                if not ind.is_expired():
                    by_severity[ind.severity.name] += 1
                    by_type[ind.threat_type.name] += 1
            
            return {
                "total_indicators": len(self.indicators),
                "blocked_entities": len(self.blocked_entities),
                "by_severity": dict(by_severity),
                "by_type": dict(by_type),
                "bloom_filter_size": self.bloom_filter.size,
                "reports": len(self.reports)
            }
