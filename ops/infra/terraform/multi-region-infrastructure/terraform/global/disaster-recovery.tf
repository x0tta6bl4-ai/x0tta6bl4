# Disaster Recovery конфигурация для x0tta6bl4 multi-region инфраструктуры

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# План disaster recovery
resource "aws_fis_experiment_template" "x0tta6bl4_dr_plan" {
  provider = aws.us-east-1

  name        = "${var.project_name}-disaster-recovery-plan"
  description = "Disaster recovery experiment for ${var.project_name}"
  role_arn    = aws_iam_role.fis_experiment_role.arn

  stop_condition {
    source = "none"
  }

  action {
    name = "stop-us-east-1-cluster"
    action_id = "aws:eks:terminate-nodegroup"

    parameter {
      name  = "clusterIdentifier"
      value = data.terraform_remote_state.us_east_1.outputs.eks_cluster_name
    }

    parameter {
      name  = "nodegroupName"
      value = "${data.terraform_remote_state.us_east_1.outputs.eks_cluster_name}-main"
    }
  }

  action {
    name = "failover-to-eu-west-1"
    action_id = "aws:route53:update-record"

    parameter {
      name  = "hostedZoneId"
      value = data.aws_route53_zone.x0tta6bl4.zone_id
    }

    parameter {
      name  = "recordName"
      value = "api.${var.domain_name}"
    }

    parameter {
      name  = "recordType"
      value = "CNAME"
    }

    parameter {
      name  = "recordValue"
      value = data.terraform_remote_state.eu_west_1.outputs.load_balancer_dns_name
    }
  }

  target {
    name = "eks-cluster-us-east-1"
    resource_type = "aws:eks:nodegroup"

    selection_mode = "COUNT(1)"

    resource_arns = [
      "arn:aws:eks:us-east-1:${data.aws_caller_identity.current.account_id}:nodegroup/${data.terraform_remote_state.us_east_1.outputs.eks_cluster_name}/${data.terraform_remote_state.us_east_1.outputs.eks_cluster_name}-main/*"
    ]
  }

  target {
    name = "route53-record"
    resource_type = "aws:route53:hostedzone"

    selection_mode = "COUNT(1)"

    resource_arns = [
      data.aws_route53_zone.x0tta6bl4.arn
    ]
  }

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-plan"
  })
}

# IAM роль для FIS экспериментов
resource "aws_iam_role" "fis_experiment_role" {
  provider = aws.us-east-1

  name = "${var.project_name}-fis-experiment-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "fis.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-fis-experiment-role"
  })
}

resource "aws_iam_role_policy" "fis_experiment_policy" {
  provider = aws.us-east-1

  name = "${var.project_name}-fis-experiment-policy"
  role = aws_iam_role.fis_experiment_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "eks:DescribeNodegroup",
          "eks:TerminateNodegroup"
        ]
        Effect = "Allow"
        Resource = [
          "arn:aws:eks:us-east-1:${data.aws_caller_identity.current.account_id}:cluster/${data.terraform_remote_state.us_east_1.outputs.eks_cluster_name}",
          "arn:aws:eks:us-east-1:${data.aws_caller_identity.current.account_id}:nodegroup/${data.terraform_remote_state.us_east_1.outputs.eks_cluster_name}/*"
        ]
      },
      {
        Action = [
          "route53:GetHostedZone",
          "route53:ChangeResourceRecordSets",
          "route53:ListResourceRecordSets"
        ]
        Effect = "Allow"
        Resource = [
          data.aws_route53_zone.x0tta6bl4.arn
        ]
      }
    ]
  })
}

# Route53 hosted zone для disaster recovery
data "aws_route53_zone" "x0tta6bl4" {
  provider = aws.us-east-1

  name         = "${var.domain_name}."
  private_zone = false
}

# Health check для мониторинга состояния регионов
resource "aws_route53_health_check" "us_east_1" {
  provider = aws.us-east-1

  fqdn              = "us-east-1.${var.domain_name}"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = "3"
  request_interval  = "30"

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-us-east-1-health-check"
  })
}

resource "aws_route53_health_check" "eu_west_1" {
  provider = aws.us-east-1

  fqdn              = "eu-west-1.${var.domain_name}"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = "3"
  request_interval  = "30"

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-eu-west-1-health-check"
  })
}

resource "aws_route53_health_check" "ap_southeast_1" {
  provider = aws.us-east-1

  fqdn              = "ap-southeast-1.${var.domain_name}"
  port              = 443
  type              = "HTTPS"
  resource_path     = "/health"
  failure_threshold = "3"
  request_interval  = "30"

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-ap-southeast-1-health-check"
  })
}

