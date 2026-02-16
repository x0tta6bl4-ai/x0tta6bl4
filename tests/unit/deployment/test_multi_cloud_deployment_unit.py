"""
Comprehensive unit tests for src/deployment/multi_cloud_deployment.py.

Tests cover:
- CloudProvider enum
- DeploymentConfig / DeploymentResult dataclasses
- MultiCloudDeployment: deploy, build_and_push (AWS/Azure/GCP), deploy_to_cluster,
  get_cluster_credentials (EKS/AKS/GKE), health_check, check_command
- deploy_multi_cloud convenience function
- All error paths, edge cases, timeouts
"""

import os
import subprocess
import time
from unittest.mock import MagicMock, call, patch

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.core.safe_subprocess import SafeCommandResult
from src.deployment.multi_cloud_deployment import (CloudProvider,
                                                   DeploymentConfig,
                                                   DeploymentResult,
                                                   MultiCloudDeployment,
                                                   deploy_multi_cloud)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config(
    provider=CloudProvider.AWS, region="us-east-1", cluster="test-cluster", **kwargs
):
    return DeploymentConfig(
        provider=provider, region=region, cluster_name=cluster, **kwargs
    )


def _ok(stdout="", stderr=""):
    return SafeCommandResult(
        success=True, returncode=0, stdout=stdout, stderr=stderr, command=[]
    )


def _fail(stderr="error"):
    return SafeCommandResult(
        success=False, returncode=1, stdout="", stderr=stderr, command=[]
    )


# ---------------------------------------------------------------------------
# CloudProvider enum
# ---------------------------------------------------------------------------


class TestCloudProvider:
    def test_values(self):
        assert CloudProvider.AWS.value == "aws"
        assert CloudProvider.AZURE.value == "azure"
        assert CloudProvider.GCP.value == "gcp"
        assert CloudProvider.LOCAL.value == "local"

    def test_from_string(self):
        assert CloudProvider("aws") == CloudProvider.AWS

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            CloudProvider("invalid")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


class TestDeploymentConfig:
    def test_defaults(self):
        cfg = _make_config()
        assert cfg.namespace == "default"
        assert cfg.image_name == "x0tta6bl4"
        assert cfg.image_tag == "latest"
        assert cfg.helm_release_name == "x0tta6bl4"
        assert cfg.helm_chart_path == "./helm/x0tta6bl4"
        assert cfg.values_file is None
        assert cfg.wait_timeout == 600
        assert cfg.health_check_timeout == 300

    def test_custom(self):
        cfg = _make_config(namespace="prod", image_tag="v1.0", values_file="vals.yaml")
        assert cfg.namespace == "prod"
        assert cfg.image_tag == "v1.0"
        assert cfg.values_file == "vals.yaml"


class TestDeploymentResult:
    def test_defaults(self):
        r = DeploymentResult(
            success=True,
            provider=CloudProvider.AWS,
            region="us-east-1",
            cluster_name="c",
        )
        assert r.image_url is None
        assert r.error is None
        assert r.deployment_time == 0.0

    def test_full(self):
        r = DeploymentResult(
            success=False,
            provider=CloudProvider.GCP,
            region="eu",
            cluster_name="c",
            image_url="img:v1",
            error="oops",
            deployment_time=42.0,
        )
        assert r.error == "oops"
        assert r.deployment_time == 42.0


# ---------------------------------------------------------------------------
# MultiCloudDeployment.__init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_init_stores_config(self):
        cfg = _make_config()
        d = MultiCloudDeployment(cfg)
        assert d.config is cfg
        assert isinstance(d.start_time, float)


# ---------------------------------------------------------------------------
# _check_command
# ---------------------------------------------------------------------------


class TestCheckCommand:
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_command_found(self, mock_sp):
        mock_sp.run.return_value = _ok()
        d = MultiCloudDeployment(_make_config())
        assert d._check_command("helm") is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_command_not_found(self, mock_sp):
        mock_sp.run.return_value = _fail()
        d = MultiCloudDeployment(_make_config())
        assert d._check_command("helm") is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_command_exception(self, mock_sp):
        mock_sp.run.side_effect = RuntimeError("boom")
        d = MultiCloudDeployment(_make_config())
        assert d._check_command("helm") is False

    @patch("src.deployment.multi_cloud_deployment.os")
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_windows_uses_where(self, mock_sp, mock_os):
        mock_os.name = "nt"
        mock_os.getenv = os.getenv  # pass through for other calls
        mock_sp.run.return_value = _ok()
        d = MultiCloudDeployment(_make_config())
        d._check_command("helm")
        args = mock_sp.run.call_args[0][0]
        assert args[0] == "where"


