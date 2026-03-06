#!/usr/bin/env bash
set -euo pipefail

DURATION_SECONDS="${DURATION_SECONDS:-180}"
CONCURRENCY="${CONCURRENCY:-8}"
SAMPLE_INTERVAL_SECONDS="${SAMPLE_INTERVAL_SECONDS:-1.0}"
BASE_URL="${BASE_URL:-http://127.0.0.1:8000}"
APP_HOST="${APP_HOST:-127.0.0.1}"
APP_PORT="${APP_PORT:-8000}"
APP_MODE="${APP_MODE:-light}" # light | full
STARTUP_TIMEOUT_SECONDS="${STARTUP_TIMEOUT_SECONDS:-180}"
MAX_MEMORY_GROWTH_MB="${MAX_MEMORY_GROWTH_MB:-200}"
MAX_ERROR_RATE_PERCENT="${MAX_ERROR_RATE_PERCENT:-1.0}"
MAX_P95_MS="${MAX_P95_MS:-3000}"
ENDPOINTS_CSV="${ENDPOINTS_CSV:-/health/ready,/health,/metrics,/api/v1/maas/plans}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
REPORT_DIR="${REPORT_DIR:-$REPO_ROOT/docs/operations}"

TIMESTAMP_UTC="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
TIMESTAMP_ID="$(date -u +%Y%m%dT%H%M%SZ)"
RAW_JSON="$REPORT_DIR/api_memory_longrun_${TIMESTAMP_ID}.json"
REPORT_MD="$REPORT_DIR/api_memory_longrun_${TIMESTAMP_ID}.md"
LATEST_MD="$REPORT_DIR/API_MEMORY_LONGRUN_LATEST.md"
APP_LOG="/tmp/api_memory_longrun_${TIMESTAMP_ID}.log"

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
  echo -e "${RED}[ERROR]${NC} $*" >&2
  exit 1
}

cleanup() {
  if [[ -n "${APP_PID:-}" ]] && kill -0 "$APP_PID" >/dev/null 2>&1; then
    kill "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

mkdir -p "$REPORT_DIR"

for bin in python3 curl uvicorn; do
  command -v "$bin" >/dev/null 2>&1 || error "$bin not found in PATH"
done

app_mode_env="MAAS_LIGHT_MODE=false"
if [[ "$APP_MODE" == "light" ]]; then
  app_mode_env="MAAS_LIGHT_MODE=true"
fi

info "Starting API (mode=${APP_MODE}) on ${APP_HOST}:${APP_PORT}"
bash -lc "cd '$REPO_ROOT' && ${app_mode_env} uvicorn src.core.app:app --host '${APP_HOST}' --port '${APP_PORT}'" >"$APP_LOG" 2>&1 &
APP_PID=$!

deadline=$((SECONDS + STARTUP_TIMEOUT_SECONDS))
until curl -fsS "${BASE_URL}/health/ready" >/dev/null 2>&1; do
  if (( SECONDS >= deadline )); then
    tail -n 120 "$APP_LOG" >&2 || true
    error "API failed to become ready at ${BASE_URL}/health/ready"
  fi
  sleep 1
done
info "API is ready (pid=${APP_PID})"

info "Running long-run memory profile (duration=${DURATION_SECONDS}s, concurrency=${CONCURRENCY})"
python3 - "$APP_PID" "$BASE_URL" "$DURATION_SECONDS" "$CONCURRENCY" "$SAMPLE_INTERVAL_SECONDS" "$ENDPOINTS_CSV" "$RAW_JSON" <<'PY'
from __future__ import annotations

import json
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path
from statistics import mean
from typing import Any
import sys

pid = int(sys.argv[1])
base_url = sys.argv[2].rstrip("/")
duration = int(sys.argv[3])
concurrency = int(sys.argv[4])
sample_interval = float(sys.argv[5])
endpoints = [x.strip() for x in sys.argv[6].split(",") if x.strip()]
raw_json_path = Path(sys.argv[7])

deadline = time.time() + duration
lock = threading.Lock()

latencies_ms: list[float] = []
requests_total = 0
requests_ok = 0
requests_error = 0
rss_samples_mb: list[float] = []

def read_rss_mb(proc_pid: int) -> float:
    status_path = Path(f"/proc/{proc_pid}/status")
    content = status_path.read_text(encoding="utf-8")
    for line in content.splitlines():
        if line.startswith("VmRSS:"):
            parts = line.split()
            if len(parts) >= 2:
                return float(parts[1]) / 1024.0
    return 0.0

def worker(worker_idx: int) -> None:
    global requests_total, requests_ok, requests_error
    endpoint_idx = worker_idx % max(len(endpoints), 1)
    timeout = 5.0
    while time.time() < deadline:
        endpoint = endpoints[endpoint_idx % len(endpoints)]
        endpoint_idx += 1
        url = f"{base_url}{endpoint}"
        start = time.perf_counter()
        ok = False
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ok = 200 <= resp.status < 500
                _ = resp.read(256)
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError):
            ok = False
        latency = (time.perf_counter() - start) * 1000.0
        with lock:
            requests_total += 1
            latencies_ms.append(latency)
            if ok:
                requests_ok += 1
            else:
                requests_error += 1

