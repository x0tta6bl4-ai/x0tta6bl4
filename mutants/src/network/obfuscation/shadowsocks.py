"""
Shadowsocks Transport for x0tta6bl4 Mesh.
Implements a Shadowsocks-compatible obfuscation layer (AEAD ChaCha20-Poly1305).
"""
import os
import socket
import struct
import secrets
from typing import Optional
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from .base import ObfuscationTransport

class ShadowsocksSocket(socket.socket):
    """Socket wrapper that applies Shadowsocks AEAD encryption."""
    
    def __init__(self, sock: socket.socket, transport: 'ShadowsocksTransport'):
        self._sock = sock
        self._transport = transport
        self._salt_sent = False
        self._salt_received = False
        self._buffer = b""
        
        try:
            super().__init__(fileno=sock.fileno())
        except Exception:
            pass
        self.timeout = sock.gettimeout()

    def send(self, data: bytes, flags=0) -> int:
        # If this is the first write, we need to prepend the salt
        prefix = b""
        if not self._salt_sent:
            # We should generate a salt for this session if not already done?
            # The transport.obfuscate method handles stateless packet encryption.
            # For stream socket, we need state.
            # Let's assume transport can generate a header for us.
            # Actually, in Shadowsocks, the salt is the first thing sent.
            # But transport.obfuscate creates a full packet (Salt + Payload).
            # If we use transport.obfuscate here, it will send a Salt every time?
            # Standard Shadowsocks sends Salt ONCE per connection.
            # So we should handle state here or in transport.
            
            # We will use a simplified approach:
            # wrapper treats each send() as a potential separate message if we used 'obfuscate' directly.
            # But for a socket wrapper, we want a stream.
            # Let's delegate to transport to create a 'session' object or similar?
            # For MVP, let's just generate a salt for this connection.
            self._session_salt = secrets.token_bytes(32) # ChaCha20 salt size
            self._salt_sent = True
            prefix = self._session_salt
            
        # Encrypt payload using session salt
        # We need a derived key for this session
        key = self._transport.derive_key(self._session_salt)
        cipher = ChaCha20Poly1305(key)
        
        # Max chunk size for Shadowsocks is usually 0x3FFF (16KB)
        # We'll just encrypt the whole data as one chunk for simplicity if it's small
        # Real SS splits large data.
        
        payload_len = len(data)
        len_bytes = struct.pack("!H", payload_len)
        
        # Encrypt length (AEAD)
        # Nonce is usually sequence number? 
        # Shadowsocks AEAD uses a specific nonce generation.
        # [salt] [encrypted length] [tag] [encrypted payload] [tag]
        # This is getting complex for a quick MVP without a library.
        
        # ALTERNATIVE: Use the stateless 'obfuscate' method which packs Salt+Data every time.
        # This acts more like UDP or independent messages. 
        # For 'NodeManager' heartbeats (stateless JSON), this is perfect.
        # For TCP streams, it adds overhead (32 bytes salt per packet).
        # Given our current use case (Mesh control plane), stateless is safer/easier.
        
        encrypted_packet = self._transport.obfuscate(data)
        return self._sock.send(encrypted_packet, flags)

    def recv(self, bufsize: int, flags=0) -> bytes:
        # Read from socket
        data = self._sock.recv(bufsize, flags)
        if not data: return b""
        
        # Deobfuscate (expects Salt+Payload)
        try:
            return self._transport.deobfuscate(data)
        except Exception:
            return b"" # Decryption failed

    def __getattr__(self, name):
        return getattr(self._sock, name)


class ShadowsocksTransport(ObfuscationTransport):
    """
    Shadowsocks Transport (Simplified AEAD).
    Uses ChaCha20-Poly1305.
    Packet Format: [Salt (32)] [Nonce (12)] [Tag (16)] [Encrypted Payload]
    Note: This is a simplified variant for internal mesh usage, slightly different from standard SS 
    to avoid implementing the full Chunk-based streaming state machine in Python.
    It treats every obfuscate() call as a discrete message.
    """
    
    def __init__(self, password: str = "x0tta6bl4"):
        self.password = password.encode('utf-8')
        # Pre-derive master key from password? 
        # SS usually derives per-session key from (Master Key + Salt).
        # Master Key is derived from Password.
        self.master_key = self._kdf(self.password, b"ss-subkey", 32)
        
    def _kdf(self, key_material: bytes, salt: bytes, length: int) -> bytes:
        hkdf = HKDF(
            algorithm=hashes.SHA1(),
            length=length,
            salt=salt,
            info=b"ss-subkey"
        )
        return hkdf.derive(key_material)

    def derive_session_key(self, salt: bytes) -> bytes:
        """Derive session key from master key and salt."""
        return self._kdf(self.master_key, salt, 32)

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return ShadowsocksSocket(sock, self)
        
    def obfuscate(self, data: bytes) -> bytes:
        """
        Encrypts data into a Shadowsocks-like packet.
        Format: [Salt 32] [Nonce 12] [Tag 16] [Ciphertext]
        """
        salt = secrets.token_bytes(32)
        session_key = self.derive_session_key(salt)
        cipher = ChaCha20Poly1305(session_key)
        
        nonce = secrets.token_bytes(12)
        
        # ChaCha20Poly1305 encrypt returns ciphertext + tag appended? 
        # No, usually just ciphertext with tag.
        # cryptography's encrypt(nonce, data, aad) returns ciphertext + tag (16 bytes).
        ciphertext_with_tag = cipher.encrypt(nonce, data, None)
        
        return salt + nonce + ciphertext_with_tag
        
    def deobfuscate(self, data: bytes) -> bytes:
        """Decrypts packet."""
        if len(data) < (32 + 12 + 16):
            raise ValueError("Data too short for Shadowsocks packet")
            
        salt = data[:32]
        nonce = data[32:44]
        ciphertext_with_tag = data[44:]
        
        session_key = self.derive_session_key(salt)
        cipher = ChaCha20Poly1305(session_key)
        
        return cipher.decrypt(nonce, ciphertext_with_tag, None)
