"""Unit tests for src.security.device_attestation module."""

import time
from unittest.mock import MagicMock, patch

import pytest

from src.security.device_attestation import (AdaptiveTrustManager,
                                             AttestationClaim, AttestationType,
                                             DeviceAttestor, DeviceFingerprint,
                                             MeshDeviceAttestor, TrustLevel,
                                             TrustScore)


class TestTrustScoreUpdate:
    """Tests for TrustScore.update() weighted average and level transitions."""

    def _make_score(self, score=0.5, level=TrustLevel.MEDIUM):
        return TrustScore(
            device_id="dev-1",
            score=score,
            level=level,
            factors={},
            last_updated=1000.0,
        )

    @patch("src.security.device_attestation.time")
    def test_weighted_average_formula(self, mock_time):
        mock_time.time.return_value = 2000.0
        ts = self._make_score(score=0.5)
        ts.update(1.0)
        # 0.7 * 1.0 + 0.3 * 0.5 = 0.85
        assert ts.score == pytest.approx(0.85)

    @patch("src.security.device_attestation.time")
    def test_weighted_average_low_new_score(self, mock_time):
        mock_time.time.return_value = 2000.0
        ts = self._make_score(score=0.8)
        ts.update(0.0)
        # 0.7 * 0.0 + 0.3 * 0.8 = 0.24
        assert ts.score == pytest.approx(0.24)

    @patch("src.security.device_attestation.time")
    def test_update_appends_old_score_to_history(self, mock_time):
        mock_time.time.return_value = 2000.0
        ts = self._make_score(score=0.6)
        ts.update(0.8)
        assert ts.history == [0.6]

    @patch("src.security.device_attestation.time")
    def test_history_capped_at_100(self, mock_time):
        mock_time.time.return_value = 2000.0
        ts = self._make_score(score=0.5)
        ts.history = list(range(100))
        ts.update(0.5)
        assert len(ts.history) == 100
        # oldest entry (0) should have been popped, replaced by 0.5
        assert ts.history[0] == 1

    @patch("src.security.device_attestation.time")
    def test_update_sets_last_updated(self, mock_time):
        mock_time.time.return_value = 9999.0
        ts = self._make_score()
        ts.update(0.5)
        assert ts.last_updated == 9999.0

    @patch("src.security.device_attestation.time")
    def test_level_transition_to_verified(self, mock_time):
        mock_time.time.return_value = 2000.0
        ts = self._make_score(score=0.9)
        ts.update(1.0)
        # 0.7 * 1.0 + 0.3 * 0.9 = 0.97
        assert ts.level == TrustLevel.VERIFIED

    @patch("src.security.device_attestation.time")
    def test_level_transition_to_untrusted(self, mock_time):
        mock_time.time.return_value = 2000.0
        ts = self._make_score(score=0.2)
        ts.update(0.0)
        # 0.7 * 0.0 + 0.3 * 0.2 = 0.06
        assert ts.level == TrustLevel.UNTRUSTED


class TestTrustScoreCalculateLevel:
    """Tests for TrustScore._calculate_level() threshold boundaries."""

    def _make_score(self, score):
        ts = TrustScore(
            device_id="dev-1",
            score=score,
            level=TrustLevel.MEDIUM,
            factors={},
            last_updated=0.0,
        )
        return ts

    def test_verified_at_0_9(self):
        ts = self._make_score(0.9)
        assert ts._calculate_level() == TrustLevel.VERIFIED

    def test_verified_at_1_0(self):
        ts = self._make_score(1.0)
        assert ts._calculate_level() == TrustLevel.VERIFIED

    def test_high_at_0_7(self):
        ts = self._make_score(0.7)
        assert ts._calculate_level() == TrustLevel.HIGH

    def test_high_at_0_89(self):
        ts = self._make_score(0.89)
        assert ts._calculate_level() == TrustLevel.HIGH

    def test_medium_at_0_5(self):
        ts = self._make_score(0.5)
        assert ts._calculate_level() == TrustLevel.MEDIUM

    def test_medium_at_0_69(self):
        ts = self._make_score(0.69)
        assert ts._calculate_level() == TrustLevel.MEDIUM

    def test_low_at_0_3(self):
        ts = self._make_score(0.3)
        assert ts._calculate_level() == TrustLevel.LOW

    def test_low_at_0_49(self):
        ts = self._make_score(0.49)
        assert ts._calculate_level() == TrustLevel.LOW

    def test_untrusted_at_0_29(self):
        ts = self._make_score(0.29)
        assert ts._calculate_level() == TrustLevel.UNTRUSTED

    def test_untrusted_at_0(self):
        ts = self._make_score(0.0)
        assert ts._calculate_level() == TrustLevel.UNTRUSTED


