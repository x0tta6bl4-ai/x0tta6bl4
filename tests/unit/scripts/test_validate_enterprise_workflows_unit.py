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


def _ci_workflow_text(include_enterprise_policy: bool = True, include_env_contract: bool = True) -> str:
    commands = [
        "python scripts/validate_runtime_contracts.py",
        "python scripts/validate_version_contract.py",
    ]
    if include_env_contract:
        commands.append("python scripts/validate_production_env_contract.py")
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


def _cd_workflow_text(include_prod_env_contract: bool = True) -> str:
    contract_block = ""
    if include_prod_env_contract:
        contract_block = """
      - name: Validate production runtime env contract (strict)
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          FLASK_SECRET_KEY: ${{ secrets.FLASK_SECRET_KEY }}
          JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}
          CSRF_SECRET_KEY: ${{ secrets.CSRF_SECRET_KEY }}
          OPERATOR_PRIVATE_KEY: ${{ secrets.OPERATOR_PRIVATE_KEY }}
        run: |
          python3 scripts/validate_production_env_contract.py --source process-env --strict-secrets
"""
    return f"""
name: CD
jobs:
  deploy-production:
    steps:
      - uses: actions/checkout@v4
{contract_block}
"""


def _deploy_eks_workflow_text(
    include_prod_env_contract: bool = True,
    include_production_guard: bool = True,
) -> str:
    contract_block = ""
    if include_prod_env_contract:
        guard_line = ""
        if include_production_guard:
            guard_line = "        if: inputs.environment == 'production'\n"
        contract_block = """
      - name: Validate production runtime env contract (strict)
""" + guard_line + """
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          FLASK_SECRET_KEY: ${{ secrets.FLASK_SECRET_KEY }}
          JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}
          CSRF_SECRET_KEY: ${{ secrets.CSRF_SECRET_KEY }}
          OPERATOR_PRIVATE_KEY: ${{ secrets.OPERATOR_PRIVATE_KEY }}
        run: |
          python3 scripts/validate_production_env_contract.py --source process-env --strict-secrets
"""
    return f"""
name: Deploy to EKS
jobs:
  terraform:
    steps:
      - uses: actions/checkout@v4
{contract_block}
"""


def _vault_deployment_workflow_text(include_prod_env_contract: bool = True) -> str:
    contract_block = ""
    if include_prod_env_contract:
        contract_block = """
      - name: Validate production runtime env contract (strict)
        env:
          DATABASE_URL: ${{ secrets.DATABASE_URL }}
          FLASK_SECRET_KEY: ${{ secrets.FLASK_SECRET_KEY }}
          JWT_SECRET_KEY: ${{ secrets.JWT_SECRET_KEY }}
          CSRF_SECRET_KEY: ${{ secrets.CSRF_SECRET_KEY }}
          OPERATOR_PRIVATE_KEY: ${{ secrets.OPERATOR_PRIVATE_KEY }}
        run: |
          python3 scripts/validate_production_env_contract.py --source process-env --strict-secrets
"""
    return f"""
name: Vault Deployment
jobs:
  deploy-production:
    steps:
      - uses: actions/checkout@v4
{contract_block}
"""


def test_release_and_ci_policy_pass_for_enterprise_hardened_config():
    policy = _load_policy_module()
    release_errors = policy.validate_release_workflow_text(_release_workflow_text())
    ci_errors = policy.validate_ci_workflow_text(_ci_workflow_text())
    cd_errors = policy.validate_cd_workflow_text(_cd_workflow_text())
    deploy_eks_errors = policy.validate_deploy_eks_workflow_text(_deploy_eks_workflow_text())
    vault_errors = policy.validate_vault_deployment_workflow_text(_vault_deployment_workflow_text())
    assert release_errors == []
    assert ci_errors == []
    assert cd_errors == []
    assert deploy_eks_errors == []
    assert vault_errors == []


def test_release_policy_flags_continue_on_error_soft_fail():
    policy = _load_policy_module()
    release_text = _release_workflow_text() + "\n      - name: bad\n        continue-on-error: true\n"
    errors = policy.validate_release_workflow_text(release_text)
    assert any("continue-on-error: true" in item for item in errors)


def test_ci_policy_requires_enterprise_workflow_validator_command():
    policy = _load_policy_module()
    errors = policy.validate_ci_workflow_text(_ci_workflow_text(include_enterprise_policy=False))
    assert any("validate_enterprise_workflows.py" in item for item in errors)


def test_ci_policy_requires_production_env_contract_command():
    policy = _load_policy_module()
    errors = policy.validate_ci_workflow_text(_ci_workflow_text(include_env_contract=False))
    assert any("validate_production_env_contract.py" in item for item in errors)


def test_cd_policy_requires_strict_production_env_contract_block():
    policy = _load_policy_module()
    errors = policy.validate_cd_workflow_text(_cd_workflow_text(include_prod_env_contract=False))
    assert any("validate_production_env_contract.py --source process-env --strict-secrets" in item for item in errors)


def test_deploy_eks_policy_requires_strict_production_env_contract_block():
    policy = _load_policy_module()
    errors = policy.validate_deploy_eks_workflow_text(
        _deploy_eks_workflow_text(include_prod_env_contract=False)
    )
    assert any("missing required production contract step" in item for item in errors)


def test_deploy_eks_policy_requires_production_guard_on_contract_step():
    policy = _load_policy_module()
    errors = policy.validate_deploy_eks_workflow_text(
        _deploy_eks_workflow_text(include_production_guard=False)
    )
    assert any("if: inputs.environment == 'production'" in item for item in errors)


def test_vault_deployment_policy_requires_strict_production_env_contract_block():
    policy = _load_policy_module()
    errors = policy.validate_vault_deployment_workflow_text(
        _vault_deployment_workflow_text(include_prod_env_contract=False)
    )
    assert any("validate_production_env_contract.py --source process-env --strict-secrets" in item for item in errors)
