"""
Ghost VPN Wire Protocol
========================
Message types, session management, and IP pool for Ghost VPN.
Shared between server and client.
"""

import hashlib
import hmac
import ipaddress
import json
import logging
import os
import pathlib
import secrets
import socket
import struct
import time
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Any, Dict, Optional, Set, Tuple

try:
    from src.network.transport.ghost_proto import ObfuscationProfile
except ImportError:
    class ObfuscationProfile(Enum):
        SRTP = "srtp"
        DNS = "dns"
        STEAM = "steam"

logger = logging.getLogger("GhostVPN-Protocol")

# ── Message Types ──────────────────────────────────────────────
class MsgType(IntEnum):
    HANDSHAKE_INIT = 0x01   # Client → Server: PQC public key
    HANDSHAKE_RESP = 0x02   # Server → Client: ciphertext + assigned IP
    DATA           = 0x03   # Bidirectional: encrypted IP packets
    PING           = 0x04   # Bidirectional keepalive request
    PONG           = 0x05   # Bidirectional keepalive response
    DISCONNECT     = 0x06   # Client → Server: graceful teardown
    HANDSHAKE_COOKIE = 0x07 # Server → Client: stateless retry token
    STRATEGY_SYNC  = 0x08   # Client → Server: propose negotiated runtime strategy
    STRATEGY_ACK   = 0x09   # Server → Client: strategy accepted/applied
    PROFILE_SWITCH = 0x0A   # Server → Client: recommend profile switch (DPI detected)
    PROFILE_SWITCH_ACK = 0x0B  # Client → Server: profile switch completed


AUTH_KEY_ENV = "GHOST_VPN_AUTH_KEY"
AUTH_KEY_FILE_ENV = "GHOST_VPN_AUTH_KEY_FILE"
CREDENTIALS_DIRECTORY_ENV = "CREDENTIALS_DIRECTORY"
SYSTEMD_AUTH_KEY_CREDENTIAL_NAME = "ghost-vpn-key"
AUTH_TAG_SIZE = 16
HANDSHAKE_INIT_MAGIC = b"GVP2"
LEGACY_HANDSHAKE_INIT_MAGIC = b"GVP1"
HANDSHAKE_RESP_MAGIC = b"GVR2"
LEGACY_HANDSHAKE_RESP_MAGIC = b"GVR1"
HANDSHAKE_COOKIE_MAGIC = b"GVC1"
STRATEGY_SYNC_MAGIC = b"GVS1"
COOKIE_ROTATION_SECONDS = 30

PROFILE_TO_ID = {
    ObfuscationProfile.SRTP: 0,
    ObfuscationProfile.DNS: 1,
    ObfuscationProfile.STEAM: 2,
}
ID_TO_PROFILE = {value: key for key, value in PROFILE_TO_ID.items()}


# ── Wire Helpers ───────────────────────────────────────────────
def pack_msg(msg_type: MsgType, payload: bytes = b"") -> bytes:
    """Pack a single-byte type header + payload."""
    return bytes([msg_type]) + payload


def unpack_msg(data: bytes) -> Tuple[Optional[MsgType], bytes]:
    """Return (MsgType, payload) or (None, b'') if malformed."""
    if not data:
        return None, b""
    try:
        return MsgType(data[0]), data[1:]
    except ValueError:
        return None, b""


def pack_protected_msg(
    auth_key: bytes,
    msg_type: MsgType,
    payload: bytes = b"",
) -> bytes:
    """Pack an authenticated GhostVPN control/data frame."""
    raw_payload = pack_msg(msg_type, payload)
    auth_tag = hmac.new(auth_key, raw_payload, hashlib.sha256).digest()[:AUTH_TAG_SIZE]
    return auth_tag + raw_payload


def unpack_protected_msg(
    auth_key: bytes,
    data: bytes,
) -> Tuple[Optional[MsgType], bytes]:
    """Unpack and authenticate a GhostVPN frame."""
    if len(data) < AUTH_TAG_SIZE + 1:
        return None, b""

    received_mac = data[:AUTH_TAG_SIZE]
    payload = data[AUTH_TAG_SIZE:]
    expected_mac = hmac.new(auth_key, payload, hashlib.sha256).digest()[:AUTH_TAG_SIZE]
    if not hmac.compare_digest(received_mac, expected_mac):
        return None, b""

    return unpack_msg(payload)


