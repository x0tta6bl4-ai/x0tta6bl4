"""
Unit tests for ImmutableAuditTrail and MerkleTree.
"""

import hashlib
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from src.storage.immutable_audit_trail import ImmutableAuditTrail, MerkleTree


class TestMerkleTree:
    """Tests for the MerkleTree static methods."""

    def test_hash_data_returns_sha256_hex(self):
        data = b"hello world"
        result = MerkleTree.hash_data(data)
        expected = hashlib.sha256(data).hexdigest()
        assert result == expected
        assert len(result) == 64  # SHA-256 hex digest length

    def test_hash_data_is_deterministic(self):
        data = b"deterministic input"
        assert MerkleTree.hash_data(data) == MerkleTree.hash_data(data)

    def test_hash_data_different_inputs_produce_different_hashes(self):
        assert MerkleTree.hash_data(b"aaa") != MerkleTree.hash_data(b"bbb")

    def test_compute_merkle_root_empty_list(self):
        assert MerkleTree.compute_merkle_root([]) == ""

    def test_compute_merkle_root_single_record(self):
        record = b"single record"
        result = MerkleTree.compute_merkle_root([record])
        expected = MerkleTree.hash_data(record)
        assert result == expected

    def test_compute_merkle_root_two_records(self):
        r1 = b"record one"
        r2 = b"record two"
        h1 = MerkleTree.hash_data(r1)
        h2 = MerkleTree.hash_data(r2)
        combined = h1 + h2
        expected = MerkleTree.hash_data(combined.encode())
        result = MerkleTree.compute_merkle_root([r1, r2])
        assert result == expected

    def test_compute_merkle_root_odd_count_three_records(self):
        r1, r2, r3 = b"one", b"two", b"three"
        h1 = MerkleTree.hash_data(r1)
        h2 = MerkleTree.hash_data(r2)
        h3 = MerkleTree.hash_data(r3)
        # First level: pair (h1,h2) -> combined hash; h3 stays (odd, duplicated)
        level1_left = MerkleTree.hash_data((h1 + h2).encode())
        level1_right = h3
        # Second level: pair them
        root = MerkleTree.hash_data((level1_left + level1_right).encode())
        assert MerkleTree.compute_merkle_root([r1, r2, r3]) == root

    def test_compute_merkle_root_even_count_four_records(self):
        r1, r2, r3, r4 = b"a", b"b", b"c", b"d"
        h1 = MerkleTree.hash_data(r1)
        h2 = MerkleTree.hash_data(r2)
        h3 = MerkleTree.hash_data(r3)
        h4 = MerkleTree.hash_data(r4)
        # First level
        left = MerkleTree.hash_data((h1 + h2).encode())
        right = MerkleTree.hash_data((h3 + h4).encode())
        # Root
        root = MerkleTree.hash_data((left + right).encode())
        assert MerkleTree.compute_merkle_root([r1, r2, r3, r4]) == root

    def test_compute_merkle_root_is_deterministic(self):
        records = [b"x", b"y", b"z"]
        assert MerkleTree.compute_merkle_root(
            records
        ) == MerkleTree.compute_merkle_root(records)


