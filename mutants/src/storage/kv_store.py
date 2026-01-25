"""
Distributed Key-Value Store (P1)
Scaffold for mesh-based storage in x0tta6bl4
"""
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

class KVStore:
    def __init__(self):
        self.store: Dict[str, Any] = {}
    def put(self, key: str, value: Any):
        self.store[key] = value
        logger.info(f"Put key={key} value={value}")
    def get(self, key: str) -> Any:
        return self.store.get(key)
    def delete(self, key: str):
        if key in self.store:
            del self.store[key]
            logger.info(f"Deleted key={key}")
