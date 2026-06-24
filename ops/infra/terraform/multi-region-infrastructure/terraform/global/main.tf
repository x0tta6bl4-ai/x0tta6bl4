# Глобальная Terraform конфигурация для x0tta6bl4
# Управляет глобальными ресурсами AWS

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    cloudflare = {
      source  = "cloudflare/cloudflare"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket         = "x0tta6bl4-terraform-state"
    key            = "global/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "x0tta6bl4-terraform-locks"
  }
}

# Провайдеры
provider "aws" {
  region = "us-east-1" # Основной регион для глобальных ресурсов
}

provider "cloudflare" {
  api_token = var.cloudflare_api_token
}

# Глобальные переменные
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

variable "cloudflare_api_token" {
  description = "Cloudflare API Token"
  type        = string
  sensitive   = true
}

variable "cloudflare_zone_id" {
  description = "Cloudflare Zone ID"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Основной домен"
  type        = string
  default     = "x0tta6bl4.com"
}

# Локальные значения
locals {
  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "terraform"
  }
}

# S3 bucket для хранения terraform state
resource "aws_s3_bucket" "terraform_state" {
  bucket = "${var.project_name}-terraform-state"

  lifecycle {
    prevent_destroy = true
  }

  tags = local.common_tags
}

resource "aws_s3_bucket_versioning" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "terraform_state" {
  bucket = aws_s3_bucket.terraform_state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

# DynamoDB таблица для блокировок
resource "aws_dynamodb_table" "terraform_locks" {
  name         = "${var.project_name}-terraform-locks"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "LockID"

  attribute {
    name = "LockID"
    type = "S"
  }

  tags = local.common_tags
}

# Глобальные IAM роли и политики
resource "aws_iam_role" "global_admin_role" {
  name = "${var.project_name}-global-admin-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Condition = {
          StringEquals = {
            "aws:PrincipalAccount" = data.aws_caller_identity.current.account_id
          }
        }
      }
    ]
  })

  tags = local.common_tags
}

# Политика для глобального администратора
resource "aws_iam_role_policy" "global_admin_policy" {
  name = "${var.project_name}-global-admin-policy"
  role = aws_iam_role.global_admin_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          aws_s3_bucket.terraform_state.arn,
          "${aws_s3_bucket.terraform_state.arn}/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:DeleteItem"
        ]
        Resource = aws_dynamodb_table.terraform_locks.arn
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

# Глобальный KMS ключ для шифрования
resource "aws_kms_key" "global_key" {
  description             = "KMS key for ${var.project_name} global resources"
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
      },
      {
        Effect = "Allow"
        Principal = {
          AWS = aws_iam_role.global_admin_role.arn
        }
        Action = [
          "kms:Decrypt",
          "kms:Encrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })

  tags = local.common_tags
}

resource "aws_kms_alias" "global_key_alias" {
  name          = "alias/${var.project_name}-global-key"
  target_key_id = aws_kms_key.global_key.key_id
}

# Глобальные security groups (используются во всех регионах)
resource "aws_security_group" "global_ssh" {
  provider = aws.us-east-1

  name_prefix = "${var.project_name}-global-ssh"
  description = "Global SSH access for ${var.project_name}"

  ingress {
    description = "SSH from trusted networks"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = ["10.0.0.0/8"] # Только из внутренних сетей
  }

  tags = local.common_tags
}

# Глобальный мониторинг дашборд
resource "aws_cloudwatch_dashboard" "global_dashboard" {
  dashboard_name = "${var.project_name}-global-dashboard"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6

        properties = {
          metrics = [
            ["AWS/EC2", "CPUUtilization", "InstanceType", "t3.medium"],
            [".", ".", ".", "t3.large"],
            [".", ".", ".", "t3.xlarge"]
          ]
          view    = "timeSeries"
          stacked = false
          region  = "us-east-1"
          title   = "Global EC2 CPU Utilization"
          period  = 300
        }
      },
      {
        type   = "log"
        x      = 12
        y      = 0
        width  = 12
        height = 6

        properties = {
          query = "SOURCE '${aws_cloudwatch_log_group.global_logs.name}' | fields @timestamp, @message | sort @timestamp desc | limit 100"
          region = "us-east-1"
          title  = "Global Application Logs"
        }
      }
    ]
  })
}

# Глобальная группа логов
resource "aws_cloudwatch_log_group" "global_logs" {
  name              = "/${var.project_name}/global"
  retention_in_days = 30
  kms_key_id        = aws_kms_key.global_key.arn

  tags = local.common_tags
}

# Глобальные алерты
resource "aws_cloudwatch_metric_alarm" "global_cpu_alarm" {
  alarm_name          = "${var.project_name}-global-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EC2 CPU utilization across all regions"
  alarm_actions       = [aws_sns_topic.global_alerts.arn]

  dimensions = {
    InstanceType = "*"
  }

  tags = local.common_tags
}

# SNS тема для глобальных алертов
resource "aws_sns_topic" "global_alerts" {
  name = "${var.project_name}-global-alerts"

  kms_master_key_id = aws_kms_key.global_key.alias

  tags = local.common_tags
}

resource "aws_sns_topic_subscription" "global_alerts_email" {
  topic_arn = aws_sns_topic.global_alerts.arn
  protocol  = "email"
  endpoint  = "alerts@${var.domain_name}"
}

# Получение текущего аккаунта AWS
data "aws_caller_identity" "current" {}

# Outputs
output "terraform_state_bucket" {
  description = "S3 bucket для хранения terraform state"
  value       = aws_s3_bucket.terraform_state.id
}

output "dynamodb_locks_table" {
  description = "DynamoDB таблица для блокировок"
  value       = aws_dynamodb_table.terraform_locks.id
}

output "kms_key_id" {
  description = "KMS ключ для шифрования"
  value       = aws_kms_key.global_key.id
}

output "global_admin_role_arn" {
  description = "ARN глобальной IAM роли"
  value       = aws_iam_role.global_admin_role.arn
}

output "sns_alerts_topic_arn" {
  description = "ARN SNS топика для алертов"
  value       = aws_sns_topic.global_alerts.arn
}