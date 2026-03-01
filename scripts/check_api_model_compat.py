#!/usr/bin/env python3
"""Validate backward/forward compatibility of API BaseModel contracts."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_ROOT = REPO_ROOT / "src" / "api"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "api" / "api_model_contract_snapshot.json"


def _is_basemodel_base(node: ast.expr) -> bool:
    if isinstance(node, ast.Name):
        return node.id == "BaseModel"
    if isinstance(node, ast.Attribute):
        return node.attr == "BaseModel"
    if isinstance(node, ast.Subscript):
        return _is_basemodel_base(node.value)
    return False


def _field_kind(class_name: str) -> str:
    if class_name.endswith("Request"):
        return "request"
    if class_name.endswith("Response"):
        return "response"
    return "generic"


@dataclass(frozen=True)
class ModelField:
    required: bool
    annotation_ast: str


def _extract_models_from_file(path: Path) -> dict[str, dict[str, ModelField]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    models: dict[str, dict[str, ModelField]] = {}

    for node in tree.body:
        if not isinstance(node, ast.ClassDef):
            continue
        if not any(_is_basemodel_base(base) for base in node.bases):
            continue

        fields: dict[str, ModelField] = {}
        for stmt in node.body:
            if not isinstance(stmt, ast.AnnAssign):
                continue
            if not isinstance(stmt.target, ast.Name):
                continue

            field_name = stmt.target.id
            if field_name.startswith("_"):
                continue

            fields[field_name] = ModelField(
                required=stmt.value is None,
                annotation_ast=ast.dump(stmt.annotation, include_attributes=False),
            )

        model_key = f"{path.relative_to(REPO_ROOT).as_posix()}:{node.name}"
        models[model_key] = fields

    return models


def collect_models(source_root: Path) -> dict[str, dict[str, dict[str, Any]]]:
    collected: dict[str, dict[str, dict[str, Any]]] = {}
    for path in sorted(source_root.rglob("*.py")):
        if path.name.startswith("_"):
            continue
        if path.name == "__init__.py":
            continue
        file_models = _extract_models_from_file(path)
        for model_key, fields in file_models.items():
            collected[model_key] = {
                name: {
                    "required": meta.required,
                    "annotation_ast": meta.annotation_ast,
                }
                for name, meta in sorted(fields.items())
            }
    return dict(sorted(collected.items()))


def _load_baseline(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _check_compatibility(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    errors: list[str] = []

    for model_key, baseline_fields in baseline.items():
        if model_key not in current:
            errors.append(f"model removed: {model_key}")
            continue

        current_fields = current[model_key]
        class_name = model_key.split(":")[-1]
        kind = _field_kind(class_name)

        for field_name, old_meta in baseline_fields.items():
            if field_name not in current_fields:
                errors.append(f"field removed: {model_key}.{field_name}")
                continue

            new_meta = current_fields[field_name]
            if old_meta["annotation_ast"] != new_meta["annotation_ast"]:
                errors.append(
                    f"type changed: {model_key}.{field_name} "
                    f"(old={old_meta['annotation_ast']} new={new_meta['annotation_ast']})"
                )

            if not old_meta["required"] and new_meta["required"]:
                errors.append(f"field became required: {model_key}.{field_name}")

        new_fields = sorted(set(current_fields.keys()) - set(baseline_fields.keys()))
        for field_name in new_fields:
            if kind == "request" and current_fields[field_name]["required"]:
                errors.append(
                    f"new required request field: {model_key}.{field_name} "
                    "(must be optional/defaulted for backward compatibility)"
                )

    return errors


def _write_baseline(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate API BaseModel compatibility.")
    parser.add_argument(
        "--source-root",
        default=str(DEFAULT_SOURCE_ROOT),
        help="Path to API source root (default: src/api).",
    )
    parser.add_argument(
        "--baseline",
        default=str(DEFAULT_BASELINE),
        help="Path to baseline snapshot JSON.",
    )
    parser.add_argument(
        "--update-baseline",
        action="store_true",
        help="Rewrite baseline snapshot from current sources.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    source_root = Path(args.source_root).resolve()
    baseline_path = Path(args.baseline).resolve()

    if not source_root.exists():
        print(f"Source root does not exist: {source_root}")
        return 2

    current = collect_models(source_root)

    if args.update_baseline:
        _write_baseline(baseline_path, current)
        print(f"Updated API model contract baseline: {baseline_path}")
        print(f"Models tracked: {len(current)}")
        return 0

    if not baseline_path.exists():
        print(f"Baseline not found: {baseline_path}")
        print("Run with --update-baseline to create initial snapshot.")
        return 2

    baseline = _load_baseline(baseline_path)
    errors = _check_compatibility(baseline, current)
    if errors:
        print("API model compatibility check FAILED:")
        for err in errors:
            print(f" - {err}")
        print(
            "If changes are intentional and non-breaking for clients, "
            "update baseline with --update-baseline in the same PR."
        )
        return 1

    print(
        "API model compatibility check passed: "
        f"models={len(current)}, baseline={baseline_path.name}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
