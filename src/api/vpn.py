from .maas.endpoints import vpn as modular
router = modular.router
from .maas.endpoints.vpn import *
from .maas.endpoints.vpn import (
    _get_vpn_server,
    _get_vpn_port,
    _build_vpn_config,
    _enforce_permission_if_authenticated,
    _check_vpn_connectivity,
)
