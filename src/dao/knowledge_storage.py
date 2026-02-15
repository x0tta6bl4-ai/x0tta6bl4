"""
DAO Knowledge Storage
=====================

Хранение Knowledge из MAPE-K цикла в DAO (on-chain или IPFS).

Функции:
- Сохранение состояний MAPE-K
- Сохранение FL моделей
- Сохранение инцидентов и решений
- Голосование по предложениям директив
"""

import json
import logging
import os
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeEntry:
    """Entry in Knowledge base."""

    entry_id: str
    entry_type: str  # "mapek_state", "fl_model", "incident", "directive"
    data: Dict[str, Any]
    timestamp: float
    node_id: str
    cid: Optional[str] = None  # IPFS CID if stored on-chain


class DAOKnowledgeStorage:
    """
    DAO-based Knowledge storage.

    Stores MAPE-K states, FL models, and incidents on-chain or IPFS.
    """

    def __init__(self, dao_engine=None, ipfs_client=None, use_real_ipfs: bool = True):
        self.dao_engine = dao_engine

        # Initialize IPFS client (real or mock)
        if ipfs_client is None:
            if use_real_ipfs and IPFS_AVAILABLE:
                try:
                    self.ipfs_client = RealIPFSClient()
                    logger.info("✅ Using real IPFS client")
                except Exception as e:
                    logger.warning(
                        f"Failed to connect to IPFS daemon: {e}. Using mock client."
                    )
                    self.ipfs_client = MockIPFSClient()
            else:
                self.ipfs_client = MockIPFSClient()
        else:
            self.ipfs_client = ipfs_client

        self.local_cache: Dict[str, KnowledgeEntry] = {}

        logger.info("DAO Knowledge Storage initialized")

    async def store_mapek_state(
        self, state: Dict[str, Any], node_id: str
    ) -> Optional[str]:
        """
        Store MAPE-K state in DAO.

        Args:
            state: MAPE-K state data
            node_id: Node that generated the state

        Returns:
            CID or entry ID if stored
        """
        entry = KnowledgeEntry(
            entry_id=f"mapek-{int(time.time() * 1000)}",
            entry_type="mapek_state",
            data=state,
            timestamp=time.time(),
            node_id=node_id,
        )

        # Store locally
        self.local_cache[entry.entry_id] = entry

        # Store on-chain/IPFS if available
        if self.ipfs_client:
            try:
                # Serialize to JSON
                data_json = json.dumps(asdict(entry), default=str)
                cid = await self.ipfs_client.add(data_json)
                entry.cid = cid
                logger.info(f"📜 MAPE-K state stored: {entry.entry_id} → {cid}")
            except Exception as e:
                logger.error(f"Failed to store on IPFS: {e}")

        # Create DAO proposal if critical state
        if state.get("metrics", {}).get("state") in ["EUPHORIC", "MYSTICAL"]:
            await self._create_directive_proposal(entry)

        return entry.entry_id

    async def store_fl_model(
        self, model_data: Dict[str, Any], round_number: int
    ) -> Optional[str]:
        """
        Store FL model in DAO.

        Args:
            model_data: FL model data
            round_number: Training round number

        Returns:
            CID or entry ID if stored
        """
        entry = KnowledgeEntry(
            entry_id=f"fl-model-{round_number}",
            entry_type="fl_model",
            data=model_data,
            timestamp=time.time(),
            node_id="coordinator",
        )

        self.local_cache[entry.entry_id] = entry

        if self.ipfs_client:
            try:
                data_json = json.dumps(asdict(entry), default=str)
                cid = await self.ipfs_client.add(data_json)
                entry.cid = cid
                logger.info(f"🧠 FL model stored: round {round_number} → {cid}")
            except Exception as e:
                logger.error(f"Failed to store FL model: {e}")

        return entry.entry_id

    async def store_incident(
        self, incident: Dict[str, Any], node_id: str
    ) -> Optional[str]:
        """Store incident in DAO."""
        entry = KnowledgeEntry(
            entry_id=f"incident-{int(time.time() * 1000)}",
            entry_type="incident",
            data=incident,
            timestamp=time.time(),
            node_id=node_id,
        )

        self.local_cache[entry.entry_id] = entry

        if self.ipfs_client:
            try:
                data_json = json.dumps(asdict(entry), default=str)
                cid = await self.ipfs_client.add(data_json)
                entry.cid = cid
                logger.info(f"🚨 Incident stored: {entry.entry_id} → {cid}")
            except Exception as e:
                logger.error(f"Failed to store incident: {e}")

        return entry.entry_id

    async def _create_directive_proposal(self, entry: KnowledgeEntry):
        """Create DAO proposal for directive based on Knowledge entry."""
        if not self.dao_engine:
            return

        try:
            # Extract directive from state
            directives = entry.data.get("directives", {})

            # Create proposal
            proposal_id = self.dao_engine.create_proposal(
                title=f"Directive from {entry.node_id}",
                description=f"Auto-generated directive from MAPE-K state",
                duration_seconds=86400,  # 24 hours
            )

            logger.info(f"📋 DAO proposal created: {proposal_id}")
        except Exception as e:
            logger.error(f"Failed to create DAO proposal: {e}")

    def get_knowledge_entry(self, entry_id: str) -> Optional[KnowledgeEntry]:
        """Get knowledge entry by ID."""
        return self.local_cache.get(entry_id)

    def list_entries(self, entry_type: Optional[str] = None) -> List[KnowledgeEntry]:
        """List knowledge entries, optionally filtered by type."""
        entries = list(self.local_cache.values())
        if entry_type:
            entries = [e for e in entries if e.entry_type == entry_type]
        return entries


