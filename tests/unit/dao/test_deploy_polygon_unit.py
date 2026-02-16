"""Unit tests for src.dao.deploy_polygon — contract deployment to Polygon."""

import json
import os
import sys
from types import SimpleNamespace
from unittest import mock

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")

import pytest

# ── Pre-install fake web3 modules so the import doesn't need the real package ──
if "web3" not in sys.modules:
    fake_web3 = mock.MagicMock()
    fake_web3.Web3 = mock.MagicMock()
    sys.modules["web3"] = fake_web3

if "web3.middleware" not in sys.modules:
    fake_web3_middleware = mock.MagicMock()
    fake_web3_middleware.ExtraDataToPOAMiddleware = mock.MagicMock(
        name="ExtraDataToPOAMiddleware"
    )
    fake_web3_middleware.geth_poa_middleware = mock.MagicMock(
        name="geth_poa_middleware"
    )
    sys.modules["web3.middleware"] = fake_web3_middleware

import src.dao.deploy_polygon as mod

HARDHAT_KEY = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"


# ---------------------------------------------------------------------------
# Fake helpers
# ---------------------------------------------------------------------------

class _FakeMiddlewareOnion:
    def __init__(self):
        self.calls = []

    def inject(self, middleware, layer=0):
        self.calls.append((middleware, layer))


class _FakeContract:
    def __init__(self):
        self._ctor_args = ()

    def constructor(self, *args):
        self._ctor_args = args
        return self

    def build_transaction(self, tx):
        payload = dict(tx)
        if self._ctor_args:
            payload["_ctor_args"] = self._ctor_args
        return payload


class _FakeAccount:
    address = "0xDeployer"

    def sign_transaction(self, _tx):
        return SimpleNamespace(rawTransaction=b"signed")


class _FakeEth:
    def __init__(self):
        self.account = SimpleNamespace(from_key=lambda _key: _FakeAccount())
        self.gas_price = 100
        self.chain_id = 137
        self._nonce = 0
        self._receipts = 0
        self.sent = []

    def get_transaction_count(self, _address):
        nonce = self._nonce
        self._nonce += 1
        return nonce

    def get_balance(self, _address):
        return 10**18

    def contract(self, abi=None, bytecode=None):
        _ = (abi, bytecode)
        return _FakeContract()

    def estimate_gas(self, _tx):
        return 100_000

    def send_raw_transaction(self, raw):
        tx_hash = bytes([len(self.sent) + 1]) * 32
        self.sent.append(raw)
        return tx_hash

    def wait_for_transaction_receipt(self, _tx_hash):
        self._receipts += 1
        if self._receipts == 1:
            return SimpleNamespace(contractAddress="0xToken")
        return SimpleNamespace(contractAddress="0xGovernance")


class _FakeWeb3:
    last_instance = None

    @staticmethod
    def HTTPProvider(url):
        return url

    def __init__(self, provider):
        self.provider = provider
        self.eth = _FakeEth()
        self.middleware_onion = _FakeMiddlewareOnion()
        _FakeWeb3.last_instance = self

    def is_connected(self):
        return True

    def from_wei(self, value, _unit):
        return value / 10**18


# ---------------------------------------------------------------------------
# load_contract tests
# ---------------------------------------------------------------------------

