"""
Authentication and Authorization Middleware for Proxy Control Plane.

Implements:
- API Key authentication
- JWT token-based authentication
- Role-based access control (RBAC)
- Rate limiting per client
- Request signing verification
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import time
from dataclasses import dataclass
from enum import Enum
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import jwt
from aiohttp import web
from aiohttp.web_middlewares import middleware

from src.core.thinking.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)

AUTH_THINKING_CLAIM_BOUNDARY = (
    "Local proxy authentication decision evidence only. It records auth mode, "
    "role, permission counts, rate-limit state, and hashed client/token/key "
    "identifiers without copying API keys, JWTs, signing secrets, request bodies, "
    "raw client ids, or remote addresses."
)


def _hash_value(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None
    text = str(value)
    if not text:
        return None
    return f"sha256:{hashlib.sha256(text.encode('utf-8')).hexdigest()}"

class Permission(Enum):
    """API permissions."""

    PROXY_READ = "proxy:read"
    PROXY_WRITE = "proxy:write"
    PROXY_ADMIN = "proxy:admin"
    METRICS_READ = "metrics:read"
    CONFIG_READ = "config:read"
    CONFIG_WRITE = "config:write"


class Role(Enum):
    """User roles with permission sets."""

    VIEWER = [Permission.PROXY_READ, Permission.METRICS_READ]
    OPERATOR = [
        Permission.PROXY_READ,
        Permission.PROXY_WRITE,
        Permission.METRICS_READ,
        Permission.CONFIG_READ,
    ]
    ADMIN = list(Permission)  # All permissions


@dataclass
class ClientIdentity:
    """Authenticated client identity."""

    client_id: str
    role: Role
    permissions: List[Permission]
    api_key_id: Optional[str] = None
    metadata: Dict[str, Any] = None

    def has_permission(self, permission: Permission) -> bool:
        """Check if client has permission."""
        return permission in self.permissions

    def can_access_proxy(self, proxy_id: Optional[str] = None) -> bool:
        """Check proxy access permission."""
        return self.has_permission(Permission.PROXY_READ)

    def can_modify_proxy(self) -> bool:
        """Check proxy modification permission."""
        return self.has_permission(Permission.PROXY_WRITE)


class RateLimiter:
    """Token bucket rate limiter."""

    def __init__(self, requests_per_minute: int = 100, burst_size: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_size = burst_size
        self.tokens: Dict[str, float] = {}
        self.last_update: Dict[str, float] = {}
        self._lock = None  # Initialized in async context

    async def acquire(self, client_id: str) -> bool:
        """Acquire a token for the client."""
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()

        async with self._lock:
            now = time.time()

            # Initialize bucket
            if client_id not in self.tokens:
                self.tokens[client_id] = self.burst_size
                self.last_update[client_id] = now

            # Add tokens based on time passed
            time_passed = now - self.last_update[client_id]
            tokens_to_add = time_passed * (self.requests_per_minute / 60)
            self.tokens[client_id] = min(
                self.burst_size, self.tokens[client_id] + tokens_to_add
            )
            self.last_update[client_id] = now

            # Try to acquire token
            if self.tokens[client_id] >= 1:
                self.tokens[client_id] -= 1
                return True

            return False

    def get_remaining(self, client_id: str) -> float:
        """Get remaining tokens for client."""
        return self.tokens.get(client_id, 0)

    def reset(self, client_id: str):
        """Reset rate limit for a client."""
        if client_id in self.tokens:
            del self.tokens[client_id]
        if client_id in self.last_update:
            del self.last_update[client_id]


class APIKeyStore:
    """Secure API key storage and validation."""

    def __init__(self):
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._load_from_env()

    def _load_from_env(self):
        """Load API keys from environment variables."""
        # Format: PROXY_API_KEY_<NAME>=<key>:<role>
        for key, value in os.environ.items():
            if key.startswith("PROXY_API_KEY_"):
                name = key[14:]  # Remove prefix
                parts = value.split(":", 1)
                api_key = parts[0]
                role = Role.VIEWER
                if len(parts) > 1 and parts[1].strip():
                    role_name = parts[1].strip().upper()
                    role = Role.__members__.get(role_name, Role.VIEWER)
                    if role is Role.VIEWER and role_name != "VIEWER":
                        logger.warning(
                            "Unknown API key role '%s' for %s; falling back to VIEWER",
                            parts[1],
                            name,
                        )

                self._keys[api_key] = {
                    "name": name,
                    "role": role,
                    "created_at": time.time(),
                    "last_used": None,
                    "use_count": 0,
                }

    def validate(self, api_key: str) -> Optional[ClientIdentity]:
        """Validate an API key and return identity."""
        key_data = self._keys.get(api_key)
        if not key_data:
            return None

        # Update usage stats
        key_data["last_used"] = time.time()
        key_data["use_count"] += 1

        return ClientIdentity(
            client_id=f"apikey:{key_data['name']}",
            role=key_data["role"],
            permissions=key_data["role"].value,
            api_key_id=key_data["name"],
            metadata={"use_count": key_data["use_count"]},
        )

    def rotate_key(self, name: str) -> str:
        """Rotate an API key."""
        new_key = f"pk_{os.urandom(32).hex()}"

        # Remove old key
        old_key = None
        for key, data in self._keys.items():
            if data["name"] == name:
                old_key = key
                break

        if old_key:
            del self._keys[old_key]

        # Add new key
        self._keys[new_key] = {
            "name": name,
            "role": Role.OPERATOR,
            "created_at": time.time(),
            "last_used": None,
            "use_count": 0,
        }

        return new_key


class JWTAuthManager:
    """JWT token authentication manager."""

    def __init__(
        self,
        secret: Optional[str] = None,
        algorithm: str = "HS256",
        expiry_hours: int = 24,
    ):
        self.secret = secret or os.environ.get("PROXY_JWT_SECRET", "")
        if not self.secret:
            if os.environ.get("ENVIRONMENT", "").lower() == "production":
                raise ValueError(
                    "PROXY_JWT_SECRET must be set in production. "
                    "Set the environment variable or pass secret= parameter."
                )
            logger.warning("JWT secret not configured, JWT auth disabled")

        self.algorithm = algorithm
        self.expiry_hours = expiry_hours
        self.thinking_coach = AgentThinkingCoach(
            agent_id="proxy-jwt-auth-manager",
            role="security",
            capabilities=("zero-trust", "ops"),
            extra_techniques=("stride_threat_modeling",),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _prepare_jwt_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "task_type": task_type,
            "goal": goal,
            "algorithm": self.algorithm,
            "expiry_hours": int(self.expiry_hours),
            "secret_configured": bool(self.secret),
            "constraints": {
                "redact_jwt": True,
                "redact_secret": True,
                "redact_client_id": True,
                "validate_expiry": True,
            },
            "safety_boundary": AUTH_THINKING_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "claim_boundary": AUTH_THINKING_CLAIM_BOUNDARY,
        }

    def create_token(
        self, client_id: str, role: Role, custom_claims: Optional[Dict[str, Any]] = None
    ) -> str:
        """Create a JWT token."""
        self._prepare_jwt_thinking_context(
            task_type="proxy_jwt_create_token",
            goal="Create a JWT for a client without exposing client id or signing secret.",
            extra={
                "client_id_hash": _hash_value(client_id),
                "role": role.name,
                "permission_count": len(role.value),
                "custom_claim_keys": sorted((custom_claims or {}).keys()),
            },
        )
        if not self.secret:
            raise ValueError("JWT secret not configured")

        payload = {
            "sub": client_id,
            "role": role.name,
            "permissions": [p.value for p in role.value],
            "iat": time.time(),
            "exp": time.time() + (self.expiry_hours * 3600),
        }

        if custom_claims:
            payload.update(custom_claims)

        return jwt.encode(payload, self.secret, algorithm=self.algorithm)

    def validate_token(self, token: str) -> Optional[ClientIdentity]:
        """Validate a JWT token."""
        self._prepare_jwt_thinking_context(
            task_type="proxy_jwt_validate_token",
            goal="Validate a JWT without exposing token contents.",
            extra={
                "token_present": bool(token),
                "token_hash": _hash_value(token),
            },
        )
        if not self.secret:
            return None

        try:
            payload = jwt.decode(token, self.secret, algorithms=[self.algorithm])

            role = Role[payload.get("role", "VIEWER")]
            permissions = [Permission(p) for p in payload.get("permissions", [])]

            identity = ClientIdentity(
                client_id=payload["sub"],
                role=role,
                permissions=permissions,
                metadata={"jwt_exp": payload.get("exp")},
            )
            self._prepare_jwt_thinking_context(
                task_type="proxy_jwt_validated",
                goal="Record validated JWT identity metadata without raw token or client id.",
                extra={
                    "client_id_hash": _hash_value(identity.client_id),
                    "role": identity.role.name,
                    "permission_count": len(identity.permissions),
                    "token_hash": _hash_value(token),
                },
            )
            return identity

        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
            self._prepare_jwt_thinking_context(
                task_type="proxy_jwt_expired",
                goal="Record expired JWT validation failure without raw token.",
                extra={"token_hash": _hash_value(token)},
            )
            return None
        except jwt.InvalidTokenError as e:
            logger.warning(f"Invalid JWT token: {e}")
            self._prepare_jwt_thinking_context(
                task_type="proxy_jwt_invalid",
                goal="Record invalid JWT validation failure without raw token.",
                extra={
                    "token_hash": _hash_value(token),
                    "error_type": type(e).__name__,
                },
            )
            return None


class ProxyAuthMiddleware:
    """
    Authentication and authorization middleware for proxy control plane.
    """

    def __init__(
        self,
        api_key_store: Optional[APIKeyStore] = None,
        jwt_manager: Optional[JWTAuthManager] = None,
        rate_limiter: Optional[RateLimiter] = None,
        require_auth: bool = True,
    ):
        self.api_key_store = api_key_store or APIKeyStore()
        self.jwt_manager = jwt_manager or JWTAuthManager()
        self.rate_limiter = rate_limiter or RateLimiter()
        self.require_auth = require_auth

        # Public paths that don't require authentication
        self.public_paths = {"/health", "/metrics", "/docs", "/openapi.json"}
        self.thinking_coach = AgentThinkingCoach(
            agent_id="proxy-auth-middleware",
            role="security",
            capabilities=("zero-trust", "ops"),
            extra_techniques=("stride_threat_modeling",),
        )
        self.last_thinking_context: Dict[str, Any] = {}

    def _identity_metadata(self, identity: Optional[ClientIdentity]) -> Dict[str, Any]:
        if identity is None:
            return {"present": False}
        return {
            "present": True,
            "client_id_hash": _hash_value(getattr(identity, "client_id", None)),
            "role": getattr(getattr(identity, "role", None), "name", None),
            "permission_count": len(getattr(identity, "permissions", []) or []),
            "api_key_id_hash": _hash_value(getattr(identity, "api_key_id", None)),
            "raw_identity_redacted": True,
        }

    def _prepare_auth_thinking_context(
        self,
        *,
        task_type: str,
        goal: str,
        extra: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        context: Dict[str, Any] = {
            "task_type": task_type,
            "goal": goal,
            "require_auth": bool(self.require_auth),
            "public_path_count": len(self.public_paths),
            "rate_limit": {
                "requests_per_minute": getattr(
                    self.rate_limiter, "requests_per_minute", None
                ),
                "burst_size": getattr(self.rate_limiter, "burst_size", None),
            },
            "constraints": {
                "redact_api_keys": True,
                "redact_jwts": True,
                "redact_client_ids": True,
                "redact_remote_addresses": True,
                "least_privilege": True,
            },
            "safety_boundary": AUTH_THINKING_CLAIM_BOUNDARY,
        }
        if extra:
            context.update(extra)
        self.last_thinking_context = self.thinking_coach.prepare_task(context)
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        status = {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
            "claim_boundary": AUTH_THINKING_CLAIM_BOUNDARY,
        }
        if hasattr(self.jwt_manager, "get_thinking_status"):
            status["jwt_manager"] = self.jwt_manager.get_thinking_status()
        return status

    @middleware
    async def authenticate(
        self, request: web.Request, handler: Callable
    ) -> web.Response:
        """Main authentication middleware."""
        path = getattr(request, "path", "")
        client_ip = request.remote or "unknown"
        self._prepare_auth_thinking_context(
            task_type="proxy_authenticate_request",
            goal="Authenticate a proxy control-plane request with least privilege.",
            extra={
                "path_hash": _hash_value(path),
                "path_is_public": path in self.public_paths,
                "remote_hash": _hash_value(client_ip),
                "api_key_present": bool(request.headers.get("X-API-Key")),
                "bearer_present": request.headers.get(
                    "Authorization", ""
                ).startswith("Bearer "),
            },
        )
        # Check if path is public
        if path in self.public_paths:
            self._prepare_auth_thinking_context(
                task_type="proxy_auth_public_path",
                goal="Allow configured public path without authentication.",
                extra={"path_hash": _hash_value(path)},
            )
            return await handler(request)

        # Check rate limit
        if not await self.rate_limiter.acquire(client_ip):
            self._prepare_auth_thinking_context(
                task_type="proxy_auth_rate_limited",
                goal="Deny request because the client exceeded local rate limits.",
                extra={"remote_hash": _hash_value(client_ip)},
            )
            return web.json_response(
                {"error": "Rate limit exceeded", "retry_after": 60}, status=429
            )

        # Try to authenticate
        identity = None

        # Try API key auth
        api_key = request.headers.get("X-API-Key")
        if api_key:
            identity = self.api_key_store.validate(api_key)

        # Try JWT auth
        if not identity:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
                identity = self.jwt_manager.validate_token(token)

        # Check if auth is required
        if not identity and self.require_auth:
            self._prepare_auth_thinking_context(
                task_type="proxy_auth_missing_identity",
                goal="Deny request because required authentication was not satisfied.",
                extra={"remote_hash": _hash_value(client_ip)},
            )
            return web.json_response(
                {
                    "error": "Authentication required",
                    "message": "Provide valid API key or JWT token",
                },
                status=401,
            )

        # Store identity in request
        request["identity"] = identity or ClientIdentity(
            client_id="anonymous", role=Role.VIEWER, permissions=Role.VIEWER.value
        )
        self._prepare_auth_thinking_context(
            task_type="proxy_auth_identity_accepted",
            goal="Record accepted identity metadata for proxy control-plane request.",
            extra={
                "identity": self._identity_metadata(request["identity"]),
                "anonymous": identity is None,
            },
        )

        # Add rate limit headers
        response = await handler(request)
        response.headers["X-RateLimit-Remaining"] = str(
            int(self.rate_limiter.get_remaining(client_ip))
        )

        return response

    def require_permission(self, permission: Permission):
        """Decorator to require specific permission."""

        def decorator(handler: Callable):
            @wraps(handler)
            async def wrapper(request: web.Request) -> web.Response:
                identity = request.get("identity")
                self._prepare_auth_thinking_context(
                    task_type="proxy_auth_require_permission",
                    goal="Check whether identity has required permission.",
                    extra={
                        "identity": self._identity_metadata(identity),
                        "required_permission": permission.value,
                    },
                )

                if not identity:
                    return web.json_response(
                        {"error": "Authentication required"}, status=401
                    )

                if not identity.has_permission(permission):
                    self._prepare_auth_thinking_context(
                        task_type="proxy_auth_permission_denied",
                        goal="Deny request because required permission is missing.",
                        extra={
                            "identity": self._identity_metadata(identity),
                            "required_permission": permission.value,
                        },
                    )
                    return web.json_response(
                        {
                            "error": "Permission denied",
                            "required": permission.value,
                            "your_permissions": [p.value for p in identity.permissions],
                        },
                        status=403,
                    )

                self._prepare_auth_thinking_context(
                    task_type="proxy_auth_permission_allowed",
                    goal="Allow request after required permission check.",
                    extra={
                        "identity": self._identity_metadata(identity),
                        "required_permission": permission.value,
                    },
                )
                return await handler(request)

            return wrapper

        return decorator

    def require_any_permission(self, permissions: List[Permission]):
        """Decorator to require any of the specified permissions."""

        def decorator(handler: Callable):
            @wraps(handler)
            async def wrapper(request: web.Request) -> web.Response:
                identity = request.get("identity")
                self._prepare_auth_thinking_context(
                    task_type="proxy_auth_require_any_permission",
                    goal="Check whether identity has any accepted permission.",
                    extra={
                        "identity": self._identity_metadata(identity),
                        "required_any": [p.value for p in permissions],
                    },
                )

                if not identity:
                    return web.json_response(
                        {"error": "Authentication required"}, status=401
                    )

                if not any(identity.has_permission(p) for p in permissions):
                    self._prepare_auth_thinking_context(
                        task_type="proxy_auth_any_permission_denied",
                        goal="Deny request because none of the accepted permissions matched.",
                        extra={
                            "identity": self._identity_metadata(identity),
                            "required_any": [p.value for p in permissions],
                        },
                    )
                    return web.json_response(
                        {
                            "error": "Permission denied",
                            "required_any": [p.value for p in permissions],
                        },
                        status=403,
                    )

                self._prepare_auth_thinking_context(
                    task_type="proxy_auth_any_permission_allowed",
                    goal="Allow request after any-permission check.",
                    extra={
                        "identity": self._identity_metadata(identity),
                        "required_any": [p.value for p in permissions],
                    },
                )
                return await handler(request)

            return wrapper

        return decorator


class RequestSigner:
    """
    Request signing for additional security.
    Implements AWS Signature Version 4 style signing.
    """

    def __init__(self, secret_key: str):
        self.secret_key = secret_key

    def sign_request(
        self,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[str] = None,
        timestamp: Optional[str] = None,
    ) -> str:
        """Sign a request."""
        timestamp = timestamp or str(int(time.time()))

        # Create canonical request
        canonical_headers = "\n".join(
            f"{k.lower()}:{v}" for k, v in sorted(headers.items())
        )
        signed_headers = ";".join(k.lower() for k in sorted(headers.keys()))

        payload_hash = hashlib.sha256((body or "").encode()).hexdigest()

        canonical_request = "\n".join(
            [
                method.upper(),
                path,
                "",  # Query string
                canonical_headers,
                "",
                signed_headers,
                payload_hash,
            ]
        )

        # Create string to sign
        credential_scope = f"{timestamp}/proxy/request"
        string_to_sign = "\n".join(
            [
                "PROXY-HMAC-SHA256",
                timestamp,
                credential_scope,
                hashlib.sha256(canonical_request.encode()).hexdigest(),
            ]
        )

        # Calculate signature
        signing_key = self._get_signing_key(timestamp)
        signature = hmac.new(
            signing_key, string_to_sign.encode(), hashlib.sha256
        ).hexdigest()

        return signature

    def _get_signing_key(self, timestamp: str) -> bytes:
        """Derive signing key."""
        k_date = hmac.new(
            f"PROXY{self.secret_key}".encode(),
            timestamp[:8].encode(),  # YYYYMMDD
            hashlib.sha256,
        ).digest()

        k_service = hmac.new(k_date, b"proxy", hashlib.sha256).digest()

        k_signing = hmac.new(k_service, b"proxy_request", hashlib.sha256).digest()

        return k_signing

    def verify_signature(
        self,
        signature: str,
        method: str,
        path: str,
        headers: Dict[str, str],
        body: Optional[str] = None,
        timestamp: Optional[str] = None,
        max_age_seconds: int = 300,
    ) -> bool:
        """Verify a request signature."""
        timestamp = timestamp or headers.get("X-Request-Timestamp")
        if not timestamp:
            return False

        # Check timestamp age
        try:
            request_time = int(timestamp)
            if abs(time.time() - request_time) > max_age_seconds:
                return False
        except ValueError:
            return False

        expected = self.sign_request(method, path, headers, body, timestamp)

        # Constant-time comparison
        return hmac.compare_digest(signature, expected)


def create_auth_middleware(
    require_auth: bool = True,
    requests_per_minute: int = 100,
    jwt_secret: Optional[str] = None,
) -> ProxyAuthMiddleware:
    """Factory function to create auth middleware with default settings."""
    return ProxyAuthMiddleware(
        api_key_store=APIKeyStore(),
        jwt_manager=JWTAuthManager(secret=jwt_secret),
        rate_limiter=RateLimiter(requests_per_minute=requests_per_minute),
        require_auth=require_auth,
    )

