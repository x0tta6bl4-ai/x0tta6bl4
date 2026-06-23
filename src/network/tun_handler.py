"""
x0tta6bl4 TUN Interface Handler
Handles TUN/TAP interface creation and packet I/O for mesh gateway.

Usage:
    from src.network.tun_handler import TUNInterface
    
    tun = TUNInterface("tun0")
    await tun.create()
    packet = await tun.read_packet()
"""

import asyncio
import fcntl
import hashlib
import logging
import os
import struct
import subprocess
import time
from typing import Any, Optional

from src.coordination.events import EventBus, EventType
from src.services.service_event_identity import service_event_identity

logger = logging.getLogger(__name__)

TUN_INTERFACE_SERVICE_NAME = "tun-interface"
TUN_INTERFACE_LAYER = "network_tun_interface_observed_state"
TUN_INTERFACE_CLAIM_BOUNDARY = (
    "Local TUN interface setup evidence only. Events record local ioctl and ip "
    "command outcomes, return codes, duration, and bounded redacted stdout/stderr "
    "metadata with hashed interface/address selectors; they do not prove external "
    "reachability, mesh routing, NAT policy, or production traffic forwarding."
)


def _hash_value(value: Any) -> Optional[str]:
    if value is None:
        return None
    return hashlib.sha256(str(value).encode("utf-8", errors="replace")).hexdigest()


def _output_metadata(value: Any, limit: int = 512) -> dict[str, Any]:
    if value is None:
        encoded = b""
    elif isinstance(value, bytes):
        encoded = value
    else:
        encoded = str(value).encode("utf-8", errors="replace")
    return {
        "bytes": len(encoded),
        "sha256": hashlib.sha256(encoded).hexdigest() if encoded else None,
        "sample_limit": limit,
        "sample_redacted": True,
        "truncated": len(encoded) > limit,
    }


def _identity_metadata() -> dict[str, Any]:
    identity = service_event_identity(service_name=TUN_INTERFACE_SERVICE_NAME)
    return {
        "service_name": TUN_INTERFACE_SERVICE_NAME,
        "layer": TUN_INTERFACE_LAYER,
        "spiffe_id_configured": bool(identity.get("spiffe_id")),
        "did_configured": bool(identity.get("did")),
        "wallet_address_configured": bool(identity.get("wallet_address")),
        "redacted": True,
    }

# TUN/TAP constants
TUNSETIFF = 0x400454ca
TUNSETPERSIST = 0x400454cb
TUNSETOWNER = 0x400454cc
TUNSETGROUP = 0x400454cd

IFF_TUN = 0x0001
IFF_TAP = 0x0002
IFF_NO_PI = 0x1000
IFF_ONE_QUEUE = 0x2000
IFF_VNET_HDR = 0x4000
IFF_TUN_EXCL = 0x8000
IFF_MULTI_QUEUE = 0x0100


