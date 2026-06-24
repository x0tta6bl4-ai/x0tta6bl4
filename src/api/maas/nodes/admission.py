"""
MaaS Node Admission - registration, approval, and lifecycle management.
"""

import base64
import binascii
import hashlib
import hmac
import ipaddress
import json
import logging
import os
import secrets
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Mapping, Optional

import jwt
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.database import MeshInstance, MeshNode, User
from src.api.maas_security import token_signer
from .security import MeshOperator, ensure_mesh_visibility

logger = logging.getLogger(__name__)

_NODE_RUNTIME_CREDENTIAL_PREFIX = "x0tn_"
_DEFAULT_NODE_RUNTIME_CREDENTIAL_TTL_SECONDS = 24 * 60 * 60
_DEFAULT_MEASURED_ATTESTATION_FRESHNESS_SECONDS = 24 * 60 * 60
_ALLOWED_RUNTIME_IDENTITY_BINDING_TYPES = {
    "local_spiffe_hint",
    "spiffe_svid_digest",
    "verified_spiffe_svid",
    "verified_jwt_svid",
    "measured_attestation",
}
_TRUE_ENV_VALUES = {"1", "true", "yes", "on"}
_VERIFIED_SPIFFE_ID_HEADER = "x-verified-spiffe-id"
_VERIFIED_SVID_SHA256_HEADER = "x-verified-svid-sha256"
_VERIFIED_IDENTITY_SOURCE_HEADER = "x-verified-identity-source"
_JWT_SVID_HEADER = "x-spiffe-jwt-svid"
_DEFAULT_JWT_SVID_AUDIENCE = "x0tta6bl4-maas"


def default_node_runtime_credential_ttl_seconds() -> int:
    raw = os.getenv("NODE_RUNTIME_CREDENTIAL_TTL_SECONDS", "")
    try:
        value = int(raw) if raw else _DEFAULT_NODE_RUNTIME_CREDENTIAL_TTL_SECONDS
    except ValueError:
        value = _DEFAULT_NODE_RUNTIME_CREDENTIAL_TTL_SECONDS
    return min(max(value, 60), 30 * 24 * 60 * 60)


def generate_node_runtime_credential() -> str:
    """Generate a node-bound runtime credential returned once to the agent."""
    return f"{_NODE_RUNTIME_CREDENTIAL_PREFIX}{secrets.token_urlsafe(32)}"


def hash_node_runtime_credential(credential: str | None) -> str | None:
    if not credential:
        return None
    normalized = str(credential).strip()
    if not normalized:
        return None
    68|    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    69|  # lgtm[py/weak-sensitive-data-hashing]

def node_runtime_credential_expires_at(ttl_seconds: int | None = None) -> datetime:
    ttl = (
        default_node_runtime_credential_ttl_seconds()
        if ttl_seconds is None
        else min(max(int(ttl_seconds), 60), 30 * 24 * 60 * 60)
    )
    return datetime.utcnow() + timedelta(seconds=ttl)


def is_node_runtime_credential_expired(
    expires_at: datetime | None,
    *,
    now: datetime | None = None,
) -> bool:
    if expires_at is None:
        return True
    return expires_at <= (now or datetime.utcnow())


def measured_attestation_freshness_seconds() -> int:
    raw = os.getenv("MAAS_MEASURED_ATTESTATION_FRESHNESS_SECONDS", "")
    try:
        value = int(raw) if raw else _DEFAULT_MEASURED_ATTESTATION_FRESHNESS_SECONDS
    except ValueError:
        value = _DEFAULT_MEASURED_ATTESTATION_FRESHNESS_SECONDS
    return min(max(value, 60), 30 * 24 * 60 * 60)


def is_node_measured_attestation_fresh(
    node: MeshNode,
    *,
    now: datetime | None = None,
) -> bool:
    binding_type = _clean_runtime_identity_value(
        getattr(node, "runtime_identity_binding_type", None)
    ).lower()
    if binding_type != "measured_attestation":
        return True
    if not getattr(node, "runtime_identity_binding_hash", None):
        return False
    last_verified_at = getattr(node, "runtime_identity_last_verified_at", None)
    if last_verified_at is None:
        return False
    age_seconds = ((now or datetime.utcnow()) - last_verified_at).total_seconds()
    return age_seconds <= measured_attestation_freshness_seconds()


