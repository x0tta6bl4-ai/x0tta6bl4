"""
Canary Deployment для x0tta6bl4.

Постепенный rollout новой версии:
- Canary: 1% трафика
- Gradual: 10% → 50% → 100%
- Автоматический rollback при проблемах

Features:
- Helm integration для Kubernetes deployments
- Integration с основными deployment скриптами
- Автоматический мониторинг и продвижение стадий
- Prometheus metrics integration
- CI/CD integration (GitLab, GitHub Actions, Jenkins, etc.)
"""
import logging
import time
import os
import subprocess
import asyncio
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class DeploymentStage(Enum):
    """Стадии deployment."""
    CANARY = "canary"  # 1% трафика
    GRADUAL_10 = "gradual_10"  # 10% трафика
    GRADUAL_50 = "gradual_50"  # 50% трафика
    FULL = "full"  # 100% трафика
    ROLLBACK = "rollback"  # Откат к предыдущей версии


@dataclass
class DeploymentConfig:
    """Конфигурация deployment."""
    canary_percentage: float = 1.0  # 1% трафика
    gradual_stages: List[float] = None  # [10.0, 50.0, 100.0]
    stage_duration: float = 3600.0  # 1 час на стадию
    health_check_interval: float = 60.0  # 1 минута
    rollback_threshold: float = 0.95  # 95% success rate для продолжения
    max_errors_per_minute: int = 10  # Максимум ошибок в минуту


@dataclass
class DeploymentMetrics:
    """Метрики deployment."""
    stage: DeploymentStage
    traffic_percentage: float
    requests_total: int = 0
    requests_success: int = 0
    requests_error: int = 0
    errors_per_minute: float = 0.0
    success_rate: float = 1.0
    start_time: float = 0.0
    duration: float = 0.0