# ---------------------------------------------------------------------------
# _build_and_push_image dispatching
# ---------------------------------------------------------------------------


class TestBuildAndPushDispatch:
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_unsupported_provider(self, mock_sp):
        cfg = _make_config(provider=CloudProvider.LOCAL)
        d = MultiCloudDeployment(cfg)
        assert d._build_and_push_image() is None

    def test_dispatch_aws(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        with patch.object(d, "_build_and_push_aws", return_value="img") as m:
            assert d._build_and_push_image() == "img"
            m.assert_called_once()

    def test_dispatch_azure(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AZURE))
        with patch.object(d, "_build_and_push_azure", return_value="img") as m:
            assert d._build_and_push_image() == "img"
            m.assert_called_once()

    def test_dispatch_gcp(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.GCP))
        with patch.object(d, "_build_and_push_gcp", return_value="img") as m:
            assert d._build_and_push_image() == "img"
            m.assert_called_once()

    def test_exception_returns_none(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        with patch.object(d, "_build_and_push_aws", side_effect=RuntimeError):
            assert d._build_and_push_image() is None


# ---------------------------------------------------------------------------
# _build_and_push_aws
# ---------------------------------------------------------------------------


class TestBuildAndPushAWS:
    def _deployer(self):
        return MultiCloudDeployment(
            _make_config(provider=CloudProvider.AWS, region="us-east-1")
        )

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_cli_missing(self, mock_sp):
        mock_sp.run.return_value = _fail()  # _check_command fails
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_credentials_not_configured(self, mock_sp):
        results = [_ok(), _fail()]  # check_command ok, get-caller-identity fails
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_empty_account(self, mock_sp):
        results = [_ok(), _ok(stdout="")]  # check ok, account empty
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_build_fails(self, mock_sp):
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _fail("build err"),  # docker build
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_ecr_login_fails(self, mock_sp):
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _fail("login err"),  # ecr get-login-password
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_docker_login_fails(self, mock_sp):
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _ok(stdout="password123"),  # ecr get-login-password
            _fail("docker login err"),  # docker login
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_repo_check_exists(self, mock_sp):
        """Full success path: repo already exists."""
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _ok(stdout="password123"),  # ecr get-login-password
            _ok(),  # docker login
            _ok(),  # describe-repositories (exists)
            _ok(),  # docker tag
            _ok(),  # docker push
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        result = d._build_and_push_aws()
        assert result is not None
        assert "123456789012" in result
        assert "ecr" in result

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_repo_create_success(self, mock_sp):
        """Repo doesn't exist, create succeeds."""
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _ok(stdout="password123"),  # ecr get-login-password
            _ok(),  # docker login
            _fail(),  # describe-repositories (not found)
            _ok(),  # create-repository
            _ok(),  # docker tag
            _ok(),  # docker push
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is not None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_repo_create_fails(self, mock_sp):
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _ok(stdout="password123"),  # ecr get-login-password
            _ok(),  # docker login
            _fail(),  # describe-repositories
            _fail("create err"),  # create-repository fails
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_docker_tag_fails(self, mock_sp):
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _ok(stdout="password123"),  # ecr get-login-password
            _ok(),  # docker login
            _ok(),  # describe-repositories
            _fail(),  # docker tag
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_docker_push_fails(self, mock_sp):
        results = [
            _ok(),  # check_command
            _ok(stdout="123456789012"),  # get-caller-identity
            _ok(),  # docker build
            _ok(stdout="password123"),  # ecr get-login-password
            _ok(),  # docker login
            _ok(),  # describe-repositories
            _ok(),  # docker tag
            _fail("push err"),  # docker push
        ]
        mock_sp.run.side_effect = results
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_timeout(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), subprocess.TimeoutExpired("cmd", 10)]
        d = self._deployer()
        assert d._build_and_push_aws() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_aws_generic_exception(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), RuntimeError("boom")]
        d = self._deployer()
        assert d._build_and_push_aws() is None


