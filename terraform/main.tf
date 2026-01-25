# Terraform configuration for x0tta6bl4 infrastructure
# Supports AWS, GCP, Azure

terraform {
  required_version = ">= 1.0"
  
  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.11"
    }
  }
  
  # Backend configuration (uncomment and configure)
  # backend "s3" {
  #   bucket = "x0tta6bl4-terraform-state"
  #   key    = "infrastructure/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

# Provider configuration
provider "kubernetes" {
  # Configure based on your cluster
  # config_path = "~/.kube/config"
}

provider "helm" {
  kubernetes {
    # Configure based on your cluster
    # config_path = "~/.kube/config"
  }
}

# Kubernetes namespace
resource "kubernetes_namespace" "x0tta6bl4" {
  metadata {
    name = "x0tta6bl4"
    labels = {
      app = "x0tta6bl4"
    }
  }
}

# Helm release
resource "helm_release" "x0tta6bl4" {
  name       = "x0tta6bl4"
  namespace  = kubernetes_namespace.x0tta6bl4.metadata[0].name
  repository = "oci://ghcr.io/x0tta6bl4"  # Or local path
  chart      = "x0tta6bl4"
  version    = "3.4.0"
  
  values = [
    file("${path.module}/helm-values.yaml")
  ]
  
  depends_on = [kubernetes_namespace.x0tta6bl4]
}

