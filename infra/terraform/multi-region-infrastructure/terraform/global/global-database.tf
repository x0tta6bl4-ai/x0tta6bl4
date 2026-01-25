# Глобальная база данных Aurora с кросс-региональной репликацией

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# Глобальный кластер Aurora (создается в основном регионе)
resource "aws_rds_global_cluster" "x0tta6bl4_global" {
  provider = aws.us-east-1

  global_cluster_identifier = "${var.project_name}-global"
  engine                   = "aurora-mysql"
  engine_version          = "8.0.mysql_aurora.3.04.0"
  database_name           = var.database_name

  deletion_protection = var.environment == "production"
  storage_encrypted   = true

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-global-cluster"
  })
}

# Основной кластер в us-east-1
resource "aws_rds_cluster" "x0tta6bl4_primary" {
  provider = aws.us-east-1

  cluster_identifier = "${var.project_name}-us-east-1"

  global_cluster_identifier = aws_rds_global_cluster.x0tta6bl4_global.id
  engine                   = "aurora-mysql"
  engine_version          = "8.0.mysql_aurora.3.04.0"
  database_name           = var.database_name

  master_username = var.db_master_username
  master_password = random_password.global_db_password.result

  # Сетевые настройки
  vpc_security_group_ids   = [data.terraform_remote_state.us_east_1.outputs.rds_security_group_id]
  db_subnet_group_name     = data.terraform_remote_state.us_east_1.outputs.database_subnet_group_name

  # Бэкап настройки
  backup_retention_period = var.backup_retention_period
  preferred_backup_window = var.backup_window
  preferred_maintenance_window = var.maintenance_window

  # Шифрование
  storage_encrypted = true
  kms_key_id       = data.terraform_remote_state.global.outputs.kms_key_id

  # Логирование
  enabled_cloudwatch_logs_exports = ["audit", "error", "general", "slowquery"]

  # Производительность
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage

  # Защита от удаления
  deletion_protection = var.environment == "production"
  skip_final_snapshot = var.environment != "production"

  # Мониторинг
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring.arn

  # Автоматическое масштабирование
  auto_minor_version_upgrade = true

  # Дополнительные настройки
  apply_immediately = var.apply_immediately

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-us-east-1-primary"
  })
}

# Реплика в eu-west-1
resource "aws_rds_cluster" "x0tta6bl4_eu_west_1_replica" {
  provider = aws.eu-west-1

  cluster_identifier = "${var.project_name}-eu-west-1"

  global_cluster_identifier = aws_rds_global_cluster.x0tta6bl4_global.id
  engine                   = "aurora-mysql"
  engine_version          = "8.0.mysql_aurora.3.04.0"

  # Сетевые настройки
  vpc_security_group_ids   = [data.terraform_remote_state.eu_west_1.outputs.rds_security_group_id]
  db_subnet_group_name     = data.terraform_remote_state.eu_west_1.outputs.database_subnet_group_name

  # Бэкап настройки
  backup_retention_period = var.backup_retention_period
  preferred_backup_window = var.backup_window
  preferred_maintenance_window = var.maintenance_window

  # Шифрование
  storage_encrypted = true
  kms_key_id       = aws_kms_key.eu_west_1_db_key.arn

  # Логирование
  enabled_cloudwatch_logs_exports = ["audit", "error", "general", "slowquery"]

  # Производительность
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage

  # Защита от удаления
  deletion_protection = var.environment == "production"
  skip_final_snapshot = var.environment != "production"

  # Мониторинг
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring_eu_west_1.arn

  # Автоматическое масштабирование
  auto_minor_version_upgrade = true

  # Дополнительные настройки
  apply_immediately = var.apply_immediately

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-eu-west-1-replica"
  })
}

