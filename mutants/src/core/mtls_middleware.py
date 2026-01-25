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
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result


class MTLSValidator:
    """Валидатор mTLS сертификатов"""
    
    def xǁMTLSValidatorǁ__init____mutmut_orig(
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
    
    def xǁMTLSValidatorǁ__init____mutmut_1(
        self,
        require_client_cert: bool = False,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_2(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "XX1.3XX",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_3(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = False
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_4(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = None
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_5(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = None
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_6(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = None
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_7(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains and ["x0tta6bl4.mesh"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_8(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["XXx0tta6bl4.meshXX"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_9(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["X0TTA6BL4.MESH"]
        self.check_expiry = check_expiry
    
    def xǁMTLSValidatorǁ__init____mutmut_10(
        self,
        require_client_cert: bool = True,
        min_tls_version: str = "1.3",
        allowed_spiffe_domains: Optional[list] = None,
        check_expiry: bool = True
    ):
        self.require_client_cert = require_client_cert
        self.min_tls_version = min_tls_version
        self.allowed_spiffe_domains = allowed_spiffe_domains or ["x0tta6bl4.mesh"]
        self.check_expiry = None
    
    xǁMTLSValidatorǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSValidatorǁ__init____mutmut_1': xǁMTLSValidatorǁ__init____mutmut_1, 
        'xǁMTLSValidatorǁ__init____mutmut_2': xǁMTLSValidatorǁ__init____mutmut_2, 
        'xǁMTLSValidatorǁ__init____mutmut_3': xǁMTLSValidatorǁ__init____mutmut_3, 
        'xǁMTLSValidatorǁ__init____mutmut_4': xǁMTLSValidatorǁ__init____mutmut_4, 
        'xǁMTLSValidatorǁ__init____mutmut_5': xǁMTLSValidatorǁ__init____mutmut_5, 
        'xǁMTLSValidatorǁ__init____mutmut_6': xǁMTLSValidatorǁ__init____mutmut_6, 
        'xǁMTLSValidatorǁ__init____mutmut_7': xǁMTLSValidatorǁ__init____mutmut_7, 
        'xǁMTLSValidatorǁ__init____mutmut_8': xǁMTLSValidatorǁ__init____mutmut_8, 
        'xǁMTLSValidatorǁ__init____mutmut_9': xǁMTLSValidatorǁ__init____mutmut_9, 
        'xǁMTLSValidatorǁ__init____mutmut_10': xǁMTLSValidatorǁ__init____mutmut_10
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSValidatorǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMTLSValidatorǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMTLSValidatorǁ__init____mutmut_orig)
    xǁMTLSValidatorǁ__init____mutmut_orig.__name__ = 'xǁMTLSValidatorǁ__init__'
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_orig(self, request: Request) -> Optional[x509.Certificate]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_1(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "client" in request.scope or request.scope["client"]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_2(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "XXclientXX" in request.scope and request.scope["client"]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_3(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "CLIENT" in request.scope and request.scope["client"]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_4(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "client" not in request.scope and request.scope["client"]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_5(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "client" in request.scope and request.scope["XXclientXX"]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_6(self, request: Request) -> Optional[x509.Certificate]:
        """
        Извлечь клиентский сертификат из HTTP запроса.
        
        В продакшене сертификат передается через:
        - SSL_CLIENT_CERT header (от nginx/ingress)
        - STARLETTE_CLIENT_CERT scope (от uvicorn с SSL)
        """
        try:
            # Попытка получить из scope (если используется SSL)
            if "client" in request.scope and request.scope["CLIENT"]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_7(self, request: Request) -> Optional[x509.Certificate]:
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
                return False  # Флаг что сертификат проверен SSL слоем
            
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_8(self, request: Request) -> Optional[x509.Certificate]:
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
            cert_header = None
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_9(self, request: Request) -> Optional[x509.Certificate]:
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
            cert_header = request.headers.get(None)
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_10(self, request: Request) -> Optional[x509.Certificate]:
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
            cert_header = request.headers.get("XXX-SSL-Client-CertXX")
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_11(self, request: Request) -> Optional[x509.Certificate]:
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
            cert_header = request.headers.get("x-ssl-client-cert")
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_12(self, request: Request) -> Optional[x509.Certificate]:
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
            cert_header = request.headers.get("X-SSL-CLIENT-CERT")
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_13(self, request: Request) -> Optional[x509.Certificate]:
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
                    cert_pem = None
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_14(self, request: Request) -> Optional[x509.Certificate]:
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
                    cert = None
                    return cert
                except Exception as e:
                    logger.warning(f"Failed to parse client cert from header: {e}")
                    return None
            
            return None
        except Exception as e:
            logger.error(f"Error extracting client cert: {e}")
            return None
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_15(self, request: Request) -> Optional[x509.Certificate]:
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
                        None,
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_16(self, request: Request) -> Optional[x509.Certificate]:
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
                        None
                    )
                    return cert
                except Exception as e:
                    logger.warning(f"Failed to parse client cert from header: {e}")
                    return None
            
            return None
        except Exception as e:
            logger.error(f"Error extracting client cert: {e}")
            return None
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_17(self, request: Request) -> Optional[x509.Certificate]:
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
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_18(self, request: Request) -> Optional[x509.Certificate]:
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
                        )
                    return cert
                except Exception as e:
                    logger.warning(f"Failed to parse client cert from header: {e}")
                    return None
            
            return None
        except Exception as e:
            logger.error(f"Error extracting client cert: {e}")
            return None
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_19(self, request: Request) -> Optional[x509.Certificate]:
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
                    logger.warning(None)
                    return None
            
            return None
        except Exception as e:
            logger.error(f"Error extracting client cert: {e}")
            return None
    
    def xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_20(self, request: Request) -> Optional[x509.Certificate]:
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
            logger.error(None)
            return None
    
    xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_1': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_1, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_2': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_2, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_3': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_3, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_4': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_4, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_5': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_5, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_6': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_6, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_7': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_7, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_8': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_8, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_9': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_9, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_10': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_10, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_11': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_11, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_12': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_12, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_13': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_13, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_14': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_14, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_15': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_15, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_16': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_16, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_17': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_17, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_18': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_18, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_19': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_19, 
        'xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_20': xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_20
    }
    
    def extract_client_cert_from_request(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_orig"), object.__getattribute__(self, "xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_mutants"), args, kwargs, self)
        return result 
    
    extract_client_cert_from_request.__signature__ = _mutmut_signature(xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_orig)
    xǁMTLSValidatorǁextract_client_cert_from_request__mutmut_orig.__name__ = 'xǁMTLSValidatorǁextract_client_cert_from_request'
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_orig(self, cert: x509.Certificate) -> tuple[bool, str]:
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_1(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать SPIFFE SVID из сертификата.
        
        Returns: (is_valid, spiffe_id)
        """
        try:
            # Ищем SAN расширение с SPIFFE ID
            san_ext = None
            
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_2(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать SPIFFE SVID из сертификата.
        
        Returns: (is_valid, spiffe_id)
        """
        try:
            # Ищем SAN расширение с SPIFFE ID
            san_ext = cert.extensions.get_extension_for_oid(
                None
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_3(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                    uri = None
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_4(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                    if uri.startswith(None):
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_5(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                    if uri.startswith("XXspiffe://XX"):
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_6(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                    if uri.startswith("SPIFFE://"):
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_7(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                        domain = None  # spiffe://domain/...
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_8(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                        domain = uri.split(None)[2]  # spiffe://domain/...
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_9(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                        domain = uri.split("XX/XX")[2]  # spiffe://domain/...
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_10(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                        domain = uri.split("/")[3]  # spiffe://domain/...
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
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_11(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                        if domain not in self.allowed_spiffe_domains:
                            return True, uri
                        else:
                            logger.warning(f"Invalid SPIFFE domain: {domain}")
                            return False, uri
            
            logger.warning("No SPIFFE SVID found in certificate")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_12(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                            return False, uri
                        else:
                            logger.warning(f"Invalid SPIFFE domain: {domain}")
                            return False, uri
            
            logger.warning("No SPIFFE SVID found in certificate")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_13(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                            logger.warning(None)
                            return False, uri
            
            logger.warning("No SPIFFE SVID found in certificate")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_14(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                            return True, uri
            
            logger.warning("No SPIFFE SVID found in certificate")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_15(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            
            logger.warning(None)
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_16(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            
            logger.warning("XXNo SPIFFE SVID found in certificateXX")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_17(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            
            logger.warning("no spiffe svid found in certificate")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_18(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            
            logger.warning("NO SPIFFE SVID FOUND IN CERTIFICATE")
            return False, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_19(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return True, "unknown"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_20(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return False, "XXunknownXX"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_21(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return False, "UNKNOWN"
        except Exception as e:
            logger.error(f"Error validating SPIFFE SVID: {e}")
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_22(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            logger.error(None)
            return False, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_23(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return True, "error"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_24(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return False, "XXerrorXX"
    
    def xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_25(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return False, "ERROR"
    
    xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_1': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_1, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_2': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_2, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_3': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_3, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_4': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_4, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_5': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_5, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_6': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_6, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_7': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_7, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_8': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_8, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_9': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_9, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_10': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_10, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_11': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_11, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_12': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_12, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_13': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_13, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_14': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_14, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_15': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_15, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_16': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_16, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_17': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_17, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_18': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_18, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_19': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_19, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_20': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_20, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_21': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_21, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_22': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_22, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_23': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_23, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_24': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_24, 
        'xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_25': xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_25
    }
    
    def validate_spiffe_svid(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_orig"), object.__getattribute__(self, "xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_mutants"), args, kwargs, self)
        return result 
    
    validate_spiffe_svid.__signature__ = _mutmut_signature(xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_orig)
    xǁMTLSValidatorǁvalidate_spiffe_svid__mutmut_orig.__name__ = 'xǁMTLSValidatorǁvalidate_spiffe_svid'
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_orig(self, cert: x509.Certificate) -> tuple[bool, str]:
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
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_1(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать не истекщен ли сертификат.
        
        Returns: (is_valid, expiry_info)
        """
        try:
            now = None
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
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_2(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать не истекщен ли сертификат.
        
        Returns: (is_valid, expiry_info)
        """
        try:
            now = datetime.utcnow()
            not_valid_after = None
            
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
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_3(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать не истекщен ли сертификат.
        
        Returns: (is_valid, expiry_info)
        """
        try:
            now = datetime.utcnow()
            not_valid_after = cert.not_valid_after
            
            if now >= not_valid_after:
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
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_4(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать не истекщен ли сертификат.
        
        Returns: (is_valid, expiry_info)
        """
        try:
            now = datetime.utcnow()
            not_valid_after = cert.not_valid_after
            
            if now > not_valid_after:
                logger.error(None)
                return False, f"expired at {not_valid_after}"
            
            # Предупреждение если истекает в течении 7 дней
            days_until_expiry = (not_valid_after - now).days
            if days_until_expiry < 7:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_5(self, cert: x509.Certificate) -> tuple[bool, str]:
        """
        Валидировать не истекщен ли сертификат.
        
        Returns: (is_valid, expiry_info)
        """
        try:
            now = datetime.utcnow()
            not_valid_after = cert.not_valid_after
            
            if now > not_valid_after:
                logger.error(f"Certificate expired at {not_valid_after}")
                return True, f"expired at {not_valid_after}"
            
            # Предупреждение если истекает в течении 7 дней
            days_until_expiry = (not_valid_after - now).days
            if days_until_expiry < 7:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_6(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            days_until_expiry = None
            if days_until_expiry < 7:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_7(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            days_until_expiry = (not_valid_after + now).days
            if days_until_expiry < 7:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_8(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            if days_until_expiry <= 7:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_9(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            if days_until_expiry < 8:
                logger.warning(f"Certificate expiring in {days_until_expiry} days")
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_10(self, cert: x509.Certificate) -> tuple[bool, str]:
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
                logger.warning(None)
            
            return True, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_11(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            
            return False, f"expires in {days_until_expiry} days"
        except Exception as e:
            logger.error(f"Error checking certificate expiry: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_12(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            logger.error(None)
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_13(self, cert: x509.Certificate) -> tuple[bool, str]:
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
            return True, f"error: {e}"
    
    xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_1': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_1, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_2': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_2, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_3': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_3, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_4': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_4, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_5': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_5, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_6': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_6, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_7': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_7, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_8': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_8, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_9': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_9, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_10': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_10, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_11': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_11, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_12': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_12, 
        'xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_13': xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_13
    }
    
    def validate_cert_expiry(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_orig"), object.__getattribute__(self, "xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_mutants"), args, kwargs, self)
        return result 
    
    validate_cert_expiry.__signature__ = _mutmut_signature(xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_orig)
    xǁMTLSValidatorǁvalidate_cert_expiry__mutmut_orig.__name__ = 'xǁMTLSValidatorǁvalidate_cert_expiry'
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_orig(self, request: Request) -> tuple[bool, str]:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_1(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = ""
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_2(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None
            
            # Starlette/ASGI стандарт
            if "XXssl_objectXX" in request.scope:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_3(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None
            
            # Starlette/ASGI стандарт
            if "SSL_OBJECT" in request.scope:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_4(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None
            
            # Starlette/ASGI стандарт
            if "ssl_object" not in request.scope:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_5(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None
            
            # Starlette/ASGI стандарт
            if "ssl_object" in request.scope:
                ssl_obj = None
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_6(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None
            
            # Starlette/ASGI стандарт
            if "ssl_object" in request.scope:
                ssl_obj = request.scope["XXssl_objectXX"]
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_7(self, request: Request) -> tuple[bool, str]:
        """
        Валидировать TLS версию из запроса.
        
        Returns: (is_valid, tls_version)
        """
        try:
            # Получить TLS информацию из scope
            tls_version = None
            
            # Starlette/ASGI стандарт
            if "ssl_object" in request.scope:
                ssl_obj = request.scope["SSL_OBJECT"]
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_8(self, request: Request) -> tuple[bool, str]:
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
                if hasattr(None, "version"):
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_9(self, request: Request) -> tuple[bool, str]:
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
                if hasattr(ssl_obj, None):
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_10(self, request: Request) -> tuple[bool, str]:
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
                if hasattr("version"):
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_11(self, request: Request) -> tuple[bool, str]:
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
                if hasattr(ssl_obj, ):
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_12(self, request: Request) -> tuple[bool, str]:
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
                if hasattr(ssl_obj, "XXversionXX"):
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_13(self, request: Request) -> tuple[bool, str]:
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
                if hasattr(ssl_obj, "VERSION"):
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_14(self, request: Request) -> tuple[bool, str]:
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
                    tls_version = None
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_15(self, request: Request) -> tuple[bool, str]:
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
            if tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_16(self, request: Request) -> tuple[bool, str]:
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
                tls_version = None
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_17(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get(None, "unknown")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_18(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("X-SSL-Protocol", None)
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_19(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("unknown")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_20(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("X-SSL-Protocol", )
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_21(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("XXX-SSL-ProtocolXX", "unknown")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_22(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("x-ssl-protocol", "unknown")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_23(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("X-SSL-PROTOCOL", "unknown")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_24(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("X-SSL-Protocol", "XXunknownXX")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_25(self, request: Request) -> tuple[bool, str]:
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
                tls_version = request.headers.get("X-SSL-Protocol", "UNKNOWN")
            
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_26(self, request: Request) -> tuple[bool, str]:
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
                if "TLSv1.3" in tls_version and "TLSv1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_27(self, request: Request) -> tuple[bool, str]:
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
                if "XXTLSv1.3XX" in tls_version or "TLSv1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_28(self, request: Request) -> tuple[bool, str]:
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
                if "tlsv1.3" in tls_version or "TLSv1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_29(self, request: Request) -> tuple[bool, str]:
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
                if "TLSV1.3" in tls_version or "TLSv1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_30(self, request: Request) -> tuple[bool, str]:
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
                if "TLSv1.3" not in tls_version or "TLSv1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_31(self, request: Request) -> tuple[bool, str]:
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
                if "TLSv1.3" in tls_version or "XXTLSv1_3XX" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_32(self, request: Request) -> tuple[bool, str]:
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
                if "TLSv1.3" in tls_version or "tlsv1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_33(self, request: Request) -> tuple[bool, str]:
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
                if "TLSv1.3" in tls_version or "TLSV1_3" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_34(self, request: Request) -> tuple[bool, str]:
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
                if "TLSv1.3" in tls_version or "TLSv1_3" not in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_35(self, request: Request) -> tuple[bool, str]:
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
                    return False, "TLSv1.3"
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_36(self, request: Request) -> tuple[bool, str]:
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
                    return True, "XXTLSv1.3XX"
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_37(self, request: Request) -> tuple[bool, str]:
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
                    return True, "tlsv1.3"
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_38(self, request: Request) -> tuple[bool, str]:
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
                    return True, "TLSV1.3"
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_39(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSv1.2" in tls_version and "TLSv1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_40(self, request: Request) -> tuple[bool, str]:
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
                elif "XXTLSv1.2XX" in tls_version or "TLSv1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_41(self, request: Request) -> tuple[bool, str]:
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
                elif "tlsv1.2" in tls_version or "TLSv1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_42(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSV1.2" in tls_version or "TLSv1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_43(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSv1.2" not in tls_version or "TLSv1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_44(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSv1.2" in tls_version or "XXTLSv1_2XX" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_45(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSv1.2" in tls_version or "tlsv1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_46(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSv1.2" in tls_version or "TLSV1_2" in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_47(self, request: Request) -> tuple[bool, str]:
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
                elif "TLSv1.2" in tls_version or "TLSv1_2" not in tls_version:
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_48(self, request: Request) -> tuple[bool, str]:
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
                    logger.error(None)
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_49(self, request: Request) -> tuple[bool, str]:
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
                    logger.error("XXTLS 1.2 not allowed, require TLS 1.3+XX")
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_50(self, request: Request) -> tuple[bool, str]:
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
                    logger.error("tls 1.2 not allowed, require tls 1.3+")
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_51(self, request: Request) -> tuple[bool, str]:
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
                    logger.error("TLS 1.2 NOT ALLOWED, REQUIRE TLS 1.3+")
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
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_52(self, request: Request) -> tuple[bool, str]:
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
                    return True, "TLSv1.2 not supported"
                else:
                    logger.error(f"Unsupported TLS version: {tls_version}")
                    return False, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_53(self, request: Request) -> tuple[bool, str]:
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
                    return False, "XXTLSv1.2 not supportedXX"
                else:
                    logger.error(f"Unsupported TLS version: {tls_version}")
                    return False, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_54(self, request: Request) -> tuple[bool, str]:
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
                    return False, "tlsv1.2 not supported"
                else:
                    logger.error(f"Unsupported TLS version: {tls_version}")
                    return False, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_55(self, request: Request) -> tuple[bool, str]:
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
                    return False, "TLSV1.2 NOT SUPPORTED"
                else:
                    logger.error(f"Unsupported TLS version: {tls_version}")
                    return False, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_56(self, request: Request) -> tuple[bool, str]:
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
                    logger.error(None)
                    return False, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_57(self, request: Request) -> tuple[bool, str]:
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
                    return True, tls_version
            
            # Если информация недоступна, логируем но не блокируем в dev
            logger.debug("TLS version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_58(self, request: Request) -> tuple[bool, str]:
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
            logger.debug(None)
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_59(self, request: Request) -> tuple[bool, str]:
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
            logger.debug("XXTLS version info not available (may be development mode)XX")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_60(self, request: Request) -> tuple[bool, str]:
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
            logger.debug("tls version info not available (may be development mode)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_61(self, request: Request) -> tuple[bool, str]:
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
            logger.debug("TLS VERSION INFO NOT AVAILABLE (MAY BE DEVELOPMENT MODE)")
            return True, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_62(self, request: Request) -> tuple[bool, str]:
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
            return False, "unknown (dev mode)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_63(self, request: Request) -> tuple[bool, str]:
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
            return True, "XXunknown (dev mode)XX"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_64(self, request: Request) -> tuple[bool, str]:
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
            return True, "UNKNOWN (DEV MODE)"
        except Exception as e:
            logger.error(f"Error checking TLS version: {e}")
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_65(self, request: Request) -> tuple[bool, str]:
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
            logger.error(None)
            return False, f"error: {e}"
    
    def xǁMTLSValidatorǁvalidate_tls_version__mutmut_66(self, request: Request) -> tuple[bool, str]:
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
            return True, f"error: {e}"
    
    xǁMTLSValidatorǁvalidate_tls_version__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSValidatorǁvalidate_tls_version__mutmut_1': xǁMTLSValidatorǁvalidate_tls_version__mutmut_1, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_2': xǁMTLSValidatorǁvalidate_tls_version__mutmut_2, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_3': xǁMTLSValidatorǁvalidate_tls_version__mutmut_3, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_4': xǁMTLSValidatorǁvalidate_tls_version__mutmut_4, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_5': xǁMTLSValidatorǁvalidate_tls_version__mutmut_5, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_6': xǁMTLSValidatorǁvalidate_tls_version__mutmut_6, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_7': xǁMTLSValidatorǁvalidate_tls_version__mutmut_7, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_8': xǁMTLSValidatorǁvalidate_tls_version__mutmut_8, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_9': xǁMTLSValidatorǁvalidate_tls_version__mutmut_9, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_10': xǁMTLSValidatorǁvalidate_tls_version__mutmut_10, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_11': xǁMTLSValidatorǁvalidate_tls_version__mutmut_11, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_12': xǁMTLSValidatorǁvalidate_tls_version__mutmut_12, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_13': xǁMTLSValidatorǁvalidate_tls_version__mutmut_13, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_14': xǁMTLSValidatorǁvalidate_tls_version__mutmut_14, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_15': xǁMTLSValidatorǁvalidate_tls_version__mutmut_15, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_16': xǁMTLSValidatorǁvalidate_tls_version__mutmut_16, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_17': xǁMTLSValidatorǁvalidate_tls_version__mutmut_17, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_18': xǁMTLSValidatorǁvalidate_tls_version__mutmut_18, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_19': xǁMTLSValidatorǁvalidate_tls_version__mutmut_19, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_20': xǁMTLSValidatorǁvalidate_tls_version__mutmut_20, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_21': xǁMTLSValidatorǁvalidate_tls_version__mutmut_21, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_22': xǁMTLSValidatorǁvalidate_tls_version__mutmut_22, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_23': xǁMTLSValidatorǁvalidate_tls_version__mutmut_23, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_24': xǁMTLSValidatorǁvalidate_tls_version__mutmut_24, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_25': xǁMTLSValidatorǁvalidate_tls_version__mutmut_25, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_26': xǁMTLSValidatorǁvalidate_tls_version__mutmut_26, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_27': xǁMTLSValidatorǁvalidate_tls_version__mutmut_27, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_28': xǁMTLSValidatorǁvalidate_tls_version__mutmut_28, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_29': xǁMTLSValidatorǁvalidate_tls_version__mutmut_29, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_30': xǁMTLSValidatorǁvalidate_tls_version__mutmut_30, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_31': xǁMTLSValidatorǁvalidate_tls_version__mutmut_31, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_32': xǁMTLSValidatorǁvalidate_tls_version__mutmut_32, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_33': xǁMTLSValidatorǁvalidate_tls_version__mutmut_33, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_34': xǁMTLSValidatorǁvalidate_tls_version__mutmut_34, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_35': xǁMTLSValidatorǁvalidate_tls_version__mutmut_35, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_36': xǁMTLSValidatorǁvalidate_tls_version__mutmut_36, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_37': xǁMTLSValidatorǁvalidate_tls_version__mutmut_37, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_38': xǁMTLSValidatorǁvalidate_tls_version__mutmut_38, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_39': xǁMTLSValidatorǁvalidate_tls_version__mutmut_39, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_40': xǁMTLSValidatorǁvalidate_tls_version__mutmut_40, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_41': xǁMTLSValidatorǁvalidate_tls_version__mutmut_41, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_42': xǁMTLSValidatorǁvalidate_tls_version__mutmut_42, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_43': xǁMTLSValidatorǁvalidate_tls_version__mutmut_43, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_44': xǁMTLSValidatorǁvalidate_tls_version__mutmut_44, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_45': xǁMTLSValidatorǁvalidate_tls_version__mutmut_45, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_46': xǁMTLSValidatorǁvalidate_tls_version__mutmut_46, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_47': xǁMTLSValidatorǁvalidate_tls_version__mutmut_47, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_48': xǁMTLSValidatorǁvalidate_tls_version__mutmut_48, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_49': xǁMTLSValidatorǁvalidate_tls_version__mutmut_49, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_50': xǁMTLSValidatorǁvalidate_tls_version__mutmut_50, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_51': xǁMTLSValidatorǁvalidate_tls_version__mutmut_51, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_52': xǁMTLSValidatorǁvalidate_tls_version__mutmut_52, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_53': xǁMTLSValidatorǁvalidate_tls_version__mutmut_53, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_54': xǁMTLSValidatorǁvalidate_tls_version__mutmut_54, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_55': xǁMTLSValidatorǁvalidate_tls_version__mutmut_55, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_56': xǁMTLSValidatorǁvalidate_tls_version__mutmut_56, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_57': xǁMTLSValidatorǁvalidate_tls_version__mutmut_57, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_58': xǁMTLSValidatorǁvalidate_tls_version__mutmut_58, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_59': xǁMTLSValidatorǁvalidate_tls_version__mutmut_59, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_60': xǁMTLSValidatorǁvalidate_tls_version__mutmut_60, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_61': xǁMTLSValidatorǁvalidate_tls_version__mutmut_61, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_62': xǁMTLSValidatorǁvalidate_tls_version__mutmut_62, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_63': xǁMTLSValidatorǁvalidate_tls_version__mutmut_63, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_64': xǁMTLSValidatorǁvalidate_tls_version__mutmut_64, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_65': xǁMTLSValidatorǁvalidate_tls_version__mutmut_65, 
        'xǁMTLSValidatorǁvalidate_tls_version__mutmut_66': xǁMTLSValidatorǁvalidate_tls_version__mutmut_66
    }
    
    def validate_tls_version(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSValidatorǁvalidate_tls_version__mutmut_orig"), object.__getattribute__(self, "xǁMTLSValidatorǁvalidate_tls_version__mutmut_mutants"), args, kwargs, self)
        return result 
    
    validate_tls_version.__signature__ = _mutmut_signature(xǁMTLSValidatorǁvalidate_tls_version__mutmut_orig)
    xǁMTLSValidatorǁvalidate_tls_version__mutmut_orig.__name__ = 'xǁMTLSValidatorǁvalidate_tls_version'


class MTLSMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware для mTLS с TLS 1.3 enforcement.
    
    Проверяет:
    1. TLS версия >= 1.3
    2. Наличие клиентского сертификата
    3. SPIFFE SVID валидность
    4. Истечение сертификата
    """
    
    def xǁMTLSMiddlewareǁ__init____mutmut_orig(
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
    
    def xǁMTLSMiddlewareǁ__init____mutmut_1(
        self,
        app,
        require_mtls: bool = False,
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
    
    def xǁMTLSMiddlewareǁ__init____mutmut_2(
        self,
        app,
        require_mtls: bool = True,
        enforce_tls_13: bool = False,
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
    
    def xǁMTLSMiddlewareǁ__init____mutmut_3(
        self,
        app,
        require_mtls: bool = True,
        enforce_tls_13: bool = True,
        allowed_spiffe_domains: Optional[list] = None,
        excluded_paths: Optional[list] = None
    ):
        super().__init__(None)
        self.require_mtls = require_mtls
        self.enforce_tls_13 = enforce_tls_13
        self.validator = MTLSValidator(
            require_client_cert=require_mtls,
            allowed_spiffe_domains=allowed_spiffe_domains
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_4(
        self,
        app,
        require_mtls: bool = True,
        enforce_tls_13: bool = True,
        allowed_spiffe_domains: Optional[list] = None,
        excluded_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.require_mtls = None
        self.enforce_tls_13 = enforce_tls_13
        self.validator = MTLSValidator(
            require_client_cert=require_mtls,
            allowed_spiffe_domains=allowed_spiffe_domains
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_5(
        self,
        app,
        require_mtls: bool = True,
        enforce_tls_13: bool = True,
        allowed_spiffe_domains: Optional[list] = None,
        excluded_paths: Optional[list] = None
    ):
        super().__init__(app)
        self.require_mtls = require_mtls
        self.enforce_tls_13 = None
        self.validator = MTLSValidator(
            require_client_cert=require_mtls,
            allowed_spiffe_domains=allowed_spiffe_domains
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_6(
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
        self.validator = None
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_7(
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
            require_client_cert=None,
            allowed_spiffe_domains=allowed_spiffe_domains
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_8(
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
            allowed_spiffe_domains=None
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_9(
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
            allowed_spiffe_domains=allowed_spiffe_domains
        )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_10(
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
            )
        # Пути что не требуют mTLS (health check, metrics, etc)
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_11(
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
        self.excluded_paths = None
    
    def xǁMTLSMiddlewareǁ__init____mutmut_12(
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
        self.excluded_paths = excluded_paths and ["/health", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_13(
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
        self.excluded_paths = excluded_paths or ["XX/healthXX", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_14(
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
        self.excluded_paths = excluded_paths or ["/HEALTH", "/metrics", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_15(
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
        self.excluded_paths = excluded_paths or ["/health", "XX/metricsXX", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_16(
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
        self.excluded_paths = excluded_paths or ["/health", "/METRICS", "/docs", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_17(
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
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "XX/docsXX", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_18(
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
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/DOCS", "/openapi.json"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_19(
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
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "XX/openapi.jsonXX"]
    
    def xǁMTLSMiddlewareǁ__init____mutmut_20(
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
        self.excluded_paths = excluded_paths or ["/health", "/metrics", "/docs", "/OPENAPI.JSON"]
    
    xǁMTLSMiddlewareǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSMiddlewareǁ__init____mutmut_1': xǁMTLSMiddlewareǁ__init____mutmut_1, 
        'xǁMTLSMiddlewareǁ__init____mutmut_2': xǁMTLSMiddlewareǁ__init____mutmut_2, 
        'xǁMTLSMiddlewareǁ__init____mutmut_3': xǁMTLSMiddlewareǁ__init____mutmut_3, 
        'xǁMTLSMiddlewareǁ__init____mutmut_4': xǁMTLSMiddlewareǁ__init____mutmut_4, 
        'xǁMTLSMiddlewareǁ__init____mutmut_5': xǁMTLSMiddlewareǁ__init____mutmut_5, 
        'xǁMTLSMiddlewareǁ__init____mutmut_6': xǁMTLSMiddlewareǁ__init____mutmut_6, 
        'xǁMTLSMiddlewareǁ__init____mutmut_7': xǁMTLSMiddlewareǁ__init____mutmut_7, 
        'xǁMTLSMiddlewareǁ__init____mutmut_8': xǁMTLSMiddlewareǁ__init____mutmut_8, 
        'xǁMTLSMiddlewareǁ__init____mutmut_9': xǁMTLSMiddlewareǁ__init____mutmut_9, 
        'xǁMTLSMiddlewareǁ__init____mutmut_10': xǁMTLSMiddlewareǁ__init____mutmut_10, 
        'xǁMTLSMiddlewareǁ__init____mutmut_11': xǁMTLSMiddlewareǁ__init____mutmut_11, 
        'xǁMTLSMiddlewareǁ__init____mutmut_12': xǁMTLSMiddlewareǁ__init____mutmut_12, 
        'xǁMTLSMiddlewareǁ__init____mutmut_13': xǁMTLSMiddlewareǁ__init____mutmut_13, 
        'xǁMTLSMiddlewareǁ__init____mutmut_14': xǁMTLSMiddlewareǁ__init____mutmut_14, 
        'xǁMTLSMiddlewareǁ__init____mutmut_15': xǁMTLSMiddlewareǁ__init____mutmut_15, 
        'xǁMTLSMiddlewareǁ__init____mutmut_16': xǁMTLSMiddlewareǁ__init____mutmut_16, 
        'xǁMTLSMiddlewareǁ__init____mutmut_17': xǁMTLSMiddlewareǁ__init____mutmut_17, 
        'xǁMTLSMiddlewareǁ__init____mutmut_18': xǁMTLSMiddlewareǁ__init____mutmut_18, 
        'xǁMTLSMiddlewareǁ__init____mutmut_19': xǁMTLSMiddlewareǁ__init____mutmut_19, 
        'xǁMTLSMiddlewareǁ__init____mutmut_20': xǁMTLSMiddlewareǁ__init____mutmut_20
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSMiddlewareǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁMTLSMiddlewareǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁMTLSMiddlewareǁ__init____mutmut_orig)
    xǁMTLSMiddlewareǁ__init____mutmut_orig.__name__ = 'xǁMTLSMiddlewareǁ__init__'
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_orig(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_1(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(None):
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_2(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(None) for path in self.excluded_paths):
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_3(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_4(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_5(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(request)
            return response
        
        # Валидировать TLS версию
        if self.enforce_tls_13:
            tls_valid, tls_version = None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_6(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(request)
            return response
        
        # Валидировать TLS версию
        if self.enforce_tls_13:
            tls_valid, tls_version = self.validator.validate_tls_version(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_7(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(request)
            return response
        
        # Валидировать TLS версию
        if self.enforce_tls_13:
            tls_valid, tls_version = self.validator.validate_tls_version(request)
            if tls_valid:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_8(self, request: Request, call_next: Callable) -> Response:
        """Процесс запроса через mTLS валидацию"""
        
        # Пропустить проверку для исключенных путей
        if any(request.url.path.startswith(path) for path in self.excluded_paths):
            response = await call_next(request)
            return response
        
        # Валидировать TLS версию
        if self.enforce_tls_13:
            tls_valid, tls_version = self.validator.validate_tls_version(request)
            if not tls_valid:
                logger.warning(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_9(self, request: Request, call_next: Callable) -> Response:
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
                    status_code=None,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_10(self, request: Request, call_next: Callable) -> Response:
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
                    content=None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_11(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_12(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_13(self, request: Request, call_next: Callable) -> Response:
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
                    status_code=401,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_14(self, request: Request, call_next: Callable) -> Response:
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
                        "XXerrorXX": "TLS 1.3 required",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_15(self, request: Request, call_next: Callable) -> Response:
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
                        "ERROR": "TLS 1.3 required",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_16(self, request: Request, call_next: Callable) -> Response:
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
                        "error": "XXTLS 1.3 requiredXX",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_17(self, request: Request, call_next: Callable) -> Response:
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
                        "error": "tls 1.3 required",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_18(self, request: Request, call_next: Callable) -> Response:
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
                        "error": "TLS 1.3 REQUIRED",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_19(self, request: Request, call_next: Callable) -> Response:
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
                        "XXdetailsXX": tls_version
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_20(self, request: Request, call_next: Callable) -> Response:
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
                        "DETAILS": tls_version
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_21(self, request: Request, call_next: Callable) -> Response:
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
            client_cert = None
            
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_22(self, request: Request, call_next: Callable) -> Response:
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
            client_cert = self.validator.extract_client_cert_from_request(None)
            
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_23(self, request: Request, call_next: Callable) -> Response:
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
            
            if client_cert is None and client_cert is False:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_24(self, request: Request, call_next: Callable) -> Response:
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
            
            if client_cert is not None or client_cert is False:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_25(self, request: Request, call_next: Callable) -> Response:
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
            
            if client_cert is None or client_cert is not False:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_26(self, request: Request, call_next: Callable) -> Response:
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
            
            if client_cert is None or client_cert is True:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_27(self, request: Request, call_next: Callable) -> Response:
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
                logger.warning(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_28(self, request: Request, call_next: Callable) -> Response:
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
                logger.warning("XXNo valid client certificate providedXX")
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_29(self, request: Request, call_next: Callable) -> Response:
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
                logger.warning("no valid client certificate provided")
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_30(self, request: Request, call_next: Callable) -> Response:
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
                logger.warning("NO VALID CLIENT CERTIFICATE PROVIDED")
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_31(self, request: Request, call_next: Callable) -> Response:
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
                    status_code=None,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_32(self, request: Request, call_next: Callable) -> Response:
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
                    content=None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_33(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_34(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_35(self, request: Request, call_next: Callable) -> Response:
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
                    status_code=404,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_36(self, request: Request, call_next: Callable) -> Response:
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
                        "XXerrorXX": "Client certificate required",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_37(self, request: Request, call_next: Callable) -> Response:
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
                        "ERROR": "Client certificate required",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_38(self, request: Request, call_next: Callable) -> Response:
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
                        "error": "XXClient certificate requiredXX",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_39(self, request: Request, call_next: Callable) -> Response:
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
                        "error": "client certificate required",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_40(self, request: Request, call_next: Callable) -> Response:
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
                        "error": "CLIENT CERTIFICATE REQUIRED",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_41(self, request: Request, call_next: Callable) -> Response:
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
                        "XXdetailsXX": "mTLS authentication failed"
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_42(self, request: Request, call_next: Callable) -> Response:
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
                        "DETAILS": "mTLS authentication failed"
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_43(self, request: Request, call_next: Callable) -> Response:
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
                        "details": "XXmTLS authentication failedXX"
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_44(self, request: Request, call_next: Callable) -> Response:
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
                        "details": "mtls authentication failed"
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_45(self, request: Request, call_next: Callable) -> Response:
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
                        "details": "MTLS AUTHENTICATION FAILED"
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_46(self, request: Request, call_next: Callable) -> Response:
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
                spiffe_valid, spiffe_id = None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_47(self, request: Request, call_next: Callable) -> Response:
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
                spiffe_valid, spiffe_id = self.validator.validate_spiffe_svid(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_48(self, request: Request, call_next: Callable) -> Response:
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
                if spiffe_valid:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_49(self, request: Request, call_next: Callable) -> Response:
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
                    logger.warning(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_50(self, request: Request, call_next: Callable) -> Response:
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
                        status_code=None,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_51(self, request: Request, call_next: Callable) -> Response:
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
                        content=None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_52(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_53(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_54(self, request: Request, call_next: Callable) -> Response:
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
                        status_code=404,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_55(self, request: Request, call_next: Callable) -> Response:
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
                            "XXerrorXX": "Invalid SPIFFE SVID",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_56(self, request: Request, call_next: Callable) -> Response:
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
                            "ERROR": "Invalid SPIFFE SVID",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_57(self, request: Request, call_next: Callable) -> Response:
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
                            "error": "XXInvalid SPIFFE SVIDXX",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_58(self, request: Request, call_next: Callable) -> Response:
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
                            "error": "invalid spiffe svid",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_59(self, request: Request, call_next: Callable) -> Response:
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
                            "error": "INVALID SPIFFE SVID",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_60(self, request: Request, call_next: Callable) -> Response:
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
                            "XXdetailsXX": spiffe_id
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_61(self, request: Request, call_next: Callable) -> Response:
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
                            "DETAILS": spiffe_id
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_62(self, request: Request, call_next: Callable) -> Response:
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
                expiry_valid, expiry_info = None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_63(self, request: Request, call_next: Callable) -> Response:
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
                expiry_valid, expiry_info = self.validator.validate_cert_expiry(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_64(self, request: Request, call_next: Callable) -> Response:
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
                if expiry_valid:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_65(self, request: Request, call_next: Callable) -> Response:
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
                    logger.warning(None)
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_66(self, request: Request, call_next: Callable) -> Response:
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
                        status_code=None,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_67(self, request: Request, call_next: Callable) -> Response:
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
                        content=None
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_68(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_69(self, request: Request, call_next: Callable) -> Response:
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_70(self, request: Request, call_next: Callable) -> Response:
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
                        status_code=404,
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_71(self, request: Request, call_next: Callable) -> Response:
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
                            "XXerrorXX": "Certificate validation failed",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_72(self, request: Request, call_next: Callable) -> Response:
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
                            "ERROR": "Certificate validation failed",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_73(self, request: Request, call_next: Callable) -> Response:
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
                            "error": "XXCertificate validation failedXX",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_74(self, request: Request, call_next: Callable) -> Response:
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
                            "error": "certificate validation failed",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_75(self, request: Request, call_next: Callable) -> Response:
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
                            "error": "CERTIFICATE VALIDATION FAILED",
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_76(self, request: Request, call_next: Callable) -> Response:
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
                            "XXdetailsXX": expiry_info
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_77(self, request: Request, call_next: Callable) -> Response:
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
                            "DETAILS": expiry_info
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
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_78(self, request: Request, call_next: Callable) -> Response:
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
                request.state.spiffe_id = None
                request.state.cert_expiry = expiry_info
        
        # Добавить безопасность заголовки в response
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_79(self, request: Request, call_next: Callable) -> Response:
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
                request.state.cert_expiry = None
        
        # Добавить безопасность заголовки в response
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_80(self, request: Request, call_next: Callable) -> Response:
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
        response = None
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_81(self, request: Request, call_next: Callable) -> Response:
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
        response = await call_next(None)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_82(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["Strict-Transport-Security"] = None
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_83(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["XXStrict-Transport-SecurityXX"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_84(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["strict-transport-security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_85(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["STRICT-TRANSPORT-SECURITY"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_86(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["Strict-Transport-Security"] = "XXmax-age=31536000; includeSubDomainsXX"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_87(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includesubdomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_88(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["Strict-Transport-Security"] = "MAX-AGE=31536000; INCLUDESUBDOMAINS"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_89(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-Content-Type-Options"] = None
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_90(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["XXX-Content-Type-OptionsXX"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_91(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["x-content-type-options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_92(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-CONTENT-TYPE-OPTIONS"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_93(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-Content-Type-Options"] = "XXnosniffXX"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_94(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-Content-Type-Options"] = "NOSNIFF"
        response.headers["X-Frame-Options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_95(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-Frame-Options"] = None
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_96(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["XXX-Frame-OptionsXX"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_97(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["x-frame-options"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_98(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-FRAME-OPTIONS"] = "DENY"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_99(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-Frame-Options"] = "XXDENYXX"
        
        return response
    
    async def xǁMTLSMiddlewareǁdispatch__mutmut_100(self, request: Request, call_next: Callable) -> Response:
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
        response.headers["X-Frame-Options"] = "deny"
        
        return response
    
    xǁMTLSMiddlewareǁdispatch__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁMTLSMiddlewareǁdispatch__mutmut_1': xǁMTLSMiddlewareǁdispatch__mutmut_1, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_2': xǁMTLSMiddlewareǁdispatch__mutmut_2, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_3': xǁMTLSMiddlewareǁdispatch__mutmut_3, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_4': xǁMTLSMiddlewareǁdispatch__mutmut_4, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_5': xǁMTLSMiddlewareǁdispatch__mutmut_5, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_6': xǁMTLSMiddlewareǁdispatch__mutmut_6, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_7': xǁMTLSMiddlewareǁdispatch__mutmut_7, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_8': xǁMTLSMiddlewareǁdispatch__mutmut_8, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_9': xǁMTLSMiddlewareǁdispatch__mutmut_9, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_10': xǁMTLSMiddlewareǁdispatch__mutmut_10, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_11': xǁMTLSMiddlewareǁdispatch__mutmut_11, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_12': xǁMTLSMiddlewareǁdispatch__mutmut_12, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_13': xǁMTLSMiddlewareǁdispatch__mutmut_13, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_14': xǁMTLSMiddlewareǁdispatch__mutmut_14, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_15': xǁMTLSMiddlewareǁdispatch__mutmut_15, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_16': xǁMTLSMiddlewareǁdispatch__mutmut_16, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_17': xǁMTLSMiddlewareǁdispatch__mutmut_17, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_18': xǁMTLSMiddlewareǁdispatch__mutmut_18, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_19': xǁMTLSMiddlewareǁdispatch__mutmut_19, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_20': xǁMTLSMiddlewareǁdispatch__mutmut_20, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_21': xǁMTLSMiddlewareǁdispatch__mutmut_21, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_22': xǁMTLSMiddlewareǁdispatch__mutmut_22, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_23': xǁMTLSMiddlewareǁdispatch__mutmut_23, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_24': xǁMTLSMiddlewareǁdispatch__mutmut_24, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_25': xǁMTLSMiddlewareǁdispatch__mutmut_25, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_26': xǁMTLSMiddlewareǁdispatch__mutmut_26, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_27': xǁMTLSMiddlewareǁdispatch__mutmut_27, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_28': xǁMTLSMiddlewareǁdispatch__mutmut_28, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_29': xǁMTLSMiddlewareǁdispatch__mutmut_29, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_30': xǁMTLSMiddlewareǁdispatch__mutmut_30, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_31': xǁMTLSMiddlewareǁdispatch__mutmut_31, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_32': xǁMTLSMiddlewareǁdispatch__mutmut_32, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_33': xǁMTLSMiddlewareǁdispatch__mutmut_33, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_34': xǁMTLSMiddlewareǁdispatch__mutmut_34, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_35': xǁMTLSMiddlewareǁdispatch__mutmut_35, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_36': xǁMTLSMiddlewareǁdispatch__mutmut_36, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_37': xǁMTLSMiddlewareǁdispatch__mutmut_37, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_38': xǁMTLSMiddlewareǁdispatch__mutmut_38, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_39': xǁMTLSMiddlewareǁdispatch__mutmut_39, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_40': xǁMTLSMiddlewareǁdispatch__mutmut_40, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_41': xǁMTLSMiddlewareǁdispatch__mutmut_41, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_42': xǁMTLSMiddlewareǁdispatch__mutmut_42, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_43': xǁMTLSMiddlewareǁdispatch__mutmut_43, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_44': xǁMTLSMiddlewareǁdispatch__mutmut_44, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_45': xǁMTLSMiddlewareǁdispatch__mutmut_45, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_46': xǁMTLSMiddlewareǁdispatch__mutmut_46, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_47': xǁMTLSMiddlewareǁdispatch__mutmut_47, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_48': xǁMTLSMiddlewareǁdispatch__mutmut_48, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_49': xǁMTLSMiddlewareǁdispatch__mutmut_49, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_50': xǁMTLSMiddlewareǁdispatch__mutmut_50, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_51': xǁMTLSMiddlewareǁdispatch__mutmut_51, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_52': xǁMTLSMiddlewareǁdispatch__mutmut_52, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_53': xǁMTLSMiddlewareǁdispatch__mutmut_53, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_54': xǁMTLSMiddlewareǁdispatch__mutmut_54, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_55': xǁMTLSMiddlewareǁdispatch__mutmut_55, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_56': xǁMTLSMiddlewareǁdispatch__mutmut_56, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_57': xǁMTLSMiddlewareǁdispatch__mutmut_57, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_58': xǁMTLSMiddlewareǁdispatch__mutmut_58, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_59': xǁMTLSMiddlewareǁdispatch__mutmut_59, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_60': xǁMTLSMiddlewareǁdispatch__mutmut_60, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_61': xǁMTLSMiddlewareǁdispatch__mutmut_61, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_62': xǁMTLSMiddlewareǁdispatch__mutmut_62, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_63': xǁMTLSMiddlewareǁdispatch__mutmut_63, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_64': xǁMTLSMiddlewareǁdispatch__mutmut_64, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_65': xǁMTLSMiddlewareǁdispatch__mutmut_65, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_66': xǁMTLSMiddlewareǁdispatch__mutmut_66, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_67': xǁMTLSMiddlewareǁdispatch__mutmut_67, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_68': xǁMTLSMiddlewareǁdispatch__mutmut_68, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_69': xǁMTLSMiddlewareǁdispatch__mutmut_69, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_70': xǁMTLSMiddlewareǁdispatch__mutmut_70, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_71': xǁMTLSMiddlewareǁdispatch__mutmut_71, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_72': xǁMTLSMiddlewareǁdispatch__mutmut_72, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_73': xǁMTLSMiddlewareǁdispatch__mutmut_73, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_74': xǁMTLSMiddlewareǁdispatch__mutmut_74, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_75': xǁMTLSMiddlewareǁdispatch__mutmut_75, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_76': xǁMTLSMiddlewareǁdispatch__mutmut_76, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_77': xǁMTLSMiddlewareǁdispatch__mutmut_77, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_78': xǁMTLSMiddlewareǁdispatch__mutmut_78, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_79': xǁMTLSMiddlewareǁdispatch__mutmut_79, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_80': xǁMTLSMiddlewareǁdispatch__mutmut_80, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_81': xǁMTLSMiddlewareǁdispatch__mutmut_81, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_82': xǁMTLSMiddlewareǁdispatch__mutmut_82, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_83': xǁMTLSMiddlewareǁdispatch__mutmut_83, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_84': xǁMTLSMiddlewareǁdispatch__mutmut_84, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_85': xǁMTLSMiddlewareǁdispatch__mutmut_85, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_86': xǁMTLSMiddlewareǁdispatch__mutmut_86, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_87': xǁMTLSMiddlewareǁdispatch__mutmut_87, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_88': xǁMTLSMiddlewareǁdispatch__mutmut_88, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_89': xǁMTLSMiddlewareǁdispatch__mutmut_89, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_90': xǁMTLSMiddlewareǁdispatch__mutmut_90, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_91': xǁMTLSMiddlewareǁdispatch__mutmut_91, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_92': xǁMTLSMiddlewareǁdispatch__mutmut_92, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_93': xǁMTLSMiddlewareǁdispatch__mutmut_93, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_94': xǁMTLSMiddlewareǁdispatch__mutmut_94, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_95': xǁMTLSMiddlewareǁdispatch__mutmut_95, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_96': xǁMTLSMiddlewareǁdispatch__mutmut_96, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_97': xǁMTLSMiddlewareǁdispatch__mutmut_97, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_98': xǁMTLSMiddlewareǁdispatch__mutmut_98, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_99': xǁMTLSMiddlewareǁdispatch__mutmut_99, 
        'xǁMTLSMiddlewareǁdispatch__mutmut_100': xǁMTLSMiddlewareǁdispatch__mutmut_100
    }
    
    def dispatch(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁMTLSMiddlewareǁdispatch__mutmut_orig"), object.__getattribute__(self, "xǁMTLSMiddlewareǁdispatch__mutmut_mutants"), args, kwargs, self)
        return result 
    
    dispatch.__signature__ = _mutmut_signature(xǁMTLSMiddlewareǁdispatch__mutmut_orig)
    xǁMTLSMiddlewareǁdispatch__mutmut_orig.__name__ = 'xǁMTLSMiddlewareǁdispatch'
