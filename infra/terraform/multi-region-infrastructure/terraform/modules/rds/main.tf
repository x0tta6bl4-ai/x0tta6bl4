# Модуль RDS Aurora для multi-region развертывания

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Локальные значения
locals {
  cluster_identifier = "${var.identifier}-${var.environment}"
}

# Глобальный кластер (создается только в основном регионе)
resource "aws_rds_global_cluster" "main" {
  count = var.create_global_cluster ? 1 : 0

  global_cluster_identifier = "${var.identifier}-global"
  engine                   = var.engine
  engine_version          = var.engine_version
  database_name           = var.database_name

  deletion_protection = var.deletion_protection
  storage_encrypted   = var.storage_encrypted

  tags = merge(var.tags, {
    Name = "${var.identifier}-global"
  })
}

# Aurora кластер
resource "aws_rds_cluster" "main" {
  cluster_identifier = local.cluster_identifier

  # Глобальный кластер настройки
  global_cluster_identifier = var.global_cluster_identifier != "" ? var.global_cluster_identifier : (var.create_global_cluster ? aws_rds_global_cluster.main[0].id : null)

  engine         = var.engine
  engine_version = var.engine_version
  database_name  = var.database_name

  master_username = var.master_username
  master_password = var.manage_master_user_password ? random_password.db_password[0].result : var.master_password

  # Сетевые настройки
  vpc_security_group_ids   = [var.security_group_id]
  db_subnet_group_name     = var.db_subnet_group_name

  # Бэкап настройки
  backup_retention_period = var.backup_retention_period
  preferred_backup_window = var.backup_window
  preferred_maintenance_window = var.maintenance_window

  # Шифрование
  storage_encrypted = var.storage_encrypted
  kms_key_id       = var.kms_key_id

  # Логирование
  enabled_cloudwatch_logs_exports = var.enabled_cloudwatch_logs_exports

  # Производительность
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage

  # Защита от удаления
  deletion_protection = var.deletion_protection
  skip_final_snapshot = var.skip_final_snapshot

  # Мониторинг
  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = var.monitoring_role_arn != "" ? var.monitoring_role_arn : null

  # Автоматическое масштабирование
  auto_minor_version_upgrade = var.auto_minor_version_upgrade

  # Дополнительные настройки
  apply_immediately = var.apply_immediately

  depends_on = [
    aws_rds_global_cluster.main
  ]

  tags = merge(var.tags, {
    Name = local.cluster_identifier
  })
}

# Генерация пароля для базы данных
resource "random_password" "db_password" {
  count = var.manage_master_user_password ? 1 : 0

  length  = 32
  special = true
}

# Хранение пароля в Secrets Manager
resource "aws_secretsmanager_secret" "db_password" {
  count = var.manage_master_user_password ? 1 : 0

  name                    = "${local.cluster_identifier}-db-password"
  description             = "Database password for ${local.cluster_identifier}"
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = merge(var.tags, {
    Name = "${local.cluster_identifier}-db-password"
  })
}

resource "aws_secretsmanager_secret_version" "db_password" {
  count = var.manage_master_user_password ? 1 : 0

  secret_id = aws_secretsmanager_secret.db_password[0].id
  secret_string = jsonencode({
    username = var.master_username
    password = random_password.db_password[0].result
  })
}

# Cluster instances (для Aurora)
resource "aws_rds_cluster_instance" "main" {
  count = var.instance_count

  identifier         = "${local.cluster_identifier}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.main.id
  instance_class     = var.instance_class

  engine         = var.engine
  engine_version = var.engine_version

  # Мониторинг
  monitoring_interval = var.monitoring_interval
  monitoring_role_arn = var.monitoring_role_arn != "" ? var.monitoring_role_arn : null

  # Автоматическое масштабирование
  auto_minor_version_upgrade = var.auto_minor_version_upgrade

  # Дополнительные настройки
  apply_immediately = var.apply_immediately

  tags = merge(var.tags, {
    Name = "${local.cluster_identifier}-${count.index + 1}"
  })
}

