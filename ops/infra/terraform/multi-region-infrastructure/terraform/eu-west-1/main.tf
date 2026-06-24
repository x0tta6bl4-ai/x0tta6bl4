# Terraform конфигурация для региона eu-west-1 (Европа)
# Основной дата-центр: Ирландия

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "s3" {
    bucket         = "x0tta6bl4-terraform-state"
    key            = "eu-west-1/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "x0tta6bl4-terraform-locks"
  }
}

# Провайдер
provider "aws" {
  region = "eu-west-1"

  default_tags {
    tags = var.global_tags
  }
}

# Локальные значения
locals {
  region_name = "eu-west-1"
  cluster_name = "${var.project_name}-${local.region_name}"
}

# Данные из глобальной конфигурации
data "terraform_remote_state" "global" {
  backend = "s3"

  config = {
    bucket = "x0tta6bl4-terraform-state"
    key    = "global/terraform.tfstate"
    region = "us-east-1"
  }
}

# Модуль VPC
module "vpc" {
  source = "../modules/vpc"

  name                 = "${var.project_name}-${local.region_name}"
  cidr_block          = "10.20.0.0/16"
  availability_zones  = ["eu-west-1a", "eu-west-1b", "eu-west-1c"]
  enable_nat_gateway  = true
  enable_vpn_gateway  = false

  public_subnets = {
    "eu-west-1a" = { cidr = "10.20.1.0/24", az = "eu-west-1a" }
    "eu-west-1b" = { cidr = "10.20.2.0/24", az = "eu-west-1b" }
    "eu-west-1c" = { cidr = "10.20.3.0/24", az = "eu-west-1c" }
  }

  private_subnets = {
    "eu-west-1a" = { cidr = "10.20.10.0/24", az = "eu-west-1a" }
    "eu-west-1b" = { cidr = "10.20.11.0/24", az = "eu-west-1b" }
    "eu-west-1c" = { cidr = "10.20.12.0/24", az = "eu-west-1c" }
  }

  database_subnets = {
    "eu-west-1a" = { cidr = "10.20.20.0/24", az = "eu-west-1a" }
    "eu-west-1b" = { cidr = "10.20.21.0/24", az = "eu-west-1b" }
    "eu-west-1c" = { cidr = "10.20.22.0/24", az = "eu-west-1c" }
  }

  tags = var.global_tags
}

# Модуль EKS кластера
module "eks" {
  source = "../modules/eks"

  cluster_name    = local.cluster_name
  cluster_version = "1.28"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids

  eks_managed_node_groups = {
    main = {
      name           = "${local.cluster_name}-main"
      instance_types = [var.regional_config.eu_west_1.instance_types.eks]
      min_size       = 2
      max_size       = 10
      desired_size   = 3

      labels = {
        Environment = var.environment
        Region      = local.region_name
      }

      tags = var.global_tags
    }

    application = {
      name           = "${local.cluster_name}-app"
      instance_types = [var.regional_config.eu_west_1.instance_types.eks]
      min_size       = 1
      max_size       = 5
      desired_size   = 2

      labels = {
        Environment = var.environment
        Region      = local.region_name
        NodeType    = "application"
      }

      taints = {
        dedicated = {
          key    = "dedicated"
          value  = "application"
          effect = "NO_SCHEDULE"
        }
      }

      tags = var.global_tags
    }
  }

  cluster_addons = {
    coredns = {
      most_recent = true
    }
    kube-proxy = {
      most_recent = true
    }
    vpc-cni = {
      most_recent = true
    }
    aws-ebs-csi-driver = {
      most_recent = true
    }
  }

  tags = var.global_tags
}

# Модуль RDS Aurora (реплика глобальной базы данных)
module "rds" {
  source = "../modules/rds"

  identifier = "${var.project_name}-${local.region_name}"

  engine         = "aurora-mysql"
  engine_version = "8.0.mysql_aurora.3.04.0"
  instance_class = var.regional_config.eu_west_1.instance_types.rds

  vpc_id               = module.vpc.vpc_id
  db_subnet_group_name = module.vpc.database_subnet_group_name

  # Реплика глобальной базы данных
  global_cluster_identifier = "${var.project_name}-global"

  allocated_storage     = 20
  max_allocated_storage = 1000

  database_name = "x0tta6bl4"
  master_username = "admin"
  manage_master_user_password = true