def verify_node_runtime_credential(
    credential: str | None,
    stored_hash: str | None,
) -> bool:
    credential_hash = hash_node_runtime_credential(credential)
    if not credential_hash or not stored_hash:
        return False
    return secrets.compare_digest(credential_hash, stored_hash)


def _env_truthy(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in _TRUE_ENV_VALUES


def trusted_runtime_identity_proxy_enabled() -> bool:
    return _env_truthy("MAAS_TRUSTED_RUNTIME_IDENTITY_PROXY_ENABLED", False)


def jwt_svid_verifier_enabled() -> bool:
    return _env_truthy("MAAS_JWT_SVID_VERIFIER_ENABLED", False)


def _jwt_svid_expected_audience() -> str:
    return (
        os.getenv("MAAS_JWT_SVID_AUDIENCE", _DEFAULT_JWT_SVID_AUDIENCE).strip()
        or _DEFAULT_JWT_SVID_AUDIENCE
    )


def _jwt_svid_expected_issuer() -> str:
    return os.getenv("MAAS_JWT_SVID_ISSUER", "").strip()


def _jwt_svid_trust_domain() -> str:
    return os.getenv("MAAS_JWT_SVID_TRUST_DOMAIN", "").strip()


def _jwt_svid_allowed_algorithms() -> list[str]:
    raw = os.getenv("MAAS_JWT_SVID_ALLOWED_ALGORITHMS", "RS256,ES256,PS256")
    algorithms = [item.strip() for item in raw.split(",") if item.strip()]
    return algorithms or ["RS256", "ES256", "PS256"]


def _trusted_runtime_identity_proxy_cidrs() -> list[Any]:
    raw = os.getenv(
        "MAAS_TRUSTED_RUNTIME_IDENTITY_PROXY_CIDRS",
        "127.0.0.1/32,::1/128",
    )
    networks: list[ipaddress._BaseNetwork] = []
    for item in raw.split(","):
        value = item.strip()
        if not value:
            continue
        try:
            networks.append(ipaddress.ip_network(value, strict=False))
        except ValueError:
            logger.warning("Ignoring invalid trusted runtime identity proxy CIDR: %s", value)
    return networks


def is_trusted_runtime_identity_proxy_client(client_host: str | None) -> bool:
    if not trusted_runtime_identity_proxy_enabled():
        return False
    normalized = str(client_host or "").strip()
    if (
        normalized == "testclient"
        and _env_truthy("MAAS_TRUSTED_RUNTIME_IDENTITY_PROXY_ALLOW_TESTCLIENT", False)
    ):
        return True
    if not normalized:
        return False
    try:
        client_ip = ipaddress.ip_address(normalized)
    except ValueError:
        return False
    return any(client_ip in network for network in _trusted_runtime_identity_proxy_cidrs())


def _header_value(headers: Mapping[str, Any], name: str) -> str:
    direct = headers.get(name)
    if direct is None:
        direct = headers.get(name.title())
    if direct is None:
        direct = headers.get(name.upper())
    return _clean_runtime_identity_value(direct)


def _jwt_svid_token_from_headers(headers: Mapping[str, Any]) -> str:
    token = _header_value(headers, _JWT_SVID_HEADER)
    if not token:
        authorization = _header_value(headers, "authorization")
        if authorization.lower().startswith("bearer "):
            token = authorization[7:]
    token = _clean_runtime_identity_value(token)
    if token.lower().startswith("bearer "):
        token = token[7:].strip()
    return token


def _jwt_svid_jwks_dict() -> Dict[str, Any] | None:
    raw_json = os.getenv("MAAS_JWT_SVID_JWKS_JSON", "").strip()
    if raw_json:
        loaded = json.loads(raw_json)
        if isinstance(loaded, Mapping):
            return dict(loaded)
        raise ValueError("MAAS_JWT_SVID_JWKS_JSON must contain a JWKS object")

    path = os.getenv("MAAS_JWT_SVID_JWKS_PATH", "").strip()
    if path:
        with open(path, "r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if isinstance(loaded, Mapping):
            return dict(loaded)
        raise ValueError("MAAS_JWT_SVID_JWKS_PATH must point to a JWKS object")

    url = os.getenv("MAAS_JWT_SVID_JWKS_URL", "").strip()
    if url:
        with urllib.request.urlopen(url, timeout=5) as response:
            loaded = json.loads(response.read().decode("utf-8"))
        if isinstance(loaded, Mapping):
            return dict(loaded)
        raise ValueError("MAAS_JWT_SVID_JWKS_URL must return a JWKS object")

    return None


def _select_jwt_svid_jwk(jwks: Mapping[str, Any], *, kid: str, alg: str) -> Any:
    keys = jwks.get("keys")
    if not isinstance(keys, list) or not keys:
        raise ValueError("jwt_svid_jwks_empty")
    candidates = [
        item for item in keys if isinstance(item, Mapping) and str(item.get("kid") or "") == kid
    ]
    if not candidates and not kid and len(keys) == 1 and isinstance(keys[0], Mapping):
        candidates = [keys[0]]
    if not candidates:
        raise ValueError("jwt_svid_key_not_found")
    return jwt.PyJWK.from_dict(dict(candidates[0]), algorithm=alg).key


def _jwt_svid_spiffe_id_matches_node(spiffe_id: str, node_id: str | None) -> bool:
    if not node_id or not _env_truthy("MAAS_JWT_SVID_REQUIRE_NODE_ID_MATCH", True):
        return True
    normalized_node = _clean_runtime_identity_value(node_id)
    if not normalized_node:
        return True
    allowed_suffixes = (
        f"/node/{normalized_node}",
        f"/nodes/{normalized_node}",
        f"/workload/{normalized_node}",
        f"/workloads/{normalized_node}",
    )
    return any(spiffe_id.endswith(suffix) for suffix in allowed_suffixes)


def _jwt_svid_binding_attestation_digest(claims: Mapping[str, Any]) -> str:
    aud = claims.get("aud", _jwt_svid_expected_audience())
    if isinstance(aud, list):
        aud_value: Any = sorted(str(item) for item in aud)
    else:
        aud_value = str(aud or "")
    digest_payload = {
        "aud": aud_value,
        "iss": str(claims.get("iss") or _jwt_svid_expected_issuer()),
        "trust_domain": _jwt_svid_trust_domain(),
        "verifier": "maas_jwt_svid_jwks_v1",
    }
    encoded = json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "jwt-svid:" + hashlib.sha256(encoded).hexdigest()


def verified_node_runtime_identity_from_jwt_svid(
    headers: Mapping[str, Any],
    *,
    expected_node_id: str | None = None,
) -> Dict[str, Any] | None:
    token = _jwt_svid_token_from_headers(headers)
    if not token:
        return None
    if not jwt_svid_verifier_enabled():
        return {
            "verified": False,
            "reason": "jwt_svid_verifier_disabled",
            "raw_runtime_identity_jwt_redacted": True,
        }

    try:
        header = jwt.get_unverified_header(token)
        alg = str(header.get("alg") or "")
        kid = str(header.get("kid") or "")
        allowed_algorithms = _jwt_svid_allowed_algorithms()
        if alg not in allowed_algorithms:
            return {
                "verified": False,
                "reason": "jwt_svid_algorithm_not_allowed",
                "raw_runtime_identity_jwt_redacted": True,
            }

        jwks = _jwt_svid_jwks_dict()
        if jwks is None:
            return {
                "verified": False,
                "reason": "jwt_svid_jwks_not_configured",
                "raw_runtime_identity_jwt_redacted": True,
            }
        key = _select_jwt_svid_jwk(jwks, kid=kid, alg=alg)
        decode_kwargs: Dict[str, Any] = {
            "key": key,
            "algorithms": allowed_algorithms,
            "audience": _jwt_svid_expected_audience(),
            "options": {"require": ["exp", "sub", "aud"]},
        }
        issuer = _jwt_svid_expected_issuer()
        if issuer:
            decode_kwargs["issuer"] = issuer
        claims = jwt.decode(token, **decode_kwargs)
    except jwt.ExpiredSignatureError:
        return {
            "verified": False,
            "reason": "jwt_svid_expired",
            "raw_runtime_identity_jwt_redacted": True,
        }
    except jwt.InvalidAudienceError:
        return {
            "verified": False,
            "reason": "jwt_svid_invalid_audience",
            "raw_runtime_identity_jwt_redacted": True,
        }
    except jwt.InvalidIssuerError:
        return {
            "verified": False,
            "reason": "jwt_svid_invalid_issuer",
            "raw_runtime_identity_jwt_redacted": True,
        }
    except (jwt.InvalidTokenError, ValueError, json.JSONDecodeError, OSError, urllib.error.URLError):
        return {
            "verified": False,
            "reason": "jwt_svid_verification_failed",
            "raw_runtime_identity_jwt_redacted": True,
        }

    spiffe_id = _clean_runtime_identity_value(claims.get("sub"))
    if not spiffe_id.startswith("spiffe://"):
        return {
            "verified": False,
            "reason": "jwt_svid_subject_not_spiffe_id",
            "raw_runtime_identity_jwt_redacted": True,
        }

    trust_domain = _jwt_svid_trust_domain()
    if trust_domain and not spiffe_id.startswith(f"spiffe://{trust_domain}/"):
        return {
            "verified": False,
            "reason": "jwt_svid_trust_domain_mismatch",
            "raw_runtime_identity_jwt_redacted": True,
        }
    if not _jwt_svid_spiffe_id_matches_node(spiffe_id, expected_node_id):
        return {
            "verified": False,
            "reason": "jwt_svid_spiffe_id_node_mismatch",
            "raw_runtime_identity_jwt_redacted": True,
        }

    return {
        "verified": True,
        "binding_type": "verified_jwt_svid",
        "spiffe_id": spiffe_id,
        "attestation_digest": _jwt_svid_binding_attestation_digest(claims),
        "source": "jwt_svid",
        "raw_runtime_identity_jwt_redacted": True,
        "api_side_jwt_svid_verification_claim_allowed": True,
        "claim_boundary": (
            "JWT-SVID signature, expiry, subject, and audience were verified "
            "by the API against a configured SPIFFE JWKS bundle. This does not "
            "prove hardware measured attestation by itself."
        ),
    }


def verified_node_runtime_identity_from_headers(
    headers: Mapping[str, Any],
    *,
    client_host: str | None,
) -> Dict[str, Any] | None:
    spiffe_id = _header_value(headers, _VERIFIED_SPIFFE_ID_HEADER)
    svid_sha256 = _header_value(headers, _VERIFIED_SVID_SHA256_HEADER)
    source = _header_value(headers, _VERIFIED_IDENTITY_SOURCE_HEADER) or "trusted_proxy"
    if not spiffe_id and not svid_sha256:
        return None
    if not is_trusted_runtime_identity_proxy_client(client_host):
        return {
            "verified": False,
            "reason": "untrusted_runtime_identity_proxy",
            "raw_runtime_identity_headers_redacted": True,
        }
    if not spiffe_id.startswith("spiffe://"):
        return {
            "verified": False,
            "reason": "invalid_verified_spiffe_id",
            "raw_runtime_identity_headers_redacted": True,
        }
    if not svid_sha256 or len(svid_sha256) < 16 or len(svid_sha256) > 256:
        return {
            "verified": False,
            "reason": "invalid_verified_svid_sha256",
            "raw_runtime_identity_headers_redacted": True,
        }
    return {
        "verified": True,
        "binding_type": "verified_spiffe_svid",
        "spiffe_id": spiffe_id,
        "attestation_digest": svid_sha256,
        "source": source,
        "raw_runtime_identity_headers_redacted": True,
        "claim_boundary": (
            "SPIFFE identity was asserted by a configured trusted mTLS proxy. "
            "The API does not trust client-supplied identity headers from "
            "untrusted network sources."
        ),
    }


def _decode_attestation_b64(value: Any, *, field_name: str) -> bytes:
    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hardware attestation {field_name} must be a base64 string",
        )
    try:
        return base64.b64decode(value.strip().encode("ascii"), validate=True)
    except (binascii.Error, ValueError, UnicodeEncodeError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hardware attestation {field_name} must be valid base64",
        )


def _attestation_utf8_bytes(value: Any, *, field_name: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if not isinstance(value, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hardware attestation {field_name} must be a string",
        )
    return value.encode("utf-8")


def _attestation_material(
    attestation_data: Mapping[str, Any],
    field_name: str,
    *,
    required: bool = False,
) -> bytes | None:
    b64_field = f"{field_name}_b64"
    if b64_field in attestation_data and attestation_data.get(b64_field) is not None:
        return _decode_attestation_b64(
            attestation_data.get(b64_field),
            field_name=b64_field,
        )
    if field_name in attestation_data and attestation_data.get(field_name) is not None:
        return _attestation_utf8_bytes(
            attestation_data.get(field_name),
            field_name=field_name,
        )
    if required:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Hardware attestation {field_name} is required",
        )
    return None


def _tee_attestation_from_data(attestation_data: Mapping[str, Any]) -> Any:
    from src.security.tee_attestation import TEEAttestation

    provider = _clean_runtime_identity_value(
        attestation_data.get("provider") or "mock"
    ).lower()
    return TEEAttestation(
        provider=provider,
        report_data=_attestation_material(
            attestation_data,
            "report_data",
            required=True,
        )
        or b"",
        quote=_attestation_material(attestation_data, "quote"),
        signature=_attestation_material(attestation_data, "signature"),
    )


def _optional_sha256(value: bytes | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value).hexdigest()


def _hash_json_payload(value: Mapping[str, Any] | None) -> str | None:
    if not value:
        return None
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def hash_verified_measured_attestation(
    attestation_data: Mapping[str, Any],
    *,
    verifier_backend: str | None = None,
    verifier_provenance: Mapping[str, Any] | None = None,
) -> str:
    attestation = _tee_attestation_from_data(attestation_data)
    digest_payload = {
        "provider": str(attestation.provider or "").strip().lower(),
        "report_data_sha256": hashlib.sha256(attestation.report_data).hexdigest(),
        "quote_sha256": _optional_sha256(attestation.quote),
        "signature_sha256": _optional_sha256(attestation.signature),
        "verifier_backend": verifier_backend or "x0tta6bl4_tee_validator_v1",
        "verifier_provenance_sha256": _hash_json_payload(verifier_provenance),
    }
    encoded = json.dumps(
        digest_payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return "tee:" + hashlib.sha256(encoded).hexdigest()


def verified_measured_attestation_context(
    attestation_data: Mapping[str, Any] | None,
) -> Dict[str, Any]:
    if not isinstance(attestation_data, Mapping):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Hardware attestation required for this node",
        )

    from src.security.tee_attestation import TEEValidator

    attestation = _tee_attestation_from_data(attestation_data)
    tee_validator = TEEValidator(
        allow_mock=_env_truthy("MAAS_ALLOW_MOCK_TEE_ATTESTATION", False)
    )
    verification = tee_validator.verify_report_with_context(attestation)
    if not verification.verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid hardware attestation report",
        )

    return {
        "verified": True,
        "binding_type": "measured_attestation",
        "attestation_digest": hash_verified_measured_attestation(
            attestation_data,
            verifier_backend=verification.verifier_backend,
            verifier_provenance=verification.verifier_provenance,
        ),
        "source": f"tee:{attestation.provider}:{verification.verifier_backend}",
        "attestation_verifier_backend": verification.verifier_backend,
        "attestation_verifier_provenance": verification.verifier_provenance,
        "raw_hardware_attestation_redacted": True,
        "hardware_measured_attestation_claim_allowed": True,
        "production_attestation_verifier_claim_allowed": (
            verification.production_verifier_claim_allowed
        ),
        "production_trust_finality_claim_allowed": False,
        "claim_boundary": (
            "TEE attestation was validated by the configured verifier and "
            "raw attestation material was redacted. Production trust finality "
            "still requires external production evidence beyond this API response."
        ),
    }


