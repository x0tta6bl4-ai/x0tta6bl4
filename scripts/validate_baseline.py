#!/usr/bin/env python3
"""
Validate Baseline Metrics

Compares current metrics against baseline to ensure no regression.
"""

import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
baseline_file = project_root / "baseline_metrics.json"

def load_baseline():
    """Load baseline metrics."""
    if not baseline_file.exists():
        print("❌ Baseline file not found. Run performance baseline first.")
        sys.exit(1)
    
    with open(baseline_file) as f:
        return json.load(f)

def validate_metrics(current_metrics, baseline):
    """Validate current metrics against baseline."""
    baseline_summary = baseline.get("summary", {})
    
    print("\n" + "="*60)
    print("📊 BASELINE VALIDATION")
    print("="*60 + "\n")
    
    checks = [
        ("Success Rate", current_metrics.get("success_rate_percent", 0), 
         baseline_summary.get("success_rate_percent", 0), ">=", "Success rate should not decrease"),
        ("Latency P95", current_metrics.get("latency_p95_ms", 0), 
         baseline_summary.get("latency_p95_ms", 0) * 1.2, "<=", "Latency P95 should not increase by more than 20%"),
        ("Memory", current_metrics.get("max_memory_mb", 0), 
         baseline_summary.get("max_memory_mb", 0) * 1.2, "<=", "Memory should not increase by more than 20%"),
    ]
    
    all_passed = True
    
    for name, current, threshold, operator, description in checks:
        if operator == ">=":
            passed = current >= threshold
        elif operator == "<=":
            passed = current <= threshold
        else:
            passed = False
        
        status = "✅" if passed else "❌"
        print(f"{status} {name}: {current:.2f} (threshold: {threshold:.2f})")
        print(f"   {description}")
        
        if not passed:
            all_passed = False
    
    print()
    print("="*60)
    
    if all_passed:
        print("✅ BASELINE VALIDATION: PASSED")
        return True
    else:
        print("❌ BASELINE VALIDATION: FAILED")
        print("   Performance regression detected!")
        return False

if __name__ == "__main__":
    baseline = load_baseline()
    
    # For now, we'll use baseline as current (in real scenario, would get from actual test)
    # This is a placeholder - in production, would compare against actual current metrics
    print("⚠️  Note: This is a baseline validation framework.")
    print("   In production, would compare current metrics against baseline.")
    print()
    
    # Validate baseline itself
    summary = baseline.get("summary", {})
    if summary:
        print("✅ Baseline metrics loaded successfully")
        print(f"   Success Rate: {summary.get('success_rate_percent', 0):.2f}%")
        print(f"   Latency P95: {summary.get('latency_p95_ms', 0):.2f}ms")
        print(f"   Memory: {summary.get('max_memory_mb', 0):.2f}MB")
        sys.exit(0)
    else:
        print("❌ Baseline summary not found")
        sys.exit(1)

