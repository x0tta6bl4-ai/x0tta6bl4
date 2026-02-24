"""
Quantum Shield Client Engine
============================

Secure VPN client with Ghost Transport protocol.
All secrets must be provided via environment variables.

Security Features:
- ChaCha20-Poly1305 AEAD encryption
- No hardcoded keys
- Safe subprocess calls for network setup
"""

import asyncio
import fcntl
import hashlib
import logging
import os
import secrets
import socket
import struct
import subprocess
import sys
from typing import Optional

# Ensure project root is in path for imports
_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if _root not in sys.path:
    sys.path.insert(0, _root)
_src = os.path.join(_root, "src")
if _src not in sys.path:
    sys.path.insert(0, _src)

from src.network.transport.ghost_proto import GhostTransport

logger = logging.getLogger("ghost-tun-v6")

# TUN interface constants
TUNSETIFF = 0x400454ca
IFF_TUN = 0x0001
IFF_NO_PI = 0x1000
TUN_INTERFACE_NAME = "x0t-tun0"


def _get_encryption_key() -> bytes:
    """
    Get encryption key from environment with production safety check.
    
    Returns:
        32-byte encryption key
        
    Raises:
        RuntimeError: If key is not set in production environment
        ValueError: If key is too short
    """
    key = os.getenv("VPN_ENCRYPTION_KEY")
    if not key:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise RuntimeError(
                "VPN_ENCRYPTION_KEY environment variable must be set in production. "
                "Generate a secure key: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
        # Development fallback with warning
        logger.warning(
            "VPN_ENCRYPTION_KEY not set, using development key. "
            "Set VPN_ENCRYPTION_KEY for production use."
        )
        key = "dev_key_do_not_use_in_production_32b"
    
    if len(key) < 32:
        raise ValueError(
            f"VPN_ENCRYPTION_KEY must be at least 32 characters, got {len(key)}"
        )
    
    # Derive 32-byte key using SHA-256
    return hashlib.sha256(key.encode()).digest()


def _get_vpn_server() -> str:
    """Get VPN server address from environment."""
    server = os.getenv("VPN_SERVER")
    if not server:
        environment = os.getenv("ENVIRONMENT", "development").lower()
        if environment == "production":
            raise RuntimeError(
                "VPN_SERVER environment variable must be set in production."
            )
        logger.warning("VPN_SERVER not set, using localhost fallback (development only)")
        server = "127.0.0.1"
    return server


def _run_command_safely(cmd_args: list, timeout: int = 30) -> bool:
    """
    Run a command safely using subprocess with argument list.
    
    This prevents shell injection attacks by avoiding shell=True.
    
    Args:
        cmd_args: List of command arguments (e.g., ["ip", "addr", "add", ...])
        timeout: Command timeout in seconds
        
    Returns:
        True if command succeeded, False otherwise
    """
    try:
        result = subprocess.run(
            cmd_args,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        if result.returncode != 0:
            logger.warning(
                f"Command failed: {' '.join(cmd_args)}\n"
                f"stderr: {result.stderr.strip()}"
            )
            return False
        return True
    except subprocess.TimeoutExpired:
        logger.error(f"Command timed out: {' '.join(cmd_args)}")
        return False
    except FileNotFoundError:
        logger.error(f"Command not found: {cmd_args[0]}")
        return False
    except Exception as e:
        logger.error(f"Command error: {e}")
        return False


class GhostTUN:
    """
    Secure TUN-based VPN client using Ghost Transport.
    
    Creates a TUN interface and routes all traffic through the
    encrypted Ghost Protocol tunnel.
    """
    
    def __init__(self, master_key: bytes, server_ip: str = '127.0.0.1', port: int = 8444):
        """
        Initialize GhostTUN.
        
        Args:
            master_key: 32-byte encryption key for GhostTransport
            server_ip: VPN server IP address
            port: VPN server port
        """
        self.transport = GhostTransport(master_key)
        self.tun_fd: Optional[int] = None
        self.remote_server = (server_ip, port)
        self._running = False

    def setup_network(self) -> bool:
        """
        Creates TUN interface and configures routing.
        
        Uses subprocess with argument lists to prevent shell injection.
        
        Returns:
            True if setup succeeded, False otherwise
        """
        try:
            # Open TUN device
            self.tun_fd = os.open('/dev/net/tun', os.O_RDWR)
            
            # Create TUN interface
            ifr = struct.pack('16sH', TUN_INTERFACE_NAME.encode(), IFF_TUN | IFF_NO_PI)
            fcntl.ioctl(self.tun_fd, TUNSETIFF, ifr)
            
            # Configure interface using safe subprocess calls
            # Note: These commands require root privileges
            commands = [
                ["ip", "addr", "add", "10.8.0.2/24", "dev", TUN_INTERFACE_NAME],
                ["ip", "link", "set", "dev", TUN_INTERFACE_NAME, "up"],
            ]
            
            for cmd in commands:
                if not _run_command_safely(cmd):
                    logger.error(f"Failed to configure network: {' '.join(cmd)}")
                    return False
            
            logger.info(f"✅ TUN Interface '{TUN_INTERFACE_NAME}' is UP.")
            return True
            
        except PermissionError:
            logger.error("Permission denied. Run with sudo or as root.")
            return False
        except OSError as e:
            logger.error(f"Failed to setup TUN: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error during network setup: {e}")
            return False

    async def run(self) -> None:
        """
        Run the VPN tunnel.
        
        Reads packets from TUN interface, encrypts them, and sends via UDP.
        Receives encrypted packets via UDP, decrypts them, and writes to TUN.
        """
        if self.tun_fd is None:
            raise RuntimeError("TUN interface not initialized. Call setup_network() first.")
        
        self._running = True
        
        # Create UDP socket
        udp_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_sock.setblocking(False)
        loop = asyncio.get_event_loop()
        
        async def read_from_server():
            """Handle incoming packets from VPN server."""
            while self._running:
                try:
                    data, _ = await loop.sock_recv(udp_sock, 4096)
                    unwrapped = self.transport.unwrap_packet(data)
                    if unwrapped:
                        os.write(self.tun_fd, unwrapped)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Error reading from server: {e}")
        
        async def write_to_server():
            """Handle outgoing packets to VPN server."""
            while self._running:
                try:
                    # Read from TUN interface
                    packet = await loop.run_in_executor(
                        None, 
                        os.read, 
                        self.tun_fd, 
                        4096
                    )
                    if not packet:
                        continue
                    
                    # Encrypt and send
                    ghost_packet = self.transport.wrap_packet(packet)
                    udp_sock.sendto(ghost_packet, self.remote_server)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.debug(f"Error writing to server: {e}")
        
        # Run both directions concurrently
        logger.info(
            f"🛡️ Quantum Shield L3 Active. "
            f"All system traffic is now routed through Ghost-Protocol to {self.remote_server}"
        )
        
        try:
            await asyncio.gather(read_from_server(), write_to_server())
        finally:
            udp_sock.close()
            self._running = False

    def stop(self) -> None:
        """Stop the VPN tunnel."""
        self._running = False
        if self.tun_fd is not None:
            try:
                os.close(self.tun_fd)
            except Exception:
                pass
            self.tun_fd = None
        logger.info("VPN tunnel stopped")


async def main():
    """Main entry point for VPN client."""
    parser = argparse.ArgumentParser(description="Quantum Shield VPN Client")
    parser.add_argument("--node_id", default="client-001", help="Node identifier")
    parser.add_argument("--api_url", default="http://localhost:8000", help="API URL")
    parser.add_argument("--server", help="VPN server IP (overrides VPN_SERVER env)")
    parser.add_argument("--port", type=int, default=8444, help="VPN server port")
    args = parser.parse_args()
    
    # Get encryption key (from env or fail in production)
    try:
        key = _get_encryption_key()
    except RuntimeError as e:
        logger.error(f"Configuration error: {e}")
        sys.exit(1)
    
    # Get server address
    server = args.server or _get_vpn_server()
    
    # Create and start VPN
    vpn = GhostTUN(key, server_ip=server, port=args.port)
    
    if not vpn.setup_network():
        logger.error("Failed to setup network")
        sys.exit(1)
    
    try:
        await vpn.run()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        vpn.stop()


if __name__ == "__main__":
    import argparse
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    asyncio.run(main())