# Failover записи для disaster recovery
resource "aws_route53_record" "api_failover" {
  provider = aws.us-east-1

  zone_id = data.aws_route53_zone.x0tta6bl4.zone_id
  name    = "api-failover.${var.domain_name}"
  type    = "CNAME"
  ttl     = "60"

  failover_routing_policy {
    type = "PRIMARY"

    set_identifier = "us-east-1-primary"

    health_check_id = aws_route53_health_check.us_east_1.id
  }

  set_identifier = "us-east-1-primary"
  records        = [data.terraform_remote_state.us_east_1.outputs.load_balancer_dns_name]
}

resource "aws_route53_record" "api_failover_secondary" {
  provider = aws.us-east-1

  zone_id = data.aws_route53_zone.x0tta6bl4.zone_id
  name    = "api-failover.${var.domain_name}"
  type    = "CNAME"
  ttl     = "60"

  failover_routing_policy {
    type = "SECONDARY"

    set_identifier = "eu-west-1-secondary"
  }

  set_identifier = "eu-west-1-secondary"
  records        = [data.terraform_remote_state.eu_west_1.outputs.load_balancer_dns_name]
}

# Геолокационные записи для распределения трафика
resource "aws_route53_record" "api_geolocation_us" {
  provider = aws.us-east-1

  zone_id = data.aws_route53_zone.x0tta6bl4.zone_id
  name    = "api.${var.domain_name}"
  type    = "CNAME"
  ttl     = "300"

  geolocation_routing_policy {
    country = "*"
    continent = "NA"
  }

  set_identifier = "us-east-1-na"
  records        = [data.terraform_remote_state.us_east_1.outputs.load_balancer_dns_name]
}

resource "aws_route53_record" "api_geolocation_eu" {
  provider = aws.us-east-1

  zone_id = data.aws_route53_zone.x0tta6bl4.zone_id
  name    = "api.${var.domain_name}"
  type    = "CNAME"
  ttl     = "300"

  geolocation_routing_policy {
    continent = "EU"
  }

  set_identifier = "eu-west-1-eu"
  records        = [data.terraform_remote_state.eu_west_1.outputs.load_balancer_dns_name]
}

resource "aws_route53_record" "api_geolocation_asia" {
  provider = aws.us-east-1

  zone_id = data.aws_route53_zone.x0tta6bl4.zone_id
  name    = "api.${var.domain_name}"
  type    = "CNAME"
  ttl     = "300"

  geolocation_routing_policy {
    continent = "AS"
  }

  set_identifier = "ap-southeast-1-asia"
  records        = [data.terraform_remote_state.ap_southeast_1.outputs.load_balancer_dns_name]
}

# Автоматическое резервное копирование критических ресурсов
resource "aws_backup_plan" "x0tta6bl4_dr_backup" {
  provider = aws.us-east-1

  name = "${var.project_name}-disaster-recovery-backup"

  rule {
    rule_name         = "daily-backup"
    target_vault_name = aws_backup_vault.x0tta6bl4_dr_vault.name
    schedule          = "cron(0 5 ? * * *)" # Ежедневно в 5:00 UTC

    lifecycle {
      delete_after = 30
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.x0tta6bl4_dr_replica_vault.arn

      lifecycle {
        delete_after = 90
      }
    }
  }

  rule {
    rule_name         = "weekly-backup"
    target_vault_name = aws_backup_vault.x0tta6bl4_dr_vault.name
    schedule          = "cron(0 6 ? * SUN *)" # Еженедельно в воскресенье

    lifecycle {
      delete_after = 90
    }

    copy_action {
      destination_vault_arn = aws_backup_vault.x0tta6bl4_dr_replica_vault.arn

      lifecycle {
        delete_after = 365
      }
    }
  }

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-backup-plan"
  })
}

# Backup vault для disaster recovery
resource "aws_backup_vault" "x0tta6bl4_dr_vault" {
  provider = aws.us-east-1

  name        = "${var.project_name}-dr-backup-vault"
  kms_key_arn = data.terraform_remote_state.global.outputs.kms_key_id
  encryption_key_arn = data.terraform_remote_state.global.outputs.kms_key_id

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-backup-vault"
  })
}

resource "aws_backup_vault" "x0tta6bl4_dr_replica_vault" {
  provider = aws.eu-west-1

  name        = "${var.project_name}-dr-backup-replica-vault"
  kms_key_arn = aws_kms_key.eu_west_1_backup_key.arn
  encryption_key_arn = aws_kms_key.eu_west_1_backup_key.arn

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-backup-replica-vault"
  })
}

# KMS ключ для шифрования бэкапов в eu-west-1
resource "aws_kms_key" "eu_west_1_backup_key" {
  provider = aws.eu-west-1

  description             = "KMS key for backup encryption in eu-west-1"
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
    Name = "${var.project_name}-eu-west-1-backup-key"
  })
}

