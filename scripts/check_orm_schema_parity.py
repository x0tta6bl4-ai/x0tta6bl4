#!/usr/bin/env python3
"""Fail-closed ORM vs migrated DB schema parity check."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from sqlalchemy import UniqueConstraint, inspect

# Ensure repository root is importable when script is executed directly.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.database import Base, engine


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
    inspector = inspect(engine)
    actual_tables = set(inspector.get_table_names())
    expected_tables = set(Base.metadata.tables.keys())
    allowed_extra = _allowed_extra_tables()

    missing_tables = expected_tables - actual_tables
    extra_tables = actual_tables - expected_tables - allowed_extra

    missing_columns: dict[str, list[str]] = {}
    extra_columns: dict[str, list[str]] = {}
    missing_unique_constraints: dict[str, list[list[str]]] = {}
    missing_indexes: dict[str, list[list[str]]] = {}

    for table_name in _sorted(expected_tables & actual_tables):
        db_cols = {col["name"] for col in inspector.get_columns(table_name)}
        orm_cols = set(Base.metadata.tables[table_name].columns.keys())
        if orm_cols - db_cols:
            missing_columns[table_name] = _sorted(orm_cols - db_cols)
        if db_cols - orm_cols:
            extra_columns[table_name] = _sorted(db_cols - orm_cols)

        expected_unique = _expected_unique_sets(Base.metadata.tables[table_name])
        actual_unique = _actual_unique_sets(inspector, table_name)
        missing_unique = sorted(list(cols) for cols in (expected_unique - actual_unique))
        if missing_unique:
            missing_unique_constraints[table_name] = missing_unique

        expected_indexes = _expected_index_sets(Base.metadata.tables[table_name])
        actual_indexes = _actual_index_sets(inspector, table_name)
        missing_index = sorted(list(cols) for cols in (expected_indexes - actual_indexes))
        if missing_index:
            missing_indexes[table_name] = missing_index

    if (
        not missing_tables
        and not extra_tables
        and not missing_columns
        and not extra_columns
        and not missing_unique_constraints
        and not missing_indexes
    ):
        print("Schema parity OK: ORM metadata matches migrated DB schema.")
        return 0

    print("Schema parity FAILED:")
    if missing_tables:
        print(f"  missing tables: {_sorted(missing_tables)}")
    if extra_tables:
        print(f"  extra tables (not allowed): {_sorted(extra_tables)}")
    if missing_columns:
        print("  missing columns:")
        for table_name in _sorted(set(missing_columns.keys())):
            print(f"    - {table_name}: {missing_columns[table_name]}")
    if extra_columns:
        print("  extra columns:")
        for table_name in _sorted(set(extra_columns.keys())):
            print(f"    - {table_name}: {extra_columns[table_name]}")
    if missing_unique_constraints:
        print("  missing unique constraints/indexes:")
        for table_name in _sorted(set(missing_unique_constraints.keys())):
            print(f"    - {table_name}: {missing_unique_constraints[table_name]}")
    if missing_indexes:
        print("  missing indexes:")
        for table_name in _sorted(set(missing_indexes.keys())):
            print(f"    - {table_name}: {missing_indexes[table_name]}")

    print("Hint: run `alembic upgrade head` and create idempotent migrations for drift.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