class TUNInterface:
    """
    TUN interface handler for x0tta6bl4 mesh gateway.
    
    Provides async I/O for reading/writing packets to a TUN interface.
    Used for transparent traffic routing through mesh network.
    """
    
    def __init__(
        self,
        name: str = "tun0",
        mtu: int = 1500,
        persist: bool = False,
        event_bus: Optional[EventBus] = None,
        event_project_root: str = ".",
        source_agent: str = TUN_INTERFACE_SERVICE_NAME,
        command_timeout_seconds: float = 5.0,
    ):
        """
        Initialize TUN interface handler.
        
        Args:
            name: Interface name (e.g., tun0, tun1)
            mtu: Maximum transmission unit
            persist: Make interface persistent
            event_bus: Optional EventBus for local TUN evidence.
            event_project_root: Project root for lazy EventBus initialization.
            source_agent: EventBus source agent/service name.
            command_timeout_seconds: Timeout for local ip commands.
        """
        self.name = name
        self.mtu = mtu
        self.persist = persist
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self.source_agent = source_agent
        self.command_timeout_seconds = command_timeout_seconds
        self.fd: Optional[int] = None
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._running = False

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        try:
            self.event_bus = EventBus(project_root=self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize TUN EventBus: %s", exc)
            return None

    def _selector_metadata(
        self,
        *,
        local_ip: Optional[str] = None,
        remote_ip: Optional[str] = None,
    ) -> dict[str, Any]:
        metadata: dict[str, Any] = {
            "interface_hash": _hash_value(self.name),
            "interface_redacted": True,
        }
        if local_ip is not None:
            metadata["local_ip_hash"] = _hash_value(local_ip)
            metadata["local_ip_redacted"] = True
        if remote_ip is not None:
            metadata["remote_ip_hash"] = _hash_value(remote_ip)
            metadata["remote_ip_redacted"] = True
        return metadata

    def _publish_observation(
        self,
        *,
        stage: str,
        operation: str,
        status: str,
        source_mode: str,
        start: float,
        returncode: Optional[int] = None,
        parsed_summary: Optional[dict[str, Any]] = None,
        error: Optional[BaseException] = None,
        extra: Optional[dict[str, Any]] = None,
    ) -> Optional[str]:
        bus = self._event_bus_or_none()
        if bus is None:
            return None

        source_agent = getattr(self, "source_agent", TUN_INTERFACE_SERVICE_NAME)
        payload: dict[str, Any] = {
            "component": "network.tun_handler",
            "stage": stage,
            "operation": operation,
            "operation_resource": f"network:tun_interface:{operation}",
            "service_name": source_agent,
            "layer": TUN_INTERFACE_LAYER,
            "identity": _identity_metadata(),
            "status": status,
            "source_mode": source_mode,
            "returncode": returncode,
            "duration_ms": round((time.monotonic() - start) * 1000, 3),
            "read_only": False,
            "observed_state": True,
            "local_actuator": True,
            "safe_actuator": False,
            "payloads_redacted": True,
            "parsed_summary": parsed_summary or {},
            "claim_boundary": TUN_INTERFACE_CLAIM_BOUNDARY,
        }
        if error is not None:
            payload["error"] = {
                "type": type(error).__name__,
                "message_hash": _hash_value(str(error)),
                "message_redacted": True,
            }
        if extra:
            payload.update(extra)

        try:
            event = bus.publish(
                EventType.PIPELINE_STAGE_END,
                source_agent,
                payload,
                priority=5,
            )
            return event.event_id
        except Exception:
            logger.exception("Failed to publish TUN interface evidence")
            return None

    def _run_interface_command(
        self,
        command: list[str],
        *,
        command_shape: list[str],
        operation: str,
        success_stage: str,
        failure_stage: str,
        missing_stage: str,
        timeout_stage: str,
        parsed_summary: dict[str, Any],
        selector_metadata: dict[str, Any],
    ) -> subprocess.CompletedProcess[str]:
        start = time.monotonic()
        extra = {
            "command_shape": command_shape,
            "command_hash": _hash_value(" ".join(command)),
            **selector_metadata,
        }
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.command_timeout_seconds,
            )
        except FileNotFoundError as exc:
            self._publish_observation(
                stage=missing_stage,
                operation=operation,
                status="failure",
                source_mode="subprocess",
                start=start,
                returncode=127,
                parsed_summary={**parsed_summary, "command_available": False},
                error=exc,
                extra={
                    **extra,
                    "stdout_metadata": _output_metadata(None),
                    "stderr_metadata": _output_metadata(None),
                },
            )
            raise
        except subprocess.TimeoutExpired as exc:
            self._publish_observation(
                stage=timeout_stage,
                operation=operation,
                status="failure",
                source_mode="subprocess",
                start=start,
                returncode=124,
                parsed_summary={**parsed_summary, "command_timed_out": True},
                error=exc,
                extra={
                    **extra,
                    "stdout_metadata": _output_metadata(exc.stdout),
                    "stderr_metadata": _output_metadata(exc.stderr),
                },
            )
            raise

        successful = result.returncode == 0
        self._publish_observation(
            stage=success_stage if successful else failure_stage,
            operation=operation,
            status="success" if successful else "failure",
            source_mode="subprocess",
            start=start,
            returncode=result.returncode,
            parsed_summary={**parsed_summary, "command_returned": True},
            extra={
                **extra,
                "stdout_metadata": _output_metadata(result.stdout),
                "stderr_metadata": _output_metadata(result.stderr),
            },
        )
        if not successful:
            raise subprocess.CalledProcessError(
                result.returncode,
                command_shape,
                output=result.stdout,
                stderr=result.stderr,
            )
        return result
        
    @property
    def is_up(self) -> bool:
        """Check if interface is up."""
        return self.fd is not None and self._running
    
    async def create(self) -> bool:
        """
        Create and configure TUN interface.
        
        Returns:
            True if successful, False otherwise
        """
        op_start = time.monotonic()
        try:
            # Open /dev/net/tun
            tun_path = "/dev/net/tun"
            if not os.path.exists(tun_path):
                # Try to create /dev/net directory
                os.makedirs("/dev/net", exist_ok=True)
                # Create device node (requires root)
                os.mknod(tun_path, 0o666 | 0o20000, (10, 200))  # char device 10,200
            
            self.fd = os.open(tun_path, os.O_RDWR | os.O_NONBLOCK)
            
            # Create interface using ioctl
            # Pack interface name and flags
            ifr = struct.pack(
                "16sH", 
                self.name.encode("utf-8")[:15], 
                IFF_TUN | IFF_NO_PI
            )
            
            fcntl.ioctl(self.fd, TUNSETIFF, ifr)
            
            # Make persistent if requested
            if self.persist:
                fcntl.ioctl(self.fd, TUNSETPERSIST, 1)
            
            # Configure interface using system commands
            await self._configure_interface()
            
            # Create asyncio stream reader
            loop = asyncio.get_event_loop()
            self._reader = asyncio.StreamReader()
            
            # Create protocol and transport
            protocol = asyncio.StreamReaderProtocol(self._reader)
            transport, _ = await loop.create_connection(
                lambda: protocol,
                sock=self._create_socket()
            )
            
            self._writer = asyncio.StreamWriter(
                transport, protocol, self._reader, loop
            )
            
            self._running = True
            self._publish_observation(
                stage="tun_interface_create_completed",
                operation="create",
                status="success",
                source_mode="kernel_ioctl",
                start=op_start,
                returncode=0,
                parsed_summary={
                    "interface_created": True,
                    "mtu": self.mtu,
                    "persist": self.persist,
                },
                extra=self._selector_metadata(),
            )
            logger.info("TUN interface created successfully")
            return True
            
        except PermissionError as exc:
            self._publish_observation(
                stage="tun_interface_create_permission_denied",
                operation="create",
                status="failure",
                source_mode="kernel_ioctl",
                start=op_start,
                returncode=13,
                parsed_summary={
                    "interface_created": False,
                    "mtu": self.mtu,
                    "persist": self.persist,
                },
                error=exc,
                extra=self._selector_metadata(),
            )
            logger.error("Permission denied. Run as root or with CAP_NET_ADMIN.")
            return False
        except Exception as e:
            self._publish_observation(
                stage="tun_interface_create_failed",
                operation="create",
                status="failure",
                source_mode="kernel_ioctl",
                start=op_start,
                returncode=1,
                parsed_summary={
                    "interface_created": False,
                    "mtu": self.mtu,
                    "persist": self.persist,
                },
                error=e,
                extra=self._selector_metadata(),
            )
            logger.error("Failed to create TUN interface; details are redacted in EventBus evidence")
            if self.fd is not None:
                os.close(self.fd)
                self.fd = None
            return False
    
    def _create_socket(self) -> int:
        """Create socket from file descriptor."""
        import socket
        sock = socket.socket(fileno=self.fd, family=socket.AF_UNSPEC)
        sock.setblocking(False)
        return sock.detach()
    
    async def _configure_interface(self) -> None:
        """Configure TUN interface using system commands."""
        # Set MTU
        self._run_interface_command(
            ["ip", "link", "set", "dev", self.name, "mtu", str(self.mtu)],
            command_shape=[
                "ip",
                "link",
                "set",
                "dev",
                "<interface>",
                "mtu",
                "<mtu>",
            ],
            operation="configure_mtu",
            success_stage="tun_interface_mtu_configured",
            failure_stage="tun_interface_mtu_failed",
            missing_stage="tun_interface_mtu_command_missing",
            timeout_stage="tun_interface_mtu_timeout",
            parsed_summary={"mtu": self.mtu},
            selector_metadata=self._selector_metadata(),
        )
        
        # Bring up interface
        self._run_interface_command(
            ["ip", "link", "set", "dev", self.name, "up"],
            command_shape=[
                "ip",
                "link",
                "set",
                "dev",
                "<interface>",
                "up",
            ],
            operation="configure_link_up",
            success_stage="tun_interface_link_up_configured",
            failure_stage="tun_interface_link_up_failed",
            missing_stage="tun_interface_link_up_command_missing",
            timeout_stage="tun_interface_link_up_timeout",
            parsed_summary={"link_up_requested": True},
            selector_metadata=self._selector_metadata(),
        )
        
        logger.debug("Configured TUN interface with MTU %s", self.mtu)
    
    async def set_address(self, local_ip: str, remote_ip: str = None) -> bool:
        """
        Set IP address on TUN interface.
        
        Args:
            local_ip: Local IP address (e.g., "10.0.0.1/32")
            remote_ip: Remote/peer IP address for point-to-point
            
        Returns:
            True if successful
        """
        try:
            if remote_ip:
                # Point-to-point configuration
                self._run_interface_command(
                    ["ip", "addr", "add", local_ip, "peer", remote_ip, "dev", self.name],
                    command_shape=[
                        "ip",
                        "addr",
                        "add",
                        "<local_ip>",
                        "peer",
                        "<remote_ip>",
                        "dev",
                        "<interface>",
                    ],
                    operation="set_address",
                    success_stage="tun_interface_address_configured",
                    failure_stage="tun_interface_address_failed",
                    missing_stage="tun_interface_address_command_missing",
                    timeout_stage="tun_interface_address_timeout",
                    parsed_summary={"peer_configured": True},
                    selector_metadata=self._selector_metadata(
                        local_ip=local_ip,
                        remote_ip=remote_ip,
                    ),
                )
            else:
                # Simple address assignment
                self._run_interface_command(
                    ["ip", "addr", "add", local_ip, "dev", self.name],
                    command_shape=[
                        "ip",
                        "addr",
                        "add",
                        "<local_ip>",
                        "dev",
                        "<interface>",
                    ],
                    operation="set_address",
                    success_stage="tun_interface_address_configured",
                    failure_stage="tun_interface_address_failed",
                    missing_stage="tun_interface_address_command_missing",
                    timeout_stage="tun_interface_address_timeout",
                    parsed_summary={"peer_configured": False},
                    selector_metadata=self._selector_metadata(local_ip=local_ip),
                )
            
            logger.info("Set address on TUN interface")
            return True
        except (
            subprocess.CalledProcessError,
            FileNotFoundError,
            subprocess.TimeoutExpired,
        ):
            logger.error("Failed to set TUN address; details are redacted in EventBus evidence")
            return False
    
    async def read_packet(self) -> Optional[bytes]:
        """
        Read a packet from TUN interface.
        
        Returns:
            Raw IP packet data, or None if no data available
        """
        if not self._reader or not self._running:
            return None
        
        try:
            # Read raw packet (no packet info header due to IFF_NO_PI)
            data = await self._reader.read(self.mtu)
            return data if data else None
        except asyncio.CancelledError:
            return None
        except Exception as e:
            logger.debug(f"Read error: {e}")
            return None
    
    async def write_packet(self, packet: bytes) -> bool:
        """
        Write a packet to TUN interface.
        
        Args:
            packet: Raw IP packet data
            
        Returns:
            True if successful
        """
        if not self._writer or not self._running:
            return False
        
        try:
            self._writer.write(packet)
            await self._writer.drain()
            return True
        except Exception as e:
            logger.debug(f"Write error: {e}")
            return False
    
    def read_packet_sync(self) -> Optional[bytes]:
        """
        Synchronously read a packet (for non-async contexts).
        
        Returns:
            Raw IP packet data, or None if no data available
        """
        if self.fd is None:
            return None
        
        try:
            data = os.read(self.fd, self.mtu)
            return data if data else None
        except BlockingIOError:
            return None
        except Exception as e:
            logger.debug(f"Sync read error: {e}")
            return None
    
    def write_packet_sync(self, packet: bytes) -> bool:
        """
        Synchronously write a packet (for non-async contexts).
        
        Args:
            packet: Raw IP packet data
            
        Returns:
            True if successful
        """
        if self.fd is None:
            return False
        
        try:
            os.write(self.fd, packet)
            return True
        except Exception as e:
            logger.debug(f"Sync write error: {e}")
            return False
    
    def close(self) -> None:
        """Close TUN interface."""
        self._running = False
        
        if self._writer:
            try:
                self._writer.close()
            except Exception:
                pass
            self._writer = None
        
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None
        
        logger.info(f"TUN interface {self.name} closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False


class IPPacketParser:
    """Parser for IP packets read from TUN interface."""
    
    @staticmethod
    def parse(packet: bytes) -> Optional[dict]:
        """
        Parse IP packet header.
        
        Args:
            packet: Raw IP packet bytes
            
        Returns:
            Dictionary with packet info, or None if invalid
        """
        if len(packet) < 20:
            return None
        
        try:
            version = packet[0] >> 4
            header_len = (packet[0] & 0x0F) * 4
            total_len = (packet[2] << 8) | packet[3]
            protocol = packet[9]
            ttl = packet[8]
            
            import socket
            
            src_ip = socket.inet_ntoa(packet[12:16])
            dst_ip = socket.inet_ntoa(packet[16:20])
            
            return {
                "version": version,
                "header_len": header_len,
                "total_len": total_len,
                "protocol": protocol,
                "ttl": ttl,
                "src_ip": src_ip,
                "dst_ip": dst_ip,
                "payload": packet[header_len:],
                "raw": packet
            }
        except Exception:
            return None
    
    @staticmethod
    def get_tcp_info(payload: bytes) -> Optional[dict]:
        """Parse TCP header from IP payload."""
        if len(payload) < 20:
            return None
        
        try:
            src_port = (payload[0] << 8) | payload[1]
            dst_port = (payload[2] << 8) | payload[3]
            seq_num = int.from_bytes(payload[4:8], "big")
            ack_num = int.from_bytes(payload[8:12], "big")
            flags = payload[13]
            
            return {
                "src_port": src_port,
                "dst_port": dst_port,
                "seq_num": seq_num,
                "ack_num": ack_num,
                "flags": {
                    "fin": bool(flags & 0x01),
                    "syn": bool(flags & 0x02),
                    "rst": bool(flags & 0x04),
                    "psh": bool(flags & 0x08),
                    "ack": bool(flags & 0x10),
                    "urg": bool(flags & 0x20),
                },
                "payload": payload[20:],
            }
        except Exception:
            return None
    
    @staticmethod
    def get_udp_info(payload: bytes) -> Optional[dict]:
        """Parse UDP header from IP payload."""
        if len(payload) < 8:
            return None
        
        try:
            src_port = (payload[0] << 8) | payload[1]
            dst_port = (payload[2] << 8) | payload[3]
            length = (payload[4] << 8) | payload[5]
            
            return {
                "src_port": src_port,
                "dst_port": dst_port,
                "length": length,
                "payload": payload[8:],
            }
        except Exception:
            return None


# Protocol constants
IPPROTO_TCP = 6
IPPROTO_UDP = 17
IPPROTO_ICMP = 1
IPPROTO_ICMPV6 = 58


async def test_tun_interface():
    """Test TUN interface creation."""
    logging.basicConfig(level=logging.DEBUG)
    
    tun = TUNInterface("tun0")
    
    try:
        if await tun.create():
            print(f"TUN interface {tun.name} created")
            
            # Set address
            await tun.set_address("10.0.0.1/32", "10.0.0.2")
            
            # Read packets
            print("Reading packets (Ctrl+C to stop)...")
            while True:
                packet = await tun.read_packet()
                if packet:
                    parsed = IPPacketParser.parse(packet)
                    if parsed:
                        print(f"Packet: {parsed['src_ip']} -> {parsed['dst_ip']} (proto: {parsed['protocol']})")
                await asyncio.sleep(0.01)
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        tun.close()


if __name__ == "__main__":
    asyncio.run(test_tun_interface())
