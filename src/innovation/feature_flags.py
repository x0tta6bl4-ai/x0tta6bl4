#!/usr/bin/env python3
"""
x0tta6bl4 Feature Flags System
============================================

Dynamic feature flag management for safe innovation testing.
Allows gradual rollout and instant rollback of experimental features.

Features:
- Runtime flag configuration
- Percentage-based rollouts
- A/B testing support
- Environment-specific flags
- Audit trail for changes
- Integration with monitoring
"""

import json
import time
import logging
from typing import Dict, List, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import threading
from datetime import datetime

logger = logging.getLogger(__name__)

class FlagType(Enum):
    """Types of feature flags."""
    BOOLEAN = "boolean"  # Simple on/off
    PERCENTAGE = "percentage"  # Rollout by percentage
    WHITELIST = "whitelist"  # Enable for specific users/nodes
    BLACKLIST = "blacklist"  # Disable for specific users/nodes
    CONDITIONAL = "conditional"  # Complex conditions

class FlagStatus(Enum):
    """Feature flag status."""
    ENABLED = "enabled"
    DISABLED = "disabled"
    TESTING = "testing"
    ROLLING_OUT = "rolling_out"
    ROLLED_BACK = "rolled_back"

@dataclass
class FeatureFlag:
    """Individual feature flag configuration."""
    name: str
    flag_type: FlagType
    status: FlagStatus
    description: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # Flag-specific values
    boolean_value: bool = False
    percentage_value: int = 0  # 0-100
    whitelist_value: Set[str] = field(default_factory=set)
    blacklist_value: Set[str] = field(default_factory=set)
    conditions: List[Dict[str, Any]] = field(default_factory=list)
    
    # Metadata
    owner: str = ""
    tags: Set[str] = field(default_factory=set)
    rollout_strategy: str = "immediate"  # immediate, gradual, manual
    dependencies: Set[str] = field(default_factory=set)  # Other flags this depends on
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "flag_type": self.flag_type.value,
            "status": self.status.value,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "boolean_value": self.boolean_value,
            "percentage_value": self.percentage_value,
            "whitelist_value": list(self.whitelist_value),
            "blacklist_value": list(self.blacklist_value),
            "conditions": self.conditions,
            "owner": self.owner,
            "tags": list(self.tags),
            "rollout_strategy": self.rollout_strategy,
            "dependencies": list(self.dependencies)
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'FeatureFlag':
        """Create from dictionary."""
        flag = cls(
            name=data["name"],
            flag_type=FlagType(data["flag_type"]),
            status=FlagStatus(data["status"]),
            description=data["description"],
            boolean_value=data.get("boolean_value", False),
            percentage_value=data.get("percentage_value", 0),
            conditions=data.get("conditions", []),
            owner=data.get("owner", ""),
            rollout_strategy=data.get("rollout_strategy", "immediate")
        )
        
        if "created_at" in data:
            flag.created_at = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data:
            flag.updated_at = datetime.fromisoformat(data["updated_at"])
        
        flag.whitelist_value = set(data.get("whitelist_value", []))
        flag.blacklist_value = set(data.get("blacklist_value", []))
        flag.tags = set(data.get("tags", []))
        flag.dependencies = set(data.get("dependencies", []))
        
        return flag

@dataclass
class FlagEvaluation:
    """Result of flag evaluation."""
    flag_name: str
    enabled: bool
    reason: str
    context: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

