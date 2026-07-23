"""
DPI Healing Planner — Phase 1 sketch (Analyze + Plan + Execute seam)
====================================================================

Closes the loop opened in Phase 0. Phase 0 (``tspu_rst_detector``) emits
``EventType.DPI_BLOCK_DETECTED`` when TSPU resets the live transport mid-stream.
This planner subscribes to that signal, decides the next transport in the
ladder, applies the confidence gate from .claude/rules/40-mesh-security.md, and
— only when allowed — asks the existing recovery executor to switch protocol.

    Monitor (Phase 0 detector)
        └─> DPI_BLOCK_DETECTED ──> [Analyze] pick next transport in ladder
                                   [Plan]    confidence gate
                                                 < dao_threshold -> OBSERVE
                                        dao..auto_threshold      -> DAO_VOTE
                                                 > auto_threshold -> AUTO_EXECUTE
                                   [Execute] recovery executor .execute(
                                                 "switch protocol ...", context)
        <── HEALING_VERIFIED (Phase 2: re-probe the new transport)

PRODUCTION SAFETY (.claude/rules/50-prod-source-of-truth.md):
- ``dry_run=True`` by default: the switch is logged, not applied.
- Actuation is confined to a THROWAWAY test profile
  (``test_profile``, e.g. the SPB canary inbounds 21443/2052 or a dedicated test
  UUID). ``TestProfileSwitchBackend`` hard-refuses any target that is not the
  test profile, so the production xray that 12 paying users depend on is never
  touched.
- A live switch on the production identity still requires explicit user approval
  and an active codex validation session. This module never crosses that line.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol

from src.coordination.events import Event, EventBus, EventType

logger = logging.getLogger(__name__)

# Transport ladder: when the active transport is reset, climb to the next rung.
# Values are (protocol, mimic) as consumed by RecoveryActionExecutor._switch_protocol.
TRANSPORT_LADDER: List[tuple[str, str]] = [
    ("reality", "tls"),
    ("xhttp", "http"),
    ("cf-tunnel", "https"),
]

# Confidence bands per rules/40-mesh-security.md.
DEFAULT_DAO_THRESHOLD = 0.6   # below -> observe only
DEFAULT_AUTO_THRESHOLD = 0.9  # above -> may auto-execute


class Decision(str, Enum):
    OBSERVE = "observe"        # confidence < dao_threshold: log, do nothing
    DAO_VOTE = "dao_vote"      # dao_threshold..auto_threshold: require governance
    AUTO_EXECUTE = "auto_execute"  # > auto_threshold: act now


def confidence_gate(
    confidence: float,
    *,
    dao_threshold: float = DEFAULT_DAO_THRESHOLD,
    auto_threshold: float = DEFAULT_AUTO_THRESHOLD,
) -> Decision:
    if confidence < dao_threshold:
        return Decision.OBSERVE
    if confidence > auto_threshold:
        return Decision.AUTO_EXECUTE
    return Decision.DAO_VOTE


def next_transport(current: str) -> Optional[tuple[str, str]]:
    """Return the next (protocol, mimic) after ``current`` in the ladder."""
    names = [p for p, _ in TRANSPORT_LADDER]
    if current not in names:
        # Unknown current transport: start from the top of the ladder.
        return TRANSPORT_LADDER[0]
    idx = names.index(current)
    if idx + 1 >= len(TRANSPORT_LADDER):
        return None  # already at the last rung; nothing left to climb to
    return TRANSPORT_LADDER[idx + 1]


class Executor(Protocol):
    def execute(self, action: str, context: Optional[Dict[str, Any]] = None) -> bool: ...


class DaoGate(Protocol):
    def request_vote(self, proposal: Dict[str, Any]) -> bool: ...


@dataclass
class PlanResult:
    decision: Decision
    confidence: float
    current_transport: str
    target_transport: Optional[str]
    executed: bool
    dry_run: bool
    detail: str = ""
    context: Dict[str, Any] = field(default_factory=dict)


class TestProfileSwitchBackend:
    """A ``switch_protocol``-compatible backend confined to a test profile.

    Wire this as the RecoveryActionExecutor routing backend. It refuses any
    profile other than the configured throwaway one, so the loop can be
    exercised end-to-end without risking production identities.
    """

    def __init__(self, test_profile: str, dry_run: bool = True) -> None:
        self.test_profile = test_profile
        self.dry_run = dry_run
        self.switch_log: List[Dict[str, Any]] = []

    def switch_protocol(self, protocol: str, mimic: str, profile: Optional[str] = None) -> bool:
        target = profile or self.test_profile
        if target != self.test_profile:
            raise PermissionError(
                f"refusing transport switch on non-test profile {target!r}; "
                f"only {self.test_profile!r} is permitted (rules/50)"
            )
        record = {"protocol": protocol, "mimic": mimic, "profile": target, "dry_run": self.dry_run}
        self.switch_log.append(record)
        if self.dry_run:
            logger.info("[dry-run] would switch %s -> protocol=%s mimic=%s", target, protocol, mimic)
            return True
        # Real actuation against the test profile goes here (Phase 1b): drive the
        # test client's xray outbound / regenerate the test sub-link. Left as a
        # seam so no live mutation ships in the sketch.
        raise NotImplementedError("live test-profile switch not wired yet")


class DpiHealingPlanner:
    """Subscribes to DPI_BLOCK_DETECTED and drives one gated transport switch."""

    def __init__(
        self,
        event_bus: EventBus,
        executor: Executor,
        *,
        test_profile: str = "ghost-test-canary",
        dao_gate: Optional[DaoGate] = None,
        dao_threshold: float = DEFAULT_DAO_THRESHOLD,
        auto_threshold: float = DEFAULT_AUTO_THRESHOLD,
        dry_run: bool = True,
        source_agent: str = "self-healing-dpi-planner",
    ) -> None:
        self.event_bus = event_bus
        self.executor = executor
        self.test_profile = test_profile
        self.dao_gate = dao_gate
        self.dao_threshold = dao_threshold
        self.auto_threshold = auto_threshold
        self.dry_run = dry_run
        self.source_agent = source_agent

    def subscribe(self) -> None:
        self.event_bus.subscribe(EventType.DPI_BLOCK_DETECTED, self.on_dpi_block)

    def on_dpi_block(self, event: Event) -> PlanResult:
        data = event.data or {}
        confidence = float(data.get("confidence", data.get("confidence_value", 0.0)) or 0.0)
        # The event carries a redacted transport hash; the operator supplies the
        # readable current transport out of band (or the planner defaults to the
        # ladder top). Phase 1b will thread the concrete label through the event.
        current = str(data.get("current_transport", TRANSPORT_LADDER[0][0]))

        decision = confidence_gate(
            confidence,
            dao_threshold=self.dao_threshold,
            auto_threshold=self.auto_threshold,
        )
        nxt = next_transport(current)

        if nxt is None:
            return self._observe(decision, confidence, current, "ladder exhausted; no transport left")

        protocol, mimic = nxt
        context = {
            "protocol": protocol,
            "mimic": mimic,
            "profile": self.test_profile,
            "dry_run": self.dry_run,
            "reason": "dpi_block_detected",
            "confidence": confidence,
        }

        if decision is Decision.OBSERVE:
            return self._observe(decision, confidence, current, "confidence below DAO threshold")

        if decision is Decision.DAO_VOTE:
            approved = self._dao_vote(protocol, confidence, context)
            if not approved:
                return PlanResult(
                    decision, confidence, current, protocol, executed=False,
                    dry_run=self.dry_run, detail="DAO vote pending/denied", context=context,
                )

        action = f"switch protocol to {protocol} (mimic {mimic})"
        executed = self.executor.execute(action, context)
        return PlanResult(
            decision, confidence, current, protocol, executed=executed,
            dry_run=self.dry_run,
            detail="executed" if executed else "executor refused",
            context=context,
        )

    def _observe(self, decision: Decision, confidence: float, current: str, why: str) -> PlanResult:
        logger.info("observe-only for DPI block on %s (%s)", current, why)
        return PlanResult(decision, confidence, current, None, executed=False, dry_run=self.dry_run, detail=why)

    def _dao_vote(self, protocol: str, confidence: float, context: Dict[str, Any]) -> bool:
        if self.dao_gate is None:
            logger.info("DAO gate not wired; transport switch to %s held pending governance", protocol)
            return False
        return self.dao_gate.request_vote(
            {"action": "switch_protocol", "protocol": protocol, "confidence": confidence, "context": context}
        )
