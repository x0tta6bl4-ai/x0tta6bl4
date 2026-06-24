# Переменные для глобальной Terraform конфигурации

variable "project_name" {
  description = "Название проекта"
  type        = string
  default     = "x0tta6bl4"
}

variable "environment" {
  description = "Среда развертывания (development, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be one of: development, staging, production."
  }
}

variable "cloudflare_api_token" {
  description = "Cloudflare API Token для управления DNS и глобальным load balancer'ом"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID для домена"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Основной домен проекта"
  type        = string
  default     = "x0tta6bl4.com"
}

variable "aws_account_id" {
  description = "AWS Account ID"
  type        = string
  sensitive   = true
}

variable "global_tags" {
  description = "Глобальные теги для всех ресурсов"
  type        = map(string)
  default = {
    Project     = "x0tta6bl4"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Настройки мониторинга
variable "monitoring_config" {
  description = "Конфигурация глобального мониторинга"
  type = object({
    enable_cloudwatch_dashboard = bool
    enable_global_alerts        = bool
    alert_email_endpoints       = list(string)
    log_retention_days         = number
  })

  default = {
    enable_cloudwatch_dashboard = true
    enable_global_alerts        = true
    alert_email_endpoints       = ["alerts@x0tta6bl4.com"]
    log_retention_days         = 30
  }
}

# Настройки безопасности
variable "security_config" {
  description = "Конфигурация глобальной безопасности"
  type = object({
    enable_kms_encryption = bool
    enable_ssh_access     = bool
    allowed_ssh_cidrs     = list(string)
    enable_vpc_flow_logs  = bool
  })

  default = {
    enable_kms_encryption = true
    enable_ssh_access     = false
    allowed_ssh_cidrs     = ["10.0.0.0/8"]
    enable_vpc_flow_logs  = true
  }
}

# Настройки резервного копирования
variable "backup_config" {
  description = "Конфигурация резервного копирования"
  type = object({
    enable_cross_region_backup = bool
    backup_retention_days      = number
    backup_window             = string
    enable_encryption         = bool
  })

  default = {
    enable_cross_region_backup = true
    backup_retention_days      = 30
    backup_window             = "03:00-04:00"
    enable_encryption         = true
  }
}

# Настройки сети
variable "network_config" {
  description = "Глобальная конфигурация сети"
  type = object({
    enable_transit_gateway = bool
    enable_vpc_peering     = bool
    dns_domain_name       = string
  })

  default = {
    enable_transit_gateway = true
    enable_vpc_peering     = false
    dns_domain_name       = "x0tta6bl4.internal"
  }
}