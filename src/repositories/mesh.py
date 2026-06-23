"""
Repository implementations for mesh-related database models.
"""

from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.database import (
    ACLPolicy,
    GlobalConfig,
    MarketplaceEscrow,
    MarketplaceListing,
    MeshInstance,
    MeshNode,
)
from src.repositories.base import BaseRepository


class MeshInstanceRepository(BaseRepository[MeshInstance]):
    """Repository for MeshInstance entity operations."""

    def get_by_id(self, id: str) -> Optional[MeshInstance]:
        return self.db.query(MeshInstance).filter(MeshInstance.id == id).first()

    def get_by_owner(self, owner_id: str) -> List[MeshInstance]:
        return (
            self.db.query(MeshInstance)
            .filter(MeshInstance.owner_id == owner_id)
            .order_by(MeshInstance.created_at.desc())
            .all()
        )

    def get_active(self) -> List[MeshInstance]:
        return (
            self.db.query(MeshInstance)
            .filter(MeshInstance.status == "active")
            .all()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[MeshInstance]:
        return self.db.query(MeshInstance).offset(skip).limit(limit).all()

    def create(self, entity: MeshInstance) -> MeshInstance:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: str, **kwargs) -> Optional[MeshInstance]:
        entity = self.get_by_id(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
        return entity

    def delete(self, id: str) -> bool:
        entity = self.get_by_id(id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        return self.db.query(func.count(MeshInstance.id)).scalar()

    def count_active(self) -> int:
        return (
            self.db.query(func.count(MeshInstance.id))
            .filter(MeshInstance.status == "active")
            .scalar()
        )


class MeshNodeRepository(BaseRepository[MeshNode]):
    """Repository for MeshNode entity operations."""

    def get_by_id(self, id: str) -> Optional[MeshNode]:
        return self.db.query(MeshNode).filter(MeshNode.id == id).first()

    def get_by_mesh(self, mesh_id: str, include_revoked: bool = False) -> List[MeshNode]:
        query = self.db.query(MeshNode).filter(MeshNode.mesh_id == mesh_id)
        if not include_revoked:
            query = query.filter(MeshNode.status != "revoked")
        return query.order_by(MeshNode.created_at.desc()).all()

    def get_by_status(self, status: str) -> List[MeshNode]:
        return (
            self.db.query(MeshNode)
            .filter(MeshNode.status == status)
            .all()
        )

    def get_healthy_count(self, mesh_ids: List[str]) -> int:
        return (
            self.db.query(func.count(MeshNode.id))
            .filter(
                MeshNode.mesh_id.in_(mesh_ids),
                MeshNode.status == "healthy",
            )
            .scalar()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[MeshNode]:
        return self.db.query(MeshNode).offset(skip).limit(limit).all()

    def create(self, entity: MeshNode) -> MeshNode:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: str, **kwargs) -> Optional[MeshNode]:
        entity = self.get_by_id(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
        return entity

    def delete(self, id: str) -> bool:
        entity = self.get_by_id(id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        return self.db.query(func.count(MeshNode.id)).scalar()

    def count_by_mesh(self, mesh_id: str) -> int:
        return (
            self.db.query(func.count(MeshNode.id))
            .filter(MeshNode.mesh_id == mesh_id)
            .scalar()
        )

    def get_node_stats(self, mesh_ids: List[str]) -> dict:
        """Get aggregated node statistics for given meshes."""
        stats = {"total": 0, "healthy": 0, "stale": 0, "offline": 0, "unknown": 0}
        if not mesh_ids:
            return stats

        nodes = (
            self.db.query(MeshNode.status)
            .filter(MeshNode.mesh_id.in_(mesh_ids), MeshNode.status != "revoked")
            .all()
        )
        for (status,) in nodes:
            stats["total"] += 1
            stats[status] = stats.get(status, 0) + 1
        return stats


class ACLPolicyRepository(BaseRepository[ACLPolicy]):
    """Repository for ACLPolicy entity operations."""

    def get_by_id(self, id: str) -> Optional[ACLPolicy]:
        return self.db.query(ACLPolicy).filter(ACLPolicy.id == id).first()

    def get_by_mesh(self, mesh_id: str) -> List[ACLPolicy]:
        return (
            self.db.query(ACLPolicy)
            .filter(ACLPolicy.mesh_id == mesh_id)
            .all()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[ACLPolicy]:
        return self.db.query(ACLPolicy).offset(skip).limit(limit).all()

    def create(self, entity: ACLPolicy) -> ACLPolicy:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: str, **kwargs) -> Optional[ACLPolicy]:
        entity = self.get_by_id(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
        return entity

    def delete(self, id: str) -> bool:
        entity = self.get_by_id(id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        return self.db.query(func.count(ACLPolicy.id)).scalar()


class MarketplaceListingRepository(BaseRepository[MarketplaceListing]):
    """Repository for MarketplaceListing entity operations."""

    def get_by_id(self, id: str) -> Optional[MarketplaceListing]:
        return self.db.query(MarketplaceListing).filter(MarketplaceListing.id == id).first()

    def get_available(self, region: Optional[str] = None) -> List[MarketplaceListing]:
        query = self.db.query(MarketplaceListing).filter(
            MarketplaceListing.status == "available"
        )
        if region:
            query = query.filter(MarketplaceListing.region == region)
        return query.all()

    def get_by_owner(self, owner_id: str) -> List[MarketplaceListing]:
        return (
            self.db.query(MarketplaceListing)
            .filter(MarketplaceListing.owner_id == owner_id)
            .all()
        )

    def get_by_renter(self, renter_id: str) -> List[MarketplaceListing]:
        return (
            self.db.query(MarketplaceListing)
            .filter(
                MarketplaceListing.renter_id == renter_id,
                MarketplaceListing.status == "rented",
            )
            .all()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[MarketplaceListing]:
        return self.db.query(MarketplaceListing).offset(skip).limit(limit).all()

    def create(self, entity: MarketplaceListing) -> MarketplaceListing:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: str, **kwargs) -> Optional[MarketplaceListing]:
        entity = self.get_by_id(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
        return entity

    def delete(self, id: str) -> bool:
        entity = self.get_by_id(id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        return self.db.query(func.count(MarketplaceListing.id)).scalar()


class MarketplaceEscrowRepository(BaseRepository[MarketplaceEscrow]):
    """Repository for MarketplaceEscrow entity operations."""

    def get_by_id(self, id: str) -> Optional[MarketplaceEscrow]:
        return self.db.query(MarketplaceEscrow).filter(MarketplaceEscrow.id == id).first()

    def get_by_listing(self, listing_id: str) -> List[MarketplaceEscrow]:
        return (
            self.db.query(MarketplaceEscrow)
            .filter(MarketplaceEscrow.listing_id == listing_id)
            .all()
        )

    def get_by_renter(self, renter_id: str) -> List[MarketplaceEscrow]:
        return (
            self.db.query(MarketplaceEscrow)
            .filter(MarketplaceEscrow.renter_id == renter_id)
            .all()
        )

    def get_held(self) -> List[MarketplaceEscrow]:
        return (
            self.db.query(MarketplaceEscrow)
            .filter(MarketplaceEscrow.status == "held")
            .all()
        )

    def get_expired(self) -> List[MarketplaceEscrow]:
        now = datetime.utcnow()
        return (
            self.db.query(MarketplaceEscrow)
            .filter(
                MarketplaceEscrow.status == "held",
                MarketplaceEscrow.expires_at < now,
            )
            .all()
        )

    def get_all(self, skip: int = 0, limit: int = 100) -> List[MarketplaceEscrow]:
        return self.db.query(MarketplaceEscrow).offset(skip).limit(limit).all()

    def create(self, entity: MarketplaceEscrow) -> MarketplaceEscrow:
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, id: str, **kwargs) -> Optional[MarketplaceEscrow]:
        entity = self.get_by_id(id)
        if entity:
            for key, value in kwargs.items():
                if hasattr(entity, key):
                    setattr(entity, key, value)
            self.db.commit()
            self.db.refresh(entity)
        return entity

    def delete(self, id: str) -> bool:
        entity = self.get_by_id(id)
        if entity:
            self.db.delete(entity)
            self.db.commit()
            return True
        return False

    def count(self) -> int:
        return self.db.query(func.count(MarketplaceEscrow.id)).scalar()


class GlobalConfigRepository:
    """Repository for GlobalConfig key-value store."""

    def __init__(self, db: Session):
        self.db = db

    def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        config = self.db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
        return config.value if config else default

    def set(self, key: str, value: str) -> None:
        config = self.db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
        if config:
            config.value = value
        else:
            config = GlobalConfig(key=key, value=value)
            self.db.add(config)
        self.db.commit()

    def delete(self, key: str) -> bool:
        config = self.db.query(GlobalConfig).filter(GlobalConfig.key == key).first()
        if config:
            self.db.delete(config)
            self.db.commit()
            return True
        return False

    def get_all(self) -> List[GlobalConfig]:
        return self.db.query(GlobalConfig).all()
