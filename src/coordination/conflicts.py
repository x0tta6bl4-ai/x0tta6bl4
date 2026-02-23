"""
Conflict Detection and Resolution

Provides automatic detection and resolution of conflicts between agents.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
import logging
import difflib

from .state import AgentRole, AgentCoordinator, FileZone

logger = logging.getLogger(__name__)


class ConflictType(str, Enum):
    """Types of conflicts between agents."""
    FILE_LOCK = "file_lock"           # Multiple agents want same file
    ZONE_VIOLATION = "zone_violation" # Agent accessing forbidden zone
    DEPENDENCY = "dependency"          # Circular or missing dependencies
    MERGE = "merge"                    # Conflicting changes to same file
    RESOURCE = "resource"              # Resource contention (CPU, memory, etc.)
    PRIORITY = "priority"              # Same priority agents on same task
    PIPELINE = "pipeline"              # Pipeline stage conflict


class ConflictSeverity(str, Enum):
    """Severity levels for conflicts."""
    LOW = "low"           # Can be auto-resolved
    MEDIUM = "medium"     # Needs coordination
    HIGH = "high"         # Needs immediate attention
    CRITICAL = "critical" # Blocks all work


class ResolutionStrategy(str, Enum):
    """Strategies for resolving conflicts."""
    PRIORITY = "priority"           # Higher priority wins
    FIRST_COME = "first_come"       # First to acquire wins
    ROLE_BASED = "role_based"       # Role hierarchy decides
    MANUAL = "manual"               # Requires human intervention
    SPLIT = "split"                 # Split work between agents
    QUEUE = "queue"                 # Queue requests
    VOTE = "vote"                   # Agents vote on resolution


@dataclass
class Conflict:
    """A detected conflict between agents."""
    conflict_id: str
    conflict_type: ConflictType
    severity: ConflictSeverity
    agents: Set[str]  # Agent IDs involved
    path: Optional[str] = None  # File path if applicable
    description: str = ""
    detected_at: datetime = field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    resolution: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_resolved(self) -> bool:
        """Check if conflict is resolved."""
        return self.resolved_at is not None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "conflict_type": self.conflict_type.value,
            "severity": self.severity.value,
            "agents": list(self.agents),
            "path": self.path,
            "description": self.description,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution,
            "metadata": self.metadata,
        }


@dataclass
class ConflictResolution:
    """Result of conflict resolution."""
    conflict_id: str
    strategy: ResolutionStrategy
    winner: Optional[str] = None  # Agent ID that won
    actions: List[Dict[str, Any]] = field(default_factory=list)
    message: str = ""
    requires_manual: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "conflict_id": self.conflict_id,
            "strategy": self.strategy.value,
            "winner": self.winner,
            "actions": self.actions,
            "message": self.message,
            "requires_manual": self.requires_manual,
        }


class ConflictDetector:
    """
    Detects and resolves conflicts between agents.
    
    Features:
    - Proactive conflict detection
    - Automatic resolution for low-severity conflicts
    - Escalation for high-severity conflicts
    - Integration with coordinator and event bus
    """
    
    CONFLICTS_FILE = ".agent_coordination/conflicts.json"
    
    # Role priority for conflict resolution
    ROLE_PRIORITY = {
        AgentRole.COORDINATOR: 10,  # Human always wins
        AgentRole.REVIEWER: 3,      # Review has high priority
        AgentRole.CODER: 2,
        AgentRole.ARCHITECT: 1,
        AgentRole.RESEARCHER: 1,
    }
    
    def __init__(
        self,
        coordinator: AgentCoordinator,
        project_root: str = "."
    ):
        self.coordinator = coordinator
        self.project_root = Path(project_root)
        self.conflicts_path = self.project_root / self.CONFLICTS_FILE
        
        # Ensure directory exists
        self.conflicts_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Conflict storage
        self.conflicts: Dict[str, Conflict] = {}
        
        # Load existing conflicts
        self._load_conflicts()
    
    def _load_conflicts(self) -> None:
        """Load conflicts from disk."""
        if self.conflicts_path.exists():
            try:
                with open(self.conflicts_path, "r") as f:
                    data = json.load(f)
                    for conflict_data in data.get("conflicts", []):
                        conflict = Conflict(
                            conflict_id=conflict_data["conflict_id"],
                            conflict_type=ConflictType(conflict_data["conflict_type"]),
                            severity=ConflictSeverity(conflict_data["severity"]),
                            agents=set(conflict_data["agents"]),
                            path=conflict_data.get("path"),
                            description=conflict_data.get("description", ""),
                            detected_at=datetime.fromisoformat(conflict_data["detected_at"]),
                            resolved_at=datetime.fromisoformat(conflict_data["resolved_at"]) if conflict_data.get("resolved_at") else None,
                            resolution=conflict_data.get("resolution"),
                            metadata=conflict_data.get("metadata", {}),
                        )
                        self.conflicts[conflict.conflict_id] = conflict
                
                logger.info(f"Loaded {len(self.conflicts)} conflicts")
            except Exception as e:
                logger.error(f"Failed to load conflicts: {e}")
    
    def _save_conflicts(self) -> None:
        """Save conflicts to disk."""
        data = {
            "conflicts": [c.to_dict() for c in self.conflicts.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        temp_path = self.conflicts_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        temp_path.rename(self.conflicts_path)
    
    def detect_conflicts(self) -> List[Conflict]:
        """Detect all current conflicts."""
        detected = []
        
        # Check for file lock conflicts
        detected.extend(self._detect_lock_conflicts())
        
        # Check for zone violations
        detected.extend(self._detect_zone_violations())
        
        # Check for priority conflicts
        detected.extend(self._detect_priority_conflicts())
        
        # Check for pipeline conflicts
        detected.extend(self._detect_pipeline_conflicts())
        
        return detected
    
    def _detect_lock_conflicts(self) -> List[Conflict]:
        """Detect conflicts from multiple agents wanting same file."""
        conflicts = []
        
        # Group agents by locked files
        file_agents: Dict[str, Set[str]] = {}
        for agent_id, state in self.coordinator.agents.items():
            for path in state.locked_files:
                if path not in file_agents:
                    file_agents[path] = set()
                file_agents[path].add(agent_id)
        
        # Check for multiple agents on same file
        for path, agents in file_agents.items():
            if len(agents) > 1:
                conflict = Conflict(
                    conflict_id=f"lock_{path}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                    conflict_type=ConflictType.FILE_LOCK,
                    severity=ConflictSeverity.HIGH,
                    agents=agents,
                    path=path,
                    description=f"Multiple agents have locks on {path}: {', '.join(agents)}",
                )
                conflicts.append(conflict)
                self.conflicts[conflict.conflict_id] = conflict
        
        if conflicts:
            self._save_conflicts()
        
        return conflicts
    
    def _detect_zone_violations(self) -> List[Conflict]:
        """Detect agents accessing forbidden zones."""
        conflicts = []
        
        for agent_id, state in self.coordinator.agents.items():
            role = state.role
            zone = self.coordinator.file_zones.get(role)
            
            if not zone:
                continue
            
            for path in state.locked_files:
                if not zone.can_access(path):
                    conflict = Conflict(
                        conflict_id=f"zone_{agent_id}_{path}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                        conflict_type=ConflictType.ZONE_VIOLATION,
                        severity=ConflictSeverity.MEDIUM,
                        agents={agent_id},
                        path=path,
                        description=f"Agent {agent_id} ({role.value}) accessed forbidden path: {path}",
                        metadata={"role": role.value, "forbidden_paths": list(zone.forbidden_paths)},
                    )
                    conflicts.append(conflict)
                    self.conflicts[conflict.conflict_id] = conflict
        
        if conflicts:
            self._save_conflicts()
        
        return conflicts
    
    def _detect_priority_conflicts(self) -> List[Conflict]:
        """Detect agents with same priority on overlapping work."""
        conflicts = []
        
        # Group agents by directory they're working in
        dir_agents: Dict[str, List[Tuple[str, AgentRole]]] = {}
        for agent_id, state in self.coordinator.agents.items():
            if state.current_task:
                task_dir = state.current_task.split("/")[0] if "/" in state.current_task else state.current_task
                if task_dir not in dir_agents:
                    dir_agents[task_dir] = []
                dir_agents[task_dir].append((agent_id, state.role))
        
        # Check for same priority agents
        for dir_path, agents in dir_agents.items():
            if len(agents) > 1:
                # Check priorities
                priorities = [self.ROLE_PRIORITY.get(r, 0) for _, r in agents]
                if len(set(priorities)) == 1 and priorities[0] < 10:  # Not human
                    conflict = Conflict(
                        conflict_id=f"priority_{dir_path}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                        conflict_type=ConflictType.PRIORITY,
                        severity=ConflictSeverity.LOW,
                        agents={a for a, _ in agents},
                        path=dir_path,
                        description=f"Agents with same priority working in {dir_path}",
                        metadata={"roles": [r.value for _, r in agents]},
                    )
                    conflicts.append(conflict)
                    self.conflicts[conflict.conflict_id] = conflict
        
        if conflicts:
            self._save_conflicts()
        
        return conflicts
    
    def _detect_pipeline_conflicts(self) -> List[Conflict]:
        """Detect pipeline stage conflicts."""
        conflicts = []
        
        # Check if agents are working on wrong pipeline stage
        # E.g., Coder working before Architect finishes
        
        # Get agents by role
        agents_by_role: Dict[AgentRole, List[str]] = {}
        for agent_id, state in self.coordinator.agents.items():
            if state.status == "working":
                if state.role not in agents_by_role:
                    agents_by_role[state.role] = []
                agents_by_role[state.role].append(agent_id)
        
        # Check for out-of-order pipeline stages
        # Architect should finish before Coder starts
        # Coder should finish before Reviewer starts
        
        pipeline_order = [
            (AgentRole.ARCHITECT, "design"),
            (AgentRole.CODER, "implementation"),
            (AgentRole.RESEARCHER, "research"),
            (AgentRole.REVIEWER, "review"),
        ]
        
        for i, (role, stage) in enumerate(pipeline_order[:-1]):
            next_role, next_stage = pipeline_order[i + 1]
            
            # If current stage agents are working but next stage is also working
            # on same files, that's a potential conflict
            current_agents = agents_by_role.get(role, [])
            next_agents = agents_by_role.get(next_role, [])
            
            if current_agents and next_agents:
                # Check if they're working on overlapping files
                current_files = set()
                for agent_id in current_agents:
                    current_files.update(self.coordinator.agents[agent_id].locked_files)
                
                next_files = set()
                for agent_id in next_agents:
                    next_files.update(self.coordinator.agents[agent_id].locked_files)
                
                overlap = current_files & next_files
                if overlap:
                    conflict = Conflict(
                        conflict_id=f"pipeline_{stage}_{next_stage}_{datetime.utcnow().strftime('%Y%m%d%H%M%S')}",
                        conflict_type=ConflictType.PIPELINE,
                        severity=ConflictSeverity.MEDIUM,
                        agents=set(current_agents + next_agents),
                        path=list(overlap)[0] if overlap else None,
                        description=f"Pipeline conflict: {stage} and {next_stage} stages working on same files",
                        metadata={
                            "current_stage": stage,
                            "next_stage": next_stage,
                            "overlapping_files": list(overlap),
                        },
                    )
                    conflicts.append(conflict)
                    self.conflicts[conflict.conflict_id] = conflict
        
        if conflicts:
            self._save_conflicts()
        
        return conflicts
    
    def resolve_conflict(
        self,
        conflict: Conflict,
        strategy: Optional[ResolutionStrategy] = None
    ) -> ConflictResolution:
        """Resolve a conflict using the specified strategy."""
        if strategy is None:
            strategy = self._select_strategy(conflict)
        
        if strategy == ResolutionStrategy.PRIORITY:
            return self._resolve_by_priority(conflict)
        elif strategy == ResolutionStrategy.FIRST_COME:
            return self._resolve_by_first_come(conflict)
        elif strategy == ResolutionStrategy.ROLE_BASED:
            return self._resolve_by_role(conflict)
        elif strategy == ResolutionStrategy.QUEUE:
            return self._resolve_by_queue(conflict)
        else:
            return ConflictResolution(
                conflict_id=conflict.conflict_id,
                strategy=ResolutionStrategy.MANUAL,
                requires_manual=True,
                message="This conflict requires manual resolution",
            )
    
    def _select_strategy(self, conflict: Conflict) -> ResolutionStrategy:
        """Select the best resolution strategy for a conflict."""
        if conflict.conflict_type == ConflictType.FILE_LOCK:
            return ResolutionStrategy.PRIORITY
        
        if conflict.conflict_type == ConflictType.ZONE_VIOLATION:
            return ResolutionStrategy.MANUAL  # Always needs manual review
        
        if conflict.conflict_type == ConflictType.PRIORITY:
            return ResolutionStrategy.QUEUE
        
        if conflict.conflict_type == ConflictType.PIPELINE:
            return ResolutionStrategy.ROLE_BASED
        
        return ResolutionStrategy.MANUAL
    
    def _resolve_by_priority(self, conflict: Conflict) -> ConflictResolution:
        """Resolve conflict by priority - higher priority wins."""
        agents_with_priority = []
        
        for agent_id in conflict.agents:
            state = self.coordinator.get_agent_state(agent_id)
            if state:
                priority = self.ROLE_PRIORITY.get(state.role, 0)
                agents_with_priority.append((agent_id, priority))
        
        # Sort by priority (highest first)
        agents_with_priority.sort(key=lambda x: x[1], reverse=True)
        
        if not agents_with_priority:
            return ConflictResolution(
                conflict_id=conflict.conflict_id,
                strategy=ResolutionStrategy.PRIORITY,
                requires_manual=True,
                message="No agents found for resolution",
            )
        
        winner = agents_with_priority[0][0]
        
        # Release locks from losers
        actions = []
        for agent_id, _ in agents_with_priority[1:]:
            if conflict.path:
                self.coordinator.release_lock(agent_id, conflict.path)
                actions.append({
                    "action": "release_lock",
                    "agent_id": agent_id,
                    "path": conflict.path,
                })
        
        # Mark conflict as resolved
        conflict.resolved_at = datetime.utcnow()
        conflict.resolution = f"Priority resolution: {winner} wins"
        self._save_conflicts()
        
        return ConflictResolution(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.PRIORITY,
            winner=winner,
            actions=actions,
            message=f"Resolved by priority: {winner} has highest priority",
        )
    
    def _resolve_by_first_come(self, conflict: Conflict) -> ConflictResolution:
        """Resolve conflict by first-come-first-served."""
        # Find who acquired lock first
        lock_info = None
        if conflict.path:
            lock_info = self.coordinator.get_lock_info(conflict.path)
        
        if lock_info:
            winner = lock_info.agent_id
            
            # Release locks from others
            actions = []
            for agent_id in conflict.agents:
                if agent_id != winner:
                    self.coordinator.release_lock(agent_id, conflict.path)
                    actions.append({
                        "action": "release_lock",
                        "agent_id": agent_id,
                        "path": conflict.path,
                    })
            
            # Mark conflict as resolved
            conflict.resolved_at = datetime.utcnow()
            conflict.resolution = f"First-come resolution: {winner} was first"
            self._save_conflicts()
            
            return ConflictResolution(
                conflict_id=conflict.conflict_id,
                strategy=ResolutionStrategy.FIRST_COME,
                winner=winner,
                actions=actions,
                message=f"Resolved by first-come: {winner} acquired lock first",
            )
        
        return ConflictResolution(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.FIRST_COME,
            requires_manual=True,
            message="Could not determine who acquired lock first",
        )
    
    def _resolve_by_role(self, conflict: Conflict) -> ConflictResolution:
        """Resolve conflict by role hierarchy."""
        return self._resolve_by_priority(conflict)  # Same logic
    
    def _resolve_by_queue(self, conflict: Conflict) -> ConflictResolution:
        """Resolve conflict by queuing requests."""
        # Create a queue order
        agents_list = list(conflict.agents)
        
        # Sort by when they registered
        agents_with_time = []
        for agent_id in agents_list:
            state = self.coordinator.get_agent_state(agent_id)
            if state:
                agents_with_time.append((agent_id, state.last_heartbeat))
        
        agents_with_time.sort(key=lambda x: x[1])
        
        if not agents_with_time:
            return ConflictResolution(
                conflict_id=conflict.conflict_id,
                strategy=ResolutionStrategy.QUEUE,
                requires_manual=True,
                message="No agents found for queueing",
            )
        
        winner = agents_with_time[0][0]
        
        # Others wait
        actions = []
        for agent_id, _ in agents_with_time[1:]:
            self.coordinator.update_agent_status(agent_id, "waiting", conflict.path)
            actions.append({
                "action": "set_waiting",
                "agent_id": agent_id,
                "reason": "queued",
            })
        
        # Mark conflict as resolved
        conflict.resolved_at = datetime.utcnow()
        conflict.resolution = f"Queue resolution: {winner} is first in queue"
        self._save_conflicts()
        
        return ConflictResolution(
            conflict_id=conflict.conflict_id,
            strategy=ResolutionStrategy.QUEUE,
            winner=winner,
            actions=actions,
            message=f"Resolved by queue: {winner} is first, others waiting",
        )
    
    def auto_resolve(self) -> List[ConflictResolution]:
        """Automatically resolve all resolvable conflicts."""
        resolutions = []
        
        for conflict in self.conflicts.values():
            if not conflict.is_resolved() and conflict.severity in (ConflictSeverity.LOW, ConflictSeverity.MEDIUM):
                resolution = self.resolve_conflict(conflict)
                resolutions.append(resolution)
        
        return resolutions
    
    def get_active_conflicts(self) -> List[Conflict]:
        """Get all unresolved conflicts."""
        return [c for c in self.conflicts.values() if not c.is_resolved()]
    
    def get_conflict_history(self, limit: int = 100) -> List[Conflict]:
        """Get conflict history."""
        sorted_conflicts = sorted(
            self.conflicts.values(),
            key=lambda c: c.detected_at,
            reverse=True
        )
        return sorted_conflicts[:limit]
