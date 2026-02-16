#!/usr/bin/env python3
"""
Dependency Health Check Script

Checks availability of all dependencies and reports status.
Can be used in CI/CD pipelines or for manual verification.
"""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.dependency_health import get_dependency_health_checker


def main():
    """Main entry point"""
    checker = get_dependency_health_checker()
    health = checker.get_health_status()

    # Print JSON output
    print(json.dumps(health, indent=2))

    # Exit with error code if unhealthy
    if not checker.is_healthy():
        print(
            "\n❌ System is UNHEALTHY - critical dependencies missing!", file=sys.stderr
        )
        sys.exit(1)
    else:
        degraded = checker.get_degraded_features()
        if degraded:
            print(
                f"\n⚠️  System is HEALTHY but {len(degraded)} features are degraded:",
                file=sys.stderr,
            )
            for feature in degraded:
                print(f"   - {feature}", file=sys.stderr)
        else:
            print(
                "\n✅ System is HEALTHY - all dependencies available", file=sys.stderr
            )
        sys.exit(0)


if __name__ == "__main__":
    main()
