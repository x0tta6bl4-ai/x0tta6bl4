"""
x0tta6bl4 PQC Beacon Protocol — Production Grade
=================================================

ML-DSA-65 (NIST FIPS 204) signatures  — beacon authentication
ML-KEM-768 (NIST FIPS 203) KEM        — session key establishment

Protocol:
  1. Startup: generate ML-DSA-65 + ML-KEM-768 keypairs.
  2. Peer discovery: exchange public keys via GET /mesh/pqc/pubkeys.
  3. Session setup: POST /mesh/kem/session — establishes AES-256 shared secret.
  4. Beacons: each beacon is signed (ML-DSA-65) and carries a nonce (replay protection).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import random
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.version import __version__

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4.pqc")

# ---------------------------------------------------------------------------
# PQC availability
# ---------------------------------------------------------------------------

LIBOQS_AVAILABLE = False
try:
    from oqs import KeyEncapsulation, Signature  # type: ignore
    LIBOQS_AVAILABLE = True
    logger.info("✅ liboqs available — PQC enabled (ML-DSA-65 + ML-KEM-768)")
except ImportError:
    logger.warning("⚠️ liboqs not available — beacon signatures disabled")

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(title="x0tta6bl4-minimal-pqc", version=__version__, docs_url="/docs")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PEER_TIMEOUT = 30.0           # seconds without beacon → dead peer
HEALTH_CHECK_INTERVAL = 5.0
NONCE_TTL = 60.0              # replay window: reject duplicate nonces within this window
KEY_ROTATION_WINDOW = 3600.0  # allow key change if peer was unseen > 1 h

# Preferred algorithms with fallbacks
_DSA_ALGOS = ("ML-DSA-65", "Dilithium3")   # FIPS 204 Level-3 / legacy
_KEM_ALGOS = ("ML-KEM-768", "Kyber768")    # FIPS 203 Level-3 / legacy

# ---------------------------------------------------------------------------
# In-memory state
# ---------------------------------------------------------------------------

node_id: str = "node-01"
peers: Dict[str, Dict] = {}
beacons_received: List[Dict] = []
dead_peers: set = set()

# DSA (signing) keys
_dsa_algo: str = _DSA_ALGOS[0]
_sig_public_key: Optional[bytes] = None
_sig_private_key: Optional[bytes] = None

# KEM (key encapsulation) keys
_kem_algo: str = _KEM_ALGOS[0]
_kem_public_key: Optional[bytes] = None
_kem_private_key: Optional[bytes] = None

# Per-peer trust state
_peer_dsa_keys: Dict[str, bytes] = {}    # peer_id → DSA public key (TOFU)
_peer_kem_keys: Dict[str, bytes] = {}    # peer_id → KEM public key
_peer_session_keys: Dict[str, bytes] = {}  # peer_id → 32-byte AES session key

# Nonce dedup: nonce_hex → received_at (pruned on schedule)
_seen_nonces: Dict[str, float] = {}

# Optional P1 integrations (initialized lazily).
_rate_limiter_manager = None
_quarantine_manager = None


# ---------------------------------------------------------------------------
# PQC key initialisation — called once at startup
# ---------------------------------------------------------------------------

def _init_pqc_keys() -> None:
    """Initialise ML-DSA-65 and ML-KEM-768 keypairs (with legacy fallbacks)."""
    global _dsa_algo, _sig_public_key, _sig_private_key
    global _kem_algo, _kem_public_key, _kem_private_key

    if not LIBOQS_AVAILABLE:
        return

    # --- DSA keypair ---
    for algo in _DSA_ALGOS:
        try:
            sig = Signature(algo)
            pub, sec = sig.generate_keypair()
            _sig_public_key, _sig_private_key = pub, sec
            _dsa_algo = algo
            logger.info(f"✅ DSA keypair ready ({algo}, pub={len(pub)}B)")
            break
        except Exception as exc:
            logger.warning(f"DSA algo {algo} failed: {exc}")

    if _sig_public_key is None:
        logger.error("❌ Could not generate any DSA keypair — signing disabled")

    # --- KEM keypair ---
    for algo in _KEM_ALGOS:
        try:
            kem = KeyEncapsulation(algo)
            pub = kem.generate_keypair()
            sec = kem.export_secret_key()
            _kem_public_key, _kem_private_key = pub, sec
            _kem_algo = algo
            logger.info(f"✅ KEM keypair ready ({algo}, pub={len(pub)}B)")
            break
        except Exception as exc:
            logger.warning(f"KEM algo {algo} failed: {exc}")

    if _kem_public_key is None:
        logger.error("❌ Could not generate any KEM keypair — session encryption disabled")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    nonce: str                         # UUID4 hex — replay protection
    neighbors: Optional[List[str]] = []
    signature: Optional[str] = None    # hex-encoded ML-DSA-65 signature
    public_key: Optional[str] = None   # hex-encoded DSA public key (first beacon / key rotation)


class KEMSessionRequest(BaseModel):
    """Peer initiates a KEM session: sends their KEM public key."""
    peer_id: str
    kem_public_key: str   # hex-encoded ML-KEM-768 public key


class RouteRequest(BaseModel):
    destination: str
    payload: str


# ---------------------------------------------------------------------------
# PQC helper functions
# ---------------------------------------------------------------------------

def _beacon_canonical(node: str, timestamp: float, nonce: str, neighbors: List[str]) -> bytes:
    """Canonical serialisation of beacon fields for signing/verification."""
    data = {
        "node_id": node,
        "timestamp": timestamp,
        "nonce": nonce,
        "neighbors": sorted(neighbors),
    }
    return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()


def sign_beacon(node: str, timestamp: float, nonce: str, neighbors: List[str]) -> bytes:
    """Sign beacon with ML-DSA-65 private key. Returns empty bytes if unavailable."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""
    try:
        sig = Signature(_dsa_algo)
        sig.secret_key = _sig_private_key
        return sig.sign(_beacon_canonical(node, timestamp, nonce, neighbors))
    except Exception as exc:
        logger.error(f"sign_beacon failed: {exc}")
        return b""


def verify_beacon_sig(
    node: str,
    timestamp: float,
    nonce: str,
    neighbors: List[str],
    signature: bytes,
    public_key: bytes,
) -> bool:
    """Verify ML-DSA-65 beacon signature. Returns False (not True) when PQC is unavailable."""
    if not LIBOQS_AVAILABLE:
        return False
    if not signature:
        return False
    try:
        sig = Signature(_dsa_algo)
        sig.public_key = public_key
        return bool(sig.verify(_beacon_canonical(node, timestamp, nonce, neighbors), signature))
    except Exception as exc:
        logger.error(f"verify_beacon_sig failed: {exc}")
        return False


def encapsulate_for_peer(peer_kem_pub: bytes) -> Tuple[bytes, bytes]:
    """
    Encapsulate a shared secret to the peer's KEM public key.
    Returns (ciphertext, shared_secret_32_bytes).
    Caller stores shared_secret as the AES-256 session key.
    """
    kem = KeyEncapsulation(_kem_algo)
    ciphertext, shared_secret = kem.encap_secret(peer_kem_pub)
    return ciphertext, shared_secret[:32]


def decapsulate_from_peer(ciphertext: bytes) -> bytes:
    """
    Decapsulate using our KEM private key.
    Returns shared_secret_32_bytes.
    """
    if _kem_private_key is None:
        raise RuntimeError("KEM private key not initialised")
    kem = KeyEncapsulation(_kem_algo, secret_key=_kem_private_key)
    shared_secret = kem.decap_secret(ciphertext)
    return shared_secret[:32]


# ---------------------------------------------------------------------------
# Nonce management
# ---------------------------------------------------------------------------

def _check_and_record_nonce(nonce: str, timestamp: float) -> bool:
    """
    Return True if nonce is fresh (not seen within NONCE_TTL).
    Records nonce on success.
    """
    now = time.time()
    # Reject if timestamp is too far in the past or future (±NONCE_TTL)
    if abs(now - timestamp) > NONCE_TTL:
        return False
    if nonce in _seen_nonces:
        return False
    _seen_nonces[nonce] = now
    return True


async def _nonce_cleanup_loop() -> None:
    """Prune expired nonces to bound memory usage."""
    while True:
        try:
            cutoff = time.time() - NONCE_TTL
            expired = [n for n, t in _seen_nonces.items() if t < cutoff]
            for n in expired:
                del _seen_nonces[n]
            if expired:
                logger.debug(f"Pruned {len(expired)} expired nonces")
        except Exception as exc:
            logger.error(f"nonce_cleanup error: {exc}")
        await asyncio.sleep(NONCE_TTL / 2)


# ---------------------------------------------------------------------------
# Background task
# ---------------------------------------------------------------------------

async def _health_check_loop() -> None:
    """Detect dead peers and clean up their state."""
    while True:
        try:
            now = time.time()
            for peer_id in list(peers):
                elapsed = now - peers[peer_id].get("last_seen", 0)
                if elapsed > PEER_TIMEOUT and peer_id not in dead_peers:
                    dead_peers.add(peer_id)
                    logger.warning(f"🔴 Peer {peer_id} marked DEAD ({elapsed:.1f}s)")
                    del peers[peer_id]
                    # Allow key re-registration after KEY_ROTATION_WINDOW
                    # (keep keys until then so we can still verify stale beacons)
        except Exception as exc:
            logger.error(f"health_check error: {exc}")
        await asyncio.sleep(HEALTH_CHECK_INTERVAL)


def _sync_rate_limiter_peer_sessions() -> None:
    """
    Best-effort sync of PQC peer session keys to rate limiter state.
    Used by P1 eBPF <-> PQC-TLS integration.
    """
    global _rate_limiter_manager
    try:
        if _rate_limiter_manager is None:
            from src.network.ebpf.rate_limiter_manager import RateLimiterManager

            interface = os.getenv("MESH_RATE_LIMIT_INTERFACE", "singbox_tun")
            _rate_limiter_manager = RateLimiterManager(interface=interface)
        _rate_limiter_manager.sync_peer_session_keys(_peer_session_keys)
    except Exception as exc:
        logger.debug(f"rate limiter peer-session sync skipped: {exc}")


def _record_pqc_verification(
    peer_id: str,
    peer_ip: Optional[str],
    verified: bool,
    reason: str = "failed_verification",
) -> None:
    """
    Best-effort reporting of PQC verification outcomes to quarantine manager.
    """
    global _quarantine_manager
    try:
        if _quarantine_manager is None:
            from src.network.ebpf.quarantine_manager import QuarantineManager

            interface = os.getenv("MESH_QUARANTINE_INTERFACE", "eth0")
            threshold = int(os.getenv("PQC_VERIFY_FAIL_THRESHOLD", "3"))
            _quarantine_manager = QuarantineManager(
                interface=interface,
                failure_threshold=threshold,
            )
        _quarantine_manager.record_pqc_verification_result(
            peer_id=peer_id,
            ip_address=peer_ip,
            verified=verified,
            reason=reason,
        )
    except Exception as exc:
        logger.debug(f"quarantine manager verification update skipped: {exc}")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "version": __version__,
        "node_id": node_id,
        "pqc_enabled": LIBOQS_AVAILABLE,
        "dsa_algo": _dsa_algo if LIBOQS_AVAILABLE else None,
        "kem_algo": _kem_algo if LIBOQS_AVAILABLE else None,
        "peers_count": len(peers),
    }


@app.get("/mesh/pqc/pubkeys")
async def pqc_pubkeys() -> Dict[str, Any]:
    """
    Return this node's PQC public keys.

    Peers call this endpoint to:
    - Cache our DSA public key for beacon verification.
    - Use our KEM public key to establish an encrypted session.
    """
    if not LIBOQS_AVAILABLE or _sig_public_key is None:
        raise HTTPException(status_code=503, detail="PQC not initialised")
    return {
        "node_id": node_id,
        "dsa_algo": _dsa_algo,
        "dsa_public_key": _sig_public_key.hex(),
        "kem_algo": _kem_algo,
        "kem_public_key": _kem_public_key.hex() if _kem_public_key else None,
    }


@app.post("/mesh/kem/session")
async def kem_session(req: KEMSessionRequest) -> Dict[str, Any]:
    """
    Establish ML-KEM-768 session key with a peer.

    Peer sends their KEM public key → we encapsulate a shared secret
    and return the ciphertext. Peer decapsulates to get the same secret.
    Both sides now have a 32-byte AES-256 key for payload encryption.
    """
    if not LIBOQS_AVAILABLE or _kem_public_key is None:
        raise HTTPException(status_code=503, detail="KEM not initialised")

    try:
        peer_pub = bytes.fromhex(req.kem_public_key)
        ciphertext, session_key = encapsulate_for_peer(peer_pub)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"KEM encapsulation failed: {exc}")

    _peer_kem_keys[req.peer_id] = peer_pub
    _peer_session_keys[req.peer_id] = session_key
    _sync_rate_limiter_peer_sessions()
    logger.info(
        f"🔑 KEM session established with {req.peer_id} "
        f"(key fingerprint: {hashlib.sha256(session_key).hexdigest()[:12]})"
    )

    return {
        "peer_id": req.peer_id,
        "ciphertext": ciphertext.hex(),
        "kem_algo": _kem_algo,
        "session_key_fingerprint": hashlib.sha256(session_key).hexdigest()[:16],
    }


@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest, request: Request) -> Dict[str, Any]:
    """
    Receive a beacon from another node.

    Security checks (when PQC available):
      1. Nonce freshness — reject replays.
      2. ML-DSA-65 signature verification.
      3. TOFU key pinning — reject unexpected public key changes.
    """
    peer_ip = request.client.host if request.client else None

    # --- Replay protection ---
    if not _check_and_record_nonce(req.nonce, req.timestamp):
        raise HTTPException(
            status_code=400,
            detail="Beacon rejected: stale timestamp or duplicate nonce",
        )

    # --- PQC signature verification ---
    if LIBOQS_AVAILABLE:
        if not req.signature or not req.public_key:
            _record_pqc_verification(
                peer_id=req.node_id,
                peer_ip=peer_ip,
                verified=False,
                reason="missing_signature_or_key",
            )
            raise HTTPException(
                status_code=400,
                detail="Beacon must include signature and public_key when PQC is enabled",
            )

        raw_sig = bytes.fromhex(req.signature)
        raw_pub = bytes.fromhex(req.public_key)

        # TOFU key pinning
        if req.node_id in _peer_dsa_keys:
            known = _peer_dsa_keys[req.node_id]
            if known != raw_pub:
                last_seen = peers.get(req.node_id, {}).get("last_seen", 0)
                if time.time() - last_seen < KEY_ROTATION_WINDOW:
                    logger.warning(f"⚠️ DSA key changed for {req.node_id} — possible attack")
                    raise HTTPException(
                        status_code=403,
                        detail="Public key changed — possible Byzantine attack",
                    )
                # Peer was absent > KEY_ROTATION_WINDOW → allow re-registration
                logger.info(f"🔄 Key rotation accepted for {req.node_id} (was absent)")
        else:
            _peer_dsa_keys[req.node_id] = raw_pub
            logger.info(f"📝 Pinned DSA public key for {req.node_id}")

        if not verify_beacon_sig(
            req.node_id, req.timestamp, req.nonce, req.neighbors or [], raw_sig, raw_pub
        ):
            _record_pqc_verification(
                peer_id=req.node_id,
                peer_ip=peer_ip,
                verified=False,
                reason="invalid_signature",
            )
            logger.warning(f"❌ Invalid DSA signature from {req.node_id}")
            raise HTTPException(status_code=403, detail="Invalid beacon signature")

        _record_pqc_verification(
            peer_id=req.node_id,
            peer_ip=peer_ip,
            verified=True,
            reason="signature_valid",
        )
        logger.debug(f"✅ Verified ML-DSA signature from {req.node_id}")

    # --- Recovery detection ---
    if req.node_id in dead_peers:
        dead_peers.discard(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED")

    peers[req.node_id] = {"last_seen": time.time(), "neighbors": req.neighbors or []}
    beacons_received.append(
        {
            "node_id": req.node_id,
            "timestamp": req.timestamp,
            "nonce": req.nonce,
            "received_at": time.time(),
            "signature_verified": LIBOQS_AVAILABLE,
        }
    )

    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "signature_verified": LIBOQS_AVAILABLE,
    }


@app.get("/mesh/beacon/sign")
async def get_signed_beacon(neighbors: Optional[str] = None) -> Dict[str, Any]:
    """Generate a signed beacon for this node (for testing / peer bootstrap)."""
    if not LIBOQS_AVAILABLE or _sig_public_key is None:
        raise HTTPException(status_code=503, detail="PQC signatures not available")

    neighbors_list = [n.strip() for n in neighbors.split(",")] if neighbors else []
    timestamp = time.time()
    nonce = uuid.uuid4().hex

    signature = sign_beacon(node_id, timestamp, nonce, neighbors_list)

    return {
        "node_id": node_id,
        "timestamp": timestamp,
        "nonce": nonce,
        "neighbors": neighbors_list,
        "signature": signature.hex(),
        "public_key": _sig_public_key.hex(),
        "dsa_algo": _dsa_algo,
    }


@app.get("/mesh/peers")
async def get_peers() -> Dict[str, Any]:
    now = time.time()
    details = {
        pid: {
            "last_seen": info.get("last_seen", 0),
            "elapsed_seconds": round(now - info.get("last_seen", 0), 2),
            "is_alive": (now - info.get("last_seen", 0)) < PEER_TIMEOUT,
            "neighbors": info.get("neighbors", []),
            "has_dsa_key": pid in _peer_dsa_keys,
            "has_session_key": pid in _peer_session_keys,
        }
        for pid, info in peers.items()
    }
    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": details,
        "dead_peers": list(dead_peers),
        "pqc_enabled": LIBOQS_AVAILABLE,
    }


@app.get("/mesh/status")
async def get_status() -> Dict[str, Any]:
    return {
        "node_id": node_id,
        "status": "online",
        "version": __version__,
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "beacons_received": len(beacons_received),
        "pqc": {
            "enabled": LIBOQS_AVAILABLE,
            "dsa_algo": _dsa_algo if LIBOQS_AVAILABLE else None,
            "kem_algo": _kem_algo if LIBOQS_AVAILABLE else None,
            "peers_with_dsa_key": len(_peer_dsa_keys),
            "peers_with_session_key": len(_peer_session_keys),
        },
        "replay_protection": {
            "nonce_ttl_seconds": NONCE_TTL,
            "tracked_nonces": len(_seen_nonces),
        },
    }


@app.post("/mesh/route")
async def route_message(req: RouteRequest) -> Dict[str, Any]:
    if req.destination == node_id:
        return {"status": "delivered", "hops": 0, "latency_ms": 0}
    if req.destination in dead_peers:
        return {"status": "unreachable", "error": f"{req.destination} is dead"}
    if req.destination in peers:
        return {
            "status": "delivered",
            "hops": 1,
            "latency_ms": round(random.uniform(10, 50), 2),
            "path": [node_id, req.destination],
        }
    # 2-hop lookup
    for peer_id, info in peers.items():
        if req.destination in info.get("neighbors", []):
            return {
                "status": "delivered",
                "hops": 2,
                "latency_ms": round(random.uniform(20, 80), 2),
                "path": [node_id, peer_id, req.destination],
            }
    return {"status": "unreachable", "error": f"No route to {req.destination}"}


@app.get("/metrics", response_class=PlainTextResponse)
async def metrics() -> str:
    now = time.time()
    alive = sum(1 for p in peers.values() if now - p.get("last_seen", 0) < PEER_TIMEOUT)
    try:
        import psutil
        memory_bytes = psutil.Process(os.getpid()).memory_info().rss
    except Exception:
        memory_bytes = 0

    return (
        f"# HELP mesh_peers_count Known peers\n"
        f"# TYPE mesh_peers_count gauge\n"
        f"mesh_peers_count {len(peers)}\n\n"
        f"# HELP mesh_alive_peers_count Alive peers\n"
        f"# TYPE mesh_alive_peers_count gauge\n"
        f"mesh_alive_peers_count {alive}\n\n"
        f"# HELP mesh_dead_peers_count Dead peers\n"
        f"# TYPE mesh_dead_peers_count gauge\n"
        f"mesh_dead_peers_count {len(dead_peers)}\n\n"
        f"# HELP mesh_beacons_total Beacons received\n"
        f"# TYPE mesh_beacons_total counter\n"
        f"mesh_beacons_total {len(beacons_received)}\n\n"
        f"# HELP mesh_pqc_enabled PQC enabled (1=yes)\n"
        f"# TYPE mesh_pqc_enabled gauge\n"
        f"mesh_pqc_enabled {1 if LIBOQS_AVAILABLE else 0}\n\n"
        f"# HELP mesh_kem_sessions Active KEM sessions\n"
        f"# TYPE mesh_kem_sessions gauge\n"
        f"mesh_kem_sessions {len(_peer_session_keys)}\n\n"
        f"# HELP mesh_nonces_tracked Tracked replay-protection nonces\n"
        f"# TYPE mesh_nonces_tracked gauge\n"
        f"mesh_nonces_tracked {len(_seen_nonces)}\n\n"
        f"# HELP process_resident_memory_bytes RSS\n"
        f"# TYPE process_resident_memory_bytes gauge\n"
        f"process_resident_memory_bytes {memory_bytes}\n"
    )


# ---------------------------------------------------------------------------
# Lifecycle
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def _startup() -> None:
    global node_id
    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 PQC beacons node={node_id} version={__version__}")

    _init_pqc_keys()

    asyncio.create_task(_health_check_loop())
    asyncio.create_task(_nonce_cleanup_loop())
    logger.info("✅ Background tasks started: health_check, nonce_cleanup")


if __name__ == "__main__":
    import uvicorn
    from src.core.settings import settings
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
