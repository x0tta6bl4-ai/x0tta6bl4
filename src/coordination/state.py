"""
Agent State Management and Coordination Locks

Provides centralized state management and file-based locking for
coordinating multiple AI agents working simultaneously.
"""

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import hashlib
import logging

logger = logging.getLogger(__name__)


class AgentRole(str, Enum):
    """Roles for AI agents in the development pipeline."""
    ARCHITECT = "gemini"      # Design, decomposition, contracts
    CODER = "codex"           # Implementation
    REVIEWER = "claude"       # Code review, quality
    RESEARCHER = "glm5"       # R&D, alternatives, experiments
    COORDINATOR = "human"     # Integration, final decisions


class AgentStatus(str, Enum):
    """Status of an agent."""
    IDLE = "idle"
    WORKING = "working"
    WAITING = "waiting"
    BLOCKED = "blocked"
    OFFLINE = "offline"


@dataclass
class FileZone:
    """Defines file zones for each agent role."""
    role: AgentRole
    allowed_paths: Set[str]
    forbidden_paths: Set[str]
    priority: int  # Higher priority wins in conflicts
    
    def can_access(self, path: str) -> bool:
        """Check if agent can access a file path."""
        path = str(path)
        
        # Check forbidden paths first
        for forbidden in self.forbidden_paths:
            if path.startswith(forbidden):
                return False
        
        # Check allowed paths
        for allowed in self.allowed_paths:
            if path.startswith(allowed):
                return True
        
        return False


# Default file zones for each agent
DEFAULT_FILE_ZONES: Dict[AgentRole, FileZone] = {
    AgentRole.ARCHITECT: FileZone(
        role=AgentRole.ARCHITECT,
        allowed_paths={"plans/", "docs/adr/", "docs/*.md"},
        forbidden_paths={"src/", "tests/", ".gitlab-ci.yml", "deploy/"},
        priority=1
    ),
    AgentRole.CODER: FileZone(
        role=AgentRole.CODER,
        allowed_paths={"src/", "tests/", "alembic/"},
        forbidden_paths={"plans/", "ROADMAP.md", "STATUS.md"},
        priority=2
    ),
    AgentRole.REVIEWER: FileZone(
        role=AgentRole.REVIEWER,
        allowed_paths={"src/", "tests/", "docs/"},
        forbidden_paths=set(),  # Can review anything
        priority=3  # Highest priority for reviews
    ),
    AgentRole.RESEARCHER: FileZone(
        role=AgentRole.RESEARCHER,
        allowed_paths={"experiments/", "tests/load/", "benchmarks/", "docs/perf/"},
        forbidden_paths={"src/"},  # Cannot modify production code directly
        priority=1
    ),
    AgentRole.COORDINATOR: FileZone(
        role=AgentRole.COORDINATOR,
        allowed_paths=set(),  # Can access everything
        forbidden_paths=set(),
        priority=10  # Highest priority
    ),
}


