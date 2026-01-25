# Модуль EKS для multi-region развертывания

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
  }
}

# Локальные значения
locals {
  cluster_name = "${var.cluster_name}-${var.environment}"
}

# IAM роль для EKS кластера
resource "aws_iam_role" "cluster" {
  name = "${local.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-cluster-role"
  })
}

# Политика для EKS кластера
resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster.id
}

resource "aws_iam_role_policy_attachment" "vpc_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.cluster.id
}

# IAM роль для node groups
resource "aws_iam_role" "node_group" {
  name = "${local.cluster_name}-node-group-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-node-group-role"
  })
}

# Политики для node groups
resource "aws_iam_role_policy_attachment" "node_group_policies" {
  for_each = toset([
    "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy",
    "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy",
    "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly",
    "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  ])

  policy_arn = each.value
  role       = aws_iam_role.node_group.id
}

# EKS кластер
resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  version  = var.cluster_version
  role_arn = aws_iam_role.cluster.arn

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = true
    endpoint_public_access  = false
    security_group_ids      = [aws_security_group.cluster.id]
  }

  encryption_config {
    provider {
      key_arn = var.kms_key_arn != "" ? var.kms_key_arn : null
    }
    resources = ["secrets"]
  }

  enabled_cluster_log_types = [
    "api",
    "audit",
    "authenticator",
    "controllerManager",
    "scheduler"
  ]

  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy_attachment.vpc_policy
  ]

  tags = merge(var.tags, {
    Name = local.cluster_name
  })
}

# Security Group для кластера
resource "aws_security_group" "cluster" {
  name_prefix = "${local.cluster_name}-cluster-"
  description = "Security group for EKS cluster"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow traffic from node groups"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  ingress {
    description = "Allow traffic from ALB"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["10.0.0.0/8"]
  }

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-cluster"
  })
}

# EKS Managed Node Groups
resource "aws_eks_node_group" "main" {
  for_each = var.eks_managed_node_groups

  cluster_name    = aws_eks_cluster.main.name
  node_group_name = each.value.name
  node_role_arn   = aws_iam_role.node_group.arn
  subnet_ids      = var.subnet_ids

  instance_types = each.value.instance_types
  capacity_type  = each.value.capacity_type != "" ? each.value.capacity_type : "ON_DEMAND"

  scaling_config {
    desired_size = each.value.desired_size
    min_size     = each.value.min_size
    max_size     = each.value.max_size
  }

  update_config {
    max_unavailable = 1
  }

  labels = each.value.labels

  dynamic "taints" {
    for_each = each.value.taints != null ? each.value.taints : {}
    content {
      key    = taints.value.key
      value  = taints.value.value
      effect = taints.value.effect
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.node_group_policies
  ]

  tags = each.value.tags
}

# OIDC провайдер для IRSA (IAM Roles for Service Accounts)
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-oidc"
  })
}

# IAM роль для кластерного автоскейлера
resource "aws_iam_role" "cluster_autoscaler" {
  name = "${local.cluster_name}-cluster-autoscaler"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.cluster.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:kube-system:cluster-autoscaler"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-cluster-autoscaler"
  })
}

resource "aws_iam_role_policy" "cluster_autoscaler" {
  name = "${local.cluster_name}-cluster-autoscaler-policy"
  role = aws_iam_role.cluster_autoscaler.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "autoscaling:DescribeAutoScalingGroups",
          "autoscaling:DescribeAutoScalingInstances",
          "autoscaling:DescribeLaunchConfigurations",
          "autoscaling:DescribeTags",
          "autoscaling:SetDesiredCapacity",
          "autoscaling:TerminateInstanceInAutoScalingGroup",
          "ec2:DescribeLaunchTemplateVersions"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# IAM роль для ALB Ingress Controller
resource "aws_iam_role" "alb_ingress" {
  name = "${local.cluster_name}-alb-ingress"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.cluster.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_eks_cluster.main.identity[0].oidc[0].issuer, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-load-balancer-controller"
          }
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-alb-ingress"
  })
}

