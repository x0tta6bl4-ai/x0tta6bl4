#!/usr/bin/env python3
"""Fail-closed ORM vs migrated DB schema parity check."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import UniqueConstraint

# Ensure repository root is importable when script is executed directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.database import get_schema_parity_report


DEFAULT_ALLOWED_EXTRA_TABLES = {"alembic_version", "es_events", "es_streams", "es_snapshots"}


def _allowed_extra_tables() -> set[str]:
    raw = os.getenv("SCHEMA_PARITY_ALLOWED_EXTRA_TABLES", "")
    env_tables = {item.strip() for item in raw.split(",") if item.strip()}
    return DEFAULT_ALLOWED_EXTRA_TABLES | env_tables


def _sorted(values: set[str]) -> list[str]:
    return sorted(values)


def _normalize_columns(columns: list[str] | tuple[str, ...] | None) -> tuple[str, ...]:
    if not columns:
        return ()
    return tuple(sorted(col for col in columns if col))


def _expected_unique_sets(table) -> set[tuple[str, ...]]:
    expected: set[tuple[str, ...]] = set()

    for column in table.columns:
        if column.unique:
            normalized = _normalize_columns([column.name])
            if normalized:
                expected.add(normalized)

    for constraint in table.constraints:
        if not isinstance(constraint, UniqueConstraint):
            continue
        normalized = _normalize_columns([col.name for col in constraint.columns])
        if normalized:
            expected.add(normalized)

    for index in table.indexes:
        if not index.unique:
            continue
        normalized = _normalize_columns([col.name for col in index.columns])
        if normalized:
            expected.add(normalized)

    return expected


def _expected_index_sets(table) -> set[tuple[str, ...]]:
    expected: set[tuple[str, ...]] = set()

    for column in table.columns:
        if column.index:
            normalized = _normalize_columns([column.name])
            if normalized:
                expected.add(normalized)

    for index in table.indexes:
        normalized = _normalize_columns([col.name for col in index.columns])
        if normalized:
            expected.add(normalized)

    return expected


def _actual_unique_sets(db_inspector, table_name: str) -> set[tuple[str, ...]]:
    actual: set[tuple[str, ...]] = set()

    pk = _normalize_columns(db_inspector.get_pk_constraint(table_name).get("constrained_columns"))
    if pk:
        actual.add(pk)

    for constraint in db_inspector.get_unique_constraints(table_name):
        normalized = _normalize_columns(constraint.get("column_names"))
        if normalized:
            actual.add(normalized)

    for index in db_inspector.get_indexes(table_name):
        if not index.get("unique"):
            continue
        normalized = _normalize_columns(index.get("column_names"))
        if normalized:
            actual.add(normalized)

    return actual


def _actual_index_sets(db_inspector, table_name: str) -> set[tuple[str, ...]]:
    actual = set(_actual_unique_sets(db_inspector, table_name))

    for index in db_inspector.get_indexes(table_name):
        normalized = _normalize_columns(index.get("column_names"))
        if normalized:
            actual.add(normalized)

    return actual


def main() -> int:
    report = get_schema_parity_report()
    if not report["gaps"]:
        print("Schema parity OK: ORM metadata matches migrated DB schema.")
        return 0

    print("Schema parity FAILED:")
    for gap in report["gaps"]:
        print(f"  - {gap}")

    print("Hint: run `alembic upgrade head` and create idempotent migrations for drift.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