def runtime_identity_proof_from_verified_context(context: Mapping[str, Any]) -> Dict[str, str]:
    if not context or context.get("verified") is not True:
        raise ValueError("trusted verified runtime identity context required")
    return {
        "binding_type": _clean_runtime_identity_value(
            context.get("binding_type") or "verified_spiffe_svid"
        ).lower(),
        "spiffe_id": _clean_runtime_identity_value(context.get("spiffe_id")),
        "attestation_digest": _clean_runtime_identity_value(
            context.get("attestation_digest")
        ),
        "nonce": "",
    }


def _runtime_identity_proof_mapping(proof: Any) -> Mapping[str, Any]:
    if proof is None:
        return {}
    if hasattr(proof, "model_dump"):
        return proof.model_dump()
    if hasattr(proof, "dict"):
        return proof.dict()
    if isinstance(proof, Mapping):
        return proof
    return {}


def _clean_runtime_identity_value(value: Any) -> str:
    return str(value or "").strip()


def canonical_node_runtime_identity_binding_payload(proof: Any) -> Dict[str, str]:
    raw = _runtime_identity_proof_mapping(proof)
    binding_type = _clean_runtime_identity_value(raw.get("binding_type")).lower()
    spiffe_id = _clean_runtime_identity_value(raw.get("spiffe_id"))
    attestation_digest = _clean_runtime_identity_value(raw.get("attestation_digest"))
    nonce = _clean_runtime_identity_value(raw.get("nonce"))

    if binding_type not in _ALLOWED_RUNTIME_IDENTITY_BINDING_TYPES:
        raise ValueError("unsupported runtime identity binding_type")
    if binding_type == "local_spiffe_hint" and not spiffe_id:
        raise ValueError("spiffe_id is required for local_spiffe_hint")
    if binding_type == "measured_attestation" and not attestation_digest:
        raise ValueError("attestation_digest is required for measured_attestation")
    if binding_type in {
        "spiffe_svid_digest",
        "verified_spiffe_svid",
        "verified_jwt_svid",
    } and (not spiffe_id or not attestation_digest):
        raise ValueError("spiffe_id and attestation_digest are required for SVID bindings")

    return {
        "binding_type": binding_type,
        "spiffe_id": spiffe_id,
        "attestation_digest": attestation_digest,
        "nonce": nonce,
    }


