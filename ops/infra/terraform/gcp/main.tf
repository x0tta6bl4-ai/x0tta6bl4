# GCP Infrastructure for x0tta6bl4
#
# Creates:
# - VPC Network
# - GKE cluster
# - Cloud Storage bucket
# - IAM roles

terraform {
  required_version = ">= 1.5"
  
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.23"
    }
  }
  
  backend "gcs" {
    bucket = "x0tta6bl4-terraform-state"
    prefix = "gcp/terraform.tfstate"
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
}

# VPC Network
resource "google_compute_network" "x0tta6bl4" {
  name                    = "vpc-x0tta6bl4-${var.environment}"
  auto_create_subnetworks = false
  
  labels = {
    environment = var.environment
    project     = "x0tta6bl4"
  }
}

# Subnet
resource "google_compute_subnetwork" "x0tta6bl4" {
  name          = "subnet-x0tta6bl4-${var.environment}"
  ip_cidr_range = var.subnet_cidr
  region        = var.gcp_region
  network       = google_compute_network.x0tta6bl4.id
  
  private_ip_google_access = true
}

# GKE Cluster
resource "google_container_cluster" "x0tta6bl4" {
  name     = "gke-x0tta6bl4-${var.environment}"
  location = var.gcp_region
  
  remove_default_node_pool = true
  initial_node_count       = 1
  
  network    = google_compute_network.x0tta6bl4.name
  subnetwork = google_compute_subnetwork.x0tta6bl4.name
  
  # Enable private cluster
  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }
  
  # Enable network policy
  network_policy {
    enabled = true
  }
  
  # Enable workload identity
  workload_identity_config {
    workload_pool = "${var.gcp_project_id}.svc.id.goog"
  }
  
  # Enable binary authorization
  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE"
  }
  
  master_auth {
    client_certificate_config {
      issue_client_certificate = false
    }
  }
  
  release_channel {
    channel = "REGULAR"
  }
  
  resource_labels = {
    environment = var.environment
    project     = "x0tta6bl4"
  }
}

# Node Pool
resource "google_container_node_pool" "x0tta6bl4" {
  name       = "x0tta6bl4-node-pool"
  location   = var.gcp_region
  cluster    = google_container_cluster.x0tta6bl4.name
  
  autoscaling {
    min_node_count = var.node_min_count
    max_node_count = var.node_max_count
  }
  
  management {
    auto_repair  = true
    auto_upgrade = true
  }
  
  node_config {
    machine_type = var.node_machine_type
    disk_size_gb = var.node_disk_size
    disk_type    = "pd-standard"
    
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    
    labels = {
      environment = var.environment
      project     = "x0tta6bl4"
    }
    
    workload_metadata_config {
      mode = "GKE_METADATA"
    }
  }
  
  initial_node_count = var.node_initial_count
}

# Cloud Storage Bucket
resource "google_storage_bucket" "x0tta6bl4_data" {
  name          = "${var.gcp_project_id}-x0tta6bl4-data-${var.environment}"
  location      = var.gcp_region
  force_destroy = false
  
  uniform_bucket_level_access = true
  
  versioning {
    enabled = true
  }
  
  encryption {
    default_kms_key_name = null
  }
  
  labels = {
    environment = var.environment
    project     = "x0tta6bl4"
  }
}

# IAM Service Account for GKE
resource "google_service_account" "gke_node" {
  account_id   = "gke-node-${var.environment}"
  display_name = "GKE Node Service Account"
}

resource "google_project_iam_member" "gke_node" {
  project = var.gcp_project_id
  role    = "roles/storage.objectViewer"
  member  = "serviceAccount:${google_service_account.gke_node.email}"
}