def pack_handshake_init(
    client_pub_key: bytes,
    profile: ObfuscationProfile = ObfuscationProfile.SRTP,
    cookie: bytes = b"",
) -> bytes:
    """Pack client handshake init with an explicit obfuscation profile + cookie."""
    profile_id = PROFILE_TO_ID.get(profile, PROFILE_TO_ID[ObfuscationProfile.SRTP])
    if len(cookie) > 255:
        raise ValueError("cookie too large")
    return HANDSHAKE_INIT_MAGIC + bytes([profile_id, len(cookie)]) + cookie + client_pub_key


def unpack_handshake_init(payload: bytes) -> Tuple[ObfuscationProfile, bytes, bytes]:
    """Unpack client handshake init, supporting legacy profile-less payloads."""
    if payload.startswith(HANDSHAKE_INIT_MAGIC) and len(payload) > len(HANDSHAKE_INIT_MAGIC):
        offset = len(HANDSHAKE_INIT_MAGIC)
        profile_id = payload[offset]
        offset += 1
        cookie_len = payload[offset]
        offset += 1
        profile = ID_TO_PROFILE.get(profile_id, ObfuscationProfile.SRTP)
        cookie = payload[offset:offset + cookie_len]
        offset += cookie_len
        return profile, cookie, payload[offset:]
    if payload.startswith(LEGACY_HANDSHAKE_INIT_MAGIC) and len(payload) > len(LEGACY_HANDSHAKE_INIT_MAGIC):
        profile_id = payload[len(LEGACY_HANDSHAKE_INIT_MAGIC)]
        profile = ID_TO_PROFILE.get(profile_id, ObfuscationProfile.SRTP)
        return profile, b"", payload[len(LEGACY_HANDSHAKE_INIT_MAGIC) + 1:]
    return ObfuscationProfile.SRTP, b"", payload


def pack_handshake_cookie(cookie: bytes) -> bytes:
    """
    Pack a stateless handshake cookie.

    Wire format: [MAGIC:4][LEN:1][COOKIE:0-255]

    Args:
        cookie: Opaque cookie bytes (max 255 bytes)

    Returns:
        Wire-format cookie frame

    Raises:
        ValueError: Cookie exceeds 255 bytes

    Note:
        Typically used for DDOS mitigation: server sends cookie challenge
        to unverified client, client echoes cookie in subsequent request.
    """
    if len(cookie) > 255:
        raise ValueError("cookie too large (max 255 bytes)")
    logger.debug(f"Packing handshake cookie: {len(cookie)}B")
    return HANDSHAKE_COOKIE_MAGIC + bytes([len(cookie)]) + cookie


def unpack_handshake_cookie(payload: bytes) -> bytes:
    """
    Unpack a stateless handshake cookie.

    Args:
        payload: Raw cookie frame from wire

    Returns:
        Opaque cookie bytes

    Raises:
        ValueError: Invalid magic, truncated, or malformed payload
    """
    if not payload.startswith(HANDSHAKE_COOKIE_MAGIC):
        raise ValueError("invalid handshake cookie magic")

    if len(payload) < len(HANDSHAKE_COOKIE_MAGIC) + 1:
        raise ValueError("handshake cookie too short (missing length byte)")

    offset = len(HANDSHAKE_COOKIE_MAGIC)
    cookie_len = payload[offset]
    offset += 1

    cookie = payload[offset:offset + cookie_len]
    if len(cookie) != cookie_len:
        raise ValueError(f"handshake cookie truncated: expected {cookie_len}B, got {len(cookie)}B")

    logger.debug(f"Unpacked handshake cookie: {len(cookie)}B")
    return cookie


def pack_strategy_sync(strategy: Dict[str, Any]) -> bytes:
    """Pack a negotiated runtime strategy proposal/ack payload."""
    strategy_id = str(strategy.get("strategy_id", "")).encode("utf-8")
    if len(strategy_id) > 255:
        raise ValueError("strategy_id too large")
    body = json.dumps(strategy, sort_keys=True).encode("utf-8")
    return STRATEGY_SYNC_MAGIC + bytes([len(strategy_id)]) + strategy_id + body


