#!/usr/bin/env python3
"""Run the x0tta6bl4 x402 paid API service."""

from __future__ import annotations

import argparse
import os

import uvicorn


def _disable_proxy_env_for_x402() -> None:
    """Avoid httpx failing on local socks:// proxy env values.

    x402's facilitator client uses httpx. Some local shells export
    ALL_PROXY=socks://127.0.0.1:... which httpx rejects unless extra SOCKS
    support and a socks5:// URL are configured. For this paid API we prefer a
    clear fail-closed service over inheriting an incompatible proxy.
    """

    if os.getenv("X0T_X402_KEEP_PROXY_ENV", "false").lower() in {"1", "true", "yes"}:
        return
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        os.environ.pop(name, None)
    os.environ.setdefault("NO_PROXY", "*")
    os.environ.setdefault("no_proxy", "*")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    _disable_proxy_env_for_x402()
    uvicorn.run(
        "src.sales.x402_paid_api:app",
        host=args.host,
        port=args.port,
        reload=False,
        access_log=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
