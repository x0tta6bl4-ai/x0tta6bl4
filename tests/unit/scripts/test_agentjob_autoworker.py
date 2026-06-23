from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentjob_autoworker.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agentjob_autoworker", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_maybe_withdraw_skips_below_minimum(monkeypatch) -> None:
    mod = _load_module()

    def fake_mcp(api_key, name, arguments, *, request_id=1):
        assert name == "get_my_profile"
        return {
            "response": {
                "result": {
                    "content": [
                        {
                            "text": (
                                '{"agent_id":"agent-1","wallet_address":"0xabc",'
                                '"wallet_balance":{"usdc":"0.50"},'
                                '"stats":{"total_revenue_usdc":0.5}}'
                            )
                        }
                    ]
                }
            }
        }

    monkeypatch.setattr(mod, "_mcp", fake_mcp)

    result = mod._maybe_withdraw_usdc(
        "ak_test",
        target_wallet="0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
        min_usdc=1.0,
    )

    assert result["attempted"] is False
    assert result["reason"] == "below_minimum"
    assert result["available_usdc"] == 0.5


def test_maybe_withdraw_calls_agentjob_tool(monkeypatch) -> None:
    mod = _load_module()
    calls = []

    def fake_mcp(api_key, name, arguments, *, request_id=1):
        calls.append((name, arguments))
        if name == "get_my_profile":
            return {
                "response": {
                    "result": {
                        "content": [
                            {
                                "text": (
                                    '{"agent_id":"agent-1","wallet_address":"0xabc",'
                                    '"wallet_balance":{"usdc":"2.25"},'
                                    '"stats":{"total_revenue_usdc":2.25}}'
                                )
                            }
                        ]
                    }
                }
            }
        if name == "withdraw_usdc":
            return {
                "ok": True,
                "response": {
                    "result": {
                        "content": [
                            {
                                "text": '{"ok":true,"txHash":"0xwithdraw"}',
                            }
                        ]
                    }
                },
            }
        raise AssertionError(name)

    monkeypatch.setattr(mod, "_mcp", fake_mcp)

    result = mod._maybe_withdraw_usdc(
        "ak_test",
        target_wallet="0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
        min_usdc=1.0,
        amount_usdc=1.5,
    )

    assert result["attempted"] is True
    assert result["amount_usdc"] == "1.5"
    assert result["withdraw_result"]["txHash"] == "0xwithdraw"
    assert calls[-1] == (
        "withdraw_usdc",
        {
            "toAddress": "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099",
            "amount": "1.5",
        },
    )
