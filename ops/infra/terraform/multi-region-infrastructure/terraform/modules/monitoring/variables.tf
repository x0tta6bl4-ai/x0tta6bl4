# Переменные для модуля мониторинга

variable "project_name" {
  description = "Название проекта"
  type        = string
}

variable "environment" {
  description = "Среда развертывания"
  type        = string
  default     = "production"
}

variable "region" {
  description = "AWS регион"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID"
  type        = string
}

variable "subnet_ids" {
  description = "Список subnet ID"
  type        = list(string)
}

variable "eks_cluster_name" {
  description = "Имя EKS кластера"
  type        = string
}

variable "eks_cluster_endpoint" {
  description = "Endpoint EKS кластера"
  type        = string
}

variable "eks_cluster_ca_cert" {
  description = "CA сертификат EKS кластера"
  type        = string
}

variable "rds_instance_id" {
  description = "ID инстанса RDS"
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Домен проекта"
  type        = string
  default     = "x0tta6bl4.com"
}

variable "log_retention_days" {
  description = "Срок хранения логов в днях"
  type        = number
  default     = 30
}

variable "kms_key_id" {
  description = "KMS ключ для шифрования"
  type        = string
  default     = ""
}

variable "alert_emails" {
  description = "Email адреса для алертов"
  type        = list(string)
  default     = []
}

variable "prometheus_retention_days" {
  description = "Срок хранения метрик в Prometheus в днях"
  type        = number
  default     = 90
}

variable "tags" {
  description = "Теги для ресурсов"
  type        = map(string)
  default     = {}
}