@dataclass
class AgentState:
    """State of a single agent."""
    agent_id: str
    role: AgentRole
    status: AgentStatus = AgentStatus.IDLE
    current_task: Optional[str] = None
    locked_files: Set[str] = field(default_factory=set)
    last_heartbeat: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_active(self, timeout_seconds: int = 300) -> bool:
        """Check if agent is still active based on heartbeat."""
        return (datetime.utcnow() - self.last_heartbeat) < timedelta(seconds=timeout_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "agent_id": self.agent_id,
            "role": self.role.value,
            "status": self.status.value,
            "current_task": self.current_task,
            "locked_files": list(self.locked_files),
            "last_heartbeat": self.last_heartbeat.isoformat(),
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentState":
        """Create from dictionary."""
        return cls(
            agent_id=data["agent_id"],
            role=AgentRole(data["role"]),
            status=AgentStatus(data["status"]),
            current_task=data.get("current_task"),
            locked_files=set(data.get("locked_files", [])),
            last_heartbeat=datetime.fromisoformat(data["last_heartbeat"]),
            metadata=data.get("metadata", {}),
        )


@dataclass
class CoordinationLock:
    """File-based lock for coordination."""
    path: str
    agent_id: str
    acquired_at: datetime = field(default_factory=datetime.utcnow)
    lock_type: str = "exclusive"  # exclusive, shared
    ttl_seconds: int = 3600  # 1 hour default
    
    def is_expired(self) -> bool:
        """Check if lock has expired."""
        return (datetime.utcnow() - self.acquired_at) > timedelta(seconds=self.ttl_seconds)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "path": self.path,
            "agent_id": self.agent_id,
            "acquired_at": self.acquired_at.isoformat(),
            "lock_type": self.lock_type,
            "ttl_seconds": self.ttl_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoordinationLock":
        """Create from dictionary."""
        return cls(
            path=data["path"],
            agent_id=data["agent_id"],
            acquired_at=datetime.fromisoformat(data["acquired_at"]),
            lock_type=data.get("lock_type", "exclusive"),
            ttl_seconds=data.get("ttl_seconds", 3600),
        )


class AgentCoordinator:
    """
    Central coordinator for multiple AI agents.
    
    Provides:
    - File-based locking to prevent conflicts
    - Agent state tracking
    - Work distribution
    - Conflict detection and resolution
    """
    
    STATE_FILE = ".agent_coordination/state.json"
    LOCK_DIR = ".agent_coordination/locks"
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.state_path = self.project_root / self.STATE_FILE
        self.lock_dir = self.project_root / self.LOCK_DIR
        
        # Ensure directories exist
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self.lock_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory state
        self.agents: Dict[str, AgentState] = {}
        self.locks: Dict[str, CoordinationLock] = {}
        self.file_zones = DEFAULT_FILE_ZONES.copy()
        
        # Load existing state
        self._load_state()
        
        # Cleanup expired locks
        self._cleanup_expired_locks()
    
    def _load_state(self) -> None:
        """Load state from disk."""
        if self.state_path.exists():
            try:
                with open(self.state_path, "r") as f:
                    data = json.load(f)
                    self.agents = {
                        k: AgentState.from_dict(v) for k, v in data.get("agents", {}).items()
                    }
                    self.locks = {
                        k: CoordinationLock.from_dict(v) for k, v in data.get("locks", {}).items()
                    }
                logger.info(f"Loaded state: {len(self.agents)} agents, {len(self.locks)} locks")
            except Exception as e:
                logger.error(f"Failed to load state: {e}")
    
    def _save_state(self) -> None:
        """Save state to disk atomically."""
        data = {
            "agents": {k: v.to_dict() for k, v in self.agents.items()},
            "locks": {k: v.to_dict() for k, v in self.locks.items()},
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        # Write to temp file first, then rename for atomicity
        temp_path = self.state_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        temp_path.rename(self.state_path)
    
    def _cleanup_expired_locks(self) -> None:
        """Remove expired locks."""
        expired = [path for path, lock in self.locks.items() if lock.is_expired()]
        for path in expired:
            del self.locks[path]
            logger.info(f"Cleaned up expired lock: {path}")
        
        if expired:
            self._save_state()
    
    def register_agent(
        self,
        agent_id: str,
        role: AgentRole,
        metadata: Optional[Dict[str, Any]] = None
    ) -> AgentState:
        """Register a new agent or update existing one."""
        state = AgentState(
            agent_id=agent_id,
            role=role,
            status=AgentStatus.IDLE,
            metadata=metadata or {},
        )
        self.agents[agent_id] = state
        self._save_state()
        logger.info(f"Registered agent: {agent_id} ({role.value})")
        return state
    
    def unregister_agent(self, agent_id: str) -> None:
        """Unregister an agent and release its locks."""
        if agent_id in self.agents:
            # Release all locks
            for path in list(self.locks.keys()):
                if self.locks[path].agent_id == agent_id:
                    del self.locks[path]
            
            del self.agents[agent_id]
            self._save_state()
            logger.info(f"Unregistered agent: {agent_id}")
    
    def heartbeat(self, agent_id: str) -> bool:
        """Update agent heartbeat."""
        if agent_id in self.agents:
            self.agents[agent_id].last_heartbeat = datetime.utcnow()
            self._save_state()
            return True
        return False
    
    def can_access(self, agent_id: str, path: str) -> bool:
        """Check if agent can access a file path."""
        if agent_id not in self.agents:
            return False
        
        role = self.agents[agent_id].role
        zone = self.file_zones.get(role)
        
        if not zone:
            return False
        
        return zone.can_access(path)
    
    def acquire_lock(
        self,
        agent_id: str,
        path: str,
        lock_type: str = "exclusive",
        ttl_seconds: int = 3600
    ) -> bool:
        """
        Acquire a lock on a file.
        
        Returns True if lock acquired, False if already locked by another agent.
        """
        if agent_id not in self.agents:
            logger.warning(f"Unknown agent: {agent_id}")
            return False
        
        # Check if agent can access this path
        if not self.can_access(agent_id, path):
            logger.warning(f"Agent {agent_id} cannot access {path}")
            return False
        
        # Check existing lock
        if path in self.locks:
            existing = self.locks[path]
            
            # Same agent can re-acquire
            if existing.agent_id == agent_id:
                return True
            
            # Check if expired
            if existing.is_expired():
                del self.locks[path]
            else:
                logger.info(f"Path {path} locked by {existing.agent_id}")
                return False
        
        # Acquire lock
        lock = CoordinationLock(
            path=path,
            agent_id=agent_id,
            lock_type=lock_type,
            ttl_seconds=ttl_seconds,
        )
        self.locks[path] = lock
        self.agents[agent_id].locked_files.add(path)
        self._save_state()
        
        # Also create file-based lock for external processes
        self._create_file_lock(path, agent_id)
        
        logger.info(f"Agent {agent_id} acquired lock on {path}")
        return True
    
    def release_lock(self, agent_id: str, path: str) -> bool:
        """Release a lock on a file."""
        if path in self.locks and self.locks[path].agent_id == agent_id:
            del self.locks[path]
            if agent_id in self.agents:
                self.agents[agent_id].locked_files.discard(path)
            
            # Remove file-based lock
            self._remove_file_lock(path)
            
            self._save_state()
            logger.info(f"Agent {agent_id} released lock on {path}")
            return True
        return False
    
    def release_all_locks(self, agent_id: str) -> int:
        """Release all locks for an agent."""
        count = 0
        for path in list(self.locks.keys()):
            if self.locks[path].agent_id == agent_id:
                del self.locks[path]
                self._remove_file_lock(path)
                count += 1
        
        if agent_id in self.agents:
            self.agents[agent_id].locked_files.clear()
        
        self._save_state()
        return count
    
    def _create_file_lock(self, path: str, agent_id: str) -> None:
        """Create a file-based lock for external processes."""
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        lock_file = self.lock_dir / f"{digest}.lock"
        with open(lock_file, "w") as f:
            json.dump({
                "path": path,
                "agent_id": agent_id,
                "timestamp": datetime.utcnow().isoformat(),
            }, f)
    
    def _remove_file_lock(self, path: str) -> None:
        """Remove a file-based lock."""
        digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
        lock_file = self.lock_dir / f"{digest}.lock"
        if lock_file.exists():
            lock_file.unlink()

        # Backward-compatible cleanup for legacy lock filenames:
        # remove any lock record that points to the same path.
        for candidate in self.lock_dir.glob("*.lock"):
            try:
                with open(candidate, "r") as f:
                    payload = json.load(f)
                if payload.get("path") == path:
                    candidate.unlink()
            except Exception:
                # Ignore malformed lock files during cleanup.
                continue
    
    def get_lock_info(self, path: str) -> Optional[CoordinationLock]:
        """Get lock info for a path."""
        return self.locks.get(path)
    
    def get_agent_state(self, agent_id: str) -> Optional[AgentState]:
        """Get state of an agent."""
        return self.agents.get(agent_id)
    
    def get_all_agents(self) -> List[AgentState]:
        """Get all registered agents."""
        return list(self.agents.values())
    
    def get_active_agents(self, timeout_seconds: int = 300) -> List[AgentState]:
        """Get all active agents."""
        return [a for a in self.agents.values() if a.is_active(timeout_seconds)]
    
    def update_agent_status(
        self,
        agent_id: str,
        status: AgentStatus,
        current_task: Optional[str] = None
    ) -> bool:
        """Update agent status."""
        if agent_id in self.agents:
            self.agents[agent_id].status = status
            self.agents[agent_id].current_task = current_task
            self.agents[agent_id].last_heartbeat = datetime.utcnow()
            self._save_state()
            return True
        return False
    
    def find_conflicts(self) -> List[Dict[str, Any]]:
        """Find potential conflicts between agents."""
        conflicts = []
        
        # Check for agents working on same files
        file_agents: Dict[str, List[str]] = {}
        for agent_id, state in self.agents.items():
            for path in state.locked_files:
                if path not in file_agents:
                    file_agents[path] = []
                file_agents[path].append(agent_id)
        
        for path, agents in file_agents.items():
            if len(agents) > 1:
                conflicts.append({
                    "type": "multiple_locks",
                    "path": path,
                    "agents": agents,
                })
        
        # Check for agents working in same directories
        dir_agents: Dict[str, List[str]] = {}
        for agent_id, state in self.agents.items():
            if state.current_task:
                # Extract directory from task
                task_dir = state.current_task.split("/")[0] if "/" in state.current_task else state.current_task
                if task_dir not in dir_agents:
                    dir_agents[task_dir] = []
                dir_agents[task_dir].append(agent_id)
        
        for dir_path, agents in dir_agents.items():
            if len(agents) > 1:
                # Check if agents have different priorities
                roles = [self.agents[a].role for a in agents]
                priorities = [self.file_zones.get(r, FileZone(r, set(), set(), 0)).priority for r in roles]
                
                if len(set(priorities)) == 1:  # Same priority
                    conflicts.append({
                        "type": "same_directory",
                        "directory": dir_path,
                        "agents": agents,
                        "roles": [r.value for r in roles],
                    })
        
        return conflicts
    
    def suggest_next_task(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Suggest next task for an agent based on current state."""
        if agent_id not in self.agents:
            return None
        
        role = self.agents[agent_id].role
        zone = self.file_zones.get(role)
        
        if not zone:
            return None
        
        # Find files that need work and are not locked
        suggestions = []
        
        for allowed_path in zone.allowed_paths:
            path = Path(self.project_root) / allowed_path
            if path.exists():
                # Check if locked
                rel_path = str(path.relative_to(self.project_root))
                if rel_path not in self.locks:
                    suggestions.append({
                        "path": rel_path,
                        "type": "available",
                        "priority": zone.priority,
                    })
        
        return suggestions[0] if suggestions else None


# Singleton instance
_coordinator: Optional[AgentCoordinator] = None


def get_coordinator(project_root: str = ".") -> AgentCoordinator:
    """Get or create the coordinator singleton."""
    global _coordinator
    if _coordinator is None:
        _coordinator = AgentCoordinator(project_root)
    return _coordinator
