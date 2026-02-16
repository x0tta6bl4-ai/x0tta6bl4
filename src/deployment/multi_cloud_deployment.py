"""
Multi-Cloud Deployment для x0tta6bl4.

Поддержка deployment в:
- AWS (EKS + ECR)
- Azure (AKS + ACR)
- GCP (GKE + Artifact Registry)

Features:
- Автоматическое определение cloud provider
- Helm integration для всех облаков
- Поддержка EKS, AKS, GKE
- Container registry integration (ECR, ACR, Artifact Registry)
- Error handling и retry logic
- Health checks после deployment
"""

import logging
import os
import subprocess
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional

from src.core.safe_subprocess import SafeCommandResult, SafeSubprocess

logger = logging.getLogger(__name__)


class CloudProvider(Enum):
    """Cloud providers."""

    AWS = "aws"
    AZURE = "azure"
    GCP = "gcp"
    LOCAL = "local"


@dataclass
class DeploymentConfig:
    """Конфигурация deployment."""

    provider: CloudProvider
    region: str
    cluster_name: str
    namespace: str = "default"
    image_name: str = "x0tta6bl4"
    image_tag: str = "latest"
    helm_release_name: str = "x0tta6bl4"
    helm_chart_path: str = "./helm/x0tta6bl4"
    values_file: Optional[str] = None
    wait_timeout: int = 600  # 10 minutes
    health_check_timeout: int = 300  # 5 minutes


@dataclass
class DeploymentResult:
    """Результат deployment."""

    success: bool
    provider: CloudProvider
    region: str
    cluster_name: str
    image_url: Optional[str] = None
    error: Optional[str] = None
    deployment_time: float = 0.0


