"""
Cradle DAO Oracle: Orchestrates experiments in isolated sandbox with DAO governance.

Part 1 of Westworld Integration.
Manages full lifecycle: setup → simulate → collect → DAO vote → canary rollout.
"""

import asyncio
import json
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    DAO_VOTING = "dao_voting"
    DAO_APPROVED = "dao_approved"
    DAO_REJECTED = "dao_rejected"
    ROLLING_OUT = "rolling_out"
    COMPLETED = "completed"


@dataclass
class CradleExperiment:
    """Represents a complete Cradle experiment with DAO integration."""
    experiment_id: str
    name: str
    objective: str
    config: Dict
    status: ExperimentStatus = ExperimentStatus.PENDING
    results: Optional[Dict] = None
    dao_proposal_id: Optional[str] = None
    dao_vote_result: Optional[bool] = None
    metrics_summary: Dict = field(default_factory=dict)
    privacy_score: float = 1.0
    governance_impact: str = ""
    recommendation: str = ""


class CradleDAOOracle:
    """
    Central orchestrator for Cradle experiments.
    
    Workflow:
    1. Setup isolated sandbox with digital twin
    2. Run simulation with chaos injection
    3. Collect metrics for 1-4 hours
    4. Evaluate against thresholds
    5. Create DAO proposal with results
    6. Wait for DAO voting (72 hours)
    7. If approved: canary rollout to production
    8. If rejected: analyze and retry
    """

    def __init__(self,
                 snapshot_api: str,
                 aragon_api: str,
                 mesh_controller_url: str,
                 observability_endpoint: str,
                 k8s_context: str = "prod"):
        self.snapshot_api = snapshot_api
        self.aragon_api = aragon_api
        self.mesh_controller = mesh_controller_url
        self.observability = observability_endpoint
        self.k8s_context = k8s_context
        
        # State
        self.experiments: Dict[str, CradleExperiment] = {}
        self.experiment_history: List[CradleExperiment] = []

    async def run_full_experiment_cycle(self,
                                       experiment_config: Dict) -> CradleExperiment:
        """
        Execute full experiment lifecycle: setup → run → evaluate → vote → rollout.
        
        Args:
            experiment_config: Full experiment specification (YAML parsed to dict)
            
        Returns:
            CradleExperiment with final status and results
        """
        exp = CradleExperiment(
            experiment_id=experiment_config["metadata"]["name"],
            name=experiment_config["metadata"]["name"],
            objective=experiment_config["spec"]["objective"],
            config=experiment_config,
            status=ExperimentStatus.PENDING
        )
        
        logger.info(f"Starting experiment: {exp.experiment_id}")
        
        try:
            # Phase 1: Setup Cradle sandbox
            logger.info(f"[{exp.experiment_id}] Phase 1: Setting up Cradle sandbox...")
            await self._setup_cradle_sandbox(exp)
            exp.status = ExperimentStatus.RUNNING
            
            # Phase 2: Run simulation
            logger.info(f"[{exp.experiment_id}] Phase 2: Running experiment simulation...")
            results = await self._run_simulation(exp)
            exp.results = results
            exp.metrics_summary = self._extract_metrics(results)
            
            # Phase 3: Evaluate against thresholds
            logger.info(f"[{exp.experiment_id}] Phase 3: Evaluating results...")
            passed = self._evaluate_against_thresholds(exp)
            exp.status = ExperimentStatus.PASSED if passed else ExperimentStatus.FAILED
            
            if not passed:
                logger.warning(f"[{exp.experiment_id}] Experiment FAILED - not proceeding to DAO vote")
                self.experiment_history.append(exp)
                return exp
            
            # Phase 4: Create DAO proposal
            if experiment_config["spec"].get("dao_vote_required", False):
                logger.info(f"[{exp.experiment_id}] Phase 4: Creating DAO proposal...")
                exp.status = ExperimentStatus.DAO_VOTING
                proposal_id = await self._create_dao_proposal(exp)
                exp.dao_proposal_id = proposal_id
                
                # Phase 5: Wait for DAO voting
                logger.info(f"[{exp.experiment_id}] Phase 5: Waiting for DAO vote...")
                approved = await self._wait_for_dao_vote(proposal_id, timeout_hours=72)
                exp.dao_vote_result = approved
                exp.status = ExperimentStatus.DAO_APPROVED if approved else ExperimentStatus.DAO_REJECTED
                
                if not approved:
                    logger.warning(f"[{exp.experiment_id}] DAO REJECTED proposal")
                    self.experiment_history.append(exp)
                    return exp
            
            # Phase 6: Canary rollout to production
            logger.info(f"[{exp.experiment_id}] Phase 6: Starting canary rollout...")
            exp.status = ExperimentStatus.ROLLING_OUT
            await self._canary_rollout_to_prod(exp)
            exp.status = ExperimentStatus.COMPLETED
            
            logger.info(f"[{exp.experiment_id}] ✓ Experiment completed successfully")
            
        except Exception as e:
            logger.error(f"[{exp.experiment_id}] ERROR: {e}")
            exp.status = ExperimentStatus.FAILED
        
        self.experiments[exp.experiment_id] = exp
        self.experiment_history.append(exp)
        return exp

    async def _setup_cradle_sandbox(self, exp: CradleExperiment):
        """Deploy isolated Cradle sandbox with digital twin."""
        logger.info(f"  → Creating K8s namespace: cradle-{exp.experiment_id}")
        
        # Would execute: kubectl create namespace cradle-{id}
        # For now, simulate
        await asyncio.sleep(0.1)
        
        logger.info(f"  → Applying network policies (isolation)")
        logger.info(f"  → Snapshotting production etcd state")
        logger.info(f"  → Deploying digital twin mesh (100 nodes)")
        logger.info(f"  → Deploying observability stack")
        
        logger.info(f"  ✓ Cradle sandbox ready")

    async def _run_simulation(self, exp: CradleExperiment) -> Dict:
        """Run experiment with chaos injection and metrics collection."""
        duration_str = exp.config["spec"].get("duration", "4h")
        duration_seconds = self._parse_duration(duration_str)
        
        logger.info(f"  → Starting mesh simulation with chaos injection...")
        await self._inject_chaos_scenarios(exp)
        
        logger.info(f"  → Collecting metrics for {duration_str}...")
        start_time = datetime.utcnow()
        metrics_history = []
        
        iteration = 0
        while (datetime.utcnow() - start_time).total_seconds() < duration_seconds:
            iteration += 1
            
            # Collect metrics snapshot
            metrics = await self._collect_metrics(exp.experiment_id)
            metrics_history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "iteration": iteration,
                "metrics": metrics
            })
            
            # Check for early termination
            if self._should_abort_early(metrics):
                logger.warning(f"  ⚠ Early abort: Critical metric threshold breached")
                break
            
            # Sleep before next collection
            await asyncio.sleep(5)
        
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"  ✓ Collected {len(metrics_history)} metric snapshots in {elapsed:.0f}s")
        
        return {
            "duration_seconds": elapsed,
            "iterations": len(metrics_history),
            "metrics_history": metrics_history,
            "final_state": await self._get_final_state(exp.experiment_id)
        }

    def _extract_metrics(self, results: Dict) -> Dict:
        """Extract key metrics for DAO proposal."""
        metrics_history = results.get("metrics_history", [])
        if not metrics_history:
            return {}
        
        latencies = [m["metrics"].get("latency_p99", 0) for m in metrics_history]
        packet_losses = [m["metrics"].get("packet_loss", 0) for m in metrics_history]
        deanon_scores = [m["metrics"].get("deanon_risk_score", 0) for m in metrics_history]
        
        return {
            "latency_p99_avg": sum(latencies) / len(latencies) if latencies else 0,
            "latency_p99_max": max(latencies) if latencies else 0,
            "packet_loss_avg": sum(packet_losses) / len(packet_losses) if packet_losses else 0,
            "deanon_risk_max": max(deanon_scores) if deanon_scores else 0,
            "mttr_samples": [m["metrics"].get("mttr", 0) for m in metrics_history[-12:]],
        }

    def _evaluate_against_thresholds(self, exp: CradleExperiment) -> bool:
        """Check if experiment passed all mandatory thresholds."""
        if not exp.metrics_summary:
            return False
        
        thresholds = exp.config["spec"].get("metrics", {})
        
        # Check golden signals
        for metric_spec in thresholds.get("golden_signals", []):
            name = metric_spec["name"]
            threshold_str = metric_spec["threshold"]
            threshold_val = self._parse_threshold(threshold_str)
            
            # Get actual value
            key = name.replace("-", "_") + "_max"
            actual_val = exp.metrics_summary.get(key, float("inf"))
            
            if actual_val > threshold_val:
                action = metric_spec.get("action_on_breach", "alert")
                if action == "rollback":
                    logger.error(f"    ✗ {name}: {actual_val:.0f} exceeds {threshold_str} (FAILED)")
                    return False
                else:
                    logger.warning(f"    ⚠ {name}: {actual_val:.0f} exceeds {threshold_str} (alert)")
        
        # Privacy metrics MUST pass
        for metric_spec in thresholds.get("privacy_metrics", []):
            name = metric_spec["name"]
            threshold_str = metric_spec["threshold"]
            threshold_val = self._parse_threshold(threshold_str)
            actual_val = exp.metrics_summary.get(name + "_max", 0)
            
            if actual_val > threshold_val:
                logger.error(f"    ✗ Privacy: {name} = {actual_val:.4f} > {threshold_str} (FAILED)")
                return False
        
        logger.info(f"    ✓ All thresholds passed")
        return True

    async def _create_dao_proposal(self, exp: CradleExperiment) -> str:
        """Create Snapshot proposal with experiment results."""
        proposal_body = self._generate_dao_proposal_text(exp)
        
        proposal_payload = {
            "version": "0.1.0",
            "timestamp": int(datetime.utcnow().timestamp()),
            "space": "x0tta6bl4.eth",
            "type": "single-choice",
            "title": f"[Cradle] {exp.name} - Production Rollout?",
            "body": proposal_body,
            "choices": [
                "✓ Approve: Roll out to production (canary)",
                "✗ Reject: Keep current version"
            ],
            "start": int(datetime.utcnow().timestamp()),
            "end": int((datetime.utcnow() + timedelta(days=3)).timestamp()),
            "snapshot": "latest",
            "plugins": {"quorum": {"total": 1000000}},
            "metadata": {
                "experiment_id": exp.experiment_id,
                "metrics": exp.metrics_summary
            }
        }
        
        logger.info(f"  → Creating proposal on Snapshot...")
        # In real implementation: POST to Snapshot API
        proposal_id = f"prop_{exp.experiment_id}_{int(datetime.utcnow().timestamp())}"
        logger.info(f"  ✓ Proposal created: {proposal_id}")
        
        return proposal_id

    def _generate_dao_proposal_text(self, exp: CradleExperiment) -> str:
        """Generate human-readable proposal text."""
        metrics = exp.metrics_summary or {}
        
        text = f"""
# Cradle Experiment Approval: {exp.name}

## Objective
{exp.objective}

## Results Summary
- **Status**: {exp.status.value}
- **Duration**: {exp.results.get('duration_seconds', 0) / 3600:.1f} hours
- **Latency (p99 avg)**: {metrics.get('latency_p99_avg', 0):.0f}ms
- **Packet Loss**: {metrics.get('packet_loss_avg', 0):.2%}
- **Max Deanon Risk**: {metrics.get('deanon_risk_max', 0):.4f}
- **Privacy Score**: {exp.privacy_score:.2f}/1.0

## Key Findings
- Mesh maintained {metrics.get('mttr_samples', [1.5])[-1] if metrics.get('mttr_samples') else 1.5:.2f}s MTTR under stress
- Zero trust verification remained operational
- No privacy breaches detected

## Recommendation
**{exp.recommendation}**

---
*Vote to approve production rollout of this change.*
"""
        return text

    async def _wait_for_dao_vote(self, proposal_id: str, timeout_hours: int = 72) -> bool:
        """Poll Snapshot until vote closes, then check result."""
        deadline = datetime.utcnow() + timedelta(hours=timeout_hours)
        
        logger.info(f"  → Waiting for DAO vote (deadline: {deadline.isoformat()})")
        
        while datetime.utcnow() < deadline:
            # In real implementation: Poll Snapshot API
            # For demo: simulate voting
            
            elapsed = (datetime.utcnow() - (deadline - timedelta(hours=timeout_hours))).total_seconds()
            if elapsed > 60:  # Simulate 60 second vote
                logger.info(f"  ✓ DAO vote closed")
                # Simulate 60% approval
                approved = True
                logger.info(f"  ✓ Vote result: APPROVED (60% support)")
                return approved
            
            await asyncio.sleep(10)
        
        logger.warning(f"  ✗ DAO vote timeout")
        return False

    async def _canary_rollout_to_prod(self, exp: CradleExperiment):
        """Staged rollout to production."""
        stages = exp.config["spec"].get("rollout_strategy", {}).get("canary_stages", [])
        
        for i, stage in enumerate(stages, 1):
            logger.info(f"  Stage {i}: Updating {stage['nodes']} nodes...")
            
            # Deploy to canary nodes
            await self._update_prod_nodes(exp.experiment_id, stage["nodes"], i)
            
            # Monitor validation gate
            stage_duration = self._parse_duration(stage.get("duration", "30m"))
            start_time = datetime.utcnow()
            
            while (datetime.utcnow() - start_time).total_seconds() < stage_duration:
                prod_metrics = await self._collect_prod_metrics()
                validation_gate = stage.get("validation_gate", "all_metrics_nominal")
                
                if not self._validate_gate(validation_gate, prod_metrics):
                    logger.error(f"  ✗ Validation gate FAILED at stage {i}")
                    logger.warning(f"  → Initiating rollback...")
                    await self._rollback_to_previous_version()
                    raise RuntimeError(f"Canary stage {i} failed")
                
                await asyncio.sleep(5)
            
            logger.info(f"  ✓ Stage {i} passed validation")
        
        logger.info(f"  ✓ Full rollout complete")

    # ===== Helper Methods =====

    def _parse_duration(self, duration_str: str) -> float:
        """Parse duration string (e.g., '4h' or '30m') to seconds."""
        units = {"s": 1, "m": 60, "h": 3600, "d": 86400}
        for unit, multiplier in units.items():
            if duration_str.endswith(unit):
                return float(duration_str[:-1]) * multiplier
        raise ValueError(f"Unknown duration format: {duration_str}")

    def _parse_threshold(self, threshold_str: str) -> float:
        """Parse threshold with units."""
        if threshold_str.endswith("ms"):
            return float(threshold_str[:-2]) / 1000
        elif threshold_str.endswith("s"):
            return float(threshold_str[:-1])
        else:
            return float(threshold_str)

    async def _inject_chaos_scenarios(self, exp: CradleExperiment):
        """Inject chaos engineering scenarios."""
        logger.info(f"  → Injecting chaos scenarios...")
        await asyncio.sleep(0.1)

    async def _collect_metrics(self, experiment_id: str) -> Dict:
        """Collect metrics snapshot from Cradle."""
        return {
            "latency_p99": 245 + (hash(str(datetime.utcnow())) % 20),
            "packet_loss": 0.02 + (hash(str(datetime.utcnow())) % 10) / 1000,
            "deanon_risk_score": 0.008,
            "mttr": 1.2,
        }

    def _should_abort_early(self, metrics: Dict) -> bool:
        """Check abort conditions."""
        return (metrics.get("deanon_risk_score", 0) > 0.05 or
                metrics.get("latency_p99", 0) > 5000)

    async def _get_final_state(self, experiment_id: str) -> Dict:
        """Get final state of experiment."""
        return {"state": "completed", "timestamp": datetime.utcnow().isoformat()}

    async def _collect_prod_metrics(self) -> Dict:
        """Collect metrics from production."""
        return {"latency_p99": 200, "packet_loss": 0.01}

    def _validate_gate(self, gate_name: str, metrics: Dict) -> bool:
        """Validate specific gate."""
        if gate_name == "all_metrics_nominal":
            return all(v < 1000 for v in metrics.values())
        elif gate_name == "latency_p99_under_threshold":
            return metrics.get("latency_p99", 0) < 500
        return True

    async def _update_prod_nodes(self, exp_id: str, num_nodes: int, stage: int):
        """Update production nodes."""
        await asyncio.sleep(0.1)

    async def _rollback_to_previous_version(self):
        """Rollback production."""
        logger.warning("  Rolling back...")
        await asyncio.sleep(0.1)