def unpack_strategy_sync(payload: bytes) -> Tuple[str, Dict[str, Any]]:
    """Unpack a negotiated runtime strategy payload."""
    if not payload.startswith(STRATEGY_SYNC_MAGIC):
        raise ValueError("invalid strategy sync magic")
    if len(payload) < len(STRATEGY_SYNC_MAGIC) + 1:
        raise ValueError("strategy sync payload too short")
    offset = len(STRATEGY_SYNC_MAGIC)
    strategy_id_len = payload[offset]
    offset += 1
    strategy_id_bytes = payload[offset:offset + strategy_id_len]
    if len(strategy_id_bytes) != strategy_id_len:
        raise ValueError("strategy id truncated")
    offset += strategy_id_len
    strategy_body = payload[offset:]
    strategy = json.loads(strategy_body.decode("utf-8"))
    strategy_id = strategy_id_bytes.decode("utf-8")
    if not strategy.get("strategy_id"):
        strategy["strategy_id"] = strategy_id
    return strategy_id, strategy


PROFILE_SWITCH_MAGIC = b"GPS1"


def pack_profile_switch(recommended_profile: str, reason: str = "dpi_detected") -> bytes:
    """Pack a server→client profile switch recommendation."""
    body = json.dumps(
        {"profile": recommended_profile, "reason": reason},
        sort_keys=True,
    ).encode("utf-8")
    return PROFILE_SWITCH_MAGIC + body


def unpack_profile_switch(payload: bytes) -> Tuple[str, str]:
    """Unpack a profile switch recommendation. Returns (profile, reason)."""
    if not payload.startswith(PROFILE_SWITCH_MAGIC):
        raise ValueError("invalid profile switch magic")
    body = json.loads(payload[len(PROFILE_SWITCH_MAGIC):].decode("utf-8"))
    return body["profile"], body.get("reason", "unknown")


PROFILE_SWITCH_ACK_MAGIC = b"GPA1"


def pack_profile_switch_ack(new_profile: str, latency_ms: float = 0.0) -> bytes:
    """Pack a profile switch ACK from client after successful reconnect."""
    body = json.dumps(
        {"profile": new_profile, "latency_ms": latency_ms},
        sort_keys=True,
    ).encode("utf-8")
    return PROFILE_SWITCH_ACK_MAGIC + body


def unpack_profile_switch_ack(payload: bytes) -> Tuple[str, float]:
    """Unpack profile switch ACK. Returns (new_profile, latency_ms)."""
    if not payload.startswith(PROFILE_SWITCH_ACK_MAGIC):
        raise ValueError("invalid profile switch ack magic")
    body = json.loads(payload[len(PROFILE_SWITCH_ACK_MAGIC):].decode("utf-8"))
    return body["profile"], body.get("latency_ms", 0.0)


def pack_handshake_resp(
    ciphertext: bytes,
    assigned_ip: str,
    profile: ObfuscationProfile = ObfuscationProfile.SRTP,
    auth_tag: bytes = b"",
) -> bytes:
    """
    Pack server handshake response with negotiated profile + IPv4.

    Args:
        ciphertext: Encapsulated shared secret from PQC
        assigned_ip: Virtual IPv4 address assigned to client
        profile: Obfuscation profile negotiated during handshake
        auth_tag: Optional HMAC-SHA256 tag binding response to request

    Returns:
        Wire format: [MAGIC:4][PROFILE:1][CT_LEN:2][AUTH_LEN:2][CT][IP:4][AUTH_TAG]

    Raises:
        ValueError: Invalid IPv4 address format
    """
    try:
        ip_bytes = socket.inet_aton(assigned_ip)
    except socket.error as e:
        logger.error(f"Invalid IPv4 address in handshake response: {assigned_ip}")
        raise ValueError(f"Invalid IPv4 address: {assigned_ip}") from e

    ct_len = struct.pack("!H", len(ciphertext))
    profile_id = PROFILE_TO_ID.get(profile, PROFILE_TO_ID[ObfuscationProfile.SRTP])
    auth_len = struct.pack("!H", len(auth_tag))
    return HANDSHAKE_RESP_MAGIC + bytes([profile_id]) + ct_len + auth_len + ciphertext + ip_bytes + auth_tag


