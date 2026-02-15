"""Unit tests for src.dao.mape_k_integration module.

Covers:
- ProposalStatus and VoteType enums
- GovernanceAction dataclass and to_proposal_description
- GovernanceMetrics dataclass
- SimpleLogisticModel: _score, predict, predict_proba
- MLBasedGovernanceOracle: should_execute_action, get_voting_recommendation, get_execution_priority
- MAEKGovernanceAdapter: submit_governance_action, cast_vote, queue_proposal, execute_proposal,
  get_governance_metrics, monitor_proposal
- DAOIntegration: process_mapek_decision, vote_on_proposal, finalize_proposal
"""

import json
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest


# ---- Mock web3/eth dependencies before importing the module under test ----
@pytest.fixture(autouse=True)
def _mock_web3_ecosystem():
    """Ensure web3, eth_account, eth_utils are mocked for all tests here."""
    mock_web3_mod = MagicMock()
    mock_eth_account = MagicMock()
    mock_eth_utils = MagicMock()

    # Web3.keccak should return a bytes-like object with .hex()
    keccak_result = MagicMock()
    keccak_result.hex.return_value = "0xabc123"
    mock_web3_mod.Web3.keccak.return_value = keccak_result

    # to_checksum_address returns the address as-is
    mock_eth_utils.to_checksum_address = lambda addr: addr

    # Account.from_key returns a mock account
    mock_account = MagicMock()
    mock_account.address = "0xTestAccountAddress"
    mock_eth_account.Account.from_key.return_value = mock_account

    with patch.dict(
        "sys.modules",
        {
            "web3": mock_web3_mod,
            "eth_account": mock_eth_account,
            "eth_utils": mock_eth_utils,
        },
    ):
        yield {
            "web3_mod": mock_web3_mod,
            "eth_account": mock_eth_account,
            "eth_utils": mock_eth_utils,
            "keccak_result": keccak_result,
            "mock_account": mock_account,
        }


@pytest.fixture
def _import_module(_mock_web3_ecosystem):
    """Import the module under test after mocks are in place."""
    import importlib

    mod = importlib.import_module("src.dao.mape_k_integration")
    return mod


# ---------------------------------------------------------------------------
# Enum tests
# ---------------------------------------------------------------------------


class TestProposalStatus:
    def test_values(self, _import_module):
        mod = _import_module
        assert mod.ProposalStatus.PENDING.value == 0
        assert mod.ProposalStatus.ACTIVE.value == 1
        assert mod.ProposalStatus.CANCELED.value == 2
        assert mod.ProposalStatus.DEFEATED.value == 3
        assert mod.ProposalStatus.SUCCEEDED.value == 4
        assert mod.ProposalStatus.QUEUED.value == 5
        assert mod.ProposalStatus.EXPIRED.value == 6
        assert mod.ProposalStatus.EXECUTED.value == 7

    def test_member_count(self, _import_module):
        mod = _import_module
        assert len(mod.ProposalStatus) == 8


class TestVoteType:
    def test_values(self, _import_module):
        mod = _import_module
        assert mod.VoteType.AGAINST.value == 0
        assert mod.VoteType.FOR.value == 1
        assert mod.VoteType.ABSTAIN.value == 2

    def test_member_count(self, _import_module):
        mod = _import_module
        assert len(mod.VoteType) == 3


# ---------------------------------------------------------------------------
# GovernanceAction dataclass
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_action(_import_module):
    mod = _import_module
    return mod.GovernanceAction(
        action_id="test-action-001",
        title="Security Patch: Rotate mTLS certs",
        description="Rotate X.509 certificates across all mesh nodes for security compliance.",
        targets=["0xTarget1", "0xTarget2"],
        values=[0, 0],
        calldatas=["0xcalldata1", "0xcalldata2"],
        votes_required=50,
        execution_delay=86400,
        created_at=datetime(2026, 1, 15, 12, 0, 0),
    )


class TestGovernanceAction:
    def test_to_proposal_description(self, sample_action):
        desc = sample_action.to_proposal_description()
        assert "# Security Patch: Rotate mTLS certs" in desc
        assert "Rotate X.509 certificates" in desc
        assert "Action ID: test-action-001" in desc

    def test_fields(self, sample_action):
        assert sample_action.action_id == "test-action-001"
        assert sample_action.votes_required == 50
        assert sample_action.execution_delay == 86400
        assert len(sample_action.targets) == 2


# ---------------------------------------------------------------------------
# GovernanceMetrics dataclass
# ---------------------------------------------------------------------------


