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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Set

from fastapi import FastAPI, HTTPException, Request, status
from pydantic import BaseModel

from src.dao.governance_contract import GovernanceContract

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("dao-executor")

_DEPLOYMENTS_DIR = Path(__file__).parent / "deployments"
_DEFAULT_PROCESSED = _DEPLOYMENTS_DIR / "executed_proposals.json"
_DEFAULT_LEDGER = _DEPLOYMENTS_DIR / "audit.jsonl"


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
    ):
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
        if not os.path.exists(script_path):
            logger.error("Release script not found: %s", script_path)
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

            if process.returncode == 0:
                logger.info("Upgrade successful for proposal %d", proposal_id)
                logger.debug("Script output: %s", stdout)
                return True

            logger.error("Upgrade failed (rc=%d): %s", process.returncode, stderr)
            return False
        except Exception as exc:
            logger.error("Exception during script execution: %s", exc)
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
