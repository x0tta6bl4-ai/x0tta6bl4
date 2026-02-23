"""Unit tests for src.network.routing.mesh.routing_table."""

from __future__ import annotations

import time

import pytest

models_mod = pytest.importorskip("src.network.routing.mesh.models")
routing_table_mod = pytest.importorskip("src.network.routing.mesh.routing_table")
RouteEntry = models_mod.RouteEntry
RoutingTable = routing_table_mod.RoutingTable

def test_add_neighbor_creates_and_updates_single_direct_route():
    table = RoutingTable("self", route_timeout=60.0)

    table.add_neighbor("node-a")
    routes = table.get_route("node-a")
    assert len(routes) == 1
    assert routes[0].path == ["self", "node-a"]

    old_timestamp = routes[0].timestamp
    table.add_neighbor("node-a")
    updated_routes = table.get_route("node-a")
    assert len(updated_routes) == 1
    assert updated_routes[0].timestamp >= old_timestamp


def test_get_route_filters_invalid_or_stale_and_sorts():
    now = time.time()
    table = RoutingTable("self", route_timeout=30.0)
    table._routes["dest"] = [
        RouteEntry("dest", "hop-1", 3, 3, timestamp=now, valid=True),
        RouteEntry("dest", "hop-2", 2, 5, timestamp=now, valid=True),
        RouteEntry("dest", "hop-3", 2, 7, timestamp=now, valid=True),
        RouteEntry("dest", "stale", 1, 9, timestamp=now - 1000, valid=True),
        RouteEntry("dest", "invalid", 1, 10, timestamp=now, valid=False),
    ]

    routes = table.get_route("dest")
    assert [r.next_hop for r in routes] == ["hop-3", "hop-2", "hop-1"]


def test_update_route_applies_seq_and_hop_update_rules():
    table = RoutingTable("self")
    table.update_route("dest", "hop-a", hop_count=4, seq_num=5)

    # Same seq_num + better hop_count should replace.
    table.update_route("dest", "hop-a", hop_count=2, seq_num=5)
    assert table.get_route("dest")[0].hop_count == 2

    # Better seq_num should replace even with higher hop_count.
    table.update_route("dest", "hop-a", hop_count=6, seq_num=6)
    assert table.get_route("dest")[0].hop_count == 6
    assert table.get_route("dest")[0].seq_num == 6

    # Different next_hop should be appended as distinct route.
    table.update_route("dest", "hop-b", hop_count=3, seq_num=6)
    assert {r.next_hop for r in table.get_route("dest")} == {"hop-a", "hop-b"}


def test_remove_neighbor_prunes_dependent_routes():
    table = RoutingTable("self")
    table.add_neighbor("n1")
    table.update_route("dest-1", "n1", hop_count=2, seq_num=1)
    table.update_route("dest-2", "n2", hop_count=2, seq_num=1)

    affected = table.remove_neighbor("n1")
    assert "dest-1" in affected
    assert table.get_route("n1") == []
    assert table.get_route("dest-1") == []
    assert table.get_route("dest-2")


def test_invalidate_route_and_direct_neighbors():
    now = time.time()
    table = RoutingTable("self", route_timeout=20.0)
    table._routes = {
        "n1": [RouteEntry("n1", "n1", 1, 1, timestamp=now, valid=True)],
        "n2": [RouteEntry("n2", "n2", 1, 1, timestamp=now - 500, valid=True)],
        "n3": [RouteEntry("n3", "n3", 1, 1, timestamp=now, valid=False)],
        "dest": [
            RouteEntry("dest", "n1", 2, 1, timestamp=now, valid=True),
            RouteEntry("dest", "n2", 2, 1, timestamp=now, valid=True),
        ],
    }

    assert table.invalidate_route("dest", "n2") is True
    assert [r.next_hop for r in table.get_route("dest")] == ["n1"]
    assert table.invalidate_route("missing", "n1") is False

    assert table.get_direct_neighbors() == ["n1"]
    assert sorted(table.get_all_destinations()) == ["dest", "n1", "n2", "n3"]
