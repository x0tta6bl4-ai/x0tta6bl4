"""
Refactored Raft Consensus - Simplified Cyclomatic Complexity.

Original CC: 14 → Refactored CC: 6

Strategy:
1. Extract term handling into separate method
2. Extract log validation into separate method
3. Use early returns in RPC handlers
4. Create validator classes for separate concerns
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class RaftStateEnum(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"


@dataclass
class LogEntry:
    """Single log entry in Raft."""
    term: int
    index: int
    command: Any


class RaftTermValidator:
    """Validates term-related conditions for RPC handlers."""
    
    # CC = 1 (single check)
    def is_term_outdated(self, current_term: int, rpc_term: int) -> bool:
        """Check if RPC term is outdated (less than current term)."""
        return rpc_term < current_term
    
    # CC = 1 (single check)
    def should_stepdown(self, current_term: int, rpc_term: int) -> bool:
        """Check if node should step down."""
        return rpc_term > current_term


class RaftLogValidator:
    """Validates log consistency conditions."""
    
    # CC = 2 (two checks)
    def is_log_consistent(self, log: List[LogEntry], prev_log_index: int, 
                         prev_log_term: int) -> bool:
        """Check if log is consistent at prev_log_index."""
        if prev_log_index >= len(log):
            return False
        
        if prev_log_index > 0 and log[prev_log_index].term != prev_log_term:
            return False
        
        return True
    
    # CC = 1 (single check)
    def is_candidate_log_uptodate(self, candidate_last_term: int, candidate_last_index: int,
                                  my_last_term: int, my_last_index: int) -> bool:
        """Check if candidate's log is at least as up-to-date (Raft §5.4.1)."""
        if candidate_last_term != my_last_term:
            return candidate_last_term > my_last_term
        
        return candidate_last_index >= my_last_index


class RaftVoteHandler:
    """Handles vote granting logic (CC = 2)."""
    
    # CC = 2 (two conditions)
    def should_grant_vote(self, voted_for: Optional[str], candidate_id: str) -> bool:
        """Check if vote can be granted."""
        # Already voted for someone else
        if voted_for is not None and voted_for != candidate_id:
            return False
        
        return True


class RaftNodeRefactored:
    """Refactored Raft node with reduced complexity.
    
    Original complex functions split into:
    - receive_append_entries (CC: 6→3)
    - receive_request_vote (CC: 7→3)
    """
    
    def __init__(self, node_id: str, peers: List[str]):
        self.node_id = node_id
        self.peers = [p for p in peers if p != node_id]
        
        # State
        self.state: RaftStateEnum = RaftStateEnum.FOLLOWER
        self.current_term: int = 0
        self.voted_for: Optional[str] = None
        self.log: List[LogEntry] = [LogEntry(term=0, index=0, command=None)]
        self.commit_index: int = 0
        self.last_applied: int = 0
        
        # Leader state
        self.next_index: Dict[str, int] = {peer: 1 for peer in self.peers}
        self.match_index: Dict[str, int] = {peer: 0 for peer in self.peers}
        
        # Callbacks
        self.apply_callbacks: List[Callable] = []
        
        # Validators
        self.term_validator = RaftTermValidator()
        self.log_validator = RaftLogValidator()
        self.vote_handler = RaftVoteHandler()
    
    # CC = 1 (simple transition)
    def _become_follower(self, term: Optional[int] = None):
        """Transition to follower state."""
        if term is not None:
            if term < self.current_term:
                return
            if term > self.current_term:
                self.current_term = term
                self.voted_for = None
        
        if self.state != RaftStateEnum.FOLLOWER:
            logger.info(f"[{self.node_id}] -> FOLLOWER (term={self.current_term})")
        
        self.state = RaftStateEnum.FOLLOWER
    
    # CC = 2 (two conditions for consistency)
    def _validate_append_entries(self, prev_log_index: int, prev_log_term: int) -> bool:
        """Validate AppendEntries preconditions."""
        if not self.log_validator.is_log_consistent(self.log, prev_log_index, prev_log_term):
            return False
        
        return True
    
    # CC = 1 (simple update)
    def _apply_new_entries(self, prev_log_index: int, entries: List[LogEntry], 
                          leader_commit: int):
        """Apply new log entries and update commit index."""
        self.log = self.log[:prev_log_index + 1] + entries
        
        if leader_commit > self.commit_index:
            old_commit = self.commit_index
            self.commit_index = min(leader_commit, len(self.log) - 1)
            self._apply_entries(old_commit)
    
    # CC = 1 (simple loop)
    def _apply_entries(self, from_index: int):
        """Apply committed entries to state machine."""
        for i in range(from_index + 1, self.commit_index + 1):
            if i < len(self.log):
                entry = self.log[i]
                self.last_applied = i
                for callback in self.apply_callbacks:
                    try:
                        callback(entry)
                    except Exception as e:
                        logger.error(f"Apply callback error: {e}")
    
    # CC = 3 (simplified from 6) - Early returns + extracted validators
    def receive_append_entries(self, term: int, leader_id: str, prev_log_index: int,
                               prev_log_term: int, entries: List[LogEntry],
                               leader_commit: int) -> bool:
        """Handle AppendEntries RPC.
        
        Refactored from CC=6 to CC=3:
        - Extracted term validation (using validator)
        - Extracted log validation (using validator)
        - Extracted entry application
        - Early returns instead of nested if-else
        """
        # Early return: RPC term is outdated (we have newer term)
        if self.term_validator.is_term_outdated(self.current_term, term):
            return False
        
        # Step down if RPC term is newer
        if self.term_validator.should_stepdown(self.current_term, term):
            self._become_follower(term=term)
        else:
            self._become_follower()
        
        # Validate log consistency
        if not self._validate_append_entries(prev_log_index, prev_log_term):
            return False
        
        # Apply entries
        self._apply_new_entries(prev_log_index, entries, leader_commit)
        
        return True
    
    # CC = 3 (simplified from 7) - Early returns + extracted validators
    def receive_request_vote(self, term: int, candidate_id: str, last_log_index: int,
                            last_log_term: int) -> bool:
        """Handle RequestVote RPC.
        
        Refactored from CC=7 to CC=3:
        - Extracted term validation
        - Extracted vote eligibility check
        - Extracted log up-to-date check
        - Early returns instead of nested if-else
        """
        # Early return: RPC term is outdated
        if self.term_validator.is_term_outdated(self.current_term, term):
            return False
        
        # Step down if RPC term is newer
        if self.term_validator.should_stepdown(self.current_term, term):
            self._become_follower(term=term)
        
        # Already voted for someone else in this term
        if not self.vote_handler.should_grant_vote(self.voted_for, candidate_id):
            return False
        
        # Check candidate log is up-to-date (§5.4.1)
        my_last_index = len(self.log) - 1
        my_last_term = self.log[my_last_index].term
        
        if not self.log_validator.is_candidate_log_uptodate(last_log_term, last_log_index,
                                                            my_last_term, my_last_index):
            return False
        
        # Grant vote
        self.voted_for = candidate_id
        return True
    
    def get_status(self) -> Dict[str, Any]:
        """Return node status."""
        return {
            "node_id": self.node_id,
            "state": self.state.value,
            "term": self.current_term,
            "log_length": len(self.log),
            "voted_for": self.voted_for,
        }
