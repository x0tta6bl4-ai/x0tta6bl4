#!/usr/bin/env bash
# Add required status check to GitHub branch protection required_status_checks.

set -euo pipefail

branch="main"
required_check="Security Scan Summary"
owner=""
repo=""
dry_run=false

usage() {
  cat <<'EOF'
Usage:
  set_required_security_check.sh [--owner ORG] [--repo REPO] [--branch BRANCH] [--check-name NAME] [--dry-run]

Environment:
  GITHUB_TOKEN   GitHub token with admin permissions for repository branch protection.

Examples:
  GITHUB_TOKEN=*** scripts/set_required_security_check.sh --owner x0tta6bl4-ai --repo x0tta6bl4
  scripts/set_required_security_check.sh --dry-run

Notes:
  - Script updates only required status checks subresource.
  - Existing required checks are preserved; `Security Scan Summary` is appended if missing.
  - If branch protection is not enabled yet, API will return an error and no changes are applied.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --owner)
      owner="${2:-}"
      shift 2
      ;;
    --repo)
      repo="${2:-}"
      shift 2
      ;;
    --branch)
      branch="${2:-}"
      shift 2
      ;;
    --check-name)
      required_check="${2:-}"
      shift 2
      ;;
    --dry-run)
      dry_run=true
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      usage
      exit 2
      ;;
  esac
done

if [[ -z "$owner" || -z "$repo" ]]; then
  origin_url="$(git remote get-url origin 2>/dev/null || true)"
  if [[ "$origin_url" =~ github\.com[:/]([^/]+)/([^/.]+)(\.git)?$ ]]; then
    owner="${owner:-${BASH_REMATCH[1]}}"
    repo="${repo:-${BASH_REMATCH[2]}}"
  fi
fi

if [[ -z "$owner" || -z "$repo" ]]; then
  echo "Unable to determine owner/repo. Pass --owner and --repo." >&2
  exit 2
fi

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is not set." >&2
  exit 2
fi

api_root="https://api.github.com/repos/${owner}/${repo}/branches/${branch}/protection/required_status_checks"
auth_header="Authorization: Bearer ${GITHUB_TOKEN}"
accept_header="Accept: application/vnd.github+json"

echo "Repository: ${owner}/${repo}"
echo "Branch: ${branch}"
echo "Required check: ${required_check}"

current_response="$(curl -fsS \
  -H "${accept_header}" \
  -H "${auth_header}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "${api_root}" 2>/dev/null || true)"

if [[ -z "$current_response" ]]; then
  echo "Failed to read current required status checks." >&2
  echo "Ensure branch protection is enabled and token has admin permissions." >&2
  exit 1
fi

contexts_json="$(
python3 - "$required_check" "$current_response" <<'PY'
import json
import sys

required = sys.argv[1]
data = json.loads(sys.argv[2])
if not isinstance(data, dict) or "contexts" not in data:
    print("Invalid response: expected required_status_checks payload", file=sys.stderr)
    sys.exit(1)

contexts = [str(x) for x in (data.get("contexts") or [])]
if required not in contexts:
    contexts.append(required)
print(json.dumps(contexts))
PY
)"

payload="$(
python3 - "$contexts_json" <<'PY'
import json
import sys

contexts = json.loads(sys.argv[1])
print(json.dumps({"strict": True, "contexts": contexts}))
PY
)"

if $dry_run; then
  echo "Dry-run mode. PATCH payload:"
  echo "$payload"
  exit 0
fi

curl -fsS -X PATCH \
  -H "${accept_header}" \
  -H "${auth_header}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  -H "Content-Type: application/json" \
  "${api_root}" \
  -d "$payload" >/dev/null

echo "Branch protection required status checks updated successfully."