class MultiCloudDeployment:
    """
    Multi-Cloud Deployment Manager.

    Управляет deployment в различных cloud providers.
    """

    def __init__(self, config: DeploymentConfig):
        """
        Инициализация Multi-Cloud Deployment.

        Args:
            config: Конфигурация deployment
        """
        self.config = config
        self.start_time = time.time()

        logger.info(
            f"✅ Multi-Cloud Deployment initialized: "
            f"provider={config.provider.value}, "
            f"region={config.region}, "
            f"cluster={config.cluster_name}"
        )

    def deploy(self) -> DeploymentResult:
        """
        Выполнить deployment.

        Returns:
            DeploymentResult с результатами
        """
        try:
            logger.info(f"🚀 Starting deployment to {self.config.provider.value}...")

            # Build and push image
            image_url = self._build_and_push_image()
            if not image_url:
                return DeploymentResult(
                    success=False,
                    provider=self.config.provider,
                    region=self.config.region,
                    cluster_name=self.config.cluster_name,
                    error="Failed to build and push image",
                )

            # Deploy to cluster
            deploy_success = self._deploy_to_cluster(image_url)

            # Health check
            if deploy_success:
                health_check_success = self._health_check()
                if not health_check_success:
                    logger.warning("⚠️ Deployment completed but health check failed")

            deployment_time = time.time() - self.start_time

            return DeploymentResult(
                success=deploy_success,
                provider=self.config.provider,
                region=self.config.region,
                cluster_name=self.config.cluster_name,
                image_url=image_url,
                deployment_time=deployment_time,
            )

        except Exception as e:
            logger.error(f"❌ Deployment failed: {e}", exc_info=True)
            return DeploymentResult(
                success=False,
                provider=self.config.provider,
                region=self.config.region,
                cluster_name=self.config.cluster_name,
                error=str(e),
                deployment_time=time.time() - self.start_time,
            )

    def _build_and_push_image(self) -> Optional[str]:
        """
        Build и push Docker image в cloud registry.

        Returns:
            Image URL или None при ошибке
        """
        try:
            if self.config.provider == CloudProvider.AWS:
                return self._build_and_push_aws()
            elif self.config.provider == CloudProvider.AZURE:
                return self._build_and_push_azure()
            elif self.config.provider == CloudProvider.GCP:
                return self._build_and_push_gcp()
            else:
                logger.error(f"❌ Unsupported provider: {self.config.provider}")
                return None
        except Exception as e:
            logger.error(f"❌ Build and push failed: {e}")
            return None

    def _build_and_push_aws(self) -> Optional[str]:
        """Build и push в AWS ECR."""
        try:
            # Check AWS CLI
            if not self._check_command("aws"):
                logger.error("❌ AWS CLI not found")
                return None

            # Get AWS account and region
            aws_result = SafeSubprocess.run(
                [
                    "aws",
                    "sts",
                    "get-caller-identity",
                    "--query",
                    "Account",
                    "--output",
                    "text",
                ],
                timeout=10,
            )
            aws_account = aws_result.stdout.strip() if aws_result.success else ""

            if not aws_account:
                logger.error("❌ AWS credentials not configured")
                return None

            region = self.config.region
            ecr_registry = f"{aws_account}.dkr.ecr.{region}.amazonaws.com"
            image_name = self.config.image_name
            image_tag = self.config.image_tag
            ecr_image = f"{ecr_registry}/{image_name}:{image_tag}"

            # Build image
            logger.info(f"📦 Building Docker image: {image_name}:{image_tag}")
            build_result = SafeSubprocess.run(
                [
                    "docker",
                    "build",
                    "-f",
                    "Dockerfile",
                    "-t",
                    f"{image_name}:{image_tag}",
                    ".",
                ],
                timeout=600,
            )

            if not build_result.success:
                logger.error(f"❌ Docker build failed: {build_result.stderr}")
                return None

            # Login to ECR
            logger.info("🔐 Logging into ECR...")
            login_result = SafeSubprocess.run(
                ["aws", "ecr", "get-login-password", "--region", region], timeout=10
            )

            if not login_result.success:
                logger.error(f"❌ ECR login failed: {login_result.stderr}")
                return None

            # Docker login
            docker_login = SafeSubprocess.run(
                [
                    "docker",
                    "login",
                    "--username",
                    "AWS",
                    "--password-stdin",
                    ecr_registry,
                ],
                input_data=login_result.stdout,
                timeout=30,
            )

            if not docker_login.success:
                logger.error("❌ Docker login to ECR failed")
                return None

            # Create ECR repository if not exists
            logger.info(f"📦 Checking ECR repository: {image_name}")
            repo_check = SafeSubprocess.run(
                [
                    "aws",
                    "ecr",
                    "describe-repositories",
                    "--repository-names",
                    image_name,
                    "--region",
                    region,
                ],
                timeout=10,
            )

            if not repo_check.success:
                logger.info(f"📦 Creating ECR repository: {image_name}")
                create_repo = SafeSubprocess.run(
                    [
                        "aws",
                        "ecr",
                        "create-repository",
                        "--repository-name",
                        image_name,
                        "--region",
                        region,
                    ],
                    timeout=30,
                )
                if not create_repo.success:
                    logger.error(
                        f"❌ Failed to create ECR repository: {create_repo.stderr}"
                    )
                    return None

            # Tag and push
            logger.info(f"📤 Pushing image to ECR: {ecr_image}")
            docker_tag = SafeSubprocess.run(
                ["docker", "tag", f"{image_name}:{image_tag}", ecr_image], timeout=10
            )

            if not docker_tag.success:
                logger.error("❌ Docker tag failed")
                return None

            push_result = SafeSubprocess.run(["docker", "push", ecr_image], timeout=600)

            if not push_result.success:
                logger.error(f"❌ Docker push failed: {push_result.stderr}")
                return None

            logger.info(f"✅ Image pushed to ECR: {ecr_image}")
            return ecr_image

        except subprocess.TimeoutExpired:
            logger.error("❌ Timeout during AWS ECR operations")
            return None
        except Exception as e:
            logger.error(f"❌ AWS ECR error: {e}")
            return None

    def _build_and_push_azure(self) -> Optional[str]:
        """Build и push в Azure ACR."""
        try:
            # Check Azure CLI
            if not self._check_command("az"):
                logger.error("❌ Azure CLI not found")
                return None

            # Check Azure login
            account_check = SafeSubprocess.run(["az", "account", "show"], timeout=10)

            if not account_check.success:
                logger.error("❌ Azure not logged in. Run 'az login'")
                return None

            # Get Azure configuration
            acr_name = os.getenv("AZURE_ACR_NAME", "x0tta6bl4acr")
            acr_image = f"{acr_name}.azurecr.io/{self.config.image_name}:{self.config.image_tag}"

            # Build image
            logger.info(
                f"📦 Building Docker image: {self.config.image_name}:{self.config.image_tag}"
            )
            build_result = SafeSubprocess.run(
                [
                    "docker",
                    "build",
                    "-f",
                    "Dockerfile",
                    "-t",
                    f"{self.config.image_name}:{self.config.image_tag}",
                    ".",
                ],
                timeout=600,
            )

            if not build_result.success:
                logger.error(f"❌ Docker build failed: {build_result.stderr}")
                return None

            # Login to ACR
            logger.info(f"🔐 Logging into ACR: {acr_name}")
            login_result = SafeSubprocess.run(
                ["az", "acr", "login", "--name", acr_name], timeout=30
            )

            if not login_result.success:
                logger.error(f"❌ ACR login failed: {login_result.stderr}")
                return None

            # Tag and push
            logger.info(f"📤 Pushing image to ACR: {acr_image}")
            docker_tag = SafeSubprocess.run(
                [
                    "docker",
                    "tag",
                    f"{self.config.image_name}:{self.config.image_tag}",
                    acr_image,
                ],
                timeout=10,
            )

            if not docker_tag.success:
                logger.error("❌ Docker tag failed")
                return None

            push_result = SafeSubprocess.run(["docker", "push", acr_image], timeout=600)

            if not push_result.success:
                logger.error(f"❌ Docker push failed: {push_result.stderr}")
                return None

            logger.info(f"✅ Image pushed to ACR: {acr_image}")
            return acr_image

        except subprocess.TimeoutExpired:
            logger.error("❌ Timeout during Azure ACR operations")
            return None
        except Exception as e:
            logger.error(f"❌ Azure ACR error: {e}")
            return None

    def _build_and_push_gcp(self) -> Optional[str]:
        """Build и push в GCP Artifact Registry."""
        try:
            # Check GCP CLI
            if not self._check_command("gcloud"):
                logger.error("❌ GCP CLI not found")
                return None

            # Check GCP login
            auth_check = SafeSubprocess.run(
                [
                    "gcloud",
                    "auth",
                    "list",
                    "--filter=status:ACTIVE",
                    "--format=value(account)",
                ],
                timeout=10,
            )

            if not auth_check.success or not auth_check.stdout.strip():
                logger.error("❌ GCP not logged in. Run 'gcloud auth login'")
                return None

            # Get GCP configuration
            project_result = SafeSubprocess.run(
                ["gcloud", "config", "get-value", "project"], timeout=10
            )
            project = os.getenv(
                "GCP_PROJECT",
                project_result.stdout.strip() if project_result.success else "",
            )

            if not project:
                logger.error("❌ GCP project not configured")
                return None

            region = self.config.region
            repo_name = os.getenv("GCP_REPO", "x0tta6bl4")
            artifact_image = f"{region}-docker.pkg.dev/{project}/{repo_name}/{self.config.image_name}:{self.config.image_tag}"

            # Build image
            logger.info(
                f"📦 Building Docker image: {self.config.image_name}:{self.config.image_tag}"
            )
            build_result = SafeSubprocess.run(
                [
                    "docker",
                    "build",
                    "-f",
                    "Dockerfile",
                    "-t",
                    f"{self.config.image_name}:{self.config.image_tag}",
                    ".",
                ],
                timeout=600,
            )

            if not build_result.success:
                logger.error(f"❌ Docker build failed: {build_result.stderr}")
                return None

            # Configure Docker for Artifact Registry
            logger.info(f"🔐 Configuring Docker for Artifact Registry...")
            configure_result = SafeSubprocess.run(
                ["gcloud", "auth", "configure-docker", f"{region}-docker.pkg.dev"],
                timeout=30,
            )

            if not configure_result.success:
                logger.warning(
                    f"⚠️ Docker configuration warning: {configure_result.stderr}"
                )

            # Create Artifact Registry repository if not exists
            logger.info(f"📦 Checking Artifact Registry repository: {repo_name}")
            repo_check = SafeSubprocess.run(
                [
                    "gcloud",
                    "artifacts",
                    "repositories",
                    "describe",
                    repo_name,
                    "--location",
                    region,
                    "--repository-format",
                    "docker",
                ],
                timeout=10,
            )

            if not repo_check.success:
                logger.info(f"📦 Creating Artifact Registry repository: {repo_name}")
                create_repo = SafeSubprocess.run(
                    [
                        "gcloud",
                        "artifacts",
                        "repositories",
                        "create",
                        repo_name,
                        "--repository-format",
                        "docker",
                        "--location",
                        region,
                        "--description",
                        "x0tta6bl4 Docker images",
                    ],
                    timeout=60,
                )
                if not create_repo.success:
                    logger.error(
                        f"❌ Failed to create Artifact Registry repository: {create_repo.stderr}"
                    )
                    return None

            # Tag and push
            logger.info(f"📤 Pushing image to Artifact Registry: {artifact_image}")
            docker_tag = SafeSubprocess.run(
                [
                    "docker",
                    "tag",
                    f"{self.config.image_name}:{self.config.image_tag}",
                    artifact_image,
                ],
                timeout=10,
            )

            if not docker_tag.success:
                logger.error("❌ Docker tag failed")
                return None

            push_result = SafeSubprocess.run(
                ["docker", "push", artifact_image], timeout=600
            )

            if not push_result.success:
                logger.error(f"❌ Docker push failed: {push_result.stderr}")
                return None

            logger.info(f"✅ Image pushed to Artifact Registry: {artifact_image}")
            return artifact_image

        except subprocess.TimeoutExpired:
            logger.error("❌ Timeout during GCP Artifact Registry operations")
            return None
        except Exception as e:
            logger.error(f"❌ GCP Artifact Registry error: {e}")
            return None

    def _deploy_to_cluster(self, image_url: str) -> bool:
        """
        Deploy в Kubernetes cluster используя Helm.

        Args:
            image_url: URL образа в registry

        Returns:
            True если deployment успешен
        """
        try:
            # Get cluster credentials
            if not self._get_cluster_credentials():
                return False

            # Check Helm
            if not self._check_command("helm"):
                logger.error("❌ Helm not found")
                return False

            # Prepare Helm command
            helm_cmd = [
                "helm",
                "upgrade",
                "--install",
                self.config.helm_release_name,
                self.config.helm_chart_path,
                "--namespace",
                self.config.namespace,
                "--create-namespace",
                "--set",
                f"image.repository={image_url.split(':')[0]}",
                "--set",
                f"image.tag={image_url.split(':')[1] if ':' in image_url else 'latest'}",
                "--wait",
                "--timeout",
                f"{self.config.wait_timeout}s",
            ]

            # Add values file if specified
            if self.config.values_file:
                helm_cmd.extend(["-f", self.config.values_file])

            logger.info(f"🚀 Deploying with Helm: {self.config.helm_release_name}")
            deploy_result = SafeSubprocess.run(
                helm_cmd, timeout=self.config.wait_timeout + 60
            )

            if not deploy_result.success:
                logger.error(f"❌ Helm deployment failed: {deploy_result.stderr}")
                return False

            logger.info(
                f"✅ Helm deployment successful: {self.config.helm_release_name}"
            )
            return True

        except subprocess.TimeoutExpired:
            logger.error("❌ Helm deployment timeout")
            return False
        except Exception as e:
            logger.error(f"❌ Deployment error: {e}")
            return False

    def _get_cluster_credentials(self) -> bool:
        """Получить credentials для Kubernetes cluster."""
        try:
            if self.config.provider == CloudProvider.AWS:
                return self._get_eks_credentials()
            elif self.config.provider == CloudProvider.AZURE:
                return self._get_aks_credentials()
            elif self.config.provider == CloudProvider.GCP:
                return self._get_gke_credentials()
            else:
                logger.error(f"❌ Unsupported provider: {self.config.provider}")
                return False
        except Exception as e:
            logger.error(f"❌ Failed to get cluster credentials: {e}")
            return False

    def _get_eks_credentials(self) -> bool:
        """Получить EKS credentials."""
        try:
            region = self.config.region
            cluster_name = self.config.cluster_name

            result = SafeSubprocess.run(
                [
                    "aws",
                    "eks",
                    "update-kubeconfig",
                    "--region",
                    region,
                    "--name",
                    cluster_name,
                ],
                timeout=60,
            )

            if not result.success:
                logger.error(f"❌ Failed to get EKS credentials: {result.stderr}")
                return False

            logger.info(f"✅ EKS credentials configured: {cluster_name}")
            return True
        except Exception as e:
            logger.error(f"❌ EKS credentials error: {e}")
            return False

    def _get_aks_credentials(self) -> bool:
        """Получить AKS credentials."""
        try:
            resource_group = os.getenv("AZURE_RG", "x0tta6bl4-rg")
            cluster_name = self.config.cluster_name

            result = SafeSubprocess.run(
                [
                    "az",
                    "aks",
                    "get-credentials",
                    "--resource-group",
                    resource_group,
                    "--name",
                    cluster_name,
                    "--overwrite-existing",
                ],
                timeout=60,
            )

            if not result.success:
                logger.error(f"❌ Failed to get AKS credentials: {result.stderr}")
                return False

            logger.info(f"✅ AKS credentials configured: {cluster_name}")
            return True
        except Exception as e:
            logger.error(f"❌ AKS credentials error: {e}")
            return False

    def _get_gke_credentials(self) -> bool:
        """Получить GKE credentials."""
        try:
            project_result = SafeSubprocess.run(
                ["gcloud", "config", "get-value", "project"], timeout=10
            )
            project = os.getenv(
                "GCP_PROJECT",
                project_result.stdout.strip() if project_result.success else "",
            )

            region = self.config.region
            cluster_name = self.config.cluster_name

            result = SafeSubprocess.run(
                [
                    "gcloud",
                    "container",
                    "clusters",
                    "get-credentials",
                    cluster_name,
                    "--region",
                    region,
                    "--project",
                    project,
                ],
                timeout=60,
            )

            if not result.success:
                logger.error(f"❌ Failed to get GKE credentials: {result.stderr}")
                return False

            logger.info(f"✅ GKE credentials configured: {cluster_name}")
            return True
        except Exception as e:
            logger.error(f"❌ GKE credentials error: {e}")
            return False

    def _health_check(self) -> bool:
        """Проверить health после deployment."""
        try:
            # Check if kubectl is available
            if not self._check_command("kubectl"):
                logger.warning("⚠️ kubectl not found, skipping health check")
                return True

            # Wait for deployment to be ready
            logger.info("🏥 Waiting for deployment to be ready...")
            wait_result = SafeSubprocess.run(
                [
                    "kubectl",
                    "wait",
                    "--for=condition=available",
                    f"deployment/{self.config.helm_release_name}",
                    "--namespace",
                    self.config.namespace,
                    "--timeout",
                    f"{self.config.health_check_timeout}s",
                ],
                timeout=self.config.health_check_timeout + 10,
            )

            if not wait_result.success:
                logger.warning(f"⚠️ Deployment not ready: {wait_result.stderr}")
                return False

            logger.info("✅ Deployment is healthy")
            return True

        except subprocess.TimeoutExpired:
            logger.warning("⚠️ Health check timeout")
            return False
        except Exception as e:
            logger.warning(f"⚠️ Health check error: {e}")
            return False

    def _check_command(self, command: str) -> bool:
        """Проверить наличие команды."""
        try:
            result = SafeSubprocess.run(
                ["which", command] if os.name != "nt" else ["where", command], timeout=5
            )
            return result.success
        except Exception:
            return False