# CloudWatch алермы для базы данных
resource "aws_cloudwatch_metric_alarm" "database_cpu_utilization" {
  alarm_name          = "${local.cluster_identifier}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors RDS CPU utilization"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.id
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "database_free_storage_space" {
  alarm_name          = "${local.cluster_identifier}-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000000000" # 2GB в байтах
  alarm_description   = "This metric monitors RDS free storage space"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.id
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "database_read_latency" {
  alarm_name          = "${local.cluster_identifier}-high-read-latency"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "ReadLatency"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "0.1" # 100ms
  alarm_description   = "This metric monitors RDS read latency"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.main.id
  }

  alarm_actions = var.alarm_actions

  tags = var.tags
}

# SNS тема для алертов базы данных
resource "aws_sns_topic" "db_alerts" {
  name = "${local.cluster_identifier}-alerts"

  kms_master_key_id = var.kms_key_id

  tags = merge(var.tags, {
    Name = "${local.cluster_identifier}-alerts"
  })
}

# Подписка на алерты
resource "aws_sns_topic_subscription" "db_alerts" {
  count = length(var.alert_emails)

  topic_arn = aws_sns_topic.db_alerts.arn
  protocol  = "email"
  endpoint  = var.alert_emails[count.index]
}

# Параметровая группа кластера
resource "aws_rds_cluster_parameter_group" "main" {
  family = "${var.engine}${replace(var.engine_version, ".", "")}"

  name = "${local.cluster_identifier}-params"

  parameter {
    name  = "character_set_server"
    value = "utf8mb4"
  }

  parameter {
    name  = "character_set_client"
    value = "utf8mb4"
  }

  parameter {
    name  = "collation_server"
    value = "utf8mb4_unicode_ci"
  }

  parameter {
    name  = "time_zone"
    value = "UTC"
  }

  parameter {
    name  = "slow_query_log"
    value = "1"
  }

  parameter {
    name  = "long_query_time"
    value = "2"
  }

  parameter {
    name  = "log_output"
    value = "FILE"
  }

  tags = merge(var.tags, {
    Name = "${local.cluster_identifier}-params"
  })
}

# Связывание параметровой группы с кластером
resource "aws_rds_cluster_parameter_group_attachment" "main" {
  cluster_id          = aws_rds_cluster.main.id
  parameter_group_name = aws_rds_cluster_parameter_group.main.name
}

# Outputs
output "cluster_identifier" {
  description = "Идентификатор кластера"
  value       = aws_rds_cluster.main.id
}

output "cluster_endpoint" {
  description = "Endpoint кластера"
  value       = aws_rds_cluster.main.endpoint
}

output "cluster_reader_endpoint" {
  description = "Reader endpoint кластера"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "cluster_port" {
  description = "Порт кластера"
  value       = aws_rds_cluster.main.port
}

output "cluster_master_username" {
  description = "Имя пользователя базы данных"
  value       = aws_rds_cluster.main.master_username
}

output "cluster_master_password_secret_arn" {
  description = "ARN секрета с паролем базы данных"
  value       = var.manage_master_user_password ? aws_secretsmanager_secret.db_password[0].arn : null
}

output "global_cluster_identifier" {
  description = "Идентификатор глобального кластера"
  value       = var.global_cluster_identifier != "" ? var.global_cluster_identifier : (var.create_global_cluster ? aws_rds_global_cluster.main[0].id : null)
}

output "sns_alerts_topic_arn" {
  description = "ARN SNS топика для алертов"
  value       = aws_sns_topic.db_alerts.arn
}

output "cluster_instances" {
  description = "Информация об инстансах кластера"
  value = {
    for instance in aws_rds_cluster_instance.main :
    instance.identifier => {
      id   = instance.id
      az   = instance.availability_zone
      type = instance.instance_class
    }
  }
}