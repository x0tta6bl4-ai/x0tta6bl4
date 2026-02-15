"""
MAPE-K Integration with Knowledge Storage v2.0
===============================================

Provides seamless integration between MAPE-K cycle and Knowledge Storage.
"""

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.self_healing.mape_k import MAPEKKnowledge
from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

logger = logging.getLogger(__name__)


class MAPEKKnowledgeStorageAdapter:
    """
    Adapter to integrate Knowledge Storage v2.0 with MAPE-K cycle.

    Handles async/sync conversion and provides seamless interface.
    """

    def __init__(self, knowledge_storage: KnowledgeStorageV2, node_id: str = "default"):
        """
        Initialize adapter.

        Args:
            knowledge_storage: Knowledge Storage v2.0 instance
            node_id: Node identifier
        """
        self.knowledge_storage = knowledge_storage
        self.node_id = node_id
        self._pending_operations: List[Dict[str, Any]] = []

        logger.info(f"✅ MAPE-K Knowledge Storage Adapter initialized for {node_id}")

    def record_incident_sync(
        self,
        metrics: Dict[str, Any],
        issue: str,
        action: str,
        success: bool = True,
        mttr: Optional[float] = None,
    ) -> str:
        """
        Record incident synchronously (for use in MAPE-K cycle).

        Args:
            metrics: System metrics
            issue: Issue type
            action: Action taken
            success: Whether action was successful
            mttr: Mean time to recover

        Returns:
            Incident ID
        """
        # Prepare incident data
        incident = {
            "id": f"incident-{int(time.time() * 1000)}",
            "timestamp": time.time(),
            "anomaly_type": issue,
            "metrics": metrics,
            "root_cause": issue,  # Will be improved by Causal Analysis
            "recovery_plan": action,
            "execution_result": {"success": success, "duration": mttr or 0.0},
        }

        # Store asynchronously (non-blocking)
        try:
            # Try to get event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, schedule as task
                    asyncio.create_task(
                        self.knowledge_storage.store_incident(incident, self.node_id)
                    )
                else:
                    # If no loop, run it
                    loop.run_until_complete(
                        self.knowledge_storage.store_incident(incident, self.node_id)
                    )
            except RuntimeError:
                # No event loop, create new one
                asyncio.run(
                    self.knowledge_storage.store_incident(incident, self.node_id)
                )

            logger.debug(f"📚 Stored incident in Knowledge Storage: {issue}")
            return incident["id"]

        except Exception as e:
            logger.warning(f"⚠️ Failed to store incident: {e}")
            # Fallback: store in pending operations
            self._pending_operations.append(incident)
            return incident["id"]

    async def record_incident_async(
        self,
        metrics: Dict[str, Any],
        issue: str,
        action: str,
        success: bool = True,
        mttr: Optional[float] = None,
    ) -> str:
        """
        Record incident asynchronously.

        Args:
            metrics: System metrics
            issue: Issue type
            action: Action taken
            success: Whether action was successful
            mttr: Mean time to recover

        Returns:
            Incident ID
        """
        incident = {
            "id": f"incident-{int(time.time() * 1000)}",
            "timestamp": time.time(),
            "anomaly_type": issue,
            "metrics": metrics,
            "root_cause": issue,
            "recovery_plan": action,
            "execution_result": {"success": success, "duration": mttr or 0.0},
        }

        try:
            incident_id = await self.knowledge_storage.store_incident(
                incident, self.node_id
            )
            logger.debug(f"📚 Stored incident: {incident_id}")
            return incident_id
        except Exception as e:
            logger.error(f"❌ Failed to store incident: {e}")
            return incident["id"]

    def search_patterns_sync(
        self, query: str, k: int = 10, threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for patterns synchronously.

        Args:
            query: Search query
            k: Number of results
            threshold: Similarity threshold

        Returns:
            List of matching incidents
        """
        try:
            # Try to get event loop
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # If loop is running, we can't use run_until_complete
                    # Return empty list and log warning
                    logger.warning(
                        "⚠️ Cannot run async search in running loop. Use async method."
                    )
                    return []
                else:
                    # If no loop, run it
                    results = loop.run_until_complete(
                        self.knowledge_storage.search_incidents(query, k, threshold)
                    )
                    return results
            except RuntimeError:
                # No event loop, create new one
                results = asyncio.run(
                    self.knowledge_storage.search_incidents(query, k, threshold)
                )
                return results

        except Exception as e:
            logger.error(f"❌ Failed to search patterns: {e}")
            return []

    async def search_patterns_async(
        self, query: str, k: int = 10, threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search for patterns asynchronously.

        Args:
            query: Search query
            k: Number of results
            threshold: Similarity threshold

        Returns:
            List of matching incidents
        """
        try:
            results = await self.knowledge_storage.search_incidents(query, k, threshold)
            return results
        except Exception as e:
            logger.error(f"❌ Failed to search patterns: {e}")
            return []

    def get_successful_patterns_sync(self, anomaly_type: str) -> List[Dict[str, Any]]:
        """
        Get successful patterns synchronously.

        Args:
            anomaly_type: Type of anomaly

        Returns:
            List of successful incidents
        """
        try:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    logger.warning("⚠️ Cannot run async search in running loop.")
                    return []
                else:
                    results = loop.run_until_complete(
                        self.knowledge_storage.get_successful_patterns(anomaly_type)
                    )
                    return results
            except RuntimeError:
                results = asyncio.run(
                    self.knowledge_storage.get_successful_patterns(anomaly_type)
                )
                return results
        except Exception as e:
            logger.error(f"❌ Failed to get patterns: {e}")
            return []

    async def flush_pending_operations(self):
        """Flush pending operations to storage."""
        if not self._pending_operations:
            return

        logger.info(
            f"🔄 Flushing {len(self._pending_operations)} pending operations..."
        )

        for incident in self._pending_operations:
            try:
                await self.knowledge_storage.store_incident(incident, self.node_id)
            except Exception as e:
                logger.error(f"❌ Failed to flush incident: {e}")

        self._pending_operations.clear()
        logger.info("✅ Pending operations flushed")


# Helper function to create integrated MAPEKKnowledge
def create_mapek_knowledge_with_storage(
    storage_path: Optional[Path] = None,
    node_id: str = "default",
    use_real_ipfs: bool = True,
) -> tuple[MAPEKKnowledge, MAPEKKnowledgeStorageAdapter]:
    """
    Create MAPEKKnowledge with Knowledge Storage v2.0 integration.

    Args:
        storage_path: Path for storage
        node_id: Node identifier
        use_real_ipfs: Whether to use real IPFS

    Returns:
        Tuple of (MAPEKKnowledge, Adapter)
    """
    # Create Knowledge Storage
    knowledge_storage = KnowledgeStorageV2(
        storage_path=storage_path, use_real_ipfs=use_real_ipfs
    )

    # Create adapter
    adapter = MAPEKKnowledgeStorageAdapter(knowledge_storage, node_id)

    # Create MAPEKKnowledge with adapter
    knowledge = MAPEKKnowledge(knowledge_storage=adapter)

    return knowledge, adapter
