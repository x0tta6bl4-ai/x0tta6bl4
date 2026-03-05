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

    def __init__(self, config: ExecutorConfig):
        self.config = config

    def upgrade(self, proposal_id: int, extra_set: Optional[Dict[str, str]] = None) -> HelmResult:
        """
        Run `helm upgrade` for the configured release.

        Args:
            proposal_id: The on-chain proposal ID that triggered this upgrade
            extra_set: Additional --set key=value pairs (e.g. from proposal metadata)

        Returns:
            HelmResult with success flag, command, and stdout/stderr
        """
        cmd = [
            "helm", "upgrade", "--install",
            self.config.helm_release,
            self.config.helm_chart,
            "--namespace", self.config.helm_namespace,
            "--wait",
            "--timeout", "5m",
            "--set", f"global.dao.proposalId={proposal_id}",
            "--set", f"global.dao.autoUpgrade=true",
        ]

        # Merge extra args from env
        cmd.extend(self.config.helm_extra_args)

        # Merge per-proposal overrides
        if extra_set:
            for k, v in extra_set.items():
                cmd.extend(["--set", f"{k}={v}"])

        cmd_str = " ".join(cmd)
        logger.info("[DAO Executor] helm command: %s", cmd_str)

        if self.config.dry_run:
            logger.info("[DAO Executor] DRY_RUN — helm not executed")
            return HelmResult(
                proposal_id=proposal_id,
                success=True,
                command=cmd_str,
                stdout="(dry-run)",
                stderr="",
                dry_run=True,
            )

        try:
            proc = subprocess.run(
                cmd,
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
                command=cmd_str,
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
                command=cmd_str,
                stdout="",
                stderr="helm timed out after 360s",
                dry_run=False,
            )
        except FileNotFoundError:
            logger.error("[DAO Executor] helm binary not found")
            return HelmResult(
                proposal_id=proposal_id,
                success=False,
                command=cmd_str,
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
