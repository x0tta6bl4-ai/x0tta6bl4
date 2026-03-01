#!/usr/bin/env python3
"""Fail-closed policy audit for Alembic migration safety and idempotency."""

from __future__ import annotations

import argparse
import ast
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = REPO_ROOT / "alembic" / "versions"

# For backward compatibility, we enforce strict policy on the latest N revisions
# in the current linear head chain. Legacy migrations may predate policy adoption.
DEFAULT_ENFORCED_DEPTH = max(1, int(os.getenv("MIGRATION_POLICY_ENFORCED_DEPTH", "3")))


@dataclass(frozen=True)
class RevisionMeta:
    revision: str
    down_revision: str | None
    path: Path


@dataclass(frozen=True)
class Finding:
    path: str
    message: str

    def format(self) -> str:
        return f"{self.path}: {self.message}"


def _to_repo_relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _const_string(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _parse_down_revision(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant):
        if isinstance(node.value, str):
            return node.value
        if node.value is None:
            return None

    if isinstance(node, (ast.Tuple, ast.List)) and node.elts:
        first = node.elts[0]
        return _const_string(first)

    return None


def parse_revision_metadata(path: Path) -> RevisionMeta:
    tree = ast.parse(_read_text(path), filename=str(path))

    revision: str | None = None
    down_revision: str | None = None

    for node in tree.body:
        if not isinstance(node, ast.Assign):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                target_id = node.target.id
                if target_id == "revision":
                    revision = _const_string(node.value) if node.value else None
                elif target_id == "down_revision":
                    down_revision = _parse_down_revision(node.value) if node.value else None
            continue
        for target in node.targets:
            if not isinstance(target, ast.Name):
                continue
            if target.id == "revision":
                revision = _const_string(node.value)
            elif target.id == "down_revision":
                down_revision = _parse_down_revision(node.value)

    if not revision:
        raise ValueError(f"Missing revision id in {path}")

    return RevisionMeta(revision=revision, down_revision=down_revision, path=path)


def discover_revisions(versions_dir: Path = VERSIONS_DIR) -> dict[str, RevisionMeta]:
    revisions: dict[str, RevisionMeta] = {}
    for path in sorted(versions_dir.glob("*.py")):
        if path.name.startswith("__"):
            continue
        meta = parse_revision_metadata(path)
        revisions[meta.revision] = meta
    return revisions


def find_heads(revisions: dict[str, RevisionMeta]) -> list[str]:
    parents = {meta.down_revision for meta in revisions.values() if meta.down_revision}
    return sorted([revision for revision in revisions.keys() if revision not in parents])


def latest_linear_chain(
    revisions: dict[str, RevisionMeta],
    *,
    depth: int,
    head_revision: str | None,
) -> list[RevisionMeta]:
    heads = find_heads(revisions)
    if not heads:
        raise ValueError("No Alembic heads found")

    head = head_revision or heads[0]
    if head not in revisions:
        raise ValueError(f"Head revision {head!r} not found")

    chain: list[RevisionMeta] = []
    current = head

    while current and len(chain) < max(1, depth):
        meta = revisions.get(current)
        if meta is None:
            raise ValueError(f"Broken revision chain at {current!r}")
        chain.append(meta)
        current = meta.down_revision

    return chain


def _func_attr_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _contains_guard(source: str, tokens: Iterable[str]) -> bool:
    return any(token in source for token in tokens)


def _check_nullable_transitions(meta: RevisionMeta, tree: ast.AST, source: str) -> list[Finding]:
    findings: list[Finding] = []
    marker = "MIGRATION_ALLOW_NULLABLE_TO_NON_NULLABLE"

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if _func_attr_name(node) != "alter_column":
            continue

        nullable_kw = None
        for kw in node.keywords:
            if kw.arg == "nullable":
                nullable_kw = kw
                break

        if nullable_kw is None:
            continue
        if not isinstance(nullable_kw.value, ast.Constant) or nullable_kw.value.value is not False:
            continue

        has_server_default = any(
            kw.arg in {"server_default", "existing_server_default"}
            and not (
                isinstance(kw.value, ast.Constant)
                and kw.value.value is None
            )
            for kw in node.keywords
        )
        has_explicit_marker = marker in source

        if not has_server_default and not has_explicit_marker:
            findings.append(
                Finding(
                    path=_to_repo_relative(meta.path),
                    message=(
                        "nullable=False transition without server_default/backfill marker; "
                        f"add explicit marker {marker}=True after validated backfill"
                    ),
                )
            )

    return findings


def _check_idempotent_style(meta: RevisionMeta, source: str) -> list[Finding]:
    findings: list[Finding] = []

    # Operations that should be guarded against "already exists" / "missing" states.
    operations = {
        "table": [".create_table(", ".drop_table("],
        "column": [".add_column(", ".drop_column("],
        "index": [".create_index(", ".drop_index("],
    }
    guards = {
        "table": ("_table_exists(", "has_table(", "checkfirst=True"),
        "column": ("_column_exists(", "_column_info(", "get_columns("),
        "index": ("_index_exists(", "get_indexes("),
    }

    local_findings: list[str] = []

    for key, patterns in operations.items():
        if not any(pattern in source for pattern in patterns):
            continue
        if _contains_guard(source, guards[key]):
            continue
        local_findings.append(key)

    for key in sorted(set(local_findings)):
        findings.append(
            Finding(
                path=_to_repo_relative(meta.path),
                message=(
                    f"{key} DDL operations are not guarded for idempotent migration style "
                    "(missing existence checks)"
                ),
            )
        )

    return findings


def audit_migrations(
    *,
    depth: int,
    head_revision: str | None = None,
) -> list[Finding]:
    revisions = discover_revisions()
    chain = latest_linear_chain(revisions, depth=depth, head_revision=head_revision)

    findings: list[Finding] = []
    for meta in chain:
        source = _read_text(meta.path)
        tree = ast.parse(source, filename=str(meta.path))
        findings.extend(_check_nullable_transitions(meta, tree, source))
        findings.extend(_check_idempotent_style(meta, source))

    return findings


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--depth",
        type=int,
        default=DEFAULT_ENFORCED_DEPTH,
        help="How many latest revisions from head to audit",
    )
    parser.add_argument(
        "--head-revision",
        default=None,
        help="Optional explicit head revision id",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    depth = max(1, int(args.depth))

    try:
        findings = audit_migrations(depth=depth, head_revision=args.head_revision)
    except Exception as exc:
        print(f"Migration policy audit FAILED: {exc}")
        return 1

    if findings:
        print("Migration policy audit FAILED")
        for finding in findings:
            print(f" - {finding.format()}")
        return 1

    print(f"Migration policy audit passed (latest_depth={depth})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
