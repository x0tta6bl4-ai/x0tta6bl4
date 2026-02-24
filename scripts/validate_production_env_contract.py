#!/usr/bin/env python3
"""Validate production environment contract for enterprise deployments."""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path
from typing import Dict, Iterable, Tuple


REQUIRED_KEYS = (
    "ENVIRONMENT",
    "DATABASE_URL",
    "FLASK_SECRET_KEY",
    "JWT_SECRET_KEY",
    "CSRF_SECRET_KEY",
    "OPERATOR_PRIVATE_KEY",
    "VPN_SERVER",
    "VPN_PORT",
    "VPN_SESSION_TOKEN",
    "MTLS_ENABLED",
    "RATE_LIMIT_ENABLED",
    "REQUEST_VALIDATION_ENABLED",
    "DB_ENFORCE_SCHEMA",
    "MAAS_LIGHT_MODE",
    "X0TTA6BL4_FAIL_OPEN_STARTUP",
    "X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY",
)

REQUIRE_TRUE_KEYS = (
    "MTLS_ENABLED",
    "RATE_LIMIT_ENABLED",
    "REQUEST_VALIDATION_ENABLED",
    "DB_ENFORCE_SCHEMA",
)

REQUIRE_FALSE_KEYS = (
    "MAAS_LIGHT_MODE",
    "X0TTA6BL4_FAIL_OPEN_STARTUP",
    "X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY",
)

SECRET_KEYS = (
    "FLASK_SECRET_KEY",
    "JWT_SECRET_KEY",
    "CSRF_SECRET_KEY",
    "OPERATOR_PRIVATE_KEY",
    "VPN_SESSION_TOKEN",
)

BOOL_TRUE = {"1", "true", "yes", "on"}
BOOL_FALSE = {"0", "false", "no", "off"}
ENV_REF_RE = re.compile(r"^\$\{[A-Za-z_][A-Za-z0-9_]*\}$|^\$[A-Za-z_][A-Za-z0-9_]*$")


def _strip_inline_comment(value: str) -> str:
    in_single = False
    in_double = False
    for i, ch in enumerate(value):
        if ch == "'" and not in_double:
            in_single = not in_single
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            continue
        if ch == "#" and not in_single and not in_double:
            if i == 0 or value[i - 1].isspace():
                return value[:i].rstrip()
    return value


def _unquote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def parse_env_file(path: Path) -> Dict[str, str]:
    env: Dict[str, str] = {}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        if "=" not in line:
            raise ValueError(f"{path}:{lineno}: expected KEY=VALUE format")
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            raise ValueError(f"{path}:{lineno}: empty key in env entry")
        value = _unquote(_strip_inline_comment(value))
        env[key] = value
    return env


def collect_process_env() -> Dict[str, str]:
    """Collect environment variables from current process."""
    return dict(os.environ)


def _parse_bool(value: str) -> bool | None:
    normalized = value.strip().lower()
    if normalized in BOOL_TRUE:
        return True
    if normalized in BOOL_FALSE:
        return False
    return None


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip()
    if not normalized:
        return True
    lower = normalized.lower()
    placeholder_tokens = (
        "change_me",
        "changeme",
        "replace_me",
        "your_",
        "generate_",
        "example",
        "todo",
        "placeholder",
    )
    if any(token in lower for token in placeholder_tokens):
        return True
    if normalized.startswith("<") and normalized.endswith(">"):
        return True
    if ENV_REF_RE.fullmatch(normalized):
        return True
    return False


def _is_env_reference(value: str) -> bool:
    return ENV_REF_RE.fullmatch(value.strip()) is not None


def validate_env_contract(
    env: Dict[str, str],
    *,
    strict_secrets: bool,
    allow_env_references: bool = False,
) -> Tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []

    for key in REQUIRED_KEYS:
        if key not in env:
            errors.append(f"Missing required key: {key}")
        elif not env[key].strip():
            errors.append(f"Required key is empty: {key}")

    if errors:
        return errors, warnings

    environment = env["ENVIRONMENT"].strip().lower()
    if environment != "production":
        errors.append(
            f"ENVIRONMENT must be 'production', got: {env['ENVIRONMENT']!r}"
        )

    db_url = env.get("DATABASE_URL", "")
    if "x0tta6bl4_password" in db_url:
        errors.append("DATABASE_URL must not include hardcoded password token `x0tta6bl4_password`")

    for key in REQUIRE_TRUE_KEYS:
        value = _parse_bool(env.get(key, ""))
        if value is None:
            errors.append(f"{key} must be a boolean value")
        elif value is not True:
            errors.append(f"{key} must be true in production")

    for key in REQUIRE_FALSE_KEYS:
        value = _parse_bool(env.get(key, ""))
        if value is None:
            errors.append(f"{key} must be a boolean value")
        elif value is not False:
            errors.append(f"{key} must be false in production")

    for key in SECRET_KEYS:
        value = env.get(key, "")
        if _looks_like_placeholder(value):
            if allow_env_references and _is_env_reference(value):
                continue
            msg = f"{key} looks like a placeholder value"
            if strict_secrets:
                errors.append(msg)
            else:
                warnings.append(msg)

    return errors, warnings


def _format_messages(messages: Iterable[str]) -> str:
    return "\n".join(f" - {item}" for item in messages)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate production env contract")
    parser.add_argument(
        "--source",
        choices=("file", "process-env"),
        default="file",
        help="Environment source: file or current process env (default: file)",
    )
    parser.add_argument(
        "--env-file",
        default=".env.production",
        help="Path to production env file (default: .env.production)",
    )
    parser.add_argument(
        "--strict-secrets",
        action="store_true",
        help="Fail when secret values look like placeholders",
    )
    args = parser.parse_args()

    if args.source == "process-env":
        env = collect_process_env()
        source_label = "process environment"
    else:
        env_path = Path(args.env_file)
        source_label = str(env_path)
        if not env_path.exists():
            print(f"Production env contract violations:\n - Missing env file: {env_path}")
            return 1

        try:
            env = parse_env_file(env_path)
        except Exception as exc:
            print(f"Production env contract violations:\n - Failed to parse {env_path}: {exc}")
            return 1

    errors, warnings = validate_env_contract(
        env,
        strict_secrets=args.strict_secrets,
        allow_env_references=(args.source == "file" and not args.strict_secrets),
    )
    if errors:
        print("Production env contract violations:")
        print(_format_messages(errors))
        return 1

    if warnings:
        print("Production env contract warnings:")
        print(_format_messages(warnings))
    print(f"Production env contract check passed: {source_label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