# ---------------------------------------------------------------------------
# _build_and_push_azure
# ---------------------------------------------------------------------------


class TestBuildAndPushAzure:
    def _deployer(self):
        return MultiCloudDeployment(
            _make_config(provider=CloudProvider.AZURE, region="eastus")
        )

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_az_cli_missing(self, mock_sp):
        mock_sp.run.return_value = _fail()
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_az_not_logged_in(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),
            _fail(),
        ]  # check_command ok, account show fails
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_build_fails(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok(), _fail("build err")]
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_acr_login_fails(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok(), _ok(), _fail("acr login")]
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_tag_fails(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok(), _ok(), _ok(), _fail()]
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_push_fails(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok(), _ok(), _ok(), _ok(), _fail("push")]
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_full_success(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(),  # az account show
            _ok(),  # docker build
            _ok(),  # az acr login
            _ok(),  # docker tag
            _ok(),  # docker push
        ]
        d = self._deployer()
        result = d._build_and_push_azure()
        assert result is not None
        assert "azurecr.io" in result

    @patch.dict(os.environ, {"AZURE_ACR_NAME": "myacr"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_custom_acr_name(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok(), _ok(), _ok(), _ok(), _ok()]
        d = self._deployer()
        result = d._build_and_push_azure()
        assert result is not None
        assert "myacr.azurecr.io" in result

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_timeout(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), subprocess.TimeoutExpired("cmd", 10)]
        d = self._deployer()
        assert d._build_and_push_azure() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_azure_generic_exception(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), RuntimeError("boom")]
        d = self._deployer()
        assert d._build_and_push_azure() is None


# ---------------------------------------------------------------------------
# _build_and_push_gcp
# ---------------------------------------------------------------------------


class TestBuildAndPushGCP:
    def _deployer(self):
        return MultiCloudDeployment(
            _make_config(provider=CloudProvider.GCP, region="us-central1")
        )

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcloud_missing(self, mock_sp):
        mock_sp.run.return_value = _fail()
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_not_logged_in(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _fail()]  # check ok, auth list fails
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_auth_empty_stdout(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok(stdout="")]  # auth list returns empty
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_no_project(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout=""),  # gcloud config get-value project (empty)
        ]
        d = self._deployer()
        # GCP_PROJECT env not set, project from gcloud is empty
        with patch.dict(os.environ, {}, clear=False):
            # Ensure GCP_PROJECT is not set
            os.environ.pop("GCP_PROJECT", None)
            assert d._build_and_push_gcp() is None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_build_fails(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _fail("build err"),  # docker build
        ]
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_repo_check_fails_create_fails(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _ok(),  # docker build
            _ok(),  # configure-docker
            _fail(),  # artifacts repositories describe
            _fail("create err"),  # artifacts repositories create
        ]
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_docker_tag_fails(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _ok(),  # docker build
            _ok(),  # configure-docker
            _ok(),  # artifacts repositories describe (exists)
            _fail(),  # docker tag
        ]
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_push_fails(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _ok(),  # docker build
            _ok(),  # configure-docker
            _ok(),  # repo describe
            _ok(),  # docker tag
            _fail("push err"),  # docker push
        ]
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_full_success_repo_exists(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _ok(),  # docker build
            _ok(),  # configure-docker
            _ok(),  # repo describe (exists)
            _ok(),  # docker tag
            _ok(),  # docker push
        ]
        d = self._deployer()
        result = d._build_and_push_gcp()
        assert result is not None
        assert "us-central1-docker.pkg.dev" in result
        assert "my-project" in result

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_full_success_repo_created(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _ok(),  # docker build
            _ok(),  # configure-docker
            _fail(),  # repo describe (not found)
            _ok(),  # repo create
            _ok(),  # docker tag
            _ok(),  # docker push
        ]
        d = self._deployer()
        assert d._build_and_push_gcp() is not None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project", "GCP_REPO": "myrepo"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_custom_repo_name(self, mock_sp):
        mock_sp.run.side_effect = [
            _ok(),
            _ok(stdout="u@e.com"),
            _ok(stdout="my-project"),
            _ok(),
            _ok(),
            _ok(),
            _ok(),
            _ok(),
        ]
        d = self._deployer()
        result = d._build_and_push_gcp()
        assert "myrepo" in result

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_timeout(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), subprocess.TimeoutExpired("cmd", 10)]
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_generic_exception(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), RuntimeError("boom")]
        d = self._deployer()
        assert d._build_and_push_gcp() is None

    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_gcp_configure_docker_warning_continues(self, mock_sp):
        """configure-docker failure is a warning, not fatal."""
        mock_sp.run.side_effect = [
            _ok(),  # check_command
            _ok(stdout="user@e.com"),  # auth list
            _ok(stdout="my-project"),  # gcloud config get-value project
            _ok(),  # docker build
            _fail("warn"),  # configure-docker (non-fatal)
            _ok(),  # repo describe
            _ok(),  # docker tag
            _ok(),  # docker push
        ]
        d = self._deployer()
        assert d._build_and_push_gcp() is not None


