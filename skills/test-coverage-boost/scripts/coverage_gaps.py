#!/usr/bin/env python3
"""
Identifies test coverage gaps in x0tta6bl4.

Compares src/ modules against tests/unit/ to find:
- Source modules with no corresponding test file
- Source modules with test files but low coverage

Output: prioritized list of modules needing tests.
"""

import os
import sys
from pathlib import Path


def find_source_modules(src_dir: Path) -> dict[str, list[Path]]:
    """Find all Python modules in src/ grouped by package."""
    modules: dict[str, list[Path]] = {}

    for py_file in sorted(src_dir.rglob('*.py')):
        if '__pycache__' in str(py_file) or py_file.name == '__init__.py':
            continue

        rel = py_file.relative_to(src_dir)
        package = str(rel.parent) if str(rel.parent) != '.' else 'root'

        if package not in modules:
            modules[package] = []
        modules[package].append(py_file)

    return modules


def find_test_files(tests_dir: Path) -> set[str]:
    """Find all test file names (normalized) in tests/unit/."""
    test_names = set()
    unit_dir = tests_dir / 'unit'

    if not unit_dir.exists():
        return test_names

    for py_file in unit_dir.rglob('test_*.py'):
        # Normalize: test_app_endpoints.py -> app_endpoints
        # Remove only leading `test_` to preserve names like `test_integration`.
        stem = py_file.stem
        if stem.startswith('test_'):
            stem = stem[len('test_'):]
        name = stem.replace('_unit', '')
        test_names.add(name)

    return test_names


def main():
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    src_dir = project_root / 'src'
    tests_dir = project_root / 'tests'

    if not src_dir.exists():
        print(f"ERROR: {src_dir} not found")
        sys.exit(1)

    modules = find_source_modules(src_dir)
    existing_tests = find_test_files(tests_dir)

    # Priority weights
    PRIORITY = {
        'security': 1, 'core': 1, 'api': 1,
        'network': 2, 'self_healing': 2, 'consensus': 2,
        'ml': 3, 'dao': 3, 'monitoring': 3,
    }

    untested = []
    tested = []

    for package, files in sorted(modules.items()):
        for f in files:
            module_name = f.stem
            module_norm = module_name.replace('-', '_')
            # Check if any test file matches this module
            has_test = any(
                module_name in t
                or t in module_name
                or module_norm in t.replace('-', '_')
                or t.replace('-', '_') in module_norm
                for t in existing_tests
            )

            priority = PRIORITY.get(package.split('/')[0] if '/' in package else package, 4)

            if has_test:
                tested.append((priority, package, module_name))
            else:
                untested.append((priority, package, module_name))

    # Sort by priority
    untested.sort(key=lambda x: (x[0], x[1], x[2]))

    print("=" * 60)
    print("UNTESTED MODULES (no matching test file found)")
    print("=" * 60)

    current_priority = None
    for priority, package, module in untested:
        p_label = {1: "P0-CRITICAL", 2: "P1-HIGH", 3: "P2-MEDIUM"}.get(priority, "P3-LOW")
        if priority != current_priority:
            current_priority = priority
            print(f"\n--- {p_label} ---")
        print(f"  src/{package}/{module}.py")

    print(f"\n{'='*60}")
    print(f"Total: {len(untested)} untested, {len(tested)} tested")
    print(f"Coverage gap: {len(untested)}/{len(untested)+len(tested)} modules ({100*len(untested)//(len(untested)+len(tested))}%)")


if __name__ == '__main__':
    main()
