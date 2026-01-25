# SECURITY FIXES - PART 2: IAM, SECURITY GROUPS, RDS ENCRYPTION
# These configurations implement fixes for issues #5, #6, #4, #7, #8

# =============================================================================
# IAM ROLES WITH LEAST PRIVILEGE (Issue #5)
# =============================================================================

# Create this file: infra/terraform/aws/iam-secure.tf

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

# EKS Cluster IAM Role
resource "aws_iam_role" "eks_cluster" {
  name = "x0tta6bl4-eks-cluster-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "x0tta6bl4-eks-cluster-role"
  }
}

# Attach required policies
resource "aws_iam_role_policy_attachment" "eks_cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.eks_cluster.name
}

resource "aws_iam_role_policy_attachment" "eks_vpc_resource_controller" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSVPCResourceController"
  role       = aws_iam_role.eks_cluster.name
}

# EKS Node IAM Role
resource "aws_iam_role" "eks_node" {
  name = "x0tta6bl4-eks-node-role"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })
  
  tags = {
    Name = "x0tta6bl4-eks-node-role"
  }
}

# Attach base policies
resource "aws_iam_role_policy_attachment" "eks_node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.eks_node.name
}

resource "aws_iam_role_policy_attachment" "eks_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.eks_node.name
}

resource "aws_iam_role_policy_attachment" "eks_registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.eks_node.name
}

# SSM access for node troubleshooting (restricted)
resource "aws_iam_role_policy_attachment" "eks_ssm_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
  role       = aws_iam_role.eks_node.name
}

# CloudWatch Container Insights
resource "aws_iam_role_policy_attachment" "eks_cloudwatch_policy" {
  policy_arn = "arn:aws:iam::aws:policy/CloudWatchAgentServerPolicy"
  role       = aws_iam_role.eks_node.name
}

# Custom policy for x0tta6bl4 application
resource "aws_iam_role_policy" "x0tta6bl4_app" {
  name = "x0tta6bl4-app-policy"
  role = aws_iam_role.eks_node.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # S3 access for data only (not state bucket)
        Sid    = "S3DataAccess"
        Effect = "Allow"
        Action = [
          "s3:GetObject",
          "s3:PutObject",
          "s3:DeleteObject"
        ]
        Resource = "arn:aws:s3:::x0tta6bl4-data-${var.environment}/*"
      },
      {
        # Secrets Manager access
        Sid    = "SecretsManagerAccess"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:DescribeSecret"
        ]
        Resource = "arn:aws:secretsmanager:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:secret:x0tta6bl4/*"
      },
      {
        # KMS decrypt (not key management)
        Sid    = "KMSDecrypt"
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:DescribeKey"
        ]
        Resource = [
          "arn:aws:kms:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:key/*"
        ]
        Condition = {
          StringEquals = {
            "kms:ViaService" = [
              "s3.${data.aws_region.current.name}.amazonaws.com",
              "secretsmanager.${data.aws_region.current.name}.amazonaws.com"
            ]
          }
        }
      }
    ]
  })
}

# RDS Monitoring IAM Role
resource "aws_iam_role" "rds_monitoring" {
  name = "x0tta6bl4-rds-monitoring"
  
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
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
  role       = aws_iam_role.rds_monitoring.name
}

# VPC Flow Logs IAM Role
resource "aws_iam_role" "vpc_flow_logs" {
  name = "x0tta6bl4-vpc-flow-logs"
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "vpc-flow-logs.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "vpc_flow_logs" {
  name = "vpc-flow-logs-policy"
  role = aws_iam_role.vpc_flow_logs.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Effect   = "Allow"
        Resource = "arn:aws:logs:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:log-group:/aws/vpc/flow-logs:*"
      }
    ]
  })
}

# =============================================================================
# SECURITY GROUPS (Issue #6)
# =============================================================================

# Create this file: infra/terraform/aws/security-groups-secure.tf

# Get VPC
data "aws_vpc" "main" {
  filter {
    name   = "tag:Name"
    values = ["x0tta6bl4-vpc"]
  }
}

# ALB Security Group
resource "aws_security_group" "alb" {
  name_prefix = "x0tta6bl4-alb-"
  description = "Security group for Application Load Balancer"
  vpc_id      = data.aws_vpc.main.id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "x0tta6bl4-alb"
  }
}

# ALB Ingress - HTTP (redirect to HTTPS)
resource "aws_vpc_security_group_ingress_rule" "alb_http" {
  security_group_id = aws_security_group.alb.id
  
  from_port   = 80
  to_port     = 80
  ip_protocol = "tcp"
  cidr_ipv4   = "0.0.0.0/0"
  
  tags = {
    Name = "alb-http"
  }
}

