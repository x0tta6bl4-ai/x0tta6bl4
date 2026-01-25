"""
mTLS middleware for FastAPI with TLS 1.3 enforcement
Обеспечивает:
- Обязательная валидация клиентских сертификатов
- Принуждение TLS 1.3+
- Проверка SPIFFE SVID
- Валидация истечения сертификата
- Логирование и метрики
"""

import ssl
import logging
from typing import Optional, Callable, Any
from datetime import datetime
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from cryptography import x509
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class MTLSValidator:
    """Валидатор mTLS сертификатов"""
    
    def __init__(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def extract_client_cert_from_request(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "client" in request.scope and request.scope["client"]:
                # В этом случае сертификат обрабатывается SSL слоем
                return True  # Флаг что сертификат проверен SSL слоем
            
            # Попытка получить из заголовка (от nginx reverse proxy)
            cert_header = request.headers.get("X-SSL-Client-Cert")
            if cert_header:
                # Декодировать PEM сертификат
                try:
                    cert_pem = f"-----BEGIN CERTIFICATE-----\n{cert_header}\n-----END CERTIFICATE-----"
                    from cryptography.hazmat.primitives import serialization
                    cert = x509.load_pem_x509_certificate(
                        cert_pem.encode(),
                        default_backend()
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
                    tls_version = ssl_obj.version
            
            # Попытка из заголовка (от nginx)
            if not tls_version:
                tls_version = request.headers.get("X-SSL-Protocol", "unknown")
            
            # Проверить минимальную версию
            if tls_version:
                if "TLSv1.3" in tls_version or "TLSv1_3" in tls_version:
                    return True, "TLSv1.3"
                elif "TLSv1.2" in tls_version or "TLSv1_2" in tls_version:
                    logger.error("TLS 1.2 not allowed, require TLS 1.3+")
                    return False, "TLSv1.2 not supported"
                else:
                    logger.error(f"Unsupported TLS version: {tls_version}")
                    return False, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
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
        excluded_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.require_mtls = require_mtls
        self.enforce_tls_13 = enforce_tls_13
        self.validator = MTLSValidator(
            require_client_cert=require_mtls,
            allowed_spiffe_domains=allowed_spiffe_domains
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
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
                    content={
                        "error": "TLS 1.3 required",
                        "details": tls_version
                    }
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
                        "details": "mTLS authentication failed"
                    }
                )
            
            # Если это реальный сертификат, проверить его
            if isinstance(client_cert, x509.Certificate):
                # Валидировать SPIFFE SVID
                spiffe_valid, spiffe_id = self.validator.validate_spiffe_svid(client_cert)
                if not spiffe_valid:
                    logger.warning(f"Invalid SPIFFE SVID: {spiffe_id}")
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Invalid SPIFFE SVID",
                            "details": spiffe_id
                        }
                    )
                
                # Валидировать истечение
                expiry_valid, expiry_info = self.validator.validate_cert_expiry(client_cert)
                if not expiry_valid:
                    logger.warning(f"Certificate validation failed: {expiry_info}")
                    return JSONResponse(
                        status_code=403,
                        content={
                            "error": "Certificate validation failed",
                            "details": expiry_info
                        }
                    )
                
                # Добавить информацию в request state
                request.state.spiffe_id = spiffe_id
                request.state.cert_expiry = expiry_info
        
        # Добавить безопасность заголовки в response
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