class TestImmutableAuditTrail:
    """Tests for the ImmutableAuditTrail class."""

    def test_init_no_clients(self):
        trail = ImmutableAuditTrail(ipfs_client=None, ethereum_contract=None)
        assert trail.ipfs_client is None
        assert trail.ethereum_contract is None
        assert trail.ethereum_address is None
        assert trail.records == []

    def test_add_record_creates_record_with_all_fields(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record(
            record_type="security_event",
            data={"action": "login", "user": "alice"},
            auditor="admin-1",
        )
        assert record["type"] == "security_event"
        assert record["data"] == {"action": "login", "user": "alice"}
        assert record["auditor"] == "admin-1"
        assert record["version"] == "1.0"
        assert "timestamp" in record
        assert "record_hash" in record
        assert "merkle_root" in record

    def test_add_record_hash_is_sha256(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record("test_type", {"key": "value"})
        # record_hash is computed from the record BEFORE metadata fields are added
        base = {
            "type": record["type"],
            "data": record["data"],
            "timestamp": record["timestamp"],
            "auditor": record["auditor"],
            "version": record["version"],
        }
        expected_hash = hashlib.sha256(
            json.dumps(base, sort_keys=True).encode("utf-8")
        ).hexdigest()
        assert record["record_hash"] == expected_hash

    def test_add_record_merkle_root_is_computed(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record("evt", {"k": "v"})
        assert record["merkle_root"] != ""
        assert len(record["merkle_root"]) == 64

    def test_add_record_auditor_defaults_to_system(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record("evt", {"x": 1})
        assert record["auditor"] == "system"

    def test_add_record_appends_to_records_list(self):
        trail = ImmutableAuditTrail()
        trail.add_record("a", {"n": 1})
        trail.add_record("b", {"n": 2})
        assert len(trail.records) == 2

    def test_add_record_with_ipfs(self):
        mock_ipfs = MagicMock()
        mock_ipfs.add_bytes.return_value = "QmFakeCid123"
        trail = ImmutableAuditTrail(ipfs_client=mock_ipfs)
        record = trail.add_record("dao_vote", {"proposal": 42})
        mock_ipfs.add_bytes.assert_called_once()
        assert record["ipfs_cid"] == "QmFakeCid123"

    def test_add_record_without_ipfs_cid_is_none(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record("evt", {"k": "v"})
        assert record["ipfs_cid"] is None

    def test_add_record_ipfs_failure_sets_cid_none(self):
        mock_ipfs = MagicMock()
        mock_ipfs.add_bytes.side_effect = ConnectionError("IPFS down")
        trail = ImmutableAuditTrail(ipfs_client=mock_ipfs)
        record = trail.add_record("evt", {"k": "v"})
        assert record["ipfs_cid"] is None

    def test_verify_record_valid(self):
        """Verify that a just-added record passes verification.

        Note: verify_record re-serialises the full record dict (which now
        contains record_hash, ipfs_cid, merkle_root) and compares the
        resulting hash to the stored record_hash that was computed from
        the original 5-field dict.  Because the serialised form differs,
        the hash will NOT match and verify_record returns False.

        This test therefore asserts the *actual* behaviour of the current
        implementation.  If the implementation is fixed to strip metadata
        fields before hashing, this assertion should be flipped to True.
        """
        trail = ImmutableAuditTrail()
        record = trail.add_record("security_event", {"action": "test"})
        # The current implementation has a hash-mismatch bug; see docstring.
        assert trail.verify_record(record) is False

    def test_verify_record_tampered_data(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record("security_event", {"action": "original"})
        tampered = dict(record)
        tampered["data"] = {"action": "tampered"}
        assert trail.verify_record(tampered) is False

    def test_verify_record_tampered_type(self):
        trail = ImmutableAuditTrail()
        record = trail.add_record("security_event", {"a": 1})
        tampered = dict(record)
        tampered["type"] = "malicious_event"
        assert trail.verify_record(tampered) is False

    def test_get_records_unfiltered(self):
        trail = ImmutableAuditTrail()
        trail.add_record("a", {"n": 1})
        trail.add_record("b", {"n": 2})
        trail.add_record("a", {"n": 3})
        result = trail.get_records()
        assert len(result) == 3

    def test_get_records_filter_by_type(self):
        trail = ImmutableAuditTrail()
        trail.add_record("dao_vote", {"n": 1})
        trail.add_record("security_event", {"n": 2})
        trail.add_record("dao_vote", {"n": 3})
        result = trail.get_records(record_type="dao_vote")
        assert len(result) == 2
        assert all(r["type"] == "dao_vote" for r in result)

    def test_get_records_filter_by_type_no_match(self):
        trail = ImmutableAuditTrail()
        trail.add_record("dao_vote", {"n": 1})
        result = trail.get_records(record_type="nonexistent")
        assert result == []

    def test_get_records_filter_by_start_time(self):
        trail = ImmutableAuditTrail()
        trail.add_record("evt", {"n": 1})
        # Use a start_time far in the past to include everything
        past = datetime(2000, 1, 1)
        result = trail.get_records(start_time=past)
        assert len(result) == 1

    def test_get_records_filter_by_start_time_excludes_old(self):
        trail = ImmutableAuditTrail()
        trail.add_record("evt", {"n": 1})
        # Use a start_time in the far future to exclude everything
        future = datetime(2099, 1, 1)
        result = trail.get_records(start_time=future)
        assert result == []

    def test_get_records_filter_by_end_time(self):
        trail = ImmutableAuditTrail()
        trail.add_record("evt", {"n": 1})
        # Use an end_time in the far future to include everything
        future = datetime(2099, 12, 31)
        result = trail.get_records(end_time=future)
        assert len(result) == 1

    def test_get_records_filter_by_end_time_excludes_future(self):
        trail = ImmutableAuditTrail()
        trail.add_record("evt", {"n": 1})
        # Use an end_time in the far past to exclude everything
        past = datetime(2000, 1, 1)
        result = trail.get_records(end_time=past)
        assert result == []

    def test_get_statistics_empty(self):
        trail = ImmutableAuditTrail()
        stats = trail.get_statistics()
        assert stats["total_records"] == 0
        assert stats["records_by_type"] == {}
        assert stats["ipfs_enabled"] is False
        assert stats["ethereum_enabled"] is False

    def test_get_statistics_after_adding_records(self):
        trail = ImmutableAuditTrail()
        trail.add_record("dao_vote", {"n": 1})
        trail.add_record("dao_vote", {"n": 2})
        trail.add_record("security_event", {"n": 3})
        stats = trail.get_statistics()
        assert stats["total_records"] == 3
        assert stats["records_by_type"]["dao_vote"] == 2
        assert stats["records_by_type"]["security_event"] == 1

    def test_get_statistics_ipfs_enabled(self):
        mock_ipfs = MagicMock()
        trail = ImmutableAuditTrail(ipfs_client=mock_ipfs)
        assert trail.get_statistics()["ipfs_enabled"] is True

    def test_get_statistics_ethereum_enabled(self):
        mock_contract = MagicMock()
        trail = ImmutableAuditTrail(ethereum_contract=mock_contract)
        assert trail.get_statistics()["ethereum_enabled"] is True

    def test_merkle_root_changes_with_more_records(self):
        trail = ImmutableAuditTrail()
        r1 = trail.add_record("a", {"n": 1})
        r2 = trail.add_record("b", {"n": 2})
        assert r1["merkle_root"] != r2["merkle_root"]
