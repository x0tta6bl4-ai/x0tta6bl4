#!/usr/bin/env python3
"""
Example: Knowledge Storage v2.0 Usage
=====================================

Demonstrates how to use Knowledge Storage v2.0 with:
- IPFS integration
- Vector search
- MAPE-K integration
"""
import asyncio
import tempfile
from pathlib import Path

from src.storage.knowledge_storage_v2 import KnowledgeStorageV2
from src.storage.mapek_integration import MAPEKKnowledgeStorageAdapter


async def main():
    """Example usage of Knowledge Storage."""
    print("🚀 Knowledge Storage v2.0 Example\n")
    
    # Create temporary storage
    temp_dir = tempfile.mkdtemp()
    storage_path = Path(temp_dir)
    
    try:
        # Initialize Knowledge Storage (using mock IPFS for demo)
        storage = KnowledgeStorageV2(
            storage_path=storage_path,
            use_real_ipfs=False  # Set to True if IPFS daemon is running
        )
        
        print("✅ Knowledge Storage initialized\n")
        
        # Store some incidents
        print("📝 Storing incidents...")
        incidents = [
            {
                'id': 'incident-1',
                'timestamp': 1234567890.0,
                'anomaly_type': 'MEMORY_PRESSURE',
                'metrics': {'memory_percent': 95.0, 'cpu_percent': 60.0},
                'root_cause': 'High memory usage due to memory leak',
                'recovery_plan': 'Clear cache and restart service',
                'execution_result': {'success': True, 'duration': 2.5}
            },
            {
                'id': 'incident-2',
                'timestamp': 1234567900.0,
                'anomaly_type': 'CPU_PRESSURE',
                'metrics': {'cpu_percent': 90.0, 'memory_percent': 70.0},
                'root_cause': 'CPU intensive task running',
                'recovery_plan': 'Scale down workload',
                'execution_result': {'success': True, 'duration': 1.8}
            },
            {
                'id': 'incident-3',
                'timestamp': 1234567910.0,
                'anomaly_type': 'NETWORK_LOSS',
                'metrics': {'packet_loss_percent': 10.0, 'latency_ms': 200.0},
                'root_cause': 'Network congestion',
                'recovery_plan': 'Reroute traffic',
                'execution_result': {'success': True, 'duration': 3.2}
            }
        ]
        
        for incident in incidents:
            incident_id = await storage.store_incident(incident, "node-1")
            print(f"  ✅ Stored: {incident_id}")
        
        print()
        
        # Search for incidents
        print("🔍 Searching for incidents...")
        queries = [
            "memory pressure recovery",
            "CPU usage high",
            "network issue"
        ]
        
        for query in queries:
            results = await storage.search_incidents(query, k=5, threshold=0.7)
            print(f"  Query: '{query}' → Found {len(results)} results")
            if results:
                print(f"    Top result: {results[0].get('anomaly_type', 'N/A')}")
        
        print()
        
        # Get successful patterns
        print("📊 Getting successful patterns...")
        patterns = await storage.get_successful_patterns('MEMORY_PRESSURE')
        print(f"  Found {len(patterns)} successful patterns for MEMORY_PRESSURE")
        
        print()
        
        # Statistics
        print("📈 Storage Statistics:")
        stats = storage.get_stats()
        print(f"  Total incidents: {stats.get('total_incidents', 0)}")
        print(f"  IPFS available: {stats.get('ipfs_available', False)}")
        print(f"  Vector index: {stats.get('vector_index_stats', {})}")
        
        print()
        
        # MAPE-K Integration example
        print("🔄 MAPE-K Integration Example:")
        adapter = MAPEKKnowledgeStorageAdapter(storage, "node-1")
        
        # Record incident via adapter
        incident_id = adapter.record_incident_sync(
            metrics={'cpu_percent': 85.0, 'memory_percent': 80.0},
            issue='HIGH_CPU',
            action='Scale down',
            success=True,
            mttr=2.0
        )
        print(f"  ✅ Recorded via adapter: {incident_id}")
        
        # Search patterns
        results = adapter.search_patterns_sync("CPU pressure", k=3)
        print(f"  🔍 Found {len(results)} patterns")
        
        print("\n✅ Example completed successfully!")
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(temp_dir)
        print(f"\n🧹 Cleaned up temporary storage: {temp_dir}")


if __name__ == "__main__":
    asyncio.run(main())

