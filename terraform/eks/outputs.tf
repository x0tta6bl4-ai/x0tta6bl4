# terraform/eks/outputs.tf
# x0tta6bl4 EKS Outputs

output "cluster_name" {
  description = "EKS cluster name"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS cluster endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = module.eks.cluster_security_group_id
}

output "cluster_arn" {
  description = "EKS cluster ARN"
  value       = module.eks.cluster_arn
}

output "cluster_oidc_issuer_url" {
  description = "OIDC issuer URL for IRSA"
  value       = module.eks.cluster_oidc_issuer_url
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data for cluster auth"
  value       = module.eks.cluster_certificate_authority_data
  sensitive   = true
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnets" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnets
}

output "mesh_security_group_id" {
  description = "Security group ID for mesh communication"
  value       = aws_security_group.mesh_nodes.id
}

# Helper commands
output "kubeconfig_command" {
  description = "Command to update kubeconfig"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "grafana_port_forward" {
  description = "Command to port-forward Grafana"
  value       = "kubectl -n monitoring port-forward svc/prometheus-grafana 3000:80"
}

output "cluster_info" {
  description = "Cluster information summary"
  value = {
    name        = module.eks.cluster_name
    region      = var.aws_region
    environment = var.environment
    version     = var.cluster_version
    node_groups = keys(module.eks.eks_managed_node_groups)
  }
}
