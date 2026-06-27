#!/usr/bin/env python3
"""Check that Telegram entrypoints do not become a mesh control plane.

Telegram may be used for alerts, sales, user onboarding, and delivery of user
configuration. Direct mesh/MAPE-K/control-plane execution from Telegram handlers
must stay behind a separate API/service boundary with explicit authorization and
claim gates.
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_TELEGRAM_ENTRYPOINTS = (
    "telegram_bot.py",
    "src/sales/telegram_bot.py",
    "src/sales/telegram_bot_v2.py",
    "scripts/telegram_webhook_server.py",
    "services/nl-server/redacted/ghost-access/telegram_bot_simple.redacted.py",
)

FORBIDDEN_IMPORT_PREFIXES = (
    "src.api.maas.endpoints",
    "src.api.maas_nodes",
    "src.api.maas_provisioning",
    "src.api.maas_marketplace",
    "src.core.mape_k",
    "src.core.mape_orchestrator",
    "src.dao.action_dispatcher",
    "src.mesh",
    "src.self_healing",
    "src.security.pqc",
)

FORBIDDEN_CALL_NAMES = {
    "deploy_mesh",
    "dispatch",
    "execute_cycle",
    "heal_node",
    "provision_mesh",
    "scale_mesh",
    "terminate_mesh",
    "trigger_aggressive_healing",
    "trigger_preemptive_checks",
}

FORBIDDEN_TEXT_PATTERNS = (
    ("kubectl-mutation", re.compile(r"\bkubectl\s+(?:apply|delete|patch|scale|rollout|cordon|drain)\b")),
    ("docker-compose-mutation", re.compile(r"\bdocker\s+compose\s+(?:up|down|restart|pull|push)\b")),
    ("alembic-mutation", re.compile(r"\balembic\s+upgrade\b")),
)


@dataclass(frozen=True)
class Finding:
    path: str
    line: int
    kind: str
    detail: str


def _module_for_import_from(node: ast.ImportFrom) -> str:
    if node.module:
        return node.module
    return ""


def _call_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parent = _call_name(node.value)
        return f"{parent}.{node.attr}" if parent else node.attr
    return ""


def _relative(path: Path, root: Path) -> str:
    try:
        return path.relative_to(root).as_posix()
    except ValueError:
        return path.as_posix()


def _is_forbidden_import(module_name: str) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.")
        for prefix in FORBIDDEN_IMPORT_PREFIXES
    )


def _scan_python_source(source: str, path: Path, root: Path) -> list[Finding]:
    rel = _relative(path, root)
    findings: list[Finding] = []
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            Finding(
                path=rel,
                line=exc.lineno or 1,
                kind="syntax-error",
                detail=exc.msg,
            )
        ]

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_import(alias.name):
                    findings.append(
                        Finding(
                            path=rel,
                            line=node.lineno,
                            kind="forbidden-import",
                            detail=alias.name,
                        )
                    )
        elif isinstance(node, ast.ImportFrom):
            module_name = _module_for_import_from(node)
            if _is_forbidden_import(module_name):
                findings.append(
                    Finding(
                        path=rel,
                        line=node.lineno,
                        kind="forbidden-import",
                        detail=module_name,
                    )
                )
        elif isinstance(node, ast.Call):
            call_name = _call_name(node.func)
            leaf = call_name.rsplit(".", 1)[-1]
            if leaf in FORBIDDEN_CALL_NAMES:
                findings.append(
                    Finding(
                        path=rel,
                        line=node.lineno,
                        kind="forbidden-call",
                        detail=call_name,
                    )
                )

    return findings


def _scan_text_patterns(source: str, path: Path, root: Path) -> list[Finding]:
    rel = _relative(path, root)
    findings: list[Finding] = []
    for index, line in enumerate(source.splitlines(), start=1):
        for kind, pattern in FORBIDDEN_TEXT_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        path=rel,
                        line=index,
                        kind=kind,
                        detail="Telegram entrypoint contains direct infrastructure mutation command",
                    )
                )
    return findings


def scan_file(path: Path, root: Path) -> list[Finding]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    findings = _scan_text_patterns(source, path, root)
    if path.suffix == ".py":
        findings.extend(_scan_python_source(source, path, root))
    return findings


def scan_root(root: Path, entrypoints: Iterable[str]) -> tuple[list[Finding], list[str]]:
    findings: list[Finding] = []
    scanned: list[str] = []
    for relative in entrypoints:
        path = root / relative
        if not path.exists() or not path.is_file():
            continue
        scanned.append(relative)
        findings.extend(scan_file(path, root))
    return findings, scanned


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="repository root")
    parser.add_argument(
        "--entrypoint",
        action="append",
        default=None,
        help="Telegram entrypoint path relative to root; can be repeated",
    )
    parser.add_argument("--json", action="store_true", help="emit JSON")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    root = Path(args.root).resolve()
    entrypoints = tuple(args.entrypoint or DEFAULT_TELEGRAM_ENTRYPOINTS)
    findings, scanned = scan_root(root, entrypoints)
    payload = {
        "schema": "x0tta6bl4.telegram_control_boundary.v1",
        "root": str(root),
        "entrypoints_scanned": scanned,
        "entrypoints_requested": list(entrypoints),
        "findings": [asdict(item) for item in findings],
        "finding_count": len(findings),
        "decision": (
            "TELEGRAM_CONTROL_BOUNDARY_OK"
            if not findings
            else "TELEGRAM_CONTROL_BOUNDARY_BLOCKED"
        ),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print(payload["decision"])
        for finding in findings:
            print(f"{finding.path}:{finding.line}: {finding.kind}: {finding.detail}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
