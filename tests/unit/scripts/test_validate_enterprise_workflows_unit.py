from __future__ import annotations

import importlib.util
from pathlib import Path


def _load_policy_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "validate_enterprise_workflows.py"
    spec = importlib.util.spec_from_file_location("enterprise_workflow_policy", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load enterprise workflow policy module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _release_workflow_text() -> str:
    return """
name: Release
jobs:
  release:
    steps:
      - name: Update version files
        run: |
          python scripts/sync_version.py --version "${{ steps.version.outputs.version }}"
          python scripts/validate_version_contract.py
      - name: Publish to PyPI
        if: ${{ secrets.PYPI_API_TOKEN != '' }}
        run: twine upload dist/*
      - name: Login to Docker Hub
        if: ${{ secrets.DOCKER_USERNAME != '' && secrets.DOCKER_PASSWORD != '' }}
        uses: docker/login-action@v3
      - name: Build and push Docker image
        if: ${{ secrets.DOCKER_USERNAME != '' && secrets.DOCKER_PASSWORD != '' }}
        uses: docker/build-push-action@v5
        with:
          push: true
      - name: Build Docker image (push skipped, no credentials)
        if: ${{ secrets.DOCKER_USERNAME == '' || secrets.DOCKER_PASSWORD == '' }}
        uses: docker/build-push-action@v5
        with:
          push: false
"""


def _ci_workflow_text(include_enterprise_policy: bool = True) -> str:
    commands = [
        "python scripts/validate_runtime_contracts.py",
        "python scripts/validate_version_contract.py",
    ]
    if include_enterprise_policy:
        commands.append("python scripts/validate_enterprise_workflows.py")
    command_block = "\n          ".join(commands)
    return f"""
name: CI
jobs:
  test:
    steps:
      - name: Validate gates
        run: |
          {command_block}
"""


def test_release_and_ci_policy_pass_for_enterprise_hardened_config():
    policy = _load_policy_module()
    release_errors = policy.validate_release_workflow_text(_release_workflow_text())
    ci_errors = policy.validate_ci_workflow_text(_ci_workflow_text())
    assert release_errors == []
    assert ci_errors == []


def test_release_policy_flags_continue_on_error_soft_fail():
    policy = _load_policy_module()
    release_text = _release_workflow_text() + "\n      - name: bad\n        continue-on-error: true\n"
    errors = policy.validate_release_workflow_text(release_text)
    assert any("continue-on-error: true" in item for item in errors)


def test_ci_policy_requires_enterprise_workflow_validator_command():
    policy = _load_policy_module()
    errors = policy.validate_ci_workflow_text(_ci_workflow_text(include_enterprise_policy=False))
    assert any("validate_enterprise_workflows.py" in item for item in errors)
