"""
mTLS middleware for FastAPI with TLS 1.3 enforcement
Обеспечивает:
- Обязательная валидация клиентских сертификатов
- Принуждение TLS 1.3+
- Проверка SPIFFE SVID
- Валидация истечения сертификата
- Логирование и метрики
"""

import logging
import ipaddress
import ssl
from datetime import datetime
from typing import Any, Callable, Optional
from urllib.parse import unquote

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

logger = logging.getLogger(__name__)


class MTLSValidator:
    """Валидатор mTLS сертификатов"""

    def __init__(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True,
        trust_proxy_headers: bool = True,
        trusted_proxy_cidrs: Optional[list[str]] = None,
        require_proxy_verified_header: bool = True,
        allow_unknown_tls: bool = False,
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
        self.trust_proxy_headers = trust_proxy_headers
        self.require_proxy_verified_header = require_proxy_verified_header
        self.allow_unknown_tls = allow_unknown_tls

        default_proxy_cidrs = [
            "127.0.0.1/32",
            "::1/128",
            "10.0.0.0/8",
            "172.16.0.0/12",
            "192.168.0.0/16",
        ]
        self.trusted_proxy_networks = []
        for cidr in trusted_proxy_cidrs or default_proxy_cidrs:
            try:
                self.trusted_proxy_networks.append(
                    ipaddress.ip_network(cidr, strict=False)
                )
            except ValueError:
                logger.warning(f"Ignoring invalid trusted proxy CIDR: {cidr}")

    def _is_request_from_trusted_proxy(self, request: Request) -> bool:
        """Проверить, что запрос пришел от доверенного reverse proxy."""
        if request.client is None or not request.client.host:
            return False

        try:
            client_ip = ipaddress.ip_address(request.client.host)
        except ValueError:
            logger.warning(f"Unable to parse client host as IP: {request.client.host}")
            return False

        return any(client_ip in network for network in self.trusted_proxy_networks)

    @staticmethod
    def _normalize_tls_version(tls_version: str) -> Optional[str]:
        """Нормализовать версию TLS к виду TLSv1.x."""
        if not tls_version:
            return None

        normalized = tls_version.strip().upper().replace("_", ".")
        mappings = {
            "TLSV1.0": "TLSv1.0",
            "TLS1.0": "TLSv1.0",
            "TLSV1.1": "TLSv1.1",
            "TLS1.1": "TLSv1.1",
            "TLSV1.2": "TLSv1.2",
            "TLS1.2": "TLSv1.2",
            "TLSV1.3": "TLSv1.3",
            "TLS1.3": "TLSv1.3",
        }
        return mappings.get(normalized)

    def extract_client_cert_from_request(
        self, request: Request
    ) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.

        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из SSL объекта (надежный источник при direct TLS)
            ssl_obj = request.scope.get("ssl_object")
            if ssl_obj is not None and hasattr(ssl_obj, "getpeercert"):
                try:
                    cert_der = ssl_obj.getpeercert(binary_form=True)
                    if cert_der:
                        return x509.load_der_x509_certificate(
                            cert_der, default_backend()
                        )
                except Exception as e:
                    logger.warning(f"Failed to read peer cert from ssl_object: {e}")

            # Попытка получить из заголовка (от nginx reverse proxy)
            cert_header = request.headers.get("X-SSL-Client-Cert") or request.headers.get(
                "SSL_CLIENT_CERT"
            )
            if cert_header:
                if not self.trust_proxy_headers:
                    logger.warning("Proxy certificate headers are disabled")
                    return None

                if not self._is_request_from_trusted_proxy(request):
                    logger.warning(
                        "Rejecting client cert header from untrusted source: %s",
                        request.client.host if request.client else "unknown",
                    )
                    return None

                if self.require_proxy_verified_header:
                    verification_status = (
                        request.headers.get("X-SSL-Client-Verify", "")
                        .strip()
                        .upper()
                    )
                    if verification_status not in {"SUCCESS", "OK", "VERIFIED"}:
                        logger.warning(
                            "Rejecting client cert header without proxy verification status"
                        )
                        return None

                # Декодировать PEM сертификат
                try:
                    cert_value = unquote(cert_header).strip()
                    if "BEGIN CERTIFICATE" in cert_value:
                        cert_pem = cert_value
                    else:
                        cert_pem = f"-----BEGIN CERTIFICATE-----\n{cert_value}\n-----END CERTIFICATE-----"
                    cert = x509.load_pem_x509_certificate(
                        cert_pem.encode(), default_backend()
                    )
                    return cert
                except Exception as e:
                    logger.warning(f"Failed to parse client cert from header: {e}")
                    return None

            return None
        except Exception as e:
            logger.error(f"Error extracting client cert: {e}")
            return None

    def validate_spiffe_svid(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать SPIFFE SVID из сертификата.

        Returns: (is_valid, spiffe_id)
        """
        try:
            # Ищем SAN расширение с SPIFFE ID
            san_ext = cert.extensions.get_extension_for_oid(
                x509.oid.ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            )

            for name in san_ext.value:
                if isinstance(name, x509.UniformResourceIdentifier):
                    uri = name.value
                    if uri.startswith("spiffe://"):
                        # Валидировать домен
                        domain = uri.split("/")[2]  # spiffe://domain/...
                        if domain in self.allowed_spiffe_domains:
                            return True, uri
                        else:
                            logger.warning(f"Invalid SPIFFE domain: {domain}")
                            return False, uri

            logger.warning("No SPIFFE SVID found in certificate")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"

    def validate_cert_expiry(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать не истекщен ли сертификат.

        Returns: (is_valid, expiry_info)
        """
        try:
            now = datetime.utcnow()
            not_valid_after = cert.not_valid_after

            if now > not_valid_after:
                logger.error(f"Certificate expired at {not_valid_after}")
                return False, f"expired at {not_valid_after}"

            # Предупреждение если истекает в течении 7 дней
            days_until_expiry = (not_valid_after - now).days
            if days_until_expiry < 7:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")

            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"

    def validate_tls_version(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.

        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None

            # Starlette/ASGI стандарт
            if "ssl_object" in request.scope:
                ssl_obj = request.scope["ssl_object"]
                if hasattr(ssl_obj, "version"):
                    v = ssl_obj.version
                    tls_version = v() if callable(v) else v

            # Попытка из заголовка (от nginx)
            if not tls_version:
                tls_version = request.headers.get("X-SSL-Protocol", "unknown")

            normalized_version = self._normalize_tls_version(str(tls_version))
            required_version = self._normalize_tls_version(self.min_tls_version)
            if required_version is None:
                required_version = self._normalize_tls_version(
                    f"TLSv{self.min_tls_version}"
                )
            if required_version is None:
                required_version = "TLSv1.3"

            if normalized_version is None:
                if self.allow_unknown_tls:
                    logger.debug(
                        "TLS version info not available (allowed by configuration)"
                    )
                    return True, "unknown (allowed)"
                logger.error("TLS version info is missing")
                return False, "unknown"

            tls_version_order = {
                "TLSv1.0": 1,
                "TLSv1.1": 2,
                "TLSv1.2": 3,
                "TLSv1.3": 4,
            }
            if tls_version_order[normalized_version] < tls_version_order[required_version]:
                logger.error(
                    "TLS version %s is below required minimum %s",
                    normalized_version,
                    required_version,
                )
                return False, f"{normalized_version} below {required_version}"

            return True, normalized_version
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"


class MTLSMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware для mTLS с TLS 1.3 enforcement.

    Проверяет:
    1. TLS версия >= 1.3
    2. Наличие клиентского сертификата
    3. SPIFFE SVID валидность
    4. Истечение сертификата
    """

    def __init__(
        self,
        app,
        require_mtls: bool = True,
        enforce_tls_13: bool = True,
        allowed_spiffe_domains: Optional[list] = None,
        excluded_paths: Optional[list] = None,
        trust_proxy_headers: bool = True,
        trusted_proxy_cidrs: Optional[list[str]] = None,
        require_proxy_verified_header: bool = True,
        allow_unknown_tls: bool = False,
    ):
        super().__init__(app)
        self.require_mtls = require_mtls
        self.enforce_tls_13 = enforce_tls_13
        self.validator = MTLSValidator(
            require_client_cert=require_mtls,
            allowed_spiffe_domains=allowed_spiffe_domains,
            trust_proxy_headers=trust_proxy_headers,
            trusted_proxy_cidrs=trusted_proxy_cidrs,
            require_proxy_verified_header=require_proxy_verified_header,
            allow_unknown_tls=allow_unknown_tls,
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""

        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(request)
            return response

        # Валидировать TLS версию
        if self.enforce_tls_13:
            tls_valid, tls_version = self.validator.validate_tls_version(request)
            if not tls_valid:
                logger.warning(f"TLS validation failed: {tls_version}")
                return JSONResponse(
                    status_code=400,
                    content={"error": "TLS 1.3 required", "details": tls_version},
                )

        # Валидировать клиентский сертификат
        if self.require_mtls:
            client_cert = self.validator.extract_client_cert_from_request(request)

            if client_cert is None or client_cert is False:
                logger.warning("No valid client certificate provided")
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": "Client certificate required",
                        "details": "mTLS authentication failed",
                    },
                )

            # Если это реальный сертификат, проверить его
            if isinstance(client_cert, x509.Certificate):
                # Валидировать SPIFFE SVID
                spiffe_valid, spiffe_id = self.validator.validate_spiffe_svid(
                    client_cert
                )
                if not spiffe_valid:
                    logger.warning(f"Invalid SPIFFE SVID: {spiffe_id}")
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Invalid SPIFFE SVID", "details": spiffe_id},
                    )

                # Валидировать истечение
                expiry_valid, expiry_info = self.validator.validate_cert_expiry(
                    client_cert
                )
                if not expiry_valid:
                    logger.warning(f"Certificate validation failed: {expiry_info}")
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Certificate validation failed",
                            "details": expiry_info,
                        },
                    )

                # Добавить информацию в request state
                request.state.spiffe_id = spiffe_id
                request.state.cert_expiry = expiry_info

        # Добавить безопасность заголовки в response
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"

        return response
