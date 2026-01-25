# Модуль VPC для multi-region развертывания

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
  name = "${var.name}-${var.environment}"
}

# VPC
resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = merge(var.tags, {
    Name = local.name
  })
}

# Internet Gateway
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "${local.name}-igw"
  })
}

# Public Subnets
resource "aws_subnet" "public" {
  for_each = var.public_subnets

  vpc_id                  = aws_vpc.main.id
  cidr_block              = each.value.cidr
  availability_zone       = each.value.az
  map_public_ip_on_launch = true

  tags = merge(var.tags, {
    Name = "${local.name}-public-${each.key}"
    Type = "Public"
  })
}

# Private Subnets
resource "aws_subnet" "private" {
  for_each = var.private_subnets

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = merge(var.tags, {
    Name = "${local.name}-private-${each.key}"
    Type = "Private"
  })
}

# Database Subnets
resource "aws_subnet" "database" {
  for_each = var.database_subnets

  vpc_id            = aws_vpc.main.id
  cidr_block        = each.value.cidr
  availability_zone = each.value.az

  tags = merge(var.tags, {
    Name = "${local.name}-database-${each.key}"
    Type = "Database"
  })
}

# NAT Gateways
resource "aws_eip" "nat" {
  count = var.enable_nat_gateway ? length(var.availability_zones) : 0

  domain = "vpc"
  depends_on = [aws_internet_gateway.main]

  tags = merge(var.tags, {
    Name = "${local.name}-nat-${var.availability_zones[count.index]}"
  })
}

resource "aws_nat_gateway" "main" {
  count = var.enable_nat_gateway ? length(var.availability_zones) : 0

  allocation_id = aws_eip.nat[count.index].id
  subnet_id     = aws_subnet.public[var.availability_zones[count.index]].id
  depends_on    = [aws_internet_gateway.main]

  tags = merge(var.tags, {
    Name = "${local.name}-nat-${var.availability_zones[count.index]}"
  })
}

# Route Tables
resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(var.tags, {
    Name = "${local.name}-public"
  })
}

resource "aws_route_table" "private" {
  count = length(var.availability_zones)

  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [""] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.main[count.index].id
    }
  }

  tags = merge(var.tags, {
    Name = "${local.name}-private-${var.availability_zones[count.index]}"
  })
}

resource "aws_route_table" "database" {
  vpc_id = aws_vpc.main.id

  tags = merge(var.tags, {
    Name = "${local.name}-database"
  })
}

# Route Table Associations
resource "aws_route_table_association" "public" {
  for_each = var.public_subnets

  subnet_id      = aws_subnet.public[each.key].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  for_each = var.private_subnets

  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[index(keys(var.private_subnets), each.key)].id
}

resource "aws_route_table_association" "database" {
  for_each = var.database_subnets

  subnet_id      = aws_subnet.database[each.key].id
  route_table_id = aws_route_table.database.id
}

# Security Groups
resource "aws_security_group" "alb" {
  name_prefix = "${local.name}-alb-"
  description = "Security group for ALB"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "HTTPS"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${local.name}-alb"
  })
}

resource "aws_security_group" "eks" {
  name_prefix = "${local.name}-eks-"
  description = "Security group for EKS"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Allow all traffic from ALB"
    from_port       = 0
    to_port         = 0
    protocol        = "-1"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description = "Allow traffic between EKS nodes"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    self        = true
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${local.name}-eks"
  })
}

resource "aws_security_group" "rds" {
  name_prefix = "${local.name}-rds-"
  description = "Security group for RDS"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "MySQL from EKS"
    from_port       = 3306
    to_port         = 3306
    protocol        = "tcp"
    security_groups = [aws_security_group.eks.id]
  }

  tags = merge(var.tags, {
    Name = "${local.name}-rds"
  })
}

resource "aws_security_group" "redis" {
  name_prefix = "${local.name}-redis-"
  description = "Security group for Redis"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Redis from EKS"
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [aws_security_group.eks.id]
  }

  tags = merge(var.tags, {
    Name = "${local.name}-redis"
  })
}

# VPC Endpoints для AWS сервисов
resource "aws_vpc_endpoint" "s3" {
  vpc_id       = aws_vpc.main.id
  service_name = "com.amazonaws.${data.aws_region.current.name}.s3"

  tags = merge(var.tags, {
    Name = "${local.name}-s3-endpoint"
  })
}

resource "aws_vpc_endpoint" "dynamodb" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${data.aws_region.current.name}.dynamodb"
  vpc_endpoint_type   = "Gateway"
  route_table_ids     = [aws_route_table.private[0].id]

  tags = merge(var.tags, {
    Name = "${local.name}-dynamodb-endpoint"
  })
}

# DB Subnet Group
resource "aws_db_subnet_group" "main" {
  name       = "${local.name}-db"
  subnet_ids = [for subnet in aws_subnet.database : subnet.id]

  tags = merge(var.tags, {
    Name = "${local.name}-db"
  })
}

# Получение текущего региона
data "aws_region" "current" {}

# Outputs
output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "vpc_cidr_block" {
  description = "VPC CIDR блок"
  value       = aws_vpc.main.cidr_block
}

output "public_subnet_ids" {
  description = "Список публичных subnet ID"
  value       = [for subnet in aws_subnet.public : subnet.id]
}

output "private_subnet_ids" {
  description = "Список приватных subnet ID"
  value       = [for subnet in aws_subnet.private : subnet.id]
}

output "database_subnet_ids" {
  description = "Список database subnet ID"
  value       = [for subnet in aws_subnet.database : subnet.id]
}

output "database_subnet_group_name" {
  description = "Имя DB subnet group"
  value       = aws_db_subnet_group.main.name
}

output "alb_security_group_id" {
  description = "Security Group ID для ALB"
  value       = aws_security_group.alb.id
}

output "eks_security_group_id" {
  description = "Security Group ID для EKS"
  value       = aws_security_group.eks.id
}

output "rds_security_group_id" {
  description = "Security Group ID для RDS"
  value       = aws_security_group.rds.id
}

output "redis_security_group_id" {
  description = "Security Group ID для Redis"
  value       = aws_security_group.redis.id
}

output "internet_gateway_id" {
  description = "Internet Gateway ID"
  value       = aws_internet_gateway.main.id
}

output "nat_gateway_ids" {
  description = "Список NAT Gateway ID"
  value       = [for nat in aws_nat_gateway.main : nat.id]
}