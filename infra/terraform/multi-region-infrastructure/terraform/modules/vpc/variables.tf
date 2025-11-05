# Переменные для модуля VPC

variable "name" {
  description = "Название VPC"
  type        = string
}

variable "environment" {
  description = "Среда развертывания"
  type        = string
  default     = "production"
}

variable "cidr_block" {
  description = "CIDR блок для VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "Список зон доступности"
  type        = list(string)
}

variable "public_subnets" {
  description = "Карта публичных subnet"
  type = map(object({
    cidr = string
    az   = string
  }))
}

variable "private_subnets" {
  description = "Карта приватных subnet"
  type = map(object({
    cidr = string
    az   = string
  }))
}

variable "database_subnets" {
  description = "Карта database subnet"
  type = map(object({
    cidr = string
    az   = string
  }))
}

variable "enable_nat_gateway" {
  description = "Включить NAT Gateway"
  type        = bool
  default     = true
}

variable "enable_vpn_gateway" {
  description = "Включить VPN Gateway"
  type        = bool
  default     = false
}

variable "tags" {
  description = "Теги для ресурсов"
  type        = map(string)
  default     = {}
}