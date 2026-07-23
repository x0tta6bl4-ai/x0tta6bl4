"""
Practical Byzantine Fault Tolerance (PBFT) Implementation

Provides a complete implementation of PBFT consensus algorithm
for Byzantine fault-tolerant distributed decision making.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
import json

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

_SERVICE_AGENT = "swarm-pbft"
PBFT_CLAIM_BOUNDARY = (
    "PBFT execution event only. It records local consensus callback policy and "
    "safe actuator state; it is not production rollout or settlement evidence."
)


class PBFTPhase(str, Enum):
    """Phases in PBFT protocol."""
    IDLE = "idle"
    PRE_PREPARE = "pre_prepare"
    PREPARE = "prepare"
    COMMIT = "commit"
    EXECUTED = "executed"


@dataclass
class PBFTMessage:
    """Base message for PBFT protocol."""
    msg_type: str
    view: int
    sequence: int
    digest: str
    sender_id: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    request: Optional[Any] = None
    signature: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.msg_type,
            "view": self.view,
            "sequence": self.sequence,
            "digest": self.digest,
            "sender_id": self.sender_id,
            "timestamp": self.timestamp.isoformat(),
            "request": self.request,
            "signature": self.signature,
        }
    
    def compute_digest(self) -> str:
        """Compute message digest for verification."""
        data = f"{self.msg_type}:{self.view}:{self.sequence}:{self.digest}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]


@dataclass
class PBFTRequest:
    """Client request for PBFT."""
    client_id: str
    timestamp: int
    operation: Any
    request_id: str = field(default_factory=lambda: str(int(time.time() * 1000)))
    
    def compute_digest(self) -> str:
        """Compute request digest."""
        data = json.dumps({
            "client_id": self.client_id,
            "timestamp": self.timestamp,
            "operation": str(self.operation),
        }, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()[:32]


@dataclass
class PBFTLogEntry:
    """Entry in the PBFT log."""
    sequence: int
    view: int
    digest: str
    request: Optional[PBFTRequest] = None
    phase: PBFTPhase = PBFTPhase.IDLE
    
    # Message tracking
    pre_prepare_msg: Optional[PBFTMessage] = None
    prepare_msgs: Dict[str, PBFTMessage] = field(default_factory=dict)
    commit_msgs: Dict[str, PBFTMessage] = field(default_factory=dict)
    
    # Execution
    executed: bool = False
    result: Optional[Any] = None


class PBFTNode:
    """
    PBFT node for Byzantine fault-tolerant consensus.
    
    Implements the full PBFT protocol:
    - Pre-prepare: Primary sends request with sequence number
    - Prepare: Replicas verify and send prepare messages
    - Commit: Replicas send commit messages after 2f+1 prepares
    - Execute: Replicas execute after 2f+1 commits
    
    Can tolerate up to f Byzantine (malicious) nodes out of 3f+1 total.
    """
    
    def __init__(
        self,
        node_id: str,
        peers: Set[str],
        f: int = 1,  # Max Byzantine nodes
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
        self.node_id = node_id
        self.peers = peers
        self.all_nodes = peers | {node_id}
        self.f = f
        self.n = 3 * f + 1  # Minimum nodes for BFT
        self.source_agent = source_agent
        self.event_project_root = event_project_root
        self.event_bus = (
            event_bus if event_bus is not None else self._default_event_bus(event_project_root)
        )
        self.policy_engine = policy_engine
        self.require_policy = (
            require_policy
            if require_policy is not None
            else self._env_bool("X0TTA6BL4_SWARM_PBFT_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_RECOVERY_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="swarm-pbft")
        self.identity = {
            "node_id": node_id,
            "spiffe_id": spiffe_id or service_identity["spiffe_id"],
            "did": did or service_identity["did"],
            "wallet_address": wallet_address or service_identity["wallet_address"],
        }
        self._last_actuator_payload: Any = None
        self.safe_actuator = safe_actuator or SafeActuator(self._execute_operation_callback)
        
        # View management
        self.view = 0
        self.primary_id = self._get_primary(self.view)
        self.is_primary = self.node_id == self.primary_id
        
        # Sequence management
        self.sequence = 0
        self.low_water_mark = 0
        self.high_water_mark = 100  # Log size limit
        
        # Log
        self._log: Dict[int, PBFTLogEntry] = {}
        
        # Message tracking
        self._prepared: Set[int] = set()  # Sequences that are prepared
        self._committed: Set[int] = set()  # Sequences that are committed
        self._view_changes: Dict[int, Dict[str, PBFTMessage]] = {}
        self._new_view_sent: Set[int] = set()
        
        # Client request tracking
        self._pending_requests: Dict[str, PBFTRequest] = {}
        self._executed_requests: Set[str] = set()
        
        # Callbacks
        self._on_execute: Optional[Callable[[Any], Any]] = None
        self._send_message: Optional[Callable[[str, Dict], None]] = None
        
        # Message handlers
        self._handlers = {
            "request": self._handle_request,
            "pre_prepare": self._handle_pre_prepare,
            "prepare": self._handle_prepare,
            "commit": self._handle_commit,
            "view_change": self._handle_view_change,
            "new_view": self._handle_new_view,
        }

    @staticmethod
    def _env_bool(name: str, default: bool) -> bool:
        value = os.getenv(name)
        if value is None:
            return default
        return value.strip().lower() in {"1", "true", "yes", "on"}

    @staticmethod
    def _default_event_bus(project_root: str) -> Optional[EventBus]:
        try:
            return get_event_bus(project_root)
        except Exception as exc:
            logger.error("Failed to initialize PBFT EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize PBFT policy engine: %s", exc)
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
        blocked_fragments = ("secret", "password", "token", "key", "private")
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

    def _execution_context(self, entry: PBFTLogEntry, operation: Any) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "sequence": entry.sequence,
            "view": entry.view,
            "digest": entry.digest,
            "operation": operation,
            "phase": entry.phase.value if hasattr(entry.phase, "value") else str(entry.phase),
        }

    def _publish_execution_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        context: Dict[str, Any],
        result: Optional[Dict[str, Any]] = None,
        reason: str = "",
        policy_decision: Any = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        payload = {
            "component": "swarm.pbft",
            "stage": stage,
            "action_type": "pbft_execute",
            "resource": "swarm:pbft:execute",
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "result": self._safe_context(result or {}) if result is not None else None,
            "success": result.get("success") if result is not None else None,
            "reason": reason,
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
            "claim_boundary": PBFT_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=7)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish PBFT execution event: %s", exc)
            return None

    def _evaluate_execution_policy(self) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "PBFT policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "PBFT SPIFFE identity is required for policy evaluation"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource="swarm:pbft:execute",
                workload_type="swarm-consensus",
            )
        except Exception as exc:
            return False, None, f"PBFT policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "PBFT policy denied execution"
        return True, decision, self._policy_reason(decision)

    def _execute_operation_callback(
        self,
        _action: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if self._on_execute is None:
            self._last_actuator_payload = None
            return SafeActuatorResult(True, "no PBFT execution callback configured")
        raw = self._on_execute(context.get("operation"))
        self._last_actuator_payload = raw
        if isinstance(raw, SafeActuatorResult):
            return raw
        if isinstance(raw, dict) and ("success" in raw or "ok" in raw):
            return SafeActuatorResult(
                success=bool(raw.get("success", raw.get("ok"))),
                reason=str(raw.get("reason", raw.get("error", "")) or ""),
                simulated=bool(raw.get("simulated", False)),
            )
        if raw is False:
            return SafeActuatorResult(False, "PBFT execution callback returned false")
        return SafeActuatorResult(True)
    
    def _get_primary(self, view: int) -> str:
        """Get the primary for a given view."""
        nodes = sorted(self.all_nodes)
        return nodes[view % len(nodes)]
    
    def set_callbacks(
        self,
        on_execute: Optional[Callable[[Any], Any]] = None,
        send_message: Optional[Callable[[str, Dict], None]] = None,
    ) -> None:
        self._on_execute = on_execute
        self._send_message = send_message
    
    def _send_to(self, target_id: str, message: Dict[str, Any]) -> None:
        """Send message to a specific node."""
        if self._send_message:
            self._send_message(target_id, message)
    
    def _send_to_all(self, message: Dict[str, Any]) -> None:
        """Send message to all peers."""
        for peer in self.peers:
            self._send_to(peer, message)
    
    def _get_or_create_entry(self, sequence: int) -> PBFTLogEntry:
        """Get or create a log entry."""
        if sequence not in self._log:
            self._log[sequence] = PBFTLogEntry(
                sequence=sequence,
                view=self.view,
                digest="",
            )
        return self._log[sequence]
    
    # ==================== Client Interface ====================
    
    async def request(self, operation: Any) -> Tuple[bool, Any]:
        """
        Submit a request to the PBFT cluster.
        
        Returns (success, result).
        """
        request = PBFTRequest(
            client_id=self.node_id,
            timestamp=int(time.time() * 1000),
            operation=operation,
        )
        
        digest = request.compute_digest()
        self._pending_requests[digest] = request
        
        # Send request to primary
        msg = PBFTMessage(
            msg_type="request",
            view=self.view,
            sequence=0,  # Will be assigned by primary
            digest=digest,
            sender_id=self.node_id,
            request=request.to_dict() if hasattr(request, 'to_dict') else {
                "client_id": request.client_id,
                "timestamp": request.timestamp,
                "operation": str(request.operation),
            },
        )
        
        self._send_to(self.primary_id, msg.to_dict())
        
        # Wait for execution (simplified)
        try:
            await asyncio.wait_for(
                self._wait_for_execution(digest),
                timeout=30.0
            )
            
            # Get result from log
            for entry in self._log.values():
                if entry.executed and entry.digest == digest:
                    return (True, entry.result)
            
            return (False, None)
        except asyncio.TimeoutError:
            logger.warning(f"Request {digest[:8]} timed out")
            return (False, None)
    
    async def _wait_for_execution(self, digest: str) -> None:
        """Wait for request to be executed."""
        while digest not in self._executed_requests:
            await asyncio.sleep(0.1)
    
    # ==================== Primary Role ====================
    
    def _handle_request(self, message: Dict[str, Any]) -> None:
        """Handle a client request (Primary only)."""
        if not self.is_primary:
            # Forward to primary
            self._send_to(self.primary_id, message)
            return
        
        digest = message["digest"]
        request_data = message.get("request", {})
        
        # Assign sequence number
        self.sequence += 1
        sequence = self.sequence
        
        # Create log entry
        entry = self._get_or_create_entry(sequence)
        entry.view = self.view
        entry.digest = digest
        entry.phase = PBFTPhase.PRE_PREPARE
        
        # Create pre-prepare message
        pre_prepare = PBFTMessage(
            msg_type="pre_prepare",
            view=self.view,
            sequence=sequence,
            digest=digest,
            sender_id=self.node_id,
            request=request_data,
        )
        entry.pre_prepare_msg = pre_prepare
        
        # Send pre-prepare to all replicas
        self._send_to_all(pre_prepare.to_dict())
        
        logger.info(f"Primary {self.node_id}: Sent pre-prepare for seq {sequence}")
    
    # ==================== Replica Role ====================
    
    def _handle_pre_prepare(self, message: Dict[str, Any]) -> None:
        """Handle a pre-prepare message from primary."""
        view = message["view"]
        sequence = message["sequence"]
        digest = message["digest"]
        sender_id = message["sender_id"]
        
        # Verify sender is primary for this view
        if sender_id != self._get_primary(view):
            logger.warning(f"Pre-prepare from non-primary {sender_id}")
            return
        
        # Verify view
        if view != self.view:
            logger.warning(f"Pre-prepare for wrong view {view} (current: {self.view})")
            return
        
        # Verify sequence
        if sequence <= self.low_water_mark or sequence > self.high_water_mark:
            logger.warning(f"Pre-prepare with invalid sequence {sequence}")
            return
        
        # Create log entry
        entry = self._get_or_create_entry(sequence)
        entry.view = view
        entry.digest = digest
        entry.phase = PBFTPhase.PRE_PREPARE
        entry.pre_prepare_msg = PBFTMessage(
            msg_type="pre_prepare",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=sender_id,
        )
        
        # Send prepare to all
        prepare = PBFTMessage(
            msg_type="prepare",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=self.node_id,
        )
        self._send_to_all(prepare.to_dict())
        
        # Also store our own prepare
        entry.prepare_msgs[self.node_id] = prepare
        
        logger.debug(f"Replica {self.node_id}: Sent prepare for seq {sequence}")
        
        # Check if we can advance to commit
        self._check_prepare(entry)
    
    def _handle_prepare(self, message: Dict[str, Any]) -> None:
        """Handle a prepare message."""
        view = message["view"]
        sequence = message["sequence"]
        digest = message["digest"]
        sender_id = message["sender_id"]
        
        # Verify view
        if view != self.view:
            return
        
        # Get log entry
        entry = self._log.get(sequence)
        if not entry or entry.digest != digest:
            return
        
        # Store prepare message
        prepare = PBFTMessage(
            msg_type="prepare",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=sender_id,
        )
        entry.prepare_msgs[sender_id] = prepare
        
        logger.debug(f"Replica {self.node_id}: Received prepare from {sender_id}")
        
        # Check if we can advance to commit
        self._check_prepare(entry)
    
    def _check_prepare(self, entry: PBFTLogEntry) -> None:
        """Check if we have enough prepares to advance to commit."""
        if entry.phase != PBFTPhase.PRE_PREPARE:
            return
        
        # Need 2f prepares (including our own)
        if len(entry.prepare_msgs) >= 2 * self.f:
            entry.phase = PBFTPhase.PREPARE
            self._prepared.add(entry.sequence)
            
            # Send commit
            commit = PBFTMessage(
                msg_type="commit",
                view=entry.view,
                sequence=entry.sequence,
                digest=entry.digest,
                sender_id=self.node_id,
            )
            self._send_to_all(commit.to_dict())
            entry.commit_msgs[self.node_id] = commit
            
            logger.debug(f"Replica {self.node_id}: Sent commit for seq {entry.sequence}")
            
            # Check if we can execute
            self._check_commit(entry)
    
    def _handle_commit(self, message: Dict[str, Any]) -> None:
        """Handle a commit message."""
        view = message["view"]
        sequence = message["sequence"]
        digest = message["digest"]
        sender_id = message["sender_id"]
        
        # Verify view
        if view != self.view:
            return
        
        # Get log entry
        entry = self._log.get(sequence)
        if not entry or entry.digest != digest:
            return
        
        # Store commit message
        commit = PBFTMessage(
            msg_type="commit",
            view=view,
            sequence=sequence,
            digest=digest,
            sender_id=sender_id,
        )
        entry.commit_msgs[sender_id] = commit
        
        logger.debug(f"Replica {self.node_id}: Received commit from {sender_id}")
        
        # Check if we can execute
        self._check_commit(entry)
    
    def _check_commit(self, entry: PBFTLogEntry) -> None:
        """Check if we have enough commits to execute."""
        if entry.phase != PBFTPhase.PREPARE:
            return
        
        # Need 2f+1 commits
        if len(entry.commit_msgs) >= 2 * self.f + 1:
            entry.phase = PBFTPhase.COMMIT
            self._committed.add(entry.sequence)
            
            # Execute
            self._execute(entry)
    
    def _execute(self, entry: PBFTLogEntry) -> None:
        """Execute the request."""
        if entry.executed:
            return
        
        # Get the request
        if entry.pre_prepare_msg and entry.pre_prepare_msg.request:
            operation = entry.pre_prepare_msg.request.get("operation")
        else:
            operation = None
        
        context = self._execution_context(entry, operation)
        self._publish_execution_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            context=context,
        )

        policy_allowed, policy_decision, policy_reason = self._evaluate_execution_policy()
        if not policy_allowed:
            result = {
                "success": False,
                "error": policy_reason,
                "policy_required": True,
                "matched_rules": self._policy_rules(policy_decision),
            }
            self._publish_execution_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                context=context,
                result=result,
                reason=policy_reason,
                policy_decision=policy_decision,
            )
            entry.executed = True
            entry.result = result
            entry.phase = PBFTPhase.EXECUTED
            self._executed_requests.add(entry.digest)
            return

        self._publish_execution_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )

        result = None
        try:
            self._last_actuator_payload = None
            actuator_result = self.safe_actuator.execute("pbft_execute", context)
            if actuator_result.simulated:
                result = {
                    "success": False,
                    "error": actuator_result.reason or "safe actuator returned simulated result",
                    "simulated": True,
                }
                self._publish_execution_event(
                    EventType.TASK_FAILED,
                    stage="actuator_simulated",
                    context=context,
                    result=result,
                    reason=result["error"],
                    policy_decision=policy_decision,
                )
            elif actuator_result.success:
                result = self._last_actuator_payload
                event_result = {
                    "success": True,
                    "reason": actuator_result.reason,
                    "simulated": actuator_result.simulated,
                    "callback_result": result,
                }
                self._publish_execution_event(
                    EventType.PIPELINE_STAGE_END,
                    stage="actuator_completed",
                    context=context,
                    result=event_result,
                    reason=actuator_result.reason or policy_reason,
                    policy_decision=policy_decision,
                )
            else:
                result = {"success": False, "error": actuator_result.reason}
                self._publish_execution_event(
                    EventType.TASK_FAILED,
                    stage="actuator_failed",
                    context=context,
                    result=result,
                    reason=actuator_result.reason or policy_reason,
                    policy_decision=policy_decision,
                )
        except Exception as e:
            logger.error(f"Execution failed: {e}")
            result = {"success": False, "error": str(e)}
            self._publish_execution_event(
                EventType.TASK_FAILED,
                stage="actuator_error",
                context=context,
                result=result,
                reason=str(e),
                policy_decision=policy_decision,
            )
        
        entry.executed = True
        entry.result = result
        entry.phase = PBFTPhase.EXECUTED
        
        self._executed_requests.add(entry.digest)
        
        logger.info(f"Replica {self.node_id}: Executed seq {entry.sequence}")
    
    # ==================== View Change ====================

    def _is_known_node(self, sender_id: str) -> bool:
        return sender_id in self.all_nodes

    def _advance_to_view(self, new_view: int) -> None:
        self.view = new_view
        self.primary_id = self._get_primary(self.view)
        self.is_primary = self.node_id == self.primary_id

    def _record_view_change(self, message: Dict[str, Any]) -> bool:
        try:
            new_view = int(message.get("view"))
        except (TypeError, ValueError):
            logger.warning("View-change with invalid view: %s", message.get("view"))
            return False

        sender_id = str(message.get("sender_id", ""))
        if not self._is_known_node(sender_id):
            logger.warning("Ignoring view-change from unknown node %s", sender_id)
            return False
        if new_view < self.view:
            logger.warning(
                "Ignoring stale view-change for view %s (current: %s)",
                new_view,
                self.view,
            )
            return False

        view_changes = self._view_changes.setdefault(new_view, {})
        view_changes[sender_id] = PBFTMessage(
            msg_type="view_change",
            view=new_view,
            sequence=int(message.get("sequence", 0) or 0),
            digest=str(message.get("digest", "") or ""),
            sender_id=sender_id,
            request=message.get("request"),
            signature=message.get("signature"),
        )
        return True

    def _view_change_quorum_reached(self, view: int) -> bool:
        return len(self._view_changes.get(view, {})) >= 2 * self.f + 1

    def _maybe_send_new_view(self, view: int) -> None:
        if self._get_primary(view) != self.node_id:
            return
        if view in self._new_view_sent:
            return
        if not self._view_change_quorum_reached(view):
            return

        msg = PBFTMessage(
            msg_type="new_view",
            view=view,
            sequence=0,
            digest="",
            sender_id=self.node_id,
            request={
                "view_change_senders": sorted(self._view_changes[view].keys()),
            },
        )
        self._new_view_sent.add(view)
        self._send_to_all(msg.to_dict())
        logger.info(
            "Replica %s: Broadcast new_view %s after %s view-change messages",
            self.node_id,
            view,
            len(self._view_changes[view]),
        )
    
    def _handle_view_change(self, message: Dict[str, Any]) -> None:
        """Handle a view change message."""
        if not self._record_view_change(message):
            return
        view = int(message["view"])
        self._maybe_send_new_view(view)
        logger.info(
            "Replica %s: Recorded view-change for view %s (%s/%s)",
            self.node_id,
            view,
            len(self._view_changes.get(view, {})),
            2 * self.f + 1,
        )
    
    def _handle_new_view(self, message: Dict[str, Any]) -> None:
        """Handle a new view message."""
        try:
            new_view = int(message.get("view", self.view + 1))
        except (TypeError, ValueError):
            logger.warning("New-view with invalid view: %s", message.get("view"))
            return

        sender_id = str(message.get("sender_id", ""))
        if not self._is_known_node(sender_id):
            logger.warning("Ignoring new-view from unknown node %s", sender_id)
            return
        expected_primary = self._get_primary(new_view)
        if sender_id != expected_primary:
            logger.warning(
                "Ignoring new-view for view %s from non-primary %s (expected %s)",
                new_view,
                sender_id,
                expected_primary,
            )
            return
        
        if new_view > self.view:
            self._advance_to_view(new_view)
            
            logger.info(f"Replica {self.node_id}: Advanced to view {self.view}, primary={self.primary_id}")
    
    def start_view_change(self) -> None:
        """Initiate a view change."""
        new_view = self.view + 1
        self._advance_to_view(new_view)
        
        # Notify others
        msg = PBFTMessage(
            msg_type="view_change",
            view=self.view,
            sequence=0,
            digest="",
            sender_id=self.node_id,
        )
        self._record_view_change(msg.to_dict())
        self._send_to_all(msg.to_dict())
        self._maybe_send_new_view(self.view)
        
        logger.info(f"Replica {self.node_id}: Started view change to {self.view}")
    
    # ==================== Message Handling ====================
    
    def receive_message(self, message: Dict[str, Any]) -> None:
        """Receive and process a message."""
        msg_type = message.get("type")
        handler = self._handlers.get(msg_type)
        if handler:
            handler(message)
        else:
            logger.warning(f"Unknown message type: {msg_type}")
    
    def get_log_entry(self, sequence: int) -> Optional[PBFTLogEntry]:
        """Get a log entry by sequence number."""
        return self._log.get(sequence)
    
    def get_executed(self) -> List[int]:
        """Get list of executed sequence numbers."""
        return sorted([s for s, e in self._log.items() if e.executed])


# Export
__all__ = [
    "PBFTPhase",
    "PBFTMessage",
    "PBFTRequest",
    "PBFTLogEntry",
    "PBFTNode",
]