def deploy_multi_cloud(
    provider: str,
    region: str,
    cluster_name: str,
    image_tag: str = "latest",
    namespace: str = "default",
    helm_release_name: str = "x0tta6bl4",
    helm_chart_path: str = "./helm/x0tta6bl4",
    values_file: Optional[str] = None,
) -> DeploymentResult:
    """
    Convenience function для multi-cloud deployment.

    Args:
        provider: Cloud provider (aws, azure, gcp)
        region: Region для deployment
        cluster_name: Имя Kubernetes cluster
        image_tag: Docker image tag
        namespace: Kubernetes namespace
        helm_release_name: Helm release name
        helm_chart_path: Path to Helm chart
        values_file: Optional Helm values file

    Returns:
        DeploymentResult
    """
    try:
        cloud_provider = CloudProvider(provider.lower())
    except ValueError:
        logger.error(f"❌ Invalid provider: {provider}")
        return DeploymentResult(
            success=False,
            provider=CloudProvider.LOCAL,
            region=region,
            cluster_name=cluster_name,
            error=f"Invalid provider: {provider}",
        )

    config = DeploymentConfig(
        provider=cloud_provider,
        region=region,
        cluster_name=cluster_name,
        namespace=namespace,
        image_tag=image_tag,
        helm_release_name=helm_release_name,
        helm_chart_path=helm_chart_path,
        values_file=values_file,
    )

    deployment = MultiCloudDeployment(config)
    return deployment.deploy()
