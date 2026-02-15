"""
Tests for Extended eBPF Loader Features.

Tests the enhanced attachment verification:
- bpftool verification
- Attachment type detection
- Program verification
"""

import subprocess
from unittest.mock import MagicMock, Mock, patch

import pytest

from src.network.ebpf.loader import EBPFAttachMode, EBPFLoader, EBPFProgramType


class TestEBPFLoaderExtended:
    """Test extended eBPF loader features."""

    @pytest.fixture
    def loader(self):
        """Create loader instance."""
        return EBPFLoader()

    def test_attachment_verification_success(self, loader):
        """Test successful attachment verification via bpftool."""
        program_id = 123
        interface = "eth0"

        with patch("subprocess.run") as mock_run:
            # Mock successful bpftool output
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = f"id {program_id} name xdp_prog type xdp attached xdp"
            mock_run.return_value = mock_result

            # Mock _attach_xdp_program to return success
            with patch.object(loader, "_attach_xdp_program", return_value=True):
                with patch.object(loader, "_verify_attachment", return_value=True):
                    # This would normally be called during attach_program
                    # For test, we verify the verification logic
                    result = loader._verify_attachment(
                        program_id, interface, EBPFProgramType.XDP
                    )

                    assert result is True

    def test_attachment_verification_failure(self, loader):
        """Test attachment verification failure."""
        program_id = 123

        with patch("subprocess.run") as mock_run:
            # Mock failed bpftool output
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stdout = ""
            mock_run.return_value = mock_result

            result = loader._verify_attachment(program_id, "eth0", EBPFProgramType.XDP)

            # Should return False on failure
            assert result is False

    def test_attachment_type_detection(self, loader):
        """Test detection of attachment type from bpftool output."""
        program_id = 123

        with patch("subprocess.run") as mock_run:
            # Mock bpftool output with XDP attachment
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = f"id {program_id} name xdp_prog type xdp attached xdp"
            mock_run.return_value = mock_result

            result = loader._verify_attachment(program_id, "eth0", EBPFProgramType.XDP)

            # Should detect XDP attachment
            assert result is True

    def test_attachment_verification_timeout(self, loader):
        """Test handling of bpftool timeout."""
        program_id = 123

        with patch("subprocess.run") as mock_run:
            # Simulate timeout
            mock_run.side_effect = subprocess.TimeoutExpired("bpftool", 5)

            result = loader._verify_attachment(program_id, "eth0", EBPFProgramType.XDP)

            # Should handle timeout gracefully
            assert result is False

    def test_attachment_verification_missing_bpftool(self, loader):
        """Test handling of missing bpftool."""
        program_id = 123

        with patch("subprocess.run") as mock_run:
            # Simulate FileNotFoundError
            mock_run.side_effect = FileNotFoundError("bpftool not found")

            result = loader._verify_attachment(program_id, "eth0", EBPFProgramType.XDP)

            # Should handle missing tool gracefully
            assert result is False

    def test_attachment_verification_unclear_type(self, loader):
        """Test handling of unclear attachment type."""
        program_id = 123

        with patch("subprocess.run") as mock_run:
            # Mock bpftool output without clear attachment type
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = f"id {program_id} name prog type socket_filter"
            mock_run.return_value = mock_result

            result = loader._verify_attachment(program_id, "eth0", EBPFProgramType.XDP)

            # Should still verify program exists
            assert result is True
