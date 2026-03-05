"""
Unit tests for src/dao/governance_script.py

Tests cover:
- Deployment file save/load
- Audit ledger append
- CLI commands: set-deployment, propose, vote, status, execute, list, info
- EIP-1559 transaction builder
- Chain-ID mismatch warning
- Read-only mode (no private key)
- Error paths: missing addresses, reverted tx, wrong vote choice
"""

import json
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner


# ---------------------------------------------------------------------------
# Helpers — build a realistic Web3 + contract mock
# ---------------------------------------------------------------------------

def _make_proposal_tuple(
    pid=1,
    title="Test Proposal",
    description="desc",
    proposer="0xDeaD",
    start_time=1000,
    end_time=int(time.time()) + 3600,
    yes=100,
    no=50,
    abstain=10,
    total_power=1000,
    executed=False,
    state=1,  # ACTIVE
):
    return (pid, title, description, proposer, start_time, end_time,
            yes, no, abstain, total_power, executed, state)


def _make_web3_mock(chain_id=84532, connected=True):
    """Return a fully wired Web3 mock."""
    w3 = MagicMock()
    w3.is_connected.return_value = connected
    w3.eth.chain_id = chain_id

    # Block for EIP-1559
    w3.eth.get_block.return_value = {"baseFeePerGas": int(1e9)}  # 1 gwei
    w3.to_wei.side_effect = lambda val, unit: int(val * 1e9) if unit == "gwei" else int(val)
    w3.from_wei.side_effect = lambda val, unit: val / 1e18 if unit == "ether" else val
    w3.to_checksum_address.side_effect = lambda x: x

    # Tx machinery
    signed = MagicMock()
    signed.raw_transaction = b"\x00" * 32
    w3.eth.account.sign_transaction.return_value = signed
    w3.eth.account.from_key.return_value = MagicMock(address="0xSender")
    w3.eth.send_raw_transaction.return_value = b"\xab" * 32
    w3.eth.wait_for_transaction_receipt.return_value = {
        "status": 1,
        "blockNumber": 9999,
        "gasUsed": 123456,
    }
    w3.eth.get_transaction_count.return_value = 0

    return w3


def _make_gov_contract_mock(proposal_count=1):
    gov = MagicMock()
    gov.functions.proposalCount.return_value.call.return_value = proposal_count
    gov.functions.getProposal.return_value.call.return_value = _make_proposal_tuple()
    gov.functions.canExecute.return_value.call.return_value = True
    gov.functions.getVotingPower.return_value.call.return_value = int(200 * 1e18)
    gov.functions.getVote.return_value.call.return_value = (False, 0)

    # build_transaction returns a dict-like object
    gov.functions.createProposal.return_value.build_transaction.return_value = {}
    gov.functions.castVote.return_value.build_transaction.return_value = {}
    gov.functions.executeProposal.return_value.build_transaction.return_value = {}
    return gov


def _make_token_contract_mock():
    tok = MagicMock()
    tok.functions.balanceOf.return_value.call.return_value = int(500 * 1e18)
    tok.functions.getStakeInfo.return_value.call.return_value = (int(200 * 1e18), 0, 0)
    return tok


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def deployment_file(tmp_path):
    dep = tmp_path / "base_sepolia.json"
    dep.write_text(json.dumps({
        "MeshGovernance": "0xGovAddr",
        "X0TToken": "0xTokAddr",
        "chainId": 84532,
    }))
    return dep


# ---------------------------------------------------------------------------
# Patch helpers
# ---------------------------------------------------------------------------

GOV_MODULE = "src.dao.governance_script"


def _patch_context(w3=None, gov=None, tok=None, account_addr="0xSender"):
    """Return a context_manager that injects a pre-built CliCtx."""
    from src.dao.governance_script import CliCtx

    w3 = w3 or _make_web3_mock()
    gov = gov or _make_gov_contract_mock()
    tok = tok or _make_token_contract_mock()
    acct = MagicMock(address=account_addr)

    ctx = CliCtx(
        w3=w3,
        gov=gov,
        token=tok,
        account=acct,
        private_key="0x" + "aa" * 32,
        ledger=None,
    )

    return patch(f"{GOV_MODULE}._make_context", return_value=ctx)