class TestLoadContract:
    """Tests for load_contract()."""

    def test_raises_for_missing_artifact(self, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "ARTIFACTS_DIR", tmp_path)
        with pytest.raises(FileNotFoundError, match="Artifact not found"):
            mod.load_contract("X0TToken")

    def test_reads_abi_and_bytecode(self, monkeypatch, tmp_path):
        token_dir = tmp_path / "X0TToken.sol"
        token_dir.mkdir(parents=True)
        artifact = token_dir / "X0TToken.json"
        artifact.write_text(json.dumps({"abi": [{"name": "fn"}], "bytecode": "0x6000"}))

        monkeypatch.setattr(mod, "ARTIFACTS_DIR", tmp_path)
        abi, bytecode = mod.load_contract("X0TToken")

        assert abi == [{"name": "fn"}]
        assert bytecode == "0x6000"

    def test_artifact_path_uses_name_twice(self, monkeypatch, tmp_path):
        """Artifact path should be ARTIFACTS_DIR / {name}.sol / {name}.json."""
        gov_dir = tmp_path / "MeshGovernance.sol"
        gov_dir.mkdir(parents=True)
        artifact = gov_dir / "MeshGovernance.json"
        artifact.write_text(json.dumps({"abi": [], "bytecode": "0x00"}))

        monkeypatch.setattr(mod, "ARTIFACTS_DIR", tmp_path)
        abi, bytecode = mod.load_contract("MeshGovernance")
        assert abi == []
        assert bytecode == "0x00"


# ---------------------------------------------------------------------------
# Hardhat private key fallback tests
# ---------------------------------------------------------------------------

class TestHardhatKeyFallback:
    """Tests for the private-key fallback logic (lines 23-26).

    The condition on line 24 has an operator precedence bug:
        if not PRIVATE_KEY and "127.0.0.1" in RPC_URL or "localhost" in RPC_URL

    Python parses this as:
        (not PRIVATE_KEY and "127.0.0.1" in RPC_URL) or ("localhost" in RPC_URL)

    The intended logic is presumably:
        not PRIVATE_KEY and ("127.0.0.1" in RPC_URL or "localhost" in RPC_URL)

    The bug means the hardhat key is ALWAYS used when "localhost" appears in
    the URL, even if PRIVATE_KEY is already set.
    """

    def _reload_module_with_env(self, private_key, rpc_url):
        """Re-execute the module-level logic by reloading with controlled env.

        We patch dotenv.load_dotenv to no-op, set POLYGON_RPC and PRIVATE_KEY,
        then reload the module and return the resulting PRIVATE_KEY.
        """
        env = {"POLYGON_RPC": rpc_url}
        if private_key is not None:
            env["PRIVATE_KEY"] = private_key
        else:
            env.pop("PRIVATE_KEY", None)

        with mock.patch.dict(os.environ, env, clear=False):
            # Remove PRIVATE_KEY if we want it absent
            if private_key is None and "PRIVATE_KEY" in os.environ:
                del os.environ["PRIVATE_KEY"]
            with mock.patch("dotenv.load_dotenv"):
                with mock.patch.dict(sys.modules, {
                    "web3": sys.modules["web3"],
                    "web3.middleware": sys.modules["web3.middleware"],
                }):
                    import importlib
                    reloaded = importlib.reload(mod)
                    return reloaded.PRIVATE_KEY

    def test_no_key_with_127_uses_hardhat(self):
        """No PRIVATE_KEY + 127.0.0.1 URL -> hardhat key."""
        result = self._reload_module_with_env(None, "http://127.0.0.1:8545")
        assert result == HARDHAT_KEY

    def test_no_key_with_localhost_uses_hardhat(self):
        """No PRIVATE_KEY + localhost URL -> hardhat key."""
        result = self._reload_module_with_env(None, "http://localhost:8545")
        assert result == HARDHAT_KEY

    def test_no_key_with_remote_rpc_stays_none(self):
        """No PRIVATE_KEY + remote RPC -> stays None (no fallback)."""
        result = self._reload_module_with_env(None, "https://polygon-rpc.com")
        assert result is None

    def test_user_key_preserved_with_localhost(self):
        """PRIVATE_KEY is set + localhost URL -> user key must be preserved.

        The operator precedence bug was fixed by adding parentheses:
            not PRIVATE_KEY and ("127.0.0.1" in RPC_URL or "localhost" in RPC_URL)

        So when PRIVATE_KEY is set, the condition is False and the key is kept.
        """
        user_key = "0xUSER_PROVIDED_KEY_SHOULD_BE_KEPT"
        result = self._reload_module_with_env(user_key, "http://localhost:8545")
        assert result == user_key, (
            "User-provided key must be preserved when PRIVATE_KEY is set, "
            "even with 'localhost' in the URL."
        )

    def test_set_key_with_127_preserved(self):
        """PRIVATE_KEY is set + 127.0.0.1 -> key is preserved (no bug here).

        The first branch (not PRIVATE_KEY and "127.0.0.1" in RPC_URL) is False
        because PRIVATE_KEY is truthy. The second branch ("localhost" in RPC_URL)
        is also False. So the condition is False and the key is kept.
        """
        user_key = "0xUSER_PROVIDED_KEY"
        result = self._reload_module_with_env(user_key, "http://127.0.0.1:8545")
        assert result == user_key


