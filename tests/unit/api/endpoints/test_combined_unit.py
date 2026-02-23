"""Unit tests for src/api/maas/endpoints/combined.py."""

from src.api.maas.endpoints.combined import get_combined_router


def _route_paths(router):
    return {route.path for route in router.routes}


def test_get_combined_router_default_includes_all_domains():
    paths = _route_paths(get_combined_router())

    assert any(path.startswith("/api/v1/maas/auth/") for path in paths)
    assert any(path.startswith("/api/v1/maas/mesh/") for path in paths)
    assert any(path.startswith("/api/v1/maas/nodes/") for path in paths)
    assert any(path.startswith("/api/v1/maas/billing/") for path in paths)


def test_get_combined_router_respects_include_flags():
    router = get_combined_router(
        include_auth=False,
        include_mesh=True,
        include_nodes=False,
        include_billing=False,
    )
    paths = _route_paths(router)

    assert any(path.startswith("/api/v1/maas/mesh/") for path in paths)
    assert not any(path.startswith("/api/v1/maas/auth/") for path in paths)
    assert not any(path.startswith("/api/v1/maas/nodes/") for path in paths)
    assert not any(path.startswith("/api/v1/maas/billing/") for path in paths)


def test_get_combined_router_applies_custom_prefix():
    router = get_combined_router(prefix="/custom/maas")
    paths = _route_paths(router)

    assert paths  # sanity
    assert all(path.startswith("/custom/maas/") for path in paths)