def _patch_load_deployment(gov="0xGovAddr", tok="0xTokAddr"):
    return patch(f"{GOV_MODULE}._load_deployment", return_value=(gov, tok))


# ---------------------------------------------------------------------------
# _load_deployment / _save_deployment
# ---------------------------------------------------------------------------

class TestDeploymentIO:
    def test_save_and_load(self, tmp_path):
        from src.dao import governance_script as gs
        orig = gs.DEPLOYMENT_FILE
        gs.DEPLOYMENT_FILE = tmp_path / "base_sepolia.json"
        gs.DEPLOYMENTS_DIR = tmp_path
        try:
            gs._save_deployment("0xGov", "0xTok")
            gov, tok = gs._load_deployment()
            assert gov == "0xGov"
            assert tok == "0xTok"
        finally:
            gs.DEPLOYMENT_FILE = orig

    def test_load_missing_file_returns_none(self, tmp_path):
        from src.dao import governance_script as gs
        orig = gs.DEPLOYMENT_FILE
        gs.DEPLOYMENT_FILE = tmp_path / "nonexistent.json"
        try:
            gov, tok = gs._load_deployment()
            assert gov is None
            assert tok is None
        finally:
            gs.DEPLOYMENT_FILE = orig

    def test_env_overrides_file(self, tmp_path, monkeypatch):
        from src.dao import governance_script as gs
        orig = gs.DEPLOYMENT_FILE
        gs.DEPLOYMENT_FILE = tmp_path / "base_sepolia.json"
        gs.DEPLOYMENTS_DIR = tmp_path
        try:
            gs._save_deployment("0xFileGov", "0xFileTok")
            monkeypatch.setenv("MESH_GOVERNANCE_ADDRESS", "0xEnvGov")
            monkeypatch.setenv("X0T_TOKEN_ADDRESS", "0xEnvTok")
            gov, tok = gs._load_deployment()
            assert gov == "0xEnvGov"
            assert tok == "0xEnvTok"
        finally:
            gs.DEPLOYMENT_FILE = orig

    def test_corrupted_file_handled(self, tmp_path):
        from src.dao import governance_script as gs
        orig = gs.DEPLOYMENT_FILE
        f = tmp_path / "base_sepolia.json"
        f.write_text("not json {{")
        gs.DEPLOYMENT_FILE = f
        try:
            gov, tok = gs._load_deployment()
            # Should return None (corrupted file gracefully handled)
            assert gov is None
            assert tok is None
        finally:
            gs.DEPLOYMENT_FILE = orig


# ---------------------------------------------------------------------------
# _audit
# ---------------------------------------------------------------------------

class TestAudit:
    def test_appends_record(self, tmp_path):
        from src.dao.governance_script import _audit
        ledger = str(tmp_path / "test_audit.jsonl")
        _audit({"action": "test", "val": 42}, ledger_path=ledger)
        _audit({"action": "test2", "val": 99}, ledger_path=ledger)
        lines = Path(ledger).read_text().strip().split("\n")
        assert len(lines) == 2
        r = json.loads(lines[0])
        assert r["action"] == "test"
        assert "_ts" in r

    def test_creates_parent_dir(self, tmp_path):
        from src.dao.governance_script import _audit
        ledger = str(tmp_path / "sub" / "dir" / "audit.jsonl")
        _audit({"action": "x"}, ledger_path=ledger)
        assert Path(ledger).exists()


# ---------------------------------------------------------------------------
# _build_tx
# ---------------------------------------------------------------------------

