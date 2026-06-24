import requests
from typing import Dict, Any, List, Optional

class MaaSClient:
    """
    Python SDK for x0tta6bl4 MaaS Enterprise API.
    """
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": api_key})

    def create_mesh(self, name: str) -> Dict[str, Any]:
        """Deploy a new mesh network."""
        resp = self.session.post(f"{self.api_url}/api/v1/maas/deploy", json={"name": name})
        resp.raise_for_status()
        return resp.json()

    def list_marketplace_nodes(self, region: str = None) -> List[Dict[str, Any]]:
        """Search available nodes."""
        params = {"region": region} if region else {}
        resp = self.session.get(f"{self.api_url}/api/v1/maas/marketplace/search", params=params)
        resp.raise_for_status()
        return resp.json()

    def rent_node(self, listing_id: str, mesh_id: str, hours: int = 1) -> Dict[str, Any]:
        """Rent a node and initiate escrow."""
        resp = self.session.post(
            f"{self.api_url}/api/v1/maas/marketplace/rent/{listing_id}",
            params={"mesh_id": mesh_id, "hours": hours}
        )
        resp.raise_for_status()
        return resp.json()

    def get_dashboard(self) -> Dict[str, Any]:
        """Get account summary and stats."""
        resp = self.session.get(f"{self.api_url}/api/v1/maas/dashboard/summary")
        resp.raise_for_status()
        return resp.json()

    def get_node_telemetry(self, mesh_id: str, node_id: str) -> Dict[str, Any]:
        """Fetch real-time telemetry for a specific node."""
        resp = self.session.get(f"{self.api_url}/api/v1/maas/{mesh_id}/nodes/{node_id}/telemetry")
        resp.raise_for_status()
        return resp.json()

    def send_playbook(self, mesh_id: str, name: str, targets: List[str], actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Create and sign a new playbook for specific nodes."""
        payload = {
            "name": name,
            "target_nodes": targets,
            "actions": actions
        }
        resp = self.session.post(f"{self.api_url}/api/v1/maas/playbooks/create?mesh_id={mesh_id}", json=payload)
        resp.raise_for_status()
        return resp.json()

    def get_audit_logs(self) -> List[Dict[str, Any]]:
        """Retrieve recent audit logs for compliance."""
        # This uses the dashboard summary as a shortcut, or a dedicated audit endpoint if available
        summary = self.get_dashboard()
        return summary.get("recent_audit", [])
