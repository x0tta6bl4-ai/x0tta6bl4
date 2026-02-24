#!/usr/bin/env python3
"""Fail CI when enterprise workflow hardening invariants are violated."""

from __future__ import annotations

import re
import sys
from pathlib import Path


RELEASE_WORKFLOW = Path(".github/workflows/release.yml")
CI_WORKFLOW = Path(".github/workflows/ci.yml")
CD_WORKFLOW = Path(".github/workflows/cd.yml")
DEPLOY_EKS_WORKFLOW = Path(".github/workflows/deploy-eks.yaml")
VAULT_DEPLOYMENT_WORKFLOW = Path(".github/workflows/vault-deployment.yml")


def _find_step_block(workflow_text: str, step_name: str) -> str | None:
    pattern = re.compile(
        rf"(?ms)^\s*-\s+name:\s*{re.escape(step_name)}\s*\n(?P<body>.*?)(?=^\s*-\s+name:|\Z)"
    )
    match = pattern.search(workflow_text)
    if not match:
        return None
    return match.group("body")


def _find_job_block(workflow_text: str, job_name: str) -> str | None:
    pattern = re.compile(
        rf"(?ms)^\s{{2}}{re.escape(job_name)}:\s*\n(?P<body>.*?)(?=^\s{{2}}[A-Za-z0-9_-]+:\s*\n|\Z)"
    )
    match = pattern.search(workflow_text)
    if not match:
        return None
    return match.group("body")


def validate_release_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []

    if "continue-on-error: true" in workflow_text:
        errors.append("release.yml: `continue-on-error: true` is forbidden for enterprise release flow")

    if "python scripts/sync_version.py --version" not in workflow_text:
        errors.append("release.yml: missing centralized version sync command")
    if "python scripts/validate_version_contract.py" not in workflow_text:
        errors.append("release.yml: missing version contract validation command")

    pypi_step = _find_step_block(workflow_text, "Publish to PyPI")
    if pypi_step is None:
        errors.append("release.yml: missing `Publish to PyPI` step")
    elif not re.search(
        r"^\s*if:\s*\$\{\{\s*secrets\.PYPI_API_TOKEN\s*!=\s*''\s*\}\}",
        pypi_step,
        re.MULTILINE,
    ):
        errors.append(
            "release.yml: `Publish to PyPI` must be guarded by `if: ${{ secrets.PYPI_API_TOKEN != '' }}`"
        )

    docker_guard_pattern = re.compile(
        r"^\s*if:\s*\$\{\{\s*secrets\.DOCKER_USERNAME\s*!=\s*''\s*&&\s*secrets\.DOCKER_PASSWORD\s*!=\s*''\s*\}\}",
        re.MULTILINE,
    )
    for step_name in ("Login to Docker Hub", "Build and push Docker image"):
        step_block = _find_step_block(workflow_text, step_name)
        if step_block is None:
            errors.append(f"release.yml: missing `{step_name}` step")
            continue
        if not docker_guard_pattern.search(step_block):
            errors.append(f"release.yml: `{step_name}` must be guarded by both Docker secrets")

    push_step = _find_step_block(workflow_text, "Build and push Docker image")
    if push_step is not None and not re.search(r"^\s*push:\s*true\s*$", push_step, re.MULTILINE):
        errors.append("release.yml: `Build and push Docker image` must set `push: true`")

    local_build_step = _find_step_block(workflow_text, "Build Docker image (push skipped, no credentials)")
    if local_build_step is None:
        errors.append("release.yml: missing fallback local Docker build step")
    else:
        if not re.search(
            r"^\s*if:\s*\$\{\{\s*secrets\.DOCKER_USERNAME\s*==\s*''\s*\|\|\s*secrets\.DOCKER_PASSWORD\s*==\s*''\s*\}\}",
            local_build_step,
            re.MULTILINE,
        ):
            errors.append("release.yml: fallback local Docker build step must be guarded by missing Docker secrets")
        if not re.search(r"^\s*push:\s*false\s*$", local_build_step, re.MULTILINE):
            errors.append("release.yml: fallback local Docker build step must set `push: false`")

    return errors


def validate_ci_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []
    required_commands = (
        "python scripts/validate_runtime_contracts.py",
        "python scripts/validate_version_contract.py",
        "python scripts/validate_production_env_contract.py",
        "python scripts/validate_enterprise_workflows.py",
    )

    for command in required_commands:
        if command not in workflow_text:
            errors.append(f"ci.yml: missing required command `{command}`")
    return errors


