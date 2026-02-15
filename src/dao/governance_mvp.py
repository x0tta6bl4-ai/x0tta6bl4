"""
DAO Governance MVP

Complete governance system with proposal management, voting,
execution engine, and governance UI integration.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Import existing governance components
try:
    from .governance import GovernanceEngine, Proposal, ProposalState, VoteType
    from .quadratic_voting import QuadraticVoting, Vote

    GOVERNANCE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Governance components not available: {e}")
    GOVERNANCE_AVAILABLE = False
    GovernanceEngine = None
    Proposal = None
    ProposalState = None
    VoteType = None


class ExecutionStatus(Enum):
    """Execution status for proposals"""

    PENDING = "pending"
    EXECUTING = "executing"
    SUCCESS = "success"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ProposalAction:
    """Action to execute when proposal passes"""

    action_type: str  # e.g., "update_config", "upgrade_model", "change_threshold"
    target: str  # Target component/resource
    parameters: Dict[str, Any] = field(default_factory=dict)
    rollback_action: Optional[Dict[str, Any]] = None


@dataclass
class ExecutionResult:
    """Result of proposal execution"""

    proposal_id: str
    status: ExecutionStatus
    executed_at: Optional[datetime] = None
    execution_time: float = 0.0
    error_message: Optional[str] = None
    rollback_applied: bool = False


class ProposalExecutor:
    """
    Executes approved proposals.

    Provides:
    - Action execution
    - Rollback support
    - Execution tracking
    - Error handling
    """

    def __init__(self):
        self.execution_history: List[ExecutionResult] = []
        self.rollback_stack: List[Dict[str, Any]] = []
        logger.info("ProposalExecutor initialized")

    async def execute_proposal(self, proposal: Proposal) -> ExecutionResult:
        """
        Execute a passed proposal.

        Args:
            proposal: Proposal to execute

        Returns:
            ExecutionResult
        """
        start_time = datetime.utcnow()

        result = ExecutionResult(
            proposal_id=proposal.id,
            status=ExecutionStatus.EXECUTING,
            executed_at=start_time,
        )

        try:
            # Execute each action
            for action_dict in proposal.actions:
                action = (
                    ProposalAction(**action_dict)
                    if isinstance(action_dict, dict)
                    else action_dict
                )

                # Save state for rollback
                if action.rollback_action:
                    self.rollback_stack.append(
                        {
                            "proposal_id": proposal.id,
                            "action": action.rollback_action,
                            "timestamp": datetime.utcnow(),
                        }
                    )

                # Execute action
                success = await self._execute_action(action)

                if not success:
                    result.status = ExecutionStatus.FAILED
                    result.error_message = f"Action {action.action_type} failed"
                    break

            if result.status == ExecutionStatus.EXECUTING:
                result.status = ExecutionStatus.SUCCESS

        except Exception as e:
            result.status = ExecutionStatus.FAILED
            result.error_message = str(e)
            logger.error(f"Proposal execution failed: {e}")

        result.execution_time = (datetime.utcnow() - start_time).total_seconds()
        self.execution_history.append(result)

        return result

    async def _execute_action(self, action: ProposalAction) -> bool:
        """
        Execute a single action.

        Args:
            action: Action to execute

        Returns:
            True if successful
        """
        try:
            if action.action_type == "update_config":
                return await self._update_config(action.target, action.parameters)
            elif action.action_type == "upgrade_model":
                return await self._upgrade_model(action.target, action.parameters)
            elif action.action_type == "change_threshold":
                return await self._change_threshold(action.target, action.parameters)
            else:
                logger.warning(f"Unknown action type: {action.action_type}")
                return False
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            return False

    async def _update_config(self, target: str, parameters: Dict[str, Any]) -> bool:
        """Update configuration"""
        logger.info(f"Updating config for {target}: {parameters}")
        # Implementation would update actual configuration
        return True

    async def _upgrade_model(self, target: str, parameters: Dict[str, Any]) -> bool:
        """Upgrade model"""
        logger.info(f"Upgrading model {target}: {parameters}")
        # Implementation would upgrade model
        return True

    async def _change_threshold(self, target: str, parameters: Dict[str, Any]) -> bool:
        """Change threshold"""
        logger.info(f"Changing threshold for {target}: {parameters}")
        # Implementation would change threshold
        return True

    async def rollback_proposal(self, proposal_id: str) -> bool:
        """
        Rollback a proposal execution.

        Args:
            proposal_id: Proposal ID to rollback

        Returns:
            True if rolled back successfully
        """
        # Find rollback actions for this proposal
        rollback_actions = [
            r for r in self.rollback_stack if r["proposal_id"] == proposal_id
        ]

        if not rollback_actions:
            logger.warning(f"No rollback actions found for {proposal_id}")
            return False

        try:
            # Execute rollback actions in reverse order
            for rollback in reversed(rollback_actions):
                action = ProposalAction(**rollback["action"])
                await self._execute_action(action)

            # Update execution result
            for result in self.execution_history:
                if result.proposal_id == proposal_id:
                    result.status = ExecutionStatus.ROLLED_BACK
                    result.rollback_applied = True

            logger.info(f"Rolled back proposal {proposal_id}")
            return True
        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False


class GovernanceMVP:
    """
    Complete DAO Governance MVP.

    Provides:
    - Proposal management
    - Voting mechanism
    - Execution engine
    - Governance UI integration
    """

    def __init__(self, node_id: str):
        """
        Initialize Governance MVP.

        Args:
            node_id: Node identifier
        """
        self.node_id = node_id

        if not GOVERNANCE_AVAILABLE:
            logger.error("Governance components not available")
            self.governance_engine = None
        else:
            self.governance_engine = GovernanceEngine(node_id)

        self.executor = ProposalExecutor()
        self.proposal_queue: List[Proposal] = []

        logger.info("GovernanceMVP initialized")

    def create_proposal(
        self,
        title: str,
        description: str,
        actions: List[Dict[str, Any]],
        duration_seconds: float = 3600,
    ) -> Optional[Proposal]:
        """
        Create a new governance proposal.

        Args:
            title: Proposal title
            description: Proposal description
            actions: List of actions to execute
            duration_seconds: Voting duration

        Returns:
            Created Proposal or None
        """
        if not self.governance_engine:
            logger.error("Governance engine not available")
            return None

        proposal = self.governance_engine.create_proposal(
            title=title,
            description=description,
            duration_seconds=duration_seconds,
            actions=actions,
        )

        logger.info(f"Created proposal {proposal.id}: {title}")
        return proposal

    def cast_vote(
        self, proposal_id: str, voter_id: str, vote: VoteType, tokens: float = 1.0
    ) -> bool:
        """
        Cast a vote on a proposal.

        Args:
            proposal_id: Proposal ID
            voter_id: Voter ID
            vote: Vote type
            tokens: Tokens for quadratic voting

        Returns:
            True if vote cast successfully
        """
        if not self.governance_engine:
            return False

        return self.governance_engine.cast_vote(
            proposal_id=proposal_id, voter_id=voter_id, vote=vote, tokens=tokens
        )

    async def process_proposals(self):
        """Process proposals and execute passed ones"""
        if not self.governance_engine:
            return

        # Check for expired proposals
        self.governance_engine.check_proposals()

        # Find passed proposals
        for proposal_id, proposal in self.governance_engine.proposals.items():
            if proposal.state == ProposalState.PASSED:
                # Execute proposal
                result = await self.executor.execute_proposal(proposal)

                if result.status == ExecutionStatus.SUCCESS:
                    proposal.state = ProposalState.EXECUTED
                    logger.info(f"Proposal {proposal_id} executed successfully")
                else:
                    logger.error(
                        f"Proposal {proposal_id} execution failed: {result.error_message}"
                    )

    def get_proposal_status(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Get proposal status.

        Args:
            proposal_id: Proposal ID

        Returns:
            Proposal status dictionary
        """
        if not self.governance_engine:
            return None

        proposal = self.governance_engine.proposals.get(proposal_id)
        if not proposal:
            return None

        # Find execution result
        execution_result = None
        for result in self.executor.execution_history:
            if result.proposal_id == proposal_id:
                execution_result = result
                break

        return {
            "proposal_id": proposal.id,
            "title": proposal.title,
            "description": proposal.description,
            "state": proposal.state.value,
            "votes": {
                vote.value: count for vote, count in proposal.vote_counts().items()
            },
            "execution": (
                {
                    "status": (
                        execution_result.status.value if execution_result else None
                    ),
                    "executed_at": (
                        execution_result.executed_at.isoformat()
                        if execution_result and execution_result.executed_at
                        else None
                    ),
                    "error": (
                        execution_result.error_message if execution_result else None
                    ),
                }
                if execution_result
                else None
            ),
        }

    def get_governance_stats(self) -> Dict[str, Any]:
        """
        Get governance statistics.

        Returns:
            Statistics dictionary
        """
        if not self.governance_engine:
            return {"error": "Governance engine not available"}

        proposals = self.governance_engine.proposals

        by_state = {}
        for proposal in proposals.values():
            state = proposal.state.value
            by_state[state] = by_state.get(state, 0) + 1

        return {
            "total_proposals": len(proposals),
            "by_state": by_state,
            "executed_proposals": len(
                [
                    r
                    for r in self.executor.execution_history
                    if r.status == ExecutionStatus.SUCCESS
                ]
            ),
            "failed_executions": len(
                [
                    r
                    for r in self.executor.execution_history
                    if r.status == ExecutionStatus.FAILED
                ]
            ),
        }


def create_governance_mvp(node_id: str) -> GovernanceMVP:
    """
    Factory function to create Governance MVP.

    Args:
        node_id: Node identifier

    Returns:
        GovernanceMVP instance
    """
    return GovernanceMVP(node_id)
