#!/usr/bin/env python3
"""
x0tta6bl4 GhostVPN Server
=========================
Multi-client L3 VPN server using the authenticated Ghost Protocol.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import math
import os
import socket
import struct
import subprocess
import sys
import time
from collections import defaultdict, deque, OrderedDict
from typing import Optional, Tuple
import atexit

from src.network.ghost_vpn_protocol import (
    AUTH_TAG_SIZE,
    COOKIE_ROTATION_SECONDS,
    IPPool,
    MsgType,
    PROFILE_TO_ID,
    SessionManager,
    compute_handshake_auth_tag,
    load_auth_key,
    pack_handshake_cookie,
    pack_handshake_resp,
    pack_ping,
    pack_profile_switch,
    pack_protected_msg,
    pack_strategy_sync,
    unpack_handshake_init,
    unpack_profile_switch_ack,
    unpack_protected_msg,
    unpack_strategy_sync,
)
from src.network.transport.ghost_handshake import GhostHandshake
from src.network.transport.ghost_proto import GhostTransport, ObfuscationProfile
from src.network.tun_handler import IPPacketParser, TUNInterface
from src.self_healing.rpc_bridge import MeshRPCBridge, HealingEvent, ProfileHint
from src.self_healing.mape_k import MAPEKMonitor, MAPEKAnalyzer, MAPEKPlanner, MAPEKExecutor, MAPEKKnowledge

logger = logging.getLogger("GhostVPN-Server")

KEEPALIVE_INTERVAL = int(os.getenv("GHOST_KEEPALIVE_SEC", "30"))
SESSION_TIMEOUT = int(os.getenv("GHOST_SESSION_TIMEOUT", "120"))
REAP_INTERVAL = int(os.getenv("GHOST_REAP_INTERVAL", "15"))
VPN_SUBNET = os.getenv("GHOST_SUBNET", "10.8.0")
VPN_PORT = int(os.getenv("GHOST_VPN_PORT", "4433"))
TUN_NAME = "tun_ghost_s"
TUN_MTU = 1400
HANDSHAKE_RESPONSE_CACHE_SEC = float(os.getenv("GHOST_HANDSHAKE_RESPONSE_CACHE_SEC", "10.0"))
TRUSTED_HANDSHAKE_TTL_SEC = float(os.getenv("GHOST_TRUSTED_HANDSHAKE_TTL_SEC", "600.0"))
HANDSHAKE_RATE_LIMIT = int(os.getenv("GHOST_HANDSHAKE_RATE_LIMIT", "100"))
HANDSHAKE_RATE_WINDOW = float(os.getenv("GHOST_HANDSHAKE_RATE_WINDOW", "10.0"))
METRICS_ENABLED = os.getenv("GHOST_METRICS_ENABLED", "1") == "1"
METRICS_HOST = os.getenv("GHOST_METRICS_HOST", "127.0.0.1")
METRICS_PORT = int(os.getenv("GHOST_METRICS_PORT", "9464"))
NODE_ID = os.getenv("GHOST_NODE_ID", os.getenv("NODE_ID", "ghost-server"))
MESH_NEIGHBORS = [n.strip() for n in os.getenv("GHOST_MESH_NEIGHBORS", "").split(",") if n.strip()]
COOKIE_REPLAY_CACHE_MAX = int(os.getenv("GHOST_COOKIE_REPLAY_CACHE_MAX", "10000"))
COOKIE_REPLAY_CACHE_TRIM_TO = int(os.getenv("GHOST_COOKIE_REPLAY_CACHE_TRIM_TO", "5000"))
ENABLE_TRUSTED_COOKIE_BYPASS = os.getenv("GHOST_ENABLE_TRUSTED_COOKIE_BYPASS", "0") == "1"
HANDSHAKE_METRIC_TTL_SEC = float(os.getenv("GHOST_HANDSHAKE_METRIC_TTL_SEC", str(COOKIE_ROTATION_SECONDS * 2)))
HANDSHAKE_DURATION_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, math.inf)


class BoundedReplayCache(OrderedDict[bytes, float]):
    def __setitem__(self, key: bytes, value: float) -> None:
        super().__setitem__(key, value)
        while len(self) > COOKIE_REPLAY_CACHE_TRIM_TO:
            self.popitem(last=False)


class GhostVPNServer(asyncio.DatagramProtocol):
    def __init__(
        self,
        tun_ip: str = f"{VPN_SUBNET}.1",
        subnet: str = VPN_SUBNET,
        auth_key: Optional[bytes | str] = None,
        handshake: Optional[GhostHandshake] = None,
        handshake_rate_limit: int = HANDSHAKE_RATE_LIMIT,
        handshake_rate_window: float = HANDSHAKE_RATE_WINDOW,
    ):
        self.tun_ip = tun_ip
        self.subnet = subnet
        self.auth_key = load_auth_key(auth_key)
        self.tun = TUNInterface(TUN_NAME, mtu=TUN_MTU)
        if handshake is not None:
            self.handshake = handshake
        else:
            use_mock_handshake = os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes"}
            try:
                self.handshake = GhostHandshake(use_mock=use_mock_handshake)
            except TypeError:
                self.handshake = GhostHandshake()
        self.sessions = SessionManager(
            ip_pool=IPPool(subnet),
            session_timeout=SESSION_TIMEOUT,
        )
        self.transport: Optional[asyncio.DatagramTransport] = None
        self._tasks: list[asyncio.Task] = []
        self._metrics_server: Optional[asyncio.AbstractServer] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self.cookie_secret = os.urandom(32)
        self.handshake_rate_limit = handshake_rate_limit
        self.handshake_rate_window = handshake_rate_window
        self._handshake_attempts: dict[str, deque[float]] = defaultdict(deque)
        self._nat_rules_installed = False
        self._valid_cookie_hashes: BoundedReplayCache = BoundedReplayCache()
        self._nat_applied_rules: list[list[str]] = []
        self._handshake_response_cache: dict[bytes, tuple[float, Tuple[str, int], bytes]] = {}
        self._trusted_handshake_ips: dict[object, float] = {}
        self._session_host_routes: set[str] = set()
        self._handshake_started_at: dict[tuple[str, int, str, bytes], float] = {}
        self._profile_session_totals: dict[tuple[str, str], int] = defaultdict(int)
        self._profile_handshake_durations: dict[str, list[float]] = defaultdict(list)

        # Mesh RPC bridge for healing event coordination
        self.rpc_bridge = MeshRPCBridge(node_id=NODE_ID, neighbors=list(MESH_NEIGHBORS))
        self.rpc_bridge.on_event(self._on_mesh_healing_event)

        # MAPE-K self-healing loop for intelligent DPI response
        self._mapek_knowledge = MAPEKKnowledge()
        self._mapek_monitor = MAPEKMonitor(knowledge=self._mapek_knowledge)
        self._mapek_analyzer = MAPEKAnalyzer()
        self._mapek_planner = MAPEKPlanner(knowledge=self._mapek_knowledge)
        self._mapek_executor = MAPEKExecutor(rpc_bridge=self.rpc_bridge)
        self._mapek_executor.set_switch_profile_callback(self._mapek_switch_profile)

        self.metrics = {
            "active_clients": 0,
            "handshakes_total": 0,
            "handshakes_failed": 0,
            "handshakes_rate_limited": 0,
            "cookie_challenges_total": 0,
            "handshake_response_replays_total": 0,
            "handshake_cookie_bypass_total": 0,
            "handshake_cookie_replay_rejects_total": 0,
            "disconnects_total": 0,
            "healing_events_received": 0,
            "healing_events_broadcast": 0,
            "spoofed_packet_drops_total": 0,
            "keepalive_pings_sent_total": 0,
            "keepalive_pongs_received_total": 0,
            "bytes_in": 0,
            "bytes_out": 0,
            "packets_in": 0,
            "packets_out": 0,
            "sessions_reaped": 0,
            "started_at": time.time(),
        }

    def connection_made(self, transport: asyncio.DatagramTransport) -> None:
        self.transport = transport
        self._tasks.append(asyncio.create_task(self._keepalive_loop()))
        self._tasks.append(asyncio.create_task(self._reap_loop()))
        if METRICS_ENABLED and self._metrics_task is None:
            self._metrics_task = asyncio.create_task(self._start_metrics_server())
        logger.info("GhostVPN Server listening on UDP :%s", VPN_PORT)

    def connection_lost(self, exc: Optional[Exception]) -> None:
        for task in self._tasks:
            task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
        if self._metrics_server:
            self._metrics_server.close()
        self.sessions.sessions.clear()
        self._sync_session_host_routes()
        self._cleanup_nat()  # Clean up iptables rules on shutdown

    def datagram_received(self, data: bytes, addr: Tuple[str, int]) -> None:
        if not data or len(data) < AUTH_TAG_SIZE + 1:
            return

        msg_type, msg_body = unpack_protected_msg(self.auth_key, data)
        if msg_type is None:
            return

        self.metrics["bytes_in"] += len(data)
        self.metrics["packets_in"] += 1

        if msg_type == MsgType.HANDSHAKE_INIT:
            self._handle_handshake(msg_body, addr)
        elif msg_type == MsgType.DATA:
            self._handle_data(msg_body, addr)
        elif msg_type == MsgType.PING:
            self._handle_ping(msg_body, addr)
        elif msg_type == MsgType.PONG:
            self._handle_pong(msg_body, addr)
        elif msg_type == MsgType.STRATEGY_SYNC:
            self._handle_strategy_sync(msg_body, addr)
        elif msg_type == MsgType.PROFILE_SWITCH_ACK:
            self._handle_profile_switch_ack(msg_body, addr)
        elif msg_type == MsgType.DISCONNECT:
            self._handle_disconnect(addr)

    def _handle_handshake(self, payload: bytes, addr: Tuple[str, int]) -> None:
        if not self._allow_handshake(addr):
            self.metrics["handshakes_rate_limited"] += 1
            logger.warning("Handshake rate limit exceeded for %s", addr[0])
            return
        requested_profile: Optional[ObfuscationProfile] = None
        client_pub_key = b""
        try:
            requested_profile, cookie, client_pub_key = unpack_handshake_init(payload)
            self._mark_handshake_started(addr, requested_profile, client_pub_key)
            cookie_valid = False
            if cookie:
                cookie_valid = self._validate_cookie(cookie, addr, requested_profile, client_pub_key)
            elif self._should_bypass_cookie(addr):
                cookie_valid = True
                self.metrics["handshake_cookie_bypass_total"] += 1
            if not cookie_valid:
                self.metrics["cookie_challenges_total"] += 1
                self._send(
                    MsgType.HANDSHAKE_COOKIE,
                    pack_handshake_cookie(
                        self._mint_cookie(addr, requested_profile, client_pub_key)
                    ),
                    addr,
                )
                return

            ciphertext, shared_secret = self.handshake.server_respond(client_pub_key)
            transport_layer = GhostTransport(shared_secret, profile=requested_profile)
            session = self.sessions.create_session(addr, transport_layer)
            if session is None:
                self.metrics["handshakes_failed"] += 1
                self._record_handshake_outcome(addr, requested_profile, client_pub_key, status="failed")
                logger.warning("Resource exhaustion: IP pool full")
                return

            auth_tag = compute_handshake_auth_tag(
                self.auth_key,
                client_pub_key,
                cookie,
                ciphertext,
                session.assigned_ip,
                requested_profile,
            )
            resp_payload = pack_handshake_resp(
                ciphertext,
                session.assigned_ip,
                requested_profile,
                auth_tag,
            )
            if cookie:
                self._cache_handshake_response(cookie, addr, resp_payload)
            self._send(MsgType.HANDSHAKE_RESP, resp_payload, addr)

            self.metrics["handshakes_total"] += 1
            self._record_handshake_outcome(
                addr,
                requested_profile,
                client_pub_key,
                status="accepted",
                duration_s=self._consume_handshake_duration(addr, requested_profile, client_pub_key),
            )
            self.metrics["active_clients"] = self.sessions.active_count
            self._trusted_handshake_ips[addr] = time.monotonic()
            self._sync_session_host_routes()
            logger.info(
                "Session %s for %s -> %s (%s)",
                session.session_id,
                addr,
                session.assigned_ip,
                requested_profile.value,
            )
        except Exception as exc:
            self.metrics["handshakes_failed"] += 1
            self._record_handshake_outcome(addr, requested_profile, client_pub_key, status="failed")
            logger.error("Handshake failed for %s: %s", addr, exc)

    @staticmethod
    def _handshake_metric_key(
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> tuple[str, int, str, bytes]:
        return (addr[0], addr[1], profile.value, hashlib.sha256(client_pub_key).digest()[:8])

    def _mark_handshake_started(
        self,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> None:
        self._prune_handshake_metric_starts()
        key = self._handshake_metric_key(addr, profile, client_pub_key)
        self._handshake_started_at.setdefault(key, time.monotonic())

    def _consume_handshake_start(
        self,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> float:
        key = self._handshake_metric_key(addr, profile, client_pub_key)
        return self._handshake_started_at.pop(key, time.monotonic())

    def _consume_handshake_duration(
        self,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> float:
        started_at = self._consume_handshake_start(addr, profile, client_pub_key)
        return max(0.0, time.monotonic() - started_at)

    def _prune_handshake_metric_starts(self) -> None:
        cutoff = time.monotonic() - HANDSHAKE_METRIC_TTL_SEC
        stale = [key for key, started_at in self._handshake_started_at.items() if started_at < cutoff]
        for key in stale:
            self._handshake_started_at.pop(key, None)

    def _record_handshake_outcome(
        self,
        addr: Tuple[str, int],
        profile: Optional[ObfuscationProfile],
        client_pub_key: bytes,
        *,
        status: str,
        duration_s: float | None = None,
    ) -> None:
        profile_name = profile.value if profile is not None else "unknown"
        self._profile_session_totals[(profile_name, status)] += 1
        if profile is not None and duration_s is None:
            self._consume_handshake_start(addr, profile, client_pub_key)
        if duration_s is not None:
            self._profile_handshake_durations[profile_name].append(duration_s)

    def _cookie_hash(self, cookie: bytes) -> bytes:
        return hmac.new(self.cookie_secret, cookie, hashlib.sha256).digest()[:8]

    def _should_bypass_cookie(self, addr: Tuple[str, int]) -> bool:
        testing_mode = os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes"}
        is_prod = os.getenv("X0TTA6BL4_PRODUCTION", "false").lower() == "true"
        effective_bypass = ENABLE_TRUSTED_COOKIE_BYPASS and not is_prod

        if not (effective_bypass or testing_mode):
            return False
        for key in (addr, addr[0]):
            last_ok = self._trusted_handshake_ips.get(key)
            if last_ok is None:
                continue
            if time.monotonic() - last_ok > TRUSTED_HANDSHAKE_TTL_SEC:
                self._trusted_handshake_ips.pop(key, None)
                continue
            return True
        return False

    def _verify_cookie_signature(
        self,
        cookie: bytes,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> bool:
        if len(cookie) < 4 + hashlib.sha256().digest_size:
            return False
        epoch = int.from_bytes(cookie[:4], "big")
        now_epoch = int(time.time() // COOKIE_ROTATION_SECONDS)
        if epoch not in {now_epoch, now_epoch - 1}:
            return False
        expected = self._mint_cookie(addr, profile, client_pub_key, epoch=epoch)
        return hmac.compare_digest(cookie, expected)

    def _cache_handshake_response(
        self,
        cookie: bytes,
        addr: Tuple[str, int],
        response_payload: bytes,
    ) -> None:
        self._handshake_response_cache[self._cookie_hash(cookie)] = (
            time.monotonic(),
            addr,
            response_payload,
        )
        now = time.monotonic()
        self._handshake_response_cache = {
            key: value
            for key, value in self._handshake_response_cache.items()
            if now - value[0] <= HANDSHAKE_RESPONSE_CACHE_SEC
        }

    def _replay_cached_handshake_response(
        self,
        cookie: bytes,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> bool:
        if not self._verify_cookie_signature(cookie, addr, profile, client_pub_key):
            return False
        entry = self._handshake_response_cache.get(self._cookie_hash(cookie))
        if entry is None:
            return False
        created_at, cached_addr, response_payload = entry
        if cached_addr != addr:
            return False
        if time.monotonic() - created_at > HANDSHAKE_RESPONSE_CACHE_SEC:
            self._handshake_response_cache.pop(self._cookie_hash(cookie), None)
            return False
        self._send(MsgType.HANDSHAKE_RESP, response_payload, addr)
        self.metrics["handshake_response_replays_total"] += 1
        return True

    def _allow_handshake(
        self, client_addr: Tuple[str, int] | str, now: Optional[float] = None
    ) -> bool:
        if self.handshake_rate_limit <= 0:
            return True
        if now is None:
            now = time.monotonic()

        key = client_addr if isinstance(client_addr, str) else client_addr[0]
        attempts = self._handshake_attempts[key]
        cutoff = now - self.handshake_rate_window
        while attempts and attempts[0] <= cutoff:
            attempts.popleft()
        if len(attempts) >= self.handshake_rate_limit:
            return False
        attempts.append(now)
        return True

    def _mint_cookie(
        self,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
        epoch: Optional[int] = None,
    ) -> bytes:
        if epoch is None:
            epoch = int(time.time() // COOKIE_ROTATION_SECONDS)
        epoch_bytes = epoch.to_bytes(4, "big")
        mac = hmac.new(self.cookie_secret, digestmod=hashlib.sha256)
        mac.update(b"ghostvpn-cookie-v1")
        mac.update(self._cookie_context(addr, profile, client_pub_key))
        mac.update(epoch_bytes)
        return epoch_bytes + mac.digest()

    def _validate_cookie(
        self,
        cookie: bytes,
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> bool:
        """Validate stateless cookie with replay protection.

        Prevents replay attacks by tracking seen cookie hashes.
        Only accepts cookies from current and previous epoch (30 second grace).
        """
        if len(cookie) < 4 + hashlib.sha256().digest_size:
            return False

        epoch = int.from_bytes(cookie[:4], "big")
        now_epoch = int(time.time() // COOKIE_ROTATION_SECONDS)

        # Only accept current and previous epoch (30 second grace window)
        if epoch not in {now_epoch, now_epoch - 1}:
            logger.debug(f"Cookie epoch {epoch} outside valid range [{now_epoch-1}, {now_epoch}]")
            return False

        # Check HMAC first before tracking (fail fast on invalid cookies)
        if not self._verify_cookie_signature(cookie, addr, profile, client_pub_key):
            return False

        # Compute hash for replay tracking (prevent reusing same cookie).
        now = time.monotonic()
        self._prune_cookie_replay_cache(now)
        cookie_hash = self._cookie_hash(cookie)
        if cookie_hash in self._valid_cookie_hashes:
            logger.warning(f"Replay attack detected: duplicate cookie from {addr[0]}")
            self.metrics["handshake_cookie_replay_rejects_total"] += 1
            return False

        # Track this cookie and trim from oldest entries first.
        self._valid_cookie_hashes[cookie_hash] = now
        if len(self._valid_cookie_hashes) > COOKIE_REPLAY_CACHE_MAX:
            while len(self._valid_cookie_hashes) > COOKIE_REPLAY_CACHE_TRIM_TO:
                self._valid_cookie_hashes.popitem(last=False)
        return True

    def _prune_cookie_replay_cache(self, now_monotonic: float) -> None:
        cutoff = now_monotonic - (COOKIE_ROTATION_SECONDS * 2)
        while self._valid_cookie_hashes:
            _, seen_at = next(iter(self._valid_cookie_hashes.items()))
            if seen_at >= cutoff:
                break
            self._valid_cookie_hashes.popitem(last=False)

    @staticmethod
    def _cookie_context(
        addr: Tuple[str, int],
        profile: ObfuscationProfile,
        client_pub_key: bytes,
    ) -> bytes:
        host_bytes = addr[0].encode("utf-8")
        profile_id = PROFILE_TO_ID.get(profile, PROFILE_TO_ID[ObfuscationProfile.SRTP])
        return (
            struct.pack("!H", len(host_bytes))
            + host_bytes
            + struct.pack("!H", addr[1])
            + struct.pack("!B", profile_id)
            + struct.pack("!I", len(client_pub_key))
            + client_pub_key
        )

    def _handle_data(self, encrypted: bytes, addr: Tuple[str, int]) -> None:
        session = self.sessions.get_session(addr)
        if session is None:
            return
        session.touch()
        session.bytes_in += len(encrypted)
        payloads = session.transport_layer.unwrap_packet(encrypted)
        for raw_ip in payloads:
            # Skip non-IPv4 packets (e.g. IPv6 NDP) silently
            if len(raw_ip) < 20 or (raw_ip[0] >> 4) != 4:
                continue
            parsed = IPPacketParser.parse(raw_ip)
            if parsed is None or parsed["src_ip"] != session.assigned_ip:
                self.metrics["spoofed_packet_drops_total"] += 1
                logger.warning(
                    "Dropping spoofed tunnel packet from %s claiming %s",
                    addr,
                    parsed["src_ip"] if parsed else "invalid-ip-packet",
                )
                continue
            if self.tun.is_up:
                self.tun.write_packet_sync(raw_ip)

    def _handle_ping(self, payload: bytes, addr: Tuple[str, int]) -> None:
        session = self.sessions.get_session(addr)
        if session is None:
            return
        session.touch()
        self._send(MsgType.PONG, payload, addr, session.transport_layer)

    def _handle_pong(self, payload: bytes, addr: Tuple[str, int]) -> None:
        session = self.sessions.get_session(addr)
        if session is None:
            return
        session.touch()
        session.last_pong_at = time.time()
        self.metrics["keepalive_pongs_received_total"] += 1

    def _handle_disconnect(self, addr: Tuple[str, int]) -> None:
        session = self.sessions.get_session(addr)
        if session:
            logger.info("Client %s (%s) disconnected gracefully", addr, session.assigned_ip)
            self.sessions.remove_session(addr)
            self._sync_session_host_routes()
            self.metrics["active_clients"] = self.sessions.active_count
            self.metrics["disconnects_total"] += 1

    def _handle_strategy_sync(self, payload: bytes, addr: Tuple[str, int]) -> None:
        session = self.sessions.get_session(addr)
        if session is None:
            return
        try:
            strategy_id, strategy = unpack_strategy_sync(payload)
            if strategy.get("profile") != session.transport_layer.profile.value:
                logger.warning(
                    "Ignoring negotiated strategy %s from %s due to profile mismatch (%s != %s)",
                    strategy_id,
                    addr,
                    strategy.get("profile"),
                    session.transport_layer.profile.value,
                )
                return
            session.transport_layer.apply_negotiated_strategy(strategy, self.auth_key)
            session.negotiated_strategy_id = strategy_id
            session.negotiated_strategy = strategy
            self._send(MsgType.STRATEGY_ACK, pack_strategy_sync(strategy), addr, session.transport_layer)
            logger.info("Negotiated strategy %s applied for %s", strategy_id, addr)
        except Exception as exc:
            logger.warning("Failed to apply negotiated strategy for %s: %s", addr, exc)

    def _handle_profile_switch_ack(self, payload: bytes, addr: Tuple[str, int]) -> None:
        """Handle client confirmation of successful profile switch."""
        session = self.sessions.get_session(addr)
        if session is None:
            return
        try:
            new_profile, latency_ms = unpack_profile_switch_ack(payload)
            logger.info(
                "PROFILE_SWITCH_ACK from %s: switched to %s (latency %.1fms)",
                addr, new_profile, latency_ms,
            )
            # Record success in MAPE-K knowledge for learning
            self._mapek_knowledge.record(
                metrics={"profile": new_profile, "latency_ms": latency_ms},
                issue="DPI Detected",
                action="Switch protocol",
                success=True,
                mttr=latency_ms / 1000.0,
                node_id=f"{addr[0]}:{addr[1]}",
            )
            # Broadcast hint to mesh neighbors
            if self.rpc_bridge and ProfileHint is not None:
                hint = ProfileHint(
                    source_node=NODE_ID,
                    profile=new_profile,
                    latency_ms=latency_ms,
                    success=True,
                )
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self.rpc_bridge.broadcast_profile_hint(hint))
                except RuntimeError:
                    pass
        except Exception as exc:
            logger.warning("Failed to handle profile switch ACK from %s: %s", addr, exc)

    @staticmethod
    def _iter_transport_packets(packet: bytes | list[bytes]) -> list[bytes]:
        if isinstance(packet, list):
            return packet
        return [packet]

    async def run_tun_listener(self) -> None:
        logger.info("Starting TUN listener...")
        if not await self.tun.create():
            logger.error("Failed to create TUN interface")
            return
        await self.tun.set_address(f"{self.tun_ip}/24")
        self._setup_nat()

        if os.getenv("GHOST_DNS_ENABLED", "1") == "1":
            try:
                from src.network.ghost_dns_forwarder import DNSForwarderProtocol

                loop = asyncio.get_running_loop()
                await loop.create_datagram_endpoint(
                    DNSForwarderProtocol,
                    local_addr=(self.tun_ip, 53),
                )
                logger.info("Ghost DNS forwarder active on %s:53", self.tun_ip)
            except Exception as exc:
                logger.warning("DNS forwarder failed: %s (VPN still works)", exc)

        logger.info("GhostVPN Server active on %s", self.tun_ip)

        while True:
            try:
                packet = await self.tun.read_packet()
                if not packet:
                    await asyncio.sleep(0.01)
                    continue
                # Skip non-IPv4 packets from TUN
                if len(packet) < 20 or (packet[0] >> 4) != 4:
                    continue
                parsed = IPPacketParser.parse(packet)
                if parsed:
                    self._route_to_client(packet, parsed["dst_ip"])
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("TUN loop error: %s", exc)
                await asyncio.sleep(1)

    def _route_to_client(self, raw_ip: bytes, dst_ip: str) -> None:
        session = self.sessions.get_session_by_ip(dst_ip)
        if session is None:
            return
        encrypted_packets = self._iter_transport_packets(
            session.transport_layer.wrap_packet(raw_ip, is_reliable=False)
        )
        for encrypted in encrypted_packets:
            self._send(MsgType.DATA, encrypted, session.client_addr, session.transport_layer)
            session.bytes_out += len(encrypted)
            session.packets_out += 1
            self.metrics["packets_out"] += 1

    async def _keepalive_loop(self) -> None:
        while True:
            await asyncio.sleep(KEEPALIVE_INTERVAL)
            for addr, session in list(self.sessions.sessions.items()):
                session.ping_seq += 1
                self._send(MsgType.PING, pack_ping(session.ping_seq), addr, session.transport_layer)
                self.metrics["keepalive_pings_sent_total"] += 1

    async def _reap_loop(self) -> None:
        while True:
            await asyncio.sleep(REAP_INTERVAL)
            removed = self.sessions.cleanup_expired()
            if removed:
                self._sync_session_host_routes()
                self.metrics["sessions_reaped"] += len(removed)
                self.metrics["active_clients"] = self.sessions.active_count
                for addr in removed:
                    logger.info("Reaped dead session: %s", addr)

    def _sync_session_host_routes(self) -> None:
        desired = {session.assigned_ip for session in self.sessions.sessions.values()}

        for ip_addr in sorted(desired - self._session_host_routes):
            try:
                subprocess.run(
                    ["ip", "route", "replace", f"{ip_addr}/32", "dev", TUN_NAME],
                    check=True,
                    capture_output=True,
                    text=True,
                )
                logger.info("Installed Ghost session route %s/32 via %s", ip_addr, TUN_NAME)
            except subprocess.CalledProcessError as exc:
                logger.warning("Failed to install Ghost session route %s/32: %s", ip_addr, exc.stderr.strip())

        for ip_addr in sorted(self._session_host_routes - desired):
            subprocess.run(
                ["ip", "route", "del", f"{ip_addr}/32", "dev", TUN_NAME],
                check=False,
                capture_output=True,
                text=True,
            )
            logger.info("Removed Ghost session route %s/32 via %s", ip_addr, TUN_NAME)

        self._session_host_routes = desired

    def _apply_transport_socket_options(self, transport_layer: Optional[GhostTransport]) -> None:
        if self.transport is None or transport_layer is None:
            return
        sock = None
        get_extra_info = getattr(self.transport, "get_extra_info", None)
        if callable(get_extra_info):
            sock = get_extra_info("socket")
        if sock is None:
            return
        ttl = transport_layer.get_send_socket_ttl()
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl or 64)
        except OSError as exc:
            logger.debug("Failed to apply server socket TTL: %s", exc)

    def _send(
        self,
        msg_type: MsgType,
        payload: bytes,
        addr: Tuple[str, int],
        transport_layer: Optional[GhostTransport] = None,
    ) -> None:
        if self.transport is None:
            return
        self._apply_transport_socket_options(transport_layer)
        frame = pack_protected_msg(self.auth_key, msg_type, payload)
        self.transport.sendto(frame, addr)
        self.metrics["bytes_out"] += len(frame)

    async def _start_metrics_server(self) -> None:
        try:
            self._metrics_server = await asyncio.start_server(
                self._handle_metrics_http,
                host=METRICS_HOST,
                port=METRICS_PORT,
            )
            logger.info(
                "GhostVPN metrics server listening on http://%s:%s",
                METRICS_HOST,
                METRICS_PORT,
            )
            await self._metrics_server.serve_forever()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("GhostVPN metrics server failed: %s", exc)

    async def _handle_metrics_http(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            # Set timeout to prevent slowloris attacks
            raw_request = await asyncio.wait_for(
                reader.read(4096),
                timeout=5.0  # 5 second timeout for HTTP request
            )
            request_line = raw_request.split(b"\r\n", 1)[0].decode("ascii", errors="replace")
            parts = request_line.split()
            path = parts[1] if len(parts) >= 2 else "/"

            if path == "/metrics":
                body = self.render_prometheus_metrics().encode("utf-8")
                content_type = "text/plain; version=0.0.4; charset=utf-8"
                status = "200 OK"
            elif path == "/healthz":
                body = json.dumps(self.get_health_status(), sort_keys=True).encode("utf-8")
                content_type = "application/json"
                status = "200 OK"
            elif path == "/rpc" and request_line.startswith("POST"):
                # Extract JSON body after headers
                rpc_body = self._extract_http_body(raw_request)
                rpc_response = await self._handle_rpc(rpc_body)
                body = json.dumps(rpc_response).encode("utf-8")
                content_type = "application/json"
                status = "200 OK"
            elif path == "/healing/events":
                events = self.rpc_bridge.event_history[-50:]
                body = json.dumps([e.model_dump() for e in events]).encode("utf-8")
                content_type = "application/json"
                status = "200 OK"
            else:
                body = b"not found\n"
                content_type = "text/plain; charset=utf-8"
                status = "404 Not Found"

            headers = [
                f"HTTP/1.1 {status}",
                f"Content-Type: {content_type}",
                f"Content-Length: {len(body)}",
                "Connection: close",
                "",
                "",
            ]
            writer.write("\r\n".join(headers).encode("ascii") + body)
            await asyncio.wait_for(writer.drain(), timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("Metrics HTTP timeout from %s", writer.get_extra_info("peername"))
        except Exception as exc:
            logger.debug("Metrics HTTP error: %s", exc)
        finally:
            writer.close()
            await writer.wait_closed()

    @staticmethod
    def _extract_http_body(raw: bytes) -> bytes:
        """Extract body from raw HTTP request."""
        separator = raw.find(b"\r\n\r\n")
        if separator == -1:
            return b"{}"
        return raw[separator + 4:]

    async def _handle_rpc(self, body: bytes) -> dict:
        """Dispatch JSON-RPC request to the mesh bridge."""
        try:
            payload = json.loads(body)
        except (json.JSONDecodeError, ValueError):
            return {"jsonrpc": "2.0", "error": {"code": -32700, "message": "parse_error"}, "id": None}
        return await self.rpc_bridge.handle_rpc_request(payload)

    def _mapek_switch_profile(self, blocked_profile: str | None, recommended_profile: str | None) -> bool:
        """MAPE-K callback: execute VPN profile switch for DPI self-healing."""
        if not recommended_profile:
            available = [p.value for p in ObfuscationProfile if p.value != blocked_profile]
            recommended_profile = available[0] if available else None
        if not recommended_profile:
            logger.warning("MAPE-K: no available profile to switch to")
            return False
        self._push_profile_switch_to_clients(recommended_profile, blocked_profile=blocked_profile)
        return True

    async def _on_mesh_healing_event(self, event: HealingEvent) -> None:
        """Callback when a healing event is received from a mesh neighbor.

        For dpi_detected incidents, routes through MAPE-K cycle for intelligent
        decision-making, then pushes PROFILE_SWITCH to connected clients.
        """
        self.metrics["healing_events_received"] += 1
        logger.info(
            "Mesh healing event: %s did %s on %s (%s)",
            event.source_node,
            event.action_taken,
            event.target_node,
            event.status,
        )

        if event.incident_type == "dpi_detected":
            blocked_profile = event.metadata.get("blocked_profile")
            recommended = event.metadata.get("profile")
            start_time = time.time()

            # Route through MAPE-K for intelligent analysis
            dpi_metrics = {
                "dpi_detected": True,
                "blocked_profile": blocked_profile or "unknown",
                "source_node": event.source_node,
                "packet_loss_percent": 100.0,  # DPI = total loss on blocked profile
            }
            monitor_result = self._mapek_monitor.check(dpi_metrics)
            # Force DPI issue type if monitor didn't catch it via thresholds
            issue = "DPI Detected" if monitor_result.get("issue") == "High Packet Loss" or not monitor_result.get("anomaly_detected") else monitor_result["issue"]
            if issue != "DPI Detected":
                issue = "DPI Detected"

            action = self._mapek_planner.plan(issue)
            logger.info("MAPE-K DPI cycle: issue=%s action=%s", issue, action)

            context = {
                "blocked_profile": blocked_profile,
                "recommended_profile": recommended,
                "source_node": event.source_node,
                "issue": issue,
            }
            success = self._mapek_executor.execute(action, context)
            mttr = time.time() - start_time

            # Record in knowledge base for learning
            self._mapek_knowledge.record(
                metrics=dpi_metrics,
                issue=issue,
                action=action,
                success=success,
                mttr=mttr,
                node_id=event.source_node,
            )

        if event.target_node == NODE_ID:
            if event.action_taken == "reconnect":
                logger.info("Neighbor requested reconnect — refreshing sessions")
            elif event.action_taken == "switch_profile":
                recommended = event.metadata.get("profile")
                if recommended:
                    logger.info("Neighbor recommends profile: %s", recommended)

    def _push_profile_switch_to_clients(
        self, recommended_profile: str, blocked_profile: Optional[str] = None
    ) -> None:
        """Send PROFILE_SWITCH to all clients currently using the blocked profile."""
        payload = pack_profile_switch(recommended_profile, reason="dpi_detected")
        pushed = 0
        for addr, session in list(self.sessions.sessions.items()):
            if blocked_profile and session.transport_layer.profile.value != blocked_profile:
                continue
            self._send(MsgType.PROFILE_SWITCH, payload, addr, session.transport_layer)
            pushed += 1
        if pushed:
            logger.info(
                "Pushed PROFILE_SWITCH(%s) to %d clients (blocked=%s)",
                recommended_profile, pushed, blocked_profile,
            )

    def _setup_nat(self) -> None:
        """Set up iptables NAT rules with proper error handling.

        Configures MASQUERADE and FORWARD rules for the VPN subnet.
        Logs all errors and marks installation state for cleanup on shutdown.
        """
        net = f"{self.subnet}.0/24"

        try:
            # Enable IP forwarding
            result = subprocess.run(
                ["sysctl", "-w", "net.ipv4.ip_forward=1"],
                capture_output=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(f"Failed to enable IP forwarding: {result.stderr.decode('utf-8', errors='replace')}")
                return

            # Apply NAT rules with error handling
            rules = [
                (
                    ["iptables", "-t", "nat", "-C", "POSTROUTING", "-s", net, "!", "-d", net, "-j", "MASQUERADE"],
                    ["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", net, "!", "-d", net, "-j", "MASQUERADE"],
                    "MASQUERADE rule"
                ),
                (
                    ["iptables", "-C", "FORWARD", "-i", TUN_NAME, "-j", "ACCEPT"],
                    ["iptables", "-I", "FORWARD", "1", "-i", TUN_NAME, "-j", "ACCEPT"],
                    "FORWARD INPUT rule"
                ),
                (
                    ["iptables", "-C", "FORWARD", "-o", TUN_NAME, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                    ["iptables", "-I", "FORWARD", "2", "-o", TUN_NAME, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                    "FORWARD OUTPUT rule"
                ),
            ]

            for check_cmd, add_cmd, desc in rules:
                try:
                    if subprocess.run(check_cmd, capture_output=True, timeout=10).returncode != 0:
                        result = subprocess.run(add_cmd, capture_output=True, timeout=10)
                        if result.returncode != 0:
                            logger.error(f"Failed to add {desc}: {result.stderr.decode('utf-8', errors='replace')}")
                        else:
                            self._nat_applied_rules.append(add_cmd)
                            logger.debug(f"Added {desc}")
                except subprocess.TimeoutExpired:
                    logger.error(f"Timeout adding {desc}")

            self._nat_rules_installed = True
            logger.info("NAT rules installed for %s", net)

        except Exception as exc:
            logger.error(f"Fatal error in _setup_nat(): {exc}")

    def _cleanup_nat(self) -> None:
        """Remove iptables NAT rules on shutdown.

        Best-effort cleanup; logs all errors but does not fail.
        """
        if not self._nat_rules_installed:
            return

        try:
            if not self._nat_applied_rules:
                net = f"{self.subnet}.0/24"
                self._nat_applied_rules = [
                    ["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", net, "!", "-d", net, "-j", "MASQUERADE"],
                    ["iptables", "-I", "FORWARD", "1", "-i", TUN_NAME, "-j", "ACCEPT"],
                    ["iptables", "-I", "FORWARD", "2", "-o", TUN_NAME, "-m", "state", "--state", "RELATED,ESTABLISHED", "-j", "ACCEPT"],
                ]

            for add_cmd in reversed(self._nat_applied_rules):
                cmd = add_cmd.copy()
                if "-A" in cmd:
                    cmd[cmd.index("-A")] = "-D"
                elif "-I" in cmd:
                    insert_idx = cmd.index("-I")
                    del cmd[insert_idx:insert_idx + 2]
                    cmd.insert(insert_idx, "-D")
                try:
                    subprocess.run(cmd, capture_output=True, timeout=10)
                except Exception as exc:
                    logger.warning(f"Error removing iptables rule {' '.join(cmd)}: {exc}")
            self._nat_applied_rules = []
            logger.info("NAT rules cleaned up for %s.0/24", self.subnet)
        except Exception as exc:
            logger.warning(f"Error in _cleanup_nat(): {exc}")

    def get_metrics(self) -> dict:
        return {
            **self.metrics,
            "uptime_sec": time.time() - self.metrics["started_at"],
            "ip_pool_available": self.sessions.ip_pool.available,
        }

    def get_health_status(self) -> dict:
        metrics = self.get_metrics()
        return {
            "healthy": self.transport is not None and self.tun.is_up,
            "transport_bound": self.transport is not None,
            "tun_up": self.tun.is_up,
            "active_clients": metrics["active_clients"],
            "ip_pool_available": metrics["ip_pool_available"],
            "handshakes_failed": metrics["handshakes_failed"],
            "handshakes_rate_limited": metrics["handshakes_rate_limited"],
        }

    def render_prometheus_metrics(self) -> str:
        metrics = self.get_metrics()
        metric_meta = {
            "ghostvpn_active_clients": ("gauge", "Active GhostVPN clients"),
            "ghostvpn_handshakes_total": ("counter", "Completed GhostVPN handshakes"),
            "ghostvpn_handshakes_failed_total": ("counter", "Failed GhostVPN handshakes"),
            "ghostvpn_handshakes_rate_limited_total": ("counter", "Rate-limited GhostVPN handshakes"),
            "ghostvpn_cookie_challenges_total": ("counter", "GhostVPN cookie challenge responses"),
            "ghostvpn_handshake_response_replays_total": ("counter", "Cached GhostVPN handshake responses replayed for duplicate UDP requests"),
            "ghostvpn_handshake_cookie_bypass_total": ("counter", "GhostVPN handshakes that bypassed cookie challenge for recently trusted IPs"),
            "ghostvpn_handshake_cookie_replay_rejects_total": ("counter", "GhostVPN cookie replay attempts rejected"),
            "ghostvpn_disconnects_total": ("counter", "GhostVPN client disconnects"),
            "ghostvpn_spoofed_packet_drops_total": ("counter", "GhostVPN spoofed inner packet drops"),
            "ghostvpn_keepalive_pings_sent_total": ("counter", "GhostVPN keepalive pings sent"),
            "ghostvpn_keepalive_pongs_received_total": ("counter", "GhostVPN keepalive pongs received"),
            "ghostvpn_packets_in_total": ("counter", "GhostVPN packets received"),
            "ghostvpn_packets_out_total": ("counter", "GhostVPN packets sent"),
            "ghostvpn_bytes_in_total": ("counter", "GhostVPN bytes received"),
            "ghostvpn_bytes_out_total": ("counter", "GhostVPN bytes sent"),
            "ghostvpn_sessions_reaped_total": ("counter", "GhostVPN sessions reaped"),
            "ghostvpn_ip_pool_available": ("gauge", "Available GhostVPN IPs in pool"),
            "ghostvpn_uptime_seconds": ("gauge", "GhostVPN server uptime in seconds"),
        }
        metric_values = {
            "ghostvpn_active_clients": metrics["active_clients"],
            "ghostvpn_handshakes_total": metrics["handshakes_total"],
            "ghostvpn_handshakes_failed_total": metrics["handshakes_failed"],
            "ghostvpn_handshakes_rate_limited_total": metrics["handshakes_rate_limited"],
            "ghostvpn_cookie_challenges_total": metrics["cookie_challenges_total"],
            "ghostvpn_handshake_response_replays_total": metrics["handshake_response_replays_total"],
            "ghostvpn_handshake_cookie_bypass_total": metrics["handshake_cookie_bypass_total"],
            "ghostvpn_handshake_cookie_replay_rejects_total": metrics["handshake_cookie_replay_rejects_total"],
            "ghostvpn_disconnects_total": metrics["disconnects_total"],
            "ghostvpn_spoofed_packet_drops_total": metrics["spoofed_packet_drops_total"],
            "ghostvpn_keepalive_pings_sent_total": metrics["keepalive_pings_sent_total"],
            "ghostvpn_keepalive_pongs_received_total": metrics["keepalive_pongs_received_total"],
            "ghostvpn_packets_in_total": metrics["packets_in"],
            "ghostvpn_packets_out_total": metrics["packets_out"],
            "ghostvpn_bytes_in_total": metrics["bytes_in"],
            "ghostvpn_bytes_out_total": metrics["bytes_out"],
            "ghostvpn_sessions_reaped_total": metrics["sessions_reaped"],
            "ghostvpn_ip_pool_available": metrics["ip_pool_available"],
            "ghostvpn_uptime_seconds": metrics["uptime_sec"],
        }

        lines = []
        for name, (metric_type, description) in metric_meta.items():
            lines.append(f"# HELP {name} {description}")
            lines.append(f"# TYPE {name} {metric_type}")
            lines.append(f"{name} {metric_values[name]}")
        lines.extend(self._render_profile_session_metrics())
        lines.extend(self._render_profile_handshake_histogram())
        return "\n".join(lines) + "\n"

    def _render_profile_session_metrics(self) -> list[str]:
        lines = [
            "# HELP ghost_vpn_session_total GhostVPN session outcomes by negotiated profile",
            "# TYPE ghost_vpn_session_total counter",
        ]
        for (profile, status), count in sorted(self._profile_session_totals.items()):
            lines.append(
                f'ghost_vpn_session_total{{profile="{profile}",status="{status}"}} {count}'
            )
        return lines

    def _render_profile_handshake_histogram(self) -> list[str]:
        lines = [
            "# HELP ghost_vpn_handshake_duration_seconds GhostVPN handshake duration by negotiated profile",
            "# TYPE ghost_vpn_handshake_duration_seconds histogram",
        ]
        for profile, samples in sorted(self._profile_handshake_durations.items()):
            for bucket in HANDSHAKE_DURATION_BUCKETS:
                count = sum(1 for sample in samples if sample <= bucket)
                le = "+Inf" if math.isinf(bucket) else f"{bucket:g}"
                lines.append(
                    f'ghost_vpn_handshake_duration_seconds_bucket{{profile="{profile}",le="{le}"}} {count}'
                )
            lines.append(
                f'ghost_vpn_handshake_duration_seconds_sum{{profile="{profile}"}} {sum(samples):.6f}'
            )
            lines.append(
                f'ghost_vpn_handshake_duration_seconds_count{{profile="{profile}"}} {len(samples)}'
            )
        return lines


async def start_server() -> None:
    loop = asyncio.get_running_loop()
    probe_echo = None
    if os.getenv("GHOST_EVOLUTION_ENABLED", "0") == "1":
        try:
            from src.anti_censorship.probe_echo_server import ProbeEchoServer

            probe_echo = ProbeEchoServer()
            await probe_echo.start()
            logger.info("Probe echo server started on %s", os.getenv("GHOST_PROBE_PORT", "4434"))
        except Exception as exc:
            logger.warning("Failed to start probe echo server: %s", exc)
    server = GhostVPNServer()
    await loop.create_datagram_endpoint(
        lambda: server,
        local_addr=("0.0.0.0", VPN_PORT),
    )
    logger.info("Bound to 0.0.0.0:%s", VPN_PORT)
    try:
        await server.run_tun_listener()
    finally:
        if probe_echo is not None:
            probe_echo.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(message)s")
    if os.geteuid() != 0:
        print("Must be run as root for TUN/iptables.")
        sys.exit(1)
    asyncio.run(start_server())
