import binascii
import importlib
import os
import sys

import fastapi
import httpx
import pytest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../../src"))
)

from core import app


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_pqc_status_endpoint():
    transport = httpx.ASGITransport(app=app.app)
    async with httpx.AsyncClient(
        transport=transport, base_url="http://testserver"
    ) as client:
        resp = await client.get("/pqc/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "liboqs_available" in data
    if data["liboqs_available"]:
        assert data["public_key"] is not None
        assert len(data["public_key"]) > 10
        assert data["algorithm"] == "ML-DSA-65"
    else:
        assert data["public_key"] is None


# Optionally: test PQC sign/verify if liboqs is available
@pytest.mark.skipif(not hasattr(app, "pqc_sign"), reason="PQC not available")
def test_pqc_sign_and_verify():
    if not hasattr(app, "pqc_sign") or not hasattr(app, "pqc_verify"):
        pytest.skip("PQC not available")
    msg = b"test-message"
    sig = app.pqc_sign(msg)
    pub = app._pqc_sig_public_key
    print(f"[TEST] msg={msg!r} (len={len(msg)})")
    print(f"[TEST] sig={sig.hex()} (len={len(sig)})")
    print(f"[TEST] pub={pub.hex()} (len={len(pub)})")
    assert isinstance(sig, bytes)
    assert len(sig) > 0
    assert isinstance(pub, bytes)
    assert len(pub) > 0
    result = app.pqc_verify(msg, sig, pub)
    print(f"[TEST] pqc_verify result: {result}")
    assert result