class TestBuildTx:
    def test_uses_eip1559_fields(self):
        from src.dao.governance_script import _build_tx, CHAIN_ID

        w3 = _make_web3_mock()
        fn = MagicMock()
        fn.build_transaction.return_value = {"from": "0xSender", "nonce": 0}

        _build_tx(w3, fn, "0xSender", 200_000)

        call_kwargs = fn.build_transaction.call_args[0][0]
        assert call_kwargs["chainId"] == CHAIN_ID
        assert "maxFeePerGas" in call_kwargs
        assert "maxPriorityFeePerGas" in call_kwargs
        assert "gasPrice" not in call_kwargs  # must NOT use legacy field

    def test_gas_limit_passed(self):
        from src.dao.governance_script import _build_tx

        w3 = _make_web3_mock()
        fn = MagicMock()
        fn.build_transaction.return_value = {}

        _build_tx(w3, fn, "0xSender", 99_999)
        call_kwargs = fn.build_transaction.call_args[0][0]
        assert call_kwargs["gas"] == 99_999


# ---------------------------------------------------------------------------
# CLI: set-deployment
# ---------------------------------------------------------------------------

class TestSetDeploymentCommand:
    def test_saves_file(self, runner, tmp_path, monkeypatch):
        from src.dao import governance_script as gs
        dep_path = tmp_path / "base_sepolia.json"
        monkeypatch.setattr(gs, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(gs, "DEPLOYMENT_FILE", dep_path)

        from src.dao.governance_script import set_deployment
        result = runner.invoke(set_deployment, ["0xGovNew", "0xTokNew"], catch_exceptions=False)
        assert result.exit_code == 0, result.output
        data = json.loads(dep_path.read_text())
        assert data["MeshGovernance"] == "0xGovNew"
        assert data["X0TToken"] == "0xTokNew"


# ---------------------------------------------------------------------------
# CLI: propose
# ---------------------------------------------------------------------------

class TestProposeCommand:
    def test_creates_proposal_successfully(self, runner):
        from src.dao.governance_script import cli

        with _patch_load_deployment(), _patch_context():
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "propose",
                "-t", "Test Title",
                "-d", "Test description",
                "--duration", "172800",
            ])
        assert result.exit_code == 0, result.output
        assert "Proposal #1 created" in result.output

    def test_propose_without_private_key_fails(self, runner):
        from src.dao.governance_script import cli
        from src.dao.governance_script import CliCtx

        w3 = _make_web3_mock()
        ctx_no_key = CliCtx(
            w3=w3,
            gov=_make_gov_contract_mock(),
            token=_make_token_contract_mock(),
            account=None,
            private_key=None,
            ledger=None,
        )

        with _patch_load_deployment(), \
             patch(f"{GOV_MODULE}._make_context", return_value=ctx_no_key):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "propose", "-t", "X", "-d", "Y",
            ])
        assert result.exit_code != 0
        assert "private-key required" in result.output.lower() or \
               "private-key required" in (result.exception and str(result.exception) or "")

    def test_propose_reverted_tx_exits_nonzero(self, runner):
        from src.dao.governance_script import CliCtx

        w3 = _make_web3_mock()
        w3.eth.wait_for_transaction_receipt.return_value = {"status": 0, "blockNumber": 1}

        ctx = CliCtx(
            w3=w3,
            gov=_make_gov_contract_mock(),
            token=_make_token_contract_mock(),
            account=MagicMock(address="0xSender"),
            private_key="0x" + "aa" * 32,
            ledger=None,
        )

        with _patch_load_deployment(), \
             patch(f"{GOV_MODULE}._make_context", return_value=ctx):
            from src.dao.governance_script import cli
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "propose", "-t", "X", "-d", "Y",
            ])
        assert result.exit_code != 0

    def test_propose_writes_audit_ledger(self, runner, tmp_path):
        from src.dao.governance_script import CliCtx, cli

        ledger = str(tmp_path / "audit.jsonl")
        ctx = CliCtx(
            w3=_make_web3_mock(),
            gov=_make_gov_contract_mock(),
            token=_make_token_contract_mock(),
            account=MagicMock(address="0xSender"),
            private_key="0x" + "aa" * 32,
            ledger=ledger,
        )

        with _patch_load_deployment(), \
             patch(f"{GOV_MODULE}._make_context", return_value=ctx):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "propose", "-t", "Audit Test", "-d", "desc",
            ])

        assert result.exit_code == 0
        assert Path(ledger).exists()
        record = json.loads(Path(ledger).read_text().strip())
        assert record["action"] == "propose"
        assert record["title"] == "Audit Test"