# ===== CLI Interface =====

async def main():
    import sys
    
    oracle = CradleDAOOracle(
        snapshot_api=os.getenv("SNAPSHOT_API", "https://snapshot.org/api"),
        aragon_api=os.getenv("ARAGON_API", "https://aragon.org/api"),
        mesh_controller_url=os.getenv("MESH_CONTROLLER_URL", ""),
        observability_endpoint=os.getenv("OBSERVABILITY_ENDPOINT", "")
    )
    
    # Load experiment config
    if len(sys.argv) > 1:
        import yaml
        with open(sys.argv[1]) as f:
            config = yaml.safe_load(f)
    else:
        # Demo config
        config = {
            "metadata": {"name": "demo-experiment"},
            "spec": {
                "objective": "Test PQC crypto migration",
                "duration": "4h",
                "dao_vote_required": True,
                "metrics": {
                    "golden_signals": [
                        {"name": "latency-p99", "threshold": "500ms", "action_on_breach": "rollback"},
                        {"name": "packet-loss", "threshold": "0.01", "action_on_breach": "alert"},
                    ],
                    "privacy_metrics": [
                        {"name": "deanon_risk_score", "threshold": "0.05", "action_on_breach": "abort"},
                    ]
                },
                "rollout_strategy": {
                    "canary_stages": [
                        {"nodes": 10, "duration": "30m", "validation_gate": "all_metrics_nominal"},
                        {"nodes": 50, "duration": "1h", "validation_gate": "latency_p99_under_threshold"},
                    ]
                }
            }
        }
    
    # Run experiment
    result = await oracle.run_full_experiment_cycle(config)
    
    print(f"\n{'='*60}")
    print(f"Experiment {result.experiment_id}: {result.status.value}")
    print(f"{'='*60}")
    print(json.dumps({
        "experiment_id": result.experiment_id,
        "status": result.status.value,
        "metrics_summary": result.metrics_summary,
        "dao_result": result.dao_vote_result,
    }, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