resource "aws_iam_role_policy" "alb_ingress" {
  name = "${local.cluster_name}-alb-ingress-policy"
  role = aws_iam_role.alb_ingress.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "acm:DescribeCertificate",
          "acm:ListCertificates",
          "acm:GetCertificate"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "ec2:AuthorizeSecurityGroupIngress",
          "ec2:CreateSecurityGroup",
          "ec2:CreateTags",
          "ec2:DeleteTags",
          "ec2:DescribeAccountAttributes",
          "ec2:DescribeAddresses",
          "ec2:DescribeAvailabilityZones",
          "ec2:DescribeInternetGateways",
          "ec2:DescribeNetworkInterfaces",
          "ec2:DescribeSecurityGroups",
          "ec2:DescribeSubnets",
          "ec2:DescribeTags",
          "ec2:DescribeVpcPeeringConnections",
          "ec2:DescribeVpcs",
          "ec2:ModifySecurityGroupIngress",
          "ec2:ModifySecurityGroupRules",
          "ec2:RevokeSecurityGroupIngress"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "elasticloadbalancing:AddTags",
          "elasticloadbalancing:CreateListener",
          "elasticloadbalancing:CreateLoadBalancer",
          "elasticloadbalancing:CreateRule",
          "elasticloadbalancing:CreateTargetGroup",
          "elasticloadbalancing:DeleteListener",
          "elasticloadbalancing:DeleteLoadBalancer",
          "elasticloadbalancing:DeleteRule",
          "elasticloadbalancing:DeleteTargetGroup",
          "elasticloadbalancing:DescribeListeners",
          "elasticloadbalancing:DescribeLoadBalancers",
          "elasticloadbalancing:DescribeLoadBalancerAttributes",
          "elasticloadbalancing:DescribeRules",
          "elasticloadbalancing:DescribeSSLPolicies",
          "elasticloadbalancing:DescribeTags",
          "elasticloadbalancing:DescribeTargetGroups",
          "elasticloadbalancing:DescribeTargetGroupAttributes",
          "elasticloadbalancing:ModifyListener",
          "elasticloadbalancing:ModifyLoadBalancerAttributes",
          "elasticloadbalancing:ModifyRule",
          "elasticloadbalancing:ModifyTargetGroup",
          "elasticloadbalancing:ModifyTargetGroupAttributes",
          "elasticloadbalancing:RegisterTargets",
          "elasticloadbalancing:RemoveTags",
          "elasticloadbalancing:RemoveListener",
          "elasticloadbalancing:RemoveTargets",
          "elasticloadbalancing:SetIpAddressType",
          "elasticloadbalancing:SetSecurityGroups",
          "elasticloadbalancing:SetSubnets",
          "elasticloadbalancing:UpdateLoadBalancerAttributes"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "iam:CreateServiceLinkedRole",
          "iam:GetServerCertificate",
          "iam:ListServerCertificates"
        ]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action = [
          "waf-regional:GetWebACLForResource",
          "waf-regional:AssociateWebACL",
          "waf-regional:DisassociateWebACL",
          "wafv2:GetWebACLForResource",
          "wafv2:AssociateWebACL",
          "wafv2:DisassociateWebACL",
          "wafv2:GetWebACL"
        ]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# Outputs
output "cluster_name" {
  description = "Имя EKS кластера"
  value       = aws_eks_cluster.main.name
}

output "cluster_endpoint" {
  description = "Endpoint EKS кластера"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_certificate_authority_data" {
  description = "CA сертификат кластера"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "Security Group ID кластера"
  value       = aws_security_group.cluster.id
}

output "oidc_provider_arn" {
  description = "ARN OIDC провайдера"
  value       = aws_iam_openid_connect_provider.cluster.arn
}

output "cluster_autoscaler_role_arn" {
  description = "ARN роли для cluster autoscaler"
  value       = aws_iam_role.cluster_autoscaler.arn
}

output "alb_ingress_role_arn" {
  description = "ARN роли для ALB Ingress Controller"
  value       = aws_iam_role.alb_ingress.arn
}

output "node_group_arns" {
  description = "ARN всех node groups"
  value       = [for ng in aws_eks_node_group.main : ng.arn]
}

output "node_group_status" {
  description = "Статус node groups"
  value       = [for ng in aws_eks_node_group.main : ng.status]
}