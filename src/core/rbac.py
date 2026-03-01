from enum import Enum
from typing import Dict, Set

class MeshPermission(str, Enum):
    """Гранальные разрешения для операций в Mesh-сети."""
    MESH_READ = "mesh:read"
    MESH_VIEW = "mesh:view" # Alias for read
    MESH_WRITE = "mesh:write"
    MESH_CREATE = "mesh:create"
    MESH_UPDATE = "mesh:update"
    MESH_DELETE = "mesh:delete"
    
    NODE_READ = "node:read"
    NODE_VIEW = "node:view" # Alias for read
    NODE_WRITE = "node:write"
    NODE_APPROVE = "node:approve"
    NODE_REVOKE = "node:revoke"
    NODE_DELETE = "node:delete"
    NODE_HEAL = "node:heal"
    
    ACL_READ = "acl:read"
    ACL_VIEW = "acl:view" # Alias for read
    ACL_WRITE = "acl:write"
    ACL_UPDATE = "acl:update" # Alias for write
    
    ANALYTICS_VIEW = "analytics:view"
    TELEMETRY_READ = "telemetry:read"
    TELEMETRY_VIEW = "telemetry:view"
    TELEMETRY_EXPORT = "telemetry:export"
    
    PLAYBOOK_CREATE = "playbook:create"
    PLAYBOOK_VIEW = "playbook:view"
    
    BILLING_VIEW = "billing:view"
    MARKETPLACE_LIST = "marketplace:list"
    MARKETPLACE_RENT = "marketplace:rent"
    VPN_CONFIG = "vpn:config"
    VPN_STATUS = "vpn:status"
    VPN_ADMIN = "vpn:admin"

# Набор прав по умолчанию для ролей (когда нет специфических привязок)
DEFAULT_ROLE_PERMISSIONS: Dict[str, Set[MeshPermission]] = {
    "admin": {p for p in MeshPermission}, # Все права
    "operator": {
        MeshPermission.MESH_VIEW,
        MeshPermission.MESH_UPDATE,
        MeshPermission.NODE_VIEW,
        MeshPermission.NODE_APPROVE,
        MeshPermission.NODE_REVOKE,
        MeshPermission.NODE_HEAL,
        MeshPermission.ACL_VIEW,
        MeshPermission.ACL_UPDATE,
        MeshPermission.ANALYTICS_VIEW,
        MeshPermission.TELEMETRY_VIEW,
        MeshPermission.PLAYBOOK_VIEW,
        MeshPermission.PLAYBOOK_CREATE,
        MeshPermission.VPN_CONFIG,
        MeshPermission.VPN_STATUS,
    },
    "user": {
        MeshPermission.MESH_VIEW,
        MeshPermission.MESH_CREATE,
        MeshPermission.MESH_UPDATE,
        MeshPermission.MESH_DELETE,
        MeshPermission.NODE_VIEW,
        MeshPermission.BILLING_VIEW,
        MeshPermission.MARKETPLACE_LIST,
        MeshPermission.MARKETPLACE_RENT,
        MeshPermission.PLAYBOOK_VIEW,
        MeshPermission.VPN_CONFIG,
        MeshPermission.VPN_STATUS,
    },
    "viewer": {
        MeshPermission.MESH_VIEW,
        MeshPermission.NODE_VIEW,
        MeshPermission.ACL_VIEW,
        MeshPermission.ANALYTICS_VIEW,
        MeshPermission.TELEMETRY_VIEW,
        MeshPermission.VPN_STATUS,
    }
}
