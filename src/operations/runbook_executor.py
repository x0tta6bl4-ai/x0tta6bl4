"""
Automated Runbook Execution Engine

Provides:
- Automated runbook execution
- Runbook testing
- Runbook versioning
- Integration with incident management
"""
import logging
import subprocess
import json
import yaml
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)


class RunbookStatus(Enum):
    """Runbook execution status"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class RunbookStep:
    """A single step in a runbook"""
    step_id: str
    name: str
    command: str
    description: Optional[str] = None
    expected_output: Optional[str] = None
    timeout: int = 30
    retry_count: int = 0
    retry_delay: float = 1.0
    required: bool = True
    condition: Optional[str] = None  # Condition to check before execution


@dataclass
class Runbook:
    """A complete runbook"""
    runbook_id: str
    name: str
    description: str
    version: int = 1
    steps: List[RunbookStep] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    author: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunbookExecution:
    """Runbook execution result"""
    execution_id: str
    runbook_id: str
    status: RunbookStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    steps_executed: List[str] = field(default_factory=list)
    steps_failed: List[str] = field(default_factory=list)
    output: Dict[str, Any] = field(default_factory=dict)
    error_message: Optional[str] = None


class RunbookExecutor:
    """
    Automated Runbook Execution Engine.
    
    Provides:
    - Automated runbook execution
    - Runbook testing
    - Runbook versioning
    - Integration with incident management
    """
    
    def __init__(self, runbooks_dir: Optional[Path] = None):
        """
        Initialize Runbook Executor.
        
        Args:
            runbooks_dir: Directory containing runbook definitions
        """
        self.runbooks_dir = runbooks_dir or Path("docs/operations/runbooks")
        self.runbooks: Dict[str, Runbook] = {}
        self.executions: Dict[str, RunbookExecution] = {}
        self.version_history: Dict[str, List[Runbook]] = {}  # runbook_id -> [versions]
        
        # Load runbooks
        self._load_runbooks()
        
        logger.info(f"RunbookExecutor initialized with {len(self.runbooks)} runbooks")
    
    def _load_runbooks(self):
        """Load runbooks from directory."""
        if not self.runbooks_dir.exists():
            logger.warning(f"Runbooks directory not found: {self.runbooks_dir}")
            return
        
        for runbook_file in self.runbooks_dir.glob("*.yaml"):
            try:
                runbook = self._load_runbook_from_file(runbook_file)
                if runbook:
                    self.runbooks[runbook.runbook_id] = runbook
                    logger.info(f"Loaded runbook: {runbook.name} (v{runbook.version})")
            except Exception as e:
                logger.error(f"Failed to load runbook from {runbook_file}: {e}")
    
    def _load_runbook_from_file(self, file_path: Path) -> Optional[Runbook]:
        """Load a runbook from YAML file."""
        try:
            with open(file_path, 'r') as f:
                data = yaml.safe_load(f)
            
            steps = [
                RunbookStep(
                    step_id=step.get("id", f"step-{i}"),
                    name=step.get("name", ""),
                    command=step.get("command", ""),
                    description=step.get("description"),
                    expected_output=step.get("expected_output"),
                    timeout=step.get("timeout", 30),
                    retry_count=step.get("retry_count", 0),
                    retry_delay=step.get("retry_delay", 1.0),
                    required=step.get("required", True),
                    condition=step.get("condition")
                )
                for i, step in enumerate(data.get("steps", []))
            ]
            
            return Runbook(
                runbook_id=data.get("id", file_path.stem),
                name=data.get("name", file_path.stem),
                description=data.get("description", ""),
                version=data.get("version", 1),
                steps=steps,
                tags=data.get("tags", []),
                author=data.get("author"),
                metadata=data.get("metadata", {})
            )
        except Exception as e:
            logger.error(f"Failed to parse runbook file {file_path}: {e}")
            return None
    
    def execute_runbook(
        self,
        runbook_id: str,
        context: Optional[Dict[str, Any]] = None,
        dry_run: bool = False
    ) -> RunbookExecution:
        """
        Execute a runbook.
        
        Args:
            runbook_id: ID of runbook to execute
            context: Additional context variables
            dry_run: If True, simulate execution without running commands
            
        Returns:
            RunbookExecution result
        """
        if runbook_id not in self.runbooks:
            raise ValueError(f"Runbook {runbook_id} not found")
        
        runbook = self.runbooks[runbook_id]
        context = context or {}
        
        execution_id = f"{runbook_id}-{datetime.now().timestamp()}"
        execution = RunbookExecution(
            execution_id=execution_id,
            runbook_id=runbook_id,
            status=RunbookStatus.RUNNING,
            started_at=datetime.now()
        )
        
        logger.info(f"Executing runbook: {runbook.name} (v{runbook.version})")
        
        try:
            for step in runbook.steps:
                # Check condition
                if step.condition and not self._evaluate_condition(step.condition, context):
                    logger.info(f"Skipping step {step.step_id}: condition not met")
                    execution.steps_executed.append(f"{step.step_id}:skipped")
                    continue
                
                # Execute step
                if dry_run:
                    logger.info(f"[DRY RUN] Would execute: {step.command}")
                    execution.steps_executed.append(step.step_id)
                    continue
                
                success = self._execute_step(step, context, execution)
                
                if success:
                    execution.steps_executed.append(step.step_id)
                else:
                    execution.steps_failed.append(step.step_id)
                    if step.required:
                        execution.status = RunbookStatus.FAILED
                        execution.error_message = f"Required step {step.step_id} failed"
                        break
            
            if execution.status == RunbookStatus.RUNNING:
                execution.status = RunbookStatus.SUCCESS
            
        except Exception as e:
            execution.status = RunbookStatus.FAILED
            execution.error_message = str(e)
            logger.error(f"Runbook execution failed: {e}")
        
        execution.completed_at = datetime.now()
        self.executions[execution_id] = execution
        
        logger.info(f"Runbook execution completed: {execution.status.value}")
        return execution
    
    def _execute_step(
        self,
        step: RunbookStep,
        context: Dict[str, Any],
        execution: RunbookExecution
    ) -> bool:
        """Execute a single runbook step."""
        logger.info(f"Executing step: {step.name} ({step.step_id})")
        
        # Substitute variables in command
        command = self._substitute_variables(step.command, context)
        
        for attempt in range(step.retry_count + 1):
            try:
                import shlex
                result = subprocess.run(
                    shlex.split(command),
                    shell=False,
                    capture_output=True,
                    text=True,
                    timeout=step.timeout
                )
                
                output = result.stdout.strip()
                execution.output[step.step_id] = {
                    "stdout": output,
                    "stderr": result.stderr.strip(),
                    "returncode": result.returncode
                }
                
                if result.returncode == 0:
                    # Check expected output if specified
                    if step.expected_output:
                        if step.expected_output not in output:
                            logger.warning(f"Step {step.step_id} output doesn't match expected")
                            if attempt < step.retry_count:
                                continue
                            return False
                    
                    logger.info(f"✅ Step {step.step_id} completed successfully")
                    return True
                else:
                    logger.warning(f"Step {step.step_id} failed with return code {result.returncode}")
                    if attempt < step.retry_count:
                        import time
                        time.sleep(step.retry_delay)
                        continue
                    return False
                    
            except subprocess.TimeoutExpired:
                logger.error(f"Step {step.step_id} timed out after {step.timeout}s")
                if attempt < step.retry_count:
                    import time
                    time.sleep(step.retry_delay)
                    continue
                return False
            except Exception as e:
                logger.error(f"Step {step.step_id} execution error: {e}")
                if attempt < step.retry_count:
                    import time
                    time.sleep(step.retry_delay)
                    continue
                return False
        
        return False
    
    def _substitute_variables(self, command: str, context: Dict[str, Any]) -> str:
        """Substitute variables in command string."""
        result = command
        for key, value in context.items():
            result = result.replace(f"${{{key}}}", str(value))
            result = result.replace(f"${key}", str(value))
        return result
    
    def _evaluate_condition(self, condition: str, context: Dict[str, Any]) -> bool:
        """Evaluate a condition string."""
        try:
            # Simple condition evaluation (can be extended)
            # Example: "${cpu_usage} > 90"
            for key, value in context.items():
                condition = condition.replace(f"${{{key}}}", str(value))
                condition = condition.replace(f"${key}", str(value))
            
            # Evaluate as Python expression (with safety checks)
            # In production, use a proper expression evaluator
            return eval(condition, {"__builtins__": {}}, {})
        except Exception as e:
            logger.warning(f"Condition evaluation failed: {e}")
            return False
    
    def test_runbook(self, runbook_id: str) -> Dict[str, Any]:
        """
        Test a runbook (dry run).
        
        Args:
            runbook_id: ID of runbook to test
            
        Returns:
            Test results
        """
        if runbook_id not in self.runbooks:
            raise ValueError(f"Runbook {runbook_id} not found")
        
        logger.info(f"Testing runbook: {runbook_id}")
        
        execution = self.execute_runbook(runbook_id, dry_run=True)
        
        return {
            "runbook_id": runbook_id,
            "test_status": "passed" if execution.status == RunbookStatus.SUCCESS else "failed",
            "steps_count": len(self.runbooks[runbook_id].steps),
            "steps_executed": len(execution.steps_executed),
            "steps_failed": len(execution.steps_failed),
            "execution_time": (execution.completed_at - execution.started_at).total_seconds() if execution.completed_at else 0
        }
    
    def update_runbook(self, runbook: Runbook) -> bool:
        """
        Update a runbook with versioning.
        
        Args:
            runbook: Updated runbook
            
        Returns:
            True if update successful
        """
        if runbook.runbook_id not in self.runbooks:
            logger.warning(f"Runbook {runbook.runbook_id} not found, creating new")
            self.runbooks[runbook.runbook_id] = runbook
            return True
        
        old_runbook = self.runbooks[runbook.runbook_id]
        
        # Increment version
        runbook.version = old_runbook.version + 1
        runbook.updated_at = datetime.now()
        
        # Save old version
        if runbook.runbook_id not in self.version_history:
            self.version_history[runbook.runbook_id] = []
        self.version_history[runbook.runbook_id].append(old_runbook)
        
        # Update runbook
        self.runbooks[runbook.runbook_id] = runbook
        
        logger.info(f"✅ Runbook {runbook.runbook_id} updated to version {runbook.version}")
        return True
    
    def get_runbook_versions(self, runbook_id: str) -> List[Runbook]:
        """Get version history for a runbook."""
        return self.version_history.get(runbook_id, [])
    
    def get_execution_history(self, runbook_id: Optional[str] = None, limit: int = 100) -> List[RunbookExecution]:
        """Get execution history."""
        executions = list(self.executions.values())
        
        if runbook_id:
            executions = [e for e in executions if e.runbook_id == runbook_id]
        
        executions.sort(key=lambda e: e.started_at, reverse=True)
        return executions[:limit]
    
    def get_runbook_status(self) -> Dict[str, Any]:
        """Get runbook executor status."""
        return {
            "total_runbooks": len(self.runbooks),
            "total_executions": len(self.executions),
            "successful_executions": sum(1 for e in self.executions.values() if e.status == RunbookStatus.SUCCESS),
            "failed_executions": sum(1 for e in self.executions.values() if e.status == RunbookStatus.FAILED),
            "versioned_runbooks": len(self.version_history)
        }


# Global instance
_runbook_executor: Optional[RunbookExecutor] = None


def get_runbook_executor() -> RunbookExecutor:
    """Get global RunbookExecutor instance."""
    global _runbook_executor
    if _runbook_executor is None:
        _runbook_executor = RunbookExecutor()
    return _runbook_executor

