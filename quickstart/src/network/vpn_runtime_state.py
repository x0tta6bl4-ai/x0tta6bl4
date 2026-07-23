from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass
from enum import Enum


class TunnelStatus(Enum):
    CONNECTING = "CONNECTING"
    ESTABLISHED = "ESTABLISHED"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"

@dataclass
class SessionInfo:
    session_id: str
    peer_address: str
    bytes_sent: int = 0
    bytes_received: int = 0
    status: TunnelStatus = TunnelStatus.CONNECTING

class VPNRuntimeState:
    """
    Thread-safe VPN runtime state management.
    Реализовано.
    """
    def __init__(self):
        self._lock = threading.RLock()
        self.sessions: dict[str, SessionInfo] = {}
        self.active_profile: str = "default"

    def add_session(self, session: SessionInfo) -> None:
        """Add a new VPN session."""
        with self._lock:
            self.sessions[session.session_id] = session

    def update_status(self, session_id: str, status: TunnelStatus) -> None:
        """Update the status of an existing session."""
        with self._lock:
            if session_id in self.sessions:
                self.sessions[session_id].status = status

    def switch_profile(self, profile: str) -> None:
        """Switch the active VPN profile."""
        with self._lock:
            self.active_profile = profile

    def to_json(self) -> str:
        """Serialize state for monitoring."""
        with self._lock:
            data = {
                "active_profile": self.active_profile,
                "sessions": {k: asdict(v) for k, v in self.sessions.items()}
            }
            for session in data["sessions"].values():
                session["status"] = session["status"].value
            return json.dumps(data)