# Real IPFS client implementation
try:
    import ipfshttpclient

    IPFS_AVAILABLE = True
except ImportError:
    IPFS_AVAILABLE = False
    logger.warning(
        "ipfshttpclient not available. Install with: pip install ipfshttpclient"
    )


class RealIPFSClient:
    """Real IPFS client using ipfshttpclient."""

    def __init__(self, host: str = "/ip4/127.0.0.1/tcp/5001", timeout: int = 30):
        """
        Initialize IPFS client.

        Args:
            host: IPFS API endpoint (default: local IPFS daemon)
            timeout: Request timeout in seconds
        """
        if not IPFS_AVAILABLE:
            raise ImportError(
                "ipfshttpclient not installed. "
                "Install with: pip install ipfshttpclient"
            )

        self.client = ipfshttpclient.connect(addr=host, timeout=timeout)
        logger.info(f"✅ IPFS client connected to {host}")

    async def add(self, data: str) -> str:
        """
        Add data to IPFS.

        Args:
            data: String data to add

        Returns:
            IPFS CID (Content Identifier)
        """
        try:
            # Add data to IPFS
            result = self.client.add_str(data)
            cid = result["Hash"]
            logger.debug(f"📤 Data added to IPFS: {cid}")
            return cid
        except Exception as e:
            logger.error(f"Failed to add data to IPFS: {e}")
            raise

    async def get(self, cid: str) -> str:
        """
        Get data from IPFS by CID.

        Args:
            cid: IPFS Content Identifier

        Returns:
            Retrieved data as string
        """
        try:
            data = self.client.cat(cid)
            return data.decode("utf-8")
        except Exception as e:
            logger.error(f"Failed to get data from IPFS (CID: {cid}): {e}")
            raise

    async def pin(self, cid: str) -> bool:
        """
        Pin content to prevent garbage collection.

        Args:
            cid: IPFS Content Identifier

        Returns:
            True if pinned successfully
        """
        try:
            self.client.pin.add(cid)
            logger.debug(f"📌 Pinned CID: {cid}")
            return True
        except Exception as e:
            logger.error(f"Failed to pin CID {cid}: {e}")
            return False


# Fallback MockIPFSClient for testing when IPFS is not available
class MockIPFSClient:
    """Mock IPFS client for testing when IPFS daemon is not available."""

    def __init__(self):
        logger.warning("⚠️ Using MockIPFSClient - IPFS daemon not available")
        self._storage: Dict[str, str] = {}

    async def add(self, data: str) -> str:
        """Mock IPFS add - stores data in memory."""
        import hashlib

        cid = hashlib.sha256(data.encode()).hexdigest()[:16]
        full_cid = f"Qm{cid}"
        self._storage[full_cid] = data
        logger.debug(f"📤 Mock IPFS: stored data with CID {full_cid}")
        return full_cid

    async def get(self, cid: str) -> str:
        """Mock IPFS get - retrieves data from memory."""
        if cid in self._storage:
            return self._storage[cid]
        raise ValueError(f"CID not found: {cid}")

    async def pin(self, cid: str) -> bool:
        """Mock IPFS pin - always succeeds."""
        return True
