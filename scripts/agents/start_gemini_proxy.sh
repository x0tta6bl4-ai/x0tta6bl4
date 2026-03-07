#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/agents/start_gemini_proxy.sh [--proxy http://127.0.0.1:7890] [--node-max-old-space-size 4096] [--no-exec] [--print-env] [-- <gemini args...>]

Options:
  --proxy URL                  Proxy URL to export as HTTPS_PROXY/HTTP_PROXY.
  --node-max-old-space-size N  Export NODE_OPTIONS with --max-old-space-size=N.
  --no-exec                    Print the resolved command and exit without starting Gemini.
  --print-env                  Print effective environment before launch.
  -h, --help       Show this help.

Environment:
  GEMINI_PROXY_URL               Default proxy URL if --proxy is omitted.
  HTTPS_PROXY / HTTP_PROXY       Existing proxy env may be reused if --proxy is omitted.
  NO_PROXY                       Existing NO_PROXY will be merged with localhost defaults.
  GEMINI_EXTRA_NO_PROXY          Extra comma-separated hosts appended to NO_PROXY.
  GEMINI_NODE_MAX_OLD_SPACE_MB   Default Node heap limit in MB for Gemini CLI.
  NODE_OPTIONS                   Existing Node runtime flags; merged with max-old-space-size.

Notes:
  - This is a local operator launcher only.
  - It does not change repository-wide tooling.
  - It preserves localhost/127.0.0.1/::1 in NO_PROXY when proxy mode is used.
  - It can be used for Gemini OOM recovery via --node-max-old-space-size and --resume.
EOF
}

proxy_url="${GEMINI_PROXY_URL:-}"
node_heap_mb="${GEMINI_NODE_MAX_OLD_SPACE_MB:-}"
no_exec=0
print_env=0
args=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --proxy)
      [[ $# -ge 2 ]] || { echo "missing value for --proxy" >&2; exit 2; }
      proxy_url="$2"
      shift 2
      ;;
    --node-max-old-space-size)
      [[ $# -ge 2 ]] || { echo "missing value for --node-max-old-space-size" >&2; exit 2; }
      node_heap_mb="$2"
      shift 2
      ;;
    --no-exec)
      no_exec=1
      shift
      ;;
    --print-env)
      print_env=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    --)
      shift
      args+=("$@")
      break
      ;;
    *)
      args+=("$1")
      shift
      ;;
  esac
done

if [[ -z "${proxy_url}" ]]; then
  proxy_url="${HTTPS_PROXY:-${HTTP_PROXY:-}}"
fi

if [[ -n "${node_heap_mb}" ]]; then
  if ! [[ "${node_heap_mb}" =~ ^[0-9]+$ ]]; then
    echo "--node-max-old-space-size must be an integer number of MB" >&2
    exit 2
  fi
fi

if [[ -n "${proxy_url}" ]]; then
  export HTTPS_PROXY="${proxy_url}"
  export HTTP_PROXY="${proxy_url}"

  default_no_proxy="localhost,127.0.0.1,::1"
  merged_no_proxy="${NO_PROXY:-}"
  if [[ -n "${merged_no_proxy}" ]]; then
    merged_no_proxy="${merged_no_proxy},${default_no_proxy}"
  else
    merged_no_proxy="${default_no_proxy}"
  fi
  if [[ -n "${GEMINI_EXTRA_NO_PROXY:-}" ]]; then
    merged_no_proxy="${merged_no_proxy},${GEMINI_EXTRA_NO_PROXY}"
  fi

  export NO_PROXY="$(python3 - "${merged_no_proxy}" <<'PY'
import sys
parts = [item.strip() for item in sys.argv[1].split(",") if item.strip()]
seen = set()
ordered = []
for item in parts:
    if item in seen:
        continue
    seen.add(item)
    ordered.append(item)
print(",".join(ordered))
PY
)"
fi

if [[ -n "${node_heap_mb}" ]]; then
  export NODE_OPTIONS="$(python3 - "${NODE_OPTIONS:-}" "${node_heap_mb}" <<'PY'
import sys
current = sys.argv[1].split()
heap = sys.argv[2]
filtered = [item for item in current if not item.startswith("--max-old-space-size=")]
filtered.append(f"--max-old-space-size={heap}")
print(" ".join(filtered).strip())
PY
)"
fi

cmd=(gemini --use-env-proxy)
has_flag=0
for arg in "${args[@]}"; do
  if [[ "${arg}" == "--use-env-proxy" ]]; then
    has_flag=1
    break
  fi
done
if [[ "${has_flag}" -eq 1 || -z "${proxy_url}" ]]; then
  cmd=(gemini)
fi
cmd+=("${args[@]}")

if [[ "${print_env}" -eq 1 || "${no_exec}" -eq 1 ]]; then
  echo "HTTPS_PROXY=${HTTPS_PROXY:-}"
  echo "HTTP_PROXY=${HTTP_PROXY:-}"
  echo "NO_PROXY=${NO_PROXY:-}"
  echo "NODE_OPTIONS=${NODE_OPTIONS:-}"
  printf 'COMMAND='
  printf '%q ' "${cmd[@]}"
  printf '\n'
fi

if [[ "${no_exec}" -eq 1 ]]; then
  exit 0
fi

if ! command -v gemini >/dev/null 2>&1; then
  echo "gemini CLI not found in PATH" >&2
  exit 127
fi

exec "${cmd[@]}"
