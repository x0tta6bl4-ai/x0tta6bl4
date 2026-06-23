from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

os.environ.setdefault("X0TTA6BL4_PRODUCTION", "false")
os.environ.setdefault("X0TTA6BL4_SPIFFE", "false")
os.environ.setdefault("X0TTA6BL4_FORCE_MOCK_SPIFFE", "true")

import libx0t.network.proxy_orchestrator as mod
from libx0t.network.residential_proxy_manager import ProxyStatus


@pytest.mark.asyncio
async def test_libx0t_proxy_orchestrator_thinking_health_report_redacts_path():
    orchestrator = mod.ProxyOrchestrator(
        config_path="/secret/full/proxy-config.yaml",
        environment="production",
    )
    orchestrator.proxy_manager = SimpleNamespace(
        proxies=[
            SimpleNamespace(id="proxy-secret-id", status=ProxyStatus.HEALTHY),
            SimpleNamespace(id="proxy-other-secret-id", status=ProxyStatus.BANNED),
        ]
    )

    await orchestrator._update_status()
    report = await orchestrator.get_health_report()

    status = report["thinking"]
    assert status["thinking"]["profile"]["role"] == "ops"
    assert "mape_k" in status["thinking"]["techniques"]
    assert (
        status["last_thinking_context"]["applied"]["framing"]["problem"]
        == "libx0t_proxy_orchestrator_health_report"
    )
    assert report["proxies"]["total"] == 2
    assert report["proxies"]["by_status"]["healthy"] == 1

    rendered = repr(status)
    assert "/secret/full/proxy-config.yaml" not in rendered
    assert "proxy-secret-id" not in rendered
    assert "proxy-other-secret-id" not in rendered
