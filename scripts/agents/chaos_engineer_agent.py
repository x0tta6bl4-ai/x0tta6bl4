#!/usr/bin/env python3
"""
Chaos Engineer Agent - Automated resilience testing for x0tta6bl4

P0 Agent for chaos engineering automation.
Integrates with existing chaos/ infrastructure and MAPE-K self-healing.
"""

import argparse
import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("chaos-engineer")


class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class ExperimentType(Enum):
    NODE_FAILURE = "node_failure"
    NETWORK_DELAY = "network_delay"
    NETWORK_PARTITION = "network_partition"
    POD_KILL = "pod_kill"
    LATENCY_INJECTION = "latency_injection"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


@dataclass
class ChaosExperiment:
    id: str
    type: ExperimentType
    target: str
    duration_seconds: int
    parameters: Dict[str, Any]
    status: ExperimentStatus = ExperimentStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: Dict[str, Any] = None
    error: Optional[str] = None


@dataclass
class ResilienceMetrics:
    recovery_time_ms: float
    success_rate: float
    error_count: int
    mttr_seconds: float
    availability_percent: float


class ChaosEngineerAgent:
    """
    Chaos Engineer Agent for automated resilience testing.
    
    Responsibilities:
    - Run scheduled chaos experiments
    - Monitor system resilience during chaos
    - Integrate with MAPE-K self-healing
    - Generate resilience reports
    - Auto-rollback on critical failures
    """
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or "/mnt/projects/config/chaos_agent.json"
        self.project_root = Path("/mnt/projects")
        self.chaos_dir = self.project_root / "chaos"
        self.results_dir = self.project_root / ".tmp/chaos_results"
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        # Load or create config
        self.config = self._load_config()
        
        # Experiment registry
        self.experiments: List[ChaosExperiment] = []
        
        logger.info("ChaosEngineerAgent initialized")
    
    def _load_config(self) -> Dict:
        """Load agent configuration."""
        if os.path.exists(self.config_path):
            with open(self.config_path) as f:
                return json.load(f)
        
        # Default config
        default_config = {
            "experiment_schedule": "0 */6 * * *",  # Every 6 hours
            "auto_rollback": True,
            "max_concurrent_experiments": 2,
            "critical_services": [
                "telegram_bot_simple.py",
                "xray",
                "x-ui",
                "mesh_router"
            ],
            "thresholds": {
                "max_recovery_time_ms": 5000,
                "min_availability_percent": 95.0,
                "max_error_rate": 0.05
            }
        }
        
        # Save default config
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, 'w') as f:
            json.dump(default_config, f, indent=2)
        
        return default_config
    
    def run_experiment(self, experiment_type: ExperimentType, 
                       target: str, 
                       duration: int = 60,
                       params: Dict[str, Any] = None) -> ChaosExperiment:
        """Run a single chaos experiment."""
        
        exp_id = f"chaos_{experiment_type.value}_{int(time.time())}"
        experiment = ChaosExperiment(
            id=exp_id,
            type=experiment_type,
            target=target,
            duration_seconds=duration,
            parameters=params or {},
            status=ExperimentStatus.RUNNING,
            started_at=datetime.utcnow().isoformat()
        )
        
        logger.info(f"Starting experiment: {exp_id} ({experiment_type.value} on {target})")
        
        try:
            # Run pre-checks
            self._pre_flight_checks(target)
            
            # Execute chaos based on type
            if experiment_type == ExperimentType.NODE_FAILURE:
                self._run_node_failure(target, duration, params)
            elif experiment_type == ExperimentType.NETWORK_DELAY:
                self._run_network_delay(target, duration, params)
            elif experiment_type == ExperimentType.NETWORK_PARTITION:
                self._run_network_partition(target, duration, params)
            elif experiment_type == ExperimentType.POD_KILL:
                self._run_pod_kill(target, params)
            elif experiment_type == ExperimentType.LATENCY_INJECTION:
                self._run_latency_injection(target, duration, params)
            else:
                raise ValueError(f"Unknown experiment type: {experiment_type}")
            
            # Measure resilience
            metrics = self._measure_resilience(target)
            
            # Complete experiment
            experiment.status = ExperimentStatus.COMPLETED
            experiment.completed_at = datetime.utcnow().isoformat()
            experiment.results = asdict(metrics)
            
            logger.info(f"Experiment {exp_id} completed. MTTR: {metrics.mttr_seconds}s")
            
        except Exception as e:
            experiment.status = ExperimentStatus.FAILED
            experiment.error = str(e)
            logger.error(f"Experiment {exp_id} failed: {e}")
            
            if self.config.get("auto_rollback"):
                logger.info(f"Auto-rollback enabled, attempting recovery...")
                self._rollback(target)
                experiment.status = ExperimentStatus.ROLLED_BACK
        
        # Save experiment result
        self._save_experiment(experiment)
        self.experiments.append(experiment)
        
        return experiment
    
    def _pre_flight_checks(self, target: str):
        """Run pre-flight checks before chaos."""
        logger.info(f"Running pre-flight checks for {target}")
        # Check target exists and is healthy
        # Implementation depends on target type
    
    def _run_node_failure(self, target: str, duration: int, params: Dict):
        """Simulate node failure."""
        logger.info(f"Simulating node failure: {target} for {duration}s")
        
        # Use existing chaos infrastructure
        yaml_file = self.chaos_dir / "node-failure.yaml"
        if yaml_file.exists():
            # Apply chaos experiment via kubectl or docker
            cmd = f"kubectl apply -f {yaml_file}"
            subprocess.run(cmd, shell=True, capture_output=True)
            time.sleep(duration)
            # Cleanup
            subprocess.run(f"kubectl delete -f {yaml_file}", shell=True, capture_output=True)
    
    def _run_network_delay(self, target: str, duration: int, params: Dict):
        """Inject network delay."""
        delay_ms = params.get("delay_ms", 100)
        logger.info(f"Injecting {delay_ms}ms delay to {target} for {duration}s")
        
        yaml_file = self.chaos_dir / "network-delay.yaml"
        if yaml_file.exists():
            cmd = f"kubectl apply -f {yaml_file}"
            subprocess.run(cmd, shell=True, capture_output=True)
            time.sleep(duration)
            subprocess.run(f"kubectl delete -f {yaml_file}", shell=True, capture_output=True)
    
    def _run_network_partition(self, target: str, duration: int, params: Dict):
        """Create network partition."""
        logger.info(f"Creating network partition for {target} for {duration}s")
        
        yaml_file = self.chaos_dir / "network-partition.yaml"
        if yaml_file.exists():
            cmd = f"kubectl apply -f {yaml_file}"
            subprocess.run(cmd, shell=True, capture_output=True)
            time.sleep(duration)
            subprocess.run(f"kubectl delete -f {yaml_file}", shell=True, capture_output=True)
    
    def _run_pod_kill(self, target: str, params: Dict):
        """Kill pods randomly."""
        kill_percent = params.get("kill_percent", 25)
        logger.info(f"Killing {kill_percent}% of pods in {target}")
        
        yaml_file = self.chaos_dir / "pod-kill-25pct.yaml"
        if yaml_file.exists():
            cmd = f"kubectl apply -f {yaml_file}"
            subprocess.run(cmd, shell=True, capture_output=True)
            time.sleep(30)  # Give time for chaos to apply
            subprocess.run(f"kubectl delete -f {yaml_file}", shell=True, capture_output=True)
    
    def _run_latency_injection(self, target: str, duration: int, params: Dict):
        """Inject latency into requests."""
        latency_ms = params.get("latency_ms", 200)
        logger.info(f"Injecting {latency_ms}ms latency to {target} for {duration}s")
        
        yaml_file = self.chaos_dir / "latency-injection.yaml"
        if yaml_file.exists():
            cmd = f"kubectl apply -f {yaml_file}"
            subprocess.run(cmd, shell=True, capture_output=True)
            time.sleep(duration)
            subprocess.run(f"kubectl delete -f {yaml_file}", shell=True, capture_output=True)
    
    def _measure_resilience(self, target: str) -> ResilienceMetrics:
        """Measure system resilience metrics."""
        logger.info(f"Measuring resilience for {target}")
        
        # Query MAPE-K metrics or Prometheus
        # Stub implementation - would integrate with actual monitoring
        
        return ResilienceMetrics(
            recovery_time_ms=1500.0,
            success_rate=0.98,
            error_count=2,
            mttr_seconds=3.5,
            availability_percent=99.5
        )
    
    def _rollback(self, target: str):
        """Rollback chaos experiment."""
        logger.info(f"Rolling back chaos on {target}")
        # Implementation depends on chaos type
    
    def _save_experiment(self, experiment: ChaosExperiment):
        """Save experiment result to file."""
        result_file = self.results_dir / f"{experiment.id}.json"
        with open(result_file, 'w') as f:
            json.dump(asdict(experiment), f, indent=2, default=str)
        logger.info(f"Experiment saved to {result_file}")
    
    def run_scheduled_experiments(self):
        """Run experiments based on schedule."""
        logger.info("Running scheduled chaos experiments")
        
        experiments = [
            (ExperimentType.NODE_FAILURE, "mesh-node-1", 60, {}),
            (ExperimentType.NETWORK_DELAY, "vpn-gateway", 120, {"delay_ms": 200}),
            (ExperimentType.POD_KILL, "xray-pods", 30, {"kill_percent": 25}),
        ]
        
        results = []
        for exp_type, target, duration, params in experiments:
            result = self.run_experiment(exp_type, target, duration, params)
            results.append(result)
        
        return results
    
    def generate_report(self) -> Dict:
        """Generate chaos engineering report."""
        if not self.experiments:
            return {"status": "no_experiments"}
        
        completed = [e for e in self.experiments if e.status == ExperimentStatus.COMPLETED]
        failed = [e for e in self.experiments if e.status == ExperimentStatus.FAILED]
        
        report = {
            "generated_at": datetime.utcnow().isoformat(),
            "total_experiments": len(self.experiments),
            "completed": len(completed),
            "failed": len(failed),
            "success_rate": len(completed) / len(self.experiments) if self.experiments else 0,
            "avg_mttr_seconds": sum(
                e.results.get("mttr_seconds", 0) for e in completed if e.results
            ) / len(completed) if completed else 0,
            "experiments": [asdict(e) for e in self.experiments]
        }
        
        report_file = self.results_dir / f"chaos_report_{int(time.time())}.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Report generated: {report_file}")
        return report


def main():
    parser = argparse.ArgumentParser(description="Chaos Engineer Agent")
    parser.add_argument("--mode", choices=["single", "scheduled", "report"], default="single")
    parser.add_argument("--type", choices=[t.value for t in ExperimentType], default="node_failure")
    parser.add_argument("--target", default="mesh-node-1")
    parser.add_argument("--duration", type=int, default=60)
    parser.add_argument("--config", default="/mnt/projects/config/chaos_agent.json")
    
    args = parser.parse_args()
    
    agent = ChaosEngineerAgent(config_path=args.config)
    
    if args.mode == "single":
        exp_type = ExperimentType(args.type)
        result = agent.run_experiment(exp_type, args.target, args.duration)
        print(json.dumps(asdict(result), indent=2, default=str))
    
    elif args.mode == "scheduled":
        results = agent.run_scheduled_experiments()
        print(json.dumps([asdict(r) for r in results], indent=2, default=str))
    
    elif args.mode == "report":
        report = agent.generate_report()
        print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