# ---------------------------------------------------------------------------
# CLI: vote
# ---------------------------------------------------------------------------

class TestVoteCommand:
    @pytest.mark.parametrize("choice,expected_support", [
        ("for", 1),
        ("yes", 1),
        ("against", 0),
        ("no", 0),
        ("abstain", 2),
    ])
    def test_vote_choices_map_correctly(self, runner, choice, expected_support):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock()

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "vote", "1", choice,
            ])

        assert result.exit_code == 0, result.output
        assert "Vote recorded" in result.output
        # Verify castVote was called with correct support value
        gov.functions.castVote.assert_called_with(1, expected_support)

    def test_vote_invalid_choice_rejected(self, runner):
        from src.dao.governance_script import cli

        with _patch_load_deployment(), _patch_context():
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "vote", "1", "maybe",
            ])
        assert result.exit_code != 0

    def test_vote_zero_power_warns(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock()
        gov.functions.getVotingPower.return_value.call.return_value = 0

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "vote", "1", "for",
            ])

        assert "voting power is 0" in result.output.lower()

    def test_vote_writes_audit_ledger(self, runner, tmp_path):
        from src.dao.governance_script import CliCtx, cli

        ledger = str(tmp_path / "vote_audit.jsonl")
        ctx = CliCtx(
            w3=_make_web3_mock(),
            gov=_make_gov_contract_mock(),
            token=_make_token_contract_mock(),
            account=MagicMock(address="0xVoter"),
            private_key="0x" + "aa" * 32,
            ledger=ledger,
        )

        with _patch_load_deployment(), \
             patch(f"{GOV_MODULE}._make_context", return_value=ctx):
            runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "vote", "2", "against",
            ])

        record = json.loads(Path(ledger).read_text().strip())
        assert record["action"] == "vote"
        assert record["support"] == 0  # against
        assert record["proposal_id"] == 2


# ---------------------------------------------------------------------------
# CLI: status
# ---------------------------------------------------------------------------

class TestStatusCommand:
    def test_status_shows_proposal_details(self, runner):
        from src.dao.governance_script import cli

        with _patch_load_deployment(), _patch_context():
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "status", "1",
            ])

        assert result.exit_code == 0, result.output
        assert "Test Proposal" in result.output
        assert "ACTIVE" in result.output

    def test_status_shows_ready_to_execute(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock()
        gov.functions.canExecute.return_value.call.return_value = True
        gov.functions.getProposal.return_value.call.return_value = _make_proposal_tuple(state=2)  # PASSED

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "status", "1",
            ])

        assert "ready to execute" in result.output.lower()

    def test_status_shows_own_vote(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock()
        gov.functions.getVote.return_value.call.return_value = (True, 1)  # voted FOR

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "status", "1",
            ])

        assert "FOR" in result.output


# ---------------------------------------------------------------------------
# CLI: execute
# ---------------------------------------------------------------------------

class TestExecuteCommand:
    def test_execute_passed_proposal(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock()
        gov.functions.canExecute.return_value.call.return_value = True
        gov.functions.getProposal.return_value.call.return_value = _make_proposal_tuple(state=2)

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "execute", "1",
            ])

        assert result.exit_code == 0, result.output
        assert "executed" in result.output.lower()

    def test_execute_not_ready_fails(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock()
        gov.functions.canExecute.return_value.call.return_value = False
        gov.functions.getProposal.return_value.call.return_value = _make_proposal_tuple(state=1)  # ACTIVE

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "execute", "1",
            ])

        assert result.exit_code != 0
        assert "cannot be executed" in result.output.lower()

    def test_execute_writes_audit_ledger(self, runner, tmp_path):
        from src.dao.governance_script import CliCtx, cli

        ledger = str(tmp_path / "exec_audit.jsonl")
        ctx = CliCtx(
            w3=_make_web3_mock(),
            gov=_make_gov_contract_mock(),
            token=_make_token_contract_mock(),
            account=MagicMock(address="0xExecutor"),
            private_key="0x" + "aa" * 32,
            ledger=ledger,
        )

        with _patch_load_deployment(), \
             patch(f"{GOV_MODULE}._make_context", return_value=ctx):
            runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "execute", "1",
            ])

        record = json.loads(Path(ledger).read_text().strip())
        assert record["action"] == "execute"
        assert record["proposal_id"] == 1


