#!/usr/bin/env python3
"""
Performance Snapshot for x0tta6bl4 Pre-Deployment
Creates comprehensive performance baseline before staging deployment.
"""

import json
import time
import psutil
import subprocess
from datetime import datetime
from pathlib import Path

def get_system_metrics():
    """Get current system performance metrics."""
    return {
        "timestamp": datetime.now().isoformat(),
        "cpu": {
            "usage_percent": psutil.cpu_percent(interval=1),
            "cores": psutil.cpu_count(logical=False),
            "logical_cores": psutil.cpu_count(logical=True),
            "load_avg": list(psutil.getloadavg()),
            "frequency": psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        },
        "memory": {
            "total": psutil.virtual_memory().total,
            "available": psutil.virtual_memory().available,
            "percent": psutil.virtual_memory().percent,
            "used": psutil.virtual_memory().used,
            "free": psutil.virtual_memory().free
        },
        "disk": {
            "total": psutil.disk_usage('/').total,
            "used": psutil.disk_usage('/').used,
            "free": psutil.disk_usage('/').free,
            "percent": psutil.disk_usage('/').percent
        },
        "network": psutil.net_io_counters()._asdict() if psutil.net_io_counters() else None
    }

def get_docker_metrics():
    """Get Docker build metrics."""
    try:
        result = subprocess.run(
            ["docker", "system", "df", "--format", "{{json .}}"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            docker_data = []
            for line in lines:
                if line:
                    try:
                        docker_data.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
            return docker_data
    except Exception:
        pass
    return []

def get_project_metrics():
    """Get project-specific metrics."""
    project_root = Path(__file__).parent.parent
    
    # Count files
    python_files = len(list(project_root.rglob("*.py")))
    yaml_files = len(list(project_root.rglob("*.yaml"))) + len(list(project_root.rglob("*.yml")))
    json_files = len(list(project_root.rglob("*.json")))
    md_files = len(list(project_root.rglob("*.md")))
    
    # Count lines of code
    total_lines = 0
    for py_file in project_root.rglob("*.py"):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                total_lines += sum(1 for _ in f)
        except:
            pass
    
    return {
        "files": {
            "python_files": python_files,
            "yaml_files": yaml_files,
            "json_files": json_files,
            "markdown_files": md_files
        },
        "lines_of_code": total_lines,
        "directories": len([d for d in project_root.rglob("*") if d.is_dir()])
    }

def get_kubernetes_metrics():
    """Get Kubernetes cluster metrics."""
    try:
        result = subprocess.run(
            ["kubectl", "get", "nodes", "--context=kind-x0tta6bl4-staging", "-o", "json"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            nodes_data = json.loads(result.stdout)
            return {
                "cluster": "kind-x0tta6bl4-staging",
                "nodes": len(nodes_data.get("items", [])),
                "status": "available"
            }
    except Exception:
        pass
    return {"cluster": "kind-x0tta6bl4-staging", "status": "unavailable"}

def create_performance_snapshot():
    """Create comprehensive performance snapshot."""
    print("📊 Creating Performance Snapshot...")
    print("=" * 60)
    
    snapshot = {
        "snapshot_metadata": {
            "timestamp": datetime.now().isoformat(),
            "purpose": "Pre-deployment baseline for x0tta6bl4 v3.4.0",
            "environment": "staging-prep"
        },
        "system_metrics": get_system_metrics(),
        "docker_metrics": get_docker_metrics(),
        "project_metrics": get_project_metrics(),
        "kubernetes_metrics": get_kubernetes_metrics(),
        "performance_targets": {
            "pqc_handshake_p95": "<0.5ms",
            "api_response_p95": "<100ms",
            "memory_usage_max": "<2GB",
            "cpu_usage_max": "<80%",
            "error_rate": "<1%"
        }
    }
    
    # Save snapshot
    snapshot_file = Path(f"performance_snapshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(snapshot_file, 'w') as f:
        json.dump(snapshot, f, indent=2, default=str)
    
    print(f"✅ Performance snapshot saved: {snapshot_file}")
    
    # Print summary
    print("\n📋 Performance Summary:")
    print(f"   CPU Usage: {snapshot['system_metrics']['cpu']['usage_percent']:.1f}%")
    print(f"   Memory Usage: {snapshot['system_metrics']['memory']['percent']:.1f}%")
    print(f"   Load Average: {snapshot['system_metrics']['cpu']['load_avg'][0]:.2f}")
    print(f"   Python Files: {snapshot['project_metrics']['files']['python_files']}")
    print(f"   Lines of Code: {snapshot['project_metrics']['lines_of_code']:,}")
    print(f"   K8s Cluster: {snapshot['kubernetes_metrics']['status']}")
    
    return snapshot_file

if __name__ == "__main__":
    create_performance_snapshot()
