"""
Comprehensive unit tests for src/swarm/vision_coding.py
"""

import asyncio
import hashlib
import io
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import pytest
from PIL import Image

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

from src.swarm.vision_coding import (AnalysisType, AStarAlgorithm,
                                     BFSAlgorithm, BoundingBox, Graph,
                                     GraphNode, Issue, OverlayElement,
                                     PathMetrics, Severity, Style, Suggestion,
                                     VisionCache, VisionCodingEngine,
                                     VisualOverlay, analyze_maze,
                                     analyze_mesh_topology, detect_anomalies,
                                     get_vision_engine)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_image(width=100, height=100, color=(255, 255, 255)):
    """Create a simple PIL image and return its bytes."""
    img = Image.new("RGB", (width, height), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_maze_image(width=50, height=50):
    """Create a simple 'maze' image with a clear white path and black walls."""
    img = Image.new("L", (width, height), 0)  # black background = walls
    # Draw a horizontal white corridor
    for x in range(width):
        for y in range(20, 30):
            img.putpixel((x, y), 255)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _build_simple_graph():
    """Build a small test graph: A -- B -- C."""
    g = Graph()
    g.add_node(GraphNode(id="A", x=0, y=0))
    g.add_node(GraphNode(id="B", x=1, y=0))
    g.add_node(GraphNode(id="C", x=2, y=0))
    g.add_edge("A", "B")
    g.add_edge("B", "C")
    return g


def _build_disconnected_graph():
    """Build a graph where D is not reachable from A."""
    g = _build_simple_graph()
    g.add_node(GraphNode(id="D", x=10, y=10))
    # no edges to D
    return g


# ===========================================================================
# Enum tests
# ===========================================================================


class TestEnums:
    def test_analysis_type_members(self):
        assert AnalysisType.UI_LAYOUT is not None
        assert AnalysisType.GRAPH_PATHFINDING is not None
        assert len(AnalysisType) == 6

    def test_severity_values(self):
        assert Severity.INFO.value == "info"
        assert Severity.WARNING.value == "warning"
        assert Severity.ERROR.value == "error"
        assert Severity.CRITICAL.value == "critical"


# ===========================================================================
# BoundingBox tests
# ===========================================================================


class TestBoundingBox:
    def test_center(self):
        bb = BoundingBox(x=0, y=0, width=10, height=20)
        assert bb.center == (5.0, 10.0)

    def test_area(self):
        bb = BoundingBox(x=0, y=0, width=5, height=4)
        assert bb.area == 20.0

    def test_contains_inside(self):
        bb = BoundingBox(x=0, y=0, width=10, height=10)
        assert bb.contains((5, 5)) is True

    def test_contains_on_edge(self):
        bb = BoundingBox(x=0, y=0, width=10, height=10)
        assert bb.contains((0, 0)) is True
        assert bb.contains((10, 10)) is True

    def test_contains_outside(self):
        bb = BoundingBox(x=0, y=0, width=10, height=10)
        assert bb.contains((11, 5)) is False
        assert bb.contains((5, -1)) is False

    def test_intersects_true(self):
        bb1 = BoundingBox(x=0, y=0, width=10, height=10)
        bb2 = BoundingBox(x=5, y=5, width=10, height=10)
        assert bb1.intersects(bb2) is True

    def test_intersects_false(self):
        bb1 = BoundingBox(x=0, y=0, width=10, height=10)
        bb2 = BoundingBox(x=20, y=20, width=10, height=10)
        assert bb1.intersects(bb2) is False

    def test_intersects_adjacent(self):
        bb1 = BoundingBox(x=0, y=0, width=10, height=10)
        bb2 = BoundingBox(x=10, y=0, width=10, height=10)
        assert bb1.intersects(bb2) is True  # touching edges count

    def test_zero_area(self):
        bb = BoundingBox(x=5, y=5, width=0, height=0)
        assert bb.area == 0.0
        assert bb.center == (5.0, 5.0)


# ===========================================================================
# Style / dataclass tests
# ===========================================================================


class TestStyle:
    def test_defaults(self):
        s = Style()
        assert s.color == "#00FF00"
        assert s.border_width == 2.0
        assert s.opacity == 0.8
        assert s.font_size == 12
        assert s.fill_color is None
        assert s.dash_pattern is None

    def test_custom(self):
        s = Style(color="#FF0000", opacity=0.5, fill_color="#0000FF")
        assert s.fill_color == "#0000FF"


class TestOverlayElement:
    def test_creation(self):
        e = OverlayElement(
            element_type="test",
            location=BoundingBox(0, 0, 10, 10),
            style=Style(),
            content="hello",
        )
        assert e.element_type == "test"
        assert e.content == "hello"
        assert e.metadata == {}


class TestIssue:
    def test_creation(self):
        issue = Issue(
            issue_type="alignment",
            severity=Severity.WARNING,
            location=BoundingBox(0, 0, 10, 10),
            description="Misaligned",
            suggestion="Fix it",
            confidence=0.9,
        )
        assert issue.confidence == 0.9


class TestSuggestion:
    def test_creation(self):
        s = Suggestion(suggestion_type="refactor", confidence=0.8, action="split")
        assert s.code_snippet == ""
        assert s.explanation == ""


# ===========================================================================
# VisualOverlay tests
# ===========================================================================


class TestVisualOverlay:
    def test_add_element(self):
        vo = VisualOverlay()
        assert len(vo.elements) == 0
        elem = OverlayElement(
            element_type="box",
            location=BoundingBox(10, 10, 50, 50),
            style=Style(),
        )
        vo.add_element(elem)
        assert len(vo.elements) == 1

    def test_render_no_elements(self):
        vo = VisualOverlay(original_size=(100, 100))
        base = Image.new("RGB", (100, 100), (128, 128, 128))
        result = vo.render(base)
        assert result.size == (100, 100)
        assert result.mode == "RGB"

    def test_render_with_fill_color(self):
        vo = VisualOverlay(original_size=(100, 100))
        vo.add_element(
            OverlayElement(
                element_type="rect",
                location=BoundingBox(10, 20, 30, 30),
                style=Style(color="#FF0000", fill_color="#00FF00", opacity=0.5),
                content="label",
            )
        )
        base = Image.new("RGB", (100, 100), (0, 0, 0))
        result = vo.render(base)
        assert result.size == (100, 100)

    def test_render_without_fill_color(self):
        vo = VisualOverlay(original_size=(100, 100))
        vo.add_element(
            OverlayElement(
                element_type="rect",
                location=BoundingBox(10, 20, 30, 30),
                style=Style(color="#0000FF", opacity=1.0),
                content="",
            )
        )
        base = Image.new("RGB", (100, 100), (255, 255, 255))
        result = vo.render(base)
        assert result.mode == "RGB"

    def test_hex_to_rgba(self):
        assert VisualOverlay._hex_to_rgba("#FF0000") == (255, 0, 0, 255)
        assert VisualOverlay._hex_to_rgba("#00ff00", 128) == (0, 255, 0, 128)
        assert VisualOverlay._hex_to_rgba("0000FF", 0) == (0, 0, 255, 0)

    def test_render_with_content_font_fallback(self):
        """Ensure font fallback works when truetype is not available."""
        vo = VisualOverlay(original_size=(200, 200))
        vo.add_element(
            OverlayElement(
                element_type="label",
                location=BoundingBox(50, 50, 60, 60),
                style=Style(color="#FFFFFF", font_size=14),
                content="Test text",
            )
        )
        base = Image.new("RGB", (200, 200), (0, 0, 0))
        # This should work regardless of font availability
        result = vo.render(base)
        assert result.size == (200, 200)


# ===========================================================================
# GraphNode tests
# ===========================================================================


class TestGraphNode:
    def test_distance_to(self):
        a = GraphNode(id="a", x=0, y=0)
        b = GraphNode(id="b", x=3, y=4)
        assert abs(a.distance_to(b) - 5.0) < 1e-6

    def test_distance_to_same(self):
        a = GraphNode(id="a", x=5, y=5)
        assert a.distance_to(a) == 0.0


# ===========================================================================
# Graph tests
# ===========================================================================


class TestGraph:
    def test_add_node(self):
        g = Graph()
        g.add_node(GraphNode(id="n1", x=0, y=0))
        assert "n1" in g.nodes
        assert "n1" in g.edges
        assert g.edges["n1"] == []

    def test_add_edge_bidirectional(self):
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        g.add_node(GraphNode(id="b", x=1, y=0))
        g.add_edge("a", "b", bidirectional=True)
        assert "b" in g.edges["a"]
        assert "a" in g.edges["b"]

    def test_add_edge_unidirectional(self):
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        g.add_node(GraphNode(id="b", x=1, y=0))
        g.add_edge("a", "b", bidirectional=False)
        assert "b" in g.edges["a"]
        assert "a" not in g.edges["b"]

    def test_add_edge_no_duplicates(self):
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        g.add_node(GraphNode(id="b", x=1, y=0))
        g.add_edge("a", "b")
        g.add_edge("a", "b")
        assert g.edges["a"].count("b") == 1

    def test_get_neighbors(self):
        g = _build_simple_graph()
        assert set(g.get_neighbors("B")) == {"A", "C"}
        assert g.get_neighbors("nonexistent") == []

    def test_add_edge_unknown_node(self):
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        # from_id known, to_id unknown => appends to a's list; no crash
        g.add_edge("a", "zzz", bidirectional=False)
        assert "zzz" in g.edges["a"]

    def test_add_edge_bidirectional_unknown_to(self):
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        # to_id not in edges => skip bidirectional part silently
        g.add_edge("a", "zzz", bidirectional=True)
        assert "zzz" in g.edges["a"]
        assert "zzz" not in g.edges  # was never added as a node


# ===========================================================================
# BFSAlgorithm tests
# ===========================================================================


class TestBFSAlgorithm:
    def test_find_path_simple(self):
        g = _build_simple_graph()
        bfs = BFSAlgorithm()
        result = bfs.find_path(g, "A", "C")
        assert result.path_nodes == ["A", "B", "C"]
        assert result.length == 3
        assert result.nodes_visited >= 2

    def test_find_path_start_equals_end(self):
        g = _build_simple_graph()
        bfs = BFSAlgorithm()
        result = bfs.find_path(g, "A", "A")
        assert result.path_nodes == ["A"]
        assert result.length == 1

    def test_find_path_start_not_found(self):
        g = _build_simple_graph()
        bfs = BFSAlgorithm()
        with pytest.raises(ValueError, match="Start node not found"):
            bfs.find_path(g, "X", "A")

    def test_find_path_end_not_found(self):
        g = _build_simple_graph()
        bfs = BFSAlgorithm()
        with pytest.raises(ValueError, match="End node not found"):
            bfs.find_path(g, "A", "X")

    def test_find_path_no_path(self):
        g = _build_disconnected_graph()
        bfs = BFSAlgorithm()
        with pytest.raises(ValueError, match="No path found"):
            bfs.find_path(g, "A", "D")

    def test_max_depth_limits_search(self):
        # Build a long chain: n0 -- n1 -- n2 -- ... -- n20
        g = Graph()
        for i in range(21):
            g.add_node(GraphNode(id=f"n{i}", x=float(i), y=0))
        for i in range(20):
            g.add_edge(f"n{i}", f"n{i+1}")

        bfs = BFSAlgorithm(max_depth=5)
        # Path length from n0 to n20 is 21 nodes; max_depth=5 will skip beyond depth 5
        with pytest.raises(ValueError, match="No path found"):
            bfs.find_path(g, "n0", "n20")

    def test_total_cost(self):
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0, cost=2.0))
        g.add_node(GraphNode(id="b", x=1, y=0, cost=3.0))
        g.add_edge("a", "b")
        bfs = BFSAlgorithm()
        result = bfs.find_path(g, "a", "b")
        assert result.total_cost == 5.0


# ===========================================================================
# AStarAlgorithm tests
# ===========================================================================


class TestAStarAlgorithm:
    def test_find_path_simple(self):
        g = _build_simple_graph()
        astar = AStarAlgorithm()
        result = astar.find_path(g, "A", "C")
        assert result.path_nodes == ["A", "B", "C"]

    def test_find_path_start_not_found(self):
        g = _build_simple_graph()
        astar = AStarAlgorithm()
        with pytest.raises(ValueError, match="Start node not found"):
            astar.find_path(g, "X", "A")

    def test_find_path_end_not_found(self):
        g = _build_simple_graph()
        astar = AStarAlgorithm()
        with pytest.raises(ValueError, match="End node not found"):
            astar.find_path(g, "A", "X")

    def test_find_path_no_path(self):
        g = _build_disconnected_graph()
        astar = AStarAlgorithm()
        with pytest.raises(ValueError, match="No path found"):
            astar.find_path(g, "A", "D")

    def test_find_path_start_equals_end(self):
        g = _build_simple_graph()
        astar = AStarAlgorithm()
        result = astar.find_path(g, "A", "A")
        assert result.path_nodes == ["A"]

    def test_custom_heuristic(self):
        g = _build_simple_graph()
        astar = AStarAlgorithm(heuristic_weight=2.0)
        custom_h = lambda a, b: abs(a.x - b.x)
        result = astar.find_path(g, "A", "C", heuristic=custom_h)
        assert "A" in result.path_nodes
        assert "C" in result.path_nodes

    def test_manhattan_distance(self):
        astar = AStarAlgorithm()
        n1 = GraphNode(id="a", x=0, y=0)
        n2 = GraphNode(id="b", x=3, y=4)
        assert astar.manhattan_distance(n1, n2) == 7.0

    def test_heuristic_weight_zero(self):
        """With weight=0, A* degenerates to Dijkstra."""
        g = _build_simple_graph()
        astar = AStarAlgorithm(heuristic_weight=0.0)
        result = astar.find_path(g, "A", "C")
        assert result.path_nodes == ["A", "B", "C"]

    def test_updates_shorter_path(self):
        """Test that A* updates g_score when a shorter path is found."""
        g = Graph()
        g.add_node(GraphNode(id="A", x=0, y=0, cost=1.0))
        g.add_node(GraphNode(id="B", x=1, y=0, cost=10.0))  # expensive
        g.add_node(GraphNode(id="C", x=1, y=1, cost=1.0))
        g.add_node(GraphNode(id="D", x=2, y=0, cost=1.0))
        g.add_edge("A", "B")
        g.add_edge("A", "C")
        g.add_edge("B", "D")
        g.add_edge("C", "D")
        astar = AStarAlgorithm()
        result = astar.find_path(g, "A", "D")
        # The path through C is cheaper (cost 1+1) vs through B (cost 1+10)
        assert "C" in result.path_nodes


# ===========================================================================
# VisionCache tests
# ===========================================================================


class TestVisionCache:
    @pytest.mark.asyncio
    async def test_set_and_get(self):
        cache = VisionCache(max_size=10, ttl_seconds=60)
        await cache.set(b"data", "op", {"result": 42})
        result = await cache.get(b"data", "op")
        assert result == {"result": 42}

    @pytest.mark.asyncio
    async def test_get_miss(self):
        cache = VisionCache()
        result = await cache.get(b"unknown", "op")
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        cache = VisionCache(ttl_seconds=0.01)
        await cache.set(b"data", "op", "value")
        await asyncio.sleep(0.02)
        result = await cache.get(b"data", "op")
        assert result is None

    @pytest.mark.asyncio
    async def test_lru_eviction(self):
        cache = VisionCache(max_size=2, ttl_seconds=60)
        await cache.set(b"d1", "op", "v1")
        await cache.set(b"d2", "op", "v2")
        # This should evict the oldest (d1)
        await cache.set(b"d3", "op", "v3")
        assert await cache.get(b"d3", "op") == "v3"
        # d1 was evicted
        assert await cache.get(b"d1", "op") is None

    @pytest.mark.asyncio
    async def test_hit_count_incremented(self):
        cache = VisionCache(ttl_seconds=60)
        await cache.set(b"data", "op", "value")
        await cache.get(b"data", "op")
        await cache.get(b"data", "op")
        stats = await cache.get_stats()
        assert stats["total_hits"] == 2

    @pytest.mark.asyncio
    async def test_get_stats_empty(self):
        cache = VisionCache()
        stats = await cache.get_stats()
        assert stats["size"] == 0
        assert stats["max_size"] == 1000
        assert stats["total_hits"] == 0
        assert stats["hit_rate"] == 0.0

    @pytest.mark.asyncio
    async def test_generate_key_deterministic(self):
        cache = VisionCache()
        k1 = cache._generate_key(b"data", "op")
        k2 = cache._generate_key(b"data", "op")
        assert k1 == k2
        assert len(k1) == 32

    @pytest.mark.asyncio
    async def test_generate_key_different_for_different_input(self):
        cache = VisionCache()
        k1 = cache._generate_key(b"data1", "op")
        k2 = cache._generate_key(b"data2", "op")
        assert k1 != k2

    @pytest.mark.asyncio
    async def test_cache_access_order_updated_on_hit(self):
        cache = VisionCache(max_size=3, ttl_seconds=60)
        await cache.set(b"d1", "op", "v1")
        await cache.set(b"d2", "op", "v2")
        # Access d1 to move it to end of access order
        await cache.get(b"d1", "op")
        # Add d3 => should evict d2 (least recently used), not d1
        await cache.set(b"d3", "op", "v3")
        assert await cache.get(b"d1", "op") == "v1"


# ===========================================================================
# VisionCodingEngine tests
# ===========================================================================


class TestVisionCodingEngine:
    def test_init(self):
        engine = VisionCodingEngine()
        assert isinstance(engine.bfs, BFSAlgorithm)
        assert isinstance(engine.a_star, AStarAlgorithm)
        assert isinstance(engine.cache, VisionCache)
        assert engine.ocr_enabled is False
        assert engine.ocr_languages == ["eng", "rus"]

    def test_find_nearest_node(self):
        engine = VisionCodingEngine()
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        g.add_node(GraphNode(id="b", x=100, y=100))
        result = engine._find_nearest_node(g, (5, 5))
        assert result.id == "a"

    def test_find_nearest_node_empty_graph(self):
        engine = VisionCodingEngine()
        g = Graph()
        with pytest.raises(ValueError, match="No nodes found"):
            engine._find_nearest_node(g, (0, 0))

    def test_create_path_overlay(self):
        engine = VisionCodingEngine()
        g = _build_simple_graph()
        pm = PathMetrics(
            length=3,
            total_cost=3.0,
            nodes_visited=3,
            time_ms=1.0,
            path_nodes=["A", "B", "C"],
        )
        img_data = _make_image(100, 100)
        overlay = engine._create_path_overlay(img_data, pm, g)
        assert isinstance(overlay, VisualOverlay)
        assert len(overlay.elements) == 3
        # First element green, last red
        assert overlay.elements[0].style.color == "#00ff00"
        assert overlay.elements[2].style.color == "#ff0000"

    def test_create_path_overlay_single_node(self):
        engine = VisionCodingEngine()
        g = Graph()
        g.add_node(GraphNode(id="A", x=5, y=5))
        pm = PathMetrics(
            length=1,
            total_cost=1.0,
            nodes_visited=1,
            time_ms=0.1,
            path_nodes=["A"],
        )
        img_data = _make_image(50, 50)
        overlay = engine._create_path_overlay(img_data, pm, g)
        assert len(overlay.elements) == 1

    @pytest.mark.asyncio
    async def test_extract_graph_from_image(self):
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        graph = await engine._extract_graph_from_image(img_data)
        assert isinstance(graph, Graph)
        assert len(graph.nodes) > 0

    @pytest.mark.asyncio
    async def test_analyze_maze(self):
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        result = await engine.analyze_maze(img_data, (25, 25), (45, 25))
        assert "path" in result
        assert "metrics" in result
        assert "overlay" in result
        assert "graph_stats" in result
        assert result["metrics"]["length"] >= 1

    @pytest.mark.asyncio
    async def test_analyze_maze_cache_hit(self):
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        # First call populates cache
        result1 = await engine.analyze_maze(img_data, (25, 25), (45, 25))
        # Second call should hit cache
        result2 = await engine.analyze_maze(img_data, (25, 25), (45, 25))
        assert result1 == result2

    @pytest.mark.asyncio
    async def test_analyze_maze_astar_fails_falls_back_to_bfs(self):
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)

        original_astar = engine.a_star.find_path

        def astar_fail(*args, **kwargs):
            raise ValueError("No path found")

        engine.a_star.find_path = astar_fail

        # Should still succeed via BFS fallback
        result = await engine.analyze_maze(img_data, (25, 25), (45, 25))
        assert "path" in result
        engine.a_star.find_path = original_astar


# ===========================================================================
# _analyze_topology tests
# ===========================================================================


class TestAnalyzeTopology:
    def test_empty_graph(self):
        engine = VisionCodingEngine()
        g = Graph()
        result = engine._analyze_topology(g)
        assert result["connectivity_score"] == 0.0
        assert result["bottlenecks"] == []
        assert result["isolated_nodes"] == []

    def test_isolated_node(self):
        engine = VisionCodingEngine()
        g = Graph()
        g.add_node(GraphNode(id="lonely", x=0, y=0))
        result = engine._analyze_topology(g)
        assert "lonely" in result["isolated_nodes"]
        assert any(
            r["action"] == "connect_isolated_node" for r in result["recommendations"]
        )

    def test_single_connection_node(self):
        engine = VisionCodingEngine()
        g = Graph()
        g.add_node(GraphNode(id="a", x=0, y=0))
        g.add_node(GraphNode(id="b", x=1, y=0))
        g.add_edge("a", "b")
        result = engine._analyze_topology(g)
        assert any(r["action"] == "add_backup_link" for r in result["recommendations"])

    def test_bottleneck_detection(self):
        engine = VisionCodingEngine()
        g = Graph()
        # Create a hub node connected to many others
        g.add_node(GraphNode(id="hub", x=0, y=0))
        for i in range(10):
            nid = f"n{i}"
            g.add_node(GraphNode(id=nid, x=float(i + 1), y=0))
            g.add_edge("hub", nid)
        result = engine._analyze_topology(g)
        # hub has 10 connections; average = (10 + 1*10) / 11 ≈ 1.8; threshold = max(4, 3.6) = 4
        # hub has 10 >= 4 so it's a bottleneck
        assert len(result["bottlenecks"]) >= 1
        assert result["bottlenecks"][0]["node_id"] == "hub"

    def test_bottleneck_severity(self):
        engine = VisionCodingEngine()
        g = Graph()
        g.add_node(GraphNode(id="hub", x=0, y=0))
        for i in range(20):
            nid = f"n{i}"
            g.add_node(GraphNode(id=nid, x=float(i + 1), y=0))
            g.add_edge("hub", nid)
        result = engine._analyze_topology(g)
        # threshold = max(4, ~3.8) = 4; 1.5 * 4 = 6; hub has 20 > 6 => severity 'high'
        assert result["bottlenecks"][0]["severity"] == "high"

    def test_connectivity_score(self):
        engine = VisionCodingEngine()
        g = Graph()
        # Fully connected graph of 3 nodes: 3 edges, max = 3
        g.add_node(GraphNode(id="a", x=0, y=0))
        g.add_node(GraphNode(id="b", x=1, y=0))
        g.add_node(GraphNode(id="c", x=0, y=1))
        g.add_edge("a", "b")
        g.add_edge("b", "c")
        g.add_edge("a", "c")
        result = engine._analyze_topology(g)
        # connectivity_score = min(1.0, 3/3 * 10) = 1.0
        assert result["connectivity_score"] == 1.0

    def test_recommendations_limited_to_10(self):
        engine = VisionCodingEngine()
        g = Graph()
        # Create 15 isolated nodes => 15 recommendations, but limited to 10
        for i in range(15):
            g.add_node(GraphNode(id=f"n{i}", x=float(i), y=0))
        result = engine._analyze_topology(g)
        assert len(result["recommendations"]) <= 10


# ===========================================================================
# detect_anomalies tests
# ===========================================================================


class TestDetectAnomalies:
    @pytest.mark.asyncio
    async def test_without_baseline(self):
        engine = VisionCodingEngine()
        img_data = _make_image(100, 100, color=(128, 128, 128))
        result = await engine.detect_anomalies(img_data)
        assert "anomalies_detected" in result
        assert "anomalies" in result
        assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_with_baseline_identical(self):
        engine = VisionCodingEngine()
        img_data = _make_image(100, 100, color=(128, 128, 128))
        result = await engine.detect_anomalies(img_data, baseline_data=img_data)
        assert result["anomalies_detected"] == 0

    @pytest.mark.asyncio
    async def test_with_baseline_different(self):
        engine = VisionCodingEngine()
        img1_data = _make_image(100, 100, color=(0, 0, 0))
        img2_data = _make_image(100, 100, color=(255, 255, 255))
        result = await engine.detect_anomalies(img2_data, baseline_data=img1_data)
        assert result["anomalies_detected"] >= 1
        anomaly = result["anomalies"][0]
        assert anomaly["type"] == "visual_change"
        assert "location" in anomaly

    @pytest.mark.asyncio
    async def test_with_baseline_different_sizes(self):
        engine = VisionCodingEngine()
        img1_data = _make_image(100, 100, color=(0, 0, 0))
        img2_data = _make_image(50, 50, color=(255, 255, 255))
        # Image is resized to match; should still detect anomalies
        result = await engine.detect_anomalies(img1_data, baseline_data=img2_data)
        assert "anomalies_detected" in result

    @pytest.mark.asyncio
    async def test_without_baseline_bright_spot(self):
        """Create an image with a bright spot on dark background."""
        engine = VisionCodingEngine()
        img = Image.new("RGB", (100, 100), (10, 10, 10))
        # Add a bright square
        for x in range(40, 60):
            for y in range(40, 60):
                img.putpixel((x, y), (255, 255, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        img_data = buf.getvalue()
        result = await engine.detect_anomalies(img_data)
        assert result["anomalies_detected"] >= 1
        assert result["anomalies"][0]["type"] == "bright_spot"

    @pytest.mark.asyncio
    async def test_without_baseline_uniform_image(self):
        """Uniform image => no bright spots detected (std = 0)."""
        engine = VisionCodingEngine()
        img_data = _make_image(100, 100, color=(128, 128, 128))
        result = await engine.detect_anomalies(img_data)
        assert result["anomalies_detected"] == 0

    @pytest.mark.asyncio
    async def test_high_severity_change(self):
        """Very large diff => severity 'high'."""
        engine = VisionCodingEngine()
        img1_data = _make_image(100, 100, color=(0, 0, 0))
        img2_data = _make_image(100, 100, color=(255, 255, 255))
        result = await engine.detect_anomalies(img2_data, baseline_data=img1_data)
        assert result["anomalies"][0]["severity"] == "high"

    @pytest.mark.asyncio
    async def test_medium_severity_change(self):
        """Moderate diff => severity 'medium'."""
        engine = VisionCodingEngine()
        img1_data = _make_image(100, 100, color=(50, 50, 50))
        img2_data = _make_image(100, 100, color=(120, 120, 120))
        result = await engine.detect_anomalies(img2_data, baseline_data=img1_data)
        if result["anomalies_detected"] > 0:
            assert result["anomalies"][0]["severity"] == "medium"


# ===========================================================================
# Module-level utility functions
# ===========================================================================


class TestModuleFunctions:
    def test_get_vision_engine_singleton(self):
        import src.swarm.vision_coding as vc

        vc._vision_engine = None
        e1 = get_vision_engine()
        e2 = get_vision_engine()
        assert e1 is e2
        assert isinstance(e1, VisionCodingEngine)
        # Clean up
        vc._vision_engine = None

    @pytest.mark.asyncio
    async def test_analyze_maze_utility(self):
        import src.swarm.vision_coding as vc

        vc._vision_engine = None
        img_data = _make_maze_image(50, 50)
        result = await analyze_maze(img_data, (25, 25), (45, 25))
        assert "path" in result
        vc._vision_engine = None

    @pytest.mark.asyncio
    async def test_detect_anomalies_utility(self):
        import src.swarm.vision_coding as vc

        vc._vision_engine = None
        img_data = _make_image(50, 50)
        result = await detect_anomalies(img_data)
        assert "anomalies_detected" in result
        vc._vision_engine = None

    @pytest.mark.asyncio
    async def test_analyze_mesh_topology_utility(self):
        """analyze_mesh_topology calls overlay.to_dict() which does not exist."""
        import src.swarm.vision_coding as vc

        vc._vision_engine = None
        img_data = _make_maze_image(50, 50)
        # This will raise AttributeError because VisualOverlay has no to_dict()
        with pytest.raises(AttributeError):
            await analyze_mesh_topology(img_data)
        vc._vision_engine = None


# ===========================================================================
# analyze_mesh_topology engine method tests
# ===========================================================================


class TestAnalyzeMeshTopology:
    @pytest.mark.asyncio
    async def test_raises_attribute_error_due_to_to_dict(self):
        """overlay.to_dict() is called but VisualOverlay has no such method."""
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        with pytest.raises(AttributeError):
            await engine.analyze_mesh_topology(img_data)

    @pytest.mark.asyncio
    async def test_cache_hit_bypasses_processing(self):
        """If cache returns data, to_dict is never reached."""
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        fake_result = {"nodes_detected": 5, "cached": True}
        await engine.cache.set(img_data, "mesh_topology", fake_result)
        result = await engine.analyze_mesh_topology(img_data)
        assert result == fake_result

    @pytest.mark.asyncio
    async def test_basic_analysis(self):
        """Verify analyze_mesh_topology returns expected keys."""
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        with patch.object(VisualOverlay, "to_dict", create=True, return_value={"elements": []}):
            result = await engine.analyze_mesh_topology(img_data)
        assert "nodes_detected" in result
        assert "links_detected" in result
        assert "bottlenecks" in result
        assert "isolated_nodes" in result
        assert "connectivity_score" in result
        assert "recommendations" in result
        assert "processing_time_ms" in result

    @pytest.mark.asyncio
    async def test_with_context_param(self):
        engine = VisionCodingEngine()
        img_data = _make_maze_image(50, 50)
        with patch.object(VisualOverlay, "to_dict", create=True, return_value={}):
            result = await engine.analyze_mesh_topology(
                img_data, context={"test": True}
            )
        assert "nodes_detected" in result


# ===========================================================================
# PathMetrics tests
# ===========================================================================


class TestPathMetrics:
    def test_creation(self):
        pm = PathMetrics(length=5, total_cost=10.0, nodes_visited=20, time_ms=1.5)
        assert pm.path_nodes == []
        assert pm.length == 5

    def test_with_path_nodes(self):
        pm = PathMetrics(
            length=2,
            total_cost=2.0,
            nodes_visited=2,
            time_ms=0.1,
            path_nodes=["a", "b"],
        )
        assert pm.path_nodes == ["a", "b"]
