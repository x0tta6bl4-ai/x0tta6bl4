"""
Unit tests for PQC Rotation Formal Logic and Safe Handover.
"""

import unittest
import asyncio
from pathlib import Path
from src.services.pqc_rotator_service import PQCRotatorService
from src.services.pqc_logic_contract import PQCFormalState

class MockProcess:
    def __init__(self, returncode=0):
        self.returncode = returncode
    async def wait(self):
        return self.returncode

class TestPQCFormalRotation(unittest.TestCase):
    def setUp(self):
        self.identity_file = Path(".tmp/test_pqc_identity.txt")
        self.service = PQCRotatorService(
            identity_file=self.identity_file,
            rotation_interval=60,
            report_generator=lambda: None
        )
        # Mock process factory to simulate PQC key generation
        async def mock_factory(*args, **kwargs):
            self.service.temp_identity_file.write_text("mock-pqc-key")
            return MockProcess()
        self.service.process_factory = mock_factory

    def tearDown(self):
        self.identity_file.unlink(missing_ok=True)
        self.service.temp_identity_file.unlink(missing_ok=True)

    def test_formal_rotation_flow(self):
        """Test a successful rotation follows the STABLE -> ... -> STABLE sequence."""
        async def run():
            result = await self.service.rotate_once()
            if not result["success"]:
                print(f"Rotation failed: {result.get('error')}")
                print(f"Violations: {self.service.logic_contract.violations}")
            self.assertTrue(result["success"])
            self.assertEqual(self.service.logic_contract.current_state, PQCFormalState.STABLE)
            self.assertEqual(len(self.service.logic_contract.violations), 0)

        asyncio.run(run())

    def test_invariant_t1_safe_handover_violation(self):
        """Test T1: Commitment blocked if staged keys are missing."""
        async def run():
            # Mock process factory to DELETE the file created by 'open'
            async def deleting_factory(*args, **kwargs):
                self.service.temp_identity_file.unlink(missing_ok=True)
                return MockProcess()
            self.service.process_factory = deleting_factory

            # This should fail at VERIFYING because file doesn't exist
            result = await self.service.rotate_once()

            self.assertFalse(result["success"])
            self.assertEqual(self.service.logic_contract.current_state, PQCFormalState.TRUST_FAILURE)
            self.assertTrue(any("T1" in v for v in self.service.logic_contract.violations))

        asyncio.run(run())

    def test_invariant_t3_unauthorized_algorithm(self):
        """Test T3: Rotation blocked if unauthorized algorithm is used."""
        async def run():
            # Set an unauthorized algorithm in signer_cmd
            self.service.signer_cmd = ("python3", "signer.py", "--algorithm", "ROT13")

            result = await self.service.rotate_once()

            self.assertFalse(result["success"])
            self.assertEqual(self.service.logic_contract.current_state, PQCFormalState.TRUST_FAILURE)
            self.assertTrue(any("T3" in v for v in self.service.logic_contract.violations))

        asyncio.run(run())

if __name__ == "__main__":
    unittest.main()
