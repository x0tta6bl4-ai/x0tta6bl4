import asyncio
from types import SimpleNamespace

import pytest


@pytest.mark.asyncio
async def test_setup_mtls_context_writes_files_and_configures_context(
    monkeypatch, tmp_path
):
    from src.security.spiffe.mtls.mtls_controller_production import \
        MTLSControllerProduction

    class _SVID:
        cert_pem = b"CERT"
        private_key_pem = b"KEY"
        cert_chain = [b"CA"]
        expiry = None

    class _Workload:
        async def fetch_x509_svid(self):
            return _SVID()

    ctrl = MTLSControllerProduction(_Workload(), enable_optimizations=False)

    # Stub SSLContext
    class _Ctx:
        def __init__(self):
            self.minimum_version = None
            self.maximum_version = None
            self.verify_mode = None
            self.verify_flags = None
            self.loaded_chain = None
            self.loaded_ca = None
            self.ciphers = None
            self.check_hostname = None

        def load_cert_chain(self, certfile, keyfile):
            self.loaded_chain = (certfile, keyfile)

        def load_verify_locations(self, cafile=None, capath=None, cadata=None):
            self.loaded_ca = cafile

        def set_ciphers(self, c):
            self.ciphers = c

    monkeypatch.setattr(
        "src.security.spiffe.mtls.mtls_controller_production.ssl.create_default_context",
        lambda purpose: _Ctx(),
    )

    # Avoid real tempfiles
    monkeypatch.setattr(ctrl, "_write_temp_cert", lambda b: str(tmp_path / "c.pem"))
    monkeypatch.setattr(ctrl, "_write_temp_key", lambda b: str(tmp_path / "k.pem"))
    monkeypatch.setattr(ctrl, "_write_temp_ca", lambda b: str(tmp_path / "ca.pem"))

    ctx = await ctrl.setup_mtls_context()

    assert ctx.loaded_chain == (str(tmp_path / "c.pem"), str(tmp_path / "k.pem"))
    assert ctx.loaded_ca == str(tmp_path / "ca.pem")
    assert ctrl.current_context is ctx


@pytest.mark.asyncio
async def test_start_creates_rotation_task_and_stop_cleans_up(monkeypatch):
    from src.security.spiffe.mtls.mtls_controller_production import \
        MTLSControllerProduction

    class _Workload:
        async def fetch_x509_svid(self):
            return SimpleNamespace(cert_pem=b"C", private_key_pem=b"K", cert_chain=[])

    ctrl = MTLSControllerProduction(
        _Workload(), rotation_interval=1, enable_optimizations=False
    )

    monkeypatch.setattr(ctrl, "setup_mtls_context", lambda: asyncio.sleep(0))

    await ctrl.start()
    assert ctrl._rotation_task is not None

    # Seed temp files list
    ctrl._temp_files = [SimpleNamespace(name="/tmp/a"), SimpleNamespace(name="/tmp/b")]
    deleted = []
    monkeypatch.setattr(
        "src.security.spiffe.mtls.mtls_controller_production.os.unlink",
        lambda p: deleted.append(p),
    )

    await ctrl.stop()
    assert "/tmp/a" in deleted
    assert "/tmp/b" in deleted
    assert ctrl._temp_files == []
