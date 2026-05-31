"""Compatibility wrapper for the modular MaaS governance endpoint."""

from .maas.endpoints import governance as modular
from .maas.endpoints.governance import *  # noqa: F401,F403

router = modular.router

for _name in dir(modular):
    if not _name.startswith("__"):
        globals()[_name] = getattr(modular, _name)
