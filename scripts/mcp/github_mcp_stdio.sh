#!/usr/bin/env bash
set -euo pipefail

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required for the local GitHub MCP server" >&2
  exit 2
fi

if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  if command -v gh >/dev/null 2>&1; then
    GITHUB_PERSONAL_ACCESS_TOKEN="$(gh auth token 2>/dev/null || true)"
    export GITHUB_PERSONAL_ACCESS_TOKEN
  fi
fi

if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  echo "GITHUB_PERSONAL_ACCESS_TOKEN is missing; run gh auth login or export a GitHub PAT locally" >&2
  exit 2
fi

: "${GITHUB_TOOLSETS:=repos,issues,pull_requests,users,actions}"
: "${GITHUB_MCP_IMAGE:=ghcr.io/github/github-mcp-server}"
export GITHUB_PERSONAL_ACCESS_TOKEN GITHUB_TOOLSETS

exec docker run -i --rm \
  -e GITHUB_PERSONAL_ACCESS_TOKEN \
  -e GITHUB_TOOLSETS \
  "${GITHUB_MCP_IMAGE}" stdio --read-only
