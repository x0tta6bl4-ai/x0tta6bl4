# terraform/eks/main.tf
# x0tta6bl4 EKS Cluster - Production-Ready Zero Trust Mesh Infrastructure
# Version: 1.0.0

terraform {
  required_version = ">= 1.7.0"
  
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.25"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.12"
    }
  }
  
  # S3 backend для state management (Zero Trust principle: immutable state)
  backend "s3" {
    bucket         = "x0tta6bl4-terraform-state"
    key            = "eks/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "x0tta6bl4-terraform-locks"
  }
}

provider "aws" {
  region = var.aws_region
  
  default_tags {
    tags = {
      Project     = "x0tta6bl4"
      ManagedBy   = "Terraform"
      Environment = var.environment
      CostCenter  = "mesh-infrastructure"
    }
  }
}

provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
  
  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)
    
    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# Data sources
data "aws_availability_zones" "available" {
  filter {
    name   = "opt-in-status"
    values = ["opt-in-not-required"]
  }
}

data "aws_caller_identity" "current" {}

# Local values
locals {
  cluster_name = "x0tta6bl4-${var.environment}"
  
  azs = slice(data.aws_availability_zones.available.names, 0, 3)
  
  tags = {
    "x0tta6bl4/cluster"   = local.cluster_name
    "x0tta6bl4/component" = "eks"
  }
}

# VPC для mesh network
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.0"
  
  name = "${local.cluster_name}-vpc"
  cidr = var.vpc_cidr
  
  azs             = local.azs
  private_subnets = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 4, k)]
  public_subnets  = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 8, k + 48)]
  intra_subnets   = [for k, v in local.azs : cidrsubnet(var.vpc_cidr, 8, k + 52)]
  
  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  # Zero Trust: private subnets для mesh nodes
  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = 1
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
  }
  
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"             = 1
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
    "karpenter.sh/discovery"                      = local.cluster_name
  }
  
  tags = local.tags
}

# EKS Cluster
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"
  
  cluster_name    = local.cluster_name
  cluster_version = var.cluster_version
  
  vpc_id                   = module.vpc.vpc_id
  subnet_ids               = module.vpc.private_subnets
  control_plane_subnet_ids = module.vpc.intra_subnets
  
  # Zero Trust: cluster access configuration
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = true
  cluster_endpoint_public_access_cidrs = var.allowed_cidr_blocks
  
  # Enable control plane logging для audit trail
  cluster_enabled_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]
  
  # IRSA для Zero Trust pod identity
  enable_irsa = true
  
  # Cluster addons
  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent              = true
      before_compute           = true
      service_account_role_arn = module.vpc_cni_irsa.iam_role_arn
      configuration_values = jsonencode({
        env = {
          ENABLE_PREFIX_DELEGATION = "true"
          WARM_PREFIX_TARGET       = "1"
        }
      })
    }
    aws-ebs-csi-driver = {
      most_recent              = true
      service_account_role_arn = module.ebs_csi_irsa.iam_role_arn
    }
  }
  
  # Node groups для mesh network
  eks_managed_node_groups = {
    # Control plane nodes (SPIRE Server, critical services)
    mesh_control = {
      name            = "mesh-control"
      use_name_prefix = true
      
      instance_types = ["t3.medium"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 1
      max_size     = 3
      desired_size = var.environment == "production" ? 2 : 1
      
      labels = {
        "x0tta6bl4/node-type" = "control"
        "spire/trust-domain"  = "x0tta6bl4.local"
      }
      
      taints = []
      
      update_config = {
        max_unavailable_percentage = 33
      }
    }
    
    # Worker nodes (mesh data plane)
    mesh_workers = {
      name            = "mesh-workers"
      use_name_prefix = true
      
      instance_types = ["t3.large", "t3.xlarge"]
      capacity_type  = var.environment == "production" ? "ON_DEMAND" : "SPOT"
      
      min_size     = 2
      max_size     = 10
      desired_size = 3
      
      labels = {
        "x0tta6bl4/node-type" = "worker"
        "mesh/tier"           = "data-plane"
      }
      
      taints = []
      
      update_config = {
        max_unavailable_percentage = 50
      }
    }
    
    # Monitoring nodes (Prometheus, Grafana)
    mesh_monitoring = {
      name            = "mesh-monitoring"
      use_name_prefix = true
      
      instance_types = ["t3.xlarge"]
      capacity_type  = "ON_DEMAND"
      
      min_size     = 1
      max_size     = 3
      desired_size = var.environment == "production" ? 2 : 1
      
      labels = {
        "x0tta6bl4/node-type" = "monitoring"
        "prometheus/scrape"   = "true"
      }
      
      taints = [
        {
          key    = "monitoring"
          value  = "true"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }
  
  # Access entries (EKS 1.30+)
  access_entries = {
    admin = {
      kubernetes_groups = []
      principal_arn     = data.aws_caller_identity.current.arn
      
      policy_associations = {
        admin = {
          policy_arn = "arn:aws:eks::aws:cluster-access-policy/AmazonEKSClusterAdminPolicy"
          access_scope = {
            type = "cluster"
          }
        }
      }
    }
  }
  
  tags = local.tags
}

# IRSA for VPC CNI
module "vpc_cni_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"
  
  role_name_prefix      = "${local.cluster_name}-vpc-cni-"
  attach_vpc_cni_policy = true
  vpc_cni_enable_ipv4   = true
  
  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-node"]
    }
  }
  
  tags = local.tags
}

# IRSA for EBS CSI Driver
module "ebs_csi_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.0"
  
  role_name_prefix      = "${local.cluster_name}-ebs-csi-"
  attach_ebs_csi_policy = true
  
  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:ebs-csi-controller-sa"]
    }
  }
  
  tags = local.tags
}

# Security group для mesh communication
resource "aws_security_group" "mesh_nodes" {
  name        = "${local.cluster_name}-mesh-sg"
  description = "Security group for x0tta6bl4 mesh nodes"
  vpc_id      = module.vpc.vpc_id
  
  # Ingress: SPIRE Server gRPC (8081)
  ingress {
    description = "SPIRE Server API"
    from_port   = 8081
    to_port     = 8081
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  
  # Ingress: BATMAN-adv mesh (UDP 4305)
  ingress {
    description = "BATMAN-adv mesh traffic"
    from_port   = 4305
    to_port     = 4305
    protocol    = "udp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  
  # Ingress: Prometheus (9090)
  ingress {
    description = "Prometheus metrics"
    from_port   = 9090
    to_port     = 9090
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  
  # Ingress: Grafana (3000)
  ingress {
    description = "Grafana UI"
    from_port   = 3000
    to_port     = 3000
    protocol    = "tcp"
    cidr_blocks = module.vpc.private_subnets_cidr_blocks
  }
  
  # Egress: Allow all (Zero Trust handled at application layer)
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  
  tags = merge(local.tags, {
    Name = "${local.cluster_name}-mesh-sg"
  })
}

# CloudWatch Log Group для cluster logs
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.environment == "production" ? 90 : 30
  
  tags = local.tags
}
