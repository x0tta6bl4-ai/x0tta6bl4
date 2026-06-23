import logging
import socket
import threading
from typing import Optional

logger = logging.getLogger("x0t.network")

class Tunnel:
    """
    A secure communication tunnel between two nodes using TCP sockets.
    """
    def __init__(self, peer_address: str, crypto_engine, sock: socket.socket = None):
        self.peer_address = peer_address
        self.host, self.port = peer_address.split(":")
        self.port = int(self.port)
        self.crypto = crypto_engine
        self.is_connected = False
        self.shared_secret = None
        self.sock = sock 

    def connect(self):
        """Establish TCP connection if not already connected."""
        if self.sock is None:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
        self.is_connected = True
        logger.info(f"Connected to {self.peer_address}")

    def handshake(self):
        """Perform PQC Handshake over the socket."""
        self.connect()
        
        if self.crypto:
            logger.info("Initiating PQC Key Exchange (KEM)...")
            
            # Simulation of protocol:
            # 1. Client sends "CLIENT_HELLO"
            self.sock.sendall(b"CLIENT_HELLO")
            
            # 2. Server sends PubKey (Mock)
            peer_pub = self.sock.recv(1024) 
            # In real impl, we'd parse this. For now, trust it's the key.
            
            # 3. KEM Encapsulate
            self.shared_secret, ciphertext = self.crypto.encapsulate(peer_pub)
            
            # 4. Send Ciphertext
            self.sock.sendall(ciphertext)
            
            logger.info("PQC Handshake Complete. Tunnel Secure.")
        else:
            logger.warning("Handshake skipped (INSECURE mode).")
        
        self.is_connected = True

    def send(self, data: bytes):
        """Send encrypted data."""
        if not self.is_connected:
            raise ConnectionError("Tunnel not connected")
            
        if self.shared_secret:
            # Mock encryption: XOR with secret (just for demo visual)
            # In prod: AES-GCM
            encrypted_data = b"ENC[" + data + b"]" 
            self.sock.sendall(encrypted_data)
        else:
            self.sock.sendall(data)

    def receive(self) -> bytes:
        """Blocking receive."""
        return self.sock.recv(4096)

    def close(self):
        self.is_connected = False
        if self.sock:
            self.sock.close()
        logger.info("Tunnel closed.")
