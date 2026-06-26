#!/usr/bin/env python3
"""
x0tta6bl4 Obfuscated SOCKS5 Proxy
SOCKS5 proxy with DPI evasion using obfuscation techniques.

Usage:
    python3 -m src.network.obfuscated_socks5 --port 1080 --method faketls

Methods:
    - faketls: TLS 1.3 handshake mimicry
    - shadowsocks: Shadowsocks AEAD encryption
    - domain_fronting: Domain fronting through CDNs
    - stegomesh: Steganographic protocol mimicry
    - hybrid: Combination of multiple methods
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import logging
import socket
import struct
import time
from typing import Any, Dict, Optional, Tuple

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity
from .vpn_obfuscation_manager import (
    ObfuscationMethod,
    RotationStrategy,
    get_vpn_obfuscator,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

_SERVICE_AGENT = "obfuscated-socks5-proxy"
_SERVICE_LAYER = "network_obfuscated_socks5_proxy_local_evidence"
_KNOWN_METHODS = frozenset(
    {"none", "faketls", "shadowsocks", "domain_fronting", "stegomesh", "hybrid"}
)
OBFUSCATED_SOCKS5_CLAIM_BOUNDARY = (
    "Local obfuscated SOCKS5 proxy evidence only. It records proxy lifecycle, "
    "SOCKS handshake/result buckets, relay byte-count buckets, duration, "
    "method buckets, and redacted service identity presence; it does not expose "
    "client addresses, target hosts, ports, payload bytes, SNI/domain "
    "parameters, or prove DPI bypass, censorship bypass, remote reachability, "
    "packet delivery, anonymity, provider health, client installation, or "
    "production customer traffic use."
)


def _sha256_prefix(value: Any) -> Optional[str]:
    text = str(value or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()[:16]


def _port_bucket(port: Any) -> str:
    if not isinstance(port, int) or port <= 0:
        return "unknown"
    if port < 1024:
        return "system"
    if port < 49152:
        return "registered"
    if port <= 65535:
        return "dynamic"
    return "invalid"


def _byte_count_bucket(value: Any) -> str:
    if not isinstance(value, int) or value <= 0:
        return "zero"
    if value <= 64:
        return "tiny"
    if value <= 512:
        return "small"
    if value <= 1500:
        return "mtu"
    if value <= 8192:
        return "chunk"
    return "large"


def _address_type(host: Any) -> str:
    text = str(host or "").strip()
    if not text:
        return "missing"
    try:
        socket.inet_pton(socket.AF_INET, text)
        return "ipv4"
    except OSError:
        pass
    try:
        socket.inet_pton(socket.AF_INET6, text)
        return "ipv6"
    except OSError:
        pass
    return "domain"


def _method_bucket(value: Any) -> str:
    method = str(value or "").strip()
    if not method:
        return "unknown"
    if method in _KNOWN_METHODS:
        return method
    return "custom"


class ObfuscatedSOCKS5Server:
    """
    SOCKS5 server with traffic obfuscation for DPI bypass.

    Features:
    - Multiple obfuscation methods (FakeTLS, Shadowsocks, etc.)
    - Rotating parameters (SNI, fingerprints)
    - Traffic shaping
    """

    SOCKS_VERSION = 5

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 1080,
        obfuscation_method: str = "faketls",
        rotation_interval: int = 300,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.host = host
        self.port = port
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self._server: Optional[asyncio.Server] = None
        self._running = False

        # Initialize obfuscation manager
        self.obfuscator = get_vpn_obfuscator(
            event_bus=event_bus,
            event_project_root=event_project_root,
        )

        # Set obfuscation method
        method_map = {
            "none": ObfuscationMethod.NONE,
            "faketls": ObfuscationMethod.FAKETLS,
            "shadowsocks": ObfuscationMethod.SHADOWSOCKS,
            "domain_fronting": ObfuscationMethod.DOMAIN_FRONTING,
            "stegomesh": ObfuscationMethod.STEGOMESH,
            "hybrid": ObfuscationMethod.HYBRID,
        }

        self.obfuscator.set_obfuscation_method(
            method_map.get(obfuscation_method, ObfuscationMethod.FAKETLS)
        )
        self.obfuscator.set_rotation_strategy(RotationStrategy.TIME_BASED)
        self.obfuscator.set_rotation_interval(rotation_interval)

        # Statistics
        self.connections = 0
        self.bytes_sent = 0
        self.bytes_recv = 0

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize obfuscated SOCKS5 EventBus: %s", exc)
            return None

    def _service_identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _listen_metadata(self) -> Dict[str, Any]:
        return {
            "host_present": bool(str(self.host or "").strip()),
            "host_hash": _sha256_prefix(self.host),
            "host_type": _address_type(self.host),
            "port_bucket": _port_bucket(self.port),
            "raw_listen_address_redacted": True,
        }

    def _obfuscation_metadata(self) -> Dict[str, Any]:
        params: Dict[str, Any] = {}
        try:
            maybe_params = self.obfuscator.get_current_parameters()
            if isinstance(maybe_params, dict):
                params = maybe_params
        except Exception as exc:
            logger.debug("Failed to read obfuscation parameters for evidence: %s", exc)
        return {
            "method_bucket": _method_bucket(params.get("method")),
            "sni_present": bool(params.get("sni")),
            "sni_hash": _sha256_prefix(params.get("sni")),
            "fingerprint_present": bool(params.get("fingerprint")),
            "fingerprint_hash": _sha256_prefix(params.get("fingerprint")),
            "rotation_interval_present": params.get("rotation_interval") is not None,
            "raw_parameters_redacted": True,
        }

    def _target_metadata(
        self,
        target: Optional[Tuple[str, int]],
    ) -> Dict[str, Any]:
        if not target:
            return {
                "present": False,
                "raw_target_redacted": True,
            }
        host, port = target
        return {
            "present": True,
            "host_type": _address_type(host),
            "host_hash": _sha256_prefix(host),
            "port_bucket": _port_bucket(port),
            "raw_target_redacted": True,
        }

    def _peer_metadata(self, peer: Any) -> Dict[str, Any]:
        return {
            "present": peer is not None,
            "peer_hash": _sha256_prefix(repr(peer)) if peer is not None else None,
            "raw_peer_redacted": True,
        }

    def _publish_proxy_evidence(
        self,
        *,
        operation: str,
        status_value: str,
        started_at: float,
        metadata: Optional[Dict[str, Any]] = None,
        error_type: Optional[str] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        payload: Dict[str, Any] = {
            "component": "network.obfuscated_socks5",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "listen": self._listen_metadata(),
            "obfuscation": self._obfuscation_metadata(),
            "service_identity": self._service_identity_presence(),
            "control_action": operation in {"start", "stop"},
            "observed_state": operation
            in {"client_session", "relay_obfuscated", "stats_read"},
            "raw_identifiers_redacted": True,
            "payloads_redacted": True,
            "targets_redacted": True,
            "client_addresses_redacted": True,
            "raw_parameters_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "claim_boundary": OBFUSCATED_SOCKS5_CLAIM_BOUNDARY,
        }
        if metadata:
            payload.update(metadata)
        if error_type:
            payload["error"] = {
                "type": error_type,
                "message_redacted": True,
            }

        event_type = (
            EventType.TASK_FAILED
            if status_value == "failed"
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish obfuscated SOCKS5 evidence: %s", exc)
            return None

    async def start(self):
        """Start the SOCKS5 server."""
        started_at = time.monotonic()
        try:
            self._server = await asyncio.start_server(
                self._handle_client, self.host, self.port
            )
            self._running = True

            params = self.obfuscator.get_current_parameters()

            self._publish_proxy_evidence(
                operation="start",
                status_value="started",
                started_at=started_at,
            )

            logger.info("=" * 60)
            logger.info("  x0tta6bl4 OBFUSCATED SOCKS5 PROXY")
            logger.info("=" * 60)
            logger.info(f"  Listening: {self.host}:{self.port}")
            logger.info(f"  Obfuscation: {params['method']}")
            logger.info(f"  SNI: {params['sni']}")
            logger.info(f"  Fingerprint: {params['fingerprint']}")
            logger.info(f"  Rotation: {params['rotation_interval']}s")
            logger.info("=" * 60)
            logger.info(
                f"  Test: curl -x socks5://127.0.0.1:{self.port} https://ifconfig.me"
            )
            logger.info("=" * 60)

            async with self._server:
                await self._server.serve_forever()
        except Exception as exc:
            self._publish_proxy_evidence(
                operation="start",
                status_value="failed",
                started_at=started_at,
                error_type=type(exc).__name__,
            )
            raise

    async def stop(self):
        """Stop the server."""
        started_at = time.monotonic()
        self._running = False
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        self._publish_proxy_evidence(
            operation="stop",
            status_value="stopped",
            started_at=started_at,
            metadata={
                "stats": {
                    "connections_bucket": _byte_count_bucket(self.connections),
                    "bytes_sent_bucket": _byte_count_bucket(self.bytes_sent),
                    "bytes_recv_bucket": _byte_count_bucket(self.bytes_recv),
                },
            },
        )

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ):
        """Handle incoming SOCKS5 connection."""
        started_at = time.monotonic()
        client_addr = writer.get_extra_info("peername")
        self.connections += 1
        target: Optional[Tuple[str, int]] = None

        try:
            # SOCKS5 handshake
            if not await self._socks5_handshake(reader, writer):
                self._publish_proxy_evidence(
                    operation="client_session",
                    status_value="handshake_rejected",
                    started_at=started_at,
                    metadata={
                        "client": self._peer_metadata(client_addr),
                        "target": self._target_metadata(target),
                        "handshake_ok": False,
                        "connect_attempted": False,
                    },
                )
                return

            # Get target address
            target = await self._get_target_address(reader, writer)
            if not target:
                self._publish_proxy_evidence(
                    operation="client_session",
                    status_value="target_parse_failed",
                    started_at=started_at,
                    metadata={
                        "client": self._peer_metadata(client_addr),
                        "target": self._target_metadata(target),
                        "handshake_ok": True,
                        "connect_attempted": False,
                    },
                )
                return

            target_host, target_port = target
            logger.info(f"🌐 {client_addr} → {target_host}:{target_port}")

            # Connect to target
            try:
                target_reader, target_writer = await asyncio.wait_for(
                    asyncio.open_connection(target_host, target_port), timeout=10.0
                )
            except Exception as e:
                logger.error(f"Connection failed: {e}")
                await self._send_reply(writer, 0x05)  # Connection refused
                self._publish_proxy_evidence(
                    operation="client_session",
                    status_value="connect_failed",
                    started_at=started_at,
                    metadata={
                        "client": self._peer_metadata(client_addr),
                        "target": self._target_metadata(target),
                        "handshake_ok": True,
                        "connect_attempted": True,
                        "connect_succeeded": False,
                    },
                    error_type=type(e).__name__,
                )
                return

            # Send success reply
            await self._send_reply(writer, 0x00)

            # Relay data with obfuscation
            await self._relay_obfuscated(
                reader, writer, target_reader, target_writer
            )

            target_writer.close()
            self._publish_proxy_evidence(
                operation="client_session",
                status_value="completed",
                started_at=started_at,
                metadata={
                    "client": self._peer_metadata(client_addr),
                    "target": self._target_metadata(target),
                    "handshake_ok": True,
                    "connect_attempted": True,
                    "connect_succeeded": True,
                },
            )

        except Exception as e:
            logger.error(f"Client error: {e}")
            self._publish_proxy_evidence(
                operation="client_session",
                status_value="failed",
                started_at=started_at,
                metadata={
                    "client": self._peer_metadata(client_addr),
                    "target": self._target_metadata(target),
                },
                error_type=type(e).__name__,
            )
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass

    async def _socks5_handshake(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> bool:
        """Perform SOCKS5 handshake."""
        header = await reader.read(2)
        if len(header) < 2:
            return False

        version, nmethods = header[0], header[1]

        if version != self.SOCKS_VERSION:
            return False

        methods = await reader.read(nmethods)

        if 0x00 in methods:
            writer.write(bytes([self.SOCKS_VERSION, 0x00]))
            await writer.drain()
            return True
        else:
            writer.write(bytes([self.SOCKS_VERSION, 0xFF]))
            await writer.drain()
            return False

    async def _get_target_address(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> Optional[Tuple[str, int]]:
        """Parse SOCKS5 connection request."""
        header = await reader.read(4)
        if len(header) < 4:
            return None

        version, cmd, _, atyp = header

        if version != self.SOCKS_VERSION:
            return None

        if cmd != 0x01:
            await self._send_reply(writer, 0x07)
            return None

        if atyp == 0x01:  # IPv4
            addr_data = await reader.read(4)
            target_host = socket.inet_ntoa(addr_data)
        elif atyp == 0x03:  # Domain
            length = (await reader.read(1))[0]
            target_host = (await reader.read(length)).decode()
        elif atyp == 0x04:  # IPv6
            addr_data = await reader.read(16)
            target_host = socket.inet_ntop(socket.AF_INET6, addr_data)
        else:
            await self._send_reply(writer, 0x08)
            return None

        port_data = await reader.read(2)
        target_port = struct.unpack("!H", port_data)[0]

        return target_host, target_port

    async def _send_reply(self, writer: asyncio.StreamWriter, status: int):
        """Send SOCKS5 reply."""
        reply = bytes([
            self.SOCKS_VERSION, status, 0x00, 0x01,
            0, 0, 0, 0,  # Bind address
            0, 0,  # Bind port
        ])
        writer.write(reply)
        await writer.drain()

    async def _relay_obfuscated(
        self,
        client_reader: asyncio.StreamReader,
        client_writer: asyncio.StreamWriter,
        target_reader: asyncio.StreamReader,
        target_writer: asyncio.StreamWriter,
    ):
        """Relay data with obfuscation applied."""
        started_at = time.monotonic()
        sent_before = self.bytes_sent
        recv_before = self.bytes_recv
        upstream_chunks = 0
        downstream_chunks = 0
        upstream_errors = 0
        downstream_errors = 0

        async def forward_upstream():
            """Client -> Target (with obfuscation)."""
            nonlocal upstream_chunks, upstream_errors
            try:
                while self._running:
                    data = await client_reader.read(8192)
                    if not data:
                        break

                    # Apply obfuscation
                    obfuscated = self.obfuscator.obfuscate(data)

                    target_writer.write(obfuscated)
                    await target_writer.drain()

                    self.bytes_sent += len(data)
                    upstream_chunks += 1

            except (ConnectionResetError, BrokenPipeError):
                upstream_errors += 1
                pass
            except Exception as e:
                upstream_errors += 1
                logger.debug(f"Upstream error: {e}")

        async def forward_downstream():
            """Target -> Client (with deobfuscation)."""
            nonlocal downstream_chunks, downstream_errors
            try:
                while self._running:
                    data = await target_reader.read(8192)
                    if not data:
                        break

                    # Remove obfuscation
                    deobfuscated = self.obfuscator.deobfuscate(data)

                    client_writer.write(deobfuscated)
                    await client_writer.drain()

                    self.bytes_recv += len(deobfuscated)
                    downstream_chunks += 1

            except (ConnectionResetError, BrokenPipeError):
                downstream_errors += 1
                pass
            except Exception as e:
                downstream_errors += 1
                logger.debug(f"Downstream error: {e}")

        await asyncio.gather(
            forward_upstream(),
            forward_downstream(),
            return_exceptions=True,
        )
        status_value = (
            "completed"
            if upstream_errors == 0 and downstream_errors == 0
            else "degraded"
        )
        self._publish_proxy_evidence(
            operation="relay_obfuscated",
            status_value=status_value,
            started_at=started_at,
            metadata={
                "relay": {
                    "upstream_chunks": upstream_chunks,
                    "downstream_chunks": downstream_chunks,
                    "upstream_errors": upstream_errors,
                    "downstream_errors": downstream_errors,
                    "bytes_sent_delta_bucket": _byte_count_bucket(
                        self.bytes_sent - sent_before
                    ),
                    "bytes_recv_delta_bucket": _byte_count_bucket(
                        self.bytes_recv - recv_before
                    ),
                    "payloads_redacted": True,
                },
            },
        )

    def get_stats(self) -> dict:
        """Get server statistics."""
        started_at = time.monotonic()
        self._publish_proxy_evidence(
            operation="stats_read",
            status_value="read",
            started_at=started_at,
            metadata={
                "stats": {
                    "connections_bucket": _byte_count_bucket(self.connections),
                    "bytes_sent_bucket": _byte_count_bucket(self.bytes_sent),
                    "bytes_recv_bucket": _byte_count_bucket(self.bytes_recv),
                },
            },
        )
        return {
            "connections": self.connections,
            "bytes_sent": self.bytes_sent,
            "bytes_recv": self.bytes_recv,
            "obfuscation": self.obfuscator.get_current_parameters(),
        }


async def main():
    parser = argparse.ArgumentParser(
        description="x0tta6bl4 Obfuscated SOCKS5 Proxy"
    )
    parser.add_argument("--host", default="0.0.0.0", help="Listen host")
    parser.add_argument("--port", type=int, default=1080, help="Listen port")
    parser.add_argument(
        "--method",
        choices=["none", "faketls", "shadowsocks", "domain_fronting", "stegomesh", "hybrid"],
        default="faketls",
        help="Obfuscation method"
    )
    parser.add_argument(
        "--rotation",
        type=int,
        default=300,
        help="Parameter rotation interval (seconds)"
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    server = ObfuscatedSOCKS5Server(
        host=args.host,
        port=args.port,
        obfuscation_method=args.method,
        rotation_interval=args.rotation,
    )

    try:
        await server.start()
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutting down...")
        await server.stop()


if __name__ == "__main__":
    asyncio.run(main())

