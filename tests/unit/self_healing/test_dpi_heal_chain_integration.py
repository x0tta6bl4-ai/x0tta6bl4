"""End-to-end wiring: DPI_BLOCK_DETECTED -> planner -> clash-api switch.

Proves the whole A->P->E chain composes with the real planner, the real
executor adapter, and the real ClashApiSelectorBackend (against an in-memory
clash-api). Only the network edge is faked; every decision object is real.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pytest

from src.coordination.events import EventBus, EventType

planner_mod = pytest.importorskip("src.self_healing.dpi_healing_planner")
switch_mod = pytest.importorskip("src.self_healing.singbox_switch")

DpiHealingPlanner = planner_mod.DpiHealingPlanner
ClashApiSelectorBackend = switch_mod.ClashApiSelectorBackend
SwitchProtocolExecutor = switch_mod.SwitchProtocolExecutor


class _FakeClash:
    def __init__(self, now: str = "nl-reality") -> None:
        self.now = now

    def __call__(self, method: str, url: str, body: Optional[Dict[str, Any]]):
        if method == "PUT":
            self.now = body["name"]
            return 204, None
        return 200, {"now": self.now}


def test_high_confidence_block_switches_transport_end_to_end(tmp_path):
    bus = EventBus(str(tmp_path))
    fake = _FakeClash(now="nl-reality")
    backend = ClashApiSelectorBackend(
        controller="127.0.0.1:10924",
        selector_tag="ghost-test-selector",
        protocol_to_tag={"reality": "nl-reality", "xhttp": "nl-xhttp", "cf-tunnel": "nl-cf"},
        test_profile="ghost-test-canary",
        http=fake,
    )
    planner = DpiHealingPlanner(
        bus,
        SwitchProtocolExecutor(backend),
        test_profile="ghost-test-canary",
    )
    planner.subscribe()

    # Detector (Phase 0) reports reality was reset mid-stream, high confidence.
    bus.publish(
        EventType.DPI_BLOCK_DETECTED,
        "tspu-detector",
        {"confidence": 0.97, "current_transport": "reality"},
    )

    # The loop climbed reality -> xhttp on the throwaway test profile only.
    assert fake.now == "nl-xhttp"
    assert backend.switch_log[-1]["ok"] is True
    assert backend.switch_log[-1]["profile"] == "ghost-test-canary"


def test_low_confidence_block_does_not_switch(tmp_path):
    bus = EventBus(str(tmp_path))
    fake = _FakeClash(now="nl-reality")
    backend = ClashApiSelectorBackend(
        controller="127.0.0.1:10924",
        selector_tag="ghost-test-selector",
        protocol_to_tag={"reality": "nl-reality", "xhttp": "nl-xhttp"},
        test_profile="ghost-test-canary",
        http=fake,
    )
    planner = DpiHealingPlanner(bus, SwitchProtocolExecutor(backend), test_profile="ghost-test-canary")
    planner.subscribe()

    bus.publish(
        EventType.DPI_BLOCK_DETECTED,
        "tspu-detector",
        {"confidence": 0.4, "current_transport": "reality"},
    )

    assert fake.now == "nl-reality"  # observe-only, no switch
    assert backend.switch_log == []