class TestGovernanceMetrics:
    def test_fields(self, _import_module):
        mod = _import_module
        ts = datetime(2026, 2, 10)
        m = mod.GovernanceMetrics(
            total_proposals=10,
            active_proposals=2,
            passed_proposals=5,
            failed_proposals=3,
            executed_proposals=4,
            total_voters=100,
            total_votes_cast=500,
            average_quorum=0.45,
            average_voting_period=50400,
            timestamp=ts,
        )
        assert m.total_proposals == 10
        assert m.executed_proposals == 4
        assert m.average_quorum == 0.45
        assert m.timestamp == ts


# ---------------------------------------------------------------------------
# SimpleLogisticModel
# ---------------------------------------------------------------------------


class TestSimpleLogisticModel:
    def test_score_basic(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0, 0.0], bias=0.0)
        # sigmoid(0) = 0.5
        assert abs(model._score([0.0, 5.0]) - 0.5) < 0.01

    def test_score_positive(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0], bias=0.0)
        # sigmoid(10) ≈ 1.0
        score = model._score([10.0])
        assert score > 0.99

    def test_score_negative(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0], bias=0.0)
        # sigmoid(-10) ≈ 0.0
        score = model._score([-10.0])
        assert score < 0.01

    def test_score_with_bias(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[0.0], bias=5.0)
        # sigmoid(5) > 0.99
        assert model._score([0.0]) > 0.99

    def test_score_feature_length_mismatch(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0, 2.0])
        with pytest.raises(ValueError, match="Feature length does not match"):
            model._score([1.0])

    def test_predict_all_positive(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0], bias=5.0)
        preds = model.predict([[0.0], [1.0], [2.0]])
        assert preds == [1, 1, 1]

    def test_predict_all_negative(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0], bias=-100.0)
        preds = model.predict([[0.0], [1.0]])
        assert preds == [0, 0]

    def test_predict_boundary(self, _import_module):
        """sigmoid(0) = 0.5 should be class 1 (>= 0.5)"""
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[0.0], bias=0.0)
        preds = model.predict([[0.0]])
        assert preds == [1]

    def test_predict_proba_shape(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0], bias=0.0)
        proba = model.predict_proba([[0.0], [5.0]])
        assert len(proba) == 2
        for row in proba:
            assert len(row) == 2
            assert abs(row[0] + row[1] - 1.0) < 1e-6

    def test_predict_proba_values(self, _import_module):
        mod = _import_module
        model = mod.SimpleLogisticModel(weights=[1.0], bias=0.0)
        proba = model.predict_proba([[0.0]])
        assert abs(proba[0][0] - 0.5) < 0.01
        assert abs(proba[0][1] - 0.5) < 0.01


# ---------------------------------------------------------------------------
# MLBasedGovernanceOracle
# ---------------------------------------------------------------------------


