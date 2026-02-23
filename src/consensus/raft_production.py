"""
Production-ready Raft Consensus Enhancements

Improves Raft consensus for production use:
- Persistent storage integration
- Network RPC layer (gRPC ready)
- Cluster membership changes
- Snapshot support
- Performance optimizations
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import base Raft implementation
try:
    from .raft_consensus import LogEntry, RaftConfig, RaftNode, RaftState

    RAFT_AVAILABLE = True
except ImportError:
    RAFT_AVAILABLE = False
    RaftNode = None  # type: ignore
    RaftState = None  # type: ignore
    LogEntry = None  # type: ignore
    RaftConfig = None  # type: ignore


@dataclass
class PersistentState:
    """Persistent Raft state for durability"""

    current_term: int
    voted_for: Optional[str]
    log: List[Dict[str, Any]]  # Serialized log entries


class RaftPersistentStorage:
    """
    Persistent storage for Raft state.

    Provides durability for Raft persistent state:
    - current_term
    - voted_for
    - log
    - snapshots with metadata
    """

    def __init__(self, storage_path: str = "/var/lib/x0tta6bl4/raft"):
        self.storage_path = Path(storage_path)
        self.state_file = self.storage_path / "raft_state.json"
        self.log_file = self.storage_path / "raft_log.json"
        self.snapshot_dir = self.storage_path / "snapshots"
        self.snapshot_metadata_file = self.snapshot_dir / "metadata.json"

        # Create directories if needed
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Raft persistent storage initialized at {storage_path}")

    def save_state(self, node_id: str, term: int, voted_for: Optional[str]):
        """Save persistent state"""
        try:
            state = {
                "node_id": node_id,
                "current_term": term,
                "voted_for": voted_for,
                "timestamp": datetime.now().isoformat(),
            }

            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)

            logger.debug(f"Saved Raft state: term={term}, voted_for={voted_for}")
        except Exception as e:
            logger.error(f"Failed to save Raft state: {e}")

    def load_state(self) -> Optional[Dict[str, Any]]:
        """Load persistent state"""
        try:
            if not self.state_file.exists():
                return None

            with open(self.state_file, "r") as f:
                state = json.load(f)

            logger.debug(f"Loaded Raft state: term={state.get('current_term')}")
            return state
        except Exception as e:
            logger.error(f"Failed to load Raft state: {e}")
            return None

    def save_log(self, log: List[LogEntry]):
        """Save log entries"""
        try:
            log_data = [
                {
                    "term": entry.term,
                    "index": entry.index,
                    "command": str(entry.command),
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in log
            ]

            with open(self.log_file, "w") as f:
                json.dump(log_data, f, indent=2)

            logger.debug(f"Saved {len(log)} log entries")
        except Exception as e:
            logger.error(f"Failed to save Raft log: {e}")

    def load_log(self) -> List[LogEntry]:
        """Load log entries"""
        try:
            if not self.log_file.exists():
                return []

            with open(self.log_file, "r") as f:
                log_data = json.load(f)

            log = []
            for entry_data in log_data:
                entry = LogEntry(
                    term=entry_data["term"],
                    index=entry_data["index"],
                    command=entry_data["command"],
                    timestamp=datetime.fromisoformat(entry_data["timestamp"]),
                )
                log.append(entry)

            logger.debug(f"Loaded {len(log)} log entries")
            return log
        except Exception as e:
            logger.error(f"Failed to load Raft log: {e}")
            return []

    def save_snapshot_metadata(
        self, last_included_index: int, last_included_term: int
    ) -> bool:
        """Save snapshot metadata for log truncation"""
        try:
            metadata = {
                "last_included_index": last_included_index,
                "last_included_term": last_included_term,
                "timestamp": datetime.now().isoformat(),
            }
            with open(self.snapshot_metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
            logger.debug(f"Saved snapshot metadata: index={last_included_index}")
            return True
        except Exception as e:
            logger.error(f"Failed to save snapshot metadata: {e}")
            return False

    def load_snapshot_metadata(self) -> Optional[Dict[str, Any]]:
        """Load snapshot metadata"""
        try:
            if not self.snapshot_metadata_file.exists():
                return None
            with open(self.snapshot_metadata_file, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load snapshot metadata: {e}")
            return None

    def truncate_log_before_snapshot(
        self, last_included_index: int, log: List[LogEntry]
    ) -> List[LogEntry]:
        """
        Truncate log entries that are included in the snapshot.
        """
        try:
            # We keep the entry at last_included_index as a sentinel for prev_log_term calculations
            # Raft log indexing starts at 1 (real entries), 0 is sentinel.
            
            # Find the actual index in the list
            found_idx = -1
            for i, entry in enumerate(log):
                if entry.index == last_included_index:
                    found_idx = i
                    break
            
            if found_idx == -1:
                logger.warning(f"Last included index {last_included_index} not found in log")
                return log

            # Keep entry at last_included_index and everything after it
            truncated_log = log[found_idx:]
            logger.info(
                f"Truncated log: removed entries before index {last_included_index}, keeping {len(truncated_log)} entries"
            )
            return truncated_log
        except Exception as e:
            logger.error(f"Failed to truncate log: {e}")
            return log


class ProductionRaftNode:
    """
    Production-ready Raft node with persistent storage and network layer.

    Extends base RaftNode with:
    - Persistent state storage
    - Network RPC layer (gRPC/HTTP)
    - Snapshot support with compression
    - Cluster membership changes
    - Performance optimizations
    """

    def __init__(
        self,
        node_id: str,
        peers: List[str],
        storage_path: Optional[str] = None,
        config: Optional[RaftConfig] = None,
        network_enabled: bool = True,
        listen_address: str = "0.0.0.0:50051",
    ):
        if not RAFT_AVAILABLE:
            raise ImportError("Raft consensus not available")

        self.node_id = node_id
        self.peers = peers
        self.config = config or RaftConfig()
        self.network_enabled = network_enabled

        # Initialize persistent storage
        self.storage = RaftPersistentStorage(
            storage_path or f"/var/lib/x0tta6bl4/raft/{node_id}"
        )

        # Load persistent state
        self._load_persistent_state()

        # Initialize base Raft node
        self.raft_node = RaftNode(node_id=node_id, peers=peers, config=config)

        # Restore state from storage
        self._restore_state()

        # Initialize network layer if enabled
        self.network_client = None
        self.network_server = None
        if network_enabled:
            try:
                from .raft_network import (get_raft_network_client,
                                           get_raft_network_server)

                self.network_client = get_raft_network_client(
                    node_id, rpc_timeout=self.config.rpc_timeout
                )
                self.network_server = get_raft_network_server(
                    node_id, listen_address=listen_address
                )

                # Setup RPC handlers
                self._setup_rpc_handlers()

                logger.info(f"Network layer initialized for {node_id}")
            except Exception as e:
                logger.warning(f"Failed to initialize network layer: {e}")

        logger.info(f"Production Raft node initialized: {node_id}")

    async def start_network_server(self):
        """Start network server for receiving RPCs"""
        if self.network_server:
            await self.network_server.start()
            logger.info(f"Network server started for {self.node_id}")

    async def stop_network_server(self):
        """Stop network server"""
        if self.network_server:
            await self.network_server.stop()
            logger.info(f"Network server stopped for {self.node_id}")

    async def send_request_vote(
        self,
        peer_id: str,
        peer_address: str,
        term: int,
        last_log_index: int,
        last_log_term: int,
    ) -> bool:
        """
        Send RequestVote RPC to peer via network layer.

        Args:
            peer_id: Peer node ID
            peer_address: Peer address (host:port)
            term: Candidate's term
            last_log_index: Index of candidate's last log entry
            last_log_term: Term of candidate's last log entry

        Returns:
            True if vote granted
        """
        if not self.network_client:
            logger.warning("Network client not available, using simulated RPC")
            return self.raft_node._request_vote_rpc(
                peer_id, term, last_log_index, last_log_term
            )

        response = await self.network_client.request_vote(
            peer_id=peer_id,
            peer_address=peer_address,
            term=term,
            candidate_id=self.node_id,
            last_log_index=last_log_index,
            last_log_term=last_log_term,
        )

        return response.success

    async def send_append_entries(
        self, peer_id: str, peer_address: str, heartbeat: bool = False
    ) -> bool:
        """
        Send AppendEntries RPC to peer via network layer.

        Args:
            peer_id: Peer node ID
            peer_address: Peer address (host:port)
            heartbeat: If True, send empty entries (heartbeat)

        Returns:
            True if append successful
        """
        if not self.network_client:
            logger.warning("Network client not available, using simulated RPC")
            return self.raft_node._append_entries_rpc(peer_id, heartbeat)

        if self.raft_node.state.value != "leader":
            return False

        prev_index = self.raft_node.next_index[peer_id] - 1
        prev_term = (
            self.raft_node.log[prev_index].term
            if prev_index < len(self.raft_node.log)
            else 0
        )

        entries = []
        if not heartbeat:
            entries = [
                {
                    "term": entry.term,
                    "index": entry.index,
                    "command": str(entry.command),
                    "timestamp": entry.timestamp.isoformat(),
                }
                for entry in self.raft_node.log[self.raft_node.next_index[peer_id] :]
            ]

        response = await self.network_client.append_entries(
            peer_id=peer_id,
            peer_address=peer_address,
            term=self.raft_node.current_term,
            leader_id=self.node_id,
            prev_log_index=prev_index,
            prev_log_term=prev_term,
            entries=entries,
            leader_commit=self.raft_node.commit_index,
        )

        if response.success:
            if entries:
                self.raft_node.match_index[peer_id] = entries[-1]["index"]
                self.raft_node.next_index[peer_id] = (
                    self.raft_node.match_index[peer_id] + 1
                )
        else:
            # Decrement next_index to retry
            self.raft_node.next_index[peer_id] = max(
                1, self.raft_node.next_index[peer_id] - 1
            )

        return response.success

    def _setup_rpc_handlers(self):
        """Setup RPC handlers for network server"""
        if not self.network_server:
            return

        async def handle_request_vote(
            term: int, candidate_id: str, last_log_index: int, last_log_term: int
        ) -> Dict[str, Any]:
            """Handle RequestVote RPC"""
            # Use base Raft node's logic
            result = self.raft_node.receive_request_vote(
                term=term,
                candidate_id=candidate_id,
                last_log_index=last_log_index,
                last_log_term=last_log_term,
            )
            return {
                "term": self.raft_node.current_term,
                "vote_granted": result,
                "reason": None,
            }

        async def handle_append_entries(
            term: int,
            leader_id: str,
            prev_log_index: int,
            prev_log_term: int,
            entries: List[Dict[str, Any]],
            leader_commit: int,
        ) -> Dict[str, Any]:
            """Handle AppendEntries RPC"""
            # Convert entries back to LogEntry objects
            log_entries = []
            for entry_data in entries:
                from .raft_consensus import LogEntry

                log_entries.append(
                    LogEntry(
                        term=entry_data["term"],
                        index=entry_data["index"],
                        command=entry_data["command"],
                        timestamp=datetime.fromisoformat(
                            entry_data.get("timestamp", datetime.now().isoformat())
                        ),
                    )
                )

            result = self.raft_node.receive_append_entries(
                term=term,
                leader_id=leader_id,
                prev_log_index=prev_log_index,
                prev_log_term=prev_log_term,
                entries=log_entries,
                leader_commit=leader_commit,
            )

            return {
                "term": self.raft_node.current_term,
                "success": result,
                "reason": None,
            }

        self.network_server.set_request_vote_handler(handle_request_vote)
        self.network_server.set_append_entries_handler(handle_append_entries)

    def _load_persistent_state(self):
        """Load persistent state from storage"""
        state = self.storage.load_state()
        if state:
            # Restore term and voted_for
            self._saved_term = state.get("current_term", 0)
            self._saved_voted_for = state.get("voted_for")
        else:
            self._saved_term = 0
            self._saved_voted_for = None

    def _restore_state(self):
        """Restore Raft node state from persistent storage"""
        # Load snapshot metadata if it exists
        metadata = self.storage.load_snapshot_metadata()
        if metadata:
            self.raft_node.last_included_index = metadata["last_included_index"]
            self.raft_node.last_included_term = metadata["last_included_term"]
            self.raft_node.last_applied = self.raft_node.last_included_index
            self.raft_node.commit_index = self.raft_node.last_included_index

        # Try to restore from latest snapshot first
        snapshot_restored = self.restore_from_snapshot()

        # Restore term
        if hasattr(self, "_saved_term"):
            self.raft_node.current_term = self._saved_term

        # Restore voted_for
        if hasattr(self, "_saved_voted_for"):
            self.raft_node.voted_for = self._saved_voted_for

        # Restore log
        log = self.storage.load_log()
        if log:
            self.raft_node.log = log

        if snapshot_restored:
            logger.info(f"Node {self.node_id} restored from snapshot")

    def append_entry(self, command: Any) -> bool:
        """
        Append entry to log (with persistence).

        Args:
            command: Command to append

        Returns:
            True if appended successfully
        """
        if self.raft_node.state != RaftState.LEADER:
            logger.warning(f"Node {self.node_id} is not leader, cannot append entry")
            return False

        # Append via base node
        success = self.raft_node.append_entry(command)

        if success:
            # Persist log
            self.storage.save_log(self.raft_node.log)
            # Persist state
            self.storage.save_state(
                self.node_id, self.raft_node.current_term, self.raft_node.voted_for
            )

        return success

    def get_status(self) -> Dict[str, Any]:
        """Get node status"""
        return {
            "node_id": self.node_id,
            "state": self.raft_node.state.value,
            "term": self.raft_node.current_term,
            "commit_index": self.raft_node.commit_index,
            "last_applied": self.raft_node.last_applied,
            "log_length": len(self.raft_node.log),
            "peers": self.peers,
        }

    def create_snapshot(
        self, last_included_index: int, snapshot_data: Any, compress: bool = True
    ) -> bool:
        """
        Create snapshot of state machine with JSON serialization and log truncation.
        
        SECURITY: Uses JSON instead of pickle to prevent RCE vulnerabilities.
        Complex objects should implement to_dict()/from_dict() for serialization.
        """
        try:
            if last_included_index < 0:
                logger.error(f"Invalid snapshot index: {last_included_index}")
                return False

            log_len = len(self.raft_node.log)
            if last_included_index >= log_len and not snapshot_data:
                logger.error(
                    "Invalid snapshot request: index %s exceeds log length %s",
                    last_included_index,
                    log_len,
                )
                return False

            if 0 <= last_included_index < log_len:
                last_included_term = self.raft_node.log[last_included_index].term
            else:
                last_included_term = self.raft_node.current_term

            snapshot_file = (
                self.storage.snapshot_dir / f"snapshot_{last_included_index:010d}.json"
            )

            # Serialize snapshot_data to JSON-safe format
            serializable_data = self._serialize_snapshot_data(snapshot_data)

            snapshot = {
                "last_included_index": last_included_index,
                "last_included_term": last_included_term,
                "data": serializable_data,
                "timestamp": datetime.now().isoformat(),
            }

            # Use JSON for safe serialization (no RCE risk)
            snapshot_json = json.dumps(snapshot, indent=2, default=str)

            # Compress if requested
            if compress:
                import gzip
                snapshot_file = snapshot_file.with_suffix(".json.gz")
                with gzip.open(snapshot_file, "wt", encoding="utf-8") as f:
                    f.write(snapshot_json)
            else:
                with open(snapshot_file, "w", encoding="utf-8") as f:
                    f.write(snapshot_json)

            # Save snapshot metadata
            self.storage.save_snapshot_metadata(last_included_index, last_included_term)
            
            # Update core RaftNode metadata
            self.raft_node.last_included_index = last_included_index
            self.raft_node.last_included_term = last_included_term

            # Truncate log
            if log_len and last_included_index < log_len:
                self.raft_node.log = self.storage.truncate_log_before_snapshot(
                    last_included_index, self.raft_node.log
                )

            # Persist updated log
            self.storage.save_log(self.raft_node.log)

            logger.info(
                f"Created and persisted JSON snapshot at index {last_included_index}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to create snapshot: {e}")
            return False

    def _serialize_snapshot_data(self, data: Any) -> Any:
        """
        Convert snapshot data to JSON-serializable format.
        
        Handles common types and objects with to_dict() method.
        """
        if data is None:
            return None
        if isinstance(data, (str, int, float, bool)):
            return data
        if isinstance(data, dict):
            return {k: self._serialize_snapshot_data(v) for k, v in data.items()}
        if isinstance(data, (list, tuple)):
            return [self._serialize_snapshot_data(item) for item in data]
        if hasattr(data, "to_dict"):
            return data.to_dict()
        # Fallback: convert to string representation
        logger.warning(f"Snapshot data type {type(data)} not directly serializable, using str()")
        return str(data)

    def load_snapshot(
        self, last_included_index: Optional[int] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Load JSON snapshot from storage.
        
        SECURITY: Uses JSON instead of pickle to prevent RCE vulnerabilities.
        """
        try:
            if last_included_index is None:
                metadata = self.storage.load_snapshot_metadata()
                if metadata:
                    last_included_index = metadata.get("last_included_index")
                else:
                    return None

            # Try compressed first
            snapshot_file = (
                self.storage.snapshot_dir
                / f"snapshot_{last_included_index:010d}.json.gz"
            )
            if snapshot_file.exists():
                import gzip
                with gzip.open(snapshot_file, "rt", encoding="utf-8") as f:
                    return json.load(f)

            # Try uncompressed
            snapshot_file = (
                self.storage.snapshot_dir / f"snapshot_{last_included_index:010d}.json"
            )
            if snapshot_file.exists():
                with open(snapshot_file, "r", encoding="utf-8") as f:
                    return json.load(f)

            return None
        except Exception as e:
            logger.error(f"Failed to load snapshot: {e}")
            return None

    def restore_from_snapshot(self) -> bool:
        """
        Restore node state and apply snapshot data to the state machine.
        """
        try:
            metadata = self.storage.load_snapshot_metadata()
            if not metadata:
                return False

            snapshot = self.load_snapshot(metadata.get("last_included_index"))
            if not snapshot:
                return False

            # Update node state
            self.raft_node.last_applied = snapshot["last_included_index"]
            self.raft_node.commit_index = max(
                self.raft_node.commit_index, snapshot["last_included_index"]
            )

            # NOTE: In a real app, we would notify the state machine here
            # to replace its state with snapshot["data"]
            if hasattr(self.raft_node, "state_machine") and self.raft_node.state_machine:
                self.raft_node.state_machine.restore(snapshot["data"])

            logger.info(
                f"Restored node state from snapshot at index {snapshot['last_included_index']}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to restore from snapshot: {e}")
            return False


# Global instance
_production_raft_node: Optional[ProductionRaftNode] = None


def get_production_raft_node(
    node_id: str, peers: List[str], storage_path: Optional[str] = None
) -> ProductionRaftNode:
    """Get or create production Raft node"""
    global _production_raft_node
    if _production_raft_node is None:
        _production_raft_node = ProductionRaftNode(
            node_id=node_id, peers=peers, storage_path=storage_path
        )
    return _production_raft_node
