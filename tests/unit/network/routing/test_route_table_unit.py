"""
Unit tests for src/network/routing/route_table.py

Tests cover:
- RouteEntry: age property, __hash__, __eq__
- RouteTable.__init__
- add_route: new route, update with better seq_num, update with better
  hop_count (same seq), new alternate route via different next_hop,
  reject update with same/older seq_num and worse hop_count
- remove_route: remove all routes to destination, remove specific next_hop only
- invalidate_route: mark invalid without removing, specific next_hop variant
- invalidate_route_by_hop: invalidate all routes through a hop
- get_routes: valid_only filtering, sorting by hop_count then metric
- get_best_route: returns best or None
- get_all_routes: only returns destinations with valid routes
- get_next_hops: unique next hops in order
- has_route: True/False based on valid routes
- cleanup_expired: removes expired and invalid, returns count
- get_stats: destinations, total_routes, average_hop_count
- find_disjoint_paths: node-disjoint path selection up to k paths
"""

import os
import time

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.network.routing.route_table import RouteEntry, RouteTable


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_entry(
    destination="dest",
    next_hop="hop1",
    hop_count=1,
    seq_num=1,
    path=None,
    valid=True,
    metric=1.0,
    timestamp=None,
):
    kwargs = dict(
        destination=destination,
        next_hop=next_hop,
        hop_count=hop_count,
        seq_num=seq_num,
        valid=valid,
        metric=metric,
    )
    if path is not None:
        kwargs["path"] = path
    if timestamp is not None:
        kwargs["timestamp"] = timestamp
    return RouteEntry(**kwargs)


# ---------------------------------------------------------------------------
# RouteEntry
# ---------------------------------------------------------------------------

class TestRouteEntry:
    def test_defaults(self):
        entry = make_entry()
        assert entry.valid is True
        assert entry.metric == 1.0
        assert entry.path == []
        assert isinstance(entry.timestamp, float)

    def test_age_is_positive(self):
        entry = make_entry()
        assert entry.age >= 0.0

    def test_age_with_past_timestamp(self):
        past = time.time() - 10.0
        entry = make_entry(timestamp=past)
        assert entry.age >= 10.0
        assert entry.age < 13.0  # generous window

    def test_age_near_zero_for_new_entry(self):
        entry = make_entry()
        assert entry.age < 1.0

    def test_hash_consistency(self):
        entry = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        h1 = hash(entry)
        h2 = hash(entry)
        assert h1 == h2

    def test_hash_same_fields_equal(self):
        e1 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        e2 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        assert hash(e1) == hash(e2)

    def test_hash_different_path_differs(self):
        e1 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        e2 = make_entry(destination="D", next_hop="H", path=["A", "X", "D"])
        assert hash(e1) != hash(e2)

    def test_eq_same_fields(self):
        e1 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        e2 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        assert e1 == e2

    def test_eq_different_destination(self):
        e1 = make_entry(destination="D1", next_hop="H", path=[])
        e2 = make_entry(destination="D2", next_hop="H", path=[])
        assert e1 != e2

    def test_eq_different_next_hop(self):
        e1 = make_entry(destination="D", next_hop="H1", path=[])
        e2 = make_entry(destination="D", next_hop="H2", path=[])
        assert e1 != e2

    def test_eq_different_path(self):
        e1 = make_entry(destination="D", next_hop="H", path=["A"])
        e2 = make_entry(destination="D", next_hop="H", path=["B"])
        assert e1 != e2

    def test_eq_not_equal_to_non_entry(self):
        entry = make_entry()
        assert entry != "not a RouteEntry"
        assert entry != 42
        assert entry != None  # noqa: E711

    def test_usable_in_set(self):
        e1 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        e2 = make_entry(destination="D", next_hop="H", path=["A", "H", "D"])
        s = {e1, e2}
        assert len(s) == 1


# ---------------------------------------------------------------------------
# RouteTable.__init__
# ---------------------------------------------------------------------------

