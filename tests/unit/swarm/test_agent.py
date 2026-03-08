"""
Unit tests for SwarmAgent.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock

from src.swarm.agent import Agent, SpecializedAgent, AgentCapability, AgentCapabilities, CapabilityScope


def test_agent_init():
    """Test Agent initialization."""
    agent = Agent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        capabilities=[AgentCapability(name="monitoring")]
    )
    
    assert agent.agent_id == "test-agent"
    assert agent.swarm_id == "test-swarm"
    assert agent.role == "test-swarm"
    assert "monitoring" in agent.capabilities
    assert agent.state.value == "initializing"


@pytest.mark.asyncio
async def test_agent_initialize():
    """Test Agent initialization."""
    agent = Agent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        capabilities=[]
    )
    
    await agent.initialize()
    
    assert agent.state.value == "idle"
    assert agent._running is True
    assert agent._message_handler_task is not None
    
    await agent.terminate()


@pytest.mark.asyncio
async def test_agent_execute_task():
    """Test task execution."""
    agent = Agent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        capabilities=[AgentCapability(name="monitoring")]
    )
    
    await agent.initialize()
    
    task = {"task_id": "test-123", "task_type": "monitoring", "payload": {"node_id": "node1"}}
    result = await agent.execute_task(task)
    
    assert result.success is True
    assert result.task_id == "test-123"
    assert result.agent_id == "test-agent"
    assert "node_id" in result.result
    assert result.result["status"] == "healthy"
    
    await agent.terminate()


@pytest.mark.asyncio
async def test_agent_execute_task_no_capability():
    """Test task execution without capability."""
    agent = Agent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        capabilities=[]
    )
    
    await agent.initialize()
    
    task = {"task_id": "test-123", "task_type": "monitoring", "payload": {}}
    
    with pytest.raises(PermissionError, match="lacks capability"):
        await agent.execute_task(task)
    
    await agent.terminate()


def test_agent_has_capability():
    """Test capability checking."""
    agent = Agent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        capabilities=[AgentCapability(name="monitoring")]
    )
    
    assert agent.has_capability("monitoring") is True
    assert agent.has_capability("optimization") is False


def test_agent_get_status():
    """Test status reporting."""
    agent = Agent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        capabilities=[AgentCapability(name="monitoring")]
    )
    
    status = agent.get_status()
    
    assert status["agent_id"] == "test-agent"
    assert status["swarm_id"] == "test-swarm"
    assert status["state"] == "initializing"
    assert "monitoring" in status["capabilities"]
    assert "metrics" in status


@pytest.mark.asyncio
async def test_specialized_agent():
    """Test SpecializedAgent creation."""
    agent = SpecializedAgent(
        agent_id="test-agent",
        swarm_id="test-swarm",
        specialization="monitoring"
    )
    
    assert agent.specialization == "monitoring"
    assert agent.has_capability("monitoring") is True
    assert agent.has_capability("metrics_collection") is True


def test_agent_capabilities_normalization():
    """Test capabilities normalization."""
    # Test with None
    caps = Agent._normalize_capabilities(None)
    assert len(caps) == 1
    assert caps[0].name == "task_execution"
    
    # Test with AgentCapabilities
    old_caps = AgentCapabilities(can_read_metrics=True, can_write_config=True)
    caps = Agent._normalize_capabilities(old_caps)
    assert len(caps) > 1
    assert any(c.name == "monitoring" for c in caps)
    assert any(c.name == "optimization" for c in caps)