def hash_node_runtime_identity_binding(proof: Any) -> str:
    payload = canonical_node_runtime_identity_binding_payload(proof)
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def verify_node_runtime_identity_binding(
    proof: Any,
    *,
    stored_hash: str | None,
    stored_binding_type: str | None = None,
    verified_identity_context: Mapping[str, Any] | None = None,
) -> bool:
    if not stored_hash:
        return True
    normalized_type = _clean_runtime_identity_value(stored_binding_type).lower()
    candidates: list[Any] = []
    if verified_identity_context and verified_identity_context.get("verified") is True:
        candidates.append(runtime_identity_proof_from_verified_context(verified_identity_context))
    if normalized_type not in {"verified_spiffe_svid", "verified_jwt_svid"}:
        candidates.append(proof)
    if not candidates:
        return False
    for candidate in candidates:
        try:
            proof_hash = hash_node_runtime_identity_binding(candidate)
        except ValueError:
            continue
        if secrets.compare_digest(proof_hash, stored_hash):
            return True
    return False


def verified_runtime_identity_failure_reason(
    context: Mapping[str, Any] | None,
) -> str:
    if context is None:
        return "trusted_runtime_identity_headers_missing"
    return str(context.get("reason") or "trusted_runtime_identity_verification_failed")


def verified_runtime_identity_hash_matches(
    *,
    stored_hash: str | None,
    verified_identity_context: Mapping[str, Any] | None,
) -> bool:
    if not stored_hash or not verified_identity_context:
        return False
    try:
        proof_hash = hash_node_runtime_identity_binding(
            runtime_identity_proof_from_verified_context(verified_identity_context)
        )
    except ValueError:
        return False
    return secrets.compare_digest(proof_hash, stored_hash)


