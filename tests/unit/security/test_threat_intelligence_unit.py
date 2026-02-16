"""Unit tests for src.security.threat_intelligence module."""

from unittest.mock import patch

import pytest

from src.security.threat_intelligence import (BloomFilter, IndicatorType,
                                              ThreatIndicator,
                                              ThreatIntelligenceEngine,
                                              ThreatReport, ThreatSeverity,
                                              ThreatType)


class TestBloomFilter:
    """Tests for BloomFilter."""

    def test_add_and_contains(self):
        bf = BloomFilter(size=1000, num_hashes=5)
        bf.add("malicious-node-1")
        bf.add("malicious-node-2")

        assert bf.contains("malicious-node-1") is True
        assert bf.contains("malicious-node-2") is True

    def test_contains_returns_false_for_absent_item(self):
        bf = BloomFilter(size=1000, num_hashes=5)
        bf.add("present")

        assert bf.contains("absent") is False

    def test_false_positive_rate_is_reasonable(self):
        """With a large enough filter and few items, false positives should be rare."""
        bf = BloomFilter(size=10000, num_hashes=7)
        for i in range(50):
            bf.add(f"item-{i}")

        false_positives = 0
        test_count = 1000
        for i in range(test_count):
            if bf.contains(f"not-added-{i}"):
                false_positives += 1

        # With size=10000, 7 hashes, and 50 items, FP rate should be very low
        assert false_positives < test_count * 0.05

    def test_merge_combines_two_filters(self):
        bf1 = BloomFilter(size=1000, num_hashes=5)
        bf2 = BloomFilter(size=1000, num_hashes=5)

        bf1.add("alpha")
        bf2.add("beta")

        assert bf1.contains("alpha") is True
        assert bf1.contains("beta") is False

        bf1.merge(bf2)

        assert bf1.contains("alpha") is True
        assert bf1.contains("beta") is True

    def test_merge_different_sizes_raises(self):
        bf1 = BloomFilter(size=1000, num_hashes=5)
        bf2 = BloomFilter(size=2000, num_hashes=5)

        with pytest.raises(ValueError, match="Cannot merge filters of different sizes"):
            bf1.merge(bf2)

    def test_to_bytes_from_bytes_roundtrip(self):
        bf = BloomFilter(size=1000, num_hashes=5)
        bf.add("test-value-1")
        bf.add("test-value-2")

        serialized = bf.to_bytes()
        restored = BloomFilter.from_bytes(serialized, size=1000, num_hashes=5)

        assert restored.contains("test-value-1") is True
        assert restored.contains("test-value-2") is True
        assert restored.contains("never-added") is False

    def test_to_bytes_from_bytes_preserves_bits(self):
        bf = BloomFilter(size=500, num_hashes=3)
        bf.add("x")
        bf.add("y")

        data = bf.to_bytes()
        bf2 = BloomFilter.from_bytes(data, size=500, num_hashes=3)

        assert bf.bits == bf2.bits


