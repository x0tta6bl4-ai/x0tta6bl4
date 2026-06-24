# terraform/eks/variables.tf
# x0tta6bl4 EKS Variables

variable "aws_region" {
  description = "AWS region for deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name (dev, staging, production)"
  type        = string
  default     = "staging"
  
  validation {
    condition     = contains(["dev", "staging", "production"], var.environment)
    error_message = "Environment must be dev, staging, or production."
  }
}

variable "vpc_cidr" {
  description = "VPC CIDR block"
  type        = string
  default     = "10.0.0.0/16"
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access EKS API"
  type        = list(string)
  default     = ["0.0.0.0/0"]
  # ⚠️ SECURITY: Restrict to office/VPN IPs in production!
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.30"
  
  validation {
    condition     = can(regex("^1\\.(2[89]|30|31)$", var.cluster_version))
    error_message = "Cluster version must be 1.28, 1.29, 1.30, or 1.31."
  }
}

variable "enable_karpenter" {
  description = "Enable Karpenter for node autoscaling"
  type        = bool
  default     = false
}

variable "monitoring_retention_days" {
  description = "Prometheus data retention in days"
  type        = number
  default     = 30
  
  validation {
    condition     = var.monitoring_retention_days >= 7 && var.monitoring_retention_days <= 365
    error_message = "Retention must be between 7 and 365 days."
  }
}
