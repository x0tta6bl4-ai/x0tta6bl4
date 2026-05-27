from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


def _load_module():
    repo_root = Path(__file__).resolve().parents[3]
    script_path = repo_root / "scripts" / "validate_payment_verification.py"
    spec = importlib.util.spec_from_file_location("validate_payment_verification", script_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Failed to load validate_payment_verification module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_configure_wallets_rejects_missing_values(monkeypatch):
    module = _load_module()
    monkeypatch.delenv("USDT_TRC20_WALLET", raising=False)
    monkeypatch.delenv("TON_WALLET", raising=False)

    with pytest.raises(ValueError, match="USDT_TRC20_WALLET is required"):
        module.configure_wallets_from_env()


def test_configure_wallets_rejects_placeholder_values(monkeypatch):
    module = _load_module()
    monkeypatch.setenv("USDT_TRC20_WALLET", "TYourWalletAddressHere")
    monkeypatch.setenv("TON_WALLET", "UQYourTonWalletAddressHere")

    with pytest.raises(ValueError, match="placeholder wallet"):
        module.configure_wallets_from_env()


def test_configure_wallets_updates_bot_config(monkeypatch):
    module = _load_module()
    usdt_wallet = "T" + "a" * 33
    ton_wallet = "UQ" + "b" * 46
    monkeypatch.setenv("USDT_TRC20_WALLET", usdt_wallet)
    monkeypatch.setenv("TON_WALLET", ton_wallet)

    assert module.configure_wallets_from_env() == (usdt_wallet, ton_wallet)
    assert module.Config.USDT_TRC20_WALLET == usdt_wallet
    assert module.Config.TON_WALLET == ton_wallet


def test_mask_wallet_hides_middle():
    module = _load_module()

    assert module._mask_wallet("T123456789abcdef") == "T12345...cdef"
