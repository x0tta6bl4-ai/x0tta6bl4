#!/usr/bin/env python3
import json
import os
import glob
from datetime import datetime

def generate_bundle():
    results_dir = "ebpf/prod/results"
    output_dir = "docs/verification"
    
    # Find the latest benchmark result
    list_of_files = glob.glob(f'{results_dir}/benchmark-*.json')
    if not list_of_files:
        print(f"No benchmark results found in {results_dir}")
        return

    latest_file = max(list_of_files, key=os.path.getctime)
    print(f"Processing latest benchmark: {latest_file}")

    with open(latest_file, 'r') as f:
        data = json.load(f)

    ts = data.get("timestamp", "unknown")
    iface = data.get("iface", "unknown")
    pps = data.get("measured_pps", 0)
    target = data.get("target_pps", 5000000)
    passed = data.get("pass", False)
    status_emoji = "🟢" if passed else "🔴"
    
    version = ts.replace("T", "_").replace("Z", "").replace(":", "")
    bundle_path = os.path.join(output_dir, f"validation_bundle_{version}.md")

    content = f"""# x0tta6bl4 Formal Validation Bundle {version}

**Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Status**: {status_emoji} {'PASSED' if passed else 'FAILED'}
**Component**: eBPF / XDP Mesh Filter

## 📊 Benchmark Summary
- **Interface**: `{iface}`
- **Measured PPS**: {pps}
- **Target PPS**: {target}
- **Artifact**: `{latest_file}`

## 🛠 Engineering Context
- **Source**: Automated CI/CD Performance Gate
- **Mode**: {'Live Benchmark' if pps > 0 else 'Plan-Only / Baseline'}

## 📋 Runbook Reference
1. Verify via: `ebpf/prod/verify-local.sh --iface {iface} --dump-status`
2. Raw data: `{latest_file}`
"""

    os.makedirs(output_dir, exist_ok=True)
    with open(bundle_path, 'w') as f:
        f.write(content)
    
    print(f"✅ Validation bundle created: {bundle_path}")

if __name__ == "__main__":
    generate_bundle()
