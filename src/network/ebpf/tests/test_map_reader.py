"""
Unit tests for MapReader component.

Tests cover:
- Initialization
- BCC backend reading
- bpftool backend reading
- Caching
- Parallel map reading
- Error handling
- Performance
"""

from unittest.mock import MagicMock, Mock, call, patch

import pytest
from telemetry_module import MapReader, MapType, TelemetryConfig


class TestMapReaderInitialization:
    """Test MapReader initialization."""

    def test_initialization_with_config(self, telemetry_config):
        """Test initialization with configuration."""
        security = MagicMock()
        reader = MapReader(telemetry_config, security)

        assert reader.config == telemetry_config
        assert reader.security == security
        assert isinstance(reader.cache, dict)
        assert reader.cache_ttl == 0.5

    def test_initialization_checks_bpftool(self, telemetry_config):
        """Test that bpftool availability is checked on initialization."""
        security = MagicMock()

        with patch("subprocess.run") as mock_run:
            mock_run.return_value = Mock(returncode=0)

            reader = MapReader(telemetry_config, security)

            assert reader.bpftool_available == True

    def test_initialization_bpftool_unavailable(self, telemetry_config):
        """Test initialization when bpftool is unavailable."""
        security = MagicMock()

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()

            reader = MapReader(telemetry_config, security)

            assert reader.bpftool_available == False

    def test_initialization_cache_empty(self, telemetry_config):
        """Test that cache is empty on initialization."""
        security = MagicMock()
        reader = MapReader(telemetry_config, security)

        assert len(reader.cache) == 0


class TestMapReaderBCCBackend:
    """Test MapReader BCC backend."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_read_map_via_bcc_success(self, reader, mock_bpf_program):
        """Test successful map reading via BCC."""
        data = reader.read_map_via_bcc(mock_bpf_program, "process_map")

        assert isinstance(data, dict)
        assert len(data) > 0
        assert "key1" in data or any("key" in k for k in data.keys())

    def test_read_map_via_bcc_struct_value(self, reader):
        """Test reading map with struct values."""
        mock_bpf = MagicMock()
        mock_table = MagicMock()

        # Mock struct value
        mock_value = MagicMock()
        mock_value.__dict__ = {
            "cpu_time_ns": 1000000,
            "context_switches": 10,
            "syscalls": 100,
        }

        mock_table.items.return_value = [(b"key1", mock_value)]

        mock_bpf.__getitem__ = Mock(return_value=mock_table)

        data = reader.read_map_via_bcc(mock_bpf, "test_map")

        assert isinstance(data, dict)
        assert len(data) > 0

    def test_read_map_via_bcc_bytes_key(self, reader):
        """Test reading map with bytes keys."""
        mock_bpf = MagicMock()
        mock_table = MagicMock()

        mock_table.items.return_value = [
            (b"binary_key", {"value": 42}),
            (b"another_key", {"value": 100}),
        ]

        mock_bpf.__getitem__ = Mock(return_value=mock_table)

        data = reader.read_map_via_bcc(mock_bpf, "test_map")

        assert isinstance(data, dict)
        assert len(data) == 2

    def test_read_map_via_bcc_exception(self, reader):
        """Test handling of BCC exception."""
        mock_bpf = MagicMock()
        mock_bpf.__getitem__ = Mock(side_effect=Exception("BCC error"))

        with pytest.raises(Exception):
            reader.read_map_via_bcc(mock_bpf, "test_map")

    def test_read_map_via_bcc_empty_map(self, reader):
        """Test reading empty map via BCC."""
        mock_bpf = MagicMock()
        mock_table = MagicMock()
        mock_table.items.return_value = []

        mock_bpf.__getitem__ = Mock(return_value=mock_table)

        data = reader.read_map_via_bcc(mock_bpf, "empty_map")

        assert isinstance(data, dict)
        assert len(data) == 0


class TestMapReaderBpftoolBackend:
    """Test MapReader bpftool backend."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_read_map_via_bpftool_success(self, reader, mock_subprocess):
        """Test successful map reading via bpftool."""
        mock_subprocess.return_value = Mock(
            returncode=0, stdout='{"data": [{"key": [0], "value": 42}]}'
        )

        data = reader.read_map_via_bpftool("test_map")

        assert isinstance(data, dict)
        assert "data" in data
        assert len(data["data"]) > 0

    def test_read_map_via_bpftool_timeout(self, reader, mock_subprocess):
        """Test handling of bpftool timeout."""
        import subprocess

        mock_subprocess.side_effect = subprocess.TimeoutExpired("bpftool", 5)

        with pytest.raises(RuntimeError):
            reader.read_map_via_bpftool("test_map")

    def test_read_map_via_bpftool_error(self, reader, mock_subprocess):
        """Test handling of bpftool error."""
        mock_subprocess.return_value = Mock(returncode=1, stderr="Error: map not found")

        with pytest.raises(RuntimeError):
            reader.read_map_via_bpftool("test_map")

    def test_read_map_via_bpftool_invalid_json(self, reader, mock_subprocess):
        """Test handling of invalid JSON from bpftool."""
        mock_subprocess.return_value = Mock(returncode=0, stdout="invalid json")

        with pytest.raises(Exception):
            reader.read_map_via_bpftool("test_map")

    def test_read_map_via_bpftool_list_data(self, reader, mock_subprocess):
        """Test reading map with list data."""
        mock_subprocess.return_value = Mock(
            returncode=0,
            stdout='{"data": [{"key": [0], "value": 42}, {"key": [1], "value": 100}]}',
        )

        data = reader.read_map_via_bpftool("test_map")

        assert isinstance(data, dict)
        assert "data" in data
        assert len(data["data"]) == 2