class TestThreatIndicator:
    """Tests for ThreatIndicator dataclass."""

    def test_is_expired_returns_false_when_within_ttl(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            indicator = ThreatIndicator(
                id="ind1",
                type=IndicatorType.IP_ADDRESS,
                value="10.0.0.1",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=0.9,
                first_seen=900.0,
                last_seen=900.0,
                reporter_id="node-1",
                ttl=200,
            )
            # time.time() = 1000, first_seen + ttl = 1100 => not expired
            assert indicator.is_expired() is False

    def test_is_expired_returns_true_when_past_ttl(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 2000.0
            indicator = ThreatIndicator(
                id="ind2",
                type=IndicatorType.NODE_ID,
                value="bad-node",
                threat_type=ThreatType.MALICIOUS_NODE,
                severity=ThreatSeverity.CRITICAL,
                confidence=0.95,
                first_seen=100.0,
                last_seen=100.0,
                reporter_id="node-1",
                ttl=500,
            )
            # time.time() = 2000, first_seen + ttl = 600 => expired
            assert indicator.is_expired() is True

    def test_to_dict(self):
        indicator = ThreatIndicator(
            id="abc123",
            type=IndicatorType.IP_ADDRESS,
            value="192.168.1.1",
            threat_type=ThreatType.NETWORK_PROBE,
            severity=ThreatSeverity.MEDIUM,
            confidence=0.75,
            first_seen=1000.0,
            last_seen=1001.0,
            reporter_id="node-x",
            description="Suspicious probe",
            corroborations=3,
        )
        d = indicator.to_dict()

        assert d["id"] == "abc123"
        assert d["type"] == "ip"
        assert d["value"] == "192.168.1.1"
        assert d["threat_type"] == "network_probe"
        assert d["severity"] == 3
        assert d["confidence"] == 0.75
        assert d["first_seen"] == 1000.0
        assert d["last_seen"] == 1001.0
        assert d["reporter_id"] == "node-x"
        assert d["description"] == "Suspicious probe"
        assert d["corroborations"] == 3


class TestThreatIntelligenceEngine:
    """Tests for ThreatIntelligenceEngine."""

    def _make_engine(self):
        return ThreatIntelligenceEngine(node_id="test-node")

    # --- report_indicator ---

    def test_report_new_indicator(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            ind = engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.99",
                threat_type=ThreatType.NETWORK_PROBE,
                severity=ThreatSeverity.LOW,
                confidence=0.5,
                description="Test probe",
            )

            assert ind.value == "10.0.0.99"
            assert ind.threat_type == ThreatType.NETWORK_PROBE
            assert ind.severity == ThreatSeverity.LOW
            assert ind.confidence == 0.5
            assert ind.first_seen == 5000.0
            assert ind.last_seen == 5000.0
            assert ind.reporter_id == "test-node"
            assert ind.corroborations == 0
            assert ind.id in engine.indicators

    def test_report_existing_indicator_increments_corroborations(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            ind1 = engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.50",
                threat_type=ThreatType.DPI_BLOCK,
                severity=ThreatSeverity.MEDIUM,
                confidence=0.6,
            )

            mock_time.time.return_value = 5100.0
            ind2 = engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.50",
                threat_type=ThreatType.DPI_BLOCK,
                severity=ThreatSeverity.MEDIUM,
                confidence=0.6,
            )

            assert ind2 is ind1
            assert ind2.corroborations == 1
            assert ind2.last_seen == 5100.0
            assert ind2.confidence == pytest.approx(0.7)

    def test_auto_block_high_severity_high_confidence(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            ind = engine.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value="evil-node",
                threat_type=ThreatType.SYBIL_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=0.85,
            )

            assert engine.is_blocked("evil-node") is True
            assert engine.reputation_scores["evil-node"] == 0.0

    def test_no_auto_block_below_confidence_threshold(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value="suspect-node",
                threat_type=ThreatType.SYBIL_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=0.7,  # below 0.8 threshold
            )

            assert engine.is_blocked("suspect-node") is False

    def test_no_auto_block_below_severity_threshold(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value="low-threat",
                threat_type=ThreatType.NETWORK_PROBE,
                severity=ThreatSeverity.MEDIUM,  # below HIGH
                confidence=0.9,
            )

            assert engine.is_blocked("low-threat") is False

    def test_auto_block_critical_severity(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value="critical-attacker",
                threat_type=ThreatType.MITM_ATTEMPT,
                severity=ThreatSeverity.CRITICAL,
                confidence=0.95,
            )

            assert engine.is_blocked("critical-attacker") is True

    # --- is_blocked ---

    def test_is_blocked_returns_false_for_unknown(self):
        engine = self._make_engine()
        assert engine.is_blocked("unknown-entity") is False

    # --- check_indicator via bloom filter ---

    def test_check_indicator_via_bloom_filter(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.77",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.LOW,
                confidence=0.5,
            )

            assert engine.check_indicator("10.0.0.77") is True
            assert engine.check_indicator("10.0.0.1") is False

    # --- get_indicator ---

    def test_get_indicator_returns_indicator_when_not_expired(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="172.16.0.1",
                threat_type=ThreatType.TRAFFIC_ANALYSIS,
                severity=ThreatSeverity.INFO,
                confidence=0.5,
                ttl=3600,
            )

            # Still within TTL
            mock_time.time.return_value = 5500.0
            result = engine.get_indicator("172.16.0.1")
            assert result is not None
            assert result.value == "172.16.0.1"

    def test_get_indicator_returns_none_when_expired(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="172.16.0.2",
                threat_type=ThreatType.TRAFFIC_ANALYSIS,
                severity=ThreatSeverity.INFO,
                confidence=0.5,
                ttl=100,
            )

            # Past TTL: first_seen(5000) + ttl(100) = 5100 < 6000
            mock_time.time.return_value = 6000.0
            result = engine.get_indicator("172.16.0.2")
            assert result is None

    def test_get_indicator_returns_none_for_unknown(self):
        engine = self._make_engine()
        assert engine.get_indicator("nonexistent") is None

    # --- detect_dos_attack ---

    def test_detect_dos_attack_under_threshold(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            # 50 connections -- well under the 100 threshold
            for _ in range(50):
                result = engine.detect_dos_attack("source-a")

            assert result is None

    def test_detect_dos_attack_over_threshold(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            # Send 101 connections to exceed the >100 threshold
            result = None
            for _ in range(101):
                result = engine.detect_dos_attack("source-b")

            assert result is not None
            assert result.threat_type == ThreatType.DOS_ATTACK
            assert result.severity == ThreatSeverity.HIGH
            assert result.value == "source-b"

    def test_detect_dos_attack_cleans_old_entries(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            # Add 80 connections at t=1000
            for _ in range(80):
                engine.detect_dos_attack("source-c")

            # Advance time beyond the 60s window
            mock_time.time.return_value = 1100.0

            # Add 30 more (should be the only ones in window now)
            result = None
            for _ in range(30):
                result = engine.detect_dos_attack("source-c")

            # 30 <= 100, so no detection
            assert result is None

    # --- detect_brute_force ---

    def test_detect_brute_force_under_threshold(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            # 9 attempts -- under the >=10 threshold
            result = None
            for _ in range(9):
                result = engine.detect_brute_force("attacker-1")

            assert result is None

    def test_detect_brute_force_at_threshold(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            # Exactly 10 attempts should trigger (>= 10)
            result = None
            for _ in range(10):
                result = engine.detect_brute_force("attacker-2")

            assert result is not None
            assert result.threat_type == ThreatType.CREDENTIAL_THEFT
            assert result.severity == ThreatSeverity.HIGH
            assert result.value == "attacker-2"
            assert result.confidence == pytest.approx(0.9)

    def test_detect_brute_force_cleans_old_entries(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            # 8 attempts at t=1000
            for _ in range(8):
                engine.detect_brute_force("attacker-3")

            # Jump past 300s window
            mock_time.time.return_value = 1400.0

            # 3 more attempts (only these remain in window)
            result = None
            for _ in range(3):
                result = engine.detect_brute_force("attacker-3")

            assert result is None

    # --- update_reputation ---

    def test_update_reputation_positive_delta(self):
        engine = self._make_engine()
        # Default reputation is 0.5
        new_score = engine.update_reputation("node-a", 0.3)
        assert new_score == pytest.approx(0.8)

    def test_update_reputation_negative_delta(self):
        engine = self._make_engine()
        new_score = engine.update_reputation("node-b", -0.2)
        assert new_score == pytest.approx(0.3)

    def test_update_reputation_clamps_at_zero(self):
        engine = self._make_engine()
        new_score = engine.update_reputation("node-c", -1.0)
        assert new_score == 0.0

    def test_update_reputation_clamps_at_one(self):
        engine = self._make_engine()
        new_score = engine.update_reputation("node-d", 1.0)
        assert new_score == 1.0

    def test_update_reputation_auto_blocks_below_threshold(self):
        engine = self._make_engine()
        # Default 0.5, subtract 0.45 => 0.05 < 0.1 => auto-block
        new_score = engine.update_reputation("shady-node", -0.45)
        assert new_score == pytest.approx(0.05)
        assert engine.is_blocked("shady-node") is True

    def test_update_reputation_no_block_at_threshold(self):
        engine = self._make_engine()
        # Default 0.5, subtract 0.39 => 0.11, NOT < 0.1 so no block
        new_score = engine.update_reputation("ok-node", -0.39)
        assert new_score == pytest.approx(0.11)
        assert engine.is_blocked("ok-node") is False

    # --- create_report ---

    def test_create_report(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            ind = engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.5",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=0.9,
            )

            report = engine.create_report(
                title="DoS Wave Report",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.HIGH,
                indicator_ids=[ind.id],
                affected_nodes=["node-1", "node-2"],
                mitigation="Rate limit source",
            )

            assert isinstance(report, ThreatReport)
            assert report.title == "DoS Wave Report"
            assert report.threat_type == ThreatType.DOS_ATTACK
            assert report.severity == ThreatSeverity.HIGH
            assert len(report.indicators) == 1
            assert report.indicators[0].id == ind.id
            assert report.affected_nodes == ["node-1", "node-2"]
            assert report.mitigation == "Rate limit source"
            assert report.id in engine.reports

    def test_create_report_with_missing_indicator_ids(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            report = engine.create_report(
                title="Empty Report",
                threat_type=ThreatType.NETWORK_PROBE,
                severity=ThreatSeverity.LOW,
                indicator_ids=["nonexistent-id"],
                affected_nodes=[],
                mitigation="N/A",
            )

            assert len(report.indicators) == 0

    def test_create_report_to_dict(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            report = engine.create_report(
                title="Test Report",
                threat_type=ThreatType.REPLAY_ATTACK,
                severity=ThreatSeverity.MEDIUM,
                indicator_ids=[],
                affected_nodes=["n1"],
                mitigation="Rotate keys",
            )

            d = report.to_dict()
            assert d["title"] == "Test Report"
            assert d["threat_type"] == "replay_attack"
            assert d["severity"] == 3
            assert d["affected_nodes"] == ["n1"]
            assert d["mitigation"] == "Rotate keys"

    # --- cleanup_expired ---

    def test_cleanup_expired_removes_expired_indicators(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.1",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.LOW,
                confidence=0.5,
                ttl=100,
            )
            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.2",
                threat_type=ThreatType.NETWORK_PROBE,
                severity=ThreatSeverity.LOW,
                confidence=0.5,
                ttl=5000,
            )

            assert len(engine.indicators) == 2

            # Advance time so first indicator expires but second doesn't
            mock_time.time.return_value = 1200.0
            removed = engine.cleanup_expired()

            assert removed == 1
            assert len(engine.indicators) == 1
            # The long-ttl indicator should still be present
            remaining = list(engine.indicators.values())[0]
            assert remaining.value == "10.0.0.2"

    def test_cleanup_expired_returns_zero_when_nothing_expired(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 1000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.1",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.LOW,
                confidence=0.5,
                ttl=9999,
            )

            removed = engine.cleanup_expired()
            assert removed == 0

    # --- get_stats ---

    def test_get_stats(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.1",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=0.9,
            )
            engine.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value="bad-node",
                threat_type=ThreatType.SYBIL_ATTACK,
                severity=ThreatSeverity.CRITICAL,
                confidence=0.95,
            )

            stats = engine.get_stats()

            assert stats["total_indicators"] == 2
            assert stats["blocked_entities"] == 2  # both auto-blocked
            assert stats["by_severity"]["HIGH"] == 1
            assert stats["by_severity"]["CRITICAL"] == 1
            assert stats["by_type"]["DOS_ATTACK"] == 1
            assert stats["by_type"]["SYBIL_ATTACK"] == 1
            assert stats["bloom_filter_size"] == 10000
            assert stats["reports"] == 0

    def test_get_stats_excludes_expired(self):
        with patch("src.security.threat_intelligence.time") as mock_time:
            mock_time.time.return_value = 5000.0
            engine = self._make_engine()

            engine.report_indicator(
                indicator_type=IndicatorType.IP_ADDRESS,
                value="10.0.0.1",
                threat_type=ThreatType.DOS_ATTACK,
                severity=ThreatSeverity.HIGH,
                confidence=0.5,
                ttl=100,
            )
            engine.report_indicator(
                indicator_type=IndicatorType.NODE_ID,
                value="node-x",
                threat_type=ThreatType.SYBIL_ATTACK,
                severity=ThreatSeverity.LOW,
                confidence=0.5,
                ttl=99999,
            )

            # Expire the first indicator
            mock_time.time.return_value = 5200.0
            stats = engine.get_stats()

            # Total still counts both (they're in the dict), but by_severity/by_type only counts non-expired
            assert stats["total_indicators"] == 2
            assert stats["by_severity"].get("HIGH", 0) == 0
            assert stats["by_severity"]["LOW"] == 1
            assert stats["by_type"].get("DOS_ATTACK", 0) == 0
            assert stats["by_type"]["SYBIL_ATTACK"] == 1

    def test_get_stats_empty_engine(self):
        engine = self._make_engine()
        stats = engine.get_stats()

        assert stats["total_indicators"] == 0
        assert stats["blocked_entities"] == 0
        assert stats["by_severity"] == {}
        assert stats["by_type"] == {}
        assert stats["reports"] == 0
