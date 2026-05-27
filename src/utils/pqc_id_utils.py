"""
Utility functions for PQC Identity and DID integration in x0tta6bl4.
"""

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def _non_empty_string(value: Any) -> Optional[str]:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _verification_did(verification_method: Optional[str]) -> Optional[str]:
    if not verification_method:
        return None
    did = verification_method.split("#", 1)[0]
    return did if did.startswith("did:") else None


def _public_key_from_methods(
    methods: Any, verification_method: Optional[str]
) -> Optional[str]:
    if not isinstance(methods, list):
        return None

    fallback: Optional[str] = None
    for method in methods:
        if not isinstance(method, dict):
            method = getattr(method, "__dict__", {})
        key = _non_empty_string(
            method.get("publicKeyHex") or method.get("public_key_hex")
        )
        if not key:
            continue
        if verification_method and method.get("id") == verification_method:
            return key
        if fallback is None:
            fallback = key
    return fallback if not verification_method else None


def _public_key_from_document(
    document: Any, verification_method: Optional[str]
) -> Optional[str]:
    if document is None:
        return None

    if isinstance(document, str):
        return _non_empty_string(document)

    if not isinstance(document, dict):
        document = getattr(document, "__dict__", {})

    direct = _non_empty_string(
        document.get("publicKeyHex")
        or document.get("public_key_hex")
        or document.get("sig_public_key")
        or document.get("public_key")
    )
    if direct:
        return direct

    return _public_key_from_methods(
        document.get("verificationMethod") or document.get("verification_method"),
        verification_method,
    )


def _declared_callable(obj: Any, name: str) -> Optional[Any]:
    if name in getattr(obj, "__dict__", {}) or hasattr(type(obj), name):
        candidate = getattr(obj, name, None)
        if callable(candidate):
            return candidate
    return None


def _resolve_public_key_hex(
    signed_manifest: Dict[str, Any], identity_manager: Any
) -> Optional[str]:
    proof = signed_manifest.get("proof", {})
    if not isinstance(proof, dict):
        return None

    direct = _non_empty_string(
        proof.get("publicKeyHex")
        or proof.get("public_key_hex")
        or proof.get("publicKey")
    )
    if direct:
        return direct

    verification_method = _non_empty_string(
        proof.get("verificationMethod") or proof.get("verification_method")
    )
    did = (
        _verification_did(verification_method)
        or _non_empty_string(proof.get("controller"))
        or _non_empty_string(signed_manifest.get("did"))
    )

    manifest = signed_manifest.get("manifest", {})
    if did is None and isinstance(manifest, dict):
        did = _non_empty_string(manifest.get("did") or manifest.get("pqc_did"))

    if not did:
        return None

    local_document = getattr(identity_manager, "document", None)
    if getattr(local_document, "id", None) == did:
        return _public_key_from_document(local_document, verification_method)

    for resolver_name in (
        "resolve_public_key_hex",
        "get_public_key_hex",
        "get_public_key_for_did",
        "resolve_did",
        "resolve",
        "get_did_document",
    ):
        resolver = _declared_callable(identity_manager, resolver_name)
        if resolver is None:
            continue
        try:
            if resolver_name in {"resolve_public_key_hex", "get_public_key_hex"}:
                resolved = resolver(did, verification_method)
            else:
                resolved = resolver(did)
        except TypeError:
            resolved = resolver(did)
        key = _public_key_from_document(resolved, verification_method)
        if key:
            return key

    return None


def verify_pqc_manifest(signed_manifest: Dict[str, Any], identity_manager: Any) -> bool:
    """
    Verifies a PQC-signed manifest using the provided identity manager.
    
    Args:
        signed_manifest: Dict containing 'manifest' and 'proof' (signature)
        identity_manager: Instance of PQCNodeIdentity
        
    Returns:
        bool: True if verification succeeds
    """
    try:
        pubkey_hex = _resolve_public_key_hex(signed_manifest, identity_manager)
        if not pubkey_hex:
            logger.warning(
                "Manifest proof missing resolvable PQC public key; verification failed."
            )
            return False
            
        return identity_manager.verify_remote_node(signed_manifest, pubkey_hex)
    except Exception as e:
        logger.error(f"Error in manifest verification utility: {e}")
        return False

def extract_node_id_from_did(did: str) -> Optional[str]:
    """Extract node_id from did:mesh:pqc:<node_id>[:<key_id>]."""
    if not isinstance(did, str):
        return None

    parts = did.split(":")
    if len(parts) < 4:
        return None
    if parts[0] != "did" or parts[1] != "mesh" or parts[2] != "pqc":
        return None

    node_id = parts[3].strip()
    return node_id or None
