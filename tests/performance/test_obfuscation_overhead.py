"""
Performance Benchmark for Obfuscation Layer.
Measures latency overhead and CPU impact of different transports.
"""
import time
import os
import psutil
import statistics
from src.network.obfuscation import TransportManager
from src.network.batman.node_manager import NodeManager

def benchmark_transport(name: str, iterations: int = 1000):
    print(f"--- Benchmarking: {name} ---")
    
    # Setup
    transport = None
    if name != "none":
        if name == "xor":
            transport = TransportManager.create(name, key="benchmark")
        elif name == "faketls":
            transport = TransportManager.create(name, sni="benchmark.com")
        
    nm = NodeManager("bench-mesh", "bench-node", obfuscation_transport=transport)
    
    # 1. Latency Test (Serialization/Obfuscation time)
    latencies = []
    start_cpu = psutil.cpu_percent(interval=None)
    
    start_total = time.perf_counter()
    for _ in range(iterations):
        t0 = time.perf_counter()
        # We manually call the internal logic that does obfuscation
        # nm.send_heartbeat calls json.dumps -> obfuscate
        nm.send_heartbeat("target")
        t1 = time.perf_counter()
        latencies.append((t1 - t0) * 1000) # ms
        
    end_total = time.perf_counter()
    end_cpu = psutil.cpu_percent(interval=None)
    
    total_time = end_total - start_total
    avg_latency = statistics.mean(latencies)
    p95_latency = statistics.quantiles(latencies, n=20)[18] # 95th percentile approx
    
    print(f"Total Time: {total_time:.4f}s for {iterations} ops")
    print(f"Avg Latency: {avg_latency:.4f} ms")
    print(f"P95 Latency: {p95_latency:.4f} ms")
    print(f"CPU Usage Increase (approx): {end_cpu - start_cpu}%") # Very rough estimate
    print("")
    
    return avg_latency

if __name__ == "__main__":
    # Warmup
    psutil.cpu_percent(interval=1)
    
    print("Starting Obfuscation Benchmarks (1000 iterations)...\n")
    
    base = benchmark_transport("none")
    xor = benchmark_transport("xor")
    fake = benchmark_transport("faketls")
    
    print("--- Summary ---")
    print(f"Baseline (None): {base:.4f} ms")
    print(f"XOR Overhead:    {xor - base:.4f} ms (+{(xor/base - 1)*100:.1f}%)")
    print(f"FakeTLS Overhead:{fake - base:.4f} ms (+{(fake/base - 1)*100:.1f}%)")