def unpack_handshake_resp(payload: bytes) -> Tuple[bytes, str, ObfuscationProfile, bytes]:
    """
    Unpack handshake response, supporting both negotiated and legacy forms.

    Protocol versions supported:
    - GHR2 (current): [MAGIC:4][PROFILE:1][CT_LEN:2][AUTH_LEN:2][CT][IP:4][AUTH_TAG]
    - GHR1 (legacy): [MAGIC:4][PROFILE:1][CT_LEN:2][CT][IP:4]
    - Fallback: [CT_LEN:2][CT][IP:4]

    Args:
        payload: Raw bytes from wire

    Returns:
        Tuple of (ciphertext, assigned_ip, profile, auth_tag)

    Raises:
        ValueError: Malformed payload, truncated, or invalid IP address
    """
    offset = 0
    profile = ObfuscationProfile.SRTP
    auth_len = 0

    try:
        if payload.startswith(HANDSHAKE_RESP_MAGIC):
            if len(payload) < len(HANDSHAKE_RESP_MAGIC) + 1 + 2 + 2 + 4:
                raise ValueError("GHR2 handshake response too short")
            offset = len(HANDSHAKE_RESP_MAGIC)
            profile = ID_TO_PROFILE.get(payload[offset], ObfuscationProfile.SRTP)
            offset += 1
            ct_len = struct.unpack("!H", payload[offset:offset + 2])[0]
            offset += 2
            auth_len = struct.unpack("!H", payload[offset:offset + 2])[0]
            offset += 2

        elif payload.startswith(LEGACY_HANDSHAKE_RESP_MAGIC):
            if len(payload) < len(LEGACY_HANDSHAKE_RESP_MAGIC) + 1 + 2 + 4:
                raise ValueError("GHR1 handshake response too short")
            offset = len(LEGACY_HANDSHAKE_RESP_MAGIC)
            profile = ID_TO_PROFILE.get(payload[offset], ObfuscationProfile.SRTP)
            offset += 1
            ct_len = struct.unpack("!H", payload[offset:offset + 2])[0]
            offset += 2

        else:
            # Fallback: assume [CT_LEN:2][CT][IP:4]
            if len(payload) < 2 + 4:
                raise ValueError("handshake response too short")
            ct_len = struct.unpack("!H", payload[offset:offset + 2])[0]
            offset += 2

        # Extract ciphertext
        ciphertext = payload[offset:offset + ct_len]
        if len(ciphertext) != ct_len:
            raise ValueError(f"ciphertext truncated: expected {ct_len}B, got {len(ciphertext)}B")
        offset += ct_len

        # Extract IP address
        ip_bytes = payload[offset:offset + 4]
        if len(ip_bytes) != 4:
            raise ValueError(f"IP address truncated: expected 4B, got {len(ip_bytes)}B")
        offset += 4

        try:
            assigned_ip = socket.inet_ntoa(ip_bytes)
        except socket.error as e:
            raise ValueError(f"invalid IPv4 address bytes") from e

        # Extract optional auth tag
        auth_tag = payload[offset:offset + auth_len]
        if len(auth_tag) != auth_len:
            raise ValueError(f"auth tag truncated: expected {auth_len}B, got {len(auth_tag)}B")

        logger.debug(f"Unpacked handshake response: ip={assigned_ip}, profile={profile.name}")
        return ciphertext, assigned_ip, profile, auth_tag

    except ValueError as e:
        logger.warning(f"Failed to unpack handshake response: {e}")
        raise


