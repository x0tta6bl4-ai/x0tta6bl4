# Terraform Multi-Cloud Infrastructure for x0tta6bl4 MaaS v1.0
variable "clusters" {
  description = "Number of clusters in federation"
  default     = 3
}

variable "federation" {
  description = "Enable cross-cluster federation"
  default     = true
}

# AWS EKS - Control Plane
resource "aws_eks_cluster" "control_plane" {
  name     = "x0tta-control-plane"
  role_arn = aws_iam_role.eks_role.arn
  vpc_config {
    subnet_ids = aws_subnet.eks_subnets[*].id
  }
}

# GCP GKE - Edge-1
resource "google_container_cluster" "edge_1" {
  name               = "x0tta-edge-1"
  location           = "us-central1"
  initial_node_count = 3
}

# Azure AKS - Edge-2
resource "azurerm_kubernetes_cluster" "edge_2" {
  name                = "x0tta-edge-2"
  location            = "us-central1" # Azure location
  resource_group_name = "x0tta-rg"
  dns_prefix          = "x0tta"

  default_node_pool {
    name       = "default"
    node_count = 3
    vm_size    = "Standard_DS2_v2"
  }

  identity {
    type = "SystemAssigned"
  }
}