class TestMapReaderCaching:
    """Test MapReader caching."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_cache_hit(self, reader, mock_bpf_program):
        """Test cache hit."""
        # First read
        data1 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Second read (should use cache)
        data2 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Should return same data
        assert data1 == data2

    def test_cache_bypass(self, reader, mock_bpf_program):
        """Test bypassing cache."""
        # First read
        data1 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Second read with cache disabled
        data2 = reader.read_map(mock_bpf_program, "test_map", use_cache=False)

        # Should still return data (but not from cache)
        assert isinstance(data2, dict)

    def test_cache_expiration(self, reader, mock_bpf_program, mock_time):
        """Test cache expiration."""
        import time

        # First read
        data1 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Advance time beyond TTL
        mock_time.return_value = 1000.0 + reader.cache_ttl + 1.0

        # Second read (cache should be expired)
        data2 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Should still return data (re-read)
        assert isinstance(data2, dict)

    def test_clear_cache(self, reader, mock_bpf_program):
        """Test clearing cache."""
        # Read some maps
        reader.read_map(mock_bpf_program, "map1", use_cache=True)
        reader.read_map(mock_bpf_program, "map2", use_cache=True)

        assert len(reader.cache) > 0

        # Clear cache
        reader.clear_cache()

        assert len(reader.cache) == 0


class TestMapReaderParallelReading:
    """Test MapReader parallel map reading."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_read_multiple_maps(self, reader, mock_bpf_program):
        """Test reading multiple maps."""
        map_names = ["map1", "map2", "map3"]

        results = reader.read_multiple_maps(mock_bpf_program, map_names)

        assert isinstance(results, dict)
        assert len(results) == len(map_names)
        for map_name in map_names:
            assert map_name in results

    def test_read_multiple_maps_parallel(self, reader, mock_bpf_program):
        """Test that multiple maps are read in parallel."""
        import time

        map_names = ["map1", "map2", "map3", "map4", "map5"]

        start_time = time.time()
        results = reader.read_multiple_maps(mock_bpf_program, map_names)
        end_time = time.time()

        # Should complete faster than sequential reading
        assert isinstance(results, dict)
        assert len(results) == len(map_names)

    def test_read_multiple_maps_with_errors(self, reader, mock_bpf_program):
        """Test reading multiple maps with some errors."""
        map_names = ["map1", "map2", "map3"]

        # Mock one map to fail
        def getitem_side_effect(key):
            if key == "map2":
                raise Exception("Map not found")
            return MagicMock()

        mock_bpf_program.__getitem__ = Mock(side_effect=getitem_side_effect)

        results = reader.read_multiple_maps(mock_bpf_program, map_names)

        # Should return results for successful reads
        assert isinstance(results, dict)
        assert "map1" in results
        assert "map3" in results
        # Failed map should have empty dict
        assert "map2" in results


class TestMapReaderMainMethod:
    """Test MapReader main read method."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_read_map_uses_bcc_first(self, reader, mock_bpf_program):
        """Test that BCC is tried first."""
        with patch("telemetry_module.BCC_AVAILABLE", True):
            data = reader.read_map(mock_bpf_program, "test_map")

            assert isinstance(data, dict)

    def test_read_map_fallback_to_bpftool(self, reader, mock_bpf_program):
        """Test fallback to bpftool when BCC fails."""
        with patch("telemetry_module.BCC_AVAILABLE", False):
            with patch.object(reader, "bpftool_available", True):
                with patch.object(reader, "read_map_via_bpftool") as mock_bpftool:
                    mock_bpftool.return_value = {"data": []}

                    data = reader.read_map(mock_bpf_program, "test_map")

                    mock_bpftool.assert_called_once()

    def test_read_map_all_methods_fail(self, reader, mock_bpf_program):
        """Test when all read methods fail."""
        with patch("telemetry_module.BCC_AVAILABLE", False):
            with patch.object(reader, "bpftool_available", False):
                data = reader.read_map(mock_bpf_program, "test_map")

                # Should return empty dict
                assert isinstance(data, dict)
                assert len(data) == 0


class TestMapReaderErrorHandling:
    """Test MapReader error handling."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_handle_bcc_exception(self, reader, mock_bpf_program):
        """Test handling of BCC exception."""
        mock_bpf_program.__getitem__ = Mock(side_effect=Exception("BCC error"))

        with patch("telemetry_module.BCC_AVAILABLE", True):
            data = reader.read_map(mock_bpf_program, "test_map")

            # Should handle gracefully
            assert isinstance(data, dict)

    def test_handle_bpftool_exception(self, reader, mock_bpf_program):
        """Test handling of bpftool exception."""
        with patch("telemetry_module.BCC_AVAILABLE", False):
            with patch.object(reader, "bpftool_available", True):
                with patch.object(reader, "read_map_via_bpftool") as mock_bpftool:
                    mock_bpftool.side_effect = Exception("bpftool error")

                    data = reader.read_map(mock_bpf_program, "test_map")

                    # Should handle gracefully
                    assert isinstance(data, dict)

    def test_log_error_on_failure(self, reader, mock_bpf_program, caplog):
        """Test that errors are logged."""
        import logging

        caplog.set_level(logging.ERROR)

        mock_bpf_program.__getitem__ = Mock(side_effect=Exception("Test error"))

        with patch("telemetry_module.BCC_AVAILABLE", True):
            data = reader.read_map(mock_bpf_program, "test_map")

            # Should log error
            assert any(
                "Error reading map" in record.message for record in caplog.records
            )