# ALB Ingress - HTTPS
resource "aws_vpc_security_group_ingress_rule" "alb_https" {
  security_group_id = aws_security_group.alb.id
  
  from_port   = 443
  to_port     = 443
  ip_protocol = "tcp"
  cidr_ipv4   = "0.0.0.0/0"
  
  tags = {
    Name = "alb-https"
  }
}

# ALB Egress - All traffic (needed for backend communication)
resource "aws_vpc_security_group_egress_rule" "alb_all" {
  security_group_id = aws_security_group.alb.id
  
  from_port   = 0
  to_port     = 65535
  ip_protocol = "tcp"
  cidr_ipv4   = "0.0.0.0/0"
  
  tags = {
    Name = "alb-egress"
  }
}

# EKS Nodes Security Group
resource "aws_security_group" "eks_nodes" {
  name_prefix = "x0tta6bl4-eks-"
  description = "Security group for EKS nodes"
  vpc_id      = data.aws_vpc.main.id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "x0tta6bl4-eks-nodes"
  }
}

# EKS Ingress from ALB
resource "aws_vpc_security_group_ingress_rule" "eks_from_alb" {
  security_group_id = aws_security_group.eks_nodes.id
  
  from_port                    = 443
  to_port                      = 443
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.alb.id
  
  tags = {
    Name = "from-alb-https"
  }
}

# EKS Node-to-Node communication
resource "aws_vpc_security_group_ingress_rule" "eks_node_to_node" {
  security_group_id = aws_security_group.eks_nodes.id
  
  from_port                    = 1025
  to_port                      = 65535
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks_nodes.id
  
  tags = {
    Name = "node-to-node"
  }
}

# EKS Kubelet API
resource "aws_vpc_security_group_ingress_rule" "eks_kubelet" {
  security_group_id = aws_security_group.eks_nodes.id
  
  from_port                    = 10250
  to_port                      = 10250
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks_nodes.id
  
  tags = {
    Name = "kubelet-api"
  }
}

# EKS Egress - All traffic
resource "aws_vpc_security_group_egress_rule" "eks_all" {
  security_group_id = aws_security_group.eks_nodes.id
  
  from_port   = 0
  to_port     = 65535
  ip_protocol = "-1"
  cidr_ipv4   = "0.0.0.0/0"
  
  tags = {
    Name = "all-egress"
  }
}

# RDS Security Group
resource "aws_security_group" "rds" {
  name_prefix = "x0tta6bl4-rds-"
  description = "Security group for RDS database"
  vpc_id      = data.aws_vpc.main.id
  
  lifecycle {
    create_before_destroy = true
  }
  
  tags = {
    Name = "x0tta6bl4-rds"
  }
}

# RDS Ingress from EKS
resource "aws_vpc_security_group_ingress_rule" "rds_from_eks" {
  security_group_id = aws_security_group.rds.id
  
  from_port                    = 3306
  to_port                      = 3306
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks_nodes.id
  
  tags = {
    Name = "from-eks"
  }
}

# Redis Security Group (if used)
resource "aws_security_group" "redis" {
  name_prefix = "x0tta6bl4-redis-"
  description = "Security group for Redis cache"
  vpc_id      = data.aws_vpc.main.id
  
  tags = {
    Name = "x0tta6bl4-redis"
  }
}

resource "aws_vpc_security_group_ingress_rule" "redis_from_eks" {
  security_group_id = aws_security_group.redis.id
  
  from_port                    = 6379
  to_port                      = 6379
  ip_protocol                  = "tcp"
  referenced_security_group_id = aws_security_group.eks_nodes.id
  
  tags = {
    Name = "from-eks"
  }
}

# =============================================================================
# RDS ENCRYPTION (Issue #4, #7, #8)
# =============================================================================

# Create this file: infra/terraform/aws/rds-secure.tf

resource "aws_kms_key" "rds" {
  description             = "KMS key for RDS encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  
  tags = {
    Name = "x0tta6bl4-rds"
  }
}

