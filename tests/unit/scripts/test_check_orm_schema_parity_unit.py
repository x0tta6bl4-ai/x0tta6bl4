from __future__ import annotations

import importlib.util
import sys

from sqlalchemy import Column, Integer, MetaData, String, Table, UniqueConstraint, create_engine, inspect


def _load_module():
    # Return cached module to avoid re-executing the script (which would
    # attempt to re-register SQLAlchemy ORM internals, causing AssertionError).
    if "check_orm_schema_parity" in sys.modules:
        return sys.modules["check_orm_schema_parity"]

    import pathlib

    repo_root = pathlib.Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "check_orm_schema_parity.py"
    spec = importlib.util.spec_from_file_location("check_orm_schema_parity", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load check_orm_schema_parity module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_normalize_columns_sorts_and_filters_empty_values():
    mod = _load_module()
    assert mod._normalize_columns(["b", "", "a"]) == ("a", "b")  # noqa: SLF001
    assert mod._normalize_columns(None) == ()  # noqa: SLF001


def test_expected_unique_and_index_sets_extract_from_table_metadata():
    mod = _load_module()

    metadata = MetaData()
    table = Table(
        "t_contract",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", String(255), unique=True),
        Column("tenant", String(64), index=True),
        Column("external_id", String(64)),
        UniqueConstraint("tenant", "external_id", name="uq_tenant_external"),
    )
    table.append_constraint(UniqueConstraint("external_id", name="uq_external_id"))

    expected_unique = mod._expected_unique_sets(table)  # noqa: SLF001
    expected_index = mod._expected_index_sets(table)  # noqa: SLF001

    assert ("email",) in expected_unique
    assert ("external_id",) in expected_unique
    assert ("external_id", "tenant") in expected_unique
    assert ("tenant",) in expected_index


def test_actual_unique_and_index_sets_extract_from_database_inspector():
    mod = _load_module()

    metadata = MetaData()
    Table(
        "t_actual",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("email", String(255), unique=True),
        Column("tenant", String(64), index=True),
    )

    engine = create_engine("sqlite:///:memory:")
    metadata.create_all(engine)
    db_inspector = inspect(engine)

    actual_unique = mod._actual_unique_sets(db_inspector, "t_actual")  # noqa: SLF001
    actual_index = mod._actual_index_sets(db_inspector, "t_actual")  # noqa: SLF001

    # PK and unique email must be represented in unique set.
    assert ("id",) in actual_unique
    assert ("email",) in actual_unique
    # Secondary index should be represented in index set.
    assert ("tenant",) in actual_index
