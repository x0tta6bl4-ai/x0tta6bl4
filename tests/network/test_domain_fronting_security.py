"""
Регрессионный тест безопасности для CVE-2026-DF-001.

Гарантирует, что DomainFrontingTransport всегда использует проверку
сертификатов сервера и никогда не принимает ssl.CERT_NONE.
"""
import ssl
import pytest
from src.network.obfuscation.domain_fronting import DomainFrontingTransport


class TestDomainFrontingCertVerification:
    """CVE-2026-DF-001: cert verification must never be disabled."""

    def test_check_hostname_enabled_by_default(self):
        """check_hostname=True должно быть установлено по умолчанию."""
        transport = DomainFrontingTransport.__new__(DomainFrontingTransport)
        DomainFrontingTransport.__init__(
            transport,
            front_domain="cdn.example.com",
            backend_host="hidden.backend",
        )
        assert transport.context.check_hostname is True, (
            "CVE-2026-DF-001 regression: check_hostname must be True"
        )

    def test_verify_mode_is_cert_required_by_default(self):
        """verify_mode=CERT_REQUIRED должен быть установлен по умолчанию."""
        transport = DomainFrontingTransport.__new__(DomainFrontingTransport)
        DomainFrontingTransport.__init__(
            transport,
            front_domain="cdn.example.com",
            backend_host="hidden.backend",
        )
        assert transport.context.verify_mode == ssl.CERT_REQUIRED, (
            "CVE-2026-DF-001 regression: verify_mode must be CERT_REQUIRED"
        )

    def test_tls_minimum_version_is_tls12(self):
        """Минимальная версия TLS должна быть 1.2+."""
        transport = DomainFrontingTransport.__new__(DomainFrontingTransport)
        DomainFrontingTransport.__init__(
            transport,
            front_domain="cdn.example.com",
            backend_host="hidden.backend",
        )
        assert transport.context.minimum_version >= ssl.TLSVersion.TLSv1_2

    def test_cert_none_raises_or_is_overridden(self):
        """Передача CERT_NONE должна быть отклонена или перезаписана."""
        transport = DomainFrontingTransport.__new__(DomainFrontingTransport)
        try:
            DomainFrontingTransport.__init__(
                transport,
                front_domain="cdn.example.com",
                backend_host="hidden.backend",
                verify_mode=ssl.CERT_NONE,
            )
            # Если не исключение — verify_mode должен быть перезаписан
            assert transport.context.verify_mode != ssl.CERT_NONE, (
                "CERT_NONE must not be accepted"
            )
        except (ValueError, ssl.SSLError):
            pass  # Корректное поведение — отклонить небезопасный режим