class TestDeviceFingerprintToDict:
    """Tests for DeviceFingerprint.to_dict()."""

    def test_to_dict_returns_all_fields(self):
        fp = DeviceFingerprint(
            fingerprint_hash="abc123",
            platform_type="linux",
            arch_type="x86_64",
            attestation_time=1000.0,
            nonce="nonce123",
        )
        d = fp.to_dict()
        assert d == {
            "fingerprint_hash": "abc123",
            "platform_type": "linux",
            "arch_type": "x86_64",
            "attestation_time": 1000.0,
            "nonce": "nonce123",
        }


class TestDeviceAttestorCreateFingerprint:
    """Tests for DeviceAttestor.create_fingerprint()."""

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_returns_valid_fingerprint(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "Intel(R) Core(TM)"
        mock_time.time.return_value = 5000.0

        attestor = DeviceAttestor(secret_salt="test-salt")
        fp = attestor.create_fingerprint()

        assert isinstance(fp, DeviceFingerprint)
        assert fp.platform_type == "linux"
        assert fp.arch_type == "x86_64"
        assert fp.attestation_time == 5000.0
        assert len(fp.nonce) == 32  # token_hex(16) = 32 hex chars
        assert len(fp.fingerprint_hash) == 64  # SHA-256 hex digest

    @patch("src.security.device_attestation.platform")
    def test_fingerprint_hash_is_deterministic_for_same_characteristics(
        self, mock_platform
    ):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "amd processor"

        attestor = DeviceAttestor(secret_salt="fixed-salt")
        fp1 = attestor.create_fingerprint()
        fp2 = attestor.create_fingerprint()
        # Same salt + same characteristics = same hash
        assert fp1.fingerprint_hash == fp2.fingerprint_hash
        # But nonces differ
        assert fp1.nonce != fp2.nonce

    @patch("src.security.device_attestation.platform")
    def test_different_salt_produces_different_hash(self, mock_platform):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "unknown cpu"

        fp1 = DeviceAttestor(secret_salt="salt-a").create_fingerprint()
        fp2 = DeviceAttestor(secret_salt="salt-b").create_fingerprint()
        assert fp1.fingerprint_hash != fp2.fingerprint_hash


class TestDeviceAttestorAnonymizeProcessor:
    """Tests for DeviceAttestor._anonymize_processor()."""

    @patch("src.security.device_attestation.platform")
    def test_intel_detected(self, mock_platform):
        mock_platform.processor.return_value = "Intel(R) Core(TM) i7-9750H"
        attestor = DeviceAttestor(secret_salt="s")
        assert attestor._anonymize_processor() == "intel"

    @patch("src.security.device_attestation.platform")
    def test_amd_detected(self, mock_platform):
        mock_platform.processor.return_value = "AMD Ryzen 9 5900X"
        attestor = DeviceAttestor(secret_salt="s")
        assert attestor._anonymize_processor() == "amd"

    @patch("src.security.device_attestation.platform")
    def test_arm_detected(self, mock_platform):
        mock_platform.processor.return_value = "ARMv8 Processor rev 1"
        attestor = DeviceAttestor(secret_salt="s")
        assert attestor._anonymize_processor() == "arm"

    @patch("src.security.device_attestation.platform")
    def test_unknown_processor(self, mock_platform):
        mock_platform.processor.return_value = "RISC-V"
        attestor = DeviceAttestor(secret_salt="s")
        assert attestor._anonymize_processor() == "unknown"


class TestDeviceAttestorCreateAttestation:
    """Tests for DeviceAttestor.create_attestation()."""

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_returns_attestation_claim(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        attestor = DeviceAttestor(secret_salt="test-salt")
        claim = attestor.create_attestation()

        assert isinstance(claim, AttestationClaim)
        assert claim.attestation_type == AttestationType.COMPOSITE
        assert claim.timestamp == 5000.0
        assert len(claim.signature) == 64
        assert len(claim.claim_id) == 16

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_composite_includes_all_evidence(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        attestor = DeviceAttestor(secret_salt="test-salt")
        claim = attestor.create_attestation(AttestationType.COMPOSITE)

        assert "hardware" in claim.evidence
        assert "software" in claim.evidence
        assert "network" in claim.evidence

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_hardware_only_attestation(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_time.time.return_value = 5000.0

        attestor = DeviceAttestor(secret_salt="test-salt")
        claim = attestor.create_attestation(AttestationType.HARDWARE)

        assert "hardware" in claim.evidence
        assert "software" not in claim.evidence
        assert "network" not in claim.evidence

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_claim_has_valid_fingerprint(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Darwin"
        mock_platform.machine.return_value = "arm64"
        mock_platform.python_version.return_value = "3.11.0"
        mock_platform.processor.return_value = "arm"
        mock_platform.architecture.return_value = ("64bit", "")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "11", "0")
        mock_time.time.return_value = 5000.0

        attestor = DeviceAttestor(secret_salt="test-salt")
        claim = attestor.create_attestation()

        assert claim.device_fingerprint.platform_type == "darwin"
        assert claim.device_fingerprint.arch_type == "arm64"


class TestDeviceAttestorVerifyAttestation:
    """Tests for DeviceAttestor.verify_attestation()."""

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def _create_valid_claim(
        self, mock_platform, mock_time, salt="test-salt", ts=5000.0
    ):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = ts

        attestor = DeviceAttestor(secret_salt=salt)
        claim = attestor.create_attestation()
        return attestor, claim

    def test_valid_claim_returns_true(self):
        attestor, claim = self._create_valid_claim()
        with patch("src.security.device_attestation.time") as mock_time:
            mock_time.time.return_value = claim.timestamp + 60  # within 5 min
            valid, reason = attestor.verify_attestation(claim)
        assert valid is True
        assert reason == "Valid"

    def test_tampered_signature_fails(self):
        attestor, claim = self._create_valid_claim()
        claim.signature = "a" * 64  # tampered
        with patch("src.security.device_attestation.time") as mock_time:
            mock_time.time.return_value = claim.timestamp + 60
            valid, reason = attestor.verify_attestation(claim)
        assert valid is False
        assert reason == "Invalid signature"

    def test_tampered_claim_id_fails(self):
        attestor, claim = self._create_valid_claim()
        claim.claim_id = "tampered_id_1234"
        with patch("src.security.device_attestation.time") as mock_time:
            mock_time.time.return_value = claim.timestamp + 60
            valid, reason = attestor.verify_attestation(claim)
        assert valid is False
        assert reason == "Invalid signature"

    def test_expired_claim_fails(self):
        attestor, claim = self._create_valid_claim()
        with patch("src.security.device_attestation.time") as mock_time:
            # More than 300 seconds after claim.timestamp
            mock_time.time.return_value = claim.timestamp + 301
            valid, reason = attestor.verify_attestation(claim)
        assert valid is False
        assert reason == "Attestation expired"

    def test_claim_exactly_at_300s_is_valid(self):
        attestor, claim = self._create_valid_claim()
        with patch("src.security.device_attestation.time") as mock_time:
            mock_time.time.return_value = claim.timestamp + 300
            valid, reason = attestor.verify_attestation(claim)
        assert valid is True
        assert reason == "Valid"

    def test_different_attestor_key_rejects(self):
        attestor, claim = self._create_valid_claim()
        other_attestor = DeviceAttestor(secret_salt="different-salt")
        with patch("src.security.device_attestation.time") as mock_time:
            mock_time.time.return_value = claim.timestamp + 60
            valid, reason = other_attestor.verify_attestation(claim)
        assert valid is False
        assert reason == "Invalid signature"


class TestAdaptiveTrustManager:
    """Tests for AdaptiveTrustManager."""

    def test_get_trust_score_creates_new_with_0_5(self):
        manager = AdaptiveTrustManager()
        score = manager.get_trust_score("new-device")
        assert score.score == 0.5
        assert score.level == TrustLevel.MEDIUM
        assert score.device_id == "new-device"
        assert score.factors == {}

    def test_get_trust_score_returns_same_instance(self):
        manager = AdaptiveTrustManager()
        s1 = manager.get_trust_score("dev-1")
        s2 = manager.get_trust_score("dev-1")
        assert s1 is s2

    @patch("src.security.device_attestation.time")
    def test_evaluate_trust_updates_score(self, mock_time):
        mock_time.time.return_value = 1000.0
        manager = AdaptiveTrustManager()
        score = manager.evaluate_trust("dev-1")
        # Score should have been updated from initial 0.5
        assert score.device_id == "dev-1"
        assert "attestation" in score.factors
        assert "behavior" in score.factors
        assert "history" in score.factors
        assert "network" in score.factors
        assert "time" in score.factors

    @patch("src.security.device_attestation.time")
    def test_evaluate_trust_with_valid_attestation(self, mock_time):
        mock_time.time.return_value = 1000.0
        manager = AdaptiveTrustManager()
        # Create a valid claim using manager's internal attestor
        attestor = manager._attestor
        with patch("src.security.device_attestation.platform") as mock_plat:
            mock_plat.system.return_value = "Linux"
            mock_plat.machine.return_value = "x86_64"
            mock_plat.python_version.return_value = "3.12.0"
            mock_plat.processor.return_value = "intel"
            mock_plat.architecture.return_value = ("64bit", "ELF")
            mock_plat.python_implementation.return_value = "CPython"
            mock_plat.python_version_tuple.return_value = ("3", "12", "0")
            claim = attestor.create_attestation()

        score = manager.evaluate_trust("dev-1", attestation=claim)
        assert score.factors["attestation"] == 1.0

    @patch("src.security.device_attestation.time")
    def test_record_positive_event(self, mock_time):
        mock_time.time.return_value = 1000.0
        manager = AdaptiveTrustManager()
        manager.record_positive_event("dev-1", "login_success")
        events = manager._behavioral_data["dev-1"]
        assert len(events) == 1
        assert events[0]["type"] == "positive"
        assert events[0]["event"] == "login_success"

    @patch("src.security.device_attestation.time")
    def test_record_negative_event(self, mock_time):
        mock_time.time.return_value = 1000.0
        manager = AdaptiveTrustManager()
        manager.record_negative_event("dev-1", "auth_fail")
        events = manager._behavioral_data["dev-1"]
        assert len(events) == 1
        assert events[0]["type"] == "negative"
        assert events[0]["event"] == "auth_fail"

    def test_is_trusted_new_device_at_medium(self):
        manager = AdaptiveTrustManager()
        # New device starts at MEDIUM (0.5)
        assert manager.is_trusted("new-dev", TrustLevel.MEDIUM) is True
        assert manager.is_trusted("new-dev", TrustLevel.LOW) is True
        assert manager.is_trusted("new-dev", TrustLevel.UNTRUSTED) is True
        assert manager.is_trusted("new-dev", TrustLevel.HIGH) is False
        assert manager.is_trusted("new-dev", TrustLevel.VERIFIED) is False

    def test_is_trusted_checks_level_value(self):
        manager = AdaptiveTrustManager()
        score = manager.get_trust_score("dev-1")
        score.level = TrustLevel.HIGH
        assert manager.is_trusted("dev-1", TrustLevel.HIGH) is True
        assert manager.is_trusted("dev-1", TrustLevel.MEDIUM) is True
        assert manager.is_trusted("dev-1", TrustLevel.VERIFIED) is False

    def test_get_all_scores_returns_copy(self):
        manager = AdaptiveTrustManager()
        manager.get_trust_score("dev-1")
        manager.get_trust_score("dev-2")
        all_scores = manager.get_all_scores()
        assert len(all_scores) == 2
        assert "dev-1" in all_scores
        assert "dev-2" in all_scores
        # It's a copy
        all_scores["dev-3"] = None
        assert "dev-3" not in manager._device_scores

    @patch("src.security.device_attestation.time")
    def test_evaluate_trust_with_network_context(self, mock_time):
        mock_time.time.return_value = 1000.0
        manager = AdaptiveTrustManager()
        context = {"known_network": True, "encrypted": True}
        score = manager.evaluate_trust("dev-1", network_context=context)
        # known_network (+0.2) + encrypted (+0.15) + base 0.5 = 0.85
        assert score.factors["network"] == pytest.approx(0.85)

    @patch("src.security.device_attestation.time")
    def test_evaluate_trust_with_suspicious_network(self, mock_time):
        mock_time.time.return_value = 1000.0
        manager = AdaptiveTrustManager()
        context = {"suspicious_patterns": True}
        score = manager.evaluate_trust("dev-1", network_context=context)
        # base 0.5 - 0.3 = 0.2
        assert score.factors["network"] == pytest.approx(0.2)

    @patch("src.security.device_attestation.time")
    def test_time_factor_recent(self, mock_time):
        manager = AdaptiveTrustManager()
        mock_time.time.return_value = 1000.0
        ts = manager.get_trust_score("dev-1")
        ts.last_updated = 999.0  # less than 1 hour ago
        factor = manager._calculate_time_factor(ts)
        assert factor == 1.0

    @patch("src.security.device_attestation.time")
    def test_time_factor_day_old(self, mock_time):
        manager = AdaptiveTrustManager()
        mock_time.time.return_value = 100000.0
        ts = manager.get_trust_score("dev-1")
        ts.last_updated = 100000.0 - 3600 * 12  # 12 hours ago
        factor = manager._calculate_time_factor(ts)
        assert factor == 0.9

    @patch("src.security.device_attestation.time")
    def test_time_factor_week_old(self, mock_time):
        manager = AdaptiveTrustManager()
        mock_time.time.return_value = 1000000.0
        ts = manager.get_trust_score("dev-1")
        ts.last_updated = 1000000.0 - 3600 * 48  # 48 hours ago
        factor = manager._calculate_time_factor(ts)
        assert factor == 0.7

    @patch("src.security.device_attestation.time")
    def test_time_factor_very_old(self, mock_time):
        manager = AdaptiveTrustManager()
        mock_time.time.return_value = 10000000.0
        ts = manager.get_trust_score("dev-1")
        ts.last_updated = 0.0  # very old
        factor = manager._calculate_time_factor(ts)
        assert factor == 0.5


class TestMeshDeviceAttestor:
    """Tests for MeshDeviceAttestor."""

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_create_mesh_attestation_format(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        mesh_attestor = MeshDeviceAttestor(node_id="node-alpha")
        result = mesh_attestor.create_mesh_attestation()

        assert result["type"] == "mesh_attestation"
        assert result["node_id"] == "node-alpha"
        assert "claim" in result
        claim = result["claim"]
        assert "claim_id" in claim
        assert "fingerprint" in claim
        assert "evidence" in claim
        assert "timestamp" in claim
        assert "signature" in claim
        # fingerprint should be a dict (from to_dict)
        assert isinstance(claim["fingerprint"], dict)
        assert claim["fingerprint"]["platform_type"] == "linux"

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_verify_peer_attestation_round_trip(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        mesh_attestor = MeshDeviceAttestor(node_id="node-alpha")
        attestation_data = mesh_attestor.create_mesh_attestation()

        # Verify the attestation created by the same node
        valid, trust_score = mesh_attestor.verify_peer_attestation(attestation_data)
        assert valid is True
        assert isinstance(trust_score, TrustScore)
        assert trust_score.device_id == "node-alpha"

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_verify_peer_attestation_tampered_signature(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        mesh_attestor = MeshDeviceAttestor(node_id="node-alpha")
        attestation_data = mesh_attestor.create_mesh_attestation()
        attestation_data["claim"]["signature"] = "f" * 64  # tamper

        valid, trust_score = mesh_attestor.verify_peer_attestation(attestation_data)
        assert valid is False

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_verify_peer_attestation_records_positive_event(
        self, mock_platform, mock_time
    ):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        mesh_attestor = MeshDeviceAttestor(node_id="node-alpha")
        attestation_data = mesh_attestor.create_mesh_attestation()

        mesh_attestor.verify_peer_attestation(attestation_data)

        events = mesh_attestor.trust_manager._behavioral_data.get("node-alpha", [])
        positive = [e for e in events if e["type"] == "positive"]
        assert len(positive) == 1
        assert positive[0]["event"] == "attestation_valid"

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_verify_peer_attestation_records_negative_event(
        self, mock_platform, mock_time
    ):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        mesh_attestor = MeshDeviceAttestor(node_id="node-alpha")
        attestation_data = mesh_attestor.create_mesh_attestation()
        attestation_data["claim"]["signature"] = "0" * 64  # tamper

        mesh_attestor.verify_peer_attestation(attestation_data)

        events = mesh_attestor.trust_manager._behavioral_data.get("node-alpha", [])
        negative = [e for e in events if e["type"] == "negative"]
        assert len(negative) == 1
        assert "attestation_invalid" in negative[0]["event"]

    @patch("src.security.device_attestation.time")
    @patch("src.security.device_attestation.platform")
    def test_verify_peer_attestation_unknown_node_id(self, mock_platform, mock_time):
        mock_platform.system.return_value = "Linux"
        mock_platform.machine.return_value = "x86_64"
        mock_platform.python_version.return_value = "3.12.0"
        mock_platform.processor.return_value = "intel"
        mock_platform.architecture.return_value = ("64bit", "ELF")
        mock_platform.python_implementation.return_value = "CPython"
        mock_platform.python_version_tuple.return_value = ("3", "12", "0")
        mock_time.time.return_value = 5000.0

        mesh_attestor = MeshDeviceAttestor(node_id="node-alpha")
        attestation_data = mesh_attestor.create_mesh_attestation()
        # Remove node_id to test fallback
        del attestation_data["node_id"]

        valid, trust_score = mesh_attestor.verify_peer_attestation(attestation_data)
        assert trust_score.device_id == "unknown"
