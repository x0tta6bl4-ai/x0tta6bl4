#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

MODE="check"
TARGET_DIR="${TARGET_DIR:-$REPO_ROOT/x0t-linkd}"
JSON=0

usage() {
    cat <<'USAGE'
Usage:
  scripts/ops/rust_toolchain_preflight.sh [--check] [--json] [--target-dir PATH]
  scripts/ops/rust_toolchain_preflight.sh --install-user
  scripts/ops/rust_toolchain_preflight.sh --print-env

Purpose:
  Verify the local Rust toolchain needed for x0t-linkd work without touching
  x0t-linkd sources, eBPF code, prod VPS state, or system packages.

Modes:
  --check         Default. Report rustc/cargo/rustup availability.
  --install-user Install rustup stable into the current user's CARGO_HOME/RUSTUP_HOME.
                 This is opt-in and never runs by default.
  --print-env    Print shell exports that put ~/.cargo/bin first on PATH.

Exit codes:
  0  Rust toolchain is available on PATH.
  2  rustc or cargo is missing.
  3  Unsupported arguments or install prerequisites are missing.
USAGE
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --check)
            MODE="check"
            ;;
        --install-user)
            MODE="install-user"
            ;;
        --print-env)
            MODE="print-env"
            ;;
        --json)
            JSON=1
            ;;
        --target-dir)
            if [[ $# -lt 2 ]]; then
                echo "ERROR: --target-dir requires a path" >&2
                exit 3
            fi
            TARGET_DIR="$2"
            shift
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unsupported argument: $1" >&2
            usage >&2
            exit 3
            ;;
    esac
    shift
done

json_escape() {
    local value="$1"
    value="${value//\\/\\\\}"
    value="${value//\"/\\\"}"
    value="${value//$'\n'/\\n}"
    printf '%s' "$value"
}

command_path() {
    local name="$1"
    command -v "$name" 2>/dev/null || true
}

command_version() {
    local name="$1"
    if command -v "$name" >/dev/null 2>&1; then
        "$name" --version 2>/dev/null | head -n 1
    else
        printf 'missing'
    fi
}

print_env() {
    cat <<'ENV'
export CARGO_HOME="${CARGO_HOME:-$HOME/.cargo}"
export RUSTUP_HOME="${RUSTUP_HOME:-$HOME/.rustup}"
export PATH="$CARGO_HOME/bin:$PATH"
ENV
}

install_user() {
    if command -v rustc >/dev/null 2>&1 && command -v cargo >/dev/null 2>&1; then
        echo "Rust toolchain already available:"
        rustc --version
        cargo --version
        exit 0
    fi

    if ! command -v curl >/dev/null 2>&1; then
        echo "ERROR: curl is required for rustup bootstrap" >&2
        exit 3
    fi

    echo "Installing Rust stable for the current user via rustup."
    echo "This writes under CARGO_HOME/RUSTUP_HOME, defaulting to ~/.cargo and ~/.rustup."
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal --default-toolchain stable
    echo
    echo "Rust installed. Load it in the current shell with:"
    print_env
}

check_toolchain() {
    local rustc_path cargo_path rustup_path rustc_version cargo_version rustup_version
    rustc_path="$(command_path rustc)"
    cargo_path="$(command_path cargo)"
    rustup_path="$(command_path rustup)"
    rustc_version="$(command_version rustc)"
    cargo_version="$(command_version cargo)"
    rustup_version="$(command_version rustup)"

    local target_status="missing"
    if [[ -d "$TARGET_DIR" ]]; then
        if [[ -f "$TARGET_DIR/Cargo.toml" ]]; then
            target_status="cargo-project"
        else
            target_status="directory-without-Cargo.toml"
        fi
    fi

    local ready=0
    if [[ -n "$rustc_path" && -n "$cargo_path" ]]; then
        ready=1
    fi

    if [[ "$JSON" -eq 1 ]]; then
        cat <<JSON
{
  "ready": $ready,
  "rustc": {
    "path": "$(json_escape "$rustc_path")",
    "version": "$(json_escape "$rustc_version")"
  },
  "cargo": {
    "path": "$(json_escape "$cargo_path")",
    "version": "$(json_escape "$cargo_version")"
  },
  "rustup": {
    "path": "$(json_escape "$rustup_path")",
    "version": "$(json_escape "$rustup_version")"
  },
  "target_dir": "$(json_escape "$TARGET_DIR")",
  "target_status": "$(json_escape "$target_status")",
  "install_command": "scripts/ops/rust_toolchain_preflight.sh --install-user"
}
JSON
    else
        echo "=== Rust Toolchain Preflight ==="
        echo "Repo root:    $REPO_ROOT"
        echo "Target dir:   $TARGET_DIR ($target_status)"
        echo "rustc:        $rustc_version${rustc_path:+ ($rustc_path)}"
        echo "cargo:        $cargo_version${cargo_path:+ ($cargo_path)}"
        echo "rustup:       $rustup_version${rustup_path:+ ($rustup_path)}"
        echo
        if [[ "$ready" -eq 1 ]]; then
            echo "READY: rustc and cargo are available on PATH."
        else
            echo "NOT READY: rustc or cargo is missing from PATH."
            echo "Install for the current user with:"
            echo "  scripts/ops/rust_toolchain_preflight.sh --install-user"
            echo
            echo "Then load PATH in the shell with:"
            print_env | sed 's/^/  /'
        fi
    fi

    if [[ "$ready" -eq 1 ]]; then
        exit 0
    fi
    exit 2
}

case "$MODE" in
    check)
        check_toolchain
        ;;
    install-user)
        install_user
        ;;
    print-env)
        print_env
        ;;
esac
