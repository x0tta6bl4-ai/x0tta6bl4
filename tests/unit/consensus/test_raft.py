"""
Unit tests for Raft consensus scaffold
"""
import pytest
from src.consensus.raft import RaftNode

def test_raft_leader_transition():
    node = RaftNode("n1")
    node.become_leader()
    assert node.state == "leader"

def test_raft_follower_transition():
    node = RaftNode("n2")
    node.become_follower()
    assert node.state == "follower"

def test_raft_append_entry():
    node = RaftNode("n3")
    entry = {"term": 1, "command": "set x=1"}
    node.append_entry(entry)
    assert node.log[-1] == entry