class TestMLBasedGovernanceOracle:
    def test_init_no_model(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        assert oracle.model is None
        assert oracle.model_path is None

    def test_init_with_valid_json_model(self, _import_module):
        mod = _import_module
        model_data = {
            "type": "logistic",
            "weights": [0.1, 0.2, 0.3, 0.4, 0.5],
            "bias": -1.0,
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(model_data, f)
            f.flush()
            path = f.name

        try:
            oracle = mod.MLBasedGovernanceOracle(model_path=path)
            assert oracle.model is not None
            assert isinstance(oracle.model, mod.SimpleLogisticModel)
            assert oracle.model.bias == -1.0
            assert len(oracle.model.weights) == 5
        finally:
            os.unlink(path)

    def test_init_with_invalid_extension(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle(model_path="/tmp/model.pkl")
        assert oracle.model is None

    def test_init_with_unsupported_model_type(self, _import_module):
        mod = _import_module
        model_data = {"type": "neural_net", "weights": [1.0]}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(model_data, f)
            f.flush()
            path = f.name
        try:
            oracle = mod.MLBasedGovernanceOracle(model_path=path)
            assert oracle.model is None
        finally:
            os.unlink(path)

    def test_init_with_missing_weights(self, _import_module):
        mod = _import_module
        model_data = {"type": "logistic", "weights": []}
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(model_data, f)
            f.flush()
            path = f.name
        try:
            oracle = mod.MLBasedGovernanceOracle(model_path=path)
            assert oracle.model is None
        finally:
            os.unlink(path)

    def test_init_with_nonexistent_file(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle(model_path="/tmp/nonexistent_model.json")
        assert oracle.model is None

    @pytest.mark.asyncio
    async def test_should_execute_action_heuristic_pass(
        self, _import_module, sample_action
    ):
        """Heuristic fallback: desc > 50, delay >= 86400, targets <= 5"""
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        result = await oracle.should_execute_action(sample_action)
        # description is >50 chars, execution_delay=86400, targets=2
        assert result is True

    @pytest.mark.asyncio
    async def test_should_execute_action_heuristic_fail_short_desc(
        self, _import_module
    ):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="a1",
            title="T",
            description="Short",
            targets=["0x1"],
            values=[0],
            calldatas=["0x"],
            votes_required=10,
            execution_delay=86400,
            created_at=datetime.now(),
        )
        result = await oracle.should_execute_action(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_execute_action_heuristic_fail_low_delay(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="a2",
            title="Title",
            description="A sufficiently long description for the heuristic check to be satisfied.",
            targets=["0x1"],
            values=[0],
            calldatas=["0x"],
            votes_required=10,
            execution_delay=3600,  # < 86400
            created_at=datetime.now(),
        )
        result = await oracle.should_execute_action(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_execute_action_heuristic_fail_too_many_targets(
        self, _import_module
    ):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="a3",
            title="Title",
            description="A sufficiently long description for the heuristic check to be satisfied fully.",
            targets=[f"0x{i}" for i in range(10)],
            values=[0] * 10,
            calldatas=["0x"] * 10,
            votes_required=10,
            execution_delay=86400,
            created_at=datetime.now(),
        )
        result = await oracle.should_execute_action(action)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_execute_action_with_model(
        self, _import_module, sample_action
    ):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        mock_model = MagicMock()
        mock_model.predict.return_value = [1]
        oracle.model = mock_model
        result = await oracle.should_execute_action(sample_action)
        assert result is True
        mock_model.predict.assert_called_once()

    @pytest.mark.asyncio
    async def test_should_execute_action_model_predicts_no(
        self, _import_module, sample_action
    ):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        mock_model = MagicMock()
        mock_model.predict.return_value = [0]
        oracle.model = mock_model
        result = await oracle.should_execute_action(sample_action)
        assert result is False

    @pytest.mark.asyncio
    async def test_should_execute_action_model_exception_falls_back(
        self, _import_module, sample_action
    ):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        mock_model = MagicMock()
        mock_model.predict.side_effect = RuntimeError("model error")
        oracle.model = mock_model
        # Falls back to heuristic which passes for sample_action
        result = await oracle.should_execute_action(sample_action)
        assert result is True

    @pytest.mark.asyncio
    async def test_get_voting_recommendation_no_model(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        rec = await oracle.get_voting_recommendation(42)
        assert rec == mod.VoteType.ABSTAIN

    @pytest.mark.asyncio
    async def test_get_voting_recommendation_model_for(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = [[0.3, 0.7]]
        oracle.model = mock_model
        rec = await oracle.get_voting_recommendation(42)
        assert rec == mod.VoteType.FOR

    @pytest.mark.asyncio
    async def test_get_voting_recommendation_model_against(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        mock_model = MagicMock()
        mock_model.predict_proba.return_value = [[0.8, 0.2]]
        oracle.model = mock_model
        rec = await oracle.get_voting_recommendation(42)
        assert rec == mod.VoteType.AGAINST

    @pytest.mark.asyncio
    async def test_get_voting_recommendation_model_exception(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        mock_model = MagicMock()
        mock_model.predict_proba.side_effect = RuntimeError("fail")
        oracle.model = mock_model
        rec = await oracle.get_voting_recommendation(42)
        assert rec == mod.VoteType.ABSTAIN

    @pytest.mark.asyncio
    async def test_get_execution_priority_base(self, _import_module, sample_action):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        # sample_action has "security" in description (+0.2) and "Patch" in title (+0.15) -> 0.85
        priority = await oracle.get_execution_priority(sample_action)
        assert abs(priority - 0.85) < 0.01

    @pytest.mark.asyncio
    async def test_get_execution_priority_with_fix(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="p1",
            title="Fix critical bug",
            description="Non-critical cosmetic changes",
            targets=[],
            values=[],
            calldatas=[],
            votes_required=10,
            execution_delay=86400,
            created_at=datetime.now(),
        )
        # base 0.5 + fix 0.15 + non-critical -0.15 = 0.5
        priority = await oracle.get_execution_priority(action)
        assert abs(priority - 0.5) < 0.01

    @pytest.mark.asyncio
    async def test_get_execution_priority_security_and_patch(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="p2",
            title="Patch vulnerability",
            description="Security hardening for mesh",
            targets=[],
            values=[],
            calldatas=[],
            votes_required=10,
            execution_delay=86400,
            created_at=datetime.now(),
        )
        # base 0.5 + security 0.2 + patch 0.15 = 0.85
        priority = await oracle.get_execution_priority(action)
        assert abs(priority - 0.85) < 0.01

    @pytest.mark.asyncio
    async def test_get_execution_priority_clamped_at_1(self, _import_module):
        """Priority should never exceed 1.0"""
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="p3",
            title="Fix patch emergency",
            description="Security critical fix patch vulnerability",
            targets=[],
            values=[],
            calldatas=[],
            votes_required=10,
            execution_delay=86400,
            created_at=datetime.now(),
        )
        priority = await oracle.get_execution_priority(action)
        assert priority <= 1.0

    @pytest.mark.asyncio
    async def test_get_execution_priority_plain(self, _import_module):
        mod = _import_module
        oracle = mod.MLBasedGovernanceOracle()
        action = mod.GovernanceAction(
            action_id="p4",
            title="Routine update",
            description="Regular maintenance cycle",
            targets=[],
            values=[],
            calldatas=[],
            votes_required=10,
            execution_delay=86400,
            created_at=datetime.now(),
        )
        # No keywords -> base 0.5
        priority = await oracle.get_execution_priority(action)
        assert abs(priority - 0.5) < 0.01


# ---------------------------------------------------------------------------
# MAEKGovernanceAdapter
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_oracle(_import_module):
    """Create a mock GovernanceOracle."""
    oracle = AsyncMock()
    oracle.should_execute_action = AsyncMock(return_value=True)
    oracle.get_voting_recommendation = AsyncMock(
        return_value=_import_module.VoteType.FOR
    )
    oracle.get_execution_priority = AsyncMock(return_value=0.8)
    return oracle


@pytest.fixture
def adapter(_import_module, mock_oracle, _mock_web3_ecosystem):
    """Create MAEKGovernanceAdapter with mocked dependencies."""
    mod = _import_module
    mocks = _mock_web3_ecosystem

    mock_w3 = MagicMock()

    adapter = mod.MAEKGovernanceAdapter(
        w3=mock_w3,
        governor_address="0x" + "a" * 40,
        governance_token_address="0x" + "b" * 40,
        treasury_address="0x" + "c" * 40,
        timelock_address="0x" + "d" * 40,
        private_key="0x" + "e" * 64,
        oracle=mock_oracle,
    )
    return adapter


class TestMAEKGovernanceAdapter:
    @pytest.mark.asyncio
    async def test_submit_governance_action_success(self, adapter, sample_action):
        result = await adapter.submit_governance_action(sample_action)
        assert result is not None

    @pytest.mark.asyncio
    async def test_submit_governance_action_oracle_rejects(
        self, adapter, sample_action, mock_oracle
    ):
        mock_oracle.should_execute_action.return_value = False
        result = await adapter.submit_governance_action(sample_action)
        assert result is None

    @pytest.mark.asyncio
    async def test_submit_governance_action_validate_only(self, adapter, sample_action):
        result = await adapter.submit_governance_action(
            sample_action, submit_proposal=False
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_submit_governance_action_exception(
        self, adapter, sample_action, _import_module
    ):
        """When Web3.keccak raises, should return None."""
        mod = _import_module
        # Patch the Web3 used by the module to raise
        with patch.object(adapter, "governor_address", side_effect=Exception("boom")):
            # Trigger exception in the try block by making keccak fail
            orig_keccak = (
                type(adapter.w3).keccak if hasattr(type(adapter.w3), "keccak") else None
            )
            # We can trigger the exception by making the string concatenation fail
            adapter.governor_address = None  # will cause TypeError in concatenation
            result = await adapter.submit_governance_action(sample_action)
            assert result is None

    @pytest.mark.asyncio
    async def test_cast_vote_with_explicit_vote_type(self, adapter, _import_module):
        mod = _import_module
        result = await adapter.cast_vote("0xabc", "0xVoter", mod.VoteType.FOR)
        assert result is True

    @pytest.mark.asyncio
    async def test_cast_vote_with_oracle_recommendation(self, adapter, mock_oracle):
        result = await adapter.cast_vote("0xabc123", "0xVoter")
        assert result is True
        mock_oracle.get_voting_recommendation.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cast_vote_exception(self, adapter, mock_oracle):
        mock_oracle.get_voting_recommendation.side_effect = RuntimeError("oracle fail")
        result = await adapter.cast_vote("0xabc123", "0xVoter")
        assert result is False

    @pytest.mark.asyncio
    async def test_queue_proposal_success(self, adapter):
        result = await adapter.queue_proposal("0xproposal123")
        assert result is True

    @pytest.mark.asyncio
    async def test_execute_proposal_success(self, adapter):
        result = await adapter.execute_proposal("0xproposal123")
        assert result is True

    @pytest.mark.asyncio
    async def test_get_governance_metrics(self, adapter, _import_module):
        mod = _import_module
        metrics = await adapter.get_governance_metrics()
        assert isinstance(metrics, mod.GovernanceMetrics)
        assert metrics.total_proposals == 0
        assert metrics.average_voting_period == 50400

    @pytest.mark.asyncio
    async def test_monitor_proposal_breaks_immediately(self, adapter):
        """monitor_proposal has a break right after logging, so it should return."""
        # This should complete quickly because the loop breaks on first iteration
        await adapter.monitor_proposal("0xproposal123", check_interval=0)


# ---------------------------------------------------------------------------
# DAOIntegration
# ---------------------------------------------------------------------------


@pytest.fixture
def contracts():
    return {
        "governor": "0x" + "a" * 40,
        "token": "0x" + "b" * 40,
        "treasury": "0x" + "c" * 40,
        "timelock": "0x" + "d" * 40,
    }


@pytest.fixture
def dao_integration(_import_module, contracts, mock_oracle, _mock_web3_ecosystem):
    mod = _import_module
    mock_w3 = MagicMock()
    return mod.DAOIntegration(
        w3=mock_w3,
        contracts=contracts,
        private_key="0x" + "f" * 64,
        oracle=mock_oracle,
    )


class TestDAOIntegration:
    @pytest.mark.asyncio
    async def test_process_mapek_decision_success(self, dao_integration):
        decision = {
            "id": "decision-001",
            "title": "Update mTLS certificates",
            "description": "Rotate certificates across all security mesh nodes for compliance and safety.",
            "targets": ["0xTarget"],
            "values": [0],
            "calldatas": ["0xcall"],
            "votes_required": 50,
            "execution_delay": 172800,
        }
        result = await dao_integration.process_mapek_decision(decision)
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_mapek_decision_defaults(self, dao_integration):
        """Test that default values are applied when not in decision."""
        decision = {
            "title": "Simple action",
            "description": "A simple action with defaults for everything else that is not specified.",
        }
        result = await dao_integration.process_mapek_decision(decision)
        assert result is not None

    @pytest.mark.asyncio
    async def test_process_mapek_decision_oracle_rejects(
        self, dao_integration, mock_oracle
    ):
        mock_oracle.should_execute_action.return_value = False
        decision = {
            "title": "Rejected action",
            "description": "This action should be rejected by the oracle.",
        }
        result = await dao_integration.process_mapek_decision(decision)
        assert result is None

    @pytest.mark.asyncio
    async def test_vote_on_proposal(self, dao_integration):
        result = await dao_integration.vote_on_proposal("0xabc", "0xVoter")
        assert result is True

    @pytest.mark.asyncio
    async def test_finalize_proposal_queue_fails(self, dao_integration):
        dao_integration.adapter.queue_proposal = AsyncMock(return_value=False)
        result = await dao_integration.finalize_proposal("0xabc")
        assert result is False

    @pytest.mark.asyncio
    async def test_finalize_proposal_success(self, dao_integration):
        dao_integration.adapter.queue_proposal = AsyncMock(return_value=True)
        dao_integration.adapter.execute_proposal = AsyncMock(return_value=True)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await dao_integration.finalize_proposal("0xabc")
        assert result is True

    @pytest.mark.asyncio
    async def test_finalize_proposal_execute_fails(self, dao_integration):
        dao_integration.adapter.queue_proposal = AsyncMock(return_value=True)
        dao_integration.adapter.execute_proposal = AsyncMock(return_value=False)
        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await dao_integration.finalize_proposal("0xabc")
        assert result is False


# ---------------------------------------------------------------------------
# GovernanceAction serialization
# ---------------------------------------------------------------------------


class TestGovernanceActionSerialization:
    def test_asdict(self, _import_module, sample_action):
        from dataclasses import asdict

        d = asdict(sample_action)
        assert d["action_id"] == "test-action-001"
        assert d["votes_required"] == 50
        assert isinstance(d["targets"], list)

    def test_proposal_description_format(self, _import_module, sample_action):
        desc = sample_action.to_proposal_description()
        lines = desc.split("\n")
        assert lines[0].startswith("# ")
        assert "Action ID:" in desc
