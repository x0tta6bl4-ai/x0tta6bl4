#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
from pathlib import Path


def main() -> int:
    module_path = Path(__file__).with_name("vps_build_runtime_state.py")
    spec = importlib.util.spec_from_file_location("vps_build_runtime_state", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return int(module.main())


if __name__ == "__main__":
    raise SystemExit(main())
