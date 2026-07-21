#!/usr/bin/env python3
"""
Build a V2RayN canary test bundle.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Build V2RayN canary bundle")
    parser.add_argument("--output", required=True, type=Path, help="Output zip path")
    args = parser.parse_args()

    test_config = {
        "v": "2",
        "ps": "Canary-Test",
        "add": "89.125.1.107",
        "port": "443",
        "id": "11111111-1111-1111-1111-111111111111",
        "aid": "0",
        "net": "tcp",
        "type": "none",
        "host": "",
        "path": "",
        "tls": "tls"
    }

    test_script = """#!/bin/bash
echo "Testing connectivity..."
curl -s --socks5 127.0.0.1:10808 https://google.com > /dev/null
if [ $? -eq 0 ]; then
    echo "Success!"
    exit 0
else
    echo "Failed!"
    exit 1
fi
"""

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(args.output, "w") as zf:
        zf.writestr("guiNConfig.json", json.dumps({"guiNConfig": [test_config]}, indent=2))
        zf.writestr("test_connectivity.sh", test_script)

    print(f"Canary bundle built at {args.output}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
