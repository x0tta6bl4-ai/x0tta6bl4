#!/usr/bin/env bash
set -euo pipefail

DURATION_SECONDS="${DURATION_SECONDS:-180}"
CONCURRENCY="${CONCURRENCY:-12}"
REQUEST_TIMEOUT_SECONDS="${REQUEST_TIMEOUT_SECONDS:-5.0}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-}"

if [[ -z "$APP_PORT" ]]; then
  for candidate in 38080 39080 40080 41080 42080 43080; do
    if command -v ss >/dev/null 2>&1; then
      if ss -ltn 2>/dev/null | awk '{print $4}' | grep -Eq "(^|[:])${candidate}$"; then
        continue
      fi
    fi
    APP_PORT="$candidate"
    break
  done
  APP_PORT="${APP_PORT:-39080}"
fi

BASE_URL="${BASE_URL:-http://${APP_HOST}:${APP_PORT}}"
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-240}"
MAX_ERROR_RATE_PERCENT="${MAX_ERROR_RATE_PERCENT:-2.0}"
MAX_SCENARIO_P95_MS="${MAX_SCENARIO_P95_MS:-1200}"
SCENARIOS_CSV="${SCENARIOS_CSV:-marketplace_search,telemetry_heartbeat,node_heartbeat}"
MESH_ID="${MESH_ID:-mesh-load-profile}"
NODE_ID="${NODE_ID:-node-load-profile-001}"
START_LOCAL_API="${START_LOCAL_API:-true}"
PROFILE_DB_PATH="${PROFILE_DB_PATH:-}"
RESET_PROFILE_DB="${RESET_PROFILE_DB:-true}"
KEEP_PROFILE_DB="${KEEP_PROFILE_DB:-false}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$REPO_ROOT/docs/operations}"

if [[ -z "$PROFILE_DB_PATH" ]]; then
  PROFILE_DB_PATH="$REPO_ROOT/test_maas_load_profile.db"
fi

PROFILE_DATABASE_URL="sqlite:///$PROFILE_DB_PATH"

TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TIMESTAMP_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RAW_JSON="$REPORT_DIR/maas_api_load_scenarios_${TIMESTAMP_ID}.json"
REPORT_MD="$REPORT_DIR/maas_api_load_scenarios_${TIMESTAMP_ID}.md"
LATEST_JSON="$REPORT_DIR/MAAS_API_LOAD_SCENARIOS_LATEST.json"
LATEST_MD="$REPORT_DIR/MAAS_API_LOAD_SCENARIOS_LATEST.md"
APP_LOG="${APP_LOG:-/tmp/maas_api_load_scenarios_${TIMESTAMP_ID}.log}"

EXIT_GATE_FAIL=2
EXIT_CONFIG=3
EXIT_STARTUP=4

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() {
  echo -e "${GREEN}[INFO]${NC}  $*"
}

warn() {
  echo -e "${YELLOW}[WARN]${NC}  $*"
}

error() {
  local message="$1"
  local code="${2:-1}"
  echo -e "${RED}[ERROR]${NC} ${message}" >&2
  exit "${code}"
}

validate_positive_integer() {
  local value="$1"
  local name="$2"
  if ! [[ "$value" =~ ^[0-9]+$ ]] || [[ "$value" -le 0 ]]; then
    error "${name} must be a positive integer (got '${value}')" "${EXIT_CONFIG}"
  fi
}

