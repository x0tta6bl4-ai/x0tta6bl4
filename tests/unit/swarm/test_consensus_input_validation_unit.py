"""
Unit tests for Swarm Consensus input validation (TD-003 fix).
==============================================================

Tests input validation in SwarmConsensusManager.decide() method.
"""

import pytest

from src.swarm.consensus_integration import (
    AgentInfo,
    ConsensusMode,
    SwarmConsensusManager,
)


@pytest.fixture
def manager():
    """Create a SwarmConsensusManager instance."""
    return SwarmConsensusManager(
        node_id="test-node",
        agents={
            "agent-1": AgentInfo(agent_id="agent-1", name="Agent 1"),
            "agent-2": AgentInfo(agent_id="agent-2", name="Agent 2"),
        },
    )


@pytest.mark.asyncio
class TestDecisionInputValidation:
    """Tests for input validation in decide() method."""

    async def test_empty_topic_rejected(self, manager):
        """Empty topic should raise ValueError."""
        with pytest.raises(ValueError, match="Topic cannot be empty"):
            await manager.decide(topic="", proposals=["a", "b"])

    async def test_none_topic_rejected(self, manager):
        """None topic should raise ValueError."""
        with pytest.raises(
            ValueError,
            match="Topic must be a string|Topic cannot be empty",
        ):
            await manager.decide(topic=None, proposals=["a", "b"])

    async def test_non_string_topic_rejected(self, manager):
        """Non-string topic should raise ValueError."""
        with pytest.raises(ValueError, match="Topic must be a string"):
            await manager.decide(topic=123, proposals=["a", "b"])

    async def test_oversized_topic_rejected(self, manager):
        """Topic exceeding max length should raise ValueError."""
        long_topic = "x" * 1001
        with pytest.raises(ValueError, match="Topic exceeds maximum length"):
            await manager.decide(topic=long_topic, proposals=["a", "b"])

    async def test_empty_proposals_rejected(self, manager):
        """Empty proposals list should raise ValueError."""
        with pytest.raises(ValueError, match="Proposals list cannot be empty"):
            await manager.decide(topic="test", proposals=[])

    async def test_none_proposals_rejected(self, manager):
        """None proposals should raise ValueError."""
        with pytest.raises(
            ValueError,
            match="Proposals must be a list|Proposals list cannot be empty",
        ):
            await manager.decide(topic="test", proposals=None)

    async def test_non_list_proposals_rejected(self, manager):
        """Non-list proposals should raise ValueError."""
        with pytest.raises(ValueError, match="Proposals must be a list"):
            await manager.decide(topic="test", proposals="not-a-list")

    async def test_oversized_proposals_rejected(self, manager):
        """Proposals list exceeding max size should raise ValueError."""
        large_proposals = [f"prop-{i}" for i in range(101)]
        with pytest.raises(ValueError, match="Proposals list cannot exceed 100"):
            await manager.decide(topic="test", proposals=large_proposals)

    async def test_zero_timeout_rejected(self, manager):
        """Zero timeout should raise ValueError."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            await manager.decide(topic="test", proposals=["a"], timeout=0)

    async def test_negative_timeout_rejected(self, manager):
        """Negative timeout should raise ValueError."""
        with pytest.raises(ValueError, match="Timeout must be positive"):
            await manager.decide(topic="test", proposals=["a"], timeout=-1.0)

    async def test_excessive_timeout_rejected(self, manager):
        """Timeout exceeding max should raise ValueError."""
        with pytest.raises(ValueError, match="Timeout cannot exceed 300"):
            await manager.decide(topic="test", proposals=["a"], timeout=301.0)

    async def test_valid_input_accepted(self, manager):
        """Valid input should be accepted."""
        # Start the manager first
        await manager.start()
        
        try:
            decision = await manager.decide(
                topic="test-topic",
                proposals=["option-a", "option-b"],
                timeout=10.0,
            )
            assert decision is not None
            assert decision.topic == "test-topic"
        finally:
            await manager.stop()

    async def test_valid_input_with_all_modes(self, manager):
        """Valid input should work with all consensus modes."""
        await manager.start()
        
        try:
            for mode in ConsensusMode:
                decision = await manager.decide(
                    topic=f"test-{mode.value}",
                    proposals=["a", "b"],
                    mode=mode,
                    timeout=5.0,
                )
                assert decision is not None
                assert decision.mode == mode
        finally:
            await manager.stop()


class TestAgentInfoValidation:
    """Tests for AgentInfo validation."""

    def test_valid_agent_info(self):
        """Valid AgentInfo should be created."""
        agent = AgentInfo(
            agent_id="agent-1",
            name="Test Agent",
            capabilities={"skill-1", "skill-2"},
            weight=1.5,
        )
        assert agent.agent_id == "agent-1"
        assert agent.name == "Test Agent"
        assert "skill-1" in agent.capabilities
        assert agent.weight == 1.5

    def test_default_values(self):
        """Default values should be set correctly."""
        agent = AgentInfo(agent_id="agent-2", name="Agent 2")
        assert agent.capabilities == set()
        assert agent.weight == 1.0
        assert agent.is_byzantine is False

    def test_to_dict(self):
        """to_dict should return correct structure."""
        agent = AgentInfo(
            agent_id="agent-3",
            name="Agent 3",
            capabilities={"cap-1"},
        )
        d = agent.to_dict()
        assert d["agent_id"] == "agent-3"
        assert d["name"] == "Agent 3"
        assert "cap-1" in d["capabilities"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
