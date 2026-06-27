#!/usr/bin/env python3
"""
x0tta6bl4 GhostVPN Client
=========================
L3 VPN client with authenticated handshake, adaptive roaming, and local
observability endpoints.
"""

import asyncio
import hmac
import ipaddress
import json
import logging
import os
import secrets
import socket
import subprocess
import sys
import time
from contextlib import suppress
from typing import List, Optional, Tuple

from src.network.ghost_vpn_protocol import (
    AUTH_TAG_SIZE,
    MsgType,
    compute_handshake_auth_tag,
    load_auth_key,
    pack_handshake_init,
    pack_ping,
    pack_profile_switch_ack,
    pack_protected_msg,
    pack_strategy_sync,
    unpack_handshake_cookie,
    unpack_handshake_resp,
    unpack_ping,
    unpack_profile_switch,
    unpack_protected_msg,
    unpack_strategy_sync,
)
from src.network.transport.ghost_handshake import GhostHandshake
from src.network.transport.ghost_proto import GhostTransport, ObfuscationProfile
from src.network.tun_handler import TUNInterface

try:
    from src.self_healing.rpc_bridge import MeshRPCBridge, ProfileHint
except Exception:
    MeshRPCBridge = None  # type: ignore
    ProfileHint = None  # type: ignore

try:
    from src.anti_censorship.ghost_vpn_adapter import GhostVPNEvolutionAdapter
except Exception:
    GhostVPNEvolutionAdapter = None  # type: ignore

logger = logging.getLogger("GhostVPN-Client")

TUN_MTU = 1400
KEEPALIVE_MIN = int(os.getenv("GHOST_KEEPALIVE_MIN_SEC", "20"))
KEEPALIVE_MAX = int(os.getenv("GHOST_KEEPALIVE_MAX_SEC", "50"))
PING_TIMEOUT = float(os.getenv("GHOST_PING_TIMEOUT_SEC", "1.0"))
HANDSHAKE_RETRY_INTERVAL = float(os.getenv("GHOST_HANDSHAKE_RETRY_SEC", "0.75"))
HANDSHAKE_MAX_RETRIES = int(os.getenv("GHOST_HANDSHAKE_MAX_RETRIES", "3"))
CLIENT_METRICS_ENABLED = os.getenv("GHOST_CLIENT_METRICS_ENABLED", "1") == "1"
CLIENT_METRICS_HOST = os.getenv("GHOST_CLIENT_METRICS_HOST", "127.0.0.1")
CLIENT_METRICS_PORT = int(os.getenv("GHOST_CLIENT_METRICS_PORT", "9465"))


EVOLUTION_ENABLED = os.getenv("GHOST_EVOLUTION_ENABLED", "0") == "1"
EVOLUTION_INTERVAL = float(os.getenv("GHOST_EVOLUTION_INTERVAL_SEC", "60"))
PROBE_PORT = int(os.getenv("GHOST_PROBE_PORT", "4434"))
PRETRAIN_GENERATIONS = int(os.getenv("GHOST_PRETRAIN_GENERATIONS", "20"))
PRETRAIN_DPI_SYSTEMS = os.getenv("GHOST_PRETRAIN_DPI", "")  # comma-separated, empty = all

# DPI detection: rapid probe to detect blocks faster than keepalive cycle
DPI_PROBE_INTERVAL = float(os.getenv("GHOST_DPI_PROBE_INTERVAL_SEC", "5"))
DPI_PROBE_COUNT = int(os.getenv("GHOST_DPI_PROBE_COUNT", "3"))
DPI_PROBE_TIMEOUT = float(os.getenv("GHOST_DPI_PROBE_TIMEOUT_SEC", "2.0"))
DPI_CONSECUTIVE_FAILURES = int(os.getenv("GHOST_DPI_CONSECUTIVE_FAILURES", "2"))
# Auto-reconnect settings
RECONNECT_ENABLED = os.getenv("GHOST_RECONNECT_ENABLED", "1") == "1"
RECONNECT_BASE_DELAY = float(os.getenv("GHOST_RECONNECT_BASE_DELAY_SEC", "1.0"))
RECONNECT_MAX_DELAY = float(os.getenv("GHOST_RECONNECT_MAX_DELAY_SEC", "60.0"))
RECONNECT_MAX_ATTEMPTS = int(os.getenv("GHOST_RECONNECT_MAX_ATTEMPTS", "0"))  # 0 = unlimited