# Backup selection для критических ресурсов
resource "aws_backup_selection" "x0tta6bl4_dr_resources" {
  provider = aws.us-east-1

  name         = "${var.project_name}-dr-backup-selection"
  plan_id      = aws_backup_plan.x0tta6bl4_dr_backup.id

  resources = [
    "arn:aws:rds:us-east-1:${data.aws_caller_identity.current.account_id}:cluster:${data.terraform_remote_state.global.outputs.primary_cluster_id}",
    "arn:aws:eks:us-east-1:${data.aws_caller_identity.current.account_id}:cluster/${data.terraform_remote_state.us_east_1.outputs.eks_cluster_name}",
    "arn:aws:elasticache:us-east-1:${data.aws_caller_identity.current.account_id}:cluster/${data.terraform_remote_state.us_east_1.outputs.elasticache_cluster_id}"
  ]

  conditions {
    string_equals {
      key   = "aws:ResourceTag/Environment"
      value = var.environment
    }
  }

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-backup-selection"
  })
}

# CloudFormation стек для автоматизированного восстановления
resource "aws_cloudformation_stack" "x0tta6bl4_dr_stack" {
  provider = aws.us-east-1

  name = "${var.project_name}-disaster-recovery-stack"

  template_body = jsonencode({
    AWSTemplateFormatVersion = "2010-09-09"
    Description = "Disaster recovery stack for ${var.project_name}"

    Resources = {
      DisasterRecoveryFunction = {
        Type = "AWS::Lambda::Function"
        Properties = {
          FunctionName = "${var.project_name}-dr-function"
          Runtime = "python3.9"
          Handler = "index.lambda_handler"
          Role = aws_iam_role.dr_lambda_role.arn
          Timeout = 900

          Code = {
            ZipFile = filebase64("${path.module}/dr_lambda_function.py")
          }

          Environment = {
            Variables = {
              PRIMARY_REGION = "us-east-1"
              FAILOVER_REGION = "eu-west-1"
              PROJECT_NAME = var.project_name
            }
          }
        }
      }

      DisasterRecoveryTrigger = {
        Type = "AWS::Events::Rule"
        Properties = {
          Name = "${var.project_name}-dr-trigger"
          Description = "Trigger disaster recovery procedures"
          State = "ENABLED"

          EventPattern = jsonencode({
            source = ["aws.health"]
            detail-type = ["AWS Health Event"]
            detail = {
              eventTypeCategory = ["scheduledChange"]
              eventStatusCode = ["upcoming"]
            }
          })

          Targets = [{
            Id = "1"
            Arn = aws_lambda_function.dr_function.arn
          }]
        }
      }

      DisasterRecoveryPermission = {
        Type = "AWS::Lambda::Permission"
        Properties = {
          FunctionName = aws_lambda_function.dr_function.arn
          Action = "lambda:InvokeFunction"
          Principal = "events.amazonaws.com"
          SourceArn = aws_cloudwatch_event_rule.dr_trigger.arn
        }
      }
    }
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-stack"
  })
}

# IAM роль для Lambda функции disaster recovery
resource "aws_iam_role" "dr_lambda_role" {
  provider = aws.us-east-1

  name = "${var.project_name}-dr-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "lambda.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.global_tags, {
    Name = "${var.project_name}-dr-lambda-role"
  })
}

resource "aws_iam_role_policy" "dr_lambda_policy" {
  provider = aws.us-east-1

  name = "${var.project_name}-dr-lambda-policy"
  role = aws_iam_role.dr_lambda_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents"
        ]
        Effect = "Allow"
        Resource = "arn:aws:logs:*:*:*"
      },
      {
        Action = [
          "route53:ChangeResourceRecordSets",
          "route53:GetHostedZone",
          "route53:ListResourceRecordSets"
        ]
        Effect = "Allow"
        Resource = data.aws_route53_zone.x0tta6bl4.arn
      },
      {
        Action = [
          "sns:Publish"
        ]
        Effect = "Allow"
        Resource = data.terraform_remote_state.global.outputs.sns_alerts_topic_arn
      }
    ]
  })
}

# Получение текущего аккаунта AWS
data "aws_caller_identity" "current" {}

# Outputs
output "disaster_recovery_plan_id" {
  description = "ID плана disaster recovery"
  value       = aws_fis_experiment_template.x0tta6bl4_dr_plan.id
}

output "backup_plan_id" {
  description = "ID плана резервного копирования"
  value       = aws_backup_plan.x0tta6bl4_dr_backup.id
}

output "backup_vault_arn" {
  description = "ARN backup vault"
  value       = aws_backup_vault.x0tta6bl4_dr_vault.arn
}

output "replica_backup_vault_arn" {
  description = "ARN реплика backup vault"
  value       = aws_backup_vault.x0tta6bl4_dr_replica_vault.arn
}

output "cloudformation_stack_id" {
  description = "ID CloudFormation стека для disaster recovery"
  value       = aws_cloudformation_stack.x0tta6bl4_dr_stack.id
}

output "lambda_function_arn" {
  description = "ARN Lambda функции для disaster recovery"
  value       = aws_lambda_function.dr_function.arn
}