# RDS Cluster with encryption
resource "aws_rds_cluster" "x0tta6bl4" {
  cluster_identifier = "x0tta6bl4-${var.environment}"
  
  engine         = "aurora-mysql"
  engine_version = "8.0.mysql_aurora.3.02.0"
  database_name  = "x0tta6bl4"
  
  # ✅ Use managed password
  master_username = "admin"
  manage_master_user_password = true  # Auto-generate via Secrets Manager
  
  # ✅ Network config
  vpc_security_group_ids = [aws_security_group.rds.id]
  db_subnet_group_name   = aws_db_subnet_group.main.name
  
  # ✅ Encryption at rest
  storage_encrypted = true
  kms_key_id       = aws_kms_key.rds.arn
  
  # ✅ Backup encryption (inherited from cluster encryption)
  backup_retention_period = var.environment == "production" ? 30 : 7
  preferred_backup_window = "03:00-04:00"
  preferred_maintenance_window = "mon:04:00-mon:05:00"
  
  # ✅ Enable CloudWatch logs
  enabled_cloudwatch_logs_exports = [
    "error",
    "general",
    "slowquery",
    "audit"
  ]
  
  # ✅ Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn
  
  # ✅ Performance Insights
  performance_insights_enabled    = true
  performance_insights_kms_key_id = aws_kms_key.rds.arn
  
  # ✅ Deletion protection for production
  deletion_protection = var.environment == "production"
  skip_final_snapshot = false
  final_snapshot_identifier = "x0tta6bl4-${var.environment}-final-snapshot-${formatdate("YYYY-MM-DD-hhmm", timestamp())}"
  
  # ✅ Backup encryption (via KMS)
  copy_tags_to_snapshot = true
  
  tags = {
    Name = "x0tta6bl4-${var.environment}"
  }
}

# RDS Cluster instances
resource "aws_rds_cluster_instance" "x0tta6bl4" {
  count = var.rds_instance_count
  
  identifier         = "x0tta6bl4-${var.environment}-${count.index + 1}"
  cluster_identifier = aws_rds_cluster.x0tta6bl4.id
  instance_class     = "db.t3.small"
  
  engine         = aws_rds_cluster.x0tta6bl4.engine
  engine_version = aws_rds_cluster.x0tta6bl4.engine_version
  
  # ✅ Monitoring
  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn
  
  # ✅ Auto upgrade
  auto_minor_version_upgrade = true
  
  tags = {
    Name = "x0tta6bl4-${var.environment}-${count.index + 1}"
  }
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "x0tta6bl4-${var.environment}"
  subnet_ids = data.aws_subnets.private.ids
  
  tags = {
    Name = "x0tta6bl4-${var.environment}"
  }
}

data "aws_subnets" "private" {
  filter {
    name   = "tag:kubernetes.io/role/internal-elb"
    values = ["1"]
  }
}

# =============================================================================
# MONITORING & LOGGING (Issue #8, #9, #10)
# =============================================================================

# Create this file: infra/terraform/aws/monitoring-secure.tf

# CloudWatch Log Group for EKS (encrypted)
resource "aws_cloudwatch_log_group" "eks" {
  name              = "/aws/eks/x0tta6bl4"
  retention_in_days = 30
  kms_key_id       = aws_kms_key.cloudwatch_logs.arn
  
  tags = {
    Name = "eks-logs"
  }
}

# KMS key for CloudWatch Logs
resource "aws_kms_key" "cloudwatch_logs" {
  description             = "KMS key for CloudWatch Logs encryption"
  deletion_window_in_days = 10
  enable_key_rotation     = true
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs"
        Effect = "Allow"
        Principal = {
          Service = "logs.${data.aws_region.current.name}.amazonaws.com"
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = "*"
      }
    ]
  })
}

# VPC Flow Logs
resource "aws_flow_log" "main" {
  iam_role_arn    = aws_iam_role.vpc_flow_logs.arn
  log_destination = "${aws_cloudwatch_log_group.vpc_flow_logs.arn}:*"
  traffic_type    = "ALL"
  vpc_id          = data.aws_vpc.main.id
  
  tags = {
    Name = "vpc-flow-logs"
  }
}

resource "aws_cloudwatch_log_group" "vpc_flow_logs" {
  name              = "/aws/vpc/flow-logs"
  retention_in_days = 7
  kms_key_id       = aws_kms_key.cloudwatch_logs.arn
}

# CloudTrail for API auditing
resource "aws_cloudtrail" "main" {
  name                          = "x0tta6bl4-audit"
  s3_bucket_name               = aws_s3_bucket.cloudtrail_logs.id
  include_global_service_events = true
  is_multi_region_trail        = true
  enable_log_file_validation   = true
  depends_on                   = [aws_s3_bucket_policy.cloudtrail]
  
  tags = {
    Name = "x0tta6bl4-audit"
  }
}

resource "aws_s3_bucket" "cloudtrail_logs" {
  bucket = "x0tta6bl4-cloudtrail-logs"
}

resource "aws_s3_bucket_versioning" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "cloudtrail_logs" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_policy" "cloudtrail" {
  bucket = aws_s3_bucket.cloudtrail_logs.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AWSCloudTrailAclCheck"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:GetBucketAcl"
        Resource = aws_s3_bucket.cloudtrail_logs.arn
      },
      {
        Sid    = "AWSCloudTrailWrite"
        Effect = "Allow"
        Principal = {
          Service = "cloudtrail.amazonaws.com"
        }
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.cloudtrail_logs.arn}/*"
        Condition = {
          StringEquals = {
            "s3:x-amz-acl" = "bucket-owner-full-control"
          }
        }
      }
    ]
  })
}
