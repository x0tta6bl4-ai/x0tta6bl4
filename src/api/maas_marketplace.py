"""Compatibility alias for the modular MaaS marketplace endpoint.

The real implementation lives in ``src.api.maas.endpoints.marketplace``.  Keep
this module name as an alias so older imports and monkeypatches mutate the same
module globals used by the endpoint functions.
"""

from __future__ import annotations

import sys

from .maas.endpoints import marketplace as _marketplace

_parent = sys.modules.get(__name__.rsplit(".", 1)[0])
if _parent is not None:
    setattr(_parent, "maas_marketplace", _marketplace)

sys.modules[__name__] = _marketplace