def load_auth_key(auth_key: Optional[bytes | str]) -> bytes:
    """
    Load the GhostVPN authentication key from argument or environment.

    Priority:
    1. Argument (if provided and non-empty)
    2. GHOST_VPN_AUTH_KEY_FILE environment variable
    3. CREDENTIALS_DIRECTORY/ghost-vpn-key (systemd LoadCredential)
    4. GHOST_VPN_AUTH_KEY environment variable
    5. None (TypeError raised)

    Args:
        auth_key: Raw bytes or UTF-8 string, or None to use environment

    Returns:
        HMAC-SHA256 key (32+ bytes recommended)

    Raises:
        RuntimeError: No key provided and no supported env/file source set

    Note:
        In production, prefer GHOST_VPN_AUTH_KEY_FILE or systemd LoadCredential
        over embedding GHOST_VPN_AUTH_KEY directly in a unit file. Never rely on
        defaults or generate keys programmatically for authentication.
    """
    if auth_key is None:
        auth_key_file = os.environ.get(AUTH_KEY_FILE_ENV, "").strip()
        if auth_key_file:
            auth_key = pathlib.Path(auth_key_file).read_text(encoding="utf-8").strip()
        else:
            credentials_directory = os.environ.get(CREDENTIALS_DIRECTORY_ENV, "").strip()
            if credentials_directory:
                credential_path = pathlib.Path(credentials_directory) / SYSTEMD_AUTH_KEY_CREDENTIAL_NAME
                if credential_path.exists():
                    auth_key = credential_path.read_text(encoding="utf-8").strip()
                else:
                    auth_key = os.environ.get(AUTH_KEY_ENV)
            else:
                auth_key = os.environ.get(AUTH_KEY_ENV)
        if auth_key is None:
            raise RuntimeError(
                "GhostVPN authentication key required! Set "
                f"{AUTH_KEY_FILE_ENV}, {AUTH_KEY_ENV}, or provide systemd "
                f"{CREDENTIALS_DIRECTORY_ENV}/{SYSTEMD_AUTH_KEY_CREDENTIAL_NAME}. "
                "Generate with: openssl rand -hex 32"
            )

    if isinstance(auth_key, str):
        auth_key = auth_key.encode("utf-8")
    if not auth_key:
        raise RuntimeError(f"{AUTH_KEY_ENV} must not be empty")

    # Warn if key is weak (< 32 bytes)
    if len(auth_key) < 32:
        logger.warning(
            f"Weak GhostVPN authentication key: {len(auth_key)}B (recommended: ≥32B). "
            f"Generate with: openssl rand -base64 {32 * 4 // 3}"
        )

    logger.debug(f"Loaded {len(auth_key)}B GhostVPN authentication key")
    return auth_key


def compute_handshake_auth_tag(
    auth_key: bytes,
    client_pub_key: bytes,
    cookie: bytes,
    ciphertext: bytes,
    assigned_ip: str,
    profile: ObfuscationProfile,
) -> bytes:
    """
    Bind the server handshake response to the client request transcript.

    Creates a cryptographic commitment tying the handshake response to
    the specific request (client public key), cookie challenge, negotiated
    profile, and assigned IP. Prevents tampering/replays.

    Args:
        auth_key: HMAC-SHA256 shared secret
        client_pub_key: PQC public key from client handshake init
        cookie: Stateless challenge cookie (or empty if not challenged)
        ciphertext: Encapsulated shared secret from PQC
        assigned_ip: Virtual IPv4 address assigned to client
        profile: Obfuscation profile negotiated during handshake

    Returns:
        HMAC-SHA256 tag (32 bytes) to include in handshake response

    Note:
        Client verifies tag by recomputing with same inputs.
        Mismatch indicates tampering or server compromise.
    """
    profile_id = PROFILE_TO_ID.get(profile, PROFILE_TO_ID[ObfuscationProfile.SRTP])
    mac = hmac.new(auth_key, digestmod=hashlib.sha256)
    mac.update(b"ghostvpn-handshake-auth-v1")
    mac.update(struct.pack("!B", profile_id))
    mac.update(struct.pack("!H", len(cookie)))
    mac.update(cookie)
    mac.update(struct.pack("!I", len(client_pub_key)))
    mac.update(client_pub_key)
    mac.update(struct.pack("!I", len(ciphertext)))
    mac.update(ciphertext)
    mac.update(ipaddress.ip_address(assigned_ip).packed)
    return mac.digest()


# ── PING/PONG ────────────────────────────────────────────────────
# Carry a 4-byte sequence for RTT (round-trip time) measurement
# Used for keepalive and connection health monitoring

