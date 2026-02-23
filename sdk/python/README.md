# x0tta6bl4 Python SDK

Official client for interacting with the x0tta6bl4 MaaS Enterprise API.

## Installation
```bash
pip install requests
```

## Quick Start

```python
from maas_client import MaaSClient

# Initialize Client
client = MaaSClient(api_url="https://api.maas.x0tta6bl4.com", api_key="your_api_key")

# 1. Search for available nodes in EU
nodes = client.list_marketplace_nodes(region="eu-central")
print(f"Found {len(nodes)} nodes")

# 2. Rent a node for 24 hours
listing_id = nodes[0]['id']
mesh_id = "my-secure-mesh-001"
rental = client.rent_node(listing_id, mesh_id, hours=24)
print(f"Escrow initiated: {rental['escrow_id']}")

# 3. Check Dashboard Stats
stats = client.get_dashboard()
print(f"Mesh Status: {stats['stats']['node_health']}")
```

## Security
This SDK supports interaction with PQC-signed endpoints. All management actions are recorded in the central Audit Log for compliance.
