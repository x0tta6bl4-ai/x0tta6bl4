from __future__ import annotations

import sys

import src.licensing as licensing


def test_licensing_package_exports_node_identity_lazily() -> None:
    licensing.__dict__.pop("LicenseAuthority", None)
    sys.modules.pop("src.licensing.node_identity", None)

    assert "LicenseAuthority" in licensing.__all__
    assert "NodeLicenseManager" in licensing.__all__
    assert "DeviceFingerprint" in licensing.__all__
    assert "src.licensing.node_identity" not in sys.modules

    assert licensing.LicenseAuthority.__name__ == "LicenseAuthority"
    assert "src.licensing.node_identity" in sys.modules