validate_positive_number() {
  local value="$1"
  local name="$2"
  if ! python3 - "$value" "$name" <<'PY'
import sys
value = sys.argv[1]
name = sys.argv[2]
try:
    parsed = float(value)
except ValueError:
    print(f"{name} must be a positive number (got {value!r})", file=sys.stderr)
    raise SystemExit(1)
if parsed <= 0:
    print(f"{name} must be > 0 (got {parsed})", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    error "Invalid numeric config for ${name}" "${EXIT_CONFIG}"
  fi
}

validate_non_negative_number() {
  local value="$1"
  local name="$2"
  if ! python3 - "$value" "$name" <<'PY'
import sys
value = sys.argv[1]
name = sys.argv[2]
try:
    parsed = float(value)
except ValueError:
    print(f"{name} must be a non-negative number (got {value!r})", file=sys.stderr)
    raise SystemExit(1)
if parsed < 0:
    print(f"{name} must be >= 0 (got {parsed})", file=sys.stderr)
    raise SystemExit(1)
PY
  then
    error "Invalid numeric config for ${name}" "${EXIT_CONFIG}"
  fi
}

cleanup() {
  if [[ -n "${APP_PID:-}" ]] && kill -0 "$APP_PID" >/dev/null 2>&1; then
    kill "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  fi
  if [[ "${KEEP_PROFILE_DB,,}" != "true" ]] && [[ -f "$PROFILE_DB_PATH" ]]; then
    rm -f "$PROFILE_DB_PATH" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

mkdir -p "$REPORT_DIR"

required_bins=(python3 curl)
if [[ "${START_LOCAL_API,,}" == "true" ]]; then
  required_bins+=(uvicorn)
fi

for bin in "${required_bins[@]}"; do
  command -v "$bin" >/dev/null 2>&1 || error "$bin not found in PATH" "${EXIT_CONFIG}"
done

validate_positive_integer "$DURATION_SECONDS" "DURATION_SECONDS"
validate_positive_integer "$CONCURRENCY" "CONCURRENCY"
validate_positive_integer "$STARTUP_TIMEOUT_SECONDS" "STARTUP_TIMEOUT_SECONDS"
validate_positive_number "$REQUEST_TIMEOUT_SECONDS" "REQUEST_TIMEOUT_SECONDS"
validate_non_negative_number "$MAX_ERROR_RATE_PERCENT" "MAX_ERROR_RATE_PERCENT"
validate_positive_number "$MAX_SCENARIO_P95_MS" "MAX_SCENARIO_P95_MS"

if [[ ! "$BASE_URL" =~ ^https?:// ]]; then
  error "BASE_URL must start with http:// or https:// (got '${BASE_URL}')" "${EXIT_CONFIG}"
fi

if [[ -z "${SCENARIOS_CSV// }" ]]; then
  error "SCENARIOS_CSV must not be empty" "${EXIT_CONFIG}"
fi

if [[ "${RESET_PROFILE_DB,,}" == "true" ]]; then
  rm -f "$PROFILE_DB_PATH"
fi

if [[ "${START_LOCAL_API,,}" == "true" ]]; then
  info "Preparing isolated profile database with migrations: $PROFILE_DB_PATH"
  # Run Alembic migrations on the isolated DB
  DATABASE_URL="$PROFILE_DATABASE_URL" bash -lc "cd '$REPO_ROOT' && alembic upgrade head" >/dev/null 2>&1 || {
      warn "Alembic migrations failed; falling back to Base.metadata.create_all()"
      DATABASE_URL="$PROFILE_DATABASE_URL" python3 - <<'PY'
from src.database import create_tables
create_tables()
PY
  }

  info "Seeding isolated profile database: $PROFILE_DB_PATH"
  DATABASE_URL="$PROFILE_DATABASE_URL" python3 - "$MESH_ID" "$NODE_ID" <<'PY'
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

from src.database import (
    MarketplaceListing,
    MeshInstance,
    MeshNode,
    SessionLocal,
    User,
    create_tables,
)

mesh_id = sys.argv[1]
node_id = sys.argv[2]
owner_id = "load-owner"
renter_id = "load-renter"
listing_id = f"lst-load-{node_id[-8:]}".replace("_", "-")


def utc_now_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

create_tables()
db = SessionLocal()
try:
    owner = db.query(User).filter(User.id == owner_id).first()
    if owner is None:
        owner = User(
            id=owner_id,
            email="load-owner@local.test",
            role="operator",
            plan="enterprise",
            password_hash="load-test-password-hash",
            api_key="load-api-key",
        )
        db.add(owner)
    else:
        owner.email = owner.email or "load-owner@local.test"
        owner.role = owner.role or "operator"
        owner.plan = owner.plan or "enterprise"
        owner.password_hash = owner.password_hash or "load-test-password-hash"
        owner.api_key = "load-api-key"

    renter = db.query(User).filter(User.id == renter_id).first()
    if renter is None:
        renter = User(
            id=renter_id,
            email="load-renter@local.test",
            role="user",
            plan="enterprise",
            password_hash="load-test-password-hash",
        )
        db.add(renter)
    else:
        renter.email = renter.email or "load-renter@local.test"
        renter.role = renter.role or "user"
        renter.plan = renter.plan or "enterprise"
        renter.password_hash = renter.password_hash or "load-test-password-hash"

    mesh = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if mesh is None:
        mesh = MeshInstance(
            id=mesh_id,
            name="Load Profile Mesh",
            owner_id=owner_id,
            plan="enterprise",
            region="global",
            nodes=1,
            join_token="load-token",
            join_token_expires_at=utc_now_naive() + timedelta(days=1),
            status="active",
        )
        db.add(mesh)
    else:
        mesh.owner_id = owner_id
        mesh.join_token = "load-token"
        mesh.join_token_expires_at = utc_now_naive() + timedelta(days=1)
        mesh.status = "active"

    node = db.query(MeshNode).filter(MeshNode.id == node_id).first()
    if node is None:
        node = MeshNode(
            id=node_id,
            mesh_id=mesh_id,
            device_class="edge",
            status="approved",
            acl_profile="default",
            last_seen=utc_now_naive(),
        )
        db.add(node)
    else:
        node.mesh_id = mesh_id
        node.device_class = node.device_class or "edge"
        node.status = "approved"
        node.last_seen = utc_now_naive()

    listing = db.query(MarketplaceListing).filter(MarketplaceListing.node_id == node_id).first()
    if listing is None:
        listing = MarketplaceListing(
            id=listing_id,
            owner_id=owner_id,
            node_id=node_id,
            region="global",
            price_per_hour=125,
            price_token_per_hour=1.25,
            currency="USD",
            bandwidth_mbps=100,
            status="available",
            renter_id=None,
            mesh_id=None,
            created_at=utc_now_naive(),
        )
        db.add(listing)
    else:
        listing.owner_id = owner_id
        listing.region = listing.region or "global"
        listing.price_per_hour = listing.price_per_hour or 125
        listing.price_token_per_hour = listing.price_token_per_hour or 1.25
        listing.currency = "USD"
        listing.bandwidth_mbps = listing.bandwidth_mbps or 100
        listing.status = "available"
        listing.renter_id = None
        listing.mesh_id = None

    db.commit()
    print(
        json.dumps(
            {
                "mesh_id": mesh_id,
                "node_id": node_id,
                "listing_id": listing.id,
                "owner_id": owner_id,
                "renter_id": renter_id,
            }
        )
    )
finally:
    db.close()
PY

  info "Starting API (full mode for Marketplace/Telemetry/Nodes) on ${APP_HOST}:${APP_PORT}"
  bash -lc "cd '$REPO_ROOT' && DATABASE_URL='$PROFILE_DATABASE_URL' TESTING=true MAAS_LIGHT_MODE=false X0TTA6BL4_FAIL_OPEN_STARTUP=true uvicorn src.core.app:app --host '$APP_HOST' --port '$APP_PORT'" >"$APP_LOG" 2>&1 &
  APP_PID=$!

  deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
  until curl -fsS "${BASE_URL}/health/ready" >/dev/null 2>&1; do
    if ! kill -0 "$APP_PID" >/dev/null 2>&1; then
      tail -n 120 "$APP_LOG" >&2 || true
      error "API process exited before readiness check passed" "${EXIT_STARTUP}"
    fi
    if (( SECONDS >= deadline )); then
      tail -n 120 "$APP_LOG" >&2 || true
      error "API failed to become ready at ${BASE_URL}/health/ready" "${EXIT_STARTUP}"
    fi
    sleep 1
  done
  info "API is ready (pid=${APP_PID})"
else
  info "START_LOCAL_API=false; using existing API at ${BASE_URL}"
fi

info "Running MaaS load scenarios (duration=${DURATION_SECONDS}s, concurrency=${CONCURRENCY}, scenarios=${SCENARIOS_CSV})"
python3 - "$BASE_URL" "$DURATION_SECONDS" "$CONCURRENCY" "$MESH_ID" "$NODE_ID" "$RAW_JSON" "$SCENARIOS_CSV" "$REQUEST_TIMEOUT_SECONDS" "$EXIT_CONFIG" <<'PY'
from __future__ import annotations

import json
import random
import threading
import time
import urllib.error
import urllib.request
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any
import sys

base_url = sys.argv[1].rstrip("/")
duration = int(sys.argv[2])
concurrency = int(sys.argv[3])
mesh_id = sys.argv[4]
node_id = sys.argv[5]
raw_json_path = Path(sys.argv[6])
scenarios_csv = sys.argv[7]
request_timeout_seconds = float(sys.argv[8])
config_exit_code = int(sys.argv[9])

random.seed(42)
deadline = time.time() + duration
lock = threading.Lock()

scenario_catalog = {
    "marketplace_search": {
        "name": "marketplace_search",
        "method": "GET",
        "path": "/api/v1/maas/marketplace/search?currency=USD&min_bandwidth=10",
    },
    "telemetry_heartbeat": {
        "name": "telemetry_heartbeat",
        "method": "POST",
        "path": "/api/v1/maas/heartbeat",
    },
    "node_heartbeat": {
        "name": "node_heartbeat",
        "method": "POST",
        "path": f"/api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat",
    },
}

scenario_names = [item.strip() for item in scenarios_csv.split(",") if item.strip()]
if not scenario_names:
    print("No scenarios selected (SCENARIOS_CSV is empty)", file=sys.stderr)
    raise SystemExit(config_exit_code)

unknown_names = sorted(set(scenario_names) - set(scenario_catalog))
if unknown_names:
    print(
        f"Unknown scenarios in SCENARIOS_CSV: {', '.join(unknown_names)}. "
        f"Supported: {', '.join(sorted(scenario_catalog))}",
        file=sys.stderr,
    )
    raise SystemExit(config_exit_code)

scenario_definitions = [scenario_catalog[name] for name in scenario_names]

scenario_metrics: dict[str, dict[str, Any]] = {
    item["name"]: {
        "requests_total": 0,
        "requests_ok": 0,
        "requests_error": 0,
        "latencies_ms": [],
        "errors_by_reason": defaultdict(int),
    }
    for item in scenario_definitions
}
totals = {"requests_total": 0, "requests_ok": 0, "requests_error": 0}


def _build_payload(name: str, iteration: int) -> dict[str, Any]:
    cpu_base = 20.0 + (iteration % 60)
    mem_base = 30.0 + (iteration % 50)
    latency_base = 5.0 + (iteration % 20)
    if name == "telemetry_heartbeat":
        return {
            "node_id": node_id,
            "cpu_usage": cpu_base,
            "memory_usage": mem_base,
            "neighbors_count": 3,
            "routing_table_size": 12,
            "uptime": 7200 + iteration,
            "latency_ms": latency_base,
            "error_reports": [],
        }
    if name == "node_heartbeat":
        return {
            "status": "healthy",
            "cpu_percent": cpu_base,
            "mem_percent": mem_base,
            "latency_ms": latency_base,
            "traffic_mbps": 32.0 + (iteration % 8),
            "active_connections": 20 + (iteration % 7),
            "custom_metrics": {"source": "load-profile"},
        }
    return {}


def _is_success(name: str, status_code: int, body: Any) -> bool:
    if status_code != 200:
        return False
    if name == "marketplace_search":
        return isinstance(body, list)
    if name == "telemetry_heartbeat":
        return isinstance(body, dict) and body.get("status") == "ack"
    if name == "node_heartbeat":
        return isinstance(body, dict) and body.get("status") == "ok"
    return True


def _decode_response(payload: bytes) -> Any:
    if not payload:
        return {}
    try:
        return json.loads(payload.decode("utf-8"))
    except Exception:
        return {}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = int((percentile / 100.0) * (len(sorted_values) - 1))
    return sorted_values[rank]


def worker(worker_idx: int) -> None:
    iteration = 0
    scenario_idx = worker_idx % len(scenario_definitions)
    while time.time() < deadline:
        scenario = scenario_definitions[scenario_idx % len(scenario_definitions)]
        scenario_idx += 1
        iteration += 1

        name = scenario["name"]
        method = scenario["method"]
        path = scenario["path"]
        url = f"{base_url}{path}"
        payload = _build_payload(name, iteration)
        body_bytes = None
        headers = {
            "Content-Type": "application/json",
            "X-Request-ID": f"load-{worker_idx}-{iteration}",
            "X-API-Key": "load-api-key",
        }
        if method == "POST":
            body_bytes = json.dumps(payload).encode("utf-8")

        started = time.perf_counter()
        status_code = 0
        body: Any = {}
        error_reason = ""
        try:
            req = urllib.request.Request(
                url,
                data=body_bytes,
                headers=headers,
                method=method,
            )
            with urllib.request.urlopen(req, timeout=request_timeout_seconds) as response:
                status_code = getattr(response, "status", 0)
                body = _decode_response(response.read())
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            body = _decode_response(exc.read())
            error_reason = f"http_{exc.code}"
        except urllib.error.URLError:
            status_code = 0
            body = {}
            error_reason = "network_error"
        except TimeoutError:
            status_code = 0
            body = {}
            error_reason = "timeout"
        except Exception:
            status_code = 0
            body = {}
            error_reason = "unexpected_exception"

        latency_ms = (time.perf_counter() - started) * 1000.0
        ok = _is_success(name, status_code, body)
        if not ok and not error_reason:
            error_reason = "unexpected_response"

        with lock:
            totals["requests_total"] += 1
            scenario_metrics[name]["requests_total"] += 1
            scenario_metrics[name]["latencies_ms"].append(latency_ms)
            if ok:
                totals["requests_ok"] += 1
                scenario_metrics[name]["requests_ok"] += 1
            else:
                totals["requests_error"] += 1
                scenario_metrics[name]["requests_error"] += 1
                scenario_metrics[name]["errors_by_reason"][error_reason] += 1


threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(concurrency)]
for thread in threads:
    thread.start()
for thread in threads:
    thread.join()

scenarios_payload: dict[str, Any] = {}
for item in scenario_definitions:
    name = item["name"]
    metrics = scenario_metrics[name]
    total = metrics["requests_total"]
    latencies = metrics["latencies_ms"]
    scenarios_payload[name] = {
        "requests_total": total,
        "requests_ok": metrics["requests_ok"],
        "requests_error": metrics["requests_error"],
        "error_rate_percent": (metrics["requests_error"] / total * 100.0) if total else 0.0,
        "latency_mean_ms": mean(latencies) if latencies else 0.0,
        "latency_p95_ms": _percentile(latencies, 95.0),
        "throughput_rps": (total / duration) if duration else 0.0,
        "errors_by_reason": dict(metrics["errors_by_reason"]),
    }

overall_error_rate = (
    totals["requests_error"] / totals["requests_total"] * 100.0
    if totals["requests_total"]
    else 0.0
)

payload: dict[str, Any] = {
    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "base_url": base_url,
    "duration_seconds": duration,
    "concurrency": concurrency,
    "request_timeout_seconds": request_timeout_seconds,
    "scenarios_selected": scenario_names,
    "mesh_id": mesh_id,
    "node_id": node_id,
    "requests_total": totals["requests_total"],
    "requests_ok": totals["requests_ok"],
    "requests_error": totals["requests_error"],
    "error_rate_percent": overall_error_rate,
    "throughput_rps": (totals["requests_total"] / duration) if duration else 0.0,
    "scenarios": scenarios_payload,
}

if payload["requests_total"] <= 0:
    print("Load run did not execute any requests", file=sys.stderr)
    raise SystemExit(config_exit_code)

raw_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(payload))
PY

info "Building markdown report"
python3 - "$RAW_JSON" "$REPORT_MD" "$LATEST_JSON" "$LATEST_MD" "$TIMESTAMP_UTC" "$MAX_ERROR_RATE_PERCENT" "$MAX_SCENARIO_P95_MS" "$EXIT_GATE_FAIL" "$EXIT_CONFIG" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import sys

raw_json = Path(sys.argv[1])
report_md = Path(sys.argv[2])
latest_json = Path(sys.argv[3])
latest_md = Path(sys.argv[4])
started_utc = sys.argv[5]
max_error = float(sys.argv[6])
max_p95 = float(sys.argv[7])
exit_gate_fail = int(sys.argv[8])
exit_config = int(sys.argv[9])

data = json.loads(raw_json.read_text(encoding="utf-8"))
scenarios = data.get("scenarios", {})
selected = data.get("scenarios_selected", [])

if not scenarios or not selected:
    print("Scenario payload is empty; cannot evaluate gate", file=sys.stderr)
    raise SystemExit(exit_config)

checks: list[tuple[str, bool]] = []
checks.append(("overall_error_rate_ok", data.get("error_rate_percent", 0.0) <= max_error))

for name, stats in scenarios.items():
    checks.append((f"{name}_p95_ok", float(stats.get("latency_p95_ms", 0.0)) <= max_p95))
    checks.append((f"{name}_has_success", int(stats.get("requests_ok", 0)) > 0))

overall = all(flag for _, flag in checks)

lines = [
    "# MaaS API Load Scenarios",
    "",
    f"- **Started (UTC):** {started_utc}",
    f"- **Collected (UTC):** {data.get('timestamp_utc')}",
    f"- **Base URL:** {data.get('base_url')}",
    f"- **Duration:** {data.get('duration_seconds')}s",
    f"- **Concurrency:** {data.get('concurrency')}",
    f"- **Request timeout:** {float(data.get('request_timeout_seconds', 0.0)):.2f}s",
    f"- **Scenarios:** `{', '.join(selected)}`",
    f"- **Mesh ID:** {data.get('mesh_id')}",
    f"- **Node ID:** {data.get('node_id')}",
    f"- **Overall:** {'PASS' if overall else 'FAIL'}",
    "",
    "## Totals",
    "",
    f"- Requests total: `{data.get('requests_total', 0)}`",
    f"- Requests ok: `{data.get('requests_ok', 0)}`",
    f"- Requests error: `{data.get('requests_error', 0)}`",
    f"- Error rate: `{float(data.get('error_rate_percent', 0.0)):.3f}%` (threshold <= `{max_error:.3f}%`)",
    f"- Throughput: `{float(data.get('throughput_rps', 0.0)):.2f} req/s`",
    "",
    "## Scenario Metrics",
    "",
]

for name, stats in scenarios.items():
    lines.extend(
        [
            f"### `{name}`",
            "",
            f"- Requests total: `{int(stats.get('requests_total', 0))}`",
            f"- Requests ok: `{int(stats.get('requests_ok', 0))}`",
            f"- Requests error: `{int(stats.get('requests_error', 0))}`",
            f"- Error rate: `{float(stats.get('error_rate_percent', 0.0)):.3f}%`",
            f"- Latency mean: `{float(stats.get('latency_mean_ms', 0.0)):.2f} ms`",
            f"- Latency p95: `{float(stats.get('latency_p95_ms', 0.0)):.2f} ms` (threshold <= `{max_p95:.2f} ms`)",
            f"- Throughput: `{float(stats.get('throughput_rps', 0.0)):.2f} req/s`",
            f"- Errors by reason: `{stats.get('errors_by_reason', {})}`",
            "",
        ]
    )

lines.extend(
    [
        "## Gate Checks",
        "",
    ]
)
for name, passed in checks:
    lines.append(f"- {name}: `{'PASS' if passed else 'FAIL'}`")

report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
latest_json.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("PASS" if overall else "FAIL")
if not overall:
    raise SystemExit(exit_gate_fail)
PY

info "Raw JSON:  $RAW_JSON"
info "Report MD: $REPORT_MD"
info "Latest JSON: $LATEST_JSON"
info "Latest MD: $LATEST_MD"
info "App log:   $APP_LOG"
info "MaaS API load scenarios completed successfully"
