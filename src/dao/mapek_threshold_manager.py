"""
MAPE-K Threshold Manager
========================

Manages MAPE-K thresholds with DAO governance integration.
Allows DAO to change thresholds and automatically applies them.
"""

import json
import logging
import os
import time
from hashlib import sha256
from hmac import compare_digest, new as hmac_new
from math import isfinite
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.dao.governance import GovernanceEngine, Proposal, ProposalState
from src.dao.mapek_threshold_proposal import (MAPEKThresholdProposal,
                                              ThresholdChange)
from src.storage.ipfs_client import IPFSClient

logger = logging.getLogger(__name__)


DEFAULT_THRESHOLDS: Dict[str, float] = {
    "cpu_threshold": 80.0,
    "memory_threshold": 90.0,
    "network_loss_threshold": 5.0,
    "latency_threshold": 100.0,
    "check_interval": 60.0,
}

THRESHOLD_BOUNDS: Dict[str, Tuple[float, float]] = {
    # % values
    "cpu_threshold": (1.0, 99.0),
    "memory_threshold": (1.0, 99.0),
    # packet loss %
    "network_loss_threshold": (0.1, 50.0),
    # ms
    "latency_threshold": (10.0, 5000.0),
    # seconds
    "check_interval": (1.0, 3600.0),
}


