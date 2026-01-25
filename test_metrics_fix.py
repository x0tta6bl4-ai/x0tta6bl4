#!/usr/bin/env python3
"""Test script to verify metrics fix"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from src.monitoring.metrics import (
    get_metrics_registry,
    get_metrics,
    record_self_healing_event,
    record_mape_k_cycle,
    MetricsRegistry
)

def test_metrics_registry_singleton():
    """Test that metrics registry is a singleton"""
    print("Testing metrics registry singleton behavior...")
    
    # Get first instance
    registry1 = get_metrics_registry()
    print(f"First registry instance: {id(registry1)}")
    
    # Get second instance
    registry2 = get_metrics_registry()
    print(f"Second registry instance: {id(registry2)}")
    
    # Verify they are the same instance
    assert id(registry1) == id(registry2), "Metrics registry is not a singleton"
    print("✓ Metrics registry is a singleton")

def test_metrics_creation():
    """Test that metrics are created correctly"""
    print("\nTesting metrics creation...")
    
    registry = get_metrics_registry()
    
    # Check that metrics are initialized
    assert hasattr(registry, 'request_count'), "request_count metric not found"
    assert hasattr(registry, 'mapek_cycle_duration'), "mapek_cycle_duration metric not found"
    assert hasattr(registry, 'self_healing_events'), "self_healing_events metric not found"
    
    print("✓ All required metrics are created")

def test_metrics_recording():
    """Test recording metrics"""
    print("\nTesting metrics recording...")
    
    # Record some metrics
    record_self_healing_event('test_event', 'node-1')
    record_mape_k_cycle('monitor', 0.1)
    record_mape_k_cycle('analyze', 0.2)
    record_mape_k_cycle('plan', 0.3)
    record_mape_k_cycle('execute', 0.4)
    
    print("✓ Metrics recorded successfully")

def test_metrics_exposition():
    """Test metrics exposition"""
    print("\nTesting metrics exposition...")
    
    metrics = get_metrics()
    
    # Verify response type
    assert hasattr(metrics, 'body'), "MetricsResponse missing body attribute"
    assert hasattr(metrics, 'media_type'), "MetricsResponse missing media_type attribute"
    
    # Verify content type is Prometheus format
    assert metrics.media_type == "text/plain; version=0.0.4; charset=utf-8", \
        f"Invalid media type: {metrics.media_type}"
    
    # Verify body contains expected metrics
    body_str = metrics.body.decode('utf-8')
    
    # Check for MAPE-K cycle metrics
    assert 'x0tta6bl4_mapek_cycle_duration_seconds' in body_str, \
        "mapek_cycle_duration metric not exposed"
    
    # Check for self-healing events
    assert 'x0tta6bl4_self_healing_events_total' in body_str, \
        "self_healing_events metric not exposed"
    
    print("✓ Metrics exposed correctly in Prometheus format")

def test_registry_encapsulation():
    """Test that metrics are properly registered in the custom registry"""
    print("\nTesting metrics registry encapsulation...")
    
    import prometheus_client
    
    # Get the default registry
    default_registry = prometheus_client.REGISTRY
    
    # Check that our metrics are NOT in the default registry
    default_names = set()
    for collector in default_registry._collector_to_names:
        default_names.update(default_registry._collector_to_names[collector])
    
    assert 'x0tta6bl4_requests_total' not in default_names, \
        "Metrics should not be in default registry"
    assert 'x0tta6bl4_mapek_cycle_duration_seconds' not in default_names, \
        "Metrics should not be in default registry"
    
    print("✓ Metrics are properly encapsulated in custom registry")

if __name__ == "__main__":
    print("=== Testing Prometheus Metrics Fix ===\n")
    
    try:
        test_metrics_registry_singleton()
        test_metrics_creation()
        test_metrics_recording()
        test_metrics_exposition()
        test_registry_encapsulation()
        
        print("\n=== ALL TESTS PASSED ===\n")
        print("Metrics fix is working correctly!")
        print("Metrics are properly isolated in custom registry and accessible through API.")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        print(f"\nStack trace:\n{traceback.format_exc()}")
        sys.exit(1)