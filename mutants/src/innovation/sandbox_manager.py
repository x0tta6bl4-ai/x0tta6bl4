#!/usr/bin/env python3
"""
x0tta6bl4 Innovation Sandbox Manager
============================================

Manages isolated sandbox environments for safe innovation testing.
Provides containerized environments with controlled resource usage.

Features:
- Isolated sandbox environments
- Resource usage monitoring
- Safe code execution
- Rollback capabilities
- Experiment tracking
- Integration with feature flags
"""

import os
import json
import time
import uuid
import shutil
import tempfile
import subprocess
import threading
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime, timedelta
import logging

from .feature_flags import FeatureFlagManager, is_enabled

logger = logging.getLogger(__name__)

@dataclass
class SandboxConfig:
    """Configuration for a sandbox environment."""
    name: str
    description: str
    image: str = "python:3.12-slim"
    memory_limit: str = "512m"
    cpu_limit: str = "0.5"
    timeout_seconds: int = 300
    network_isolated: bool = True
    filesystem_readonly: bool = False
    allowed_paths: List[str] = field(default_factory=list)
    environment_vars: Dict[str, str] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)  # pip packages

@dataclass
class Experiment:
    """Innovation experiment record."""
    experiment_id: str
    name: str
    description: str
    sandbox_name: str
    code: str
    config: SandboxConfig
    status: str  # CREATED, RUNNING, COMPLETED, FAILED, TIMEOUT
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)

class SandboxManager:
    """
    Manages sandbox environments for safe code experimentation.
    
    Provides:
    - Container-based isolation
    - Resource monitoring
    - Experiment tracking
    - Rollback capabilities
    """
    
    def __init__(self, sandbox_dir: Optional[str] = None):
        self.sandbox_dir = Path(sandbox_dir) if sandbox_dir else Path(tempfile.mkdtemp(prefix="x0tta_sandbox_"))
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)
        
        self.sandboxes: Dict[str, SandboxConfig] = {}
        self.experiments: Dict[str, Experiment] = {}
        self._lock = threading.RLock()
        
        # Feature flag manager for experimental features
        self.feature_flags = FeatureFlagManager()
        
        # Initialize default sandboxes
        self._initialize_default_sandboxes()
        
        logger.info(f"SandboxManager initialized with directory: {self.sandbox_dir}")
    
    def create_sandbox(self, config: SandboxConfig) -> bool:
        """
        Create a new sandbox configuration.
        
        Args:
            config: Sandbox configuration
            
        Returns:
            True if created successfully
        """
        with self._lock:
            if config.name in self.sandboxes:
                logger.warning(f"Sandbox '{config.name}' already exists")
                return False
            
            # Validate configuration
            if not self._validate_sandbox_config(config):
                return False
            
            self.sandboxes[config.name] = config
            
            # Create sandbox directory
            sandbox_path = self.sandbox_dir / config.name
            sandbox_path.mkdir(parents=True, exist_ok=True)
            
            # Create Dockerfile if needed
            self._create_sandbox_dockerfile(config)
            
            logger.info(f"Created sandbox '{config.name}'")
            return True
    
    def run_experiment(self, 
                      name: str,
                      description: str,
                      sandbox_name: str,
                      code: str,
                      config_override: Optional[Dict[str, Any]] = None) -> str:
        """
        Run an experiment in a sandbox.
        
        Args:
            name: Experiment name
            description: Experiment description
            sandbox_name: Name of sandbox to use
            code: Code to execute
            config_override: Optional configuration overrides
            
        Returns:
            Experiment ID
        """
        experiment_id = str(uuid.uuid4())
        
        with self._lock:
            # Get sandbox configuration
            sandbox_config = self.sandboxes.get(sandbox_name)
            if not sandbox_config:
                raise ValueError(f"Sandbox '{sandbox_name}' not found")
            
            # Apply configuration overrides
            if config_override:
                config = self._apply_config_override(sandbox_config, config_override)
            else:
                config = sandbox_config
            
            # Create experiment record
            experiment = Experiment(
                experiment_id=experiment_id,
                name=name,
                description=description,
                sandbox_name=sandbox_name,
                code=code,
                config=config,
                status="CREATED"
            )
            
            self.experiments[experiment_id] = experiment
            
            # Run experiment in background
            threading.Thread(
                target=self._execute_experiment,
                args=(experiment,),
                daemon=True
            ).start()
            
            logger.info(f"Started experiment '{name}' (ID: {experiment_id}) in sandbox '{sandbox_name}'")
            return experiment_id
    
    def get_experiment_status(self, experiment_id: str) -> Optional[Dict[str, Any]]:
        """Get experiment status and results."""
        with self._lock:
            experiment = self.experiments.get(experiment_id)
            if not experiment:
                return None
            
            return {
                "experiment_id": experiment.experiment_id,
                "name": experiment.name,
                "description": experiment.description,
                "sandbox_name": experiment.sandbox_name,
                "status": experiment.status,
                "created_at": experiment.created_at.isoformat(),
                "started_at": experiment.started_at.isoformat() if experiment.started_at else None,
                "completed_at": experiment.completed_at.isoformat() if experiment.completed_at else None,
                "result": experiment.result,
                "error": experiment.error,
                "metrics": experiment.metrics
            }
    
    def list_experiments(self, status_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """List experiments, optionally filtered by status."""
        with self._lock:
            experiments = []
            
            for experiment in self.experiments.values():
                if status_filter and experiment.status != status_filter:
                    continue
                
                experiments.append({
                    "experiment_id": experiment.experiment_id,
                    "name": experiment.name,
                    "sandbox_name": experiment.sandbox_name,
                    "status": experiment.status,
                    "created_at": experiment.created_at.isoformat(),
                    "duration": (
                        (experiment.completed_at or datetime.now()) - experiment.started_at
                    ).total_seconds() if experiment.started_at else None
                })
            
            return sorted(experiments, key=lambda x: x["created_at"], reverse=True)
    
    def cleanup_experiment(self, experiment_id: str) -> bool:
        """Clean up experiment resources."""
        with self._lock:
            experiment = self.experiments.get(experiment_id)
            if not experiment:
                return False
            
            # Remove experiment directory
            experiment_dir = self.sandbox_dir / "experiments" / experiment_id
            if experiment_dir.exists():
                shutil.rmtree(experiment_dir)
            
            # Remove from tracking
            del self.experiments[experiment_id]
            
            logger.info(f"Cleaned up experiment {experiment_id}")
            return True
    
    def get_sandbox_stats(self) -> Dict[str, Any]:
        """Get sandbox statistics."""
        with self._lock:
            stats = {
                "total_sandboxes": len(self.sandboxes),
                "total_experiments": len(self.experiments),
                "experiments_by_status": {},
                "active_experiments": 0,
                "sandbox_directory": str(self.sandbox_dir)
            }
            
            for experiment in self.experiments.values():
                status = experiment.status
                stats["experiments_by_status"][status] = stats["experiments_by_status"].get(status, 0) + 1
                
                if status in ["CREATED", "RUNNING"]:
                    stats["active_experiments"] += 1
            
            return stats
    
    def _execute_experiment(self, experiment: Experiment) -> None:
        """Execute experiment in sandbox."""
        try:
            experiment.status = "RUNNING"
            experiment.started_at = datetime.now()
            
            # Create experiment directory
            experiment_dir = self.sandbox_dir / "experiments" / experiment.experiment_id
            experiment_dir.mkdir(parents=True, exist_ok=True)
            
            # Write code to file
            code_file = experiment_dir / "experiment.py"
            with open(code_file, 'w') as f:
                f.write(experiment.code)
            
            # Create requirements file if dependencies specified
            if experiment.config.dependencies:
                req_file = experiment_dir / "requirements.txt"
                with open(req_file, 'w') as f:
                    f.write('\n'.join(experiment.config.dependencies))
            
            # Execute in sandbox
            result = self._run_in_container(experiment, experiment_dir)
            
            # Update experiment
            experiment.status = "COMPLETED" if result["success"] else "FAILED"
            experiment.completed_at = datetime.now()
            experiment.result = result
            experiment.metrics = result.get("metrics", {})
            
            if not result["success"]:
                experiment.error = result.get("error", "Unknown error")
            
        except Exception as e:
            experiment.status = "FAILED"
            experiment.completed_at = datetime.now()
            experiment.error = str(e)
            logger.error(f"Experiment {experiment.experiment_id} failed: {e}")
    
    def _run_in_container(self, experiment: Experiment, experiment_dir: Path) -> Dict[str, Any]:
        """Run experiment in Docker container."""
        try:
            # Check if Docker is available
            if not shutil.which("docker"):
                return self._run_locally(experiment, experiment_dir)
            
            # Build container command
            cmd = [
                "docker", "run", "--rm",
                "--memory", experiment.config.memory_limit,
                "--cpus", experiment.config.cpu_limit,
                "--timeout", str(experiment.config.timeout_seconds),
                "-v", f"{experiment_dir}:/workspace",
                "-w", "/workspace"
            ]
            
            # Add network isolation if requested
            if experiment.config.network_isolated:
                cmd.append("--network=none")
            
            # Add environment variables
            for key, value in experiment.config.environment_vars.items():
                cmd.extend(["-e", f"{key}={value}"])
            
            cmd.append(experiment.config.image)
            cmd.extend(["python", "experiment.py"])
            
            # Execute with timeout
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=experiment.config.timeout_seconds
                )
                
                duration = time.time() - start_time
                
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "metrics": {
                        "duration_seconds": duration,
                        "memory_used": "unknown",  # Would need additional monitoring
                        "exit_code": result.returncode
                    }
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Experiment timed out",
                    "metrics": {"duration_seconds": experiment.config.timeout_seconds}
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Container execution failed: {e}",
                "metrics": {}
            }
    
    def _run_locally(self, experiment: Experiment, experiment_dir: Path) -> Dict[str, Any]:
        """Run experiment locally (fallback when Docker unavailable)."""
        try:
            # Change to experiment directory
            original_cwd = os.getcwd()
            os.chdir(experiment_dir)
            
            # Install dependencies if specified
            if experiment.config.dependencies:
                subprocess.run(
                    ["pip", "install", "-r", "requirements.txt"],
                    capture_output=True,
                    timeout=60
                )
            
            # Execute experiment
            start_time = time.time()
            
            try:
                result = subprocess.run(
                    ["python", "experiment.py"],
                    capture_output=True,
                    text=True,
                    timeout=experiment.config.timeout_seconds
                )
                
                duration = time.time() - start_time
                
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode,
                    "metrics": {
                        "duration_seconds": duration,
                        "exit_code": result.returncode
                    }
                }
                
            except subprocess.TimeoutExpired:
                return {
                    "success": False,
                    "error": "Experiment timed out",
                    "metrics": {"duration_seconds": experiment.config.timeout_seconds}
                }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Local execution failed: {e}",
                "metrics": {}
            }
        finally:
            os.chdir(original_cwd)
    
    def _validate_sandbox_config(self, config: SandboxConfig) -> bool:
        """Validate sandbox configuration."""
        if not config.name:
            logger.error("Sandbox name is required")
            return False
        
        if not config.description:
            logger.error("Sandbox description is required")
            return False
        
        # Validate resource limits
        if config.memory_limit:
            if not config.memory_limit.endswith(('m', 'g')):
                logger.error("Memory limit must end with 'm' or 'g'")
                return False
        
        if config.cpu_limit:
            try:
                cpu_float = float(config.cpu_limit)
                if cpu_float <= 0 or cpu_float > 64:
                    logger.error("CPU limit must be between 0 and 64")
                    return False
            except ValueError:
                logger.error("CPU limit must be a number")
                return False
        
        return True
    
    def _apply_config_override(self, base_config: SandboxConfig, override: Dict[str, Any]) -> SandboxConfig:
        """Apply configuration overrides to base config."""
        # Create new config with overrides
        new_config = SandboxConfig(
            name=base_config.name,
            description=base_config.description,
            image=override.get("image", base_config.image),
            memory_limit=override.get("memory_limit", base_config.memory_limit),
            cpu_limit=override.get("cpu_limit", base_config.cpu_limit),
            timeout_seconds=override.get("timeout_seconds", base_config.timeout_seconds),
            network_isolated=override.get("network_isolated", base_config.network_isolated),
            filesystem_readonly=override.get("filesystem_readonly", base_config.filesystem_readonly),
            allowed_paths=override.get("allowed_paths", base_config.allowed_paths),
            environment_vars=override.get("environment_vars", base_config.environment_vars),
            dependencies=override.get("dependencies", base_config.dependencies)
        )
        
        return new_config
    
    def _create_sandbox_dockerfile(self, config: SandboxConfig) -> None:
        """Create Dockerfile for sandbox if needed."""
        if config.image == "python:3.12-slim" and not config.dependencies:
            return  # Use default image
        
        sandbox_path = self.sandbox_dir / config.name
        dockerfile_path = sandbox_path / "Dockerfile"
        
        dockerfile_content = f"FROM {config.image}\n"
        
        if config.dependencies:
            dockerfile_content += "COPY requirements.txt .\n"
            dockerfile_content += "RUN pip install -r requirements.txt\n"
        
        dockerfile_content += "WORKDIR /workspace\n"
        
        with open(dockerfile_path, 'w') as f:
            f.write(dockerfile_content)
    
    def _initialize_default_sandboxes(self) -> None:
        """Initialize default sandbox configurations."""
        default_sandboxes = [
            SandboxConfig(
                name="python_basic",
                description="Basic Python sandbox for simple experiments",
                image="python:3.12-slim",
                memory_limit="256m",
                cpu_limit="0.5",
                timeout_seconds=60
            ),
            SandboxConfig(
                name="python_ml",
                description="Python sandbox with ML libraries",
                image="python:3.12-slim",
                memory_limit="1g",
                cpu_limit="1.0",
                timeout_seconds=300,
                dependencies=["numpy", "pandas", "scikit-learn"]
            ),
            SandboxConfig(
                name="network_test",
                description="Sandbox for network-related experiments",
                image="python:3.12-slim",
                memory_limit="512m",
                cpu_limit="0.5",
                timeout_seconds=120,
                network_isolated=False,
                dependencies=["requests", "aiohttp"]
            ),
            SandboxConfig(
                name="security_test",
                description="Isolated sandbox for security experiments",
                image="python:3.12-slim",
                memory_limit="256m",
                cpu_limit="0.3",
                timeout_seconds=60,
                network_isolated=True,
                filesystem_readonly=True
            )
        ]
        
        for config in default_sandboxes:
            if config.name not in self.sandboxes:
                self.create_sandbox(config)
        
        logger.info(f"Initialized {len(default_sandboxes)} default sandboxes")

# Global instance for easy access
_global_sandbox_manager: Optional[SandboxManager] = None

def get_sandbox_manager() -> SandboxManager:
    """Get global sandbox manager instance."""
    global _global_sandbox_manager
    if _global_sandbox_manager is None:
        _global_sandbox_manager = SandboxManager()
    return _global_sandbox_manager

def run_experiment(name: str, 
                  description: str,
                  sandbox_name: str,
                  code: str,
                  config_override: Optional[Dict[str, Any]] = None) -> str:
    """Convenience function to run an experiment."""
    return get_sandbox_manager().run_experiment(name, description, sandbox_name, code, config_override)
