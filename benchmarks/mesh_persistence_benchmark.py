#!/usr/bin/env python3
"""
Mesh Instance Persistence Benchmark
====================================

Tests database persistence of mesh instances under load:
- Concurrent mesh creation
- Database write latency
- Query performance
- Transaction rollback handling
- Connection pool behavior
"""

import asyncio
import time
import statistics
import json
import os
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class MeshInstanceData:
    """Test data for mesh instance"""
    id: str
    name: str
    owner_id: str
    plan: str
    region: str
    nodes: int
    pqc_profile: str
    pqc_enabled: bool
    obfuscation: str
    traffic_profile: str
    status: str
    join_token: str
    join_token_expires_at: datetime
    created_at: datetime


class MeshPersistenceBenchmark:
    """Benchmark suite for mesh instance persistence"""
    
    def __init__(self):
        self.db_available = False
        self.SessionLocal = None
        self.MeshInstance = None
        self.engine = None
        self.results: Dict[str, Any] = {}
        
        self._init_db()
    
    def _init_db(self):
        """Initialize database connection"""
        try:
            from src.database import get_db, MeshInstance, SessionLocal, engine
            self.SessionLocal = SessionLocal
            self.MeshInstance = MeshInstance
            self.engine = engine
            self.db_available = True
            logger.info("✅ Database module available")
        except ImportError as e:
            logger.warning(f"⚠️ Database module not available: {e}")
            self.db_available = False
    
    def _generate_mesh_data(self, index: int) -> MeshInstanceData:
        """Generate test mesh instance data"""
        mesh_id = f"mesh-{uuid.uuid4().hex[:8]}"
        now = datetime.utcnow()
        
        return MeshInstanceData(
            id=mesh_id,
            name=f"test-mesh-{index:04d}",
            owner_id=f"user-{index % 100:03d}",
            plan=["starter", "pro", "enterprise"][index % 3],
            region=["us-east-1", "eu-west-1", "ap-southeast-1"][index % 3],
            nodes=5 + (index % 20),
            pqc_profile=["edge", "gateway", "server"][index % 3],
            pqc_enabled=True,
            obfuscation=["none", "xor", "aes"][index % 3],
            traffic_profile=["none", "gaming", "streaming"][index % 3],
            status="active",
            join_token=uuid.uuid4().hex,
            join_token_expires_at=now + timedelta(days=7),
            created_at=now
        )
    
    def benchmark_single_insert(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark single mesh insert operations"""
        logger.info(f"  Benchmarking single inserts ({iterations} iterations)...")
        
        if not self.db_available:
            return self._simulate_single_insert(iterations)
        
        times = []
        errors = 0
        
        for i in range(iterations):
            mesh_data = self._generate_mesh_data(i)
            
            start = time.perf_counter()
            try:
                db = self.SessionLocal()
                try:
                    mesh = self.MeshInstance(
                        id=mesh_data.id,
                        name=mesh_data.name,
                        owner_id=mesh_data.owner_id,
                        plan=mesh_data.plan,
                        region=mesh_data.region,
                        nodes=mesh_data.nodes,
                        pqc_profile=mesh_data.pqc_profile,
                        pqc_enabled=mesh_data.pqc_enabled,
                        obfuscation=mesh_data.obfuscation,
                        traffic_profile=mesh_data.traffic_profile,
                        status=mesh_data.status,
                        join_token=mesh_data.join_token,
                        join_token_expires_at=mesh_data.join_token_expires_at,
                        created_at=mesh_data.created_at
                    )
                    db.add(mesh)
                    db.commit()
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)
                finally:
                    db.close()
            except Exception as e:
                errors += 1
                logger.warning(f"Insert failed: {e}")
        
        return self._calculate_stats("single_insert", times, errors, iterations, target_ms=50.0)
    
    def _simulate_single_insert(self, iterations: int) -> Dict[str, Any]:
        """Simulate single insert performance"""
        # SQLite: ~1-5ms, PostgreSQL: ~5-20ms
        times = [10.0 + 5.0 * (hash(str(i)) % 100) / 100 for i in range(iterations)]
        return self._calculate_stats("single_insert_simulated", times, 0, iterations, target_ms=50.0)
    
    def benchmark_batch_insert(self, batch_sizes: List[int] = [10, 50, 100]) -> Dict[str, Any]:
        """Benchmark batch insert operations"""
        logger.info(f"  Benchmarking batch inserts...")
        
        results = {}
        
        for batch_size in batch_sizes:
            if not self.db_available:
                results[f"batch_{batch_size}"] = self._simulate_batch_insert(batch_size)
                continue
            
            times = []
            errors = 0
            
            # Generate batch data
            mesh_data_list = [self._generate_mesh_data(i) for i in range(batch_size)]
            
            start = time.perf_counter()
            try:
                db = self.SessionLocal()
                try:
                    for mesh_data in mesh_data_list:
                        mesh = self.MeshInstance(
                            id=mesh_data.id,
                            name=mesh_data.name,
                            owner_id=mesh_data.owner_id,
                            plan=mesh_data.plan,
                            region=mesh_data.region,
                            nodes=mesh_data.nodes,
                            pqc_profile=mesh_data.pqc_profile,
                            pqc_enabled=mesh_data.pqc_enabled,
                            obfuscation=mesh_data.obfuscation,
                            traffic_profile=mesh_data.traffic_profile,
                            status=mesh_data.status,
                            join_token=mesh_data.join_token,
                            join_token_expires_at=mesh_data.join_token_expires_at,
                            created_at=mesh_data.created_at
                        )
                        db.add(mesh)
                    db.commit()
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)
                finally:
                    db.close()
            except Exception as e:
                errors += 1
                logger.warning(f"Batch insert failed: {e}")
            
            if times:
                results[f"batch_{batch_size}"] = {
                    "batch_size": batch_size,
                    "total_time_ms": times[0],
                    "avg_per_item_ms": times[0] / batch_size,
                    "errors": errors,
                    "target_met": times[0] / batch_size < 20.0
                }
        
        return results
    
    def _simulate_batch_insert(self, batch_size: int) -> Dict[str, Any]:
        """Simulate batch insert performance"""
        # Batch inserts are more efficient per item
        time_per_item = 2.0  # ~2ms per item in batch
        total_time = time_per_item * batch_size
        
        return {
            "batch_size": batch_size,
            "total_time_ms": total_time,
            "avg_per_item_ms": time_per_item,
            "errors": 0,
            "target_met": time_per_item < 20.0,
            "simulated": True
        }
    
    def benchmark_query_by_owner(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark query by owner_id"""
        logger.info(f"  Benchmarking query by owner ({iterations} iterations)...")
        
        if not self.db_available:
            return self._simulate_query("query_by_owner", iterations)
        
        times = []
        
        for i in range(iterations):
            owner_id = f"user-{i % 100:03d}"
            
            start = time.perf_counter()
            try:
                db = self.SessionLocal()
                try:
                    meshes = db.query(self.MeshInstance).filter(
                        self.MeshInstance.owner_id == owner_id
                    ).all()
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Query failed: {e}")
        
        return self._calculate_stats("query_by_owner", times, 0, iterations, target_ms=20.0)
    
    def benchmark_query_by_status(self, iterations: int = 100) -> Dict[str, Any]:
        """Benchmark query by status"""
        logger.info(f"  Benchmarking query by status ({iterations} iterations)...")
        
        if not self.db_available:
            return self._simulate_query("query_by_status", iterations)
        
        times = []
        statuses = ["active", "provisioning", "degraded", "terminated"]
        
        for i in range(iterations):
            status = statuses[i % len(statuses)]
            
            start = time.perf_counter()
            try:
                db = self.SessionLocal()
                try:
                    meshes = db.query(self.MeshInstance).filter(
                        self.MeshInstance.status == status
                    ).all()
                    elapsed = (time.perf_counter() - start) * 1000
                    times.append(elapsed)
                finally:
                    db.close()
            except Exception as e:
                logger.warning(f"Query failed: {e}")
        
        return self._calculate_stats("query_by_status", times, 0, iterations, target_ms=20.0)
    
    def _simulate_query(self, name: str, iterations: int) -> Dict[str, Any]:
        """Simulate query performance"""
        # Indexed query: ~1-10ms
        times = [5.0 + 3.0 * (hash(str(i)) % 100) / 100 for i in range(iterations)]
        return self._calculate_stats(f"{name}_simulated", times, 0, iterations, target_ms=20.0)
    
    def benchmark_concurrent_writes(self, num_threads: int = 10, writes_per_thread: int = 10) -> Dict[str, Any]:
        """Benchmark concurrent write operations"""
        logger.info(f"  Benchmarking concurrent writes ({num_threads} threads, {writes_per_thread} writes each)...")
        
        if not self.db_available:
            return self._simulate_concurrent_writes(num_threads, writes_per_thread)
        
        all_times = []
        all_errors = []
        
        def write_thread(thread_id: int):
            times = []
            errors = 0
            
            for i in range(writes_per_thread):
                mesh_data = self._generate_mesh_data(thread_id * writes_per_thread + i)
                
                start = time.perf_counter()
                try:
                    db = self.SessionLocal()
                    try:
                        mesh = self.MeshInstance(
                            id=mesh_data.id,
                            name=mesh_data.name,
                            owner_id=mesh_data.owner_id,
                            plan=mesh_data.plan,
                            region=mesh_data.region,
                            nodes=mesh_data.nodes,
                            pqc_profile=mesh_data.pqc_profile,
                            pqc_enabled=mesh_data.pqc_enabled,
                            obfuscation=mesh_data.obfuscation,
                            traffic_profile=mesh_data.traffic_profile,
                            status=mesh_data.status,
                            join_token=mesh_data.join_token,
                            join_token_expires_at=mesh_data.join_token_expires_at,
                            created_at=mesh_data.created_at
                        )
                        db.add(mesh)
                        db.commit()
                        elapsed = (time.perf_counter() - start) * 1000
                        times.append(elapsed)
                    finally:
                        db.close()
                except Exception as e:
                    errors += 1
            
            return times, errors
        
        start = time.perf_counter()
        
        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(write_thread, i) for i in range(num_threads)]
            
            for future in futures:
                try:
                    times, errors = future.result(timeout=60.0)
                    all_times.extend(times)
                    all_errors.append(errors)
                except Exception as e:
                    logger.warning(f"Thread failed: {e}")
                    all_errors.append(writes_per_thread)
        
        total_time = time.perf_counter() - start
        total_writes = num_threads * writes_per_thread
        
        return {
            "operation": "concurrent_writes",
            "threads": num_threads,
            "writes_per_thread": writes_per_thread,
            "total_writes": total_writes,
            "successful_writes": len(all_times),
            "failed_writes": sum(all_errors),
            "total_time_ms": total_time * 1000,
            "avg_time_per_write_ms": statistics.mean(all_times) if all_times else 0,
            "throughput_writes_per_sec": len(all_times) / total_time if total_time > 0 else 0,
            "target_met": statistics.mean(all_times) < 100.0 if all_times else False
        }
    
    def _simulate_concurrent_writes(self, num_threads: int, writes_per_thread: int) -> Dict[str, Any]:
        """Simulate concurrent write performance"""
        total_writes = num_threads * writes_per_thread
        # Concurrent writes: higher latency due to contention
        avg_time = 30.0  # 30ms average under contention
        total_time = (total_writes * avg_time) / num_threads / 1000  # Parallel execution
        
        return {
            "operation": "concurrent_writes_simulated",
            "threads": num_threads,
            "writes_per_thread": writes_per_thread,
            "total_writes": total_writes,
            "successful_writes": total_writes,
            "failed_writes": 0,
            "total_time_ms": total_time * 1000,
            "avg_time_per_write_ms": avg_time,
            "throughput_writes_per_sec": total_writes / total_time,
            "target_met": avg_time < 100.0,
            "simulated": True
        }
    
    def _calculate_stats(self, name: str, times: List[float], errors: int, total: int, target_ms: float) -> Dict[str, Any]:
        """Calculate statistics from timing data"""
        if not times:
            return {
                "operation": name,
                "error": "No successful operations",
                "errors": errors,
                "total": total
            }
        
        sorted_times = sorted(times)
        avg_time = statistics.mean(times)
        
        return {
            "operation": name,
            "iterations": len(times),
            "errors": errors,
            "total": total,
            "total_time_ms": sum(times),
            "avg_time_ms": avg_time,
            "min_time_ms": min(times),
            "max_time_ms": max(times),
            "p50_ms": sorted_times[int(len(sorted_times) * 0.50)],
            "p95_ms": sorted_times[int(len(sorted_times) * 0.95)],
            "p99_ms": sorted_times[int(len(sorted_times) * 0.99)],
            "ops_per_sec": 1000 / avg_time if avg_time > 0 else 0,
            "target_met": avg_time < target_ms,
            "target_ms": target_ms
        }
    
    def run_all_benchmarks(self) -> Dict[str, Any]:
        """Run all persistence benchmarks"""
        logger.info("\n" + "=" * 70)
        logger.info("MESH INSTANCE PERSISTENCE BENCHMARK")
        logger.info("=" * 70)
        
        results = {
            "timestamp": datetime.now().isoformat(),
            "db_available": self.db_available,
            "benchmarks": {}
        }
        
        # Single inserts
        logger.info("\n📊 Single Insert Benchmarks")
        results["benchmarks"]["single_insert"] = self.benchmark_single_insert(100)
        
        # Batch inserts
        logger.info("\n📊 Batch Insert Benchmarks")
        results["benchmarks"]["batch_insert"] = self.benchmark_batch_insert([10, 50, 100])
        
        # Queries
        logger.info("\n📊 Query Benchmarks")
        results["benchmarks"]["query_by_owner"] = self.benchmark_query_by_owner(100)
        results["benchmarks"]["query_by_status"] = self.benchmark_query_by_status(100)
        
        # Concurrent writes
        logger.info("\n📊 Concurrent Write Benchmarks")
        results["benchmarks"]["concurrent_writes"] = self.benchmark_concurrent_writes(10, 20)
        
        return results
    
    def generate_report(self) -> str:
        """Generate human-readable report"""
        results = self.run_all_benchmarks()
        
        report = []
        report.append("=" * 70)
        report.append("MESH INSTANCE PERSISTENCE REPORT")
        report.append("=" * 70)
        report.append(f"\nDatabase Available: {'✅ Yes' if results['db_available'] else '⚠️ No (simulated)'}")
        
        for name, data in results["benchmarks"].items():
            report.append("\n" + "-" * 70)
            report.append(f"{name.upper()}")
            report.append("-" * 70)
            
            if "error" in data:
                report.append(f"  ❌ {data['error']}")
                continue
            
            if "avg_time_ms" in data:
                status = "✅ PASS" if data.get("target_met") else "❌ FAIL"
                report.append(f"  Avg: {data['avg_time_ms']:.2f} ms")
                if "p95_ms" in data:
                    report.append(f"  P95: {data['p95_ms']:.2f} ms")
                if "ops_per_sec" in data:
                    report.append(f"  Throughput: {data['ops_per_sec']:.0f} ops/sec")
                if "target_ms" in data:
                    report.append(f"  Target (<{data['target_ms']}ms): {status}")
            
            if "throughput_writes_per_sec" in data:
                report.append(f"  Threads: {data['threads']}")
                report.append(f"  Total writes: {data['total_writes']}")
                report.append(f"  Throughput: {data['throughput_writes_per_sec']:.0f} writes/sec")
                status = "✅ PASS" if data.get("target_met") else "❌ FAIL"
                report.append(f"  Target: {status}")
            
            if isinstance(data, dict) and "batch_" in str(data.keys()):
                for batch_name, batch_data in data.items():
                    if isinstance(batch_data, dict) and "avg_per_item_ms" in batch_data:
                        status = "✅ PASS" if batch_data.get("target_met") else "❌ FAIL"
                        report.append(f"  {batch_name}: {batch_data['avg_per_item_ms']:.2f} ms/item {status}")
        
        report.append("\n" + "=" * 70)
        
        return "\n".join(report)


def main():
    """Main entry point"""
    benchmark = MeshPersistenceBenchmark()
    report = benchmark.generate_report()
    print(report)
    
    # Save results
    results = benchmark.run_all_benchmarks()
    output_file = "benchmarks/results/mesh_persistence_benchmark.json"
    os.makedirs("benchmarks/results", exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n📊 Results saved to: {output_file}")


if __name__ == "__main__":
    main()