def validate_cd_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []
    job_block = _find_job_block(workflow_text, "deploy-production")
    if job_block is None:
        return ["cd.yml: missing required job `deploy-production`"]

    required_tokens = (
        "Validate production runtime env contract (strict)",
        "python3 scripts/validate_production_env_contract.py --source process-env --strict-secrets",
        "${{ secrets.DATABASE_URL }}",
        "${{ secrets.FLASK_SECRET_KEY }}",
        "${{ secrets.JWT_SECRET_KEY }}",
        "${{ secrets.CSRF_SECRET_KEY }}",
        "${{ secrets.OPERATOR_PRIVATE_KEY }}",
    )

    for token in required_tokens:
        if token not in job_block:
            errors.append(f"cd.yml: missing required production contract token `{token}`")
    return errors


def validate_deploy_eks_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []
    job_block = _find_job_block(workflow_text, "terraform")
    if job_block is None:
        return ["deploy-eks.yaml: missing required job `terraform`"]

    step_block = _find_step_block(job_block, "Validate production runtime env contract (strict)")
    if step_block is None:
        return [
            "deploy-eks.yaml: missing required production contract step "
            "`Validate production runtime env contract (strict)`"
        ]

    required_step_tokens = (
        "python3 scripts/validate_production_env_contract.py --source process-env --strict-secrets",
        "${{ secrets.DATABASE_URL }}",
        "${{ secrets.FLASK_SECRET_KEY }}",
        "${{ secrets.JWT_SECRET_KEY }}",
        "${{ secrets.CSRF_SECRET_KEY }}",
        "${{ secrets.OPERATOR_PRIVATE_KEY }}",
    )

    if not re.search(r"^\s*if:\s*inputs\.environment\s*==\s*'production'\s*$", step_block, re.MULTILINE):
        errors.append(
            "deploy-eks.yaml: production contract step must be guarded by "
            "`if: inputs.environment == 'production'`"
        )

    for token in required_step_tokens:
        if token not in step_block:
            errors.append(
                f"deploy-eks.yaml: missing required production contract token `{token}` in strict step"
            )
    return errors


def validate_vault_deployment_workflow_text(workflow_text: str) -> list[str]:
    errors: list[str] = []
    job_block = _find_job_block(workflow_text, "deploy-production")
    if job_block is None:
        return ["vault-deployment.yml: missing required job `deploy-production`"]

    required_tokens = (
        "name: Validate production runtime env contract (strict)",
        "python3 scripts/validate_production_env_contract.py --source process-env --strict-secrets",
        "${{ secrets.DATABASE_URL }}",
        "${{ secrets.FLASK_SECRET_KEY }}",
        "${{ secrets.JWT_SECRET_KEY }}",
        "${{ secrets.CSRF_SECRET_KEY }}",
        "${{ secrets.OPERATOR_PRIVATE_KEY }}",
    )

    for token in required_tokens:
        if token not in job_block:
            errors.append(f"vault-deployment.yml: missing required production contract token `{token}`")
    return errors


def _read_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def main() -> int:
    errors: list[str] = []

    release_text = _read_text(RELEASE_WORKFLOW)
    if release_text is None:
        errors.append(f"missing workflow file: {RELEASE_WORKFLOW}")
    else:
        errors.extend(validate_release_workflow_text(release_text))

    ci_text = _read_text(CI_WORKFLOW)
    if ci_text is None:
        errors.append(f"missing workflow file: {CI_WORKFLOW}")
    else:
        errors.extend(validate_ci_workflow_text(ci_text))

    cd_text = _read_text(CD_WORKFLOW)
    if cd_text is None:
        errors.append(f"missing workflow file: {CD_WORKFLOW}")
    else:
        errors.extend(validate_cd_workflow_text(cd_text))

    deploy_eks_text = _read_text(DEPLOY_EKS_WORKFLOW)
    if deploy_eks_text is None:
        errors.append(f"missing workflow file: {DEPLOY_EKS_WORKFLOW}")
    else:
        errors.extend(validate_deploy_eks_workflow_text(deploy_eks_text))

    vault_deployment_text = _read_text(VAULT_DEPLOYMENT_WORKFLOW)
    if vault_deployment_text is None:
        errors.append(f"missing workflow file: {VAULT_DEPLOYMENT_WORKFLOW}")
    else:
        errors.extend(validate_vault_deployment_workflow_text(vault_deployment_text))

    if errors:
        print("Enterprise workflow policy violations:")
        for error in errors:
            print(f" - {error}")
        return 1

    print("Enterprise workflow policy check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
