terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.region
}

resource "aws_vpc" "mesh" {
  cidr_block = var.vpc_cidr
  tags = { Name = "x0tta6bl4-mesh-vpc" }
}

resource "aws_subnet" "mesh_a" {
  vpc_id                  = aws_vpc.mesh.id
  cidr_block              = var.subnet_cidr_a
  availability_zone       = var.az_a
  map_public_ip_on_launch = true
  tags = { Name = "x0tta6bl4-mesh-subnet-a" }
}

resource "aws_security_group" "mesh_nodes" {
  name        = "x0tta6bl4-mesh-nodes"
  description = "Security group for mesh EC2 nodes"
  vpc_id      = aws_vpc.mesh.id

  ingress {
    description = "Allow SSH"
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = [var.admin_cidr]
  }
  ingress {
    description = "Allow mesh UDP"
    from_port   = 7000
    to_port     = 7000
    protocol    = "udp"
    cidr_blocks = [aws_vpc.mesh.cidr_block]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
  tags = { Name = "x0tta6bl4-mesh-nodes-sg" }
}

resource "aws_instance" "mesh_nodes" {
  count         = var.node_count
  ami           = var.node_ami
  instance_type = var.instance_type
  subnet_id     = aws_subnet.mesh_a.id
  vpc_security_group_ids = [aws_security_group.mesh_nodes.id]

  tags = {
    Name = "mesh-node-${count.index}"
    Role = "mesh"
    Phase = "1"
  }
}

output "mesh_node_ips" {
  value = [for i in aws_instance.mesh_nodes : i.public_ip]
}