# Реплика в ap-southeast-1
resource "aws_rds_cluster" "x0tta6bl4_ap_southeast_1_replica" {
  provider = aws.ap-southeast-1

  cluster_identifier = "${var.project_name}-ap-southeast-1"

  global_cluster_identifier = aws_rds_global_cluster.x0tta6bl4_global.id
  engine                   = "aurora-mysql"
  engine_version          = "8.0.mysql_aurora.3.04.0"

  # Сетевые настройки
  vpc_security_group_ids   = [data.terraform_remote_state.ap_southeast_1.outputs.rds_security_group_id]
  db_subnet_group_name     = data.terraform_remote_state.ap_southeast_1.outputs.database_subnet_group_name

  # Бэкап настройки
  backup_retention_period = var.backup_retention_period
  preferred_backup_window = var.backup_window
  preferred_maintenance_window = var.maintenance_window

  # Шифрование
  storage_encrypted = true
  kms_key_id       = aws_kms_key.ap_southeast_1_db_key.arn

  # Логирование
  enabled_cloudwatch_logs_exports = ["audit", "error", "general", "slowquery"]

  # Производительность
  allocated_storage     = var.allocated_storage
  max_allocated_storage = var.max_allocated_storage

  # Защита от удаления
  deletion_protection = var.environment == "production"
  skip_final_snapshot = var.environment != "production"

  # Мониторинг
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_enhanced_monitoring_ap_southeast_1.arn

  # Автоматическое масштабирование
  auto_minor_version_upgrade = true

  # Дополнительные настройки
  apply_immediately = var.apply_immediately

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-ap-southeast-1-replica"
  })
}

# Генерация пароля для глобальной базы данных
resource "random_password" "global_db_password" {
  length  = 32
  special = true
}

# Хранение пароля в AWS Secrets Manager
resource "aws_secretsmanager_secret" "global_db_password" {
  provider = aws.us-east-1

  name                    = "${var.project_name}-global-db-password"
  description             = "Global database password for ${var.project_name}"
  recovery_window_in_days = var.environment == "production" ? 30 : 0
  kms_key_id             = data.terraform_remote_state.global.outputs.kms_key_id

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-global-db-password"
  })
}

resource "aws_secretsmanager_secret_version" "global_db_password" {
  provider = aws.us-east-1

  secret_id = aws_secretsmanager_secret.global_db_password.id
  secret_string = jsonencode({
    username = var.db_master_username
    password = random_password.global_db_password.result
  })
}

# KMS ключи для шифрования в каждом регионе
resource "aws_kms_key" "eu_west_1_db_key" {
  provider = aws.eu-west-1

  description             = "KMS key for database encryption in eu-west-1"
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-eu-west-1-db-key"
  })
}

resource "aws_kms_key" "ap_southeast_1_db_key" {
  provider = aws.ap-southeast-1

  description             = "KMS key for database encryption in ap-southeast-1"
  deletion_window_in_days = 30

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-ap-southeast-1-db-key"
  })
}

# IAM роли для enhanced monitoring в каждом регионе
resource "aws_iam_role" "rds_enhanced_monitoring" {
  provider = aws.us-east-1

  name = "${var.project_name}-rds-enhanced-monitoring"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-rds-enhanced-monitoring"
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring" {
  provider = aws.us-east-1

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  role       = aws_iam_role.rds_enhanced_monitoring.name
}

resource "aws_iam_role" "rds_enhanced_monitoring_eu_west_1" {
  provider = aws.eu-west-1

  name = "${var.project_name}-rds-enhanced-monitoring-eu-west-1"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-rds-enhanced-monitoring-eu-west-1"
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring_eu_west_1" {
  provider = aws.eu-west-1

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  role       = aws_iam_role.rds_enhanced_monitoring_eu_west_1.name
}

resource "aws_iam_role" "rds_enhanced_monitoring_ap_southeast_1" {
  provider = aws.ap-southeast-1

  name = "${var.project_name}-rds-enhanced-monitoring-ap-southeast-1"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "monitoring.rds.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-rds-enhanced-monitoring-ap-southeast-1"
  })
}

resource "aws_iam_role_policy_attachment" "rds_enhanced_monitoring_ap_southeast_1" {
  provider = aws.ap-southeast-1

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  role       = aws_iam_role.rds_enhanced_monitoring_ap_southeast_1.name
}

# Глобальный мониторинг базы данных
resource "aws_cloudwatch_metric_alarm" "global_db_cpu_utilization" {
  provider = aws.us-east-1

  alarm_name          = "${var.project_name}-global-db-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors global database CPU utilization"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.x0tta6bl4_primary.id
  }

  alarm_actions = [data.terraform_remote_state.global.outputs.sns_alerts_topic_arn]

  tags = var.global_tags
}

