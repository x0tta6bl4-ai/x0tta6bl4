#!/usr/bin/env python3
"""
x0tta6bl4 Unified Pathfinder
============================================

Унифицированный pathfinder для k-дизъюнктных путей в mesh-сети.
Интегрирует Batman-adv topology с MeshRouter для отказоустойчивой маршрутизации.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple
from datetime import datetime
from enum import Enum
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

@dataclass
class PathMetrics:
    """Metrics for a computed path"""
    path: List[str]
    quality_score: float
    latency_ms: float
    throughput_mbps: float
    reliability: float
    computed_at: datetime = field(default_factory=datetime.now)
    
    def is_valid(self, ttl_seconds: int = 300) -> bool:
        return (datetime.now() - self.computed_at).total_seconds() < ttl_seconds

@dataclass
class NetworkEdge:
    """Represents an edge in the network graph"""
    source: str
    destination: str
    weight: float
    latency_ms: float
    throughput_mbps: float
    reliability: float
    
    def quality_score(self) -> float:
        return max(0, min(100, 100 - self.weight))

class UnifiedPathfinder:
    """Unified pathfinder for k-disjoint paths computation"""
    
    def __init__(self, node_id: str, k_disjoint: int = 3, cache_ttl: int = 300):
        self.node_id = node_id
        self.k_disjoint = k_disjoint
        self.cache_ttl = cache_ttl
        
        self.nodes: Set[str] = set()
        self.edges: Dict[Tuple[str, str], NetworkEdge] = {}
        self.path_cache: Dict[Tuple[str, str], List[PathMetrics]] = {}
        self.cache_timestamps: Dict[Tuple[str, str], datetime] = {}
        
        self.compute_count = 0
        self.cache_hits = 0
        self.cache_misses = 0
        
        logger.info(f"UnifiedPathfinder initialized for {node_id} (k={k_disjoint})")
    
    def add_node(self, node_id: str) -> None:
        self.nodes.add(node_id)
        self._invalidate_all_cache()
    
    def add_edge(self, edge: NetworkEdge) -> None:
        self.nodes.update([edge.source, edge.destination])
        self.edges[(edge.source, edge.destination)] = edge
        self.edges[(edge.destination, edge.source)] = NetworkEdge(
            source=edge.destination, destination=edge.source,
            weight=edge.weight, latency_ms=edge.latency_ms,
            throughput_mbps=edge.throughput_mbps, reliability=edge.reliability
        )
        self._invalidate_all_cache()
    
    def compute_k_disjoint_paths(self, source: str, destination: str, k: Optional[int] = None) -> List[PathMetrics]:
        if k is None:
            k = self.k_disjoint
            
        cache_key = (source, destination)
        
        if cached_paths := self._get_cached_paths(cache_key):
            return cached_paths
        
        paths = self._compute_disjoint_paths(source, destination, k)
        
        path_metrics = []
        for path in paths:
            metrics = self._compute_path_metrics(path)
            path_metrics.append(metrics)
        
        path_metrics.sort(key=lambda x: x.quality_score, reverse=True)
        
        self._update_cache(cache_key, path_metrics)
        self.compute_count += 1
        self.cache_misses += 1
        
        return path_metrics
    
    def get_failover_path(self, destination: str, failed_path: List[str]) -> Optional[PathMetrics]:
        cache_key = (self.node_id, destination)
        paths = self._get_cached_paths(cache_key)
        
        if not paths:
            paths = self.compute_k_disjoint_paths(self.node_id, destination)
        
        failed_edges = self._path_to_edges(failed_path)
        
        for path_metrics in paths:
            path_edges = self._path_to_edges(path_metrics.path)
            if not failed_edges.intersection(path_edges):
                return path_metrics
        
        return None
    
    def _compute_disjoint_paths(self, source: str, destination: str, k: int) -> List[List[str]]:
        if source not in self.nodes or destination not in self.nodes:
            return []
        
        if source == destination:
            return [[source]]
        
        paths = []
        used_edges: Set[Tuple[str, str]] = set()
        
        for i in range(k):
            path = self._find_shortest_path_avoiding_edges(source, destination, used_edges)
            if not path:
                break
            
            paths.append(path)
            
            for j in range(len(path) - 1):
                used_edges.add((path[j], path[j + 1]))
                used_edges.add((path[j + 1], path[j]))
        
        return paths
    
    def _find_shortest_path_avoiding_edges(self, source: str, destination: str, used_edges: Set[Tuple[str, str]]) -> List[str]:
        distances = {node: float('inf') for node in self.nodes}
        distances[source] = 0
        previous = {node: None for node in self.nodes}
        unvisited = set(self.nodes)
        
        while unvisited:
            current = min(unvisited, key=lambda n: distances[n])
            
            if distances[current] == float('inf'):
                break
            
            if current == destination:
                path = []
                node = destination
                while node is not None:
                    path.append(node)
                    node = previous[node]
                return list(reversed(path))
            
            for neighbor in self._get_neighbors(current):
                if neighbor in unvisited:
                    if (current, neighbor) in used_edges or (neighbor, current) in used_edges:
                        continue
                    
                    edge = self.edges.get((current, neighbor))
                    if edge:
                        new_distance = distances[current] + edge.weight
                        if new_distance < distances[neighbor]:
                            distances[neighbor] = new_distance
                            previous[neighbor] = current
            
            unvisited.remove(current)
        
        return []
    
    def _get_neighbors(self, node_id: str) -> List[str]:
        neighbors = []
        for (src, dst), edge in self.edges.items():
            if src == node_id and edge.reliability > 0.3:
                neighbors.append(dst)
        return neighbors
    
    def _compute_path_metrics(self, path: List[str]) -> PathMetrics:
        if len(path) < 2:
            return PathMetrics(path, 0.0, 0.0, 0.0, 0.0)
        
        total_latency = 0.0
        min_throughput = float('inf')
        total_reliability = 1.0
        
        for i in range(len(path) - 1):
            edge = self.edges.get((path[i], path[i + 1]))
            if edge:
                total_latency += edge.latency_ms
                min_throughput = min(min_throughput, edge.throughput_mbps)
                total_reliability *= edge.reliability
        
        latency_score = max(0, 100 - total_latency / 5)
        throughput_score = min(100, min_throughput / 10)
        reliability_score = total_reliability * 100
        
        quality_score = (latency_score + throughput_score + reliability_score) / 3
        
        return PathMetrics(
            path=path,
            quality_score=quality_score,
            latency_ms=total_latency,
            throughput_mbps=min_throughput,
            reliability=total_reliability
        )
    
    def _path_to_edges(self, path: List[str]) -> Set[Tuple[str, str]]:
        edges = set()
        for i in range(len(path) - 1):
            edges.add((path[i], path[i + 1]))
            edges.add((path[i + 1], path[i]))
        return edges
    
    def _get_cached_paths(self, cache_key: Tuple[str, str]) -> Optional[List[PathMetrics]]:
        if cache_key not in self.path_cache:
            return None
        
        if cache_key in self.cache_timestamps:
            age = (datetime.now() - self.cache_timestamps[cache_key]).total_seconds()
            if age < self.cache_ttl:
                self.cache_hits += 1
                return self.path_cache[cache_key]
        
        del self.path_cache[cache_key]
        if cache_key in self.cache_timestamps:
            del self.cache_timestamps[cache_key]
        
        return None
    
    def _update_cache(self, cache_key: Tuple[str, str], paths: List[PathMetrics]) -> None:
        self.path_cache[cache_key] = paths
        self.cache_timestamps[cache_key] = datetime.now()
    
    def _invalidate_all_cache(self) -> None:
        self.path_cache.clear()
        self.cache_timestamps.clear()
    
    def get_performance_metrics(self) -> Dict:
        return {
            "compute_count": self.compute_count,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hits / (self.cache_hits + self.cache_misses) if (self.cache_hits + self.cache_misses) > 0 else 0.0,
            "cached_paths": len(self.path_cache),
            "nodes": len(self.nodes),
            "edges": len(self.edges)
        }