def pack_ping(seq: int) -> bytes:
    """
    Pack a PING keepalive message.

    Args:
        seq: Monotonically increasing sequence number for RTT tracking

    Returns:
        4-byte payload with big-endian sequence number
    """
    return struct.pack("!I", seq)


def unpack_ping(payload: bytes) -> int:
    """
    Unpack a PING keepalive message.

    Args:
        payload: Raw PING payload from wire

    Returns:
        Sequence number (0 if payload malformed or too short)

    Note:
        Returns 0 gracefully for truncated payloads rather than raising.
        Caller should not rely on 0 being a valid sequence (reserve for error).
    """
    if len(payload) < 4:
        logger.debug(f"Truncated PING payload: {len(payload)}B (expected ≥4B)")
        return 0
    return struct.unpack("!I", payload[:4])[0]


def pack_pong(seq: int) -> bytes:
    """Pack a PONG keepalive payload.

    GhostVPN uses the same 4-byte RTT sequence encoding for PING and PONG.
    """
    return pack_ping(seq)


def unpack_pong(payload: bytes) -> int:
    """Unpack a PONG keepalive payload."""
    return unpack_ping(payload)


# ── IP Pool ────────────────────────────────────────────────────
class IPPool:
    """
    Simple /24 IP address pool.
    .1 reserved for server, .2-.254 for clients.
    """

    def __init__(self, subnet: str = "10.8.0"):
        self.subnet = subnet
        self._used: Set[int] = set()

    def allocate(self) -> Optional[str]:
        """Allocate next available IP. Returns None if pool exhausted."""
        for octet in range(2, 255):
            if octet not in self._used:
                self._used.add(octet)
                return f"{self.subnet}.{octet}"
        return None

    def release(self, ip: str) -> None:
        """Release an IP back to the pool."""
        parts = ip.split(".")
        if len(parts) == 4:
            try:
                octet = int(parts[3])
                self._used.discard(octet)
            except ValueError:
                pass

    @property
    def available(self) -> int:
        return 253 - len(self._used)


# ── Session ────────────────────────────────────────────────────
@dataclass
class VPNSession:
    """
    Per-client session state maintained by server.

    Tracks one connected client including assigned IP, transport encryption,
    keepalive status, and traffic metrics. Sessions are created on successful
    handshake and removed on disconnect or timeout.

    Attributes:
        session_id: Unique session identifier (hex string)
        client_addr: (host, port) of client UDP endpoint
        assigned_ip: Virtual /32 IPv4 address for this client
        transport_layer: GhostTransport instance (encryption/decryption)
        created_at: Unix timestamp when session created
        last_activity: Unix timestamp of last packet (in/out/keepalive)
        ping_seq: Monotonically increasing PING sequence number
        last_pong_at: Unix timestamp when last PONG received
        bytes_in/out: Total bytes received/sent (encrypted)
        packets_in/out: Total packets received/sent
    """

    session_id: str
    client_addr: Tuple[str, int]
    assigned_ip: str
    transport_layer: object  # GhostTransport
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    ping_seq: int = 0
    last_pong_at: float = field(default_factory=time.time)
    bytes_in: int = 0
    bytes_out: int = 0
    packets_in: int = 0
    packets_out: int = 0
    negotiated_strategy_id: Optional[str] = None
    negotiated_strategy: Optional[Dict[str, Any]] = None

    def touch(self) -> None:
        """Update last_activity timestamp (called when packet arrives)."""
        self.last_activity = time.time()

    def is_expired(self, timeout: float = 120.0) -> bool:
        """
        Session expired if no activity for `timeout` seconds.

        Activity includes: data packets, successful keepalives (PONG).
        Expired sessions are reaped by server.
        """
        return (time.time() - self.last_activity) > timeout

    def is_dead(self, timeout: float = 90.0) -> bool:
        """
        Session dead if no PONG received within timeout.

        Indicates client no longer responding to PINGs.
        Dead sessions are reaped regardless of last_activity.
        """
        return (time.time() - self.last_pong_at) > timeout


