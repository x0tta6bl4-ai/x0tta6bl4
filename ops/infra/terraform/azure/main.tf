# Azure Infrastructure for x0tta6bl4
#
# Creates:
# - Resource Group
# - Virtual Network
# - AKS cluster
# - Load Balancer
# - Storage Account

terraform {
  required_version = ">= 1.5"
  
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
  
  backend "azurerm" {
    resource_group_name  = "x0tta6bl4-terraform"
    storage_account_name = "x0tta6bl4tfstate"
    container_name       = "terraform-state"
    key                  = "azure/terraform.tfstate"
  }
}

provider "azurerm" {
  features {}
}

# Resource Group
resource "azurerm_resource_group" "x0tta6bl4" {
  name     = "rg-x0tta6bl4-${var.environment}"
  location = var.azure_location
  
  tags = {
    Environment = var.environment
    Project     = "x0tta6bl4"
    ManagedBy   = "Terraform"
  }
}

# Virtual Network
resource "azurerm_virtual_network" "x0tta6bl4" {
  name                = "vnet-x0tta6bl4-${var.environment}"
  address_space       = [var.vnet_address_space]
  location            = azurerm_resource_group.x0tta6bl4.location
  resource_group_name = azurerm_resource_group.x0tta6bl4.name
  
  tags = {
    Environment = var.environment
  }
}

# Subnets
resource "azurerm_subnet" "aks" {
  name                 = "subnet-aks"
  resource_group_name  = azurerm_resource_group.x0tta6bl4.name
  virtual_network_name = azurerm_virtual_network.x0tta6bl4.name
  address_prefixes     = [var.aks_subnet_cidr]
}

# AKS Cluster
resource "azurerm_kubernetes_cluster" "x0tta6bl4" {
  name                = "aks-x0tta6bl4-${var.environment}"
  location            = azurerm_resource_group.x0tta6bl4.location
  resource_group_name = azurerm_resource_group.x0tta6bl4.name
  dns_prefix          = "x0tta6bl4-${var.environment}"
  kubernetes_version  = var.kubernetes_version
  
  default_node_pool {
    name                = "default"
    node_count          = var.node_count
    vm_size            = var.node_vm_size
    enable_auto_scaling = true
    min_count          = var.node_min_count
    max_count          = var.node_max_count
    vnet_subnet_id     = azurerm_subnet.aks.id
  }
  
  identity {
    type = "SystemAssigned"
  }
  
  network_profile {
    network_plugin = "azure"
    network_policy = "azure"
  }
  
  role_based_access_control_enabled = true
  
  tags = {
    Environment = var.environment
  }
}

# Storage Account
resource "azurerm_storage_account" "x0tta6bl4" {
  name                     = "x0tta6bl4${var.environment}${substr(md5(azurerm_resource_group.x0tta6bl4.name), 0, 8)}"
  resource_group_name      = azurerm_resource_group.x0tta6bl4.name
  location                 = azurerm_resource_group.x0tta6bl4.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version         = "TLS1_2"
  
  tags = {
    Environment = var.environment
  }
}

# Container Registry (optional, for private images)
resource "azurerm_container_registry" "x0tta6bl4" {
  name                = "x0tta6bl4${var.environment}${substr(md5(azurerm_resource_group.x0tta6bl4.name), 0, 6)}"
  resource_group_name = azurerm_resource_group.x0tta6bl4.name
  location            = azurerm_resource_group.x0tta6bl4.location
  sku                 = "Basic"
  admin_enabled       = false
  
  tags = {
    Environment = var.environment
  }
}