  backup_retention_period = var.backup_config.backup_retention_days
  backup_window          = var.backup_config.backup_window
  maintenance_window     = "sun:04:00-sun:05:00"

  deletion_protection = var.environment == "production"
  skip_final_snapshot = var.environment != "production"

  enabled_cloudwatch_logs_exports = ["audit", "error", "general", "slowquery"]

  tags = var.global_tags
}

# Модуль ElastiCache Redis
module "elasticache" {
  source = "../modules/elasticache"

  cluster_id           = "${var.project_name}-${local.region_name}"
  engine_version       = "7.0"
  node_type           = "cache.t3.medium"
  num_cache_nodes     = 2
  parameter_group_name = "default.redis7"

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids

  availability_zones = ["eu-west-1a", "eu-west-1b"]

  security_group_ids = [module.vpc.redis_security_group_id]

  maintenance_window = "sun:05:00-sun:06:00"

  snapshot_retention_period = var.backup_config.backup_retention_days
  snapshot_window          = "06:00-07:00"

  tags = var.global_tags
}

# Модуль мониторинга
module "monitoring" {
  source = "../modules/monitoring"

  project_name = var.project_name
  environment  = var.environment
  region       = local.region_name

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids

  eks_cluster_name       = module.eks.cluster_name
  eks_cluster_endpoint   = module.eks.cluster_endpoint
  eks_cluster_ca_cert    = module.eks.cluster_certificate_authority_data

  rds_instance_id = module.rds.cluster_identifier

  tags = var.global_tags
}

# Application Load Balancer для региона
resource "aws_lb" "regional" {
  name               = "${var.project_name}-${local.region_name}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.vpc.alb_security_group_id]
  subnets           = module.vpc.public_subnet_ids

  enable_deletion_protection = var.environment == "production"

  access_logs {
    bucket  = aws_s3_bucket.alb_logs.bucket
    prefix  = "alb-logs"
    enabled = true
  }

  tags = var.global_tags
}

# Target group для ALB
resource "aws_lb_target_group" "app" {
  name        = "${var.project_name}-${local.region_name}-app"
  port        = 80
  protocol    = "HTTP"
  vpc_id      = module.vpc.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 2
    timeout             = 5
    interval            = 30
    path                = "/health"
    matcher             = "200"
    port                = "traffic-port"
    protocol            = "HTTP"
  }

  stickiness {
    type            = "lb_cookie"
    cookie_duration = 1800
    enabled         = false
  }

  tags = var.global_tags
}

# Listener для ALB
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.regional.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# S3 bucket для ALB логов
resource "aws_s3_bucket" "alb_logs" {
  bucket = "${var.project_name}-alb-logs-${local.region_name}"

  lifecycle {
    prevent_destroy = true
  }

  tags = var.global_tags
}

resource "aws_s3_bucket_lifecycle_configuration" "alb_logs" {
  bucket = aws_s3_bucket.alb_logs.id

  rule {
    id     = "alb_logs_lifecycle"
    status = "Enabled"

    expiration {
      days = 90
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

# CloudWatch метрики для ALB
resource "aws_cloudwatch_metric_alarm" "alb_target_response_time" {
  alarm_name          = "${aws_lb.regional.name}-high-response-time"
  comparison_operator = "GreaterThanThreshold"
  evaluation_periods  = "2"
  metric_name         = "TargetResponseTime"
  namespace           = "AWS/ApplicationELB"
  period              = "300"
  statistic           = "Average"
  threshold           = "5"
  alarm_description   = "This metric monitors ALB target response time"

  dimensions = {
    LoadBalancer = aws_lb.regional.arn_suffix
  }

  alarm_actions = [data.terraform_remote_state.global.outputs.sns_alerts_topic_arn]

  tags = var.global_tags
}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "EKS кластер имя"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "EKS кластер endpoint"
  value       = module.eks.cluster_endpoint
}

output "rds_cluster_endpoint" {
  description = "RDS кластер endpoint"
  value       = module.rds.cluster_endpoint
}

output "elasticache_cluster_endpoint" {
  description = "ElastiCache кластер endpoint"
  value       = module.elasticache.cluster_address
}

output "load_balancer_dns_name" {
  description = "DNS имя регионального load balancer'а"
  value       = aws_lb.regional.dns_name
}

output "monitoring_workspace_id" {
  description = "Amazon Managed Prometheus workspace ID"
  value       = module.monitoring.workspace_id
}