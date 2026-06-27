"""
x0tta6bl4 Agent Integrity & Supply Chain Verification.

Handles:
- Binary hash calculation.
- SBOM/Attestation verification against MaaS Supply Chain API.
- PQC-signed metadata validation.
"""
from __future__ import annotations

import hashlib
import logging
import os
import sys
from typing import Any, Dict, Tuple

try:
    import httpx
except ImportError:
    httpx = None

logger = logging.getLogger(__name__)

# Default MaaS Supply Chain API endpoint (can be overridden by env)
MAAS_SC_URL = os.getenv("MAAS_SUPPLY_CHAIN_URL", "http://localhost:8000/api/v1/maas/supply-chain")

def calculate_binary_hash() -> str:
    """Calculate SHA-256 hash of the currently running agent binary."""
    try:
        main_file = sys.modules['__main__'].__file__
        if main_file and os.path.exists(main_file):
            with open(main_file, "rb") as f:
                return "sha256:" + hashlib.sha256(f.read()).hexdigest()
    except Exception:
        pass
    
    executable = getattr(sys, "executable", "")
    if executable and os.path.exists(executable):
        with open(executable, "rb") as f:
            return "sha256:" + hashlib.sha256(f.read()).hexdigest()

    fallback_material = f"{sys.version}:{sys.argv[0]}".encode()
    logger.warning("Falling back to runtime fingerprint for binary hash")
    return "sha256:" + hashlib.sha256(fallback_material).hexdigest()


def _strict_integrity_enabled() -> bool:
    return os.getenv("X0TTA6BL4_INTEGRITY_FAIL_OPEN", "false").strip().lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }


def _require_sbom_signature() -> bool:
    return os.getenv("X0TTA6BL4_REQUIRE_SBOM_PQC_SIGNATURE", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _verify_sbom_signature(
    sbom: Dict[str, Any],
    *,
    agent_version: str,
    checksum_sha256: str,
) -> Tuple[bool, str]:
    pqc_sig = sbom.get("pqc_signature")
    if not pqc_sig:
        return False, "missing pqc_signature"

    public_key_hex = sbom.get("pqc_public_key")
    if not public_key_hex:
        return False, "missing pqc_public_key"

    try:
        signature = bytes.fromhex(str(pqc_sig))
        public_key = bytes.fromhex(str(public_key_hex))
    except ValueError:
        return False, "invalid hex signature or public key"

    try:
        from src.core.app import pqc_verify

        payload = f"{agent_version}:{checksum_sha256}".encode()
        if pqc_verify(payload, signature, public_key):
            return True, "verified"
        return False, "pqc_verify returned false"
    except Exception as exc:
        return False, f"pqc verification failed: {exc}"

async def verify_integrity(node_id: str, agent_version: str) -> bool:
    """
    Verify agent integrity against MaaS Supply Chain registry.
    Returns True if verified, False if mismatch or compromised.
    """
    if not httpx:
        logger.warning("httpx not available, skipping remote integrity verification")
        return True

    checksum = calculate_binary_hash()
    logger.info(f"🛡️ Integrity check: version={agent_version}, checksum={checksum}")

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 1. Fetch SBOM for this version
            resp = await client.get(f"{MAAS_SC_URL}/sbom/{agent_version}")
            if resp.status_code != 200:
                logger.error(f"❌ Failed to fetch SBOM for version {agent_version}: {resp.status_code}")
                return False
            
            sbom = resp.json()
            
            # 2. Check checksum match
            expected_checksum = sbom.get("checksum_sha256")
            if checksum != expected_checksum:
                logger.error(f"🚨 INTEGRITY MISMATCH! Expected {expected_checksum}, found {checksum}")
                
                # Report mismatch to MaaS
                await client.post(f"{MAAS_SC_URL}/verify-binary", json={
                    "node_id": node_id,
                    "agent_version": agent_version,
                    "checksum_sha256": checksum
                })
                return False

            # 3. Verify PQC signature when enough material is present.
            signature_ok, signature_reason = _verify_sbom_signature(
                sbom,
                agent_version=agent_version,
                checksum_sha256=expected_checksum,
            )
            if signature_ok:
                logger.info("✅ SBOM PQC-signature verified")
            else:
                logger.warning("⚠️ SBOM PQC-signature not verified: %s", signature_reason)
                if _require_sbom_signature():
                    return False

            # 4. Report successful attestation
            await client.post(f"{MAAS_SC_URL}/verify-binary", json={
                "node_id": node_id,
                "agent_version": agent_version,
                "checksum_sha256": checksum
            })
            
            logger.info("✅ Agent integrity verified against MaaS Supply Chain registry")
            return True

    except Exception as e:
        logger.error(f"⚠️ Integrity verification failed due to error: {e}")
        return not _strict_integrity_enabled()