class SessionManager:
    """
    Manages VPN sessions keyed by client UDP address.

    Maintains bidirectional mapping between UDP endpoints (host, port) and
    virtual IPv4 addresses. Allocates IPs from a pool, creates/destroys sessions,
    tracks metrics, and performs garbage collection of expired/dead sessions.

    Thread-safe: operates within asyncio event loop context (single-threaded).

    Attributes:
        sessions: Dict keyed by (host, port) → VPNSession
        ip_pool: IPPool for virtual IP allocation
        session_timeout: Inactivity threshold (seconds) for reaping
    """

    def __init__(self, ip_pool: Optional[IPPool] = None, session_timeout: float = 120.0):
        self.sessions: Dict[Tuple[str, int], VPNSession] = {}
        self._ip_to_addr: Dict[str, Tuple[str, int]] = {}  # virtual IP → client addr
        self.ip_pool = ip_pool or IPPool()
        self.session_timeout = session_timeout
        logger.debug(f"SessionManager initialized: subnet={self.ip_pool.subnet}, timeout={session_timeout}s")

    def create_session(
        self,
        client_addr: Tuple[str, int],
        transport_layer: object,
    ) -> Optional[VPNSession]:
        """
        Create a new session, allocating a virtual IP.

        If client already has an active session, tears it down first
        (prevents resource leaks from repeated handshakes).
        Always ensures old IP is released before allocating new one.

        Args:
            client_addr: (host, port) of client UDP endpoint
            transport_layer: GhostTransport or compatible cipher object

        Returns:
            VPNSession instance, or None if IP pool exhausted
        """
        # If client already has a session, tear it down first
        # This is critical to prevent IP pool leaks
        if client_addr in self.sessions:
            logger.warning(f"Duplicate session request from {client_addr[0]}; tearing down old session")
            old_session = self.sessions[client_addr]
            old_ip = old_session.assigned_ip

            # Remove from dicts
            self.sessions.pop(client_addr, None)
            self._ip_to_addr.pop(old_ip, None)

            # Return IP to pool (critical: do this BEFORE allocating new IP)
            self.ip_pool.release(old_ip)
            logger.debug(f"Released old IP {old_ip} back to pool")

        # Now allocate a fresh IP for the new session
        assigned_ip = self.ip_pool.allocate()
        if assigned_ip is None:
            logger.error("IP pool exhausted; cannot create new session")
            return None

        session = VPNSession(
            session_id=secrets.token_hex(8),
            client_addr=client_addr,
            assigned_ip=assigned_ip,
            transport_layer=transport_layer,
        )
        self.sessions[client_addr] = session
        self._ip_to_addr[assigned_ip] = client_addr
        logger.info(f"Session created: client={client_addr[0]}, ip={assigned_ip}, session_id={session.session_id}")
        return session

    def get_session(self, client_addr: Tuple[str, int]) -> Optional[VPNSession]:
        """Get session by client UDP address."""
        return self.sessions.get(client_addr)

    def get_session_by_ip(self, virtual_ip: str) -> Optional[VPNSession]:
        """Get session by assigned virtual IP address."""
        addr = self._ip_to_addr.get(virtual_ip)
        if addr:
            return self.sessions.get(addr)
        return None

    def remove_session(self, client_addr: Tuple[str, int]) -> None:
        """Remove a session and return its IP to the pool."""
        session = self.sessions.pop(client_addr, None)
        if session:
            self._ip_to_addr.pop(session.assigned_ip, None)
            self.ip_pool.release(session.assigned_ip)
            logger.info(f"Session removed: client={client_addr[0]}, ip={session.assigned_ip}")

    def cleanup_expired(self) -> list:
        """
        Remove expired/dead sessions. Returns list of removed client addresses.

        A session is reaped if:
        - No activity for session_timeout seconds, OR
        - No PONG received for 90 seconds (indicates dead connection)

        Returns:
            List of (host, port) tuples that were removed
        """
        to_remove = []
        for addr, session in self.sessions.items():
            if session.is_expired(self.session_timeout) or session.is_dead():
                to_remove.append(addr)

        for addr in to_remove:
            self.remove_session(addr)

        if to_remove:
            logger.info(f"Reaped {len(to_remove)} expired/dead sessions")

        return to_remove

    @property
    def active_count(self) -> int:
        """Current number of active sessions."""
        return len(self.sessions)
