"""
DAO Proposal Executor Webhook — x0tta6bl4
=========================================

Listens for `ProposalExecuted(uint256 indexed proposalId)` events emitted by
the MeshGovernance contract (Base Sepolia / any EVM chain) and automatically
runs `helm upgrade` for the matching chart.

Architecture:
  - Polling loop: `eth_getLogs` every POLL_INTERVAL_SECONDS (avoids ws deps)
  - Idempotent: each proposalId is processed at most once (persisted to
    `PROCESSED_FILE`)
  - Dry-run mode: set ENV=DRY_RUN=true to log the helm command without running
  - Audit trail: every execution is appended to LEDGER_PATH (JSONL)

Usage (standalone):
  python -m src.dao.proposal_executor_webhook

Environment variables:
  BASE_SEPOLIA_RPC              Chain RPC URL
  MESH_GOVERNANCE_ADDRESS       MeshGovernance contract address
  HELM_RELEASE_NAME             Helm release name (default: mesh-op)
  HELM_CHART_PATH               Chart path (default: charts/x0tta-mesh-operator/)
  HELM_NAMESPACE                Kubernetes namespace (default: default)
  HELM_EXTRA_ARGS               Space-separated extra --set flags
  EXECUTOR_POLL_INTERVAL        Seconds between polls (default: 15)
  EXECUTOR_START_BLOCK          Start scanning from this block (default: "latest-200")
  EXECUTOR_PROCESSED_FILE       JSON file to persist seen proposal IDs
  EXECUTOR_LEDGER_PATH          JSONL audit trail (default: src/dao/deployments/audit.jsonl)
  EXECUTOR_DRY_RUN              If "true", print helm command but don't run it
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import (
    SafeActuator,
    SafeActuatorEvidenceMetadata,
    SafeActuatorResult,
)
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Optional Web3 import
# ---------------------------------------------------------------------------
try:
    from web3 import Web3
    WEB3_AVAILABLE = True
except ImportError:
    WEB3_AVAILABLE = False
    logger.warning("web3 not installed — executor running in stub mode")

# ---------------------------------------------------------------------------
# Constants / defaults
# ---------------------------------------------------------------------------
_DEPLOYMENTS_DIR = Path(__file__).parent / "deployments"
_DEFAULT_LEDGER = _DEPLOYMENTS_DIR / "audit.jsonl"
_DEFAULT_PROCESSED = _DEPLOYMENTS_DIR / "executed_proposals.json"
_ABI_PATH = (
    Path(__file__).parent
    / "contracts"
    / "artifacts"
    / "contracts"
    / "MeshGovernance.sol"
    / "MeshGovernance.json"
)

_PROPOSAL_EXECUTED_TOPIC = (
    "0xc3be0e6a9a4297ab5ade6d0c44cf9a5b53b0c024a9e4c12b28d01b9c0671c98"
)

_SERVICE_AGENT = "dao-proposal-executor"
_HELM_UPGRADE_RESOURCE = "dao:proposal_executor:helm_upgrade"
_HELM_EXECUTOR_STRONG_CLAIM_IDS = (
    "production_rollout",
    "production_readiness",
    "dataplane_delivery",
    "customer_traffic",
    "external_settlement_finality",
)

HELM_EXECUTOR_CLAIM_BOUNDARY = (
    "DAO proposal executor event only. It records local identity, policy, "
    "and safe actuator state for helm upgrade attempts; it is not proof of a "
    "successful production rollout without operator-captured deployment evidence."
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_bool(name: str, default: bool = False) -> bool:
    raw = _env(name)
    if not raw:
        return default
    return raw.lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int = 0) -> int:
    raw = _env(name, str(default))
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass
class ExecutorConfig:
    rpc_url: str = field(default_factory=lambda: _env("BASE_SEPOLIA_RPC", "https://sepolia.base.org"))
    governance_address: str = field(default_factory=lambda: _env("MESH_GOVERNANCE_ADDRESS"))
    helm_release: str = field(default_factory=lambda: _env("HELM_RELEASE_NAME", "mesh-op"))
    helm_chart: str = field(default_factory=lambda: _env("HELM_CHART_PATH", "charts/x0tta-mesh-operator/"))
    helm_namespace: str = field(default_factory=lambda: _env("HELM_NAMESPACE", "default"))
    helm_extra_args: List[str] = field(
        default_factory=lambda: _env("HELM_EXTRA_ARGS", "").split() if _env("HELM_EXTRA_ARGS") else []
    )
    poll_interval: int = field(default_factory=lambda: _env_int("EXECUTOR_POLL_INTERVAL", 15))
    start_block_offset: int = field(default_factory=lambda: _env_int("EXECUTOR_START_BLOCK_OFFSET", 200))
    processed_file: Path = field(default_factory=lambda: Path(_env("EXECUTOR_PROCESSED_FILE", str(_DEFAULT_PROCESSED))))
    ledger_path: Path = field(default_factory=lambda: Path(_env("EXECUTOR_LEDGER_PATH", str(_DEFAULT_LEDGER))))
    dry_run: bool = field(default_factory=lambda: _env_bool("EXECUTOR_DRY_RUN"))


# ---------------------------------------------------------------------------
# Processed proposals store (idempotency)
# ---------------------------------------------------------------------------

class ProcessedStore:
    """Persists the set of already-executed proposal IDs to disk."""

    def __init__(self, path: Path):
        self._path = path
        self._ids: Set[int] = self._load()

    def _load(self) -> Set[int]:
        if self._path.exists():
            try:
                data = json.loads(self._path.read_text())
                return set(int(x) for x in data.get("executed", []))
            except Exception as exc:
                logger.warning("Failed to load processed store: %s", exc)
        return set()

    def contains(self, proposal_id: int) -> bool:
        return proposal_id in self._ids

    def add(self, proposal_id: int) -> None:
        self._ids.add(proposal_id)
        self._persist()

    def _persist(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps({"executed": sorted(self._ids)}, indent=2))


# ---------------------------------------------------------------------------
# Helm runner
# ---------------------------------------------------------------------------

class HelmRunner:
    """Wraps `helm upgrade` with configurable dry-run and audit trail."""

    def __init__(
        self,
        config: ExecutorConfig,
        *,
        node_id: str = "dao-proposal-executor",
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        policy_engine: Optional[Any] = None,
        require_policy: Optional[bool] = None,
        source_agent: str = _SERVICE_AGENT,
        spiffe_id: Optional[str] = None,
        did: Optional[str] = None,
        wallet_address: Optional[str] = None,
        safe_actuator: Optional[SafeActuator] = None,
    ):
        self.config = config
        self.node_id = node_id
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else _env_bool("X0TTA6BL4_DAO_PROPOSAL_EXECUTOR_POLICY_REQUIRED", False)
            or _env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="dao-proposal-executor")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id if spiffe_id is not None else service_identity["spiffe_id"],
            "did": did if did is not None else service_identity["did"],
            "wallet_address": (
                wallet_address
                if wallet_address is not None
                else service_identity["wallet_address"]
            ),
        }
        self.safe_actuator = safe_actuator or SafeActuator(
            self._execute_upgrade_through_actuator
        )
        self._last_helm_result: Optional[HelmResult] = None
        self._last_helm_duration_ms: Optional[int] = None

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except Exception as exc:
            logger.error("Failed to initialize DAO proposal executor EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize DAO proposal executor policy engine: %s", exc)
            return None

    @staticmethod
    def _policy_allowed(decision: Any) -> bool:
        return normalize_policy_allowed(decision)

    @staticmethod
    def _policy_reason(decision: Any) -> str:
        return normalize_policy_reason(decision)

    @staticmethod
    def _policy_rules(decision: Any) -> list[str]:
        return normalize_policy_rules(decision)

    @classmethod
    def _safe_value(cls, key: str, value: Any, depth: int = 0) -> Any:
        blocked_fragments = ("secret", "password", "token", "key", "private", "command")
        if any(fragment in str(key).lower() for fragment in blocked_fragments):
            return "<redacted>"
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, dict) and depth < 3:
            return {
                str(child_key): cls._safe_value(str(child_key), child_value, depth + 1)
                for child_key, child_value in value.items()
            }
        if isinstance(value, list) and depth < 3:
            return [cls._safe_value(key, item, depth + 1) for item in value]
        return str(value)

    @classmethod
    def _safe_context(cls, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            str(key): cls._safe_value(str(key), value)
            for key, value in context.items()
        }

    @staticmethod
    def _helm_cross_plane_claim_gate() -> Dict[str, Any]:
        return {
            "schema": "x0tta6bl4.cross_plane_proof_gate.v1",
            "surface": "dao.proposal_executor.helm_upgrade.safe_actuator",
            "decision": "CROSS_PLANE_CLAIMS_BLOCKED",
            "allowed": False,
            "requested_claim_ids": list(_HELM_EXECUTOR_STRONG_CLAIM_IDS),
            "blockers": ["dao_proposal_executor_helm_upgrade_local_action_only"],
            "claim_boundary": (
                "DAO proposal executor helm metadata records a local guarded Helm "
                "command attempt only. Production rollout, readiness, dataplane, "
                "customer traffic, and settlement-finality claims need external "
                "cross-plane evidence."
            ),
        }

    @classmethod
    def _helm_claim_gate(
        cls,
        *,
        action: str,
        context: Dict[str, Any],
        success: bool,
        simulated: bool,
        action_recognized: bool,
        return_code: Optional[int],
    ) -> Dict[str, Any]:
        local_helm_execution_allowed = (
            action_recognized
            and success
            and not simulated
            and return_code == 0
        )
        blockers = [
            "production_rollout_requires_deployment_evidence",
            "production_readiness_requires_cross_plane_proof",
            "dataplane_claim_requires_dedicated_dataplane_probe",
            "settlement_finality_requires_external_chain_evidence",
        ]
        if not action_recognized:
            blockers.append("unknown_dao_proposal_executor_action")
        if simulated:
            blockers.append("safe_actuator_result_simulated")
        if not success:
            blockers.append("helm_upgrade_not_successful")
        if return_code is None:
            blockers.append("helm_return_code_missing")
        if return_code not in (None, 0):
            blockers.append("helm_return_code_nonzero")

        return {
            "schema": "x0tta6bl4.dao_proposal_executor.safe_actuator_claim_gate.v1",
            "surface": "dao.proposal_executor.helm_upgrade",
            "operation": "helm_upgrade",
            "action": str(action or ""),
            "resource": _HELM_UPGRADE_RESOURCE,
            "proposal_id_present": context.get("proposal_id") is not None,
            "helm_command_present": bool(context.get("command")),
            "safe_actuator_result_recorded": True,
            "local_safe_actuator_success": bool(success),
            "return_code_observed": return_code is not None,
            "local_helm_command_execution_claim_allowed": local_helm_execution_allowed,
            "production_rollout_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "dataplane_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "external_settlement_finality_claim_allowed": False,
            "traffic_shift_claim_allowed": False,
            "live_customer_traffic_claim_allowed": False,
            "blocked_claim_ids": list(_HELM_EXECUTOR_STRONG_CLAIM_IDS),
            "blockers": blockers,
            "payloads_redacted": True,
            "redacted": True,
            "claim_boundary": (
                "HelmRunner SafeActuator metadata proves only a local guarded Helm "
                "command attempt and its bounded process outcome. It does not prove "
                "production rollout, production readiness, dataplane or customer "
                "traffic delivery, or external settlement finality."
            ),
        }

    @classmethod
    def _helm_evidence_metadata(
        cls,
        *,
        action: str,
        context: Dict[str, Any],
        success: bool,
        simulated: bool = False,
        action_recognized: bool = True,
        return_code: Optional[int] = None,
        duration_ms: Optional[int] = None,
    ) -> SafeActuatorEvidenceMetadata:
        claim_gate = cls._helm_claim_gate(
            action=action,
            context=context,
            success=success,
            simulated=simulated,
            action_recognized=action_recognized,
            return_code=return_code,
        )
        evidence = {
            "source_agents": [_SERVICE_AGENT],
            "event_ids": [],
            "resource": _HELM_UPGRADE_RESOURCE,
            "operation": "helm_upgrade",
            "action": str(action or ""),
            "proposal_id_present": context.get("proposal_id") is not None,
            "helm_command_present": bool(context.get("command")),
            "helm_command_redacted": True,
            "extra_set_redacted": True,
            "return_code": return_code,
            "return_code_observed": return_code is not None,
            "duration_ms": int(duration_ms or 0),
            "simulated": bool(simulated),
            "raw_values_redacted": True,
            "raw_context_values_redacted": True,
            "raw_command_output_redacted": True,
            "payloads_redacted": True,
            "redacted": True,
        }
        return SafeActuatorEvidenceMetadata.from_value(
            {
                "claim_gate": claim_gate,
                "cross_plane_claim_gate": cls._helm_cross_plane_claim_gate(),
                "evidence": evidence,
                "source_agents": [_SERVICE_AGENT],
                "event_ids": [],
                "claim_boundary": claim_gate["claim_boundary"],
                "redacted": True,
            }
        )

    def _publish_upgrade_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        context: Dict[str, Any],
        result: Optional["HelmResult"] = None,
        reason: str = "",
        policy_decision: Any = None,
        simulated: Optional[bool] = None,
        safe_actuator_evidence_metadata: Optional[SafeActuatorEvidenceMetadata] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        reason_redacted = bool(
            reason
            and stage in {"actuator_completed", "actuator_failed", "actuator_simulated"}
        )
        payload = {
            "component": "dao.proposal_executor_webhook",
            "stage": stage,
            "operation": "helm_upgrade",
            "resource": _HELM_UPGRADE_RESOURCE,
            "proposal_id": context.get("proposal_id"),
            "helm_release": self.config.helm_release,
            "helm_chart": self.config.helm_chart,
            "helm_namespace": self.config.helm_namespace,
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "success": result.success if result is not None else None,
            "dry_run": result.dry_run if result is not None else context.get("dry_run"),
            "simulated": simulated,
            "returncode": result.returncode if result is not None else None,
            "reason": "<redacted>" if reason_redacted else reason,
            "reason_redacted": reason_redacted,
            "policy_required": self.require_policy or self.policy_engine is not None,
            "policy_allowed": self._policy_allowed(policy_decision)
            if policy_decision is not None
            else None,
            "policy_reason": self._policy_reason(policy_decision)
            if policy_decision is not None
            else "",
            "matched_rules": self._policy_rules(policy_decision)
            if policy_decision is not None
            else [],
            "safe_actuator": True,
            "safe_actuator_evidence_metadata": (
                safe_actuator_evidence_metadata.to_dict()
                if safe_actuator_evidence_metadata is not None
                else SafeActuatorEvidenceMetadata().to_dict()
            ),
            "claim_boundary": HELM_EXECUTOR_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=8)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish DAO proposal executor event: %s", exc)
            return None

    def _evaluate_upgrade_policy(self) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "DAO proposal executor policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "DAO proposal executor SPIFFE identity is required for policy evaluation"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource=_HELM_UPGRADE_RESOURCE,
                workload_type="dao-proposal-executor",
            )
        except Exception as exc:
            return False, None, f"DAO proposal executor policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, (
                self._policy_reason(decision) or "DAO proposal executor policy denied helm upgrade"
            )
        return True, decision, self._policy_reason(decision)

    @staticmethod
    def _build_command(config: ExecutorConfig, proposal_id: int, extra_set: Optional[Dict[str, str]]) -> tuple[List[str], str]:
        cmd = [
            "helm", "upgrade", "--install",
            config.helm_release,
            config.helm_chart,
            "--namespace", config.helm_namespace,
            "--wait",
            "--timeout", "5m",
            "--set", f"global.dao.proposalId={proposal_id}",
            "--set", "global.dao.autoUpgrade=true",
        ]
        cmd.extend(config.helm_extra_args)
        if extra_set:
            for k, v in extra_set.items():
                cmd.extend(["--set", f"{k}={v}"])
        return cmd, " ".join(cmd)

    def _execute_upgrade_through_actuator(
        self,
        action: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if action != "helm_upgrade":
            return SafeActuatorResult(
                False,
                f"unknown DAO proposal executor action: {action}",
                evidence_metadata=self._helm_evidence_metadata(
                    action=action,
                    context=context,
                    success=False,
                    action_recognized=False,
                ),
            )
        start = time.monotonic()
        result = self._upgrade_internal(
            proposal_id=int(context.get("proposal_id", 0)),
            command=list(context.get("command", [])),
            command_str=str(context.get("command_str", "")),
        )
        duration_ms = int((time.monotonic() - start) * 1000)
        self._last_helm_result = result
        self._last_helm_duration_ms = duration_ms
        return SafeActuatorResult(
            result.success,
            result.stderr or result.stdout,
            simulated=result.dry_run,
            evidence_metadata=self._helm_evidence_metadata(
                action=action,
                context=context,
                success=result.success,
                simulated=result.dry_run,
                return_code=result.returncode,
                duration_ms=duration_ms,
            ),
        )

    def upgrade(self, proposal_id: int, extra_set: Optional[Dict[str, str]] = None) -> HelmResult:
        """
        Run `helm upgrade` for the configured release.

        Args:
            proposal_id: The on-chain proposal ID that triggered this upgrade
            extra_set: Additional --set key=value pairs (e.g. from proposal metadata)

        Returns:
            HelmResult with success flag, command, and stdout/stderr
        """
        cmd, cmd_str = self._build_command(self.config, proposal_id, extra_set)
        context = {
            "proposal_id": proposal_id,
            "extra_set": extra_set or {},
            "command": cmd,
            "command_str": cmd_str,
            "dry_run": self.config.dry_run,
        }
        self._last_helm_result = None
        self._last_helm_duration_ms = None
        self._publish_upgrade_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            context=context,
        )
        policy_allowed, policy_decision, policy_reason = self._evaluate_upgrade_policy()
        if not policy_allowed:
            result = HelmResult(
                proposal_id=proposal_id,
                success=False,
                command=cmd_str,
                stdout="",
                stderr=policy_reason,
                dry_run=self.config.dry_run,
                returncode=0,
            )
            self._publish_upgrade_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                context=context,
                result=result,
                reason=policy_reason,
                policy_decision=policy_decision,
                simulated=False,
            )
            return result

        self._publish_upgrade_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )
        actuator_result = self.safe_actuator.execute("helm_upgrade", context)
        helm_result_observed = self._last_helm_result is not None
        result = self._last_helm_result or HelmResult(
            proposal_id=proposal_id,
            success=actuator_result.success,
            command=cmd_str,
            stdout="",
            stderr=actuator_result.reason,
            dry_run=bool(actuator_result.simulated),
            returncode=0,
        )
        simulated = bool(actuator_result.simulated or result.dry_run)
        if not actuator_result.evidence_metadata.claim_gate:
            actuator_result = SafeActuatorResult(
                success=actuator_result.success,
                reason=actuator_result.reason,
                simulated=actuator_result.simulated,
                evidence_metadata=self._helm_evidence_metadata(
                    action="helm_upgrade",
                    context=context,
                    success=result.success,
                    simulated=simulated,
                    return_code=result.returncode if helm_result_observed else None,
                    duration_ms=getattr(self, "_last_helm_duration_ms", None),
                ),
            )
        event_type = (
            EventType.PIPELINE_STAGE_END
            if result.success and not simulated
            else EventType.TASK_FAILED
            if not result.success or simulated
            else EventType.PIPELINE_STAGE_END
        )
        stage = (
            "actuator_completed"
            if result.success and not simulated
            else "actuator_simulated"
            if simulated
            else "actuator_failed"
        )
        self._publish_upgrade_event(
            event_type,
            stage=stage,
            context=context,
            result=result,
            reason=actuator_result.reason or result.stderr,
            policy_decision=policy_decision,
            simulated=simulated,
            safe_actuator_evidence_metadata=actuator_result.evidence_metadata,
        )
        return result

    def _upgrade_internal(self, *, proposal_id: int, command: List[str], command_str: str) -> HelmResult:
        logger.info("[DAO Executor] helm command: <redacted>")
        if self.config.dry_run:
            logger.info("[DAO Executor] DRY_RUN — helm not executed")
            return HelmResult(
                proposal_id=proposal_id,
                success=True,
                command=command_str,
                stdout="(dry-run)",
                stderr="",
                dry_run=True,
            )

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=360,
            )
            success = proc.returncode == 0
            if not success:
                logger.error("[DAO Executor] helm failed (rc=%d): %s", proc.returncode, proc.stderr)
            else:
                logger.info("[DAO Executor] helm upgrade succeeded for proposal %d", proposal_id)
            return HelmResult(
                proposal_id=proposal_id,
                success=success,
                command=command_str,
                stdout=proc.stdout,
                stderr=proc.stderr,
                dry_run=False,
                returncode=proc.returncode,
            )
        except subprocess.TimeoutExpired:
            logger.error("[DAO Executor] helm timed out for proposal %d", proposal_id)
            return HelmResult(
                proposal_id=proposal_id,
                success=False,
                command=command_str,
                stdout="",
                stderr="helm timed out after 360s",
                dry_run=False,
            )
        except FileNotFoundError:
            logger.error("[DAO Executor] helm binary not found")
            return HelmResult(
                proposal_id=proposal_id,
                success=False,
                command=command_str,
                stdout="",
                stderr="helm binary not found in PATH",
                dry_run=False,
            )


@dataclass
class HelmResult:
    proposal_id: int
    success: bool
    command: str
    stdout: str = ""
    stderr: str = ""
    dry_run: bool = False
    returncode: int = 0


# ---------------------------------------------------------------------------
# Ledger writer
# ---------------------------------------------------------------------------

def _append_ledger(ledger: Path, record: Dict[str, Any]) -> None:
    ledger.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger, "a") as f:
        f.write(json.dumps(record) + "\n")


# ---------------------------------------------------------------------------
# Event listener
# ---------------------------------------------------------------------------

class ProposalExecutedListener:
    """
    Polls `eth_getLogs` for ProposalExecuted events and triggers HelmRunner.

    Designed for robustness:
      - Tolerates RPC failures (logs and retries on next poll)
      - Idempotent (processed IDs persisted to disk)
      - Each proposal triggers exactly one helm upgrade
    """

    def __init__(self, config: ExecutorConfig):
        self.config = config
        self.processed = ProcessedStore(config.processed_file)
        self.helm = HelmRunner(config)
        self._w3: Optional[Any] = None  # web3 instance, lazy-init
        self._contract: Optional[Any] = None
        self._last_block: Optional[int] = None

    # ------------------------------------------------------------------
    # Web3 connection (lazy)
    # ------------------------------------------------------------------

    def _connect(self) -> bool:
        if not WEB3_AVAILABLE:
            logger.error("[DAO Executor] web3 not installed — cannot connect")
            return False
        if not self.config.governance_address:
            logger.error("[DAO Executor] MESH_GOVERNANCE_ADDRESS not set")
            return False
        try:
            self._w3 = Web3(Web3.HTTPProvider(self.config.rpc_url))
            if not self._w3.is_connected():
                logger.warning("[DAO Executor] RPC not reachable: %s", self.config.rpc_url)
                return False
            abi = self._load_abi()
            self._contract = self._w3.eth.contract(
                address=Web3.to_checksum_address(self.config.governance_address),
                abi=abi,
            )
            logger.info("[DAO Executor] connected to %s", self.config.rpc_url)
            return True
        except Exception as exc:
            logger.error("[DAO Executor] connection failed: %s", exc)
            return False

    @staticmethod
    def _load_abi() -> List[Dict]:
        try:
            data = json.loads(_ABI_PATH.read_text())
            return data["abi"]
        except Exception as exc:
            logger.warning("[DAO Executor] could not load ABI from file: %s", exc)
            # Minimal fallback ABI for ProposalExecuted
            return [
                {
                    "anonymous": False,
                    "inputs": [
                        {"indexed": True, "name": "proposalId", "type": "uint256"}
                    ],
                    "name": "ProposalExecuted",
                    "type": "event",
                }
            ]

    # ------------------------------------------------------------------
    # Single poll cycle
    # ------------------------------------------------------------------

    def poll_once(self) -> List[HelmResult]:
        """
        Fetch new ProposalExecuted events since last poll and process each.

        Returns list of HelmResult (one per new proposal handled).
        """
        if self._w3 is None or not self._w3.is_connected():
            if not self._connect():
                return []

        try:
            latest = self._w3.eth.block_number
        except Exception as exc:
            logger.warning("[DAO Executor] could not get latest block: %s", exc)
            self._w3 = None
            return []

        from_block = self._last_block or max(0, latest - self.config.start_block_offset)
        to_block = latest

        if from_block > to_block:
            return []

        try:
            logs = self._contract.events.ProposalExecuted.get_logs(
                from_block=from_block,
                to_block=to_block,
            )
        except Exception as exc:
            logger.warning("[DAO Executor] get_logs failed: %s", exc)
            self._w3 = None
            return []

        self._last_block = to_block + 1

        results: List[HelmResult] = []
        for log in logs:
            proposal_id = int(log["args"]["proposalId"])
            if self.processed.contains(proposal_id):
                logger.debug("[DAO Executor] proposal %d already processed — skip", proposal_id)
                continue

            logger.info("[DAO Executor] new ProposalExecuted event: proposalId=%d", proposal_id)
            result = self._handle(proposal_id, log)
            results.append(result)

        return results

    def _handle(self, proposal_id: int, log: Dict[str, Any]) -> HelmResult:
        """Process a single ProposalExecuted event."""
        result = self.helm.upgrade(proposal_id)

        record = {
            "event": "ProposalExecuted",
            "proposal_id": proposal_id,
            "tx_hash": log.get("transactionHash", b"").hex()
                if hasattr(log.get("transactionHash", b""), "hex")
                else str(log.get("transactionHash", "")),
            "block_number": log.get("blockNumber"),
            "helm_success": result.success,
            "helm_command": result.command,
            "helm_stderr": result.stderr[-500:] if result.stderr else "",
            "dry_run": result.dry_run,
            "executed_at": datetime.now(timezone.utc).isoformat(),
        }
        _append_ledger(self.config.ledger_path, record)

        if result.success:
            self.processed.add(proposal_id)
            logger.info("[DAO Executor] proposal %d helm upgrade complete", proposal_id)
        else:
            logger.error(
                "[DAO Executor] proposal %d helm upgrade FAILED — will retry on next poll",
                proposal_id,
            )

        return result

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self, max_iterations: Optional[int] = None) -> None:
        """
        Run the polling loop indefinitely (or for max_iterations in tests).
        """
        logger.info(
            "[DAO Executor] starting poll loop (interval=%ds, dry_run=%s)",
            self.config.poll_interval,
            self.config.dry_run,
        )
        iteration = 0
        while max_iterations is None or iteration < max_iterations:
            try:
                results = self.poll_once()
                if results:
                    ok = sum(1 for r in results if r.success)
                    fail = len(results) - ok
                    logger.info(
                        "[DAO Executor] poll: %d events, %d ok, %d failed",
                        len(results), ok, fail,
                    )
            except Exception as exc:
                logger.exception("[DAO Executor] unexpected error in poll loop: %s", exc)

            iteration += 1
            if max_iterations is None or iteration < max_iterations:
                time.sleep(self.config.poll_interval)


# ---------------------------------------------------------------------------
# Register helm_upgrade action in GovernanceEngine dispatcher
# ---------------------------------------------------------------------------

def register_helm_upgrade_action(dispatcher, config: Optional[ExecutorConfig] = None) -> None:
    """
    Register a 'helm_upgrade' action handler into an ActionDispatcher.

    This enables off-chain governance proposals to include a helm_upgrade
    action that will be executed when the proposal passes.

    Action format:
        {
            "type": "helm_upgrade",
            "release": "mesh-op",           # optional override
            "chart": "charts/x0tta-mesh-operator/",  # optional override
            "set": {"key": "value"},         # optional --set overrides
        }
    """
    from src.dao.governance import ActionResult

    cfg = config or ExecutorConfig()
    runner = HelmRunner(cfg)

    def _handle_helm_upgrade(action: Dict[str, Any]) -> ActionResult:
        release_override = action.get("release")
        chart_override = action.get("chart")
        extra_set = action.get("set", {})

        # Temporary config override if action specifies release/chart
        run_cfg = cfg
        if release_override or chart_override:
            import dataclasses
            run_cfg = dataclasses.replace(
                cfg,
                helm_release=release_override or cfg.helm_release,
                helm_chart=chart_override or cfg.helm_chart,
            )
            actual_runner = HelmRunner(run_cfg)
        else:
            actual_runner = runner

        result = actual_runner.upgrade(
            proposal_id=action.get("proposal_id", 0),
            extra_set=extra_set or None,
        )
        return ActionResult(
            action_type="helm_upgrade",
            success=result.success,
            detail=result.stderr[:200] if not result.success else f"release={run_cfg.helm_release}",
        )

    dispatcher.register("helm_upgrade", _handle_helm_upgrade)
    logger.info("[DAO Executor] helm_upgrade action registered in dispatcher")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = ExecutorConfig()

    if not config.governance_address:
        logger.error("MESH_GOVERNANCE_ADDRESS not set — exiting")
        sys.exit(1)

    listener = ProposalExecutedListener(config)
    listener.run()


if __name__ == "__main__":
    main()
