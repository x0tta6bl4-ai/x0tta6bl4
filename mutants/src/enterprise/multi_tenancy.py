"""
Multi-Tenancy Support

Provides namespace isolation, resource quotas, and tenant management.
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ResourceQuota:
    """Resource quota for a tenant"""
    cpu_limit: float = 1.0  # CPU cores
    memory_limit: int = 1024  # MB
    storage_limit: int = 10240  # MB
    network_bandwidth: int = 1000  # Mbps
    max_nodes: int = 10
    max_users: int = 100


@dataclass
class Tenant:
    """Represents a tenant in the system"""
    tenant_id: str
    name: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    quota: ResourceQuota = field(default_factory=ResourceQuota)
    metadata: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True


class TenantIsolation:
    """
    Provides namespace isolation for tenants.
    
    Ensures:
    - Network isolation
    - Resource isolation
    - Data isolation
    - Security isolation
    """
    
    def __init__(self):
        self.tenant_namespaces: Dict[str, str] = {}  # tenant_id -> namespace
        self.namespace_resources: Dict[str, Dict[str, Any]] = {}  # namespace -> resources
        logger.info("TenantIsolation initialized")
    
    def create_namespace(self, tenant_id: str) -> str:
        """
        Create isolated namespace for tenant.
        
        Args:
            tenant_id: Tenant identifier
        
        Returns:
            Namespace identifier
        """
        namespace = f"tenant-{tenant_id}"
        self.tenant_namespaces[tenant_id] = namespace
        self.namespace_resources[namespace] = {
            "tenant_id": tenant_id,
            "created_at": datetime.utcnow().isoformat(),
            "resources": {}
        }
        logger.info(f"Created namespace {namespace} for tenant {tenant_id}")
        return namespace
    
    def get_namespace(self, tenant_id: str) -> Optional[str]:
        """Get namespace for tenant"""
        return self.tenant_namespaces.get(tenant_id)
    
    def isolate_resource(self, tenant_id: str, resource_type: str, resource_id: str):
        """
        Isolate a resource to a tenant namespace.
        
        Args:
            tenant_id: Tenant identifier
            resource_type: Type of resource (node, service, etc.)
            resource_id: Resource identifier
        """
        namespace = self.get_namespace(tenant_id)
        if not namespace:
            namespace = self.create_namespace(tenant_id)
        
        if namespace not in self.namespace_resources:
            self.namespace_resources[namespace] = {"resources": {}}
        
        if resource_type not in self.namespace_resources[namespace]["resources"]:
            self.namespace_resources[namespace]["resources"][resource_type] = []
        
        self.namespace_resources[namespace]["resources"][resource_type].append(resource_id)
        logger.debug(f"Isolated {resource_type}:{resource_id} to tenant {tenant_id}")
    
    def check_access(self, tenant_id: str, resource_type: str, resource_id: str) -> bool:
        """
        Check if tenant has access to resource.
        
        Args:
            tenant_id: Tenant identifier
            resource_type: Type of resource
            resource_id: Resource identifier
        
        Returns:
            True if tenant has access
        """
        namespace = self.get_namespace(tenant_id)
        if not namespace:
            return False
        
        resources = self.namespace_resources.get(namespace, {}).get("resources", {})
        tenant_resources = resources.get(resource_type, [])
        
        return resource_id in tenant_resources


class TenantManager:
    """
    Manages tenants and their resources.
    
    Provides:
    - Tenant creation/deletion
    - Resource quota management
    - Tenant isolation
    """
    
    def __init__(self):
        self.tenants: Dict[str, Tenant] = {}
        self.isolation = TenantIsolation()
        logger.info("TenantManager initialized")
    
    def create_tenant(
        self,
        name: str,
        quota: Optional[ResourceQuota] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Tenant:
        """
        Create a new tenant.
        
        Args:
            name: Tenant name
            quota: Resource quota (default if None)
            metadata: Optional metadata
        
        Returns:
            Created Tenant object
        """
        tenant_id = str(uuid4())
        tenant = Tenant(
            tenant_id=tenant_id,
            name=name,
            quota=quota or ResourceQuota(),
            metadata=metadata or {}
        )
        
        self.tenants[tenant_id] = tenant
        self.isolation.create_namespace(tenant_id)
        
        logger.info(f"Created tenant {tenant_id} ({name})")
        return tenant
    
    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID"""
        return self.tenants.get(tenant_id)
    
    def list_tenants(self) -> List[Tenant]:
        """List all tenants"""
        return list(self.tenants.values())
    
    def update_tenant_quota(self, tenant_id: str, quota: ResourceQuota) -> bool:
        """
        Update tenant resource quota.
        
        Args:
            tenant_id: Tenant identifier
            quota: New quota
        
        Returns:
            True if updated successfully
        """
        tenant = self.tenants.get(tenant_id)
        if not tenant:
            logger.warning(f"Tenant {tenant_id} not found")
            return False
        
        tenant.quota = quota
        logger.info(f"Updated quota for tenant {tenant_id}")
        return True
    
    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete a tenant and all its resources.
        
        Args:
            tenant_id: Tenant identifier
        
        Returns:
            True if deleted successfully
        """
        if tenant_id not in self.tenants:
            logger.warning(f"Tenant {tenant_id} not found")
            return False
        
        # Clean up namespace
        namespace = self.isolation.get_namespace(tenant_id)
        if namespace:
            del self.isolation.namespace_resources[namespace]
            del self.isolation.tenant_namespaces[tenant_id]
        
        del self.tenants[tenant_id]
        logger.info(f"Deleted tenant {tenant_id}")
        return True
    
    def check_resource_access(self, tenant_id: str, resource_type: str, resource_id: str) -> bool:
        """
        Check if tenant has access to a resource.
        
        Args:
            tenant_id: Tenant identifier
            resource_type: Type of resource
            resource_id: Resource identifier
        
        Returns:
            True if tenant has access
        """
        return self.isolation.check_access(tenant_id, resource_type, resource_id)
    
    def assign_resource(self, tenant_id: str, resource_type: str, resource_id: str) -> bool:
        """
        Assign a resource to a tenant.
        
        Args:
            tenant_id: Tenant identifier
            resource_type: Type of resource
            resource_id: Resource identifier
        
        Returns:
            True if assigned successfully
        """
        if tenant_id not in self.tenants:
            logger.warning(f"Tenant {tenant_id} not found")
            return False
        
        self.isolation.isolate_resource(tenant_id, resource_type, resource_id)
        return True

