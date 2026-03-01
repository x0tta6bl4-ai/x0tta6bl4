#!/usr/bin/env python3
"""Fail-closed audit for insecure env defaults and hardcoded secret fallbacks."""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass
from pathlib import Path


PYTHON_SCAN_DIRS = (
    "src/api",
    "src/core",
    "src/network",
    "src/security",
    "src/libx0t/core",
    "src/libx0t/security",
)

SHELL_SCAN_DIR = "scripts"

SENSITIVE_ENV_SUFFIXES = (
    "_SECRET",
    "_TOKEN",
    "_PASSWORD",
    "_PRIVATE_KEY",
    "_API_KEY",
)

SENSITIVE_ENV_ALLOWLIST = {
    # Explicitly test-only helper in hardening self-check flow.
    "TEST_PASSWORD",
}

REQUIRED_SAFE_BOOL_DEFAULTS = {
    "MAAS_LIGHT_MODE": "false",
    "X0TTA6BL4_ALLOW_INSECURE_PQC_VERIFY": "false",
    "X0TTA6BL4_ALLOW_NOAUTH_SOCKS5": "false",
    "DB_ENFORCE_SCHEMA": "true",
}

PLACEHOLDER_MARKERS = (
    "placeholder",
    "change_me",
    "changeme",
    "replace_me",
    "your_",
    "generate_",
    "example",
    "todo",
    "mock",
    "demo",
    "test",
)

SHELL_ASSIGN_RE = re.compile(
    r"^\s*(?:export\s+)?(?P<name>[A-Z][A-Z0-9_]*(?:_SECRET|_TOKEN|_PASSWORD|_PRIVATE_KEY|_API_KEY))=(?P<value>.+?)\s*$"
)
SHELL_DEFAULT_FALLBACK_RE = re.compile(
    r'^["\']?\$\{[A-Za-z_][A-Za-z0-9_]*:-(?P<fallback>[^}]*)\}["\']?$'
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    message: str

    def format(self) -> str:
        return f"{self.path}:{self.line}: {self.message}"


def _to_repo_relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _is_placeholder(value: str) -> bool:
    normalized = value.strip().strip("'").strip('"')
    if not normalized:
        return True
    low = normalized.lower()
    if any(marker in low for marker in PLACEHOLDER_MARKERS):
        return True
    return normalized.startswith("<") and normalized.endswith(">")


def _is_sensitive_env_name(name: str) -> bool:
    if name in SENSITIVE_ENV_ALLOWLIST:
        return False
    return name.endswith(SENSITIVE_ENV_SUFFIXES)


def _extract_getenv_name(node: ast.Call) -> str | None:
    if not node.args:
        return None
    arg0 = node.args[0]
    if isinstance(arg0, ast.Constant) and isinstance(arg0.value, str):
        return arg0.value
    return None


def _extract_literal_default(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_bool_default(node: ast.expr | None) -> str | None:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return "true" if node.value else "false"
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value.strip().lower()
    return None


def _is_getenv_call(node: ast.Call) -> bool:
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "getenv"
    if isinstance(func, ast.Attribute):
        if func.attr == "getenv" and isinstance(func.value, ast.Name):
            return func.value.id == "os"
        if func.attr == "get":
            value = func.value
            return (
                isinstance(value, ast.Attribute)
                and value.attr == "environ"
                and isinstance(value.value, ast.Name)
                and value.value.id == "os"
            )
    return False


def scan_python_file(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as exc:
        return [
            Finding(
                path=_to_repo_relative(path, root),
                line=exc.lineno or 1,
                message=f"failed to parse file: {exc.msg}",
            )
        ]

    rel = _to_repo_relative(path, root)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _is_getenv_call(node):
            continue

        env_name = _extract_getenv_name(node)
        if not env_name:
            continue

        default_node = node.args[1] if len(node.args) > 1 else None
        bool_default = _extract_bool_default(default_node)
        if env_name in REQUIRED_SAFE_BOOL_DEFAULTS and bool_default is not None:
            expected = REQUIRED_SAFE_BOOL_DEFAULTS[env_name]
            if bool_default != expected:
                findings.append(
                    Finding(
                        path=rel,
                        line=getattr(node, "lineno", 1),
                        message=(
                            f"{env_name} default must be {expected!r}, got {bool_default!r}"
                        ),
                    )
                )

        if not _is_sensitive_env_name(env_name):
            continue

        default_literal = _extract_literal_default(default_node)
        if default_literal is None:
            continue
        if not default_literal.strip():
            continue
        if _is_placeholder(default_literal):
            continue

        findings.append(
            Finding(
                path=rel,
                line=getattr(node, "lineno", 1),
                message=(
                    f"{env_name} uses hardcoded non-empty default literal "
                    f"{default_literal!r}; require explicit env/vault value"
                ),
            )
        )

    return findings


def _unquote_shell(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _extract_shell_literal(value: str) -> str | None:
    raw = value.strip()
    if not raw:
        return ""
    if "$(" in raw or "`" in raw:
        return None
    if "$" in raw:
        # Variable expansion is not a hardcoded literal.
        return None
    return _unquote_shell(raw)


def scan_shell_file(path: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    rel = _to_repo_relative(path, root)
    active_heredoc: str | None = None

    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        stripped = raw.strip()

        if active_heredoc is not None:
            if stripped == active_heredoc:
                active_heredoc = None
            continue

        if not stripped or stripped.startswith("#"):
            continue

        heredoc_match = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?", raw)
        if heredoc_match:
            active_heredoc = heredoc_match.group(1)
            continue

        match = SHELL_ASSIGN_RE.match(raw)
        if not match:
            continue

        name = match.group("name")
        value = match.group("value").strip()

        fb_match = SHELL_DEFAULT_FALLBACK_RE.match(value)
        if fb_match:
            fallback = _unquote_shell(fb_match.group("fallback").strip())
            if fallback and not _is_placeholder(fallback):
                findings.append(
                    Finding(
                        path=rel,
                        line=lineno,
                        message=(
                            f"{name} uses non-empty default fallback {fallback!r} in "
                            "parameter expansion"
                        ),
                    )
                )
            continue

        literal = _extract_shell_literal(value)
        if literal is None:
            continue
        if not literal:
            continue
        if _is_placeholder(literal):
            continue

        findings.append(
            Finding(
                path=rel,
                line=lineno,
                message=f"{name} is hardcoded to non-placeholder literal value",
            )
        )

    return findings


def _iter_python_files(root: Path):
    for rel_dir in PYTHON_SCAN_DIRS:
        directory = root / rel_dir
        if not directory.exists():
            continue
        yield from directory.rglob("*.py")


def _iter_shell_files(root: Path):
    scripts_dir = root / SHELL_SCAN_DIR
    if not scripts_dir.exists():
        return
    yield from scripts_dir.rglob("*.sh")


def scan_repo(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for py_file in _iter_python_files(root):
        findings.extend(scan_python_file(py_file, root))
    for sh_file in _iter_shell_files(root):
        findings.extend(scan_shell_file(sh_file, root))
    return sorted(findings, key=lambda item: (item.path, item.line, item.message))


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    findings = scan_repo(root)

    if findings:
        print("Env security defaults audit FAILED")
        for item in findings:
            print(f" - {item.format()}")
        return 1

    print("Env security defaults audit passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