# ---------------------------------------------------------------------------
# _get_cluster_credentials
# ---------------------------------------------------------------------------


class TestGetClusterCredentials:
    def test_dispatch_aws(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        with patch.object(d, "_get_eks_credentials", return_value=True) as m:
            assert d._get_cluster_credentials() is True
            m.assert_called_once()

    def test_dispatch_azure(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AZURE))
        with patch.object(d, "_get_aks_credentials", return_value=True) as m:
            assert d._get_cluster_credentials() is True
            m.assert_called_once()

    def test_dispatch_gcp(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.GCP))
        with patch.object(d, "_get_gke_credentials", return_value=True) as m:
            assert d._get_cluster_credentials() is True
            m.assert_called_once()

    def test_unsupported_provider(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.LOCAL))
        assert d._get_cluster_credentials() is False

    def test_exception(self):
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        with patch.object(d, "_get_eks_credentials", side_effect=RuntimeError):
            assert d._get_cluster_credentials() is False


# ---------------------------------------------------------------------------
# _get_eks_credentials
# ---------------------------------------------------------------------------


class TestGetEKSCredentials:
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_success(self, mock_sp):
        mock_sp.run.return_value = _ok()
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        assert d._get_eks_credentials() is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_failure(self, mock_sp):
        mock_sp.run.return_value = _fail("no access")
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        assert d._get_eks_credentials() is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_exception(self, mock_sp):
        mock_sp.run.side_effect = RuntimeError("boom")
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AWS))
        assert d._get_eks_credentials() is False


# ---------------------------------------------------------------------------
# _get_aks_credentials
# ---------------------------------------------------------------------------


class TestGetAKSCredentials:
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_success(self, mock_sp):
        mock_sp.run.return_value = _ok()
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AZURE))
        assert d._get_aks_credentials() is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_failure(self, mock_sp):
        mock_sp.run.return_value = _fail("no access")
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AZURE))
        assert d._get_aks_credentials() is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_exception(self, mock_sp):
        mock_sp.run.side_effect = RuntimeError("boom")
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AZURE))
        assert d._get_aks_credentials() is False

    @patch.dict(os.environ, {"AZURE_RG": "custom-rg"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_custom_resource_group(self, mock_sp):
        mock_sp.run.return_value = _ok()
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.AZURE))
        d._get_aks_credentials()
        cmd = mock_sp.run.call_args[0][0]
        assert "custom-rg" in cmd


# ---------------------------------------------------------------------------
# _get_gke_credentials
# ---------------------------------------------------------------------------


class TestGetGKECredentials:
    @patch.dict(os.environ, {"GCP_PROJECT": "my-project"})
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_success(self, mock_sp):
        mock_sp.run.side_effect = [_ok(stdout="my-project"), _ok()]
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.GCP))
        assert d._get_gke_credentials() is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_failure(self, mock_sp):
        mock_sp.run.side_effect = [_ok(stdout="proj"), _fail("no access")]
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.GCP))
        assert d._get_gke_credentials() is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_exception(self, mock_sp):
        mock_sp.run.side_effect = RuntimeError("boom")
        d = MultiCloudDeployment(_make_config(provider=CloudProvider.GCP))
        assert d._get_gke_credentials() is False


# ---------------------------------------------------------------------------
# _health_check
# ---------------------------------------------------------------------------