class GhostVPNClient(asyncio.DatagramProtocol):
    def __init__(
        self,
        server_addr: Tuple[str, int],
        auth_key: Optional[bytes | str] = None,
        handshake: Optional[GhostHandshake] = None,
        rpc_bridge: Optional["MeshRPCBridge"] = None,
        enable_evolution: Optional[bool] = None,
        evolution_interval_sec: Optional[float] = None,
        initial_profile_idx: int = 0,
    ):
        self.server_addr = server_addr
        self.auth_key = load_auth_key(auth_key)
        self.handshake = handshake or GhostHandshake()
        self.transport_layer: Optional[GhostTransport] = None
        self.transport: Optional[asyncio.DatagramTransport] = None
        self.tun = TUNInterface("tun_ghost_c", mtu=TUN_MTU)
        self.rpc_bridge = rpc_bridge

        self.profiles = [
            ObfuscationProfile.SRTP,
            ObfuscationProfile.DNS,
            ObfuscationProfile.STEAM,
        ]
        self.current_profile_idx = initial_profile_idx % len(self.profiles)
        self.assigned_ip: Optional[str] = None
        self.session_ready = asyncio.Event()
        self._temp_priv: Optional[bytes] = None
        self._pending_client_pub: Optional[bytes] = None
        self._handshake_cookie: bytes = b""
        self._handshake_in_progress = False
        self._shutdown = False
        self._last_pong = 0.0

        self._latency_task: Optional[asyncio.Task] = None
        self._metrics_server: Optional[asyncio.AbstractServer] = None
        self._metrics_task: Optional[asyncio.Task] = None
        self._handshake_retry_task: Optional[asyncio.Task] = None
        self._managed_routes: list[list[str]] = []
        self._managed_rules: list[list[str]] = []
        self._ping_seq = 0
        self._pending_ping_seq: Optional[int] = None
        self._pending_ping_future: Optional[asyncio.Future] = None
        self._pending_strategy_id: Optional[str] = None
        self._pending_strategy_payload: Optional[dict] = None

        self.metrics = {
            "handshakes_total": 0,
            "handshakes_failed": 0,
            "handshake_cookies_received_total": 0,
            "handshake_auth_failures_total": 0,
            "handshake_retries_total": 0,
            "roam_events_total": 0,
            "disconnects_total": 0,
            "keepalive_pings_sent_total": 0,
            "keepalive_pongs_received_total": 0,
            "keepalive_timeouts_total": 0,
            "dpi_probes_sent": 0,
            "dpi_probes_failed": 0,
            "dpi_blocks_detected": 0,
            "reconnect_attempts": 0,
            "reconnect_successes": 0,
            "packets_in": 0,
            "packets_out": 0,
            "bytes_in": 0,
            "bytes_out": 0,
            "started_at": time.time(),
        }
        self._dpi_probe_task: Optional[asyncio.Task] = None
        self._dpi_consecutive_failures = 0
        self._connection_lost_event = asyncio.Event()

        # Evolutionary DPI evasion
        self._evolution_adapter: Optional["GhostVPNEvolutionAdapter"] = None
        self._evolution_enabled = enable_evolution if enable_evolution is not None else EVOLUTION_ENABLED
        self._evolution_interval_sec = (
            evolution_interval_sec if evolution_interval_sec is not None else EVOLUTION_INTERVAL
        )
        if self._evolution_enabled and GhostVPNEvolutionAdapter is not None:
            probe_target = (server_addr[0], PROBE_PORT)
            self._evolution_adapter = GhostVPNEvolutionAdapter(
                node_id=f"ghost-client-{os.getpid()}",
                probe_target=probe_target,
                master_key=self.auth_key[:32] if len(self.auth_key) >= 32 else self.auth_key.ljust(32, b"\x00"),
                rpc_bridge=rpc_bridge,
                evolution_interval_sec=self._evolution_interval_sec,
            )
            self._evolution_adapter.on_strategy_sync_request(self._queue_strategy_sync)
            logger.info("Evolutionary DPI evasion enabled (probe→%s:%d)", *probe_target)

            # Предтренировка: разогрев популяции на DPI-симуляторах до первого хендшейка
            if PRETRAIN_GENERATIONS > 0:
                dpi_systems = [s.strip() for s in PRETRAIN_DPI_SYSTEMS.split(",") if s.strip()] or None
                try:
                    pt = self._evolution_adapter.pretrain(
                        dpi_systems=dpi_systems,
                        generations=PRETRAIN_GENERATIONS,
                    )
                    logger.info(
                        "Pretrained evolution: fitness=%.3f mimic=%s (%d gens)",
                        pt["best_fitness"], pt["best_mimic"], pt["generations_trained"],
                    )
                except Exception as e:
                    logger.warning("Pretrain failed (non-critical): %s", e)

    def _ensure_runtime_state(self) -> None:
        if not hasattr(self, "rpc_bridge"):
            self.rpc_bridge = None
        if not hasattr(self, "_managed_routes"):
            self._managed_routes = []
        if not hasattr(self, "_managed_rules"):
            self._managed_rules = []
        if not hasattr(self, "_handshake_retry_task"):
            self._handshake_retry_task = None
        if not hasattr(self, "_metrics_server"):
            self._metrics_server = None
        if not hasattr(self, "_metrics_task"):
            self._metrics_task = None
        if not hasattr(self, "_latency_task"):
            self._latency_task = None
        if not hasattr(self, "_pending_ping_seq"):
            self._pending_ping_seq = None
        if not hasattr(self, "_pending_ping_future"):
            self._pending_ping_future = None
        if not hasattr(self, "_last_pong"):
            self._last_pong = 0.0

    def connection_made(self, transport):
        self._ensure_runtime_state()
        self.transport = transport
        if CLIENT_METRICS_ENABLED and self._metrics_task is None:
            try:
                loop = asyncio.get_running_loop()
                self._metrics_task = loop.create_task(self._start_metrics_server())
            except RuntimeError:
                self._metrics_task = None
        self._initiate_adaptive_handshake()

    def connection_lost(self, exc: Optional[Exception]) -> None:
        self._ensure_runtime_state()
        if self._handshake_retry_task:
            self._handshake_retry_task.cancel()
        if self._metrics_task:
            self._metrics_task.cancel()
        if self._metrics_server:
            self._metrics_server.close()
        if self._evolution_adapter is not None:
            self._evolution_adapter.stop()
        # Signal reconnect loop
        self._connection_lost_event.set()

    def _initiate_adaptive_handshake(self, reuse_keypair: bool = False):
        self._ensure_runtime_state()
        profile = self.profiles[self.current_profile_idx]
        logger.info("Attempting GhostVPN handshake with profile %s", profile.value)
        self._handshake_in_progress = True
        if not reuse_keypair or self._pending_client_pub is None or self._temp_priv is None:
            pub, priv = self.handshake.client_init()
            self._pending_client_pub = pub
            self._temp_priv = priv
            self._handshake_cookie = b""

        self._send_current_handshake_init()
        self._restart_handshake_retry_loop()

    def _send_current_handshake_init(self) -> None:
        if self._pending_client_pub is None:
            return
        profile = self.profiles[self.current_profile_idx]
        self._send(
            MsgType.HANDSHAKE_INIT,
            pack_handshake_init(
                self._pending_client_pub,
                profile,
                self._handshake_cookie,
            ),
        )

    def _restart_handshake_retry_loop(self) -> None:
        self._ensure_runtime_state()
        if self._handshake_retry_task:
            self._handshake_retry_task.cancel()
        if self.transport is None or not self._handshake_in_progress or self.session_ready.is_set():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._handshake_retry_task = loop.create_task(self._handshake_retry_loop())

    async def _handshake_retry_loop(self) -> None:
        retries = 0
        try:
            while (
                retries < HANDSHAKE_MAX_RETRIES
                and self.transport is not None
                and self._handshake_in_progress
                and not self.session_ready.is_set()
                and not self._shutdown
            ):
                await asyncio.sleep(HANDSHAKE_RETRY_INTERVAL)
                if (
                    self.transport is None
                    or not self._handshake_in_progress
                    or self.session_ready.is_set()
                    or self._shutdown
                ):
                    return
                retries += 1
                self.metrics["handshake_retries_total"] += 1
                self._send_current_handshake_init()
        except asyncio.CancelledError:
            raise

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        if addr != self.server_addr or not data or len(data) < AUTH_TAG_SIZE + 1:
            return

        msg_type, payload = unpack_protected_msg(self.auth_key, data)
        if msg_type is None:
            if self.transport_layer:
                self._handle_data(data)
            return

        self.metrics["bytes_in"] += len(data)
        self.metrics["packets_in"] += 1

        if self._handshake_in_progress:
            if msg_type == MsgType.HANDSHAKE_COOKIE:
                self._handle_handshake_cookie(payload)
                return
            if msg_type == MsgType.HANDSHAKE_RESP:
                self._handle_handshake_resp(payload)
                return

        if self.transport_layer:
            if msg_type == MsgType.DATA:
                self._handle_data(payload)
                return
            if msg_type == MsgType.PING:
                self._send(MsgType.PONG, payload)
                return
            if msg_type == MsgType.PONG:
                self._handle_pong(payload)
                return
            if msg_type == MsgType.STRATEGY_ACK:
                self._handle_strategy_ack(payload)
                return
            if msg_type == MsgType.PROFILE_SWITCH:
                self._handle_profile_switch(payload)
                return
            if msg_type == MsgType.DISCONNECT:
                self._shutdown = True
                return

    def _handle_handshake_cookie(self, payload: bytes) -> None:
        self.metrics["handshake_cookies_received_total"] += 1
        self._handshake_cookie = unpack_handshake_cookie(payload)
        self._initiate_adaptive_handshake(reuse_keypair=True)

    def _handle_data(self, encrypted: bytes) -> None:
        if self.transport_layer is None:
            return
        payloads = self.transport_layer.unwrap_packet(encrypted)
        for raw_ip in payloads:
            if self.tun.is_up:
                self.tun.write_packet_sync(raw_ip)
        # Feed passive metric to evolution agent
        if self._evolution_adapter is not None:
            self._evolution_adapter.record_packet_received()

    def _handle_pong(self, payload: bytes) -> None:
        seq = unpack_ping(payload)
        self.metrics["keepalive_pongs_received_total"] += 1
        self._last_pong = time.time()
        if (
            self._pending_ping_future is None
            or self._pending_ping_future.done()
            or seq != self._pending_ping_seq
        ):
            return
        self._pending_ping_future.set_result(time.perf_counter())

    def _queue_strategy_sync(self, strategy: dict) -> None:
        """Queue a negotiated strategy update for the current or next session."""
        self._pending_strategy_id = strategy.get("strategy_id")
        self._pending_strategy_payload = strategy
        if not self.session_ready.is_set() or self.transport_layer is None:
            return
        if strategy.get("profile") != self.transport_layer.profile.value:
            return
        self._send_strategy_sync()

    def _send_strategy_sync(self) -> None:
        if self._pending_strategy_payload is None:
            return
        self._send(MsgType.STRATEGY_SYNC, pack_strategy_sync(self._pending_strategy_payload))

    def _handle_strategy_ack(self, payload: bytes) -> None:
        if self.transport_layer is None or self._pending_strategy_payload is None:
            return
        strategy_id, strategy = unpack_strategy_sync(payload)
        if strategy_id != self._pending_strategy_id:
            return
        self.transport_layer.apply_negotiated_strategy(strategy, self.auth_key)
        if self._evolution_adapter is not None:
            self._evolution_adapter.mark_strategy_negotiated(strategy_id)
        self._pending_strategy_id = None
        self._pending_strategy_payload = None

    def _handle_profile_switch(self, payload: bytes) -> None:
        """Handle server-pushed profile switch recommendation (DPI detected)."""
        try:
            recommended, reason = unpack_profile_switch(payload)
            profile_map = {p.value: i for i, p in enumerate(self.profiles)}
            idx = profile_map.get(recommended)
            if idx is None:
                logger.warning("Server recommended unknown profile: %s", recommended)
                return
            if idx == self.current_profile_idx:
                logger.debug("Server recommended current profile %s — ignoring", recommended)
                return
            logger.warning(
                "Server pushed PROFILE_SWITCH to %s (reason=%s) — roaming",
                recommended, reason,
            )
            self.current_profile_idx = idx
            self.metrics["dpi_blocks_detected"] += 1
            self._dpi_consecutive_failures = 0
            self._profile_switch_pending = time.time()  # track for ACK
            self._clear_active_session(notify_server=True)
            self._handshake_cookie = b""
            self._pending_client_pub = None
            self._temp_priv = None
            self._handshake_in_progress = False
            if self._handshake_retry_task:
                self._handshake_retry_task.cancel()
                self._handshake_retry_task = None
            self._initiate_adaptive_handshake()
        except Exception as exc:
            logger.warning("Failed to handle profile switch: %s", exc)

    def _clear_active_session(self, notify_server: bool = False) -> None:
        self._ensure_runtime_state()
        if notify_server and self.transport_layer is not None:
            self._send(MsgType.DISCONNECT)
            self.metrics["disconnects_total"] += 1
        if self._evolution_adapter is not None:
            self._evolution_adapter.detach_transport()
        self.transport_layer = None
        self.assigned_ip = None
        self.session_ready.clear()
        self._pending_ping_seq = None
        self._pending_ping_future = None

    @staticmethod
    def _iter_transport_packets(packet: bytes | List[bytes]) -> List[bytes]:
        if isinstance(packet, list):
            return packet
        return [packet]

    def _send_transport_data(self, packet: bytes | List[bytes]) -> None:
        for wire_packet in self._iter_transport_packets(packet):
            self._send(MsgType.DATA, wire_packet)

    def _handle_handshake_resp(self, payload: bytes):
        self._ensure_runtime_state()
        try:
            previous_assigned_ip = self.assigned_ip
            ciphertext, assigned_ip, negotiated_profile, auth_tag = unpack_handshake_resp(payload)
            if self._pending_client_pub is None or self._temp_priv is None:
                raise ValueError("missing pending handshake state")
            expected_auth_tag = compute_handshake_auth_tag(
                self.auth_key,
                self._pending_client_pub,
                self._handshake_cookie,
                ciphertext,
                assigned_ip,
                negotiated_profile,
            )
            if not auth_tag or not hmac.compare_digest(auth_tag, expected_auth_tag):
                self.metrics["handshake_auth_failures_total"] += 1
                raise ValueError("invalid handshake authentication tag")

            shared_secret = self.handshake.client_final(ciphertext, self._temp_priv)
            self._temp_priv = None
            self._pending_client_pub = None
            self._handshake_cookie = b""
            self._handshake_in_progress = False
            if self._handshake_retry_task:
                self._handshake_retry_task.cancel()
                self._handshake_retry_task = None

            if negotiated_profile in self.profiles:
                self.current_profile_idx = self.profiles.index(negotiated_profile)
            self.transport_layer = GhostTransport(shared_secret, profile=negotiated_profile)
            self.assigned_ip = assigned_ip
            self.session_ready.set()
            self.metrics["handshakes_total"] += 1

            # Attach evolution agent to the new transport
            if self._evolution_adapter is not None:
                self._evolution_adapter.attach_transport(self.transport_layer)
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._evolution_adapter.start())
                except RuntimeError:
                    pass
            if (
                self._pending_strategy_payload is not None
                and self._pending_strategy_payload.get("profile") == negotiated_profile.value
            ):
                self._send_strategy_sync()
            if (
                self.tun.is_up
                and previous_assigned_ip is not None
                and previous_assigned_ip != assigned_ip
            ):
                self._replace_tun_address(assigned_ip)
            logger.info(
                "GhostVPN session active with profile %s and IP %s",
                negotiated_profile.value,
                assigned_ip,
            )

            # Send PROFILE_SWITCH_ACK if this handshake was triggered by a profile switch
            switch_start = getattr(self, "_profile_switch_pending", None)
            if switch_start:
                latency_ms = (time.time() - switch_start) * 1000.0
                ack_payload = pack_profile_switch_ack(negotiated_profile.value, latency_ms)
                self._send(MsgType.PROFILE_SWITCH_ACK, ack_payload)
                self._profile_switch_pending = None
                logger.info(
                    "Sent PROFILE_SWITCH_ACK for %s (reconnect latency %.1fms)",
                    negotiated_profile.value, latency_ms,
                )
        except Exception as exc:
            self.metrics["handshakes_failed"] += 1
            logger.error("Handshake failed: %s", exc)
            self._roam_profile()

    def _roam_profile(self):
        self._ensure_runtime_state()
        self.metrics["roam_events_total"] += 1
        self._clear_active_session(notify_server=True)

        # Healing-aware profile selection: ask RPC bridge for best profile
        next_idx = self._select_next_profile()
        self.current_profile_idx = next_idx

        self._handshake_cookie = b""
        self._pending_client_pub = None
        self._temp_priv = None
        self._handshake_in_progress = False
        if self._handshake_retry_task:
            self._handshake_retry_task.cancel()
            self._handshake_retry_task = None
        logger.warning(
            "Switching to next GhostVPN profile: %s",
            self.profiles[self.current_profile_idx].value,
        )
        self._initiate_adaptive_handshake()

    def _select_next_profile(self) -> int:
        """Select next profile using mesh healing hints or round-robin fallback."""
        if self._evolution_adapter is not None:
            recommended = self._evolution_adapter.get_recommended_profile()
            if recommended:
                profile_map = {p.value: i for i, p in enumerate(self.profiles)}
                idx = profile_map.get(recommended)
                if idx is not None and idx != self.current_profile_idx:
                    logger.info("Evolution agent recommends profile %s", recommended)
                    return idx

        if self.rpc_bridge is not None:
            try:
                recommended = self.rpc_bridge.get_best_profile()
                if recommended:
                    profile_map = {p.value: i for i, p in enumerate(self.profiles)}
                    if recommended in profile_map:
                        idx = profile_map[recommended]
                        if idx != self.current_profile_idx:
                            logger.info(
                                "Mesh hints recommend profile %s", recommended
                            )
                            return idx
            except Exception as exc:
                logger.debug("Failed to get mesh profile hint: %s", exc)

        # Default: round-robin
        return (self.current_profile_idx + 1) % len(self.profiles)

    def _report_profile_success(self, latency_ms: float) -> None:
        """Report successful profile to mesh neighbors via RPC bridge."""
        if self.rpc_bridge is None or ProfileHint is None:
            return
        try:
            profile = self.profiles[self.current_profile_idx]
            hint = ProfileHint(
                source_node=self.rpc_bridge.node_id,
                profile=profile.value,
                latency_ms=latency_ms,
                success=True,
            )
            loop = asyncio.get_running_loop()
            loop.create_task(self.rpc_bridge.broadcast_profile_hint(hint))
        except Exception as exc:
            logger.debug("Failed to report profile success: %s", exc)

    async def _latency_monitor_loop(self):
        """Monitor RTT and trigger roaming when keepalive responses stall."""
        while not self._shutdown:
            sleep_for = KEEPALIVE_MIN
            if KEEPALIVE_MAX > KEEPALIVE_MIN:
                sleep_for += secrets.randbelow(KEEPALIVE_MAX - KEEPALIVE_MIN + 1)
            await asyncio.sleep(sleep_for)
            if not self.transport_layer:
                continue

            start = time.perf_counter()
            self._ping_seq += 1
            self._pending_ping_seq = self._ping_seq
            self._pending_ping_future = asyncio.get_running_loop().create_future()
            self.metrics["keepalive_pings_sent_total"] += 1
            self._send(MsgType.PING, pack_ping(self._ping_seq))
            try:
                pong_time = await asyncio.wait_for(self._pending_ping_future, timeout=PING_TIMEOUT)
                rtt = (pong_time - start) * 1000
                logger.info("GhostVPN RTT %.2f ms", rtt)
                self._report_profile_success(rtt)
                if self._evolution_adapter is not None:
                    self._evolution_adapter.record_packet_received(latency_ms=rtt)
                if rtt > (PING_TIMEOUT * 1000):
                    self._roam_profile()
            except asyncio.TimeoutError:
                self.metrics["keepalive_timeouts_total"] += 1
                logger.warning("GhostVPN keepalive timeout, roaming")
                self._roam_profile()
            finally:
                self._pending_ping_future = None
                self._pending_ping_seq = None

    async def _dpi_probe_loop(self):
        """Active DPI detection: send rapid probe bursts to detect blocking faster.

        Sends DPI_PROBE_COUNT pings in quick succession every DPI_PROBE_INTERVAL.
        If DPI_CONSECUTIVE_FAILURES successive probe rounds fail, triggers profile
        roaming and reports dpi_detected to the mesh via RPC bridge.
        """
        while not self._shutdown:
            await asyncio.sleep(DPI_PROBE_INTERVAL)
            if not self.transport_layer or not self.session_ready.is_set():
                self._dpi_consecutive_failures = 0
                continue

            successes = 0
            for _ in range(DPI_PROBE_COUNT):
                self._ping_seq += 1
                seq = self._ping_seq
                fut = asyncio.get_running_loop().create_future()
                self._pending_ping_seq = seq
                self._pending_ping_future = fut
                self.metrics["dpi_probes_sent"] += 1
                self._send(MsgType.PING, pack_ping(seq))
                try:
                    await asyncio.wait_for(fut, timeout=DPI_PROBE_TIMEOUT)
                    successes += 1
                    break  # one success is enough
                except asyncio.TimeoutError:
                    pass
                finally:
                    self._pending_ping_future = None
                    self._pending_ping_seq = None

            if successes == 0:
                self._dpi_consecutive_failures += 1
                self.metrics["dpi_probes_failed"] += 1
                logger.warning(
                    "DPI probe round failed (%d/%d consecutive)",
                    self._dpi_consecutive_failures,
                    DPI_CONSECUTIVE_FAILURES,
                )
                if self._dpi_consecutive_failures >= DPI_CONSECUTIVE_FAILURES:
                    self.metrics["dpi_blocks_detected"] += 1
                    self._dpi_consecutive_failures = 0
                    logger.warning(
                        "DPI BLOCK DETECTED on profile %s — switching",
                        self.profiles[self.current_profile_idx].value,
                    )
                    self._broadcast_dpi_event()
                    self._roam_profile()
            else:
                self._dpi_consecutive_failures = 0

    def _broadcast_dpi_event(self) -> None:
        """Notify mesh neighbors that DPI blocked the current profile."""
        if self.rpc_bridge is None:
            return
        try:
            event = self.rpc_bridge.make_event(
                target_node=self.rpc_bridge.node_id,
                incident_type="dpi_detected",
                action_taken="switch_profile",
                status="started",
                blocked_profile=self.profiles[self.current_profile_idx].value,
            )
            loop = asyncio.get_running_loop()
            loop.create_task(self.rpc_bridge.broadcast_event(event))
        except Exception as exc:
            logger.debug("Failed to broadcast DPI event: %s", exc)

    async def run_tun_listener(self):
        await self.tun.create()
        await self.session_ready.wait()
        await self.tun.set_address(f"{self.assigned_ip}/24")
        self._setup_routing()
        self._latency_task = asyncio.create_task(self._latency_monitor_loop())
        self._dpi_probe_task = asyncio.create_task(self._dpi_probe_loop())
        try:
            while not self._shutdown:
                packet = await self.tun.read_packet()
                if not packet or not self.transport_layer:
                    await asyncio.sleep(0.01)
                    continue
                # Only tunnel IPv4 packets (skip IPv6 NDP, etc.)
                if len(packet) < 20 or (packet[0] >> 4) != 4:
                    continue
                encrypted = self.transport_layer.wrap_packet(
                    packet, is_reliable=False
                )
                self._send_transport_data(encrypted)
                if self._evolution_adapter is not None:
                    self._evolution_adapter.record_packet_sent()
        finally:
            for task in (self._latency_task, self._dpi_probe_task):
                if task is not None:
                    task.cancel()
                    with suppress(asyncio.CancelledError):
                        await task
            self._latency_task = None
            self._dpi_probe_task = None
            self._cleanup_routing()

    def _setup_server_bypass(self) -> None:
        """Add ip rule + route so handshake packets bypass other VPN (e.g. sing-box)."""
        self._ensure_runtime_state()
        try:
            server_ip = self._server_route_target()
            res = subprocess.check_output(["ip", "route", "show", "default"]).decode()
            gw = res.split("via ")[1].split()[0]
            dev = res.split("dev ")[1].split()[0]

            # ip rule: traffic to VPN server goes via main table, not sing-box table 2022
            rule_spec = ["to", f"{server_ip}/32", "lookup", "main", "priority", "8998"]
            result = subprocess.run(["ip", "rule", "add", *rule_spec], capture_output=True, text=True)
            if result.returncode == 0:
                self._managed_rules.append(rule_spec)
                logger.info("Added server bypass rule: %s", " ".join(rule_spec))

            # ip route: ensure VPN server is reachable via physical gateway
            route_spec = [f"{server_ip}/32", "via", gw, "dev", dev]
            result = subprocess.run(["ip", "route", "add", *route_spec], capture_output=True, text=True)
            if result.returncode == 0:
                self._managed_routes.append(route_spec)
                logger.info("Added server bypass route: %s", " ".join(route_spec))
            elif "File exists" not in (result.stderr or ""):
                logger.debug("Server route already exists or failed: %s", result.stderr)
        except Exception as exc:
            logger.warning("Server bypass setup failed: %s", exc)

    def _setup_routing(self):
        self._ensure_runtime_state()
        self._cleanup_routing()
        try:
            res = subprocess.check_output(["ip", "route", "show", "default"]).decode()
            gw = res.split("via ")[1].split()[0]
            dev = res.split("dev ")[1].split()[0]
            vpn_gateway = self._vpn_gateway()
            server_target = self._server_route_target()

            # Add ip rule to bypass other VPN policy routing (e.g. sing-box table 2022)
            # for traffic destined to Ghost VPN subnet and for traffic from TUN
            ghost_subnet = f"{vpn_gateway.rsplit('.', 1)[0]}.0/24"
            rule_specs = [
                ["to", ghost_subnet, "lookup", "main", "priority", "8999"],
                ["from", ghost_subnet, "lookup", "main", "priority", "8999"],
            ]
            for rule_spec in rule_specs:
                result = subprocess.run(
                    ["ip", "rule", "add", *rule_spec],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self._managed_rules.append(rule_spec)
                    logger.debug("Added ip rule: %s", " ".join(rule_spec))

            route_specs = [
                [server_target, "via", gw, "dev", dev],
                ["0.0.0.0/1", "via", vpn_gateway, "dev", "tun_ghost_c"],
                ["128.0.0.0/1", "via", vpn_gateway, "dev", "tun_ghost_c"],
            ]
            for route_spec in route_specs:
                result = subprocess.run(
                    ["ip", "route", "add", *route_spec],
                    capture_output=True,
                    text=True,
                )
                if result.returncode == 0:
                    self._managed_routes.append(route_spec)
                elif "File exists" not in (result.stderr or ""):
                    logger.warning(
                        "Failed to add GhostVPN route %s: %s",
                        " ".join(route_spec),
                        (result.stderr or "").strip(),
                    )
        except Exception as exc:
            logger.warning("GhostVPN route setup failed: %s", exc)

    def _replace_tun_address(self, assigned_ip: str) -> None:
        subprocess.run(
            ["ip", "addr", "replace", f"{assigned_ip}/24", "dev", "tun_ghost_c"],
            capture_output=True,
        )

    def _vpn_gateway(self) -> str:
        if not self.assigned_ip:
            raise ValueError("assigned_ip is not set")
        try:
            ipaddress.IPv4Address(self.assigned_ip)
        except ipaddress.AddressValueError:
            raise ValueError(f"assigned_ip must be a valid IPv4 address: {self.assigned_ip}")
        subnet_prefix, _, _ = self.assigned_ip.rpartition(".")
        return f"{subnet_prefix}.1"

    def _server_route_target(self) -> str:
        host = self.server_addr[0]
        try:
            # If host is already an IP address, return it
            return str(ipaddress.ip_address(host))
        except ValueError:
            pass

        # Host is a hostname, resolve it
        addr_info = socket.getaddrinfo(host, self.server_addr[1], type=socket.SOCK_DGRAM)
        if not addr_info:
            raise ValueError(f"failed to resolve server address: {host}")
        return addr_info[0][4][0]

    def _cleanup_routing(self):
        self._ensure_runtime_state()
        for route_spec in reversed(self._managed_routes):
            subprocess.run(["ip", "route", "del", *route_spec], capture_output=True)
        self._managed_routes = []
        for rule_spec in reversed(self._managed_rules):
            subprocess.run(["ip", "rule", "del", *rule_spec], capture_output=True)
        self._managed_rules = []

    def _apply_transport_socket_options(self) -> None:
        if self.transport is None or self.transport_layer is None:
            return
        sock = None
        get_extra_info = getattr(self.transport, "get_extra_info", None)
        if callable(get_extra_info):
            sock = get_extra_info("socket")
        if sock is None:
            return
        ttl = self.transport_layer.get_send_socket_ttl()
        try:
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_TTL, ttl or 64)
        except OSError as exc:
            logger.debug("Failed to apply client socket TTL: %s", exc)

    def _send(self, msg_type: MsgType, payload: bytes = b""):
        if self.transport is None:
            return
        self._apply_transport_socket_options()
        frame = pack_protected_msg(self.auth_key, msg_type, payload)
        self.transport.sendto(frame, self.server_addr)
        self.metrics["bytes_out"] += len(frame)
        self.metrics["packets_out"] += 1

    async def _start_metrics_server(self) -> None:
        try:
            self._metrics_server = await asyncio.start_server(
                self._handle_metrics_http,
                host=CLIENT_METRICS_HOST,
                port=CLIENT_METRICS_PORT,
            )
            logger.info(
                "GhostVPN client metrics server listening on http://%s:%s",
                CLIENT_METRICS_HOST,
                CLIENT_METRICS_PORT,
            )
            await self._metrics_server.serve_forever()
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.warning("GhostVPN client metrics server failed: %s", exc)

    async def _handle_metrics_http(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        try:
            raw_request = await reader.read(4096)
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
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    def get_metrics(self) -> dict:
        return {
            **self.metrics,
            "uptime_sec": time.time() - self.metrics["started_at"],
            "active_profile": self.profiles[self.current_profile_idx].value,
            "transport_ready": self.transport_layer is not None,
            "session_ready": self.session_ready.is_set(),
        }

    def get_health_status(self) -> dict:
        metrics = self.get_metrics()
        return {
            "healthy": self.transport is not None and self.tun.is_up and metrics["session_ready"],
            "transport_bound": self.transport is not None,
            "tun_up": self.tun.is_up,
            "session_ready": metrics["session_ready"],
            "active_profile": metrics["active_profile"],
            "handshakes_failed": metrics["handshakes_failed"],
            "keepalive_timeouts_total": metrics["keepalive_timeouts_total"],
            "roam_events_total": metrics["roam_events_total"],
        }

    def render_prometheus_metrics(self) -> str:
        metrics = self.get_metrics()
        metric_meta = {
            "ghostvpn_client_handshakes_total": ("counter", "Completed GhostVPN client handshakes"),
            "ghostvpn_client_handshakes_failed_total": ("counter", "Failed GhostVPN client handshakes"),
            "ghostvpn_client_handshake_cookies_received_total": ("counter", "GhostVPN client cookie challenges received"),
            "ghostvpn_client_handshake_auth_failures_total": ("counter", "GhostVPN client handshake authentication failures"),
            "ghostvpn_client_handshake_retries_total": ("counter", "GhostVPN client handshake retransmissions"),
            "ghostvpn_client_roam_events_total": ("counter", "GhostVPN client roam events"),
            "ghostvpn_client_disconnects_total": ("counter", "GhostVPN client disconnects"),
            "ghostvpn_client_keepalive_pings_sent_total": ("counter", "GhostVPN client keepalive pings sent"),
            "ghostvpn_client_keepalive_pongs_received_total": ("counter", "GhostVPN client keepalive pongs received"),
            "ghostvpn_client_keepalive_timeouts_total": ("counter", "GhostVPN client keepalive timeouts"),
            "ghostvpn_client_packets_in_total": ("counter", "GhostVPN client packets received"),
            "ghostvpn_client_packets_out_total": ("counter", "GhostVPN client packets sent"),
            "ghostvpn_client_bytes_in_total": ("counter", "GhostVPN client bytes received"),
            "ghostvpn_client_bytes_out_total": ("counter", "GhostVPN client bytes sent"),
            "ghostvpn_client_session_ready": ("gauge", "GhostVPN client session state"),
            "ghostvpn_client_transport_ready": ("gauge", "GhostVPN client transport readiness"),
            "ghostvpn_client_uptime_seconds": ("gauge", "GhostVPN client uptime in seconds"),
        }
        metric_values = {
            "ghostvpn_client_handshakes_total": metrics["handshakes_total"],
            "ghostvpn_client_handshakes_failed_total": metrics["handshakes_failed"],
            "ghostvpn_client_handshake_cookies_received_total": metrics["handshake_cookies_received_total"],
            "ghostvpn_client_handshake_auth_failures_total": metrics["handshake_auth_failures_total"],
            "ghostvpn_client_handshake_retries_total": metrics["handshake_retries_total"],
            "ghostvpn_client_roam_events_total": metrics["roam_events_total"],
            "ghostvpn_client_disconnects_total": metrics["disconnects_total"],
            "ghostvpn_client_keepalive_pings_sent_total": metrics["keepalive_pings_sent_total"],
            "ghostvpn_client_keepalive_pongs_received_total": metrics["keepalive_pongs_received_total"],
            "ghostvpn_client_keepalive_timeouts_total": metrics["keepalive_timeouts_total"],
            "ghostvpn_client_packets_in_total": metrics["packets_in"],
            "ghostvpn_client_packets_out_total": metrics["packets_out"],
            "ghostvpn_client_bytes_in_total": metrics["bytes_in"],
            "ghostvpn_client_bytes_out_total": metrics["bytes_out"],
            "ghostvpn_client_session_ready": 1 if metrics["session_ready"] else 0,
            "ghostvpn_client_transport_ready": 1 if metrics["transport_ready"] else 0,
            "ghostvpn_client_uptime_seconds": metrics["uptime_sec"],
        }

        lines = []
        for name, (metric_type, description) in metric_meta.items():
            lines.append(f"# HELP {name} {description}")
            lines.append(f"# TYPE {name} {metric_type}")
            lines.append(f"{name} {metric_values[name]}")
        lines.append(f'ghostvpn_client_active_profile{{profile="{metrics["active_profile"]}"}} 1')
        return "\n".join(lines) + "\n"

    def disconnect(self):
        self._shutdown = True
        self._clear_active_session(notify_server=True)
        self._cleanup_routing()
        self.tun.close()
        if self.transport:
            self.transport.close()


# ------------------------------------------------------------------
# TCP Transport Adapter
# ------------------------------------------------------------------


class GhostTCPTransport:
    """
    Adapts a TCP connection to look like a DatagramTransport.

    The TCP bridge on the server uses 2-byte big-endian length-prefixed
    framing, so each UDP datagram is wrapped as [len(2)][payload].
    """

    def __init__(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
        protocol: GhostVPNClient,
    ):
        self._reader = reader
        self._writer = writer
        self._protocol = protocol
        self._closed = False
        self._read_task: Optional[asyncio.Task] = None

    def start(self) -> None:
        """Begin reading frames from TCP and dispatching as datagrams."""
        self._read_task = asyncio.get_running_loop().create_task(self._read_loop())

    async def _read_loop(self) -> None:
        try:
            while not self._closed:
                header = await self._reader.readexactly(2)
                length = int.from_bytes(header, "big")
                if length == 0 or length > 65535:
                    break
                data = await self._reader.readexactly(length)
                self._protocol.datagram_received(data, self._protocol.server_addr)
        except (asyncio.IncompleteReadError, ConnectionError, OSError):
            if not self._closed:
                logger.warning("TCP transport connection lost")
                self._protocol.connection_lost(ConnectionError("TCP closed"))
        except asyncio.CancelledError:
            pass

    def sendto(self, data: bytes, addr=None) -> None:
        """Send a datagram as a length-prefixed TCP frame."""
        if self._closed or self._writer.is_closing():
            return
        frame = len(data).to_bytes(2, "big") + data
        self._writer.write(frame)

    def close(self) -> None:
        self._closed = True
        if self._read_task:
            self._read_task.cancel()
        if not self._writer.is_closing():
            self._writer.close()

    def is_closing(self) -> bool:
        return self._closed

    def get_extra_info(self, name, default=None):
        return self._writer.get_extra_info(name, default)


# ------------------------------------------------------------------
# Connection helpers
# ------------------------------------------------------------------


UDP_HANDSHAKE_TIMEOUT = float(os.getenv("GHOST_UDP_TIMEOUT", "5.0"))
TCP_BRIDGE_PORT = int(os.getenv("GHOST_TCP_PORT", "4434"))
TRANSPORT_MODE = os.getenv("GHOST_TRANSPORT", "auto")  # "udp", "tcp", "auto"


async def connect_udp(
    server_ip: str, port: int, client: GhostVPNClient
) -> None:
    """Connect via UDP (standard path)."""
    loop = asyncio.get_running_loop()
    await loop.create_datagram_endpoint(
        lambda: client, remote_addr=(server_ip, port)
    )
    logger.info("Connected via UDP to %s:%d", server_ip, port)


async def connect_tcp(
    server_ip: str, port: int, client: GhostVPNClient
) -> None:
    """Connect via TCP bridge (fallback when UDP is blocked)."""
    reader, writer = await asyncio.open_connection(server_ip, port)
    tcp_transport = GhostTCPTransport(reader, writer, client)
    # Inject TCP transport as if it were a DatagramTransport
    client.transport = tcp_transport  # type: ignore[assignment]
    tcp_transport.start()
    client.connection_made(tcp_transport)  # type: ignore[arg-type]
    logger.info("Connected via TCP bridge to %s:%d", server_ip, port)


async def connect_auto(
    server_ip: str,
    udp_port: int,
    tcp_port: int,
    client: GhostVPNClient,
) -> None:
    """Try UDP first; if handshake fails within timeout, fall back to TCP."""
    try:
        await connect_udp(server_ip, udp_port, client)
        await asyncio.wait_for(client.session_ready.wait(), timeout=UDP_HANDSHAKE_TIMEOUT)
        logger.info("UDP handshake succeeded")
    except (asyncio.TimeoutError, OSError) as exc:
        logger.warning("UDP failed (%s), falling back to TCP bridge", exc)
        # Close the failed UDP transport
        if client.transport:
            client.transport.close()
            client.transport = None
        client.session_ready.clear()
        client._handshake_in_progress = False
        await connect_tcp(server_ip, tcp_port, client)


async def _connect_client(
    server_ip: str, udp_port: int, tcp_port: int, mode: str, client: GhostVPNClient
) -> None:
    """Establish connection using the specified transport mode."""
    if mode == "tcp":
        await connect_tcp(server_ip, tcp_port, client)
    elif mode == "udp":
        await connect_udp(server_ip, udp_port, client)
    else:
        await connect_auto(server_ip, udp_port, tcp_port, client)


def _next_profile_idx(current_profile_idx: int, num_profiles: int) -> int:
    """Advance to the next obfuscation profile, wrapping around safely."""
    if num_profiles <= 0:
        return 0
    return (current_profile_idx + 1) % num_profiles


async def run_client(
    server_ip: str,
    udp_port: int,
    *,
    tcp_port: Optional[int] = None,
    mode: Optional[str] = None,
    auth_key: Optional[bytes | str] = None,
    enable_evolution: Optional[bool] = None,
    evolution_interval_sec: Optional[float] = None,
    reconnect_enabled: Optional[bool] = None,
    reconnect_base_delay: Optional[float] = None,
    reconnect_max_delay: Optional[float] = None,
    reconnect_max_attempts: Optional[int] = None,
    require_root: bool = True,
) -> None:
    if require_root and os.geteuid() != 0:
        print("Must be run as root.")
        sys.exit(1)

    tcp_port = TCP_BRIDGE_PORT if tcp_port is None else tcp_port
    mode = TRANSPORT_MODE if mode is None else mode
    reconnect_enabled = RECONNECT_ENABLED if reconnect_enabled is None else reconnect_enabled
    reconnect_base_delay = (
        RECONNECT_BASE_DELAY if reconnect_base_delay is None else reconnect_base_delay
    )
    reconnect_max_delay = RECONNECT_MAX_DELAY if reconnect_max_delay is None else reconnect_max_delay
    reconnect_max_attempts = (
        RECONNECT_MAX_ATTEMPTS if reconnect_max_attempts is None else reconnect_max_attempts
    )

    attempt = 0
    delay = reconnect_base_delay
    profile_idx = 0

    while True:
        client = GhostVPNClient(
            server_addr=(server_ip, udp_port),
            auth_key=auth_key,
            enable_evolution=enable_evolution,
            evolution_interval_sec=evolution_interval_sec,
            initial_profile_idx=profile_idx,
        )
        client._setup_server_bypass()

        try:
            await _connect_client(server_ip, udp_port, tcp_port, mode, client)
            attempt = 0
            delay = reconnect_base_delay

            # Run TUN listener and watch for connection_lost concurrently
            tun_task = asyncio.create_task(client.run_tun_listener())
            lost_task = asyncio.create_task(client._connection_lost_event.wait())

            done, pending = await asyncio.wait(
                [tun_task, lost_task], return_when=asyncio.FIRST_COMPLETED
            )
            for t in pending:
                t.cancel()
                with suppress(asyncio.CancelledError):
                    await t

            # Check if TUN listener exited cleanly (shutdown requested)
            if client._shutdown:
                logger.info("GhostVPN client shutdown requested")
                break

        except (OSError, ConnectionError, asyncio.TimeoutError) as exc:
            logger.warning("Connection failed: %s", exc)
        finally:
            profile_idx = client.current_profile_idx
            client.disconnect()

        if not reconnect_enabled:
            logger.info("Auto-reconnect disabled, exiting")
            break

        attempt += 1
        if reconnect_max_attempts > 0 and attempt >= reconnect_max_attempts:
            logger.error("Max reconnect attempts (%d) reached", reconnect_max_attempts)
            break

        # Rotate profile after every 2 consecutive reconnect attempts
        if attempt % 2 == 0:
            old_profile = client.profiles[profile_idx].value
            profile_idx = _next_profile_idx(profile_idx, len(client.profiles))
            logger.warning(
                "Rotating profile after %d reconnect failures: %s → %s",
                attempt,
                old_profile,
                client.profiles[profile_idx].value,
            )

        client.metrics["reconnect_attempts"] += 1
        logger.info("Reconnecting in %.1fs (attempt %d)...", delay, attempt)
        await asyncio.sleep(delay)
        delay = min(delay * 2, reconnect_max_delay)


async def main():
    server_ip = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GHOST_VPN_SERVER", "")
    if not server_ip:
        print("Usage: ghost_vpn_client.py <server_ip>  or set GHOST_VPN_SERVER env var")
        sys.exit(1)
    udp_port = int(os.getenv("GHOST_VPN_PORT", "4433"))
    await run_client(server_ip, udp_port)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    asyncio.run(main())
