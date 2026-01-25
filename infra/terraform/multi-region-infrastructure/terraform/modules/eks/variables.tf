# Переменные для модуля EKS

variable "cluster_name" {
  description = "Имя EKS кластера"
  type        = string
}

variable "environment" {
  description = "Среда развертывания"
  type        = string
  default     = "production"
}

variable "cluster_version" {
  description = "Версия Kubernetes"
  type        = string
  default     = "1.28"
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Список subnet ID для кластера"
  type        = list(string)
}

variable "kms_key_arn" {
  description = "ARN KMS ключа для шифрования секретов"
  type        = string
  default     = ""
}

variable "eks_managed_node_groups" {
  description = "Конфигурация managed node groups"
  type = map(object({
    name           = string
    instance_types = list(string)
    capacity_type  = string
    min_size       = number
    max_size       = number
    desired_size   = number
    labels         = map(string)
    taints         = map(object({
      key    = string
      value  = string
      effect = string
    }))
    tags = map(string)
  }))
}

variable "cluster_addons" {
  description = "Дополнения кластера"
  type = map(object({
    most_recent = bool
  }))
  default = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
  }
}

variable "tags" {
  description = "Теги для ресурсов"
  type        = map(string)
  default     = {}
}