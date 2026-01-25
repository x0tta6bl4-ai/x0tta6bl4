from src.consensus.raft_consensus import RaftCluster, RaftConfig, RaftNode
from datetime import datetime, timedelta


def _force_timeout(node: RaftNode):
    """Force node's last_activity far enough in past to trigger election immediately."""
    node.last_activity = datetime.now() - timedelta(milliseconds=node.election_timeout + 10)


def _drive_until_leader(cluster: RaftCluster, max_rounds: int = 5):
    # Force all nodes into timeout state repeatedly to accelerate election
    for _ in range(max_rounds):
        for node in cluster.nodes.values():
            _force_timeout(node)
        cluster.simulate_tick()
        leader = cluster.get_leader()
        if leader:
            return leader
    return None


def test_leader_election_occurs():
    cluster = RaftCluster(['n1','n2','n3'], config=RaftConfig(election_timeout_min=50, election_timeout_max=60, heartbeat_interval=100))
    leader = _drive_until_leader(cluster)
    assert leader in ['n1','n2','n3']


def test_follower_timeout_triggers_election():
    cluster = RaftCluster(['a','b'], config=RaftConfig(election_timeout_min=50, election_timeout_max=60, heartbeat_interval=100))
    leader = _drive_until_leader(cluster)
    assert leader in ['a','b']


def test_append_entry_requires_leader():
    cluster = RaftCluster(['x','y','z'], config=RaftConfig(election_timeout_min=50, election_timeout_max=60, heartbeat_interval=100))
    # initially no leader
    assert cluster.add_command({'op':'set','k':'v'}) is False
    leader = _drive_until_leader(cluster)
    assert leader in ['x','y','z']
    assert cluster.add_command({'op':'set','k':'v'}) is True
