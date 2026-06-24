#!/usr/bin/env python3
"""Save an Agent402 API key into the local secret file without printing it."""

from __future__ import annotations

import getpass
import json
from pathlib import Path


def main() -> int:
    key = getpass.getpass("Agent402 API key: ").strip()
    if not key:
        print("empty key; nothing written")
        return 2
    path = Path(".tmp/non-bounty/agent402_identity.secret.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"api_key": key}, indent=2) + "\n", encoding="utf-8")  # lgtm[py/clear-text-storage-sensitive-data]  # nosec - chmod 0o600, local CI use only
    path.chmod(0o600)
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