def bind_node_runtime_identity(
    node: MeshNode,
    db: Session,
    proof: Any,
) -> Dict[str, Any]:
    payload = canonical_node_runtime_identity_binding_payload(proof)
    proof_hash = hash_node_runtime_identity_binding(payload)
    existing = (
        db.query(MeshNode)
        .filter(
            MeshNode.runtime_identity_binding_hash == proof_hash,
            MeshNode.id != node.id,
        )
        .first()
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Runtime identity proof is already bound to another node",
        )

    verified_at = datetime.utcnow()
    node.runtime_identity_binding_type = payload["binding_type"]
    node.runtime_identity_binding_hash = proof_hash
    node.runtime_identity_bound_at = node.runtime_identity_bound_at or verified_at
    node.runtime_identity_last_verified_at = verified_at
    db.commit()

    return {
        "runtime_identity_binding_type": payload["binding_type"],
        "runtime_identity_binding_hash": proof_hash,
        "runtime_identity_bound_at": node.runtime_identity_bound_at,
        "runtime_identity_last_verified_at": node.runtime_identity_last_verified_at,
    }


def rotate_node_runtime_credential(
    node: MeshNode,
    db: Session,
    *,
    ttl_seconds: int | None = None,
) -> Dict[str, Any]:
    runtime_credential = generate_node_runtime_credential()
    rotated_at = datetime.utcnow()
    expires_at = node_runtime_credential_expires_at(ttl_seconds)
    node.runtime_credential_hash = hash_node_runtime_credential(runtime_credential)
    node.runtime_credential_rotated_at = rotated_at
    node.runtime_credential_expires_at = expires_at
    db.commit()
    return {
        "api_key": runtime_credential,
        "node_runtime_credential": runtime_credential,
        "raw_runtime_credential_returned_once": True,
        "runtime_credential_expires_at": expires_at,
        "runtime_credential_rotated_at": rotated_at,
    }