class TestRouteTableInit:
    def test_routes_empty_on_init(self):
        rt = RouteTable()
        assert rt._routes == {}

    def test_route_timeout_constant(self):
        assert RouteTable.ROUTE_TIMEOUT == 60.0


# ---------------------------------------------------------------------------
# add_route
# ---------------------------------------------------------------------------

class TestAddRoute:
    def test_add_new_route(self):
        rt = RouteTable()
        entry = make_entry(destination="Z", next_hop="H1", seq_num=1, hop_count=2)
        result = rt.add_route(entry)
        assert result is True
        assert "Z" in rt._routes
        assert rt._routes["Z"][0] is entry

    def test_add_same_next_hop_newer_seq_updates(self):
        rt = RouteTable()
        e1 = make_entry(destination="Z", next_hop="H1", seq_num=1, hop_count=3)
        e2 = make_entry(destination="Z", next_hop="H1", seq_num=2, hop_count=3)
        rt.add_route(e1)
        result = rt.add_route(e2)
        assert result is True
        assert rt._routes["Z"][0] is e2

    def test_add_same_next_hop_older_seq_rejected(self):
        rt = RouteTable()
        e1 = make_entry(destination="Z", next_hop="H1", seq_num=5, hop_count=3)
        e2 = make_entry(destination="Z", next_hop="H1", seq_num=3, hop_count=3)
        rt.add_route(e1)
        result = rt.add_route(e2)
        assert result is False
        assert rt._routes["Z"][0] is e1  # original kept

    def test_add_same_seq_better_hop_count_updates(self):
        rt = RouteTable()
        e1 = make_entry(destination="Z", next_hop="H1", seq_num=1, hop_count=5)
        e2 = make_entry(destination="Z", next_hop="H1", seq_num=1, hop_count=2)
        rt.add_route(e1)
        result = rt.add_route(e2)
        assert result is True
        assert rt._routes["Z"][0].hop_count == 2

    def test_add_same_seq_worse_hop_count_rejected(self):
        rt = RouteTable()
        e1 = make_entry(destination="Z", next_hop="H1", seq_num=1, hop_count=2)
        e2 = make_entry(destination="Z", next_hop="H1", seq_num=1, hop_count=5)
        rt.add_route(e1)
        result = rt.add_route(e2)
        assert result is False
        assert rt._routes["Z"][0].hop_count == 2

    def test_add_different_next_hop_creates_alternate_route(self):
        rt = RouteTable()
        e1 = make_entry(destination="Z", next_hop="H1", seq_num=1)
        e2 = make_entry(destination="Z", next_hop="H2", seq_num=1)
        rt.add_route(e1)
        result = rt.add_route(e2)
        assert result is True
        assert len(rt._routes["Z"]) == 2

    def test_add_multiple_destinations(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="A"))
        rt.add_route(make_entry(destination="B"))
        rt.add_route(make_entry(destination="C"))
        assert len(rt._routes) == 3


# ---------------------------------------------------------------------------
# remove_route
# ---------------------------------------------------------------------------

class TestRemoveRoute:
    def test_remove_nonexistent_returns_zero(self):
        rt = RouteTable()
        assert rt.remove_route("ghost") == 0

    def test_remove_all_routes_to_destination(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        rt.add_route(make_entry(destination="Z", next_hop="H2"))
        count = rt.remove_route("Z")
        assert count == 2
        assert "Z" not in rt._routes

    def test_remove_specific_next_hop(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        rt.add_route(make_entry(destination="Z", next_hop="H2"))
        count = rt.remove_route("Z", next_hop="H1")
        assert count == 1
        assert "Z" in rt._routes
        assert rt._routes["Z"][0].next_hop == "H2"

    def test_remove_specific_next_hop_last_route_cleans_up(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        rt.remove_route("Z", next_hop="H1")
        assert "Z" not in rt._routes

    def test_remove_next_hop_not_in_table_returns_zero(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        count = rt.remove_route("Z", next_hop="H-unknown")
        assert count == 0
        assert "Z" in rt._routes  # original untouched


# ---------------------------------------------------------------------------
# invalidate_route
# ---------------------------------------------------------------------------

class TestInvalidateRoute:
    def test_invalidate_all_routes_to_destination(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        rt.add_route(make_entry(destination="Z", next_hop="H2"))
        rt.invalidate_route("Z")
        for route in rt._routes["Z"]:
            assert route.valid is False

    def test_invalidate_specific_next_hop(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        rt.add_route(make_entry(destination="Z", next_hop="H2"))
        rt.invalidate_route("Z", next_hop="H1")
        routes = {r.next_hop: r for r in rt._routes["Z"]}
        assert routes["H1"].valid is False
        assert routes["H2"].valid is True

    def test_invalidate_nonexistent_destination_no_error(self):
        rt = RouteTable()
        # Should not raise
        rt.invalidate_route("ghost")

    def test_invalidated_route_hidden_by_get_routes(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1"))
        rt.invalidate_route("Z")
        assert rt.get_routes("Z") == []


# ---------------------------------------------------------------------------
# invalidate_route_by_hop
# ---------------------------------------------------------------------------

class TestInvalidateRouteByHop:
    def test_invalidates_all_routes_through_hop(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="A", next_hop="bad-hop"))
        rt.add_route(make_entry(destination="B", next_hop="bad-hop"))
        rt.add_route(make_entry(destination="C", next_hop="good-hop"))
        rt.invalidate_route_by_hop("bad-hop")

        for route in rt._routes["A"]:
            assert route.valid is False
        for route in rt._routes["B"]:
            assert route.valid is False
        for route in rt._routes["C"]:
            assert route.valid is True

    def test_invalidate_by_unknown_hop_no_effect(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="A", next_hop="H1"))
        rt.invalidate_route_by_hop("unknown-hop")
        assert rt._routes["A"][0].valid is True


# ---------------------------------------------------------------------------
# get_routes
# ---------------------------------------------------------------------------

class TestGetRoutes:
    def test_returns_empty_for_unknown_destination(self):
        rt = RouteTable()
        assert rt.get_routes("unknown") == []

    def test_valid_only_filters_invalid(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", valid=False))
        assert rt.get_routes("Z", valid_only=True) == []

    def test_valid_only_false_includes_invalid(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", valid=False))
        routes = rt.get_routes("Z", valid_only=False)
        assert len(routes) == 1

    def test_filters_expired_routes(self):
        rt = RouteTable()
        old_ts = time.time() - (RouteTable.ROUTE_TIMEOUT + 10.0)
        rt.add_route(make_entry(destination="Z", next_hop="H1", timestamp=old_ts))
        assert rt.get_routes("Z") == []

    def test_sorted_by_hop_count_ascending(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H3", hop_count=5, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=1, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=3, seq_num=1))
        routes = rt.get_routes("Z")
        assert [r.hop_count for r in routes] == [1, 3, 5]

    def test_sorted_by_metric_when_same_hop_count(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=2, metric=3.0, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=2, metric=1.0, seq_num=1))
        routes = rt.get_routes("Z")
        assert routes[0].metric == 1.0
        assert routes[1].metric == 3.0


# ---------------------------------------------------------------------------
# get_best_route
# ---------------------------------------------------------------------------

class TestGetBestRoute:
    def test_returns_none_when_no_routes(self):
        rt = RouteTable()
        assert rt.get_best_route("Z") is None

    def test_returns_best_route(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=3, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=1, seq_num=1))
        best = rt.get_best_route("Z")
        assert best is not None
        assert best.hop_count == 1

    def test_ignores_invalid_routes(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=1, valid=False))
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=5, valid=True))
        best = rt.get_best_route("Z")
        assert best is not None
        assert best.next_hop == "H2"


# ---------------------------------------------------------------------------
# get_all_routes
# ---------------------------------------------------------------------------

class TestGetAllRoutes:
    def test_returns_empty_dict_when_no_routes(self):
        rt = RouteTable()
        assert rt.get_all_routes() == {}

    def test_only_includes_destinations_with_valid_routes(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="A", next_hop="H1", valid=True))
        rt.add_route(make_entry(destination="B", next_hop="H2", valid=False))
        result = rt.get_all_routes()
        assert "A" in result
        assert "B" not in result

    def test_returns_all_valid_destinations(self):
        rt = RouteTable()
        for dest in ["X", "Y", "Z"]:
            rt.add_route(make_entry(destination=dest, next_hop=f"H-{dest}"))
        result = rt.get_all_routes()
        assert set(result.keys()) == {"X", "Y", "Z"}


# ---------------------------------------------------------------------------
# get_next_hops
# ---------------------------------------------------------------------------

class TestGetNextHops:
    def test_returns_empty_for_unknown_destination(self):
        rt = RouteTable()
        assert rt.get_next_hops("Z") == []

    def test_returns_unique_next_hops(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=1, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=2, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H3", hop_count=3, seq_num=1))
        hops = rt.get_next_hops("Z")
        assert set(hops) == {"H1", "H2", "H3"}

    def test_ordered_by_route_quality(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H3", hop_count=5, seq_num=1))
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=1, seq_num=1))
        hops = rt.get_next_hops("Z")
        assert hops[0] == "H1"
        assert hops[1] == "H3"


# ---------------------------------------------------------------------------
# has_route
# ---------------------------------------------------------------------------

class TestHasRoute:
    def test_returns_false_for_unknown_destination(self):
        rt = RouteTable()
        assert rt.has_route("Z") is False

    def test_returns_true_when_valid_route_exists(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z"))
        assert rt.has_route("Z") is True

    def test_returns_false_when_all_routes_invalid(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", valid=False))
        assert rt.has_route("Z") is False

    def test_returns_false_when_all_routes_expired(self):
        rt = RouteTable()
        old_ts = time.time() - (RouteTable.ROUTE_TIMEOUT + 5.0)
        rt.add_route(make_entry(destination="Z", timestamp=old_ts))
        assert rt.has_route("Z") is False


# ---------------------------------------------------------------------------
# cleanup_expired
# ---------------------------------------------------------------------------

class TestCleanupExpired:
    def test_no_routes_returns_zero(self):
        rt = RouteTable()
        assert rt.cleanup_expired() == 0

    def test_removes_expired_routes(self):
        rt = RouteTable()
        old_ts = time.time() - (RouteTable.ROUTE_TIMEOUT + 10.0)
        rt.add_route(make_entry(destination="Z", next_hop="H1", timestamp=old_ts))
        count = rt.cleanup_expired()
        assert count == 1
        assert "Z" not in rt._routes

    def test_removes_invalid_routes(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", valid=False))
        count = rt.cleanup_expired()
        assert count == 1
        assert "Z" not in rt._routes

    def test_keeps_valid_unexpired_routes(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", valid=True))
        count = rt.cleanup_expired()
        assert count == 0
        assert "Z" in rt._routes

    def test_partial_cleanup_mixed_routes(self):
        rt = RouteTable()
        old_ts = time.time() - (RouteTable.ROUTE_TIMEOUT + 10.0)
        rt.add_route(make_entry(destination="Z", next_hop="H1", timestamp=old_ts))
        rt.add_route(make_entry(destination="Z", next_hop="H2", valid=True))
        count = rt.cleanup_expired()
        assert count == 1
        assert "Z" in rt._routes
        assert len(rt._routes["Z"]) == 1
        assert rt._routes["Z"][0].next_hop == "H2"

    def test_cleanup_removes_empty_destination_key(self):
        rt = RouteTable()
        old_ts = time.time() - (RouteTable.ROUTE_TIMEOUT + 5.0)
        rt.add_route(make_entry(destination="Z", next_hop="H1", timestamp=old_ts))
        rt.cleanup_expired()
        assert "Z" not in rt._routes


# ---------------------------------------------------------------------------
# get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_stats_empty_table(self):
        rt = RouteTable()
        stats = rt.get_stats()
        assert stats["destinations"] == 0
        assert stats["total_routes"] == 0
        assert stats["average_hop_count"] == 0.0

    def test_stats_single_route(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", hop_count=3))
        stats = rt.get_stats()
        assert stats["destinations"] == 1
        assert stats["total_routes"] == 1
        assert stats["average_hop_count"] == 3.0

    def test_stats_multiple_routes(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="A", next_hop="H1", hop_count=2, seq_num=1))
        rt.add_route(make_entry(destination="B", next_hop="H2", hop_count=4, seq_num=1))
        stats = rt.get_stats()
        assert stats["destinations"] == 2
        assert stats["total_routes"] == 2
        assert stats["average_hop_count"] == 3.0

    def test_stats_includes_invalid_routes_in_total(self):
        # get_stats reads from _routes directly, not through get_routes
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=2, valid=False))
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=4, valid=True))
        stats = rt.get_stats()
        assert stats["total_routes"] == 2


# ---------------------------------------------------------------------------
# find_disjoint_paths
# ---------------------------------------------------------------------------

class TestFindDisjointPaths:
    def test_returns_empty_for_unknown_destination(self):
        rt = RouteTable()
        assert rt.find_disjoint_paths("Z") == []

    def test_single_path_returned(self):
        rt = RouteTable()
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=1, path=[]))
        paths = rt.find_disjoint_paths("Z", k=3)
        assert len(paths) == 1

    def test_disjoint_paths_selected(self):
        rt = RouteTable()
        # path1: A -> H1 -> Z (uses H1 as intermediate)
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=2, seq_num=1, path=["H1"]))
        # path2: A -> H2 -> Z (uses H2 as intermediate, disjoint from path1)
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=2, seq_num=1, path=["H2"]))
        paths = rt.find_disjoint_paths("Z", k=2)
        assert len(paths) == 2
        # Ensure they use different intermediates
        assert paths[0].next_hop != paths[1].next_hop

    def test_shared_node_paths_excluded(self):
        rt = RouteTable()
        # path1: uses shared node M
        rt.add_route(make_entry(destination="Z", next_hop="H1", hop_count=2, seq_num=1, path=["M", "H1"]))
        # path2: also uses shared node M (not disjoint from path1)
        rt.add_route(make_entry(destination="Z", next_hop="H2", hop_count=2, seq_num=1, path=["M", "H2"]))
        # path3: uses unique node U (disjoint from both)
        rt.add_route(make_entry(destination="Z", next_hop="H3", hop_count=3, seq_num=1, path=["U", "H3"]))
        paths = rt.find_disjoint_paths("Z", k=3)
        # path1 and path3 should be selected (path2 shares M with path1)
        assert len(paths) == 2

    def test_k_limits_results(self):
        rt = RouteTable()
        for i in range(5):
            rt.add_route(make_entry(
                destination="Z",
                next_hop=f"H{i}",
                hop_count=2,
                seq_num=1,
                path=[f"node{i}"],  # all distinct intermediates
            ))
        paths = rt.find_disjoint_paths("Z", k=3)
        assert len(paths) <= 3

    def test_empty_paths_are_all_disjoint(self):
        rt = RouteTable()
        # Routes with empty path lists — no intermediate nodes, always disjoint
        for i in range(4):
            rt.add_route(make_entry(
                destination="Z",
                next_hop=f"H{i}",
                hop_count=1,
                seq_num=1,
                path=[],
            ))
        paths = rt.find_disjoint_paths("Z", k=4)
        assert len(paths) == 4
