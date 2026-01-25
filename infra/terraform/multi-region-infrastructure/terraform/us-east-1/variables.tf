# Переменные для региона us-east-1

variable "project_name" {
  description = "Название проекта"
  type        = string
  default     = "x0tta6bl4"
}

variable "environment" {
  description = "Среда развертывания"
  type        = string
  default     = "production"
}

variable "global_tags" {
  description = "Глобальные теги"
  type        = map(string)
  default = {
    Project     = "x0tta6bl4"
    Environment = "production"
    ManagedBy   = "terraform"
  }
}

# Региональные настройки
variable "regional_config" {
  description = "Конфигурация для региона us-east-1"
  type = object({
    primary_az = string
    secondary_az = string
    instance_types = object({
      eks = string
      rds = string
    })
  })

  default = {
    primary_az = "us-east-1a"
    secondary_az = "us-east-1b"
    instance_types = {
      eks = "t3.medium"
      rds = "db.t3.medium"
    }
  }
}

# Конфигурация сети
variable "network_config" {
  description = "Сетевая конфигурация"
  type = object({
    vpc_cidr = string
    public_subnets = map(object({
      cidr = string
      az   = string
    }))
    private_subnets = map(object({
      cidr = string
      az   = string
    }))
    database_subnets = map(object({
      cidr = string
      az   = string
    }))
  })

  default = {
    vpc_cidr = "10.10.0.0/16"
    public_subnets = {
      "us-east-1a" = { cidr = "10.10.1.0/24", az = "us-east-1a" }
      "us-east-1b" = { cidr = "10.10.2.0/24", az = "us-east-1b" }
      "us-east-1c" = { cidr = "10.10.3.0/24", az = "us-east-1c" }
    }
    private_subnets = {
      "us-east-1a" = { cidr = "10.10.10.0/24", az = "us-east-1a" }
      "us-east-1b" = { cidr = "10.10.11.0/24", az = "us-east-1b" }
      "us-east-1c" = { cidr = "10.10.12.0/24", az = "us-east-1c" }
    }
    database_subnets = {
      "us-east-1a" = { cidr = "10.10.20.0/24", az = "us-east-1a" }
      "us-east-1b" = { cidr = "10.10.21.0/24", az = "us-east-1b" }
      "us-east-1c" = { cidr = "10.10.22.0/24", az = "us-east-1c" }
    }
  }
}

# Конфигурация EKS
variable "eks_config" {
  description = "Конфигурация EKS кластера"
  type = object({
    cluster_version = string
    node_groups = map(object({
      instance_types = list(string)
      min_size       = number
      max_size       = number
      desired_size   = number
    }))
  })

  default = {
    cluster_version = "1.28"
    node_groups = {
      main = {
        instance_types = ["t3.medium"]
        min_size       = 2
        max_size       = 10
        desired_size   = 3
      }
      application = {
        instance_types = ["t3.medium"]
        min_size       = 1
        max_size       = 5
        desired_size   = 2
      }
    }
  }
}

# Конфигурация RDS
variable "rds_config" {
  description = "Конфигурация RDS базы данных"
  type = object({
    engine_version      = string
    instance_class      = string
    allocated_storage   = number
    database_name       = string
    backup_retention_period = number
    enable_multi_az     = bool
  })

  default = {
    engine_version      = "8.0.mysql_aurora.3.04.0"
    instance_class      = "db.t3.medium"
    allocated_storage   = 20
    database_name       = "x0tta6bl4"
    backup_retention_period = 30
    enable_multi_az     = true
  }
}

# Конфигурация ElastiCache
variable "elasticache_config" {
  description = "Конфигурация ElastiCache Redis"
  type = object({
    engine_version       = string
    node_type           = string
    num_cache_nodes     = number
    parameter_group_name = string
  })

  default = {
    engine_version       = "7.0"
    node_type           = "cache.t3.medium"
    num_cache_nodes     = 2
    parameter_group_name = "default.redis7"
  }
}

# Конфигурация мониторинга
variable "monitoring_config" {
  description = "Конфигурация мониторинга"
  type = object({
    enable_prometheus = bool
    enable_grafana    = bool
    retention_days    = number
  })

  default = {
    enable_prometheus = true
    enable_grafana    = true
    retention_days    = 30
  }
}

# Конфигурация резервного копирования
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