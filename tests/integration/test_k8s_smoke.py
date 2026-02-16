"""
P0 #5: Staging Kubernetes E2E Smoke Tests

Tests for verifying the x0tta6bl4 deployment in Kubernetes staging environment:
- Pod deployment and readiness
- Service accessibility
- Health check endpoints
- Metrics collection
- SPIRE integration
- Mesh connectivity
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest
import requests


class TestK8sDeployment:
    """Tests for Kubernetes deployment"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup test environment"""
        self.namespace = "x0tta6bl4-staging"
        self.deployment_name = "staging-x0tta6bl4"

        if shutil.which("kubectl") is None:
            pytest.skip("kubectl is not available in this environment")

        try:
            cluster = subprocess.run(
                ["kubectl", "cluster-info"], capture_output=True, text=True, timeout=10
            )
            if cluster.returncode != 0:
                pytest.skip("kubernetes cluster is not reachable")
        except Exception:
            pytest.skip("kubernetes cluster is not reachable")

        ns_check = subprocess.run(
            ["kubectl", "get", "namespace", self.namespace],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if ns_check.returncode != 0:
            pytest.skip(f"staging namespace '{self.namespace}' not found")

    def run_kubectl(self, *args):
        """Run kubectl command and return output"""
        cmd = ["kubectl"] + list(args)
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            return result.stdout, result.stderr, result.returncode
        except subprocess.TimeoutExpired:
            pytest.skip("kubectl command timeout")

    def test_namespace_exists(self):
        """Test that staging namespace exists"""
        stdout, _, rc = self.run_kubectl("get", "namespace", self.namespace)
        assert rc == 0, "Staging namespace should exist"
        assert self.namespace in stdout

    def test_deployment_exists(self):
        """Test that deployment exists"""
        stdout, _, rc = self.run_kubectl(
            "get", "deployment", self.deployment_name, "-n", self.namespace
        )
        assert rc == 0, "Deployment should exist"
        assert self.deployment_name in stdout

    def test_deployment_replicas_ready(self):
        """Test that deployment replicas are ready"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        replicas = deployment["spec"]["replicas"]
        ready_replicas = deployment["status"].get("readyReplicas", 0)

        assert (
            ready_replicas == replicas
        ), f"Expected {replicas} ready replicas, got {ready_replicas}"

    def test_pods_running(self):
        """Test that pods are running"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            "app.kubernetes.io/name=x0tta6bl4",
            "-o",
            "json",
        )
        assert rc == 0

        pods = json.loads(stdout)["items"]
        assert len(pods) > 0, "Should have at least one pod"

        for pod in pods:
            status = pod["status"]["phase"]
            assert (
                status == "Running"
            ), f"Pod {pod['metadata']['name']} not running (status: {status})"

    def test_service_exists(self):
        """Test that service exists"""
        stdout, _, rc = self.run_kubectl(
            "get", "svc", "staging-x0tta6bl4", "-n", self.namespace
        )
        assert rc == 0, "Service should exist"

    def test_service_has_cluster_ip(self):
        """Test that service has cluster IP"""
        stdout, _, rc = self.run_kubectl(
            "get", "svc", "staging-x0tta6bl4", "-n", self.namespace, "-o", "json"
        )
        assert rc == 0

        svc = json.loads(stdout)
        cluster_ip = svc["spec"]["clusterIP"]
        assert cluster_ip and cluster_ip != "None"

    def test_configmap_exists(self):
        """Test that configmap exists"""
        stdout, _, rc = self.run_kubectl(
            "get", "configmap", "staging-x0tta6bl4-config", "-n", self.namespace
        )
        assert rc == 0, "ConfigMap should exist"

    def test_configmap_has_correct_values(self):
        """Test that configmap contains expected values"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "configmap",
            "staging-x0tta6bl4-config",
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        cm = json.loads(stdout)
        data = cm["data"]

        assert data["SPIFFE_TRUST_DOMAIN"] == "x0tta6bl4.mesh"
        assert data["METRICS_ENABLED"] == "true"
        assert "mape_k_config.yaml" in data

    def test_pod_has_metrics_annotation(self):
        """Test that pods have metrics scraping annotations"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            "app.kubernetes.io/name=x0tta6bl4",
            "-o",
            "json",
        )
        assert rc == 0

        pods = json.loads(stdout)["items"]
        for pod in pods:
            annotations = pod["metadata"]["annotations"]
            assert annotations.get("prometheus.io/scrape") == "true"
            assert annotations.get("prometheus.io/port") == "9090"

    def test_pod_security_context(self):
        """Test that pods have correct security context"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            "app.kubernetes.io/name=x0tta6bl4",
            "-o",
            "json",
        )
        assert rc == 0

        pods = json.loads(stdout)["items"]
        for pod in pods:
            spec = pod["spec"]
            assert spec["securityContext"]["runAsNonRoot"] == True
            assert spec["securityContext"]["runAsUser"] == 1000

    def test_pod_resource_limits(self):
        """Test that pods have resource limits"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            "app.kubernetes.io/name=x0tta6bl4",
            "-o",
            "json",
        )
        assert rc == 0

        pods = json.loads(stdout)["items"]
        for pod in pods:
            for container in pod["spec"]["containers"]:
                if container["name"] == "x0tta6bl4":
                    resources = container.get("resources", {})
                    assert "limits" in resources
                    assert "requests" in resources

    def test_serviceaccount_exists(self):
        """Test that service account exists"""
        stdout, _, rc = self.run_kubectl(
            "get", "serviceaccount", "staging-x0tta6bl4", "-n", self.namespace
        )
        assert rc == 0, "ServiceAccount should exist"

    def test_rbac_role_exists(self):
        """Test that RBAC role exists"""
        stdout, _, rc = self.run_kubectl("get", "clusterrole", "x0tta6bl4-staging")
        assert rc == 0, "ClusterRole should exist"

    def test_rbac_rolebinding_exists(self):
        """Test that RBAC role binding exists"""
        stdout, _, rc = self.run_kubectl(
            "get", "clusterrolebinding", "x0tta6bl4-staging"
        )
        assert rc == 0, "ClusterRoleBinding should exist"

    def test_pods_have_volume_mounts(self):
        """Test that pods have required volume mounts"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            "app.kubernetes.io/name=x0tta6bl4",
            "-o",
            "json",
        )
        assert rc == 0

        pods = json.loads(stdout)["items"]
        for pod in pods:
            for container in pod["spec"]["containers"]:
                if container["name"] == "x0tta6bl4":
                    mounts = {m["name"] for m in container.get("volumeMounts", [])}
                    assert "config" in mounts
                    assert "data" in mounts

    def test_metrics_service_monitor(self):
        """Test that ServiceMonitor exists for metrics"""
        stdout, _, rc = self.run_kubectl(
            "get", "servicemonitor", "staging-x0tta6bl4", "-n", self.namespace
        )
        assert rc == 0, "ServiceMonitor should exist"

    def test_anti_affinity_configured(self):
        """Test that pod anti-affinity is configured"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        affinity = deployment["spec"]["template"]["spec"]["affinity"]
        assert "podAntiAffinity" in affinity
        assert (
            len(
                affinity["podAntiAffinity"][
                    "preferredDuringSchedulingIgnoredDuringExecution"
                ]
            )
            > 0
        )

    def test_rolling_update_strategy(self):
        """Test that deployment uses RollingUpdate strategy"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        strategy = deployment["spec"]["strategy"]
        assert strategy["type"] == "RollingUpdate"

    def test_liveness_probe_configured(self):
        """Test that liveness probe is configured"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        for container in deployment["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "x0tta6bl4":
                assert "livenessProbe" in container
                assert container["livenessProbe"]["httpGet"]["path"] == "/health"

    def test_readiness_probe_configured(self):
        """Test that readiness probe is configured"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        for container in deployment["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "x0tta6bl4":
                assert "readinessProbe" in container
                assert container["readinessProbe"]["httpGet"]["path"] == "/health"

    def test_ports_exposed(self):
        """Test that all required ports are exposed"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        for container in deployment["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "x0tta6bl4":
                ports = {p["name"] for p in container["ports"]}
                assert "http" in ports
                assert "metrics" in ports
                assert "mesh" in ports

    def test_environment_variables_set(self):
        """Test that environment variables are properly set"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "deployment",
            self.deployment_name,
            "-n",
            self.namespace,
            "-o",
            "json",
        )
        assert rc == 0

        deployment = json.loads(stdout)
        for container in deployment["spec"]["template"]["spec"]["containers"]:
            if container["name"] == "x0tta6bl4":
                env_names = {e["name"] for e in container.get("env", [])}
                assert "LOG_LEVEL" in env_names
                assert "SPIFFE_TRUST_DOMAIN" in env_names
                assert "METRICS_ENABLED" in env_names

    def test_kustomization_labels_applied(self):
        """Test that kustomization labels are applied"""
        stdout, _, rc = self.run_kubectl(
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            "app.kubernetes.io/name=x0tta6bl4",
            "-o",
            "json",
        )
        assert rc == 0

        pods = json.loads(stdout)["items"]
        for pod in pods:
            labels = pod["metadata"]["labels"]
            assert labels.get("environment") == "staging"
            assert "app.kubernetes.io/name" in labels


class TestKustomizeOverlay:
    """Tests for kustomize overlay"""

    def test_overlay_directory_exists(self):
        """Test that overlay directory exists"""
        overlay_path = Path("infra/k8s/overlays/staging")
        assert overlay_path.exists(), "Staging overlay directory should exist"

    def test_kustomization_file_exists(self):
        """Test that kustomization.yaml exists"""
        kustomization_path = Path("infra/k8s/overlays/staging/kustomization.yaml")
        assert kustomization_path.exists(), "kustomization.yaml should exist"

    def test_kustomization_file_valid(self):
        """Test that kustomization file is valid YAML"""
        import yaml

        kustomization_path = Path("infra/k8s/overlays/staging/kustomization.yaml")
        with open(kustomization_path) as f:
            content = yaml.safe_load(f)
            assert content is not None
            assert "bases" in content or "resources" in content

    def test_deployment_patch_exists(self):
        """Test that deployment patch exists"""
        patch_path = Path("infra/k8s/overlays/staging/deployment-patch.yaml")
        assert patch_path.exists(), "Deployment patch should exist"

    def test_rbac_manifests_exist(self):
        """Test that RBAC manifests exist"""
        rbac_path = Path("infra/k8s/overlays/staging/rbac.yaml")
        assert rbac_path.exists(), "RBAC manifests should exist"

    def test_monitoring_manifest_exists(self):
        """Test that monitoring manifest exists"""
        monitoring_path = Path("infra/k8s/overlays/staging/monitoring.yaml")
        assert monitoring_path.exists(), "Monitoring manifest should exist"

    def test_base_namespace_manifest_exists(self):
        """Test that base namespace manifest exists"""
        ns_path = Path("infra/k8s/base/namespace.yaml")
        assert ns_path.exists(), "Base namespace manifest should exist"

    def test_base_deployment_manifest_exists(self):
        """Test that base deployment manifest exists"""
        deploy_path = Path("infra/k8s/base/deployment.yaml")
        assert deploy_path.exists(), "Base deployment manifest should exist"

    def test_base_service_manifest_exists(self):
        """Test that base service manifest exists"""
        svc_path = Path("infra/k8s/base/service.yaml")
        assert svc_path.exists(), "Base service manifest should exist"

    def test_base_configmap_manifest_exists(self):
        """Test that base configmap manifest exists"""
        cm_path = Path("infra/k8s/base/configmap.yaml")
        assert cm_path.exists(), "Base configmap manifest should exist"

    def test_base_serviceaccount_manifest_exists(self):
        """Test that base serviceaccount manifest exists"""
        sa_path = Path("infra/k8s/base/serviceaccount.yaml")
        assert sa_path.exists(), "Base serviceaccount manifest should exist"

    def test_helm_values_staging_exists(self):
        """Test that Helm values-staging.yaml exists"""
        values_path = Path("infra/helm/x0tta6bl4/values-staging.yaml")
        assert values_path.exists(), "Helm values-staging.yaml should exist"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