# ---------------------------------------------------------------------------
# main() tests
# ---------------------------------------------------------------------------

class TestMain:
    """Tests for main() deployment flow."""

    def test_exits_when_private_key_missing(self, monkeypatch):
        monkeypatch.setattr(mod, "RPC_URL", "https://rpc.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", None)

        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        assert exc_info.value.code == 1

    def test_exits_when_rpc_unreachable(self, monkeypatch):
        class _DisconnectedWeb3(_FakeWeb3):
            def is_connected(self):
                return False

        monkeypatch.setattr(mod, "RPC_URL", "https://rpc.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "Web3", _DisconnectedWeb3)

        with pytest.raises(SystemExit) as exc_info:
            mod.main()
        assert exc_info.value.code == 1

    def test_success_writes_deployment_artifact(self, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        middleware = object()
        monkeypatch.setattr(mod, "geth_poa_middleware", middleware)
        monkeypatch.setattr(mod, "Web3", _FakeWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))

        times = iter([1_700_000_000.0, 1_700_000_000.0])

        def _fake_time():
            try:
                return next(times)
            except StopIteration:
                return 1_700_000_000.0

        monkeypatch.setattr(mod.time, "time", _fake_time)

        mod.main()

        deployment_file = tmp_path / "polygon_deployment_1700000000.json"
        assert deployment_file.exists()

        payload = json.loads(deployment_file.read_text())
        assert payload["network"] == "https://polygon.example"
        assert payload["deployer"] == "0xDeployer"
        assert payload["chain_id"] == 137
        assert payload["contracts"]["X0TToken"] == "0xToken"
        assert payload["contracts"]["MeshGovernance"] == "0xGovernance"

        web3_instance = _FakeWeb3.last_instance
        assert web3_instance is not None
        assert web3_instance.middleware_onion.calls == [(middleware, 0)]
        assert len(web3_instance.eth.sent) == 2

    def test_poa_middleware_injected_at_layer_zero(self, monkeypatch, tmp_path):
        """PoA middleware must be injected at layer 0."""
        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        sentinel = object()
        monkeypatch.setattr(mod, "geth_poa_middleware", sentinel)
        monkeypatch.setattr(mod, "Web3", _FakeWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))
        monkeypatch.setattr(mod.time, "time", lambda: 1_000_000.0)

        mod.main()

        w3 = _FakeWeb3.last_instance
        assert w3.middleware_onion.calls == [(sentinel, 0)]

    def test_governance_receives_token_address(self, monkeypatch, tmp_path):
        """MeshGovernance constructor must receive the token contract address."""
        call_log = []

        class _TrackingContract(_FakeContract):
            def constructor(self, *args):
                call_log.append(args)
                return super().constructor(*args)

        class _TrackingEth(_FakeEth):
            def contract(self, abi=None, bytecode=None):
                return _TrackingContract()

        class _TrackingWeb3(_FakeWeb3):
            def __init__(self, provider):
                super().__init__(provider)
                self.eth = _TrackingEth()

        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(mod, "Web3", _TrackingWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))
        monkeypatch.setattr(mod.time, "time", lambda: 1_000_000.0)

        mod.main()

        # First constructor call: X0TToken (no args)
        assert call_log[0] == ()
        # Second constructor call: MeshGovernance(token_address)
        assert call_log[1] == ("0xToken",)

    def test_gas_estimation_failure_uses_default(self, monkeypatch, tmp_path):
        """When estimate_gas raises, gas should default to 3_000_000."""
        built_txs = []

        class _FailGasEth(_FakeEth):
            def estimate_gas(self, _tx):
                raise RuntimeError("gas estimation failed")

        class _FailGasWeb3(_FakeWeb3):
            def __init__(self, provider):
                super().__init__(provider)
                self.eth = _FailGasEth()

        orig_sign = _FakeAccount.sign_transaction

        def _track_sign(self, tx):
            built_txs.append(tx)
            return orig_sign(self, tx)

        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(mod, "Web3", _FailGasWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))
        monkeypatch.setattr(mod.time, "time", lambda: 1_000_000.0)
        monkeypatch.setattr(_FakeAccount, "sign_transaction", _track_sign)

        mod.main()

        # Both txs should have default gas = 3_000_000
        for tx in built_txs:
            assert tx["gas"] == 3_000_000

    def test_gas_estimation_success_adds_ten_percent(self, monkeypatch, tmp_path):
        """Successful gas estimate should be multiplied by 1.1."""
        built_txs = []

        class _FixedGasEth(_FakeEth):
            def estimate_gas(self, _tx):
                return 100_000

        class _FixedGasWeb3(_FakeWeb3):
            def __init__(self, provider):
                super().__init__(provider)
                self.eth = _FixedGasEth()

        orig_sign = _FakeAccount.sign_transaction

        def _track_sign(self, tx):
            built_txs.append(tx)
            return orig_sign(self, tx)

        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(mod, "Web3", _FixedGasWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))
        monkeypatch.setattr(mod.time, "time", lambda: 1_000_000.0)
        monkeypatch.setattr(_FakeAccount, "sign_transaction", _track_sign)

        mod.main()

        # int(100_000 * 1.1) = 110_000
        for tx in built_txs:
            assert tx["gas"] == 110_000

    def test_zero_balance_does_not_abort(self, monkeypatch, tmp_path):
        """Deployment should proceed even when balance is zero (just warns)."""

        class _ZeroBalanceEth(_FakeEth):
            def get_balance(self, _address):
                return 0

        class _ZeroBalanceWeb3(_FakeWeb3):
            def __init__(self, provider):
                super().__init__(provider)
                self.eth = _ZeroBalanceEth()

        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(mod, "Web3", _ZeroBalanceWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))
        monkeypatch.setattr(mod.time, "time", lambda: 1_000_000.0)

        # Should not raise
        mod.main()

        # Deployment file should still be written
        files = list(tmp_path.glob("polygon_deployment_*.json"))
        assert len(files) == 1

    def test_deployment_json_contains_timestamp(self, monkeypatch, tmp_path):
        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(mod, "Web3", _FakeWeb3)
        monkeypatch.setattr(mod, "load_contract", lambda _name: ([], "0x6000"))
        monkeypatch.setattr(mod.time, "time", lambda: 1_700_000_000.0)

        mod.main()

        deployment_file = tmp_path / "polygon_deployment_1700000000.json"
        payload = json.loads(deployment_file.read_text())
        assert payload["timestamp"] == 1_700_000_000.0

    def test_two_contracts_deployed_in_order(self, monkeypatch, tmp_path):
        """load_contract must be called first for X0TToken then MeshGovernance."""
        names_loaded = []

        def _tracking_load(name):
            names_loaded.append(name)
            return ([], "0x6000")

        monkeypatch.setattr(mod, "RPC_URL", "https://polygon.example")
        monkeypatch.setattr(mod, "PRIVATE_KEY", "0xabc")
        monkeypatch.setattr(mod, "DEPLOYMENTS_DIR", tmp_path)
        monkeypatch.setattr(mod, "Web3", _FakeWeb3)
        monkeypatch.setattr(mod, "load_contract", _tracking_load)
        monkeypatch.setattr(mod.time, "time", lambda: 1_000_000.0)

        mod.main()

        assert names_loaded == ["X0TToken", "MeshGovernance"]