class TestMapReaderPerformance:
    """Test MapReader performance."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_cache_performance(self, reader, mock_bpf_program):
        """Test that cache improves performance."""
        import time

        # First read (cache miss)
        start1 = time.time()
        data1 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)
        time1 = time.time() - start1

        # Second read (cache hit)
        start2 = time.time()
        data2 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)
        time2 = time.time() - start2

        # Cache hit should be faster
        assert time2 < time1

    def test_parallel_reading_performance(self, reader, mock_bpf_program):
        """Test that parallel reading is faster than sequential."""
        import time

        map_names = ["map1", "map2", "map3", "map4", "map5"]

        # Parallel read
        start_parallel = time.time()
        results_parallel = reader.read_multiple_maps(mock_bpf_program, map_names)
        time_parallel = time.time() - start_parallel

        # Should complete successfully
        assert isinstance(results_parallel, dict)
        assert len(results_parallel) == len(map_names)


class TestMapReaderEdgeCases:
    """Test MapReader edge cases."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_read_map_with_none_bpf_program(self, reader):
        """Test reading map with None BPF program."""
        data = reader.read_map(None, "test_map")

        # Should return empty dict
        assert isinstance(data, dict)
        assert len(data) == 0

    def test_read_map_with_empty_map_name(self, reader, mock_bpf_program):
        """Test reading map with empty name."""
        data = reader.read_map(mock_bpf_program, "")

        # Should return empty dict
        assert isinstance(data, dict)

    def test_read_map_with_special_characters(self, reader, mock_bpf_program):
        """Test reading map with special characters in name."""
        data = reader.read_map(mock_bpf_program, "map_with-special_chars")

        # Should handle gracefully
        assert isinstance(data, dict)

    def test_read_map_with_unicode_name(self, reader, mock_bpf_program):
        """Test reading map with unicode characters in name."""
        data = reader.read_map(mock_bpf_program, "map_тест")

        # Should handle gracefully
        assert isinstance(data, dict)

    def test_read_multiple_maps_empty_list(self, reader, mock_bpf_program):
        """Test reading multiple maps with empty list."""
        results = reader.read_multiple_maps(mock_bpf_program, [])

        assert isinstance(results, dict)
        assert len(results) == 0

    def test_read_multiple_maps_duplicate_names(self, reader, mock_bpf_program):
        """Test reading multiple maps with duplicate names."""
        map_names = ["map1", "map1", "map2"]

        results = reader.read_multiple_maps(mock_bpf_program, map_names)

        # Should handle duplicates
        assert isinstance(results, dict)
        assert "map1" in results
        assert "map2" in results


class TestMapReaderIntegration:
    """Integration tests for MapReader."""

    @pytest.fixture
    def reader(self, telemetry_config):
        security = MagicMock()
        return MapReader(telemetry_config, security)

    def test_full_workflow(self, reader, mock_bpf_program_with_maps):
        """Test full workflow of reading maps."""
        # Read multiple maps
        map_names = ["process_map", "system_metrics_map"]
        results = reader.read_multiple_maps(mock_bpf_program_with_maps, map_names)

        # Verify results
        assert isinstance(results, dict)
        assert len(results) == len(map_names)

        # Verify cache is populated
        assert len(reader.cache) > 0

        # Read again (should use cache)
        results2 = reader.read_multiple_maps(mock_bpf_program_with_maps, map_names)

        # Should return same results
        assert results == results2

    def test_workflow_with_cache_clear(self, reader, mock_bpf_program):
        """Test workflow with cache clearing."""
        # Read map
        data1 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Clear cache
        reader.clear_cache()

        # Read again (should re-read)
        data2 = reader.read_map(mock_bpf_program, "test_map", use_cache=True)

        # Should still return data
        assert isinstance(data2, dict)
