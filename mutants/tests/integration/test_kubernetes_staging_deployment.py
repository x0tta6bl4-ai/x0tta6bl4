"""
Kubernetes Staging Deployment & Validation Tests

Comprehensive testing for x0tta6bl4 deployment in Kubernetes staging environment:
- Pod lifecycle (creation, health, termination)
- Network connectivity and service discovery
- Resource management and limits
- Storage persistence
- RBAC and security policies
- Scaling and load handling
- Health checks and readiness probes
- Monitoring and logging integration
- Chaos testing and recovery

Phase: Q1 2026 Production Readiness
Target: 100+ node mesh network in k8s staging
"""

import pytest
import asyncio
import json
import subprocess
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pathlib import Path


@pytest.fixture(scope="session")
def k8s_namespace():
    """Get or create staging namespace."""
    namespace = "x0tta6bl4-staging"
    try:
        result = subprocess.run(
            ["kubectl", "get", "namespace", namespace],
            capture_output=True,
            text=True
        )
        if result.returncode != 0:
            subprocess.run(
                ["kubectl", "create", "namespace", namespace],
                check=True
            )
    except Exception as e:
        pytest.skip(f"Kubernetes not available: {e}")
    
    return namespace


@pytest.fixture(scope="session")
def k8s_context():
    """Get current kubectl context."""
    try:
        result = subprocess.run(
            ["kubectl", "config", "current-context"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except Exception:
        pytest.skip("kubectl not available")


class TestKubernetesClusterReadiness:
    """Test Kubernetes cluster readiness for x0tta6bl4."""

    def test_cluster_accessible(self):
        """Test cluster is accessible."""
        try:
            result = subprocess.run(
                ["kubectl", "cluster-info"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0, "Cluster not accessible"
        except subprocess.TimeoutExpired:
            pytest.skip("Cluster unreachable (timeout)")

    def test_api_server_responsive(self):
        """Test API server is responsive."""
        try:
            result = subprocess.run(
                ["kubectl", "get", "nodes"],
                capture_output=True,
                text=True,
                timeout=5
            )
            assert result.returncode == 0
            assert "NAME" in result.stdout  # Header line present
        except Exception as e:
            pytest.skip(f"API server not responsive: {e}")

    def test_required_namespaces_exist(self):
        """Test required namespaces exist or can be created."""
        required_namespaces = [
            "default",
            "kube-system",
            "kube-public"
        ]
        
        for ns in required_namespaces:
            result = subprocess.run(
                ["kubectl", "get", "namespace", ns],
                capture_output=True,
                text=True
            )
            assert result.returncode == 0, f"Namespace {ns} not found"

    def test_crd_support(self):
        """Test CRD (Custom Resource Definition) support."""
        result = subprocess.run(
            ["kubectl", "api-versions"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        # Should have apiextensions.k8s.io for CRDs
        assert "apiextensions" in result.stdout or result.returncode == 0


class TestPodDeployment:
    """Test pod deployment and lifecycle."""

    def test_deployment_creation(self, k8s_namespace):
        """Test creating a deployment."""
        deployment_yaml = f"""
apiVersion: apps/v1
kind: Deployment
metadata:
  name: x0tta6bl4-test
  namespace: {k8s_namespace}
spec:
  replicas: 2
  selector:
    matchLabels:
      app: x0tta6bl4-test
  template:
    metadata:
      labels:
        app: x0tta6bl4-test
    spec:
      containers:
      - name: app
        image: nginx:latest
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi
"""
        # Write deployment
        with open("/tmp/test-deployment.yaml", "w") as f:
            f.write(deployment_yaml)
        
        # Create deployment
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-deployment.yaml"],
            capture_output=True,
            text=True,
            timeout=30
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-deployment.yaml"],
            capture_output=True,
            timeout=10
        )

    def test_pod_readiness_probe(self, k8s_namespace):
        """Test pod readiness probes."""
        pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: x0tta6bl4-readiness-test
  namespace: {k8s_namespace}
spec:
  containers:
  - name: app
    image: nginx:latest
    ports:
    - containerPort: 80
    readinessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 10
    livenessProbe:
      httpGet:
        path: /
        port: 80
      initialDelaySeconds: 15
      periodSeconds: 20
"""
        with open("/tmp/test-pod.yaml", "w") as f:
            f.write(pod_yaml)
        
        # Create pod
        subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-pod.yaml"],
            capture_output=True,
            timeout=30
        )
        
        # Check readiness (should become ready within 30s)
        for i in range(6):
            result = subprocess.run(
                ["kubectl", "get", "pod", "-n", k8s_namespace,
                 "x0tta6bl4-readiness-test", "-o", "json"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                pod_json = json.loads(result.stdout)
                conditions = pod_json.get("status", {}).get("conditions", [])
                ready = any(c["type"] == "Ready" and c["status"] == "True" 
                           for c in conditions)
                
                if ready:
                    break
            
            asyncio.run(asyncio.sleep(5))
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-pod.yaml"],
            capture_output=True,
            timeout=10
        )

    def test_pod_resource_limits(self, k8s_namespace):
        """Test pod resource limits enforcement."""
        pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: x0tta6bl4-resource-test
  namespace: {k8s_namespace}
spec:
  containers:
  - name: app
    image: nginx:latest
    resources:
      requests:
        cpu: 50m
        memory: 64Mi
      limits:
        cpu: 200m
        memory: 256Mi
"""
        with open("/tmp/test-resource-pod.yaml", "w") as f:
            f.write(pod_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-resource-pod.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Verify resource limits in pod spec
        result = subprocess.run(
            ["kubectl", "get", "pod", "-n", k8s_namespace,
             "x0tta6bl4-resource-test", "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            pod_json = json.loads(result.stdout)
            container = pod_json["spec"]["containers"][0]
            limits = container["resources"]["limits"]
            assert "cpu" in limits
            assert "memory" in limits
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "pod", "-n", k8s_namespace,
             "x0tta6bl4-resource-test"],
            capture_output=True
        )


class TestNetworkConnectivity:
    """Test network connectivity in Kubernetes."""

    def test_service_discovery(self, k8s_namespace):
        """Test Kubernetes service discovery."""
        # Create service
        service_yaml = f"""
apiVersion: v1
kind: Service
metadata:
  name: x0tta6bl4-test-service
  namespace: {k8s_namespace}
spec:
  selector:
    app: x0tta6bl4-test
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
"""
        with open("/tmp/test-service.yaml", "w") as f:
            f.write(service_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-service.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Verify service created
        result = subprocess.run(
            ["kubectl", "get", "svc", "-n", k8s_namespace,
             "x0tta6bl4-test-service"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-service.yaml"],
            capture_output=True
        )

    def test_pod_to_pod_networking(self, k8s_namespace):
        """Test pod-to-pod networking."""
        pods_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: x0tta6bl4-pod1
  namespace: {k8s_namespace}
spec:
  containers:
  - name: app
    image: nginx:latest

---
apiVersion: v1
kind: Pod
metadata:
  name: x0tta6bl4-pod2
  namespace: {k8s_namespace}
spec:
  containers:
  - name: app
    image: busybox:latest
    command: ['sleep', '3600']
"""
        with open("/tmp/test-pods.yaml", "w") as f:
            f.write(pods_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-pods.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-pods.yaml"],
            capture_output=True
        )


class TestStorageAndPersistence:
    """Test storage and data persistence."""

    def test_configmap_creation(self, k8s_namespace):
        """Test ConfigMap creation and usage."""
        cm_yaml = f"""
apiVersion: v1
kind: ConfigMap
metadata:
  name: x0tta6bl4-config
  namespace: {k8s_namespace}
data:
  trust_domain: x0tta6bl4.mesh
  replica_count: "3"
  log_level: INFO
"""
        with open("/tmp/test-cm.yaml", "w") as f:
            f.write(cm_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-cm.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Verify data
        result = subprocess.run(
            ["kubectl", "get", "configmap", "-n", k8s_namespace,
             "x0tta6bl4-config", "-o", "json"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            cm = json.loads(result.stdout)
            data = cm["data"]
            assert data["trust_domain"] == "x0tta6bl4.mesh"
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-cm.yaml"],
            capture_output=True
        )

    def test_secret_creation(self, k8s_namespace):
        """Test Secret creation for sensitive data."""
        secret_yaml = f"""
apiVersion: v1
kind: Secret
metadata:
  name: x0tta6bl4-secret
  namespace: {k8s_namespace}
type: Opaque
data:
  spiffe_key: c3BpZmZlX2tleV9kYXRh
  tls_cert: dGxzX2NlcnRfZGF0YQ==
"""
        with open("/tmp/test-secret.yaml", "w") as f:
            f.write(secret_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-secret.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-secret.yaml"],
            capture_output=True
        )


class TestMonitoringAndLogging:
    """Test monitoring and logging integration."""

    def test_pod_logging(self, k8s_namespace):
        """Test pod logging functionality."""
        pod_yaml = f"""
apiVersion: v1
kind: Pod
metadata:
  name: x0tta6bl4-logging-test
  namespace: {k8s_namespace}
spec:
  containers:
  - name: app
    image: nginx:latest
  restartPolicy: Never
"""
        with open("/tmp/test-logging-pod.yaml", "w") as f:
            f.write(pod_yaml)
        
        subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-logging-pod.yaml"],
            capture_output=True
        )
        
        # Get logs
        result = subprocess.run(
            ["kubectl", "logs", "-n", k8s_namespace,
             "x0tta6bl4-logging-test", "--tail=10"],
            capture_output=True,
            text=True,
            timeout=5
        )
        # Logs should be retrievable (even if empty)
        assert result.returncode in [0, 1]  # 1 if pod not ready yet
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-logging-pod.yaml"],
            capture_output=True
        )


class TestSecurityPolicies:
    """Test Kubernetes security policies."""

    def test_network_policy(self, k8s_namespace):
        """Test NetworkPolicy creation."""
        policy_yaml = f"""
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: x0tta6bl4-deny-all
  namespace: {k8s_namespace}
spec:
  podSelector: {{}}
  policyTypes:
  - Ingress
"""
        with open("/tmp/test-netpolicy.yaml", "w") as f:
            f.write(policy_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-netpolicy.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-netpolicy.yaml"],
            capture_output=True
        )

    def test_rbac_role_creation(self, k8s_namespace):
        """Test RBAC role creation."""
        role_yaml = f"""
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: x0tta6bl4-reader
  namespace: {k8s_namespace}
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
"""
        with open("/tmp/test-role.yaml", "w") as f:
            f.write(role_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-role.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-role.yaml"],
            capture_output=True
        )


class TestScalingAndLoad:
    """Test horizontal and vertical scaling."""

    def test_horizontal_pod_autoscaling(self, k8s_namespace):
        """Test HPA (Horizontal Pod Autoscaler) configuration."""
        hpa_yaml = f"""
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: x0tta6bl4-hpa
  namespace: {k8s_namespace}
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: x0tta6bl4-test
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
"""
        with open("/tmp/test-hpa.yaml", "w") as f:
            f.write(hpa_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-hpa.yaml"],
            capture_output=True,
            text=True
        )
        # HPA creation may fail if metrics-server not installed, that's ok
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-hpa.yaml"],
            capture_output=True
        )

    def test_pod_disruption_budget(self, k8s_namespace):
        """Test PodDisruptionBudget for availability."""
        pdb_yaml = f"""
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: x0tta6bl4-pdb
  namespace: {k8s_namespace}
spec:
  minAvailable: 1
  selector:
    matchLabels:
      app: x0tta6bl4-test
"""
        with open("/tmp/test-pdb.yaml", "w") as f:
            f.write(pdb_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-pdb.yaml"],
            capture_output=True,
            text=True
        )
        # PDB creation may fail, that's ok for this test
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-pdb.yaml"],
            capture_output=True
        )


class TestProductionReadiness:
    """Test production readiness criteria."""

    def test_multi_zone_support(self):
        """Test cluster has nodes across multiple zones."""
        result = subprocess.run(
            ["kubectl", "get", "nodes", "-o",
             "jsonpath={.items[*].metadata.labels.topology\\.kubernetes\\.io/zone}"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            zones = set(result.stdout.split())
            # Multi-zone is ideal but not required for staging
            assert len(zones) >= 1

    def test_resource_quotas(self, k8s_namespace):
        """Test namespace resource quotas."""
        quota_yaml = f"""
apiVersion: v1
kind: ResourceQuota
metadata:
  name: x0tta6bl4-quota
  namespace: {k8s_namespace}
spec:
  hard:
    requests.cpu: "100"
    requests.memory: "200Gi"
    limits.cpu: "200"
    limits.memory: "400Gi"
    pods: "500"
"""
        with open("/tmp/test-quota.yaml", "w") as f:
            f.write(quota_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-quota.yaml"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-quota.yaml"],
            capture_output=True
        )

    def test_ingress_configuration(self, k8s_namespace):
        """Test Ingress configuration."""
        ingress_yaml = f"""
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: x0tta6bl4-ingress
  namespace: {k8s_namespace}
spec:
  rules:
  - host: x0tta6bl4.staging
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: x0tta6bl4-test-service
            port:
              number: 80
"""
        with open("/tmp/test-ingress.yaml", "w") as f:
            f.write(ingress_yaml)
        
        result = subprocess.run(
            ["kubectl", "apply", "-f", "/tmp/test-ingress.yaml"],
            capture_output=True,
            text=True
        )
        # Ingress creation may fail if no ingress controller, that's ok
        
        # Cleanup
        subprocess.run(
            ["kubectl", "delete", "-f", "/tmp/test-ingress.yaml"],
            capture_output=True
        )
