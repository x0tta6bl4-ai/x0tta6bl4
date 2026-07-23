"""
Fast JSON serialization adapter for high-throughput Swarm messaging.

Attempts to use orjson for high performance, falling back to stdlib json.
"""
from __future__ import annotations

from typing import Any

try:
    import orjson

    def dumps(obj: Any, sort_keys: bool = False, *args: Any, **kwargs: Any) -> str:
        """Serialize object to JSON string using orjson."""
        option = orjson.OPT_SORT_KEYS if sort_keys else 0
        return orjson.dumps(obj, option=option).decode("utf-8")

    def loads(s: str | bytes, *args: Any, **kwargs: Any) -> Any:
        """Deserialize JSON string or bytes using orjson."""
        return orjson.loads(s)

    HAS_ORJSON = True
except ImportError:
    import json

    def dumps(obj: Any, *args: Any, **kwargs: Any) -> str:
        """Serialize object to JSON string using stdlib json."""
        if "default" not in kwargs:
            kwargs["default"] = str
        return json.dumps(obj, *args, **kwargs)

    def loads(s: str | bytes, *args: Any, **kwargs: Any) -> Any:
        """Deserialize JSON string or bytes using stdlib json."""
        return json.loads(s, *args, **kwargs)

    HAS_ORJSON = False
