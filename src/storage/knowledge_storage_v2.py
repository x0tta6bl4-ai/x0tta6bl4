"""
Knowledge Storage v2.0 for x0tta6bl4
=====================================

Complete implementation of Knowledge Storage with:
- IPFS for distributed storage
- CRDT for conflict-free synchronization
- Vector Memory (HNSW) for RAG
- SQLite for local cache
"""

import asyncio
import json
import logging
import sqlite3
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from src.storage.ipfs_client import IPFSClient, MockIPFSClient
from src.storage.vector_index import VectorIndex

logger = logging.getLogger(__name__)


@dataclass
class IncidentEntry:
    """Incident entry in knowledge base."""

    incident_id: str
    timestamp: float
    node_id: str
    anomaly_type: str
    metrics: Dict[str, Any]
    root_cause: str
    recovery_plan: str
    execution_result: Dict[str, Any]
    signature: Optional[str] = None
    ipfs_cid: Optional[str] = None
    embedding: Optional[List[float]] = None


class KnowledgeStorageV2:
    """
    Complete Knowledge Storage implementation.

    Features:
    - IPFS for distributed storage
    - CRDT for synchronization
    - Vector Memory (HNSW) for semantic search
    - SQLite for local cache
    - Integration with MAPE-K cycle
    """

    def __init__(
        self,
        node_id: str,
        storage_path: Path = Path("/var/lib/x0tta6bl4"),
        ipfs_client: Optional[IPFSClient] = None,
        use_real_ipfs: bool = True,
    ):
        """
        Initialize Knowledge Storage.

        Args:
            node_id: The ID of the current node.
            storage_path: Base path for local storage
            ipfs_client: IPFS client (optional)
            use_real_ipfs: Whether to use real IPFS or mock
        """
        self.node_id = node_id
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)

        # Initialize IPFS client
        if ipfs_client is None:
            if use_real_ipfs:
                self.ipfs_client = IPFSClient()
            else:
                self.ipfs_client = MockIPFSClient()
        else:
            self.ipfs_client = ipfs_client

        # Initialize SQLite database
        self.db_path = self.storage_path / "incidents.db"
        self._init_database()

        # Initialize Vector Index
        vector_index_path = self.storage_path / "hnsw_index"
        self.vector_index = VectorIndex(index_path=vector_index_path)
        try:
            self.vector_index.load(vector_index_path)
        except Exception as e:
            logger.warning(f"⚠️ Failed to load vector index: {e}. Starting fresh.")

        # Initialize CRDT sync (if available)
        try:
            from src.data_sync.crdt_sync import CRDTSync

            self.crdt_sync = CRDTSync(self.node_id)
        except (ImportError, AttributeError):
            self.crdt_sync = None
            logger.warning("⚠️ CRDT sync not available")

        logger.info("✅ Knowledge Storage v2.0 initialized")

    def _init_database(self):
        """Initialize SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Create incidents table
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS incidents (
                incident_id TEXT PRIMARY KEY,
                timestamp REAL,
                node_id TEXT,
                anomaly_type TEXT,
                metrics TEXT,
                root_cause TEXT,
                recovery_plan TEXT,
                execution_result TEXT,
                signature TEXT,
                ipfs_cid TEXT,
                embedding TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
        )

        # Create index for faster queries
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_timestamp ON incidents(timestamp)
        """
        )
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_anomaly_type ON incidents(anomaly_type)
        """
        )

        conn.commit()
        conn.close()
        logger.info(f"✅ SQLite database initialized: {self.db_path}")

    async def store_incident(self, incident: Dict[str, Any], node_id: str) -> str:
        """
        Store incident in knowledge base.

        Args:
            incident: Incident data
            node_id: Node that generated the incident

        Returns:
            Incident ID
        """
        incident_id = incident.get("id") or f"incident-{int(time.time() * 1000)}"

        # Create entry
        entry = IncidentEntry(
            incident_id=incident_id,
            timestamp=incident.get("timestamp", time.time()),
            node_id=node_id,
            anomaly_type=incident.get("anomaly_type", "UNKNOWN"),
            metrics=incident.get("metrics", {}),
            root_cause=incident.get("root_cause", ""),
            recovery_plan=incident.get("recovery_plan", ""),
            execution_result=incident.get("execution_result", {}),
            signature=incident.get("signature"),
            ipfs_cid=None,
            embedding=None,
        )

        # Store in IPFS
        try:
            data_json = json.dumps(asdict(entry), default=str)
            cid = await self.ipfs_client.add(data_json, pin=True)
            entry.ipfs_cid = cid
            logger.info(f"📦 Stored incident in IPFS: {incident_id} → {cid}")
        except Exception as e:
            logger.error(f"❌ Failed to store in IPFS: {e}")

        # Generate embedding and add to vector index
        try:
            text = self._prepare_text_for_embedding(entry)
            embedding = self.vector_index.embed(text)
            entry.embedding = (
                embedding.tolist() if hasattr(embedding, "tolist") else embedding
            )

            # Add to vector index
            doc_id = self.vector_index.add(
                text=text,
                metadata={
                    "incident_id": incident_id,
                    "anomaly_type": entry.anomaly_type,
                    "root_cause": entry.root_cause,
                    "recovery_plan": entry.recovery_plan,
                    "timestamp": entry.timestamp,
                },
                embedding=embedding,
            )
            logger.info(f"🔍 Added to vector index: {incident_id} → doc_id {doc_id}")
        except Exception as e:
            logger.error(f"❌ Failed to add to vector index: {e}")

        # Store in SQLite (local cache)
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT OR REPLACE INTO incidents (
                    incident_id, timestamp, node_id, anomaly_type,
                    metrics, root_cause, recovery_plan, execution_result,
                    signature, ipfs_cid, embedding
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    entry.incident_id,
                    entry.timestamp,
                    entry.node_id,
                    entry.anomaly_type,
                    json.dumps(entry.metrics),
                    entry.root_cause,
                    entry.recovery_plan,
                    json.dumps(entry.execution_result),
                    entry.signature,
                    entry.ipfs_cid,
                    json.dumps(entry.embedding) if entry.embedding else None,
                ),
            )
            conn.commit()
            conn.close()
            logger.info(f"💾 Stored in SQLite: {incident_id}")
        except Exception as e:
            logger.error(f"❌ Failed to store in SQLite: {e}")

        # Sync via CRDT (if available)
        if self.crdt_sync and hasattr(self.crdt_sync, "sync"):
            try:
                if asyncio.iscoroutinefunction(self.crdt_sync.sync):
                    await self.crdt_sync.sync(entry.incident_id, asdict(entry))
                else:
                    self.crdt_sync.sync(entry.incident_id, asdict(entry))
            except Exception as e:
                logger.warning(f"⚠️ CRDT sync failed: {e}")

        return incident_id

    def _prepare_text_for_embedding(self, entry: IncidentEntry) -> str:
        """Prepare text for embedding."""
        parts = [
            f"Anomaly type: {entry.anomaly_type}",
            f"Root cause: {entry.root_cause}",
            f"Recovery plan: {entry.recovery_plan}",
        ]

        if entry.execution_result:
            parts.append(f"Result: {entry.execution_result.get('success', False)}")
            if "duration" in entry.execution_result:
                parts.append(f"Duration: {entry.execution_result['duration']}s")

        return " ".join(parts)

    async def search_incidents(
        self, query: str, k: int = 10, threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Search incidents using hybrid search (BM25 + Vector).

        Args:
            query: Search query
            k: Number of results
            threshold: Similarity threshold

        Returns:
            List of matching incidents
        """
        # Vector search
        vector_results = self.vector_index.search(query, k=k, threshold=threshold)

        # Convert to incident format
        incidents = []
        for doc_id, similarity, metadata in vector_results:
            incident_id = metadata.get("incident_id")
            if incident_id:
                # Retrieve from SQLite
                incident = self._get_incident_from_db(incident_id)
                if incident:
                    incident["similarity"] = similarity
                    incidents.append(incident)

        # Sort by similarity
        incidents.sort(key=lambda x: x.get("similarity", 0.0), reverse=True)

        return incidents[:k]

    def _get_incident_from_db(self, incident_id: str) -> Optional[Dict[str, Any]]:
        """Get incident from SQLite database."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM incidents WHERE incident_id = ?
            """,
                (incident_id,),
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                return {
                    "incident_id": row[0],
                    "timestamp": row[1],
                    "node_id": row[2],
                    "anomaly_type": row[3],
                    "metrics": json.loads(row[4]) if row[4] else {},
                    "root_cause": row[5],
                    "recovery_plan": row[6],
                    "execution_result": json.loads(row[7]) if row[7] else {},
                    "signature": row[8],
                    "ipfs_cid": row[9],
                    "embedding": json.loads(row[10]) if row[10] else None,
                }
        except Exception as e:
            logger.error(f"❌ Failed to get incident from DB: {e}")

        return None

    async def get_successful_patterns(self, anomaly_type: str) -> List[Dict[str, Any]]:
        """
        Get successful recovery patterns for anomaly type.

        Args:
            anomaly_type: Type of anomaly (e.g., "MEMORY_PRESSURE")

        Returns:
            List of successful incidents
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT * FROM incidents
                WHERE anomaly_type = ? AND execution_result LIKE '%"success": true%'
                ORDER BY timestamp DESC
                LIMIT 100
            """,
                (anomaly_type,),
            )
            rows = cursor.fetchall()
            conn.close()

            incidents = []
            for row in rows:
                execution_result = json.loads(row[7]) if row[7] else {}
                if execution_result.get("success"):
                    incidents.append(
                        {
                            "incident_id": row[0],
                            "timestamp": row[1],
                            "recovery_plan": row[6],
                            "execution_result": execution_result,
                        }
                    )

            return incidents
        except Exception as e:
            logger.error(f"❌ Failed to get patterns: {e}")
            return []

    def save_index(self):
        """Save vector index to disk."""
        try:
            self.vector_index.save()
            logger.info("💾 Vector index saved")
        except Exception as e:
            logger.error(f"❌ Failed to save index: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM incidents")
            count = cursor.fetchone()[0]
            conn.close()

            return {
                "total_incidents": count,
                "ipfs_available": self.ipfs_client.is_available(),
                "vector_index_stats": self.vector_index.get_stats(),
            }
        except Exception as e:
            logger.error(f"❌ Failed to get stats: {e}")
            return {}
