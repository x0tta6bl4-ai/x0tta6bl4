"""
Post-Quantum Cryptography Module (Demo Implementation).
Uses AES-GCM for symmetric encryption (simulating Kyber KEM shared secret).
"""
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

class PQCCrypto:
    def __init__(self):
        self.key = os.urandom(32)  # Simulating shared secret from PQC KEM
    
    def encrypt(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def decrypt(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
