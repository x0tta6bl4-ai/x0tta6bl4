"""
MaaS Registry - Global state management.

Contains global state dictionaries and audit logging for the MaaS API.
"""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List

from .mesh_instance import MeshInstance

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Global State
# ---------------------------------------------------------------------------

# Mesh instances: mesh_id -> MeshInstance
_mesh_registry: Dict[str, MeshInstance] = {}

# Pending nodes for approval: mesh_id -> { node_id -> registration_data }
_pending_nodes: Dict[str, Dict[str, Dict]] = {}

# Real-time telemetry: node_id -> heartbeat_data
_node_telemetry: Dict[str, Dict] = {}

# ACL Policies: mesh_id -> List of policies
_mesh_policies: Dict[str, List[Dict]] = {}

# Audit log: mesh_id -> chronological events
_mesh_audit_log: Dict[str, List[Dict[str, Any]]] = {}

# MAPE-K event stream: mesh_id -> chronological events
_mesh_mapek_events: Dict[str, List[Dict[str, Any]]] = {}

# Revoked nodes: mesh_id -> { node_id -> revoke_metadata }
_revoked_nodes: Dict[str, Dict[str, Dict[str, Any]]] = {}

# One-time reissue enrollment tokens:
# mesh_id -> { token -> { node_id, issued_at, expires_at, used } }
_mesh_reissue_tokens: Dict[str, Dict[str, Dict[str, Any]]] = {}

# Async lock for registry operations
_registry_lock = asyncio.Lock()

# MAPE-K event buffer size
_MAPEK_EVENT_BUFFER_SIZE = 1000


# ---------------------------------------------------------------------------
# Audit Logging
# ---------------------------------------------------------------------------

async def record_audit_log(
    mesh_id: str,
    actor: str,
    event: str,
    details: str,
) -> None:
    """Append control-plane audit event (async, with registry lock)."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "actor": actor,
        "event": event,
        "details": details,
    }
    async with _registry_lock:
        if mesh_id not in _mesh_audit_log:
            _mesh_audit_log[mesh_id] = []
        _mesh_audit_log[mesh_id].append(entry)


def audit_sync(mesh_id: str, actor: str, event: str, details: str) -> None:
    """Sync audit helper for use inside non-async endpoints."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "actor": actor,
        "event": event,
        "details": details,
    }
    if mesh_id not in _mesh_audit_log:
        _mesh_audit_log[mesh_id] = []
    _mesh_audit_log[mesh_id].append(entry)


# ---------------------------------------------------------------------------
# Registry Access
# ---------------------------------------------------------------------------

def get_mesh(mesh_id: str) -> MeshInstance | None:
    """Get mesh instance by ID."""
    return _mesh_registry.get(mesh_id)


def get_all_meshes() -> Dict[str, MeshInstance]:
    """Get all mesh instances."""
    return _mesh_registry.copy()


def register_mesh(instance: MeshInstance) -> None:
    """Register a new mesh instance."""
    _mesh_registry[instance.mesh_id] = instance


def unregister_mesh(mesh_id: str) -> bool:
    """Unregister a mesh instance. Returns True if found and removed."""
    if mesh_id in _mesh_registry:
        del _mesh_registry[mesh_id]
        return True
    return False


def get_pending_nodes(mesh_id: str) -> Dict[str, Dict]:
    """Get pending nodes for a mesh."""
    return _pending_nodes.get(mesh_id, {}).copy()


def add_pending_node(mesh_id: str, node_id: str, data: Dict) -> None:
    """Add a pending node registration."""
    if mesh_id not in _pending_nodes:
        _pending_nodes[mesh_id] = {}
    _pending_nodes[mesh_id][node_id] = data


def remove_pending_node(mesh_id: str, node_id: str) -> Dict | None:
    """Remove and return a pending node registration."""
    if mesh_id in _pending_nodes and node_id in _pending_nodes[mesh_id]:
        return _pending_nodes[mesh_id].pop(node_id)
    return None


def get_node_telemetry(node_id: str) -> Dict | None:
    """Get telemetry for a node."""
    return _node_telemetry.get(node_id)


