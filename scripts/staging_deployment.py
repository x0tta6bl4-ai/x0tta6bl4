#!/usr/bin/env python3
"""
Staging Deployment Script for x0tta6bl4

Deploys application to staging environment and runs validation tests.
"""

import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import httpx

project_root = Path(__file__).parent.parent


def check_docker() -> bool:
    """Check if Docker is available."""
    try:
        result = subprocess.run(
            ["docker", "--version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False


def check_docker_compose() -> bool:
    """Check if Docker Compose is available."""
    try:
        result = subprocess.run(
            ["docker", "compose", "version"], capture_output=True, text=True, timeout=5
        )
        return result.returncode == 0
    except:
        return False


def deploy_staging_local() -> Dict[str, Any]:
    """Deploy to local staging environment using Docker Compose."""
    print("🚀 Deploying to staging (local Docker Compose)...")

    staging_dir = project_root / "staging"
    docker_compose_file = staging_dir / "docker-compose.staging.minimal.yml"

    if not docker_compose_file.exists():
        print(f"⚠️  Docker Compose file not found: {docker_compose_file}")
        print("   Creating minimal staging compose file...")
        create_minimal_compose_file(docker_compose_file)

    try:
        # Build and start
        print("   Building Docker image...")
        build_result = subprocess.run(
            [
                "docker",
                "build",
                "-t",
                "x0tta6bl4-app:staging",
                "-f",
                "Dockerfile.app",
                ".",
            ],
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if build_result.returncode != 0:
            return {"success": False, "error": f"Build failed: {build_result.stderr}"}

        print("   Starting services...")
        compose_result = subprocess.run(
            ["docker", "compose", "-f", str(docker_compose_file), "up", "-d"],
            cwd=staging_dir,
            capture_output=True,
            text=True,
            timeout=60,
        )

        if compose_result.returncode != 0:
            return {
                "success": False,
                "error": f"Compose failed: {compose_result.stderr}",
            }

        print("   ✅ Services started")
        return {"success": True}

    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Deployment timeout"}
    except Exception as e:
        return {"success": False, "error": str(e)}


def create_minimal_compose_file(path: Path):
    """Create minimal Docker Compose file for staging."""
    content = """version: '3.8'

services:
  control-plane:
    image: x0tta6bl4-app:staging
    container_name: x0tta6bl4-staging
    ports:
      - "8080:8080"
      - "9090:9090"
    environment:
      - NODE_ID=staging-node-01
      - ENVIRONMENT=staging
      - LOG_LEVEL=INFO
      - LD_LIBRARY_PATH=/usr/local/lib
      - OQS_BUILD_ONLY_LIB=ON
    restart: unless-stopped
    networks:
      - x0tta6bl4_staging
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 10s
      timeout: 5s
      retries: 3

networks:
  x0tta6bl4_staging:
    driver: bridge
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def wait_for_health(max_wait: int = 60) -> bool:
    """Wait for health endpoint to be ready."""
    print("⏳ Waiting for health endpoint...")

    url = "http://localhost:8080/health"
    start_time = time.time()

    while time.time() - start_time < max_wait:
        try:
            response = httpx.get(url, timeout=2)
            if response.status_code == 200:
                print("   ✅ Health endpoint ready")
                return True
        except:
            pass

        time.sleep(2)
        print(f"   Waiting... ({int(time.time() - start_time)}s)")

    print("   ❌ Health endpoint not ready")
    return False


def run_smoke_tests() -> Dict[str, Any]:
    """Run smoke tests."""
    print("\n🧪 Running smoke tests...")

    endpoints = [
        ("/health", "GET"),
        ("/mesh/peers", "GET"),
        ("/mesh/stats", "GET"),
    ]

    results = []
    all_passed = True

    for endpoint, method in endpoints:
        url = f"http://localhost:8080{endpoint}"
        try:
            start = time.time()
            response = httpx.request(method, url, timeout=5)
            elapsed = (time.time() - start) * 1000

            passed = response.status_code == 200
            all_passed = all_passed and passed

            status = "✅" if passed else "❌"
            print(
                f"   {status} {method} {endpoint}: {response.status_code} ({elapsed:.2f}ms)"
            )

            results.append(
                {
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": response.status_code,
                    "latency_ms": elapsed,
                    "passed": passed,
                }
            )
        except Exception as e:
            print(f"   ❌ {method} {endpoint}: ERROR - {e}")
            results.append(
                {
                    "endpoint": endpoint,
                    "method": method,
                    "status_code": 0,
                    "latency_ms": 0,
                    "passed": False,
                    "error": str(e),
                }
            )
            all_passed = False

    return {"all_passed": all_passed, "results": results}


def check_monitoring() -> Dict[str, Any]:
    """Check monitoring endpoints."""
    print("\n📊 Checking monitoring...")

    endpoints = [
        ("/metrics", "Prometheus metrics"),
    ]

    results = []
    all_passed = True

    for endpoint, description in endpoints:
        url = f"http://localhost:8080{endpoint}"
        try:
            response = httpx.get(url, timeout=5)
            passed = response.status_code == 200
            all_passed = all_passed and passed

            status = "✅" if passed else "❌"
            print(f"   {status} {description}: {response.status_code}")

            results.append(
                {
                    "endpoint": endpoint,
                    "description": description,
                    "status_code": response.status_code,
                    "passed": passed,
                }
            )
        except Exception as e:
            print(f"   ❌ {description}: ERROR - {e}")
            results.append(
                {
                    "endpoint": endpoint,
                    "description": description,
                    "status_code": 0,
                    "passed": False,
                    "error": str(e),
                }
            )
            all_passed = False

    return {"all_passed": all_passed, "results": results}


def main():
    """Main deployment function."""
    print("\n" + "=" * 60)
    print("🚀 STAGING DEPLOYMENT")
    print("=" * 60 + "\n")

    # Check prerequisites
    if not check_docker():
        print("❌ Docker not found. Please install Docker.")
        sys.exit(1)

    if not check_docker_compose():
        print("❌ Docker Compose not found. Please install Docker Compose.")
        sys.exit(1)

    # Deploy
    deploy_result = deploy_staging_local()
    if not deploy_result.get("success"):
        print(f"❌ Deployment failed: {deploy_result.get('error')}")
        sys.exit(1)

    # Wait for health
    if not wait_for_health(max_wait=60):
        print("❌ Health check failed")
        sys.exit(1)

    # Run smoke tests
    smoke_results = run_smoke_tests()
    if not smoke_results["all_passed"]:
        print("\n❌ Some smoke tests failed")
        sys.exit(1)

    # Check monitoring
    monitoring_results = check_monitoring()
    if not monitoring_results["all_passed"]:
        print("\n⚠️  Some monitoring endpoints failed (non-critical)")

    print("\n" + "=" * 60)
    print("✅ STAGING DEPLOYMENT: SUCCESS")
    print("=" * 60)
    print("\nNext steps:")
    print("  1. Run load test: python3 scripts/run_load_test.py")
    print("  2. Run chaos tests: python3 tests/chaos/staging_chaos_test.py")
    print("  3. Check logs: docker logs x0tta6bl4-staging")
    print()


if __name__ == "__main__":
    main()
