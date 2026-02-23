"""
Task Queue for Agent Coordination

Provides a priority-based task queue with dependency tracking and assignment.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
import logging
import uuid

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Status of a task."""
    PENDING = "pending"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskPriority(int, Enum):
    """Priority levels for tasks."""
    CRITICAL = 0  # P0 - Must be done immediately
    HIGH = 1      # P1 - Should be done soon
    MEDIUM = 2    # P2 - Normal priority
    LOW = 3       # P3 - Can wait
    BACKGROUND = 4  # Background tasks


class TaskType(str, Enum):
    """Types of tasks in the pipeline."""
    # Design phase (Gemini)
    DESIGN_ARCHITECTURE = "design.architecture"
    DESIGN_INTERFACE = "design.interface"
    DESIGN_DECOMPOSITION = "design.decomposition"
    
    # Code phase (Codex)
    CODE_IMPLEMENT = "code.implement"
    CODE_TEST = "code.test"
    CODE_MIGRATION = "code.migration"
    
    # Review phase (Claude)
    REVIEW_CODE = "review.code"
    REVIEW_SECURITY = "review.security"
    REVIEW_REFACTOR = "review.refactor"
    
    # R&D phase (GLM-5)
    RESEARCH_ALTERNATIVES = "research.alternatives"
    RESEARCH_OPTIMIZATION = "research.optimization"
    RESEARCH_LOAD_TEST = "research.load_test"
    
    # Integration phase (Human)
    INTEGRATE_MERGE = "integrate.merge"
    INTEGRATE_DEPLOY = "integrate.deploy"
    INTEGRATE_DOCUMENT = "integrate.document"


