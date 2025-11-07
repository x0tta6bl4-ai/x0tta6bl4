from pathlib import Path
from src.security.spiffe.agent.manager import SPIREAgentManager, WorkloadEntry, AttestationStrategy


def test_spire_agent_start_stop(tmp_path):
    mgr = SPIREAgentManager(config_path=tmp_path / 'agent.conf', socket_path=tmp_path / 'agent.sock')
    assert mgr.start() is True
    # stop returns False because process placeholder not set
    assert mgr.stop() is False


def test_spire_agent_attest_join_token(tmp_path):
    mgr = SPIREAgentManager(config_path=tmp_path / 'agent.conf', socket_path=tmp_path / 'agent.sock')
    assert mgr.attest_node(AttestationStrategy.JOIN_TOKEN, token='abc123') is True


def test_spire_agent_register_and_list(tmp_path):
    mgr = SPIREAgentManager(config_path=tmp_path / 'agent.conf', socket_path=tmp_path / 'agent.sock')
    entry = WorkloadEntry(spiffe_id='spiffe://x0tta6bl4.mesh/workload/api', parent_id='spiffe://x0tta6bl4.mesh/node/n1', selectors={'unix:uid':'1000'})
    assert mgr.register_workload(entry) is True
    assert mgr.list_workloads() == []


def test_spire_agent_health(tmp_path):
    mgr = SPIREAgentManager(config_path=tmp_path / 'agent.conf', socket_path=tmp_path / 'agent.sock')
    # no socket yet
    assert mgr.health_check() is False
    # create fake socket path
    mgr.socket_path.write_text('')
    assert mgr.health_check() is True
