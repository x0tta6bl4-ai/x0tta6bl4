import asyncio
import unittest
from unittest.mock import MagicMock, patch
import os
import sys

# Add current directory to sys.path
if "." not in sys.path:
    sys.path.append(".")

# Mock web3 BEFORE any imports
with patch.dict('sys.modules', {'web3': MagicMock()}):
    from src.dao.executor_webhook import DAOExecutor
    from src.dao.governance_contract import ProposalInfo, ProposalState

class TestDAOExecutor(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.contract_addr = "0x1234567890123456789012345678901234567890"
        self.token_addr = "0x0987654321098765432109876543210987654321"
        self.rpc_url = "http://localhost:8545"
        self.processed_file = f"/tmp/test_dao_executor_processed_{id(self)}.json"
        self.ledger_file = f"/tmp/test_dao_executor_ledger_{id(self)}.jsonl"
        os.environ["DAO_EXECUTOR_PROCESSED_FILE"] = self.processed_file
        os.environ["DAO_EXECUTOR_LEDGER_PATH"] = self.ledger_file
        
        # Initialize executor with a real-ish but mocked gov contract
        with patch('src.dao.governance_contract.Web3'):
            self.executor = DAOExecutor(
                self.contract_addr,
                self.token_addr,
                self.rpc_url,
                poll_interval=1
            )
        
        # Patch the internal gov instance methods
        self.executor.gov.get_proposal = MagicMock()
        self.executor.gov.web3 = MagicMock()
        self.executor.gov.contract = MagicMock()

    def tearDown(self):
        os.environ.pop("DAO_EXECUTOR_PROCESSED_FILE", None)
        os.environ.pop("DAO_EXECUTOR_LEDGER_PATH", None)
        if os.path.exists(self.processed_file):
            os.remove(self.processed_file)
        if os.path.exists(self.ledger_file):
            os.remove(self.ledger_file)

    @patch('src.dao.executor_webhook.subprocess.Popen')
    @patch('os.path.exists', return_value=True)
    async def test_process_proposal_triggers_upgrade(self, mock_exists, mock_popen):
        """Test that process_proposal correctly identifies a trigger and runs the script."""
        # 1. Setup mock proposal data
        self.executor.gov.get_proposal.return_value = ProposalInfo(
            id=42,
            title="HELM_UPGRADE: Version 3.4.1",
            description="Upgrade mesh nodes to latest PQC build",
            proposer="0xABC",
            start_time=0,
            end_time=0,
            yes_votes=100,
            no_votes=0,
            abstain_votes=0,
            total_voting_power=100,
            executed=True,
            state=ProposalState.EXECUTED
        )
        
        # Setup subprocess mock
        mock_process = MagicMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = ("Success", "")
        mock_popen.return_value = mock_process
        
        # 2. Call process_proposal directly
        await self.executor.process_proposal(42)
        
        # 3. Verifications
        self.executor.gov.get_proposal.assert_called_with(42)
        mock_popen.assert_called_once()
        args, kwargs = mock_popen.call_args
        self.assertEqual(args[0], ["bash", "scripts/release_to_main.sh"])
        self.assertEqual(kwargs['env']['DAO_PROPOSAL_ID'], "42")

    async def test_process_proposal_ignores_unrelated(self):
        """Test that proposals without keywords are ignored."""
        self.executor.gov.get_proposal.return_value = ProposalInfo(
            id=43,
            title="Fix documentation typos",
            description="Minor README updates",
            proposer="0xABC",
            start_time=0,
            end_time=0,
            yes_votes=50,
            no_votes=0,
            abstain_votes=0,
            total_voting_power=100,
            executed=True,
            state=ProposalState.EXECUTED
        )
        
        with patch.object(self.executor, 'trigger_upgrade') as mock_trigger:
            await self.executor.process_proposal(43)
            mock_trigger.assert_not_called()

    async def test_process_proposal_skips_duplicate(self):
        """Duplicate proposal IDs must be idempotently ignored."""
        self.executor.gov.get_proposal.return_value = ProposalInfo(
            id=44,
            title="HELM_UPGRADE: Version 3.4.2",
            description="Upgrade mesh nodes",
            proposer="0xABC",
            start_time=0,
            end_time=0,
            yes_votes=100,
            no_votes=0,
            abstain_votes=0,
            total_voting_power=100,
            executed=True,
            state=ProposalState.EXECUTED
        )

        with patch.object(self.executor, "trigger_upgrade", return_value=True) as mock_trigger:
            first = await self.executor.process_proposal(44)
            second = await self.executor.process_proposal(44)

        self.assertTrue(first["executed"])
        self.assertEqual(first["reason"], "upgrade_success")
        self.assertFalse(second["executed"])
        self.assertEqual(second["reason"], "duplicate")
        mock_trigger.assert_called_once()

if __name__ == "__main__":
    unittest.main()
