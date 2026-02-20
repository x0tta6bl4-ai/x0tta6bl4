terraform {
  required_providers {
    x0t = {
      source  = "x0tta6bl4/x0t"
      version = "1.0.0"
    }
  }
}

provider "x0t" {
  api_key = "test-key"
  api_url = "http://localhost:8000/api/v1/maas"
}

resource "x0t_mesh" "demo" {
  name  = "warehouse-mesh"
  nodes = 10
  plan  = "pro"
}
