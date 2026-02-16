from starlette.requests import Request

from src.core.mtls_middleware import MTLSValidator


def _request_with_scope(scope_overrides=None):
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/secure",
        "headers": [],
        "query_string": b"",
        "client": ("127.0.0.1", 12345),
    }
    if scope_overrides:
        scope.update(scope_overrides)
    return Request(scope)


def test_extract_client_cert_does_not_trust_client_scope_only():
    validator = MTLSValidator()
    request = _request_with_scope()
    cert = validator.extract_client_cert_from_request(request)
    assert cert is None


def test_validate_tls_version_accepts_tls13_from_ssl_object():
    class DummySSL:
        def version(self):
            return "TLSv1.3"

    validator = MTLSValidator()
    request = _request_with_scope({"ssl_object": DummySSL()})
    is_valid, version = validator.validate_tls_version(request)
    assert is_valid is True
    assert version == "TLSv1.3"


def test_validate_tls_version_rejects_tls12():
    class DummySSL:
        def version(self):
            return "TLSv1.2"

    validator = MTLSValidator()
    request = _request_with_scope({"ssl_object": DummySSL()})
    is_valid, version = validator.validate_tls_version(request)
    assert is_valid is False
    assert "TLSv1.2" in version
