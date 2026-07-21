"""Vision cache."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import time
from typing import Any, Dict, Optional, Tuple


@dataclass
class VisionCache:
    """Minimal cache shim matching the public test contract."""

    max_size: int = 1000
    ttl_seconds: float = 3600.0

    def __post_init__(self) -> None:
        self._items: Dict[str, Tuple[Any, float]] = {}
        self._order: list[str] = []

    def _make_key(self, data: bytes, operation: str) -> str:
        return hashlib.sha256(data + operation.encode("utf-8")).hexdigest()[:32]

    def get(self, data: bytes, operation: str) -> Optional[Any]:
        key = self._make_key(data, operation)
        entry = self._items.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            self._items.pop(key, None)
            if key in self._order:
                self._order.remove(key)
            return None
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)
        return value

    def set(self, data: bytes, operation: str, result: Any) -> None:
        key = self._make_key(data, operation)
        expires_at = time.time() + self.ttl_seconds if self.ttl_seconds else float("inf")
        self._items[key] = (result, expires_at)
        if key in self._order:
            self._order.remove(key)
        self._order.append(key)
        while len(self._items) > self.max_size:
            oldest = self._order.pop(0)
            self._items.pop(oldest, None)

    def get_stats(self) -> Dict[str, Any]:
        return {"size": len(self._items), "max_size": self.max_size}
