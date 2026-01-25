# Модуль мониторинга для multi-region развертывания

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.0"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.0"
    }
  }
}

# Локальные значения
locals {
  name = "${var.project_name}-${var.environment}-${var.region}"
}

# Amazon Managed Prometheus workspace
resource "aws_prometheus_workspace" "main" {
  alias = local.name

  tags = merge(var.tags, {
    Name = local.name
  })
}

# Amazon Managed Grafana workspace
resource "aws_grafana_workspace" "main" {
  name                     = local.name
  account_access_type      = "CURRENT_ACCOUNT"
  authentication_providers = ["AWS_SSO"]
  permission_type         = "SERVICE_MANAGED"
  data_sources            = ["PROMETHEUS", "CLOUDWATCH", "XRAY"]

  configuration = jsonencode({
    unifiedAlerting = {
      enabled = true
    }
    plugins = {
      pluginAdminEnabled = true
    }
  })

  tags = merge(var.tags, {
    Name = local.name
  })
}

# IAM роль для Prometheus
resource "aws_iam_role" "prometheus" {
  name = "${local.name}-prometheus"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "prometheus.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.name}-prometheus"
  })
}

resource "aws_iam_role_policy_attachment" "prometheus" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonPrometheusFullAccess"
  role       = aws_iam_role.prometheus.id
}

# IAM роль для Grafana
resource "aws_iam_role" "grafana" {
  name = "${local.name}-grafana"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "grafana.amazonaws.com"
        }
      }
    ]
  })

  tags = merge(var.tags, {
    Name = "${local.name}-grafana"
  })
}

resource "aws_iam_role_policy_attachment" "grafana" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonGrafanaCloudWatchAccess"
  role       = aws_iam_role.grafana.id
}

# CloudWatch Log Group для приложений
resource "aws_cloudwatch_log_group" "application" {
  name              = "/${var.project_name}/${var.environment}/${var.region}/application"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_id

  tags = merge(var.tags, {
    Name = "${local.name}-application"
  })
}

# CloudWatch Log Group для инфраструктуры
resource "aws_cloudwatch_log_group" "infrastructure" {
  name              = "/${var.project_name}/${var.environment}/${var.region}/infrastructure"
  retention_in_days = var.log_retention_days
  kms_key_id        = var.kms_key_id

  tags = merge(var.tags, {
    Name = "${local.name}-infrastructure"
  })
}

# SNS тема для алертов мониторинга
resource "aws_sns_topic" "monitoring_alerts" {
  name = "${local.name}-monitoring-alerts"

  kms_master_key_id = var.kms_key_id

  tags = merge(var.tags, {
    Name = "${local.name}-monitoring-alerts"
  })
}

# Подписки на алерты
resource "aws_sns_topic_subscription" "monitoring_alerts" {
  for_each = toset(var.alert_emails)

  topic_arn = aws_sns_topic.monitoring_alerts.arn
  protocol  = "email"
  endpoint  = each.value
}