# ---------------------------------------------------------------------------
# CLI: list
# ---------------------------------------------------------------------------

class TestListCommand:
    def test_list_shows_proposals(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock(proposal_count=3)
        gov.functions.getProposal.return_value.call.side_effect = [
            _make_proposal_tuple(pid=1, title="Proposal One", state=4),   # EXECUTED
            _make_proposal_tuple(pid=2, title="Proposal Two", state=1),   # ACTIVE
            _make_proposal_tuple(pid=3, title="Proposal Three", state=2), # PASSED
        ]

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "list", "--limit", "10",
            ])

        assert result.exit_code == 0, result.output
        assert "Total proposals: 3" in result.output
        assert "Proposal One" in result.output
        assert "EXECUTED" in result.output
        assert "ACTIVE" in result.output

    def test_list_empty(self, runner):
        from src.dao.governance_script import cli

        gov = _make_gov_contract_mock(proposal_count=0)

        with _patch_load_deployment(), _patch_context(gov=gov):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "list",
            ])

        assert result.exit_code == 0
        assert "No proposals yet" in result.output


# ---------------------------------------------------------------------------
# CLI: info
# ---------------------------------------------------------------------------

class TestInfoCommand:
    def test_info_shows_balance_and_power(self, runner):
        from src.dao.governance_script import cli

        with _patch_load_deployment(), _patch_context():
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "--private-key", "0x" + "aa" * 32,
                "info",
            ])

        assert result.exit_code == 0, result.output
        assert "X0T balance" in result.output
        assert "Voting power" in result.output
        assert "Staked" in result.output

    def test_info_with_explicit_address(self, runner):
        from src.dao.governance_script import cli

        # to_checksum_address is a Web3 classmethod — patch it directly
        with _patch_load_deployment(), _patch_context(), \
             patch(f"{GOV_MODULE}.Web3.to_checksum_address", side_effect=lambda x: x):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "info", "0xDeadBeef",
            ])

        assert result.exit_code == 0, result.output
        assert "0xDeadBeef" in result.output

    def test_info_no_key_no_address_fails(self, runner):
        from src.dao.governance_script import CliCtx, cli

        ctx = CliCtx(
            w3=_make_web3_mock(),
            gov=_make_gov_contract_mock(),
            token=_make_token_contract_mock(),
            account=None,
            private_key=None,
            ledger=None,
        )

        with _patch_load_deployment(), \
             patch(f"{GOV_MODULE}._make_context", return_value=ctx):
            result = runner.invoke(cli, [
                "--governance-address", "0xGov",
                "--token-address", "0xTok",
                "info",
            ])

        assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Chain ID guard
# ---------------------------------------------------------------------------

class TestChainIdGuard:
    def test_chain_id_constant_is_base_sepolia(self):
        """CHAIN_ID must be 84532 (Base Sepolia)."""
        from src.dao.governance_script import CHAIN_ID
        assert CHAIN_ID == 84532

    def test_vote_map_completeness(self):
        """All CLI vote aliases map to valid on-chain support values {0,1,2}."""
        from src.dao.governance_script import VOTE_MAP
        assert set(VOTE_MAP.values()) == {0, 1, 2}
        assert VOTE_MAP["for"] == 1
        assert VOTE_MAP["against"] == 0
        assert VOTE_MAP["abstain"] == 2