def sampler() -> None:
    while time.time() < deadline:
        try:
            rss = read_rss_mb(pid)
            with lock:
                rss_samples_mb.append(rss)
        except Exception:
            pass
        time.sleep(sample_interval)

sampler_thread = threading.Thread(target=sampler, daemon=True)
sampler_thread.start()

threads = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(concurrency)]
for t in threads:
    t.start()
for t in threads:
    t.join()
sampler_thread.join()

if not rss_samples_mb:
    raise SystemExit("No RSS samples were collected")

sorted_latencies = sorted(latencies_ms) if latencies_ms else [0.0]
p95_index = int(0.95 * (len(sorted_latencies) - 1))
p95_ms = sorted_latencies[p95_index]

start_rss = rss_samples_mb[0]
end_rss = rss_samples_mb[-1]
peak_rss = max(rss_samples_mb)
growth = end_rss - start_rss
error_rate = (requests_error / requests_total * 100.0) if requests_total else 0.0
rps = requests_total / duration if duration else 0.0

payload: dict[str, Any] = {
    "timestamp_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    "base_url": base_url,
    "duration_seconds": duration,
    "concurrency": concurrency,
    "sample_interval_seconds": sample_interval,
    "endpoints": endpoints,
    "requests_total": requests_total,
    "requests_ok": requests_ok,
    "requests_error": requests_error,
    "error_rate_percent": error_rate,
    "throughput_rps": rps,
    "latency_mean_ms": mean(latencies_ms) if latencies_ms else 0.0,
    "latency_p95_ms": p95_ms,
    "rss_start_mb": start_rss,
    "rss_end_mb": end_rss,
    "rss_peak_mb": peak_rss,
    "rss_growth_mb": growth,
    "rss_samples_count": len(rss_samples_mb),
}

raw_json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps(payload))
PY

info "Building markdown report"
python3 - "$RAW_JSON" "$REPORT_MD" "$LATEST_MD" "$TIMESTAMP_UTC" "$APP_MODE" "$MAX_MEMORY_GROWTH_MB" "$MAX_ERROR_RATE_PERCENT" "$MAX_P95_MS" <<'PY'
from __future__ import annotations

import json
from pathlib import Path
import sys

raw_json = Path(sys.argv[1])
report_md = Path(sys.argv[2])
latest_md = Path(sys.argv[3])
started_utc = sys.argv[4]
app_mode = sys.argv[5]
max_growth = float(sys.argv[6])
max_error = float(sys.argv[7])
max_p95 = float(sys.argv[8])

data = json.loads(raw_json.read_text(encoding="utf-8"))

checks = {
    "memory_growth_ok": data["rss_growth_mb"] <= max_growth,
    "error_rate_ok": data["error_rate_percent"] <= max_error,
    "latency_p95_ok": data["latency_p95_ms"] <= max_p95,
}
overall = all(checks.values())

lines = [
    "# API Long-Run Memory Profile",
    "",
    f"- **Started (UTC):** {started_utc}",
    f"- **Collected (UTC):** {data['timestamp_utc']}",
    f"- **Mode:** {app_mode}",
    f"- **Duration:** {data['duration_seconds']}s",
    f"- **Concurrency:** {data['concurrency']}",
    f"- **Base URL:** {data['base_url']}",
    f"- **Overall:** {'PASS' if overall else 'FAIL'}",
    "",
    "## Workload",
    "",
    f"- Endpoints: `{', '.join(data['endpoints'])}`",
    f"- Requests total: `{data['requests_total']}`",
    f"- Throughput: `{data['throughput_rps']:.2f} req/s`",
    f"- Error rate: `{data['error_rate_percent']:.3f}%` (threshold <= `{max_error:.3f}%`)",
    f"- Latency mean: `{data['latency_mean_ms']:.2f} ms`",
    f"- Latency p95: `{data['latency_p95_ms']:.2f} ms` (threshold <= `{max_p95:.2f} ms`)",
    "",
    "## Memory",
    "",
    f"- RSS start: `{data['rss_start_mb']:.2f} MiB`",
    f"- RSS end: `{data['rss_end_mb']:.2f} MiB`",
    f"- RSS peak: `{data['rss_peak_mb']:.2f} MiB`",
    f"- RSS growth: `{data['rss_growth_mb']:.2f} MiB` (threshold <= `{max_growth:.2f} MiB`)",
    f"- Samples: `{data['rss_samples_count']}`",
    "",
    "## Gate Checks",
    "",
    f"- memory_growth_ok: `{'PASS' if checks['memory_growth_ok'] else 'FAIL'}`",
    f"- error_rate_ok: `{'PASS' if checks['error_rate_ok'] else 'FAIL'}`",
    f"- latency_p95_ok: `{'PASS' if checks['latency_p95_ok'] else 'FAIL'}`",
]

report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
latest_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

print("PASS" if overall else "FAIL")
if not overall:
    raise SystemExit(2)
PY

info "Raw JSON:  $RAW_JSON"
info "Report MD: $REPORT_MD"
info "Latest MD: $LATEST_MD"
info "App log:   $APP_LOG"
info "Long-run memory profile completed successfully"
