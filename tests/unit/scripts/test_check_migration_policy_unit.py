from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "check_migration_policy.py"
    spec = importlib.util.spec_from_file_location("check_migration_policy", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load check_migration_policy module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_parse_revision_metadata_supports_string_down_revision(tmp_path):
    mod = _load_module()
    path = tmp_path / "rev.py"
    path.write_text(
        "revision = 'rev_a'\n"
        "down_revision = 'rev_b'\n",
        encoding="utf-8",
    )

    meta = mod.parse_revision_metadata(path)

    assert meta.revision == "rev_a"
    assert meta.down_revision == "rev_b"


def test_parse_revision_metadata_supports_list_down_revision(tmp_path):
    mod = _load_module()
    path = tmp_path / "rev.py"
    path.write_text(
        "revision = 'rev_a'\n"
        "down_revision = ['rev_b']\n",
        encoding="utf-8",
    )

    meta = mod.parse_revision_metadata(path)

    assert meta.revision == "rev_a"
    assert meta.down_revision == "rev_b"


def test_latest_linear_chain_from_head():
    mod = _load_module()

    rev1 = mod.RevisionMeta(revision="r1", down_revision=None, path=Path("r1.py"))
    rev2 = mod.RevisionMeta(revision="r2", down_revision="r1", path=Path("r2.py"))
    rev3 = mod.RevisionMeta(revision="r3", down_revision="r2", path=Path("r3.py"))

    chain = mod.latest_linear_chain(
        {"r1": rev1, "r2": rev2, "r3": rev3},
        depth=2,
        head_revision="r3",
    )

    assert [item.revision for item in chain] == ["r3", "r2"]


def test_nullable_false_without_marker_or_default_is_flagged(tmp_path):
    mod = _load_module()
    path = tmp_path / "risk.py"
    source = (
        "from alembic import op\n"
        "def upgrade():\n"
        "    op.alter_column('users', 'email', nullable=False)\n"
    )
    tree = __import__("ast").parse(source)
    meta = mod.RevisionMeta("r", None, path)

    findings = mod._check_nullable_transitions(meta, tree, source)  # noqa: SLF001

    assert findings
    assert "nullable=False transition" in findings[0].message


def test_nullable_false_with_marker_is_allowed(tmp_path):
    mod = _load_module()
    path = tmp_path / "safe.py"
    source = (
        "from alembic import op\n"
        "MIGRATION_ALLOW_NULLABLE_TO_NON_NULLABLE = True\n"
        "def upgrade():\n"
        "    op.alter_column('users', 'email', nullable=False)\n"
    )
    tree = __import__("ast").parse(source)
    meta = mod.RevisionMeta("r", None, path)

    findings = mod._check_nullable_transitions(meta, tree, source)  # noqa: SLF001

    assert findings == []


def test_idempotent_style_flags_create_table_without_guard(tmp_path):
    mod = _load_module()
    path = tmp_path / "unsafe.py"
    meta = mod.RevisionMeta("r", None, path)

    findings = mod._check_idempotent_style(meta, "op.create_table('t')")  # noqa: SLF001

    assert findings
    assert "idempotent migration style" in findings[0].message


def test_idempotent_style_allows_guarded_operations(tmp_path):
    mod = _load_module()
    path = tmp_path / "safe.py"
    meta = mod.RevisionMeta("r", None, path)

    source = "_table_exists(inspector, 't')\nop.create_table('t')\n"
    findings = mod._check_idempotent_style(meta, source)  # noqa: SLF001

    assert findings == []