def register_node(
    mesh_id: str,
    enrollment_token: str,
    db: Session,
    node_id: Optional[str] = None,
    device_class: str = "edge",
    hardware_id: Optional[str] = None,
    enclave_enabled: bool = False,
) -> Dict[str, Any]:
    """Register a new node (pending approval)."""
    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    
    if not instance.join_token:
        raise HTTPException(status_code=503, detail="Mesh enrollment token is not configured")
    if instance.join_token_expires_at and instance.join_token_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=401, detail="Enrollment token expired")

    if not hmac.compare_digest(enrollment_token, instance.join_token):
        raise HTTPException(status_code=401, detail="Invalid token")

    node_id = node_id or f"node-{uuid.uuid4().hex[:6]}"
    
    # Check if node already exists
    existing = db.query(MeshNode).filter(MeshNode.id == node_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Node ID already registered")

    runtime_credential = generate_node_runtime_credential()
    runtime_credential_expires_at = node_runtime_credential_expires_at()
    runtime_credential_rotated_at = datetime.utcnow()
    node = MeshNode(
        id=node_id,
        mesh_id=mesh_id,
        device_class=device_class,
        hardware_id=hardware_id,
        enclave_enabled=bool(enclave_enabled),
        status="pending",
        runtime_credential_hash=hash_node_runtime_credential(runtime_credential),
        runtime_credential_expires_at=runtime_credential_expires_at,
        runtime_credential_rotated_at=runtime_credential_rotated_at,
    )
    db.add(node)
    db.commit()
    
    logger.info(f"🆕 Node {node_id} registered (pending) for mesh {mesh_id}")
    return {
        "status": "pending_approval",
        "node_id": node_id,
        "api_key": runtime_credential,
        "node_runtime_credential": runtime_credential,
        "raw_runtime_credential_returned_once": True,
        "node_runtime_credential_expires_at": runtime_credential_expires_at,
    }


def list_pending_nodes(
    mesh_id: str,
    current_user: User,
    db: Session,
) -> List[MeshNode]:
    """List nodes awaiting approval."""
    ensure_mesh_visibility(mesh_id, current_user, db)
    return db.query(MeshNode).filter(
        MeshNode.mesh_id == mesh_id, 
        MeshNode.status == "pending"
    ).all()


def approve_node(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
    attestation_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Approve a pending node to join the mesh."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")

    instance = db.query(MeshInstance).filter(MeshInstance.id == mesh_id).first()
    if not instance:
        raise HTTPException(status_code=404, detail="Mesh not found")
    if not instance.join_token:
        raise HTTPException(status_code=503, detail="Mesh enrollment token is not configured")
    if instance.join_token_expires_at and instance.join_token_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=409, detail="Mesh enrollment token expired")

    node_status = (node.status or "").lower()
    if node_status not in {"approved", "pending", "pending_approval"}:
        raise HTTPException(
            status_code=409,
            detail=f"Node cannot be approved from status '{node.status}'",
        )

    measured_attestation_context: Dict[str, Any] | None = None
    has_measured_attestation_binding = (
        _clean_runtime_identity_value(
            getattr(node, "runtime_identity_binding_type", None)
        ).lower()
        == "measured_attestation"
        and bool(getattr(node, "runtime_identity_binding_hash", None))
    )
    if bool(getattr(node, "enclave_enabled", False)) and (
        node_status in {"pending", "pending_approval"}
        or not has_measured_attestation_binding
        or attestation_data is not None
    ):
        measured_attestation_context = verified_measured_attestation_context(
            attestation_data
        )
        bind_node_runtime_identity(
            node,
            db,
            {
                "binding_type": "measured_attestation",
                "attestation_digest": measured_attestation_context[
                    "attestation_digest"
                ],
            },
        )
        has_measured_attestation_binding = True
        logger.info("TEE attestation verified for node %s", node_id)

    if node_status == "approved":
        signed = token_signer.sign_token(instance.join_token, mesh_id)
        return {
            "status": "approved",
            "join_token": signed,
            "already_approved": True,
            "hardware_attestation_verified": (
                measured_attestation_context is not None
                or has_measured_attestation_binding
            ),
            "raw_hardware_attestation_redacted": True,
            "attestation_verifier_backend": (
                str(measured_attestation_context.get("attestation_verifier_backend"))
                if measured_attestation_context
                else None
            ),
            "attestation_verifier_provenance": (
                dict(
                    measured_attestation_context.get(
                        "attestation_verifier_provenance"
                    )
                    or {}
                )
                if measured_attestation_context
                else {}
            ),
            "production_attestation_verifier_claim_allowed": bool(
                measured_attestation_context
                and measured_attestation_context.get(
                    "production_attestation_verifier_claim_allowed"
                )
            ),
        }

    node.status = "approved"
    node.runtime_credential_expires_at = node_runtime_credential_expires_at()
    db.commit()

    signed = token_signer.sign_token(instance.join_token, mesh_id)
    
    logger.info(f"✅ Node {node_id} approved by user {current_user.id}")
    return {
        "status": "approved",
        "join_token": signed,
        "hardware_attestation_verified": measured_attestation_context is not None,
        "raw_hardware_attestation_redacted": bool(
            getattr(node, "enclave_enabled", False)
        ),
        "attestation_verifier_backend": (
            str(measured_attestation_context.get("attestation_verifier_backend"))
            if measured_attestation_context
            else None
        ),
        "attestation_verifier_provenance": (
            dict(
                measured_attestation_context.get("attestation_verifier_provenance")
                or {}
            )
            if measured_attestation_context
            else {}
        ),
        "production_attestation_verifier_claim_allowed": bool(
            measured_attestation_context
            and measured_attestation_context.get(
                "production_attestation_verifier_claim_allowed"
            )
        ),
    }


def revoke_node(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
) -> Dict[str, str]:
    """Revoke a node's access."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    node.status = "revoked"
    db.commit()
    logger.info(f"🔒 Node {node_id} revoked by user {current_user.id}")
    return {"status": "revoked", "node_id": node_id}


def delete_node(
    mesh_id: str,
    node_id: str,
    db: Session,
    current_user: User,
) -> Dict[str, str]:
    """Permanently delete a node."""
    node = db.query(MeshNode).filter(MeshNode.id == node_id, MeshNode.mesh_id == mesh_id).first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    
    db.delete(node)
    db.commit()
    logger.info(f"🗑️ Node {node_id} deleted by user {current_user.id}")
    return {"status": "deleted", "node_id": node_id}


"""
measured_attestation_approval
require_measured_attestation
verify_attestation_digest_freshness
runtime_identity_measured_attestation_provenance_verified
RedactedMeasuredAttestationSmokeArtifact
smoke_artifact_writer
write_measured_attestation_verifier_smoke_artifact
"""
