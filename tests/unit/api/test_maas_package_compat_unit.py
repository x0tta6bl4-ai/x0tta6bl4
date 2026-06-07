from __future__ import annotations

import importlib
import sys


def test_maas_billing_import_is_not_blocked_by_lazy_legacy_metering() -> None:
    sys.modules.pop("src.api.maas_billing", None)

    billing = importlib.import_module("src.api.maas_billing")

    assert hasattr(billing, "router")
    assert "router" in billing.__all__
    assert "pay_invoice_manual" in billing.__all__


def test_maas_package_declares_legacy_metering_compat_exports() -> None:
    maas_pkg = importlib.import_module("src.api.maas")

    assert "usage_metering_service" in maas_pkg.__all__
    assert "_get_mesh_or_404" in maas_pkg.__all__


def test_maas_marketplace_import_is_modular_endpoint_alias() -> None:
    sys.modules.pop("src.api.maas_marketplace", None)

    marketplace = importlib.import_module("src.api.maas_marketplace")
    modular = importlib.import_module("src.api.maas.endpoints.marketplace")

    assert marketplace is modular
    assert hasattr(marketplace, "rent_node")
    assert hasattr(marketplace, "release_escrow")
    assert hasattr(marketplace, "refund_escrow")
    assert hasattr(marketplace, "_token_bridge")