class TestHealthCheck:
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_kubectl_missing_returns_true(self, mock_sp):
        """If kubectl is not found, health check is skipped (returns True)."""
        mock_sp.run.return_value = _fail()
        d = MultiCloudDeployment(_make_config())
        assert d._health_check() is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_health_check_success(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok()]  # check_command, kubectl wait
        d = MultiCloudDeployment(_make_config())
        assert d._health_check() is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_health_check_fails(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _fail("not ready")]
        d = MultiCloudDeployment(_make_config())
        assert d._health_check() is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_health_check_timeout(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), subprocess.TimeoutExpired("cmd", 10)]
        d = MultiCloudDeployment(_make_config())
        assert d._health_check() is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_health_check_exception(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), RuntimeError("boom")]
        d = MultiCloudDeployment(_make_config())
        assert d._health_check() is False


# ---------------------------------------------------------------------------
# _deploy_to_cluster
# ---------------------------------------------------------------------------


class TestDeployToCluster:
    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_credentials_fail(self, mock_sp):
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=False):
            assert d._deploy_to_cluster("img:v1") is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_helm_not_found(self, mock_sp):
        mock_sp.run.return_value = _fail()  # _check_command("helm") fails
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            assert d._deploy_to_cluster("img:v1") is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_helm_deploy_success(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok()]  # check_command, helm upgrade
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            assert d._deploy_to_cluster("registry/img:v1") is True

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_helm_deploy_fails(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _fail("helm err")]
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            assert d._deploy_to_cluster("img:v1") is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_helm_deploy_timeout(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), subprocess.TimeoutExpired("helm", 600)]
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            assert d._deploy_to_cluster("img:v1") is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_helm_deploy_exception(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), RuntimeError("boom")]
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            assert d._deploy_to_cluster("img:v1") is False

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_values_file_added(self, mock_sp):
        mock_sp.run.side_effect = [_ok(), _ok()]
        cfg = _make_config(values_file="custom-values.yaml")
        d = MultiCloudDeployment(cfg)
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            d._deploy_to_cluster("img:v1")
        # Check helm command includes values file
        helm_call = mock_sp.run.call_args_list[1]
        cmd = helm_call[0][0]
        assert "-f" in cmd
        assert "custom-values.yaml" in cmd

    @patch("src.deployment.multi_cloud_deployment.SafeSubprocess")
    def test_image_url_without_colon(self, mock_sp):
        """Image URL with no tag defaults to 'latest'."""
        mock_sp.run.side_effect = [_ok(), _ok()]
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_get_cluster_credentials", return_value=True):
            d._deploy_to_cluster("registry/img")
        cmd = mock_sp.run.call_args_list[1][0][0]
        assert "image.tag=latest" in " ".join(cmd)


# ---------------------------------------------------------------------------
# deploy (top-level orchestration)
# ---------------------------------------------------------------------------


class TestDeploy:
    def test_deploy_image_build_fails(self):
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_build_and_push_image", return_value=None):
            result = d.deploy()
            assert result.success is False
            assert result.error == "Failed to build and push image"

    def test_deploy_cluster_fails(self):
        d = MultiCloudDeployment(_make_config())
        with (
            patch.object(d, "_build_and_push_image", return_value="img:v1"),
            patch.object(d, "_deploy_to_cluster", return_value=False),
            patch.object(d, "_health_check", return_value=True),
        ):
            result = d.deploy()
            assert result.success is False
            assert result.image_url == "img:v1"

    def test_deploy_success_health_ok(self):
        d = MultiCloudDeployment(_make_config())
        with (
            patch.object(d, "_build_and_push_image", return_value="img:v1"),
            patch.object(d, "_deploy_to_cluster", return_value=True),
            patch.object(d, "_health_check", return_value=True),
        ):
            result = d.deploy()
            assert result.success is True
            assert result.image_url == "img:v1"
            assert result.deployment_time > 0

    def test_deploy_success_health_fails(self):
        """Deployment succeeds even if health check fails (just a warning)."""
        d = MultiCloudDeployment(_make_config())
        with (
            patch.object(d, "_build_and_push_image", return_value="img:v1"),
            patch.object(d, "_deploy_to_cluster", return_value=True),
            patch.object(d, "_health_check", return_value=False),
        ):
            result = d.deploy()
            assert result.success is True

    def test_deploy_health_not_called_when_deploy_fails(self):
        d = MultiCloudDeployment(_make_config())
        with (
            patch.object(d, "_build_and_push_image", return_value="img:v1"),
            patch.object(d, "_deploy_to_cluster", return_value=False),
            patch.object(d, "_health_check") as mock_hc,
        ):
            d.deploy()
            mock_hc.assert_not_called()

    def test_deploy_exception(self):
        d = MultiCloudDeployment(_make_config())
        with patch.object(d, "_build_and_push_image", side_effect=RuntimeError("boom")):
            result = d.deploy()
            assert result.success is False
            assert "boom" in result.error
            assert result.deployment_time >= 0

    def test_deploy_result_fields(self):
        cfg = _make_config(
            provider=CloudProvider.GCP, region="eu-west1", cluster="prod"
        )
        d = MultiCloudDeployment(cfg)
        with (
            patch.object(d, "_build_and_push_image", return_value="img:v1"),
            patch.object(d, "_deploy_to_cluster", return_value=True),
            patch.object(d, "_health_check", return_value=True),
        ):
            result = d.deploy()
            assert result.provider == CloudProvider.GCP
            assert result.region == "eu-west1"
            assert result.cluster_name == "prod"


