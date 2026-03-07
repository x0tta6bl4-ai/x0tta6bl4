
import asyncio
import httpx
import time
import json
import statistics
from datetime import datetime

ENDPOINTS = [
    "/health",
    "/api/v1/maas/marketplace/search",
    "/status"
]
BASE_URL = "http://localhost:8080"
CONCURRENT_REQUESTS = 10
DURATION_SECONDS = 10

async def measure_endpoint(client, path):
    latencies = []
    start_time = time.time()
    count = 0
    errors = 0
    
    while time.time() - start_time < DURATION_SECONDS:
        req_start = time.time()
        try:
            resp = await client.get(path)
            if resp.status_code == 200:
                latencies.append((time.time() - req_start) * 1000)
            else:
                errors += 1
        except Exception:
            errors += 1
        count += 1
    
    return {
        "path": path,
        "total_requests": count,
        "errors": errors,
        "avg_ms": statistics.mean(latencies) if latencies else 0,
        "p95_ms": statistics.quantiles(latencies, n=20)[18] if len(latencies) > 20 else 0,
        "rps": count / DURATION_SECONDS
    }

async def main():
    print(f"🚀 Starting Performance Snapshot (Duration: {DURATION_SECONDS}s, Concurrency: {CONCURRENT_REQUESTS})")
    
    async with httpx.AsyncClient(base_url=BASE_URL, timeout=10.0, trust_env=False) as client:
        tasks = [measure_endpoint(client, path) for path in ENDPOINTS]
        results = await asyncio.gather(*tasks)
    
    baseline = {
        "timestamp": datetime.now().isoformat(),
        "environment": "development-light",
        "results": results
    }
    
    print(json.dumps(baseline, indent=2))
    with open("PERFORMANCE_BASELINE.json", "w") as f:
        json.dump(baseline, f, indent=2)
    print("\n✅ Baseline saved to PERFORMANCE_BASELINE.json")

if __name__ == "__main__":
    asyncio.run(main())
