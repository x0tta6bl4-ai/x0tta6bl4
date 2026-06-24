variable "gcp_project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "gcp_region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "production"
}

variable "subnet_cidr" {
  description = "CIDR for subnet"
  type        = string
  default     = "10.0.0.0/24"
}

variable "node_min_count" {
  description = "Minimum node count"
  type        = number
  default     = 3
}

variable "node_max_count" {
  description = "Maximum node count"
  type        = number
  default     = 10
}

variable "node_initial_count" {
  description = "Initial node count"
  type        = number
  default     = 3
}

variable "node_machine_type" {
  description = "Machine type for nodes"
  type        = string
  default     = "e2-medium"
}

variable "node_disk_size" {
  description = "Disk size in GB"
  type        = number
  default     = 50
}

