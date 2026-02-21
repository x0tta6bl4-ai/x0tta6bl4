"""
MaaS Helm Chart Tests
=====================

Unit tests for Helm chart templates using pytest.
Run with: pytest tests/helm/test_maas_chart.py -v
"""

import os
import subprocess
import json
import pytest
from pathlib import Path


# Chart path
CHART_PATH = Path(__file__).parent.parent.parent / "deploy" / "helm" / "maas"
HELM_BIN = os.getenv("HELM_BIN", "helm")


def _helm_available() -> bool:
    try:
        probe = subprocess.run(
            [HELM_BIN, "version", "--short"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False

    if probe.returncode == 0:
        return True

    err = (probe.stderr or "").lower()
    # Some sandboxed environments expose snap helm that cannot execute.
    if "snap-confine" in err or "required permitted capability" in err:
        return False
    return False


pytestmark = pytest.mark.skipif(
    not _helm_available(),
    reason="Helm binary is not executable in this environment.",
)


def helm_template(values: dict = None, release_name: str = "test-maas", namespace: str = "default") -> dict:
    """
    Render Helm chart templates and return parsed YAML.
    
    Args:
        values: Dictionary of values to override
        release_name: Helm release name
        namespace: Target namespace
    
    Returns:
        Dictionary of rendered Kubernetes resources
    """
    cmd = [
        HELM_BIN, "template", release_name, str(CHART_PATH),
        "--namespace", namespace,
    ]
    
    if values:
        # Write values to temp file
        import tempfile
        import yaml
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(values, f)
            cmd.extend(["--values", f.name])
            temp_file = f.name
    else:
        temp_file = None
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        
        # Parse YAML output (multiple documents separated by ---)
        import yaml
        documents = []
        for doc in yaml.safe_load_all(result.stdout):
            if doc:
                documents.append(doc)
        
        return documents
    finally:
        if temp_file and os.path.exists(temp_file):
            os.unlink(temp_file)


class TestChartMetadata:
    """Tests for Chart.yaml metadata."""
    
    def test_chart_exists(self):
        """Verify chart directory exists."""
        assert CHART_PATH.exists(), f"Chart not found at {CHART_PATH}"
    
    def test_chart_yaml_exists(self):
        """Verify Chart.yaml exists."""
        chart_file = CHART_PATH / "Chart.yaml"
        assert chart_file.exists(), "Chart.yaml not found"
    
    def test_chart_has_required_fields(self):
        """Verify Chart.yaml has required fields."""
        import yaml
        with open(CHART_PATH / "Chart.yaml") as f:
            chart = yaml.safe_load(f)
        
        assert "apiVersion" in chart, "Missing apiVersion"
        assert "name" in chart, "Missing name"
        assert "version" in chart, "Missing version"
        assert chart["apiVersion"] == "v2", "Invalid apiVersion"
    
    def test_values_yaml_exists(self):
        """Verify values.yaml exists."""
        values_file = CHART_PATH / "values.yaml"
        assert values_file.exists(), "values.yaml not found"


class TestAPIDeployment:
    """Tests for API deployment template."""
    
    def test_api_deployment_renders(self):
        """Verify API deployment renders without errors."""
        docs = helm_template()
        
        api_deployments = [
            d for d in docs
            if d.get("kind") == "Deployment"
            and d.get("metadata", {}).get("name", "").endswith("-api")
        ]
        
        assert len(api_deployments) > 0, "API deployment not found"
    
    def test_api_deployment_replicas(self):
        """Verify API deployment has correct replica count."""
        docs = helm_template({"api": {"replicaCount": 5}})
        
        api_deployment = next(
            d for d in docs
            if d.get("kind") == "Deployment"
            and d.get("metadata", {}).get("name", "").endswith("-api")
        )
        
        assert api_deployment["spec"]["replicas"] == 5
    
    def test_api_deployment_resources(self):
        """Verify API deployment has resource limits."""
        docs = helm_template()
        
        api_deployment = next(
            d for d in docs
            if d.get("kind") == "Deployment"
            and d.get("metadata", {}).get("name", "").endswith("-api")
        )
        
        container = api_deployment["spec"]["template"]["spec"]["containers"][0]
        assert "resources" in container, "Missing resource limits"
        assert "limits" in container["resources"], "Missing resource limits"
        assert "requests" in container["resources"], "Missing resource requests"
    
    def test_api_deployment_probes(self):
        """Verify API deployment has liveness and readiness probes."""
        docs = helm_template()
        
        api_deployment = next(
            d for d in docs
            if d.get("kind") == "Deployment"
            and d.get("metadata", {}).get("name", "").endswith("-api")
        )
        
        container = api_deployment["spec"]["template"]["spec"]["containers"][0]
        assert "livenessProbe" in container, "Missing liveness probe"
        assert "readinessProbe" in container, "Missing readiness probe"


class TestAPIService:
    """Tests for API service template."""
    
    def test_api_service_renders(self):
        """Verify API service renders without errors."""
        docs = helm_template()
        
        api_services = [
            d for d in docs
            if d.get("kind") == "Service"
            and d.get("metadata", {}).get("name", "").endswith("-api")
        ]
        
        assert len(api_services) > 0, "API service not found"
    
    def test_api_service_type(self):
        """Verify API service has correct type."""
        docs = helm_template({"api": {"service": {"type": "LoadBalancer"}}})
        
        api_service = next(
            d for d in docs
            if d.get("kind") == "Service"
            and d.get("metadata", {}).get("name", "").endswith("-api")
        )
        
        assert api_service["spec"]["type"] == "LoadBalancer"


class TestIngress:
    """Tests for Ingress template."""
    
    def test_ingress_disabled_by_default(self):
        """Verify ingress can be disabled."""
        docs = helm_template({"api": {"ingress": {"enabled": False}}})
        
        ingresses = [
            d for d in docs
            if d.get("kind") == "Ingress"
        ]
        
        assert len(ingresses) == 0, "Ingress should be disabled"
    
    def test_ingress_enabled(self):
        """Verify ingress renders when enabled."""
        docs = helm_template({
            "api": {
                "ingress": {
                    "enabled": True,
                    "hosts": [{"host": "test.local", "paths": [{"path": "/", "pathType": "Prefix"}]}]
                }
            }
        })
        
        ingresses = [
            d for d in docs
            if d.get("kind") == "Ingress"
        ]
        
        assert len(ingresses) > 0, "Ingress not found"


class TestConfigMap:
    """Tests for ConfigMap template."""
    
    def test_configmap_renders(self):
        """Verify ConfigMap renders without errors."""
        docs = helm_template()
        
        configmaps = [
            d for d in docs
            if d.get("kind") == "ConfigMap"
        ]
        
        assert len(configmaps) > 0, "ConfigMap not found"
    
    def test_configmap_has_environment(self):
        """Verify ConfigMap has environment variable."""
        docs = helm_template({"global": {"environment": "staging"}})
        
        configmap = next(
            d for d in docs
            if d.get("kind") == "ConfigMap"
        )
        
        assert configmap["data"]["ENVIRONMENT"] == "staging"


class TestSecrets:
    """Tests for Secrets template."""
    
    def test_secret_renders(self):
        """Verify Secret renders without errors."""
        docs = helm_template()
        
        secrets = [
            d for d in docs
            if d.get("kind") == "Secret"
        ]
        
        assert len(secrets) > 0, "Secret not found"
    
    def test_secret_is_opaque(self):
        """Verify Secret is Opaque type."""
        docs = helm_template()
        
        secret = next(
            d for d in docs
            if d.get("kind") == "Secret"
        )
        
        assert secret["type"] == "Opaque"


class TestHPA:
    """Tests for HorizontalPodAutoscaler template."""
    
    def test_hpa_disabled(self):
        """Verify HPA can be disabled."""
        docs = helm_template({"api": {"autoscaling": {"enabled": False}}})
        
        hpas = [
            d for d in docs
            if d.get("kind") == "HorizontalPodAutoscaler"
        ]
        
        # Should not have API HPA
        api_hpas = [h for h in hpas if h.get("metadata", {}).get("name", "").endswith("-api")]
        assert len(api_hpas) == 0, "API HPA should be disabled"
    
    def test_hpa_enabled(self):
        """Verify HPA renders when enabled."""
        docs = helm_template({
            "api": {
                "autoscaling": {
                    "enabled": True,
                    "minReplicas": 2,
                    "maxReplicas": 10
                }
            }
        })
        
        hpa = next(
            (d for d in docs
             if d.get("kind") == "HorizontalPodAutoscaler"
             and d.get("metadata", {}).get("name", "").endswith("-api")),
            None
        )
        
        assert hpa is not None, "HPA not found"
        assert hpa["spec"]["minReplicas"] == 2
        assert hpa["spec"]["maxReplicas"] == 10


class TestNetworkPolicy:
    """Tests for NetworkPolicy template."""
    
    def test_network_policy_disabled(self):
        """Verify NetworkPolicy can be disabled."""
        docs = helm_template({"networkPolicy": {"enabled": False}})
        
        policies = [
            d for d in docs
            if d.get("kind") == "NetworkPolicy"
        ]
        
        assert len(policies) == 0, "NetworkPolicy should be disabled"
    
    def test_network_policy_enabled(self):
        """Verify NetworkPolicy renders when enabled."""
        docs = helm_template({"networkPolicy": {"enabled": True}})
        
        policies = [
            d for d in docs
            if d.get("kind") == "NetworkPolicy"
        ]
        
        assert len(policies) > 0, "NetworkPolicy not found"


class TestRBAC:
    """Tests for RBAC template."""
    
    def test_rbac_disabled(self):
        """Verify RBAC can be disabled."""
        docs = helm_template({"rbac": {"create": False}})
        
        roles = [
            d for d in docs
            if d.get("kind") in ["Role", "RoleBinding", "ClusterRole", "ClusterRoleBinding"]
        ]
        
        assert len(roles) == 0, "RBAC should be disabled"
    
    def test_rbac_enabled(self):
        """Verify RBAC renders when enabled."""
        docs = helm_template({"rbac": {"create": True}})
        
        roles = [
            d for d in docs
            if d.get("kind") == "Role"
        ]
        
        role_bindings = [
            d for d in docs
            if d.get("kind") == "RoleBinding"
        ]
        
        assert len(roles) > 0, "Role not found"
        assert len(role_bindings) > 0, "RoleBinding not found"


class TestServiceAccount:
    """Tests for ServiceAccount template."""
    
    def test_service_account_disabled(self):
        """Verify ServiceAccount can be disabled."""
        docs = helm_template({"serviceAccount": {"create": False}})
        
        service_accounts = [
            d for d in docs
            if d.get("kind") == "ServiceAccount"
        ]
        
        assert len(service_accounts) == 0, "ServiceAccount should be disabled"
    
    def test_service_account_enabled(self):
        """Verify ServiceAccount renders when enabled."""
        docs = helm_template({"serviceAccount": {"create": True}})
        
        service_accounts = [
            d for d in docs
            if d.get("kind") == "ServiceAccount"
        ]
        
        assert len(service_accounts) > 0, "ServiceAccount not found"


class TestWorkerDeployment:
    """Tests for Worker deployment template."""
    
    def test_worker_deployment_renders(self):
        """Verify Worker deployment renders without errors."""
        docs = helm_template()
        
        worker_deployments = [
            d for d in docs
            if d.get("kind") == "Deployment"
            and d.get("metadata", {}).get("name", "").endswith("-worker")
        ]
        
        assert len(worker_deployments) > 0, "Worker deployment not found"
    
    def test_worker_has_celery_config(self):
        """Verify Worker has Celery configuration."""
        docs = helm_template()
        
        worker_deployment = next(
            (d for d in docs
             if d.get("kind") == "Deployment"
             and d.get("metadata", {}).get("name", "").endswith("-worker")),
            None
        )
        
        if worker_deployment:
            container = worker_deployment["spec"]["template"]["spec"]["containers"][0]
            env_vars = {e["name"]: e["value"] for e in container.get("env", [])}
            
            # Should have Celery broker URL
            assert "CELERY_BROKER_URL" in env_vars or any(
                e.get("name") == "CELERY_BROKER_URL" for e in container.get("envFrom", [])
            ), "Missing Celery broker configuration"


class TestControllerDeployment:
    """Tests for Controller deployment template."""
    
    def test_controller_deployment_renders(self):
        """Verify Controller deployment renders without errors."""
        docs = helm_template()
        
        controller_deployments = [
            d for d in docs
            if d.get("kind") == "Deployment"
            and d.get("metadata", {}).get("name", "").endswith("-controller")
        ]
        
        assert len(controller_deployments) > 0, "Controller deployment not found"


class TestStagingValues:
    """Tests for staging values file."""
    
    def test_staging_values_file_exists(self):
        """Verify staging values file exists."""
        staging_file = CHART_PATH / "values-staging.yaml"
        assert staging_file.exists(), "values-staging.yaml not found"
    
    def test_staging_values_valid_yaml(self):
        """Verify staging values is valid YAML."""
        import yaml
        with open(CHART_PATH / "values-staging.yaml") as f:
            values = yaml.safe_load(f)
        
        assert values is not None, "values-staging.yaml is empty"
        assert "global" in values, "Missing global section"
        assert values["global"]["environment"] == "staging"


class TestProductionValues:
    """Tests for production values file."""
    
    def test_production_values_file_exists(self):
        """Verify production values file exists."""
        prod_file = CHART_PATH / "values-production.yaml"
        assert prod_file.exists(), "values-production.yaml not found"
    
    def test_production_values_valid_yaml(self):
        """Verify production values is valid YAML."""
        import yaml
        with open(CHART_PATH / "values-production.yaml") as f:
            values = yaml.safe_load(f)
        
        assert values is not None, "values-production.yaml is empty"
        assert "global" in values, "Missing global section"
        assert values["global"]["environment"] == "production"
    
    def test_production_has_higher_replicas(self):
        """Verify production has higher replica counts."""
        import yaml
        with open(CHART_PATH / "values-staging.yaml") as f:
            staging = yaml.safe_load(f)
        
        with open(CHART_PATH / "values-production.yaml") as f:
            production = yaml.safe_load(f)
        
        # Production should have more replicas
        assert production["api"]["replicaCount"] >= staging["api"]["replicaCount"]
        assert production["worker"]["replicaCount"] >= staging["worker"]["replicaCount"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