def update_node_telemetry(node_id: str, data: Dict) -> None:
    """Update telemetry for a node."""
    _node_telemetry[node_id] = data


def get_mesh_policies(mesh_id: str) -> List[Dict]:
    """Get ACL policies for a mesh."""
    return _mesh_policies.get(mesh_id, []).copy()


def add_mesh_policy(mesh_id: str, policy: Dict) -> None:
    """Add an ACL policy to a mesh."""
    if mesh_id not in _mesh_policies:
        _mesh_policies[mesh_id] = []
    _mesh_policies[mesh_id].append(policy)


def get_audit_log(mesh_id: str) -> List[Dict[str, Any]]:
    """Get audit log for a mesh."""
    return _mesh_audit_log.get(mesh_id, []).copy()


def get_mapek_events(mesh_id: str) -> List[Dict[str, Any]]:
    """Get MAPE-K events for a mesh."""
    return _mesh_mapek_events.get(mesh_id, []).copy()


def add_mapek_event(mesh_id: str, event: Dict[str, Any]) -> None:
    """Add a MAPE-K event to a mesh's event stream."""
    if mesh_id not in _mesh_mapek_events:
        _mesh_mapek_events[mesh_id] = []
    _mesh_mapek_events[mesh_id].append(event)
    # Trim to buffer size
    if len(_mesh_mapek_events[mesh_id]) > _MAPEK_EVENT_BUFFER_SIZE:
        _mesh_mapek_events[mesh_id] = _mesh_mapek_events[mesh_id][-_MAPEK_EVENT_BUFFER_SIZE:]


def is_node_revoked(mesh_id: str, node_id: str) -> bool:
    """Check if a node is revoked."""
    return node_id in _revoked_nodes.get(mesh_id, {})


def get_revoked_node(mesh_id: str, node_id: str) -> Dict | None:
    """Get revoked node metadata."""
    return _revoked_nodes.get(mesh_id, {}).get(node_id)


def revoke_node(mesh_id: str, node_id: str, metadata: Dict) -> None:
    """Revoke a node."""
    if mesh_id not in _revoked_nodes:
        _revoked_nodes[mesh_id] = {}
    _revoked_nodes[mesh_id][node_id] = metadata


def unrevoke_node(mesh_id: str, node_id: str) -> Dict | None:
    """Remove a node from the revoked list."""
    if mesh_id in _revoked_nodes and node_id in _revoked_nodes[mesh_id]:
        return _revoked_nodes[mesh_id].pop(node_id)
    return None


def get_reissue_token(mesh_id: str, token: str) -> Dict | None:
    """Get reissue token data."""
    return _mesh_reissue_tokens.get(mesh_id, {}).get(token)


def add_reissue_token(mesh_id: str, token: str, data: Dict) -> None:
    """Add a reissue token."""
    if mesh_id not in _mesh_reissue_tokens:
        _mesh_reissue_tokens[mesh_id] = {}
    _mesh_reissue_tokens[mesh_id][token] = data


def find_mesh_for_node(node_id: str) -> str | None:
    """Find the mesh_id that contains a given node."""
    for mesh_id, instance in _mesh_registry.items():
        if node_id in instance.node_instances:
            return mesh_id
    return None


# Export lock for external use
def get_registry_lock() -> asyncio.Lock:
    """Get the registry lock for async operations."""
    return _registry_lock


__all__ = [
    # Audit
    "record_audit_log",
    "audit_sync",
    # Mesh registry
    "get_mesh",
    "get_all_meshes",
    "register_mesh",
    "unregister_mesh",
    # Pending nodes
    "get_pending_nodes",
    "add_pending_node",
    "remove_pending_node",
    # Telemetry
    "get_node_telemetry",
    "update_node_telemetry",
    # Policies
    "get_mesh_policies",
    "add_mesh_policy",
    # Events
    "get_audit_log",
    "get_mapek_events",
    "add_mapek_event",
    # Revocation
    "is_node_revoked",
    "get_revoked_node",
    "revoke_node",
    "unrevoke_node",
    # Reissue tokens
    "get_reissue_token",
    "add_reissue_token",
    # Utilities
    "find_mesh_for_node",
    "get_registry_lock",
]
