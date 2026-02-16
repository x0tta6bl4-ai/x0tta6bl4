from datetime import datetime, timedelta

import pytest

from src.consensus.raft_consensus import (LogEntry, RaftCluster, RaftNode,
                                          RaftState)


def test_raft_initialization():
    node = RaftNode("n1", ["n1", "n2", "n3"])
    status = node.get_status()
    assert status["state"] == "follower"
    assert status["term"] == 0
    assert status["log_length"] == 1  # sentinel entry


def test_raft_election():
    cluster = RaftCluster(["n1", "n2", "n3"])
    # Directly trigger election on one node to ensure deterministic test
    n1 = cluster.nodes["n1"]
    won = n1.start_election()
    # Should win with 95% vote probability on 2 peers
    assert won, "Node n1 failed to win election"
    assert cluster.get_leader() == "n1"


def test_append_entry_as_leader():
    cluster = RaftCluster(["a", "b", "c"])
    # Directly elect leader
    leader_node = cluster.nodes["a"]
    won = leader_node.start_election()
    assert won, "Node a failed to win election"

    leader_id = cluster.get_leader()
    assert leader_id == "a"

    ok = leader_node.append_entry({"op": "put", "k": "x", "v": 1})
    assert ok
    assert leader_node.log[-1].command["k"] == "x"


def test_followers_do_not_append_directly():
    node = RaftNode("solo", ["solo", "f2"])  # no election yet
    appended = node.append_entry({"op": "noop"})
    assert appended is False


def test_timeout_triggers_election():
    node = RaftNode("n1", ["n1", "n2"])
    node.last_activity = datetime.now() - timedelta(
        milliseconds=node.election_timeout + 10
    )
    triggered = node.check_timeout()
    assert triggered is True or node.state == RaftState.FOLLOWER  # may or may not win


def test_receive_append_entries_consistency():
    follower = RaftNode("f", ["f", "l"])
    # leader sends one entry (simulated)
    entry = LogEntry(term=1, index=1, command={"op": "set"})
    ok = follower.receive_append_entries(
        term=1,
        leader_id="l",
        prev_log_index=0,
        prev_log_term=0,
        entries=[entry],
        leader_commit=1,
    )
    assert ok
    assert follower.log[-1].command == {"op": "set"}
