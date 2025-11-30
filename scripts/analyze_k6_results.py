import json
import sys
from pathlib import Path

def analyze_results(result_file):
    try:
        with open(result_file) as f:
            data = json.load(f)
    except Exception as e:
        print(f"❌ Error reading {result_file}: {e}")
        return
    
    metrics = data.get('metrics', {})
    
    print(f"\n{'='*60}")
    print(f"Results: {result_file}")
    print(f"{'='*60}\n")
    
    # HTTP metrics
    if 'http_req_duration' in metrics:
        duration = metrics['http_req_duration']
        # Check if 'values' exists (older k6) or if it's direct (newer k6 summary)
        if 'values' in duration:
            duration = duration['values']
            
        print(f"📊 HTTP Request Duration:")
        print(f"   P95: {duration.get('p(95)', 0):.2f}ms")
        print(f"   Max: {duration.get('max', 0):.2f}ms\n")
    
    # Request rate
    if 'http_reqs' in metrics:
        reqs = metrics['http_reqs']
        if 'values' in reqs:
            reqs = reqs['values']
        rate = reqs.get('rate', 0)
        print(f"🚀 Throughput: {rate:.2f} req/s\n")
    
    # Failure rate
    if 'failed_requests' in metrics:
        failures = metrics['failed_requests']
        if 'values' in failures:
            failures = failures['values']
        fail_rate = failures.get('rate', 0)
        print(f"❌ Failure Rate: {fail_rate*100:.2f}%\n")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python analyze_k6_results.py results/*.json")
        sys.exit(1)
    
    for result_file in sys.argv[1:]:
        analyze_results(result_file)
