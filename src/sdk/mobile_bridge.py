"""Mobile bridge — stubs for SDK tests."""

from __future__ import annotations

from typing import Any


class MobileBridgeClient:
    """Stub for mobile bridge client."""
    def __init__(self, *args, **kwargs):
        pass

    async def connect(self, *args, **kwargs) -> bool:
        return True

    async def send_message(self, *args, **kwargs) -> dict:
        return {"sent": True}
