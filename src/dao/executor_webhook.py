"""
DAO Executor service for x0tta6bl4.

Supports both:
1. Polling mode: scan ProposalExecuted events from chain.
2. Webhook mode: accept ProposalExecuted payloads via FastAPI.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from src.coordination.events import EventBus, EventType, get_event_bus
from src.integration.spine import SafeActuator, SafeActuatorResult
from src.security.policy_decision_adapter import (
    policy_allowed as normalize_policy_allowed,
    policy_reason as normalize_policy_reason,
    policy_rules as normalize_policy_rules,
)
from src.services.service_event_identity import service_event_identity

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dao-executor")

_DEPLOYMENTS_DIR = Path(__file__).parent / "deployments"
_DEFAULT_PROCESSED = _DEPLOYMENTS_DIR / "executed_proposals.json"
_DEFAULT_LEDGER = _DEPLOYMENTS_DIR / "audit.jsonl"
_SERVICE_AGENT = "dao-executor"

DAO_EXECUTOR_CLAIM_BOUNDARY = (
    "DAO executor release event only. It records local identity, policy, and "
    "safe actuator state for release script attempts; it is not proof of a "
    "successful production rollout without operator-captured deployment evidence."
)


class ProposalExecutedWebhook(BaseModel):
    proposal_id: int
    title: Optional[str] = None
    source: str = "webhook"


class DAOExecutor:
    """Automates deployment tasks based on DAO decisions."""

    def __init__(
        self,
        contract_address: str,
        token_address: str,
        rpc_url: str,
        poll_interval: int = 15,
        processed_file: Optional[str] = None,
        ledger_path: Optional[str] = None,
        *,
        node_id: str = "dao-executor",
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
        from src.dao.governance_contract import GovernanceContract

        self.gov = GovernanceContract(
            contract_address=contract_address,
            token_address=token_address,
            rpc_url=rpc_url,
        )
        self.poll_interval = poll_interval
        self.last_block = int(self.gov.web3.eth.block_number)
        self.is_running = False
        self.processed_file = Path(
            processed_file or os.getenv("DAO_EXECUTOR_PROCESSED_FILE", str(_DEFAULT_PROCESSED))
        )
        self.ledger_path = Path(
            ledger_path or os.getenv("DAO_EXECUTOR_LEDGER_PATH", str(_DEFAULT_LEDGER))
        )
        self._processed_ids = self._load_processed_ids()
        self.last_result: Dict[str, Any] = {}
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
            else self._env_bool("X0TTA6BL4_DAO_EXECUTOR_POLICY_REQUIRED", False)
            or self._env_bool("X0TTA6BL4_PRODUCTION", False)
        )
        if self.policy_engine is None and self.require_policy:
            self.policy_engine = self._default_policy_engine()
        service_identity = service_event_identity(service_name="dao-executor")
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
            self._execute_release_through_actuator
        )
        self._last_upgrade_success: Optional[bool] = None

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
            logger.error("Failed to initialize DAO executor EventBus: %s", exc)
            return None

    @staticmethod
    def _default_policy_engine() -> Optional[Any]:
        try:
            from src.security.zero_trust.policy_engine import get_policy_engine

            return get_policy_engine()
        except Exception as exc:
            logger.error("Failed to initialize DAO executor policy engine: %s", exc)
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

    def _publish_release_event(
        self,
        event_type: EventType,
        *,
        stage: str,
        context: Dict[str, Any],
        success: Optional[bool] = None,
        reason: str = "",
        policy_decision: Any = None,
        simulated: Optional[bool] = None,
    ) -> Optional[str]:
        if self.event_bus is None:
            return None
        payload = {
            "component": "dao.executor_webhook",
            "stage": stage,
            "operation": "release_script",
            "resource": "dao:executor:release_script",
            "proposal_id": context.get("proposal_id"),
            "proposal_title": context.get("title"),
            "script_path": context.get("script_path"),
            "node_id": self.identity["node_id"],
            "spiffe_id": self.identity["spiffe_id"],
            "did": self.identity["did"],
            "wallet_address": self.identity["wallet_address"],
            "identity": dict(self.identity),
            "context": self._safe_context(context),
            "success": success,
            "simulated": simulated,
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
            "safe_actuator": True,
            "claim_boundary": DAO_EXECUTOR_CLAIM_BOUNDARY,
        }
        try:
            event = self.event_bus.publish(event_type, self.source_agent, payload, priority=8)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish DAO executor release event: %s", exc)
            return None

    def _evaluate_release_policy(self) -> tuple[bool, Any, str]:
        if self.policy_engine is None:
            if self.require_policy:
                return False, None, "DAO executor policy engine is required but unavailable"
            return True, None, ""
        spiffe_id = self.identity.get("spiffe_id")
        if not spiffe_id:
            return False, None, "DAO executor SPIFFE identity is required for policy evaluation"
        try:
            decision = self.policy_engine.evaluate(
                spiffe_id,
                resource="dao:executor:release_script",
                workload_type="dao-executor",
            )
        except Exception as exc:
            return False, None, f"DAO executor policy evaluation failed: {exc}"
        if not self._policy_allowed(decision):
            return False, decision, self._policy_reason(decision) or "DAO executor policy denied release script"
        return True, decision, self._policy_reason(decision)

    def _execute_release_through_actuator(
        self,
        action: str,
        context: Dict[str, Any],
    ) -> SafeActuatorResult:
        if action != "release_script":
            return SafeActuatorResult(False, f"unknown DAO executor action: {action}")
        success = self._trigger_upgrade_internal(
            proposal_id=int(context.get("proposal_id", 0)),
            title=str(context.get("title", "")),
            script_path=str(context.get("script_path", "")),
        )
        self._last_upgrade_success = success
        return SafeActuatorResult(success, "release script completed" if success else "release script failed")

    async def start(self):
        """Start the event listener loop."""
        logger.info("DAO executor started; monitoring from block %d", self.last_block)
        self.is_running = True

        while self.is_running:
            try:
                await self.poll_events()
            except Exception as exc:
                logger.error("Error during polling: %s", exc)

            await asyncio.sleep(self.poll_interval)

    async def poll_events(self):
        """Poll for new ProposalExecuted events."""
        try:
            current_block = int(self.gov.web3.eth.block_number)
        except (TypeError, ValueError) as exc:
            logger.error("Failed to get current block number: %s", exc)
            return

        if current_block <= self.last_block:
            return

        logger.debug("Polling blocks %d..%d", self.last_block + 1, current_block)
        event_filter = self.gov.contract.events.ProposalExecuted.create_filter(
            fromBlock=self.last_block + 1,
            toBlock=current_block,
        )

        for event in event_filter.get_all_entries():
            proposal_id = int(event["args"]["proposalId"])
            logger.info("Detected ProposalExecuted event for proposal_id=%d", proposal_id)
            await self.process_proposal(proposal_id, source="poll_event")

        self.last_block = current_block

    async def process_proposal(
        self,
        proposal_id: int,
        proposal_title: Optional[str] = None,
        source: str = "poll",
    ) -> Dict[str, Any]:
        """Analyze proposal and trigger actions."""
        try:
            if proposal_id in self._processed_ids:
                result = {
                    "executed": False,
                    "reason": "duplicate",
                    "proposal_id": proposal_id,
                }
                self.last_result = result
                logger.info("Skipping duplicate proposal %d", proposal_id)
                return result

            title = proposal_title
            if not title:
                proposal = self.gov.get_proposal(proposal_id)
                title = proposal.title
            logger.info("Analyzing proposal '%s' (id=%d)", title, proposal_id)

            if self._is_upgrade_trigger(title):
                logger.info("Triggering automated upgrade for proposal %d", proposal_id)
                success = self.trigger_upgrade(proposal_id, title)
                reason = "upgrade_success" if success else "upgrade_failed"
                executed = bool(success)
            else:
                logger.info("Proposal %d has no upgrade trigger, skipping", proposal_id)
                executed = False
                reason = "no_upgrade_trigger"

            self._processed_ids.add(proposal_id)
            self._persist_processed_ids()
            self._append_ledger(
                proposal_id=proposal_id,
                title=title,
                source=source,
                executed=executed,
                reason=reason,
            )
            result = {
                "executed": executed,
                "reason": reason,
                "proposal_id": proposal_id,
            }
            self.last_result = result
            return result
        except Exception as exc:
            logger.error("Failed to process proposal %d: %s", proposal_id, exc)
            result = {
                "executed": False,
                "reason": "exception",
                "proposal_id": proposal_id,
                "error": str(exc),
            }
            self.last_result = result
            return result

    @staticmethod
    def _is_upgrade_trigger(title: str) -> bool:
        title_upper = title.upper()
        return "HELM_UPGRADE" in title_upper or "DEPLOY" in title_upper

    def trigger_upgrade(self, proposal_id: int, title: str) -> bool:
        """Execute the release script."""
        script_path = "scripts/release_to_main.sh"
        context = {
            "proposal_id": proposal_id,
            "title": title,
            "script_path": script_path,
        }
        self._last_upgrade_success = None
        self._publish_release_event(
            EventType.COORDINATION_REQUEST,
            stage="received",
            context=context,
        )
        policy_allowed, policy_decision, policy_reason = self._evaluate_release_policy()
        if not policy_allowed:
            self._publish_release_event(
                EventType.TASK_BLOCKED,
                stage="policy_denied",
                context=context,
                success=False,
                reason=policy_reason,
                policy_decision=policy_decision,
                simulated=False,
            )
            return False

        self._publish_release_event(
            EventType.PIPELINE_STAGE_START,
            stage="actuator_start",
            context=context,
            reason=policy_reason,
            policy_decision=policy_decision,
        )
        actuator_result = self.safe_actuator.execute("release_script", context)
        success = bool(self._last_upgrade_success if self._last_upgrade_success is not None else actuator_result.success)
        event_type = EventType.PIPELINE_STAGE_END if success and not actuator_result.simulated else EventType.TASK_FAILED
        stage = (
            "actuator_completed"
            if success and not actuator_result.simulated
            else "actuator_simulated"
            if actuator_result.simulated
            else "actuator_failed"
        )
        self._publish_release_event(
            event_type,
            stage=stage,
            context=context,
            success=success and not actuator_result.simulated,
            reason=actuator_result.reason,
            policy_decision=policy_decision,
            simulated=bool(actuator_result.simulated),
        )
        return success and not actuator_result.simulated

    def _trigger_upgrade_internal(self, proposal_id: int, title: str, script_path: str) -> bool:
        """Execute the release script after identity, policy, and safe actuator gates."""
        if not os.path.exists(script_path):
            logger.error("Release script not found: %s", script_path)
            self._last_release_return_code = None
            return False

        logger.info("Executing %s for proposal '%s' (%d)", script_path, title, proposal_id)
        try:
            env = os.environ.copy()
            env["DAO_PROPOSAL_ID"] = str(proposal_id)
            env["DAO_PROPOSAL_TITLE"] = title

            process = subprocess.Popen(
                ["bash", script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            stdout, stderr = process.communicate()
            self._last_release_return_code = int(process.returncode)

            if process.returncode == 0:
                logger.info("Upgrade successful for proposal %d", proposal_id)
                logger.debug("Script output: %s", stdout)
                return True

            logger.error("Upgrade failed (rc=%d): %s", process.returncode, stderr)
            return False
        except Exception as exc:
            logger.error("Exception during script execution: %s", exc)
            self._last_release_return_code = None
            return False

    def _load_processed_ids(self) -> Set[int]:
        if not self.processed_file.exists():
            return set()
        try:
            data = json.loads(self.processed_file.read_text())
            return {int(x) for x in data.get("executed", [])}
        except Exception as exc:
            logger.warning("Failed to load processed proposals from %s: %s", self.processed_file, exc)
            return set()

    def _persist_processed_ids(self) -> None:
        self.processed_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {"executed": sorted(self._processed_ids)}
        self.processed_file.write_text(json.dumps(payload, indent=2))

    def _append_ledger(
        self,
        proposal_id: int,
        title: str,
        source: str,
        executed: bool,
        reason: str,
    ) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "event": "ProposalProcessed",
            "proposal_id": proposal_id,
            "proposal_title": title,
            "source": source,
            "executed": executed,
            "reason": reason,
            "processed_at": datetime.now(timezone.utc).isoformat(),
        }
        with self.ledger_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record) + "\n")


def _verify_webhook_token(x_executor_token: Optional[str]) -> None:
    required_token = os.getenv("DAO_EXECUTOR_WEBHOOK_TOKEN", "").strip()
    if not required_token:
        return
    if not x_executor_token or x_executor_token != required_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid executor token",
        )


def create_app(executor: DAOExecutor) -> FastAPI:
    """Create FastAPI app for receiving ProposalExecuted webhooks."""
    app = FastAPI(title="x0tta6bl4 DAO Executor Webhook", version="3.4.0")

    @app.get("/healthz")
    async def healthz():
        return {"status": "ok", "service": "dao-executor"}

    @app.get("/status")
    async def status_view():
        return {
            "service": "dao-executor",
            "processed_count": len(executor._processed_ids),
            "last_block": executor.last_block,
            "last_result": executor.last_result,
        }

    @app.post("/webhook/proposal-executed")
    async def proposal_executed(
        event_data: ProposalExecutedWebhook,
        request: Request,
    ):
        _verify_webhook_token(request.headers.get("X-Executor-Token"))
        result = await executor.process_proposal(
            proposal_id=event_data.proposal_id,
            proposal_title=event_data.title,
            source=event_data.source,
        )
        return {
            "accepted": True,
            "proposal_id": event_data.proposal_id,
            "source": event_data.source,
            "executed": result["executed"],
            "reason": result["reason"],
        }

    return app


def _executor_from_env() -> Optional[DAOExecutor]:
    contract_addr = os.getenv("GOVERNANCE_ADDR")
    token_addr = os.getenv("TOKEN_ADDR")
    rpc_url = os.getenv("RPC_URL", "https://sepolia.base.org")

    if not contract_addr or not token_addr:
        logger.error("GOVERNANCE_ADDR and TOKEN_ADDR must be set")
        return None

    return DAOExecutor(
        contract_address=contract_addr,
        token_address=token_addr,
        rpc_url=rpc_url,
    )


async def _main_polling():
    executor = _executor_from_env()
    if executor is None:
        return
    await executor.start()


def main():
    mode = os.getenv("DAO_EXECUTOR_MODE", "poll").strip().lower()
    if mode == "webhook":
        executor = _executor_from_env()
        if executor is None:
            return
        app = create_app(executor)
        import uvicorn

        uvicorn.run(
            app,
            host=os.getenv("DAO_EXECUTOR_HOST", "0.0.0.0"),
            port=int(os.getenv("DAO_EXECUTOR_PORT", "8090")),
        )
        return

    asyncio.run(_main_polling())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