class CanaryDeployment:
    """
    Canary Deployment Manager.
    
    Управляет постепенным rollout новой версии с автоматическим rollback.
    """
    
    def __init__(
        self,
        config: Optional[DeploymentConfig] = None,
        health_check_fn: Optional[Callable[[], bool]] = None,
        metrics_collector: Optional[Callable[[], Dict[str, Any]]] = None
    ):
        """
        Инициализация Canary Deployment.
        
        Args:
            config: Конфигурация deployment
            health_check_fn: Функция для health check
            metrics_collector: Функция для сбора метрик
        """
        self.config = config or DeploymentConfig()
        if self.config.gradual_stages is None:
            self.config.gradual_stages = [10.0, 50.0, 100.0]
        
        self.health_check_fn = health_check_fn
        self.metrics_collector = metrics_collector
        
        # Current stage
        self.current_stage = DeploymentStage.CANARY
        self.current_traffic_percentage = self.config.canary_percentage
        
        # Metrics
        self.metrics = DeploymentMetrics(
            stage=self.current_stage,
            traffic_percentage=self.current_traffic_percentage,
            start_time=time.time()
        )
        
        # Stage history
        self.stage_history: List[DeploymentMetrics] = []
        
        # Running state
        self._running = False
        self._rollback_triggered = False
        
        # Deployment integration
        self.helm_release_name = os.getenv("HELM_RELEASE_NAME", "x0tta6bl4")
        self.helm_namespace = os.getenv("HELM_NAMESPACE", "default")
        self.helm_chart_path = os.getenv("HELM_CHART_PATH", "./helm/x0tta6bl4")
        
        # Monitoring integration
        self.prometheus_url = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
        self.monitoring_task: Optional[asyncio.Task] = None
        
        logger.info(
            f"✅ Canary Deployment initialized: "
            f"canary={self.config.canary_percentage}%, "
            f"stages={self.config.gradual_stages}%, "
            f"helm_release={self.helm_release_name}"
        )
    
    def start(self, new_version: Optional[str] = None):
        """
        Start canary deployment.
        
        Args:
            new_version: Version tag for new deployment (e.g., "3.4.1")
        """
        self._running = True
        self.current_stage = DeploymentStage.CANARY
        self.current_traffic_percentage = self.config.canary_percentage
        self.metrics.start_time = time.time()
        
        logger.info(f"🚀 Canary deployment started: {self.current_traffic_percentage}% traffic")
        
        # Deploy canary version if specified
        if new_version:
            self._deploy_canary_version(new_version)
        
        # Start monitoring task
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                self.monitoring_task = asyncio.create_task(self._monitor_deployment())
            else:
                loop.run_until_complete(self._monitor_deployment())
        except RuntimeError:
            # No event loop, will be started manually
            pass
    
    def stop(self):
        """Stop deployment."""
        self._running = False
        
        # Stop monitoring task
        if self.monitoring_task and not self.monitoring_task.done():
            self.monitoring_task.cancel()
        
        logger.info("🛑 Canary deployment stopped")
    
    def should_route_to_new_version(self) -> bool:
        """
        Определить, следует ли направлять трафик на новую версию.
        
        Returns:
            True если трафик должен идти на новую версию
        """
        if not self._running:
            return False
        
        if self._rollback_triggered:
            return False
        
        # Simple percentage-based routing
        import random
        return random.random() * 100 < self.current_traffic_percentage
    
    def record_request(self, success: bool):
        """Записать результат запроса."""
        self.metrics.requests_total += 1
        
        if success:
            self.metrics.requests_success += 1
        else:
            self.metrics.requests_error += 1
        
        # Update success rate
        if self.metrics.requests_total > 0:
            self.metrics.success_rate = (
                self.metrics.requests_success / self.metrics.requests_total
            )
        
        # Check if rollback needed
        self._check_rollback_conditions()
    
    def _check_rollback_conditions(self):
        """Проверить условия для rollback."""
        # Check success rate
        if self.metrics.success_rate < self.config.rollback_threshold:
            logger.error(
                f"🔴 Success rate below threshold: "
                f"{self.metrics.success_rate:.2%} < {self.config.rollback_threshold:.2%}"
            )
            self._trigger_rollback("low_success_rate")
            return
        
        # Check errors per minute
        if self.metrics.errors_per_minute > self.config.max_errors_per_minute:
            logger.error(
                f"🔴 Errors per minute too high: "
                f"{self.metrics.errors_per_minute:.1f} > {self.config.max_errors_per_minute}"
            )
            self._trigger_rollback("high_error_rate")
            return
        
        # Check health
        if self.health_check_fn and not self.health_check_fn():
            logger.error("🔴 Health check failed")
            self._trigger_rollback("health_check_failed")
            return
    
    def _trigger_rollback(self, reason: str):
        """Триггер rollback."""
        if self._rollback_triggered:
            return
        
        self._rollback_triggered = True
        self.current_stage = DeploymentStage.ROLLBACK
        self.current_traffic_percentage = 0.0
        
        logger.critical(f"🔴 ROLLBACK TRIGGERED: {reason}")
        
        # Integrated rollback with deployment system
        rollback_success = False
        
        try:
            # Try Helm rollback first (if using Helm)
            if self._is_helm_deployment():
                rollback_success = self._helm_rollback()
            
            # Try Kubernetes rollback (if in K8s environment)
            if not rollback_success:
                if os.path.exists('/var/run/secrets/kubernetes.io/serviceaccount'):
                    deployment_name = os.getenv('K8S_DEPLOYMENT_NAME', self.helm_release_name)
                    namespace = os.getenv('K8S_NAMESPACE', self.helm_namespace)
                
                result = subprocess.run(
                    ['kubectl', 'rollout', 'undo', f'deployment/{deployment_name}', '-n', namespace],
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                if result.returncode == 0:
                    logger.info(f"✅ Kubernetes rollback initiated for {deployment_name}")
                    rollback_success = True
                    
                    # Wait for rollout to complete
                    result = subprocess.run(
                        ['kubectl', 'rollout', 'status', f'deployment/{deployment_name}', '-n', namespace, '--timeout=60s'],
                        capture_output=True,
                        text=True,
                        timeout=65
                    )
                    if result.returncode == 0:
                        logger.info("✅ Kubernetes rollback completed successfully")
                    else:
                        logger.warning("⚠️ Kubernetes rollback status check failed")
                else:
                    logger.warning(f"Kubernetes rollback failed: {result.stderr}")
            
            # Try Docker Compose rollback if K8s failed or not available
            if not rollback_success:
                rollback_success = self._docker_compose_rollback()
            
            # Try CI/CD integration (GitLab/GitHub Actions/Jenkins/CircleCI)
            if not rollback_success:
                rollback_success = self._trigger_cicd_rollback()
            
        except FileNotFoundError:
            # kubectl not available, try Docker Compose
            rollback_success = self._docker_compose_rollback()
        except Exception as e:
            logger.error(f"❌ Rollback failed: {e}")
        
        # Final fallback: scale down canary
        if not rollback_success:
            logger.warning("All rollback methods failed, scaling down canary as fallback")
            self._scale_down_canary()
    
    def _docker_compose_rollback(self):
        """Rollback using Docker Compose."""
        try:
            import subprocess
            result = subprocess.run(
                ['docker', 'compose', '-f', 'staging/docker-compose.staging.yml', 'rollback'],
                capture_output=True,
                text=True,
                timeout=60
            )
            if result.returncode == 0:
                logger.info("✅ Docker Compose rollback completed")
            else:
                logger.warning(f"Docker Compose rollback failed: {result.stderr}")
        except Exception as e:
            logger.error(f"❌ Docker Compose rollback error: {e}")
    
    def _scale_down_canary(self):
        """Scale down canary deployment as fallback."""
        try:
            import subprocess
            # Scale canary to 0 replicas
            subprocess.run(
                ['kubectl', 'scale', 'deployment/x0tta6bl4-canary', '--replicas=0'],
                capture_output=True,
                timeout=30
            )
            logger.info("✅ Canary scaled down")
        except Exception as e:
            logger.error(f"❌ Scale down failed: {e}")
    
    def advance_stage(self) -> bool:
        """
        Перейти к следующей стадии deployment.
        
        Returns:
            True если стадия изменена, False если уже на последней стадии
        """
        if self._rollback_triggered:
            return False
        
        # Save current metrics
        self.metrics.duration = time.time() - self.metrics.start_time
        self.stage_history.append(self.metrics)
        
        # Create new metrics for next stage
        old_stage = self.current_stage
        
        # Advance to next stage
        if self.current_stage == DeploymentStage.CANARY:
            if self.config.gradual_stages:
                self.current_stage = DeploymentStage.GRADUAL_10
                self.current_traffic_percentage = self.config.gradual_stages[0]
                logger.info(f"📈 Advanced to {self.current_traffic_percentage}% traffic")
        
        elif self.current_stage == DeploymentStage.GRADUAL_10:
            if len(self.config.gradual_stages) > 1:
                self.current_stage = DeploymentStage.GRADUAL_50
                self.current_traffic_percentage = self.config.gradual_stages[1]
                logger.info(f"📈 Advanced to {self.current_traffic_percentage}% traffic")
        
        elif self.current_stage == DeploymentStage.GRADUAL_50:
            if len(self.config.gradual_stages) > 2:
                self.current_stage = DeploymentStage.FULL
                self.current_traffic_percentage = self.config.gradual_stages[2]
                logger.info(f"📈 Advanced to {self.current_traffic_percentage}% traffic (FULL)")
        
        # If stage changed, update deployment
        if self.current_stage != old_stage:
            # Update Helm traffic percentage if using Helm
            if self._is_helm_deployment():
                self._update_helm_traffic_percentage()
            
            # Reset metrics for new stage
            self.metrics = DeploymentMetrics(
                stage=self.current_stage,
                traffic_percentage=self.current_traffic_percentage,
                start_time=time.time()
            )
            return True
        
        # Already at full deployment
        return False
    
    def get_deployment_status(self) -> Dict[str, Any]:
        """Получить статус deployment."""
        status = {
            "stage": self.current_stage.value,
            "traffic_percentage": self.current_traffic_percentage,
            "running": self._running,
            "rollback_triggered": self._rollback_triggered,
            "metrics": {
                "requests_total": self.metrics.requests_total,
                "requests_success": self.metrics.requests_success,
                "requests_error": self.metrics.requests_error,
                "success_rate": self.metrics.success_rate,
                "errors_per_minute": self.metrics.errors_per_minute,
                "duration_seconds": time.time() - self.metrics.start_time
            },
            "stage_history": [
                {
                    "stage": m.stage.value,
                    "traffic_percentage": m.traffic_percentage,
                    "success_rate": m.success_rate,
                    "duration": m.duration
                }
                for m in self.stage_history
            ],
            "integration": {
                "helm_enabled": self._is_helm_deployment(),
                "helm_release": self.helm_release_name if self._is_helm_deployment() else None,
                "prometheus_enabled": bool(self.prometheus_url),
                "monitoring_active": self.monitoring_task is not None and not self.monitoring_task.done()
            }
        }
        return status
    
    def _trigger_cicd_rollback(self) -> bool:
        """
        Trigger rollback via CI/CD system APIs.
        
        Supports:
        - GitLab CI/CD
        - GitHub Actions
        - Jenkins
        - CircleCI
        - Azure DevOps
        
        Returns:
            True if rollback was triggered successfully
        """
        import os
        import subprocess
        
        ci_system = os.getenv('CI_SYSTEM', '').lower()
        
        # GitLab CI/CD
        if ci_system == 'gitlab' or 'GITLAB_CI' in os.environ:
            try:
                project_id = os.getenv('CI_PROJECT_ID')
                pipeline_id = os.getenv('CI_PIPELINE_ID')
                gitlab_token = os.getenv('GITLAB_TOKEN') or os.getenv('CI_JOB_TOKEN')
                
                if project_id and pipeline_id and gitlab_token:
                    import httpx
                    # Cancel current pipeline and trigger rollback pipeline
                    url = f"https://gitlab.com/api/v4/projects/{project_id}/pipelines/{pipeline_id}/cancel"
                    headers = {"PRIVATE-TOKEN": gitlab_token}
                    
                    response = httpx.post(url, headers=headers, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"✅ GitLab pipeline {pipeline_id} cancelled")
                        
                        # Trigger rollback pipeline
                        rollback_url = f"https://gitlab.com/api/v4/projects/{project_id}/pipeline"
                        rollback_data = {"ref": "main", "variables": [{"key": "ROLLBACK", "value": "true"}]}
                        rollback_response = httpx.post(rollback_url, headers=headers, json=rollback_data, timeout=10)
                        if rollback_response.status_code == 201:
                            logger.info("✅ GitLab rollback pipeline triggered")
                            return True
            except Exception as e:
                logger.warning(f"GitLab rollback failed: {e}")
        
        # GitHub Actions
        elif ci_system == 'github' or 'GITHUB_ACTIONS' in os.environ:
            try:
                repo = os.getenv('GITHUB_REPOSITORY')
                github_token = os.getenv('GITHUB_TOKEN')
                workflow_id = os.getenv('GITHUB_WORKFLOW_ID', 'rollback.yml')
                
                if repo and github_token:
                    import httpx
                    # Trigger rollback workflow
                    url = f"https://api.github.com/repos/{repo}/actions/workflows/{workflow_id}/dispatches"
                    headers = {
                        "Authorization": f"token {github_token}",
                        "Accept": "application/vnd.github.v3+json"
                    }
                    data = {"ref": "main", "inputs": {"rollback": "true"}}
                    
                    response = httpx.post(url, headers=headers, json=data, timeout=10)
                    if response.status_code == 204:
                        logger.info(f"✅ GitHub Actions rollback workflow triggered for {repo}")
                        return True
            except Exception as e:
                logger.warning(f"GitHub Actions rollback failed: {e}")
        
        # Jenkins
        elif ci_system == 'jenkins' or 'JENKINS_URL' in os.environ:
            try:
                jenkins_url = os.getenv('JENKINS_URL')
                jenkins_user = os.getenv('JENKINS_USER')
                jenkins_token = os.getenv('JENKINS_TOKEN')
                job_name = os.getenv('JENKINS_JOB_NAME', 'x0tta6bl4-rollback')
                
                if jenkins_url and jenkins_user and jenkins_token:
                    import httpx
                    import base64
                    auth = base64.b64encode(f"{jenkins_user}:{jenkins_token}".encode()).decode()
                    url = f"{jenkins_url}/job/{job_name}/buildWithParameters"
                    headers = {"Authorization": f"Basic {auth}"}
                    params = {"ROLLBACK": "true"}
                    
                    response = httpx.post(url, headers=headers, params=params, timeout=10)
                    if response.status_code in [200, 201]:
                        logger.info(f"✅ Jenkins rollback job triggered: {job_name}")
                        return True
            except Exception as e:
                logger.warning(f"Jenkins rollback failed: {e}")
        
        # CircleCI
        elif ci_system == 'circleci' or 'CIRCLECI' in os.environ:
            try:
                circle_token = os.getenv('CIRCLE_TOKEN')
                project_slug = os.getenv('CIRCLE_PROJECT_SLUG')
                
                if circle_token and project_slug:
                    import httpx
                    url = f"https://circleci.com/api/v2/project/{project_slug}/pipeline"
                    headers = {"Circle-Token": circle_token}
                    data = {"branch": "main", "parameters": {"rollback": True}}
                    
                    response = httpx.post(url, headers=headers, json=data, timeout=10)
                    if response.status_code == 201:
                        logger.info(f"✅ CircleCI rollback pipeline triggered for {project_slug}")
                        return True
            except Exception as e:
                logger.warning(f"CircleCI rollback failed: {e}")
        
        # Azure DevOps
        elif ci_system == 'azure' or 'AZURE_DEVOPS' in os.environ:
            try:
                org = os.getenv('AZURE_DEVOPS_ORG')
                project = os.getenv('AZURE_DEVOPS_PROJECT')
                pat = os.getenv('AZURE_DEVOPS_PAT')
                pipeline_id = os.getenv('AZURE_PIPELINE_ID')
                
                if org and project and pat and pipeline_id:
                    import httpx
                    import base64
                    auth = base64.b64encode(f":{pat}".encode()).decode()
                    url = f"https://dev.azure.com/{org}/{project}/_apis/pipelines/{pipeline_id}/runs"
                    headers = {
                        "Authorization": f"Basic {auth}",
                        "Content-Type": "application/json"
                    }
                    data = {"resources": {}, "templateParameters": {"rollback": "true"}}
                    
                    response = httpx.post(url, headers=headers, json=data, timeout=10)
                    if response.status_code == 200:
                        logger.info(f"✅ Azure DevOps rollback pipeline triggered")
                        return True
            except Exception as e:
                logger.warning(f"Azure DevOps rollback failed: {e}")
        
        return False