@dataclass
class Task:
    """A task in the coordination queue."""
    task_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    task_type: TaskType = TaskType.CODE_IMPLEMENT
    title: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Assignment
    assigned_to: Optional[str] = None  # Agent ID
    assigned_role: Optional[str] = None  # Role that should handle this
    
    # Files and resources
    target_files: Set[str] = field(default_factory=set)
    created_files: Set[str] = field(default_factory=set)
    
    # Dependencies
    depends_on: Set[str] = field(default_factory=set)  # Task IDs
    blocks: Set[str] = field(default_factory=set)  # Task IDs that depend on this
    
    # Timing
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    deadline: Optional[datetime] = None
    
    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    artifacts: Dict[str, Any] = field(default_factory=dict)
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    def is_ready(self, completed_tasks: Set[str]) -> bool:
        """Check if all dependencies are satisfied."""
        return self.depends_on.issubset(completed_tasks)
    
    def is_overdue(self) -> bool:
        """Check if task is past deadline."""
        if self.deadline is None:
            return False
        return datetime.utcnow() > self.deadline
    
    def duration(self) -> Optional[timedelta]:
        """Get task duration if completed or in progress."""
        if self.started_at is None:
            return None
        
        end = self.completed_at or datetime.utcnow()
        return end - self.started_at
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "task_id": self.task_id,
            "task_type": self.task_type.value,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "priority": self.priority.value,
            "assigned_to": self.assigned_to,
            "assigned_role": self.assigned_role,
            "target_files": list(self.target_files),
            "created_files": list(self.created_files),
            "depends_on": list(self.depends_on),
            "blocks": list(self.blocks),
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "result": self.result,
            "error": self.error,
            "artifacts": self.artifacts,
            "metadata": self.metadata,
            "tags": list(self.tags),
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Create from dictionary."""
        return cls(
            task_id=data["task_id"],
            task_type=TaskType(data["task_type"]),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=TaskStatus(data.get("status", "pending")),
            priority=TaskPriority(data.get("priority", 2)),
            assigned_to=data.get("assigned_to"),
            assigned_role=data.get("assigned_role"),
            target_files=set(data.get("target_files", [])),
            created_files=set(data.get("created_files", [])),
            depends_on=set(data.get("depends_on", [])),
            blocks=set(data.get("blocks", [])),
            created_at=datetime.fromisoformat(data["created_at"]),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            result=data.get("result"),
            error=data.get("error"),
            artifacts=data.get("artifacts", {}),
            metadata=data.get("metadata", {}),
            tags=set(data.get("tags", [])),
        )


class TaskQueue:
    """
    Priority-based task queue with dependency tracking.
    
    Features:
    - Priority ordering
    - Dependency resolution
    - Role-based assignment
    - Task lifecycle management
    """
    
    QUEUE_FILE = ".agent_coordination/tasks.json"
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.queue_path = self.project_root / self.QUEUE_FILE
        
        # Ensure directory exists
        self.queue_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Task storage
        self.tasks: Dict[str, Task] = {}
        
        # Indexes for fast lookup
        self._by_status: Dict[TaskStatus, Set[str]] = {s: set() for s in TaskStatus}
        self._by_assigned: Dict[str, Set[str]] = {}  # agent_id -> task_ids
        
        # Load existing tasks
        self._load_tasks()
    
    def _load_tasks(self) -> None:
        """Load tasks from disk."""
        if self.queue_path.exists():
            try:
                with open(self.queue_path, "r") as f:
                    data = json.load(f)
                    for task_data in data.get("tasks", []):
                        task = Task.from_dict(task_data)
                        self.tasks[task.task_id] = task
                        self._index_task(task)
                
                logger.info(f"Loaded {len(self.tasks)} tasks from queue")
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")
    
    def _save_tasks(self) -> None:
        """Save tasks to disk."""
        data = {
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "updated_at": datetime.utcnow().isoformat(),
        }
        
        temp_path = self.queue_path.with_suffix(".tmp")
        with open(temp_path, "w") as f:
            json.dump(data, f, indent=2)
        temp_path.rename(self.queue_path)
    
    def _index_task(self, task: Task) -> None:
        """Add task to indexes."""
        self._by_status[task.status].add(task.task_id)
        
        if task.assigned_to:
            if task.assigned_to not in self._by_assigned:
                self._by_assigned[task.assigned_to] = set()
            self._by_assigned[task.assigned_to].add(task.task_id)
    
    def _unindex_task(self, task: Task) -> None:
        """Remove task from indexes."""
        self._by_status[task.status].discard(task.task_id)
        
        if task.assigned_to and task.assigned_to in self._by_assigned:
            self._by_assigned[task.assigned_to].discard(task.task_id)
    
    def add_task(
        self,
        task_type: TaskType,
        title: str,
        description: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        target_files: Optional[Set[str]] = None,
        depends_on: Optional[Set[str]] = None,
        assigned_role: Optional[str] = None,
        deadline: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
        tags: Optional[Set[str]] = None,
    ) -> Task:
        """Add a new task to the queue."""
        task = Task(
            task_type=task_type,
            title=title,
            description=description,
            priority=priority,
            target_files=target_files or set(),
            depends_on=depends_on or set(),
            assigned_role=assigned_role,
            deadline=deadline,
            metadata=metadata or {},
            tags=tags or set(),
        )
        
        self.tasks[task.task_id] = task
        self._index_task(task)
        
        # Update reverse dependencies
        for dep_id in task.depends_on:
            if dep_id in self.tasks:
                self.tasks[dep_id].blocks.add(task.task_id)
        
        self._save_tasks()
        logger.info(f"Added task {task.task_id}: {title}")
        return task
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        result: Optional[str] = None,
        error: Optional[str] = None,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update task status."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        old_status = task.status
        
        # Update indexes
        self._unindex_task(task)
        
        task.status = status
        
        if status == TaskStatus.IN_PROGRESS and task.started_at is None:
            task.started_at = datetime.utcnow()
        
        if status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED):
            task.completed_at = datetime.utcnow()
        
        if result is not None:
            task.result = result
        
        if error is not None:
            task.error = error
        
        if artifacts is not None:
            task.artifacts.update(artifacts)
        
        self._index_task(task)
        self._save_tasks()
        
        logger.info(f"Task {task_id} status: {old_status.value} -> {status.value}")
        return True
    
    def assign_task(self, task_id: str, agent_id: str) -> bool:
        """Assign a task to an agent."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        # Check if task is already assigned
        if task.assigned_to and task.assigned_to != agent_id:
            logger.warning(f"Task {task_id} already assigned to {task.assigned_to}")
            return False
        
        # Update indexes
        self._unindex_task(task)
        
        task.assigned_to = agent_id
        task.status = TaskStatus.ASSIGNED
        
        self._index_task(task)
        self._save_tasks()
        
        logger.info(f"Task {task_id} assigned to {agent_id}")
        return True
    
    def get_ready_tasks(self) -> List[Task]:
        """Get tasks that are ready to be worked on."""
        completed = self._by_status[TaskStatus.COMPLETED]
        
        ready = []
        for task_id in self._by_status[TaskStatus.PENDING]:
            task = self.tasks[task_id]
            if task.is_ready(completed):
                ready.append(task)
        
        # Sort by priority
        ready.sort(key=lambda t: t.priority.value)
        return ready
    
    def get_tasks_for_agent(self, agent_id: str, role: str) -> List[Task]:
        """Get tasks suitable for an agent based on role."""
        # Get tasks assigned to this agent
        assigned = []
        if agent_id in self._by_assigned:
            for task_id in self._by_assigned[agent_id]:
                task = self.tasks[task_id]
                if task.status in (TaskStatus.ASSIGNED, TaskStatus.IN_PROGRESS):
                    assigned.append(task)
        
        # Get ready tasks for this role
        ready = self.get_ready_tasks()
        suitable = [
            t for t in ready
            if t.assigned_role is None or t.assigned_role == role
        ]
        
        # Combine: assigned first, then suitable
        return assigned + suitable
    
    def get_blocked_tasks(self) -> List[Task]:
        """Get tasks that are blocked by dependencies."""
        return [self.tasks[tid] for tid in self._by_status[TaskStatus.BLOCKED]]
    
    def get_overdue_tasks(self) -> List[Task]:
        """Get tasks past their deadline."""
        return [
            t for t in self.tasks.values()
            if t.is_overdue() and t.status not in (TaskStatus.COMPLETED, TaskStatus.CANCELLED)
        ]
    
    def get_dependencies(self, task_id: str) -> List[Task]:
        """Get all dependencies of a task."""
        task = self.tasks.get(task_id)
        if not task:
            return []
        
        return [self.tasks[d] for d in task.depends_on if d in self.tasks]
    
    def get_dependents(self, task_id: str) -> List[Task]:
        """Get all tasks that depend on this task."""
        task = self.tasks.get(task_id)
        if not task:
            return []
        
        return [self.tasks[b] for b in task.blocks if b in self.tasks]
    
    def complete_task(
        self,
        task_id: str,
        result: str,
        created_files: Optional[Set[str]] = None,
        artifacts: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Mark a task as completed."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        self._unindex_task(task)
        
        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow()
        task.result = result
        
        if created_files:
            task.created_files.update(created_files)
        
        if artifacts:
            task.artifacts.update(artifacts)
        
        self._index_task(task)
        
        # Check if any blocked tasks are now ready
        completed = self._by_status[TaskStatus.COMPLETED]
        for blocked_id in task.blocks:
            blocked_task = self.tasks.get(blocked_id)
            if blocked_task and blocked_task.status == TaskStatus.BLOCKED:
                if blocked_task.is_ready(completed):
                    self._unindex_task(blocked_task)
                    blocked_task.status = TaskStatus.PENDING
                    self._index_task(blocked_task)
        
        self._save_tasks()
        logger.info(f"Task {task_id} completed: {result}")
        return True
    
    def fail_task(self, task_id: str, error: str) -> bool:
        """Mark a task as failed."""
        return self.update_task_status(task_id, TaskStatus.FAILED, error=error)
    
    def cancel_task(self, task_id: str, reason: str = "") -> bool:
        """Cancel a task."""
        return self.update_task_status(
            task_id,
            TaskStatus.CANCELLED,
            error=reason or "Cancelled by user"
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        return {
            "total": len(self.tasks),
            "by_status": {s.value: len(ids) for s, ids in self._by_status.items()},
            "overdue": len(self.get_overdue_tasks()),
            "blocked": len(self.get_blocked_tasks()),
        }
    
    def create_pipeline(
        self,
        title: str,
        description: str,
        files: Set[str],
        priority: TaskPriority = TaskPriority.MEDIUM,
    ) -> List[Task]:
        """
        Create a standard pipeline of tasks for a feature.
        
        Creates tasks in order:
        1. Design (Gemini)
        2. Code (Codex)
        3. Research (GLM-5)
        4. Review (Claude)
        5. Integrate (Human)
        """
        tasks = []
        
        # 1. Design task
        design = self.add_task(
            task_type=TaskType.DESIGN_ARCHITECTURE,
            title=f"Design: {title}",
            description=description,
            priority=priority,
            target_files=files,
            assigned_role="gemini",
            tags={"pipeline", "design"},
        )
        tasks.append(design)
        
        # 2. Code task (depends on design)
        code = self.add_task(
            task_type=TaskType.CODE_IMPLEMENT,
            title=f"Implement: {title}",
            description=description,
            priority=priority,
            target_files=files,
            depends_on={design.task_id},
            assigned_role="codex",
            tags={"pipeline", "code"},
        )
        tasks.append(code)
        
        # 3. Research task (depends on code)
        # Safely increment priority, capping at lowest priority (BACKGROUND = 4)
        next_priority_value = min(int(priority.value) + 1, len(TaskPriority) - 1)
        research = self.add_task(
            task_type=TaskType.RESEARCH_ALTERNATIVES,
            title=f"Research: {title}",
            description=f"Find alternatives and edge cases for {title}",
            priority=TaskPriority(next_priority_value),  # Lower priority (capped)
            target_files=files,
            depends_on={code.task_id},
            assigned_role="glm5",
            tags={"pipeline", "research"},
        )
        tasks.append(research)
        
        # 4. Review task (depends on code and research)
        review = self.add_task(
            task_type=TaskType.REVIEW_CODE,
            title=f"Review: {title}",
            description=f"Code review for {title}",
            priority=priority,
            target_files=files,
            depends_on={code.task_id, research.task_id},
            assigned_role="claude",
            tags={"pipeline", "review"},
        )
        tasks.append(review)
        
        # 5. Integrate task (depends on review)
        integrate = self.add_task(
            task_type=TaskType.INTEGRATE_MERGE,
            title=f"Integrate: {title}",
            description=f"Merge and deploy {title}",
            priority=priority,
            target_files=files,
            depends_on={review.task_id},
            assigned_role="human",
            tags={"pipeline", "integrate"},
        )
        tasks.append(integrate)
        
        logger.info(f"Created pipeline with {len(tasks)} tasks for: {title}")
        return tasks


# Singleton instance
_task_queue: Optional[TaskQueue] = None


def get_task_queue(project_root: str = ".") -> TaskQueue:
    """Get or create the task queue singleton."""
    global _task_queue
    if _task_queue is None:
        _task_queue = TaskQueue(project_root)
    return _task_queue
