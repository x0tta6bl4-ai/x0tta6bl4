from .maas.endpoints import agent_mesh as modular
router = modular.router
from .maas.endpoints.agent_mesh import *
from .maas.endpoints.agent_mesh import _health_bot