# CloudWatch алермы для инфраструктуры
resource "aws_cloudwatch_metric_alarm" "cpu_utilization" {
  alarm_name          = "${local.name}-high-cpu"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "CPUUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "80"
  alarm_description   = "This metric monitors EC2 CPU utilization"

  alarm_actions = [aws_sns_topic.monitoring_alerts.arn]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "memory_utilization" {
  alarm_name          = "${local.name}-high-memory"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "MemoryUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "85"
  alarm_description   = "This metric monitors EC2 memory utilization"

  alarm_actions = [aws_sns_topic.monitoring_alerts.arn]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "disk_utilization" {
  alarm_name          = "${local.name}-high-disk"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "1"
  metric_name         = "DiskSpaceUtilization"
  namespace           = "AWS/EC2"
  period              = "300"
  statistic           = "Average"
  threshold           = "90"
  alarm_description   = "This metric monitors EC2 disk utilization"

  alarm_actions = [aws_sns_topic.monitoring_alerts.arn]

  tags = var.tags
}

# Prometheus правило записи для кастомных метрик
resource "aws_prometheus_rule_group_namespace" "main" {
  name      = local.name
  workspace_id = aws_prometheus_workspace.main.id

  data = jsonencode({
    groups = [
      {
        name = "x0tta6bl4-metrics"
        rules = [
          {
            record = "x0tta6bl4:requests:rate5m"
            expr   = "rate(x0tta6bl4_requests_total[5m])"
          },
          {
            record = "x0tta6bl4:latency:p95"
            expr   = "histogram_quantile(0.95, rate(x0tta6bl4_request_duration_seconds_bucket[5m]))"
          }
        ]
      }
    ]
  })
}

# Kubernetes провайдер для развертывания мониторинга
provider "kubernetes" {
  alias = "eks"

  host                   = var.eks_cluster_endpoint
  cluster_ca_certificate = base64decode(var.eks_cluster_ca_cert)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", var.eks_cluster_name, "--region", var.region]
  }
}

# Namespace для мониторинга
resource "kubernetes_namespace" "monitoring" {
  provider = kubernetes.eks

  metadata {
    name = "monitoring"
    labels = {
      name = "monitoring"
    }
  }
}

# Prometheus оператор через Helm
resource "helm_release" "prometheus_operator" {
  provider = kubernetes.eks

  name       = "prometheus-operator"
  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "kube-prometheus-stack"
  namespace  = kubernetes_namespace.monitoring.metadata[0].name
  version    = "45.0.0"

  values = [
    yamlencode({
      prometheus = {
        prometheusSpec = {
          serviceAccountName = "prometheus"
          serviceMonitorSelectorNilUsesHelmValues = false
          ruleSelectorNilUsesHelmValues = false
          podMonitorSelectorNilUsesHelmValues = false
          retention = "${var.prometheus_retention_days}d"
          storageSpec = {
            volumeClaimTemplate = {
              spec = {
                storageClassName = "gp3"
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "50Gi"
                  }
                }
              }
            }
          }
          remoteWrite = [
            {
              url = "https://aps-workspaces.${var.region}.amazonaws.com/workspaces/${aws_prometheus_workspace.main.id}/api/v1/remote_write"
              queue_config = {
                max_samples_per_send = 1000
                max_shards = 200
                capacity = 2500
              }
              sigv4 = {
                region = var.region
              }
            }
          ]
        }
      }

      grafana = {
        adminPassword = random_password.grafana_password.result
        persistence = {
          enabled = true
          storageClassName = "gp3"
          accessModes = ["ReadWriteOnce"]
          size = "10Gi"
        }
        grafana.ini = {
          server = {
            root_url = "https://grafana.${var.region}.${var.domain_name}"
          }
        }
      }

      alertmanager = {
        alertmanagerSpec = {
          storage = {
            volumeClaimTemplate = {
              spec = {
                storageClassName = "gp3"
                accessModes = ["ReadWriteOnce"]
                resources = {
                  requests = {
                    storage = "10Gi"
                  }
                }
              }
            }
          }
        }
      }
    })
  ]

  depends_on = [
    kubernetes_namespace.monitoring
  ]
}

# Пароль для Grafana
resource "random_password" "grafana_password" {
  length  = 16
  special = true
}

# Secret для Grafana пароля
resource "aws_secretsmanager_secret" "grafana_password" {
  name                    = "${local.name}-grafana-password"
  description             = "Grafana admin password"
  recovery_window_in_days = var.environment == "production" ? 30 : 0

  tags = merge(var.tags, {
    Name = "${local.name}-grafana-password"
  })
}

resource "aws_secretsmanager_secret_version" "grafana_password" {
  secret_id = aws_secretsmanager_secret.grafana_password.id
  secret_string = jsonencode({
    password = random_password.grafana_password.result
  })
}

# Service Monitor для RDS
resource "kubernetes_manifest" "rds_service_monitor" {
  provider = kubernetes.eks

  manifest = {
    apiVersion = "monitoring.coreos.com/v1"
    kind       = "ServiceMonitor"
    metadata = {
      name      = "rds-service-monitor"
      namespace = kubernetes_namespace.monitoring.metadata[0].name
      labels = {
        name = "rds-service-monitor"
      }
    }
    spec = {
      selector = {
        matchLabels = {
          "app.kubernetes.io/name" = "rds-exporter"
        }
      }
      endpoints = [
        {
          port     = "metrics"
          interval = "30s"
          path     = "/metrics"
        }
      ]
    }
  }

  depends_on = [
    helm_release.prometheus_operator
  ]
}

# Outputs
output "prometheus_workspace_id" {
  description = "Amazon Managed Prometheus workspace ID"
  value       = aws_prometheus_workspace.main.id
}

output "prometheus_workspace_endpoint" {
  description = "Amazon Managed Prometheus workspace endpoint"
  value       = aws_prometheus_workspace.main.prometheus_endpoint
}

output "grafana_workspace_id" {
  description = "Amazon Managed Grafana workspace ID"
  value       = aws_grafana_workspace.main.id
}

output "grafana_workspace_endpoint" {
  description = "Amazon Managed Grafana workspace endpoint"
  value       = aws_grafana_workspace.main.endpoint
}

output "grafana_admin_password_secret_arn" {
  description = "ARN секрета с паролем Grafana"
  value       = aws_secretsmanager_secret.grafana_password.arn
}

output "monitoring_alerts_topic_arn" {
  description = "ARN SNS топика для алертов мониторинга"
  value       = aws_sns_topic.monitoring_alerts.arn
}

output "cloudwatch_log_group_application" {
  description = "CloudWatch Log Group для приложений"
  value       = aws_cloudwatch_log_group.application.name
}

output "cloudwatch_log_group_infrastructure" {
  description = "CloudWatch Log Group для инфраструктуры"
  value       = aws_cloudwatch_log_group.infrastructure.name
}