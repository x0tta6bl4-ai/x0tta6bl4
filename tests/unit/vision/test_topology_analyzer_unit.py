"""Unit tests for src/vision/topology_analyzer.py - MeshTopologyAnalyzer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.vision.topology_analyzer import (
    MeshTopologyAnalyzer,
    NodeMetrics,
    LinkMetrics,
    TopologyMetrics,
)


class TestNodeMetrics:
    """Tests for NodeMetrics dataclass."""
    
    def test_node_metrics_defaults(self):
        """Test default values."""
        node = NodeMetrics(node_id="node-1")
        assert node.node_id == "node-1"
        assert node.centrality == 0.0
        assert node.degree == 0
        assert node.is_bottleneck is False
        assert node.is_isolated is False
        assert node.health_score == 1.0
    
    def test_node_metrics_with_values(self):
        """Test with custom values."""
        node = NodeMetrics(
            node_id="node-2",
            centrality=0.8,
            degree=5,
            is_bottleneck=True,
            health_score=0.5
        )
        assert node.centrality == 0.8
        assert node.degree == 5
        assert node.is_bottleneck is True
        assert node.health_score == 0.5


class TestLinkMetrics:
    """Tests for LinkMetrics dataclass."""
    
    def test_link_metrics_defaults(self):
        """Test default values."""
        link = LinkMetrics(source="node-1", target="node-2")
        assert link.source == "node-1"
        assert link.target == "node-2"
        assert link.bandwidth == 0.0
        assert link.latency_ms == 0.0
        assert link.is_congested is False
    
    def test_link_metrics_congestion(self):
        """Test congestion detection."""
        link = LinkMetrics(
            source="node-1",
            target="node-2",
            latency_ms=150,
            is_congested=True
        )
        assert link.latency_ms == 150
        assert link.is_congested is True


class TestMeshTopologyAnalyzer:
    """Tests for MeshTopologyAnalyzer class."""
    
    @pytest.fixture
    def mock_processor(self):
        """Create mock VisionProcessor."""
        processor = MagicMock()
        processor.process_image = AsyncMock(return_value={
            "objects_detected": [
                {"id": "node-1", "type": "router"},
                {"id": "node-2", "type": "switch"},
                {"id": "node-3", "type": "host"},
            ],
            "links": [
                {"source": "node-1", "target": "node-2", "latency_ms": 10},
                {"source": "node-2", "target": "node-3", "latency_ms": 5},
            ],
            "findings": {"test": "data"}
        })
        return processor
    
    @pytest.fixture
    def analyzer(self, mock_processor):
        """Create analyzer with mock processor."""
        return MeshTopologyAnalyzer(
            vision_processor=mock_processor,
            config={"centrality_threshold": 0.8, "latency_threshold_ms": 100}
        )
    
    def test_analyzer_init(self, analyzer):
        """Test analyzer initialization."""
        assert analyzer.processor is not None
        assert analyzer._centrality_threshold == 0.8
        assert analyzer._latency_threshold_ms == 100
        assert isinstance(analyzer._cache, dict)
    
    def test_compute_node_degree(self, analyzer):
        """Test node degree computation."""
        nodes = [
            {"id": "n1"}, {"id": "n2"}, {"id": "n3"}
        ]
        links = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
        ]
        
        degrees = analyzer._compute_node_degree(nodes, links)
        
        assert degrees["n1"] == 1
        assert degrees["n2"] == 2
        assert degrees["n3"] == 1
    
    def test_compute_centrality(self, analyzer):
        """Test centrality computation."""
        nodes = [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}]
        links = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
        ]
        
        centrality = analyzer._compute_centrality(nodes, links)
        
        assert "n1" in centrality
        assert "n2" in centrality
        assert "n3" in centrality
        assert centrality["n2"] > centrality["n1"]  # n2 has higher degree
    
    def test_detect_bottlenecks(self, analyzer):
        """Test bottleneck detection."""
        nodes = [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}]
        links = [
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
        ]
        centrality = {"n1": 0.3, "n2": 0.9, "n3": 0.3}
        
        bottlenecks = analyzer._detect_bottlenecks(nodes, links, centrality)
        
        assert "n2" in bottlenecks
        assert "n1" not in bottlenecks
    
    def test_detect_isolated_nodes(self, analyzer):
        """Test isolated node detection."""
        nodes = [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}]
        links = [
            {"source": "n1", "target": "n2"},
        ]
        
        isolated = analyzer._detect_isolated_nodes(nodes, links)
        
        assert "n3" in isolated
        assert "n1" not in isolated
    
    def test_compute_resilience_score(self, analyzer):
        """Test resilience score calculation."""
        nodes = [{"id": "n1"}, {"id": "n2"}]
        links = [{"source": "n1", "target": "n2"}]
        
        # Normal network
        score = analyzer._compute_resilience_score(nodes, links, set(), set())
        assert score > 0.5
        
        # Network with bottlenecks
        score_with_bottleneck = analyzer._compute_resilience_score(
            nodes, links, {"n1"}, set()
        )
        assert score_with_bottleneck < score
        
        # Network with isolated nodes
        score_with_isolated = analyzer._compute_resilience_score(
            nodes, links, set(), {"n2"}
        )
        assert score_with_isolated < score
    
    @pytest.mark.asyncio
    async def test_analyze_bytes_success(self, analyzer, mock_processor):
        """Test successful analysis."""
        image_data = b"fake image data"
        
        result = await analyzer.analyze_bytes(image_data)
        
        assert result["status"] == "success"
        assert result["nodes_detected"] == 3
        assert result["links_detected"] == 2
        assert "metrics" in result
    
    @pytest.mark.asyncio
    async def test_analyze_bytes_caching(self, analyzer, mock_processor):
        """Test that results are cached."""
        image_data = b"test data"
        
        # First call
        result1 = await analyzer.analyze_bytes(image_data)
        
        # Second call should use cache
        result2 = await analyzer.analyze_bytes(image_data)
        
        assert result1["status"] == result2["status"]
        assert result1["nodes_detected"] == result2["nodes_detected"]
    
    @pytest.mark.asyncio
    async def test_analyze_bytes_no_detection(self, analyzer):
        """Test error when no topology detected."""
        analyzer.processor.process_image = AsyncMock(return_value={
            "objects_detected": [],
            "findings": {}
        })
        
        with pytest.raises(RuntimeError, match="Vision model failed to detect"):
            await analyzer.analyze_bytes(b"test")
    
    @pytest.mark.asyncio
    async def test_analyze_from_path(self, analyzer, tmp_path):
        """Test analysis from file path."""
        # Create temporary image file
        test_file = tmp_path / "topology.png"
        test_file.write_bytes(b"fake png data")
        
        # Mock the processor to avoid actual API call
        analyzer.processor.process_image = AsyncMock(return_value={
            "objects_detected": [{"id": "node-1"}],
            "links": [],
            "findings": {}
        })
        
        result = await analyzer.analyze(str(test_file))
        
        assert result["status"] == "success"
        assert result["nodes_detected"] == 1
    
    @pytest.mark.asyncio
    async def test_analyze_file_not_found(self, analyzer):
        """Test error for missing file."""
        with pytest.raises(FileNotFoundError):
            await analyzer.analyze("/nonexistent/path.png")
    
    def test_clear_cache(self, analyzer):
        """Test cache clearing."""
        analyzer._cache["test"] = "value"
        
        analyzer.clear_cache()
        
        assert len(analyzer._cache) == 0


class TestTopologyAlgorithms:
    """Tests for topology analysis algorithms."""
    
    @pytest.fixture
    def analyzer(self):
        """Create analyzer with default config."""
        return MeshTopologyAnalyzer()
    
    def test_degree_centrality_empty_graph(self, analyzer):
        """Test with empty graph."""
        nodes = []
        links = []
        
        degrees = analyzer._compute_node_degree(nodes, links)
        centrality = analyzer._compute_centrality(nodes, links)
        
        assert degrees == {}
        assert centrality == {}
    
    def test_degree_centrality_single_node(self, analyzer):
        """Test with single node."""
        nodes = [{"id": "n1"}]
        links = []
        
        degrees = analyzer._compute_node_degree(nodes, links)
        centrality = analyzer._compute_centrality(nodes, links)
        
        assert degrees["n1"] == 0
        assert centrality["n1"] == 0.0
    
    def test_bottleneck_detection_high_centrality(self, analyzer):
        """Test bottleneck detection with high centrality nodes."""
        nodes = [{"id": "n1"}, {"id": "n2"}]
        links = [{"source": "n1", "target": "n2"}]
        
        # n1 has higher centrality
        centrality = {"n1": 0.95, "n2": 0.3}
        
        bottlenecks = analyzer._detect_bottlenecks(nodes, links, centrality)
        
        assert "n1" in bottlenecks
    
    def test_resilience_score_empty_network(self, analyzer):
        """Test resilience with empty network."""
        score = analyzer._compute_resilience_score([], [], set(), set())
        assert score == 0.0
    
    def test_resilience_perfect_network(self, analyzer):
        """Test resilience of fully connected network."""
        nodes = [{"id": f"n{i}"} for i in range(4)]
        links = [
            {"source": "n0", "target": "n1"},
            {"source": "n1", "target": "n2"},
            {"source": "n2", "target": "n3"},
            {"source": "n3", "target": "n0"},
            {"source": "n0", "target": "n2"},
        ]
        
        score = analyzer._compute_resilience_score(nodes, links, set(), set())
        
        assert score > 0.8  # Should be high for connected graph
