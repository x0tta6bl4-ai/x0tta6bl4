"""x0tta6bl4 Command Line Interface."""

from __future__ import annotations

import sys


def main():
    """Main CLI entry point."""
    print("x0tta6bl4 v1.0.0")
    print("Usage:")
    print("  x0tta6bl4-server    Start FastAPI server")
    print("  x0tta6bl4-health    Check system health")
    print()
    print("For more information, see: https://docs.x0tta6bl4.dev")
    return 0


if __name__ == "__main__":
    sys.exit(main())
