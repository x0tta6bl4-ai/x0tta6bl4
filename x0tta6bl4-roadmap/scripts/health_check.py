#!/usr/bin/env python3
"""Kubernetes namespace health summary for x0tta6bl4.

Usage:
  python3 scripts/health_check.py --namespace mtls-demo --json

Outputs pod phase counts and readiness ratio.
"""
from __future__ import annotations
import argparse, json, subprocess, sys, datetime
from typing import Dict, Any

def kubectl_get_pods(namespace: str) -> Dict[str, Any]:
    try:
        out = subprocess.check_output([
            'kubectl','get','pods','-n',namespace,'-o','json'
        ], text=True)
    except subprocess.CalledProcessError as e:
        print(f"kubectl error: {e}", file=sys.stderr)
        return {}
    return json.loads(out)

def summarize(namespace: str) -> Dict[str, Any]:
    data = kubectl_get_pods(namespace)
    items = data.get('items', [])
    phases = {}
    containers_ready = 0
    containers_total = 0
    for pod in items:
        phase = pod.get('status', {}).get('phase', 'Unknown')
        phases[phase] = phases.get(phase, 0) + 1
        for cs in pod.get('status', {}).get('containerStatuses', []) or []:
            containers_total += 1
            if cs.get('ready'): containers_ready += 1
    return {
        'namespace': namespace,
        'timestamp': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'pod_counts': phases,
        'pods_total': len(items),
        'containers_total': containers_total,
        'containers_ready': containers_ready,
        'containers_ready_pct': round((containers_ready/containers_total*100),2) if containers_total else 0.0,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--namespace','-n', default='mtls-demo')
    ap.add_argument('--json', action='store_true', help='Print JSON only')
    args = ap.parse_args()
    summary = summarize(args.namespace)
    if args.json:
        print(json.dumps(summary, indent=2))
    else:
        print(f"Namespace: {summary['namespace']}")
        print(f"Timestamp: {summary['timestamp']}")
        print(f"Pods total: {summary['pods_total']}")
        for phase, count in summary['pod_counts'].items():
            print(f"  {phase}: {count}")
        print(f"Containers ready: {summary['containers_ready']} / {summary['containers_total']} ({summary['containers_ready_pct']}%)")
        if summary['pod_counts'].get('Running',0) == summary['pods_total'] and summary['pods_total']>0:
            print("✅ All pods running")
        else:
            print("⌛ Not all pods running yet")

if __name__ == '__main__':
    main()