class MAPEKThresholdManager:
    """
    Manages MAPE-K thresholds with DAO governance.

    Features:
    - Read current thresholds
    - Apply DAO-approved threshold changes
    - Store thresholds in IPFS (for distribution)
    - Verify threshold application
    """

    def __init__(
        self,
        governance_engine: GovernanceEngine,
        ipfs_client: Optional[IPFSClient] = None,
        storage_path: Optional[Path] = None,
    ):
        """
        Initialize threshold manager.

        Args:
            governance_engine: DAO governance engine
            ipfs_client: IPFS client for distribution
            storage_path: Path for local storage
        """
        self.governance = governance_engine
        self.ipfs_client = ipfs_client
        self.storage_path = storage_path or Path("/var/lib/x0tta6bl4")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.threshold_file = self.storage_path / "mapek_thresholds.json"
        self.threshold_hmac_file = self.storage_path / "mapek_thresholds.hmac"
        self.threshold_audit_file = self.storage_path / "mapek_threshold_audit.jsonl"
        # Optional integrity key for zero-trust local storage verification.
        self.threshold_hmac_key = os.getenv("X0TTA6BL4_THRESHOLDS_HMAC_KEY", "").strip()

        # Current thresholds (loaded from storage or defaults)
        self.thresholds: Dict[str, float] = self._load_thresholds()

        # Threshold proposal manager (with reference to this manager for execution)
        self.proposal_manager = MAPEKThresholdProposal(
            governance_engine, threshold_manager=self
        )

        logger.info("✅ MAPE-K Threshold Manager initialized")

    def _load_thresholds(self) -> Dict[str, float]:
        """Load thresholds from storage or use defaults."""
        if self.threshold_file.exists():
            try:
                payload = self.threshold_file.read_bytes()
                if not self._verify_threshold_integrity(payload):
                    logger.error(
                        "❌ Threshold integrity check failed, using fail-safe defaults"
                    )
                    return DEFAULT_THRESHOLDS.copy()

                thresholds = json.loads(payload.decode("utf-8"))
                valid, reasons = self._validate_threshold_changes(thresholds)
                if not valid:
                    logger.error(
                        "❌ Invalid threshold file values (%s), using defaults",
                        "; ".join(reasons),
                    )
                    return DEFAULT_THRESHOLDS.copy()

                merged = DEFAULT_THRESHOLDS.copy()
                merged.update({k: float(v) for k, v in thresholds.items()})
                logger.info(f"📂 Loaded thresholds from {self.threshold_file}")
                return merged
            except Exception as e:
                logger.warning(f"⚠️ Failed to load thresholds: {e}")

        logger.info("📂 Using default thresholds")
        return DEFAULT_THRESHOLDS.copy()

    def _canonical_thresholds_json(self) -> str:
        """Create deterministic JSON for hash/HMAC operations."""
        return json.dumps(self.thresholds, sort_keys=True, separators=(",", ":"))

    def _sign_threshold_payload(self, payload: bytes) -> Optional[str]:
        """Sign payload with HMAC-SHA256 if key is configured."""
        if not self.threshold_hmac_key:
            return None
        digest = hmac_new(
            self.threshold_hmac_key.encode("utf-8"), payload, digestmod="sha256"
        ).hexdigest()
        return digest

    def _verify_threshold_integrity(self, payload: bytes) -> bool:
        """Verify threshold file HMAC when integrity key is configured."""
        if not self.threshold_hmac_key:
            return True

        if not self.threshold_hmac_file.exists():
            logger.error(
                "Missing thresholds HMAC file: %s", self.threshold_hmac_file
            )
            return False

        expected_hmac = self.threshold_hmac_file.read_text(encoding="utf-8").strip()
        actual_hmac = self._sign_threshold_payload(payload)
        return bool(actual_hmac) and compare_digest(expected_hmac, actual_hmac)

    def _write_threshold_hmac(self, payload: bytes) -> bool:
        """Write threshold HMAC next to threshold JSON file."""
        signature = self._sign_threshold_payload(payload)
        if signature is None:
            return True

        try:
            self.threshold_hmac_file.write_text(signature, encoding="utf-8")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to write threshold HMAC: {e}")
            return False

    def _save_thresholds(self) -> bool:
        """Save thresholds to local storage."""
        try:
            payload = (
                json.dumps(self.thresholds, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            self.threshold_file.write_bytes(payload)
            if not self._write_threshold_hmac(payload):
                return False
            logger.info(f"💾 Saved thresholds to {self.threshold_file}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to save thresholds: {e}")
            return False

    def _validate_threshold_changes(
        self, changes: Dict[str, Any]
    ) -> Tuple[bool, List[str]]:
        """Validate threshold changes against allowed schema and bounds."""
        errors: List[str] = []

        for parameter, value in changes.items():
            if parameter not in THRESHOLD_BOUNDS:
                errors.append(f"unknown parameter: {parameter}")
                continue

            if not isinstance(value, (int, float)) or not isfinite(float(value)):
                errors.append(f"{parameter}: value must be a finite number")
                continue

            min_v, max_v = THRESHOLD_BOUNDS[parameter]
            numeric_value = float(value)
            if numeric_value < min_v or numeric_value > max_v:
                errors.append(
                    f"{parameter}: {numeric_value} out of bounds [{min_v}, {max_v}]"
                )

        return (len(errors) == 0), errors

    def _record_threshold_change_audit(
        self,
        source: str,
        changes: Dict[str, float],
        previous_values: Dict[str, Optional[float]],
    ) -> None:
        """Append threshold change event to local audit log."""
        record = {
            "timestamp": time.time(),
            "source": source,
            "changes": changes,
            "previous_values": previous_values,
            "thresholds_sha256": sha256(
                self._canonical_thresholds_json().encode("utf-8")
            ).hexdigest(),
        }
        try:
            with open(self.threshold_audit_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, sort_keys=True) + "\n")
        except Exception as e:
            logger.warning(f"⚠️ Failed to write threshold audit event: {e}")

    async def _publish_thresholds_to_ipfs(self) -> Optional[str]:
        """Publish thresholds to IPFS for distribution."""
        if not self.ipfs_client:
            return None

        try:
            data = {
                "thresholds": self.thresholds,
                "timestamp": time.time(),
                "version": "2.0",
            }
            data_json = json.dumps(data)
            cid = await self.ipfs_client.add(data_json, pin=True)
            logger.info(f"📦 Published thresholds to IPFS: {cid}")
            return cid
        except Exception as e:
            logger.error(f"❌ Failed to publish to IPFS: {e}")
            return None

    def get_threshold(self, parameter: str, default: Optional[float] = None) -> float:
        """
        Get current threshold for parameter.

        Args:
            parameter: Parameter name (e.g., "cpu_threshold")
            default: Default value if not found

        Returns:
            Threshold value
        """
        return self.thresholds.get(parameter, default or 80.0)

    def get_all_thresholds(self) -> Dict[str, float]:
        """Get all current thresholds."""
        return self.thresholds.copy()

    def update_threshold(self, parameter: str, value: float) -> bool:
        """
        Update a single threshold.

        Args:
            parameter: Parameter name (e.g., "cpu_threshold")
            value: New threshold value

        Returns:
            True if updated successfully
        """
        return self.apply_threshold_changes({parameter: value}, source="manual")

    def apply_threshold_changes(
        self, changes: Dict[str, float], source: str = "manual"
    ) -> bool:
        """
        Apply threshold changes.

        Args:
            changes: Dict of parameter -> new value
            source: Source of changes ("dao", "manual", etc.)

        Returns:
            True if applied successfully
        """
        try:
            valid, reasons = self._validate_threshold_changes(changes)
            if not valid:
                logger.error(
                    "❌ Threshold change rejected (%s): %s",
                    source,
                    "; ".join(reasons),
                )
                return False

            previous_values: Dict[str, Optional[float]] = {}
            # Apply changes
            for parameter, value in changes.items():
                old_value = self.thresholds.get(parameter)
                previous_values[parameter] = old_value
                self.thresholds[parameter] = float(value)
                logger.info(
                    f"✅ Updated threshold: {parameter} = {value} "
                    f"(was {old_value}, source: {source})"
                )

            # Save to local storage
            if not self._save_thresholds():
                return False

            self._record_threshold_change_audit(
                source=source,
                changes={k: float(v) for k, v in changes.items()},
                previous_values=previous_values,
            )

            # Publish to IPFS (async, non-blocking)
            if self.ipfs_client:
                try:
                    import asyncio

                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self._publish_thresholds_to_ipfs())
                    else:
                        loop.run_until_complete(self._publish_thresholds_to_ipfs())
                except Exception as e:
                    logger.warning(f"⚠️ Failed to publish to IPFS: {e}")

            logger.info(f"✅ Threshold changes applied (source: {source})")
            return True

        except Exception as e:
            logger.error(f"❌ Failed to apply threshold changes: {e}")
            return False

    def check_and_apply_dao_proposals(self) -> int:
        """
        Check for passed DAO proposals and apply threshold changes.

        Returns:
            Number of proposals applied
        """
        applied_count = 0

        # Check all proposals
        for proposal_id, proposal in self.governance.proposals.items():
            if proposal.state == ProposalState.PASSED:
                # Check if it's a threshold proposal
                if hasattr(proposal, "threshold_changes") or any(
                    action.get("type") == "update_mapek_threshold"
                    for action in proposal.actions
                ):
                    # Extract threshold changes from actions
                    changes = {}
                    for action in proposal.actions:
                        if action.get("type") == "update_mapek_threshold":
                            parameter = action.get("parameter")
                            value = action.get("value")
                            if parameter and value is not None:
                                changes[parameter] = value

                    if changes:
                        # Apply changes
                        if self.apply_threshold_changes(changes, source="dao"):
                            # Mark proposal as executed
                            self.governance.execute_proposal(proposal_id)
                            applied_count += 1
                            logger.info(f"✅ Applied DAO proposal: {proposal_id}")

        return applied_count

    def create_threshold_proposal(
        self, title: str, changes: List[ThresholdChange], rationale: str = ""
    ) -> Proposal:
        """
        Create a proposal to change thresholds.

        Args:
            title: Proposal title
            changes: List of threshold changes
            rationale: Explanation

        Returns:
            Created proposal
        """
        return self.proposal_manager.create_threshold_proposal(
            title=title, changes=changes, rationale=rationale
        )

    def verify_threshold_application(
        self, parameter: str, expected_value: float
    ) -> bool:
        """
        Verify that threshold was applied correctly.

        Args:
            parameter: Parameter name
            expected_value: Expected value

        Returns:
            True if matches
        """
        current_value = self.get_threshold(parameter)
        matches = (
            abs(current_value - expected_value) < 0.01
        )  # Allow small floating point differences

        if not matches:
            logger.warning(
                f"⚠️ Threshold mismatch: {parameter} = {current_value}, "
                f"expected {expected_value}"
            )

        return matches


# Helper function to create threshold manager
def create_threshold_manager(
    governance_engine: GovernanceEngine, node_id: str = "default"
) -> MAPEKThresholdManager:
    """
    Create threshold manager with IPFS integration.

    Args:
        governance_engine: DAO governance engine
        node_id: Node identifier

    Returns:
        Threshold manager instance
    """
    from src.storage.ipfs_client import IPFSClient

    # Create IPFS client
    ipfs_client = IPFSClient()

    # Create threshold manager
    manager = MAPEKThresholdManager(
        governance_engine=governance_engine, ipfs_client=ipfs_client
    )

    return manager
