"""Mobile bridge — SDK stubs for mesh + mobile agent tests."""

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional


class MobileBridgeClient:
    """Stub for mobile bridge client."""

    def __init__(self, *args, **kwargs):
        pass

    async def connect(self, *args, **kwargs) -> bool:
        return True

    async def send_message(self, *args, **kwargs) -> dict:
        return {"sent": True}


class MobileMeshAgent:
    """Test-compatible stub for mobile mesh agent."""

    def __init__(self, mesh_id: str, token: str, *args: Any, **kwargs: Any) -> None:
        self.mesh_id = mesh_id
        self.token = token
        self.is_running = False
        self._thread: Optional[threading.Thread] = None
        self._status: Dict[str, Any] = {
            "connected": False,
            "pqc_active": True,
            "neighbor_count": 0,
            "battery_mode": "eco",
        }

    def get_status(self) -> Dict[str, Any]:
        return dict(self._status)

    def _mesh_loop(self) -> None:
        while self.is_running:
            self._status.update(
                {
                    "connected": True,
                    "neighbor_count": 2,
                }
            )
            time.sleep(0.05)

    def start(self) -> int:
        if self._thread is not None and self._thread.is_alive():
            return 1
        self.is_running = True
        self._thread = threading.Thread(target=self._mesh_loop, daemon=True)
        self._thread.start()
        return 0

    def stop(self) -> None:
        self.is_running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None


def x0t_mobile_init(mesh_id: str, token: str) -> MobileMeshAgent:
    """Factory used by SDK tests."""
    return MobileMeshAgent(mesh_id=mesh_id, token=token)