resource "aws_cloudwatch_metric_alarm" "global_db_free_storage_space" {
  provider = aws.us-east-1

  alarm_name          = "${var.project_name}-global-db-low-storage"
  comparison_operator = "LessThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "FreeStorageSpace"
  namespace           = "AWS/RDS"
  period              = "300"
  statistic           = "Average"
  threshold           = "2000000000" # 2GB в байтах
  alarm_description   = "This metric monitors global database free storage space"

  dimensions = {
    DBClusterIdentifier = aws_rds_cluster.x0tta6bl4_primary.id
  }

  alarm_actions = [data.terraform_remote_state.global.outputs.sns_alerts_topic_arn]

  tags = var.global_tags
}

# Кросс-региональная репликация S3 для бэкапов
resource "aws_s3_bucket" "global_db_backups" {
  provider = aws.us-east-1

  bucket = "${var.project_name}-global-db-backups"

  lifecycle {
    prevent_destroy = true
  }

  tags = var.global_tags
}

resource "aws_s3_bucket_versioning" "global_db_backups" {
  provider = aws.us-east-1

  bucket = aws_s3_bucket.global_db_backups.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_replication_configuration" "global_db_backups" {
  provider = aws.us-east-1

  bucket = aws_s3_bucket.global_db_backups.id

  role = aws_iam_role.s3_replication.arn

  rule {
    id     = "cross-region-replication"
    status = "Enabled"

    destination {
      bucket = aws_s3_bucket.global_db_backups_replica.arn
    }

    filter {}

    delete_marker_replication {
      status = "Enabled"
    }
  }
}

resource "aws_s3_bucket" "global_db_backups_replica" {
  provider = aws.eu-west-1

  bucket = "${var.project_name}-global-db-backups-replica"

  lifecycle {
    prevent_destroy = true
  }

  tags = var.global_tags
}

resource "aws_iam_role" "s3_replication" {
  provider = aws.us-east-1

  name = "${var.project_name}-s3-replication"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "s3.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-s3-replication"
  })
}

resource "aws_iam_role_policy" "s3_replication" {
  provider = aws.us-east-1

  name = "${var.project_name}-s3-replication-policy"
  role = aws_iam_role.s3_replication.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket"
        ]
        Effect = "Allow"
        Resource = [
          aws_s3_bucket.global_db_backups.arn,
          aws_s3_bucket.global_db_backups_replica.arn
        ]
      },
      {
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging"
        ]
        Effect = "Allow"
        Resource = [
          "${aws_s3_bucket.global_db_backups.arn}/*",
          "${aws_s3_bucket.global_db_backups_replica.arn}/*"
        ]
      },
      {
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags"
        ]
        Effect = "Allow"
        Resource = [
          "${aws_s3_bucket.global_db_backups.arn}/*",
          "${aws_s3_bucket.global_db_backups_replica.arn}/*"
        ]
      }
    ]
  })
}

# Получение текущего аккаунта AWS
data "aws_caller_identity" "current" {}

# Outputs
output "global_cluster_id" {
  description = "ID глобального кластера"
  value       = aws_rds_global_cluster.x0tta6bl4_global.id
}

output "primary_cluster_endpoint" {
  description = "Endpoint основного кластера"
  value       = aws_rds_cluster.x0tta6bl4_primary.endpoint
}

output "eu_west_1_replica_endpoint" {
  description = "Endpoint реплики в eu-west-1"
  value       = aws_rds_cluster.x0tta6bl4_eu_west_1_replica.endpoint
}

output "ap_southeast_1_replica_endpoint" {
  description = "Endpoint реплики в ap-southeast-1"
  value       = aws_rds_cluster.x0tta6bl4_ap_southeast_1_replica.endpoint
}

output "global_db_password_secret_arn" {
  description = "ARN секрета с паролем глобальной базы данных"
  value       = aws_secretsmanager_secret.global_db_password.arn
}

output "backup_bucket_arn" {
  description = "ARN S3 bucket для бэкапов"
  value       = aws_s3_bucket.global_db_backups.arn
}

output "replica_bucket_arn" {
  description = "ARN реплика S3 bucket для бэкапов"
  value       = aws_s3_bucket.global_db_backups_replica.arn
}