"""
Simple XOR-based Obfuscation.
Not cryptographically secure, but sufficient to break simple static signature detection.
"""
import socket
from .base import ObfuscationTransport

class XORSocket(socket.socket):
    """Socket wrapper that applies XOR obfuscation."""
    
    def __init__(self, sock: socket.socket, key: bytes):
        # Copy socket attributes
        self._sock = sock
        self._key = key
        self._key_len = len(key)
        
        # Copy fileno so select() works
        try:
            super().__init__(fileno=sock.fileno())
        except Exception:
            pass  # Can't always inherit from socket directly in wrappers
            
        self.timeout = sock.gettimeout()
        
    def _xor(self, data: bytes) -> bytes:
        return bytes(a ^ self._key[i % self._key_len] for i, a in enumerate(data))
        
    def send(self, data: bytes, flags=0) -> int:
        return self._sock.send(self._xor(data), flags)
        
    def recv(self, bufsize: int, flags=0) -> bytes:
        data = self._sock.recv(bufsize, flags)
        return self._xor(data)
    
    def close(self):
        self._sock.close()
        
    def __getattr__(self, name):
        return getattr(self._sock, name)

class SimpleXORTransport(ObfuscationTransport):
    """Simple XOR Transport Implementation."""
    
    def __init__(self, key: str = "x0tta6bl4"):
        self.key = key.encode('utf-8')
        
    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        return XORSocket(sock, self.key)
        
    def obfuscate(self, data: bytes) -> bytes:
        key_len = len(self.key)
        return bytes(a ^ self.key[i % key_len] for i, a in enumerate(data))
        
    def deobfuscate(self, data: bytes) -> bytes:
        # XOR is symmetric
        return self.obfuscate(data)
