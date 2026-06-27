import time
from unittest.mock import MagicMock

import pytest

from src.dao.agent_voter import AgentVoter
from src.dao.fl_governance import Proposal, VoteType
from src.llm.local_llm import LLAMA_AVAILABLE, LocalLLM


@pytest.mark.skipif(not LLAMA_AVAILABLE, reason="llama-cpp-python not installed")
def test_agent_voter_decision():
    """Test that agent uses LLM to vote."""

    # Mock LLM to avoid loading real model during quick tests
    # or use real one if available
    llm = MagicMock(spec=LocalLLM)
    llm.is_ready.return_value = True
    llm.generate.return_value = (
        "FOR. The model shows improved accuracy and latency metrics."
    )

    agent = AgentVoter("GuardianAlgorithm", llm)

    proposal = Proposal(
        id=1,
        proposer="DevTeam",
        title="Upgrade to v2.0",
        description="Improves accuracy by 5% and reduces size by 10%.",
        ipfs_hash="QmHash",
        model_version=2,
        start_time=time.time(),
        end_time=time.time() + 3600,
    )

    vote = agent.decide_vote(proposal)

    assert vote == VoteType.FOR
    llm.generate.assert_called_once()


@pytest.mark.skipif(not LLAMA_AVAILABLE, reason="llama-cpp-python not installed")
def test_agent_voter_against():
    """Test negative vote."""
    llm = MagicMock(spec=LocalLLM)
    llm.is_ready.return_value = True
    llm.generate.return_value = "AGAINST. The description is vague and lacks metrics."

    agent = AgentVoter("SkepticNode", llm)

    proposal = Proposal(
        id=2,
        title="Suspicious Update",
        description="Trust me bro.",
        proposer="Anon",
        ipfs_hash="QmBad",
        model_version=3,
        start_time=time.time(),
        end_time=time.time() + 3600,
    )

    vote = agent.decide_vote(proposal)
    assert vote == VoteType.AGAINST