class FeatureFlagManager:
    """
    Manages feature flags with runtime evaluation and persistence.
    
    Supports:
    - Dynamic flag updates
    - Context-aware evaluation
    - Audit logging
    - Performance optimization
    """
    
    def __init__(self, config_file: Optional[str] = None):
        self.config_file = Path(config_file) if config_file else None
        self.flags: Dict[str, FeatureFlag] = {}
        self._lock = threading.RLock()
        
        # Evaluation cache for performance
        self._evaluation_cache: Dict[str, FlagEvaluation] = {}
        self._cache_ttl = 60  # seconds
        self._last_cache_clear = time.time()
        
        # Load existing configuration
        if self.config_file and self.config_file.exists():
            self._load_config()
        
        # Register default flags
        self._register_default_flags()
        
        logger.info(f"FeatureFlagManager initialized with {len(self.flags)} flags")
    
    def is_enabled(self, flag_name: str, context: Dict[str, Any] = None) -> bool:
        """
        Check if a feature flag is enabled for the given context.
        
        Args:
            flag_name: Name of the flag to check
            context: Evaluation context (user_id, node_id, environment, etc.)
            
        Returns:
            True if flag is enabled, False otherwise
        """
        context = context or {}
        
        with self._lock:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found, defaulting to False")
                return False
            
            # Check cache
            cache_key = f"{flag_name}:{hash(str(sorted(context.items())))}"
            if self._is_cache_valid(cache_key):
                cached_result = self._evaluation_cache[cache_key]
                return cached_result.enabled
            
            # Evaluate flag
            enabled, reason = self._evaluate_flag(flag, context)
            
            # Cache result
            evaluation = FlagEvaluation(
                flag_name=flag_name,
                enabled=enabled,
                reason=reason,
                context=dict(context)
            )
            self._evaluation_cache[cache_key] = evaluation
            
            # Log evaluation
            logger.debug(f"Flag '{flag_name}' evaluated to {enabled} for context {context}: {reason}")
            
            return enabled
    
    def create_flag(self, flag: FeatureFlag) -> bool:
        """
        Create a new feature flag.
        
        Args:
            flag: Feature flag to create
            
        Returns:
            True if created successfully, False if flag already exists
        """
        with self._lock:
            if flag.name in self.flags:
                logger.warning(f"Feature flag '{flag.name}' already exists")
                return False
            
            # Validate flag
            if not self._validate_flag(flag):
                return False
            
            self.flags[flag.name] = flag
            self._save_config()
            
            logger.info(f"Created feature flag '{flag.name}'")
            return True
    
    def update_flag(self, flag_name: str, updates: Dict[str, Any]) -> bool:
        """
        Update an existing feature flag.
        
        Args:
            flag_name: Name of flag to update
            updates: Dictionary of fields to update
            
        Returns:
            True if updated successfully, False otherwise
        """
        with self._lock:
            flag = self.flags.get(flag_name)
            if not flag:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            # Apply updates
            old_status = flag.status
            for key, value in updates.items():
                if hasattr(flag, key):
                    setattr(flag, key, value)
            
            flag.updated_at = datetime.now()
            
            # Clear cache for this flag
            self._clear_flag_cache(flag_name)
            
            self._save_config()
            
            logger.info(f"Updated feature flag '{flag_name}' from {old_status} to {flag.status}")
            return True
    
    def delete_flag(self, flag_name: str) -> bool:
        """
        Delete a feature flag.
        
        Args:
            flag_name: Name of flag to delete
            
        Returns:
            True if deleted successfully, False otherwise
        """
        with self._lock:
            if flag_name not in self.flags:
                logger.warning(f"Feature flag '{flag_name}' not found")
                return False
            
            del self.flags[flag_name]
            self._clear_flag_cache(flag_name)
            self._save_config()
            
            logger.info(f"Deleted feature flag '{flag_name}'")
            return True
    
    def get_flag(self, flag_name: str) -> Optional[FeatureFlag]:
        """Get feature flag by name."""
        with self._lock:
            return self.flags.get(flag_name)
    
    def list_flags(self, status_filter: Optional[FlagStatus] = None) -> List[FeatureFlag]:
        """
        List all feature flags, optionally filtered by status.
        
        Args:
            status_filter: Optional status filter
            
        Returns:
            List of feature flags
        """
        with self._lock:
            flags = list(self.flags.values())
            
            if status_filter:
                flags = [f for f in flags if f.status == status_filter]
            
            return sorted(flags, key=lambda f: f.name)
    
    def get_flag_stats(self) -> Dict[str, Any]:
        """Get statistics about feature flags."""
        with self._lock:
            stats = {
                "total_flags": len(self.flags),
                "by_status": {},
                "by_type": {},
                "by_owner": {},
                "cache_size": len(self._evaluation_cache),
                "last_updated": None
            }
            
            for flag in self.flags.values():
                # Status breakdown
                status = flag.status.value
                stats["by_status"][status] = stats["by_status"].get(status, 0) + 1
                
                # Type breakdown
                flag_type = flag.flag_type.value
                stats["by_type"][flag_type] = stats["by_type"].get(flag_type, 0) + 1
                
                # Owner breakdown
                owner = flag.owner or "unowned"
                stats["by_owner"][owner] = stats["by_owner"].get(owner, 0) + 1
                
                # Track latest update
                if not stats["last_updated"] or flag.updated_at > stats["last_updated"]:
                    stats["last_updated"] = flag.updated_at
            
            if stats["last_updated"]:
                stats["last_updated"] = stats["last_updated"].isoformat()
            
            return stats
    
    def _evaluate_flag(self, flag: FeatureFlag, context: Dict[str, Any]) -> tuple[bool, str]:
        """Evaluate a single flag against context."""
        # Check if flag is enabled
        if flag.status == FlagStatus.DISABLED:
            return False, "Flag is disabled"
        elif flag.status == FlagStatus.ROLLED_BACK:
            return False, "Flag has been rolled back"
        
        # Check dependencies
        for dep_flag in flag.dependencies:
            if not self.is_enabled(dep_flag, context):
                return False, f"Dependency '{dep_flag}' is not enabled"
        
        # Evaluate based on flag type
        if flag.flag_type == FlagType.BOOLEAN:
            return flag.boolean_value, f"Boolean value: {flag.boolean_value}"
        
        elif flag.flag_type == FlagType.PERCENTAGE:
            return self._evaluate_percentage(flag, context)
        
        elif flag.flag_type == FlagType.WHITELIST:
            return self._evaluate_whitelist(flag, context)
        
        elif flag.flag_type == FlagType.BLACKLIST:
            return self._evaluate_blacklist(flag, context)
        
        elif flag.flag_type == FlagType.CONDITIONAL:
            return self._evaluate_conditional(flag, context)
        
        else:
            return False, f"Unknown flag type: {flag.flag_type}"
    
    def _evaluate_percentage(self, flag: FeatureFlag, context: Dict[str, Any]) -> tuple[bool, str]:
        """Evaluate percentage-based flag."""
        if flag.percentage_value <= 0:
            return False, "Percentage is 0%"
        elif flag.percentage_value >= 100:
            return True, "Percentage is 100%"
        
        # Use consistent hashing for percentage rollout
        identifier = context.get("user_id") or context.get("node_id") or "default"
        hash_value = hash(identifier) % 100
        
        enabled = hash_value < flag.percentage_value
        reason = f"Hash {hash_value} < {flag.percentage_value}%"
        
        return enabled, reason
    
    def _evaluate_whitelist(self, flag: FeatureFlag, context: Dict[str, Any]) -> tuple[bool, str]:
        """Evaluate whitelist flag."""
        identifier = context.get("user_id") or context.get("node_id")
        
        if not identifier:
            return False, "No identifier in context for whitelist evaluation"
        
        enabled = identifier in flag.whitelist_value
        reason = f"Identifier '{identifier}' {'in' if enabled else 'not in'} whitelist"
        
        return enabled, reason
    
    def _evaluate_blacklist(self, flag: FeatureFlag, context: Dict[str, Any]) -> tuple[bool, str]:
        """Evaluate blacklist flag."""
        identifier = context.get("user_id") or context.get("node_id")
        
        if not identifier:
            return True, "No identifier in context for blacklist evaluation"
        
        enabled = identifier not in flag.blacklist_value
        reason = f"Identifier '{identifier}' {'not in' if enabled else 'in'} blacklist"
        
        return enabled, reason
    
    def _evaluate_conditional(self, flag: FeatureFlag, context: Dict[str, Any]) -> tuple[bool, str]:
        """Evaluate conditional flag."""
        for condition in flag.conditions:
            if self._evaluate_condition(condition, context):
                return True, f"Condition matched: {condition}"
        
        return False, "No conditions matched"
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: Dict[str, Any]) -> bool:
        """Evaluate a single condition."""
        field = condition.get("field")
        operator = condition.get("operator")
        value = condition.get("value")
        
        if not all([field, operator, value is not None]):
            return False
        
        context_value = context.get(field)
        if context_value is None:
            return False
        
        # Simple condition evaluation
        if operator == "equals":
            return context_value == value
        elif operator == "not_equals":
            return context_value != value
        elif operator == "contains":
            return value in str(context_value)
        elif operator == "greater_than":
            return context_value > value
        elif operator == "less_than":
            return context_value < value
        elif operator == "in":
            return context_value in value
        else:
            return False
    
    def _validate_flag(self, flag: FeatureFlag) -> bool:
        """Validate feature flag configuration."""
        if not flag.name:
            logger.error("Flag name is required")
            return False
        
        if not flag.description:
            logger.error("Flag description is required")
            return False
        
        # Type-specific validation
        if flag.flag_type == FlagType.PERCENTAGE:
            if not (0 <= flag.percentage_value <= 100):
                logger.error("Percentage value must be between 0 and 100")
                return False
        
        elif flag.flag_type == FlagType.WHITELIST:
            if not flag.whitelist_value:
                logger.error("Whitelist flags must have at least one entry")
                return False
        
        elif flag.flag_type == FlagType.CONDITIONAL:
            if not flag.conditions:
                logger.error("Conditional flags must have at least one condition")
                return False
        
        return True
    
    def _register_default_flags(self) -> None:
        """Register default feature flags for x0tta6bl4."""
        default_flags = [
            FeatureFlag(
                name="experimental_pqc",
                flag_type=FlagType.BOOLEAN,
                status=FlagStatus.DISABLED,
                description="Enable experimental post-quantum cryptography features",
                boolean_value=False,
                tags=["security", "experimental"]
            ),
            FeatureFlag(
                name="mesh_optimization",
                flag_type=FlagType.PERCENTAGE,
                status=FlagStatus.TESTING,
                description="Enable mesh network optimization algorithms",
                percentage_value=10,  # 10% rollout
                tags=["network", "performance"]
            ),
            FeatureFlag(
                name="advanced_monitoring",
                flag_type=FlagType.WHITELIST,
                status=FlagStatus.ENABLED,
                description="Enable advanced monitoring and analytics",
                whitelist_value={"admin", "test_node"},
                tags=["monitoring"]
            ),
            FeatureFlag(
                name="auto_scaling",
                flag_type=FlagType.CONDITIONAL,
                status=FlagStatus.DISABLED,
                description="Enable automatic scaling based on load",
                conditions=[
                    {"field": "environment", "operator": "equals", "value": "production"},
                    {"field": "load_percentage", "operator": "greater_than", "value": 80}
                ],
                tags=["scaling", "automation"]
            )
        ]
        
        for flag in default_flags:
            if flag.name not in self.flags:
                self.flags[flag.name] = flag
        
        logger.info(f"Registered {len(default_flags)} default feature flags")
    
    def _load_config(self) -> None:
        """Load flag configuration from file."""
        try:
            with open(self.config_file, 'r') as f:
                data = json.load(f)
            
            for flag_data in data.get("flags", []):
                flag = FeatureFlag.from_dict(flag_data)
                self.flags[flag.name] = flag
            
            logger.info(f"Loaded {len(self.flags)} feature flags from {self.config_file}")
            
        except Exception as e:
            logger.error(f"Failed to load feature flag config: {e}")
    
    def _save_config(self) -> None:
        """Save flag configuration to file."""
        if not self.config_file:
            return
        
        try:
            # Ensure directory exists
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            
            data = {
                "flags": [flag.to_dict() for flag in self.flags.values()],
                "saved_at": datetime.now().isoformat()
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(data, f, indent=2)
            
        except Exception as e:
            logger.error(f"Failed to save feature flag config: {e}")
    
    def _is_cache_valid(self, cache_key: str) -> bool:
        """Check if cached evaluation is still valid."""
        if cache_key not in self._evaluation_cache:
            return False
        
        # Clear old cache entries periodically
        if time.time() - self._last_cache_clear > self._cache_ttl:
            self._clear_old_cache()
            return False
        
        return True
    
    def _clear_flag_cache(self, flag_name: str) -> None:
        """Clear cache entries for a specific flag."""
        keys_to_remove = [key for key in self._evaluation_cache.keys() if key.startswith(f"{flag_name}:")]
        for key in keys_to_remove:
            del self._evaluation_cache[key]
    
    def _clear_old_cache(self) -> None:
        """Clear old cache entries."""
        current_time = time.time()
        keys_to_remove = []
        
        for key, evaluation in self._evaluation_cache.items():
            age = current_time - evaluation.timestamp.timestamp()
            if age > self._cache_ttl:
                keys_to_remove.append(key)
        
        for key in keys_to_remove:
            del self._evaluation_cache[key]
        
        self._last_cache_clear = current_time
        logger.debug(f"Cleared {len(keys_to_remove)} old cache entries")

# Global instance for easy access
_global_flag_manager: Optional[FeatureFlagManager] = None

def get_flag_manager() -> FeatureFlagManager:
    """Get global feature flag manager instance."""
    global _global_flag_manager
    if _global_flag_manager is None:
        _global_flag_manager = FeatureFlagManager()
    return _global_flag_manager

def is_enabled(flag_name: str, context: Dict[str, Any] = None) -> bool:
    """Convenience function to check if a flag is enabled."""
    return get_flag_manager().is_enabled(flag_name, context)