# ---------------------------------------------------------------------------
# deploy_multi_cloud convenience function
# ---------------------------------------------------------------------------


class TestDeployMultiCloud:
    @patch("src.deployment.multi_cloud_deployment.MultiCloudDeployment")
    def test_valid_aws(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.deploy.return_value = DeploymentResult(
            success=True,
            provider=CloudProvider.AWS,
            region="us-east-1",
            cluster_name="c",
        )
        mock_cls.return_value = mock_instance

        result = deploy_multi_cloud("aws", "us-east-1", "c")
        assert result.success is True
        mock_cls.assert_called_once()
        cfg = mock_cls.call_args[0][0]
        assert cfg.provider == CloudProvider.AWS

    @patch("src.deployment.multi_cloud_deployment.MultiCloudDeployment")
    def test_valid_azure(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.deploy.return_value = DeploymentResult(
            success=True,
            provider=CloudProvider.AZURE,
            region="eastus",
            cluster_name="c",
        )
        mock_cls.return_value = mock_instance
        result = deploy_multi_cloud("azure", "eastus", "c")
        assert result.success is True

    @patch("src.deployment.multi_cloud_deployment.MultiCloudDeployment")
    def test_valid_gcp(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.deploy.return_value = DeploymentResult(
            success=True,
            provider=CloudProvider.GCP,
            region="us-central1",
            cluster_name="c",
        )
        mock_cls.return_value = mock_instance
        result = deploy_multi_cloud("gcp", "us-central1", "c")
        assert result.success is True

    def test_invalid_provider(self):
        result = deploy_multi_cloud("invalid_cloud", "us-east-1", "c")
        assert result.success is False
        assert "Invalid provider" in result.error
        assert result.provider == CloudProvider.LOCAL

    @patch("src.deployment.multi_cloud_deployment.MultiCloudDeployment")
    def test_case_insensitive_provider(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.deploy.return_value = DeploymentResult(
            success=True,
            provider=CloudProvider.AWS,
            region="us-east-1",
            cluster_name="c",
        )
        mock_cls.return_value = mock_instance
        result = deploy_multi_cloud("AWS", "us-east-1", "c")
        assert result.success is True

    @patch("src.deployment.multi_cloud_deployment.MultiCloudDeployment")
    def test_all_params_forwarded(self, mock_cls):
        mock_instance = MagicMock()
        mock_instance.deploy.return_value = DeploymentResult(
            success=True, provider=CloudProvider.AWS, region="r", cluster_name="c"
        )
        mock_cls.return_value = mock_instance

        deploy_multi_cloud(
            provider="aws",
            region="us-west-2",
            cluster_name="my-cluster",
            image_tag="v2.0",
            namespace="prod",
            helm_release_name="myapp",
            helm_chart_path="./charts/myapp",
            values_file="prod.yaml",
        )

        cfg = mock_cls.call_args[0][0]
        assert cfg.region == "us-west-2"
        assert cfg.cluster_name == "my-cluster"
        assert cfg.image_tag == "v2.0"
        assert cfg.namespace == "prod"
        assert cfg.helm_release_name == "myapp"
        assert cfg.helm_chart_path == "./charts/myapp"
        assert cfg.values_file == "prod.yaml"
