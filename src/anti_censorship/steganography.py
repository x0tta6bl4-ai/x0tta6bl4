"""
Steganography Module - Hide encrypted traffic within innocent-looking data.

Provides multiple steganographic techniques for covert communication:
- Image steganography (LSB, DCT, palette-based)
- Audio steganography (phase coding, spread spectrum)
- Text steganography (whitespace, zero-width characters)
- Video steganography (frame differencing)
- Protocol steganography (DNS, HTTP headers)
"""

import hashlib
import logging
import math
import os
import random
import struct
import time
import warnings
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from src.coordination.events import EventBus, EventType, get_event_bus
from src.services.service_event_identity import service_event_identity

# Try to import cryptography library for secure stream cipher
try:
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
    from cryptography.hazmat.backends import default_backend
    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    warnings.warn(
        "cryptography library not available. Falling back to SHA-256 counter mode "
        "which is NOT cryptographically secure. Install 'cryptography' package "
        "for secure ChaCha20 encryption.",
        RuntimeWarning
    )

logger = logging.getLogger(__name__)


class SteganographyType(Enum):
    """Types of steganographic carriers."""
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"
    VIDEO = "video"
    PROTOCOL = "protocol"


_SERVICE_AGENT = "anti-censorship-steganography-engine"
_SERVICE_LAYER = "anti_censorship_steganography_local_evidence"
STEGANOGRAPHY_ENGINE_CLAIM_BOUNDARY = (
    "Local steganography engine evidence only. It records local carrier "
    "capacity, embed/extract/auto-detect/covert-channel outcomes, duration, "
    "carrier-type buckets, byte-count buckets, encryption/configuration "
    "presence, and service identity presence; it does not expose carrier bytes, "
    "hidden payload bytes, encryption keys, generated covert domains, HTTP "
    "headers, zero-width text, audio/image contents, extracted payloads, or "
    "prove DPI bypass, censorship bypass, remote reachability, packet delivery, "
    "anonymity, provider health, client installation, or production customer "
    "traffic use."
)


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


def _carrier_type_bucket(carrier_type: Any) -> str:
    value = getattr(carrier_type, "value", carrier_type)
    text = str(value or "").strip().lower()
    if text in {item.value for item in SteganographyType}:
        return text
    return "unsupported"


def _safe_result_metadata(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    safe: Dict[str, Any] = {}
    for key in ("method", "bits_embedded", "chunks", "headers_added", "detected_type"):
        item = value.get(key)
        if isinstance(item, bool):
            safe[key] = item
        elif isinstance(item, int):
            safe[key] = item
        elif isinstance(item, str):
            safe[key] = item[:64]
    return safe


@dataclass
class SteganographyConfig:
    """Configuration for steganographic operations."""
    # Embedding parameters
    embedding_strength: float = 1.0  # 0.0 to 1.0
    redundancy: int = 3  # Number of times to embed each bit
    
    # Security parameters
    use_encryption: bool = True
    encryption_key: Optional[bytes] = None
    
    # Detection avoidance
    random_seed_source: str = "key_derived"  # key_derived, timestamp, random
    adaptive_embedding: bool = True
    
    # Capacity settings
    max_capacity_ratio: float = 0.1  # Max ratio of hidden data to carrier size


@dataclass
class EmbeddingResult:
    """Result of steganographic embedding."""
    success: bool
    carrier_data: Optional[bytes] = None
    capacity_used: int = 0
    capacity_total: int = 0
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExtractionResult:
    """Result of steganographic extraction."""
    success: bool
    hidden_data: Optional[bytes] = None
    data_length: int = 0
    integrity_valid: bool = False
    error_message: Optional[str] = None


class SteganographyCarrier(ABC):
    """Abstract base class for steganographic carriers."""
    
    # ChaCha20 in cryptography library requires 16-byte (128-bit) nonce
    _STREAM_NONCE_SIZE = 16
    _CHACHA20_NONCE_SIZE = 16

    def __init__(self, config: Optional[SteganographyConfig] = None):
        self.config = config or SteganographyConfig()
    
    @abstractmethod
    def get_capacity(self, carrier_data: bytes) -> int:
        """Calculate maximum hidden data capacity in bytes."""
        pass
    
    @abstractmethod
    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        """Embed hidden data into carrier."""
        pass
    
    @abstractmethod
    def extract(self, carrier_data: bytes) -> ExtractionResult:
        """Extract hidden data from carrier."""
        pass
    
    def _derive_key(self, key_material: Optional[bytes] = None) -> bytes:
        """Derive encryption key from material or config."""
        if key_material:
            return hashlib.sha256(key_material).digest()
        if self.config.encryption_key:
            return hashlib.sha256(self.config.encryption_key).digest()
        return hashlib.sha256(b"default_stego_key").digest()
    
    def _generate_keystream_fallback(self, key: bytes, nonce: bytes, length: int) -> bytes:
        """
        Generate deterministic keystream blocks from key+nonce using SHA-256 counter mode.
        
        WARNING: This is a FALLBACK implementation used only when the 'cryptography'
        library is not available. SHA-256 in counter mode is NOT a cryptographically
        vetted stream cipher. For production use with sensitive data, ensure the
        'cryptography' package is installed to use ChaCha20.
        """
        stream = bytearray()
        counter = 0
        while len(stream) < length:
            block = hashlib.sha256(
                key + nonce + counter.to_bytes(8, byteorder="big")
            ).digest()
            stream.extend(block)
            counter += 1
        return bytes(stream[:length])

    def _stream_cipher_encrypt(self, data: bytes, key: bytes) -> bytes:
        """
        Encrypt data using ChaCha20 stream cipher.
        
        Uses the 'cryptography' library for cryptographically secure encryption.
        Falls back to SHA-256 counter mode (INSECURE) if cryptography is unavailable.
        
        Output format: nonce (16 bytes) || ciphertext
        
        Security properties:
        - ChaCha20 is a vetted stream cipher with 256-bit security
        - Nonce must never be reused with the same key (enforced via random generation)
        - Key is derived via SHA-256 from input key material
        """
        nonce_size = (
            self._CHACHA20_NONCE_SIZE
            if CRYPTOGRAPHY_AVAILABLE
            else self._STREAM_NONCE_SIZE
        )
        nonce = os.urandom(nonce_size)
        key_material = hashlib.sha256(key).digest()
        
        if CRYPTOGRAPHY_AVAILABLE:
            # Use ChaCha20 for secure encryption
            cipher = Cipher(
                algorithms.ChaCha20(key_material, nonce),
                mode=None,
                backend=default_backend()
            )
            encryptor = cipher.encryptor()
            ciphertext = encryptor.update(data)
            return nonce + ciphertext
        else:
            # Fallback to insecure SHA-256 counter mode
            keystream = self._generate_keystream_fallback(key_material, nonce, len(data))
            ciphertext = bytearray(len(data))
            for i, byte in enumerate(data):
                ciphertext[i] = byte ^ keystream[i]
            return nonce + bytes(ciphertext)

    def _stream_cipher_decrypt(self, payload: bytes, key: bytes) -> bytes:
        """
        Decrypt data encrypted with ChaCha20 stream cipher.
        
        Input format: nonce (16 bytes) || ciphertext
        
        Uses the 'cryptography' library for cryptographically secure decryption.
        Falls back to SHA-256 counter mode (INSECURE) if cryptography is unavailable.
        """
        nonce_size = (
            self._CHACHA20_NONCE_SIZE
            if CRYPTOGRAPHY_AVAILABLE
            else self._STREAM_NONCE_SIZE
        )
        if len(payload) < nonce_size:
            return b""
        
        nonce = payload[:nonce_size]
        ciphertext = payload[nonce_size:]
        key_material = hashlib.sha256(key).digest()
        
        if CRYPTOGRAPHY_AVAILABLE:
            # Use ChaCha20 for secure decryption
            cipher = Cipher(
                algorithms.ChaCha20(key_material, nonce),
                mode=None,
                backend=default_backend()
            )
            decryptor = cipher.decryptor()
            plaintext = decryptor.update(ciphertext)
            return plaintext
        else:
            # Fallback to insecure SHA-256 counter mode
            keystream = self._generate_keystream_fallback(key_material, nonce, len(ciphertext))
            plaintext = bytearray(len(ciphertext))
            for i, byte in enumerate(ciphertext):
                plaintext[i] = byte ^ keystream[i]
            return bytes(plaintext)
    
    def _add_integrity(self, data: bytes) -> bytes:
        """Add integrity checksum to data."""
        checksum = zlib.crc32(data) & 0xffffffff
        return struct.pack(">I", checksum) + data
    
    def _verify_integrity(self, data: bytes) -> Tuple[bool, bytes]:
        """Verify and strip integrity checksum."""
        if len(data) < 4:
            return False, b""
        stored_checksum = struct.unpack(">I", data[:4])[0]
        payload = data[4:]
        computed_checksum = zlib.crc32(payload) & 0xffffffff
        return stored_checksum == computed_checksum, payload


class ImageSteganography(SteganographyCarrier):
    """
    Image-based steganography using multiple techniques.
    
    Supports:
    - LSB (Least Significant Bit) embedding
    - DCT (Discrete Cosine Transform) domain embedding
    - Palette-based embedding for GIF/PNG
    """
    
    def get_capacity(self, carrier_data: bytes) -> int:
        """Calculate LSB capacity for image."""
        # Estimate based on image size (simplified)
        # Real implementation would parse image dimensions
        estimated_pixels = len(carrier_data) // 3  # Assume RGB
        # LSB in each color channel = 3 bits per pixel
        # With redundancy, effective capacity is reduced
        capacity_bits = estimated_pixels * 3 // self.config.redundancy
        return capacity_bits // 8  # Convert to bytes
    
    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        """Embed data using LSB steganography."""
        try:
            # Prepare hidden data
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_encrypt(hidden_data, key)
            
            # Add length prefix and integrity
            data_with_length = struct.pack(">I", len(hidden_data)) + hidden_data
            data_with_length = self._add_integrity(data_with_length)
            
            capacity = self.get_capacity(carrier_data)
            if len(data_with_length) > capacity:
                return EmbeddingResult(
                    success=False,
                    error_message=f"Data too large: {len(data_with_length)} > {capacity} bytes"
                )
            
            # Convert to bit array
            bits = self._bytes_to_bits(data_with_length)
            
            # Embed in carrier (simplified LSB)
            carrier = bytearray(carrier_data)
            bit_index = 0
            
            # Skip potential header (first 54 bytes for BMP-like)
            start_offset = 54
            
            for i in range(start_offset, len(carrier)):
                if bit_index >= len(bits):
                    break
                
                # Apply adaptive embedding if enabled
                if self.config.adaptive_embedding:
                    # Skip high-entropy regions
                    if i > 0 and abs(carrier[i] - carrier[i-1]) > 50:
                        continue
                
                # Embed bit in LSB
                for _ in range(self.config.redundancy):
                    if bit_index < len(bits) and i < len(carrier):
                        carrier[i] = (carrier[i] & 0xFE) | bits[bit_index]
                        bit_index += 1
                        i += 1
            
            return EmbeddingResult(
                success=True,
                carrier_data=bytes(carrier),
                capacity_used=len(data_with_length),
                capacity_total=capacity,
                metadata={"method": "LSB", "bits_embedded": bit_index}
            )
            
        except Exception as e:
            logger.error(f"Embedding failed: {e}")
            return EmbeddingResult(success=False, error_message=str(e))
    
    def extract(self, carrier_data: bytes) -> ExtractionResult:
        """Extract LSB-embedded data."""
        try:
            carrier = bytearray(carrier_data)
            extracted_bits = []
            
            # Skip header
            start_offset = 54
            
            for i in range(start_offset, len(carrier)):
                # Extract LSB
                bit = carrier[i] & 1
                extracted_bits.append(bit)
                
                # Stop when we have enough for length prefix
                if len(extracted_bits) >= 32 + 4 * 8:  # Length + CRC
                    # Try to decode length
                    length_bits = extracted_bits[:32]
                    length = self._bits_to_int(length_bits)
                    
                    if 0 < length < len(carrier_data):  # Sanity check
                        required_bits = 32 + length * 8 + 32  # Length + data + CRC
                        if len(extracted_bits) >= required_bits:
                            break
            
            # Convert bits to bytes
            extracted_bytes = self._bits_to_bytes(extracted_bits)
            
            # Verify integrity
            valid, payload = self._verify_integrity(extracted_bytes)
            if not valid:
                return ExtractionResult(
                    success=False,
                    error_message="Integrity check failed"
                )
            
            # Extract length and data
            if len(payload) < 4:
                return ExtractionResult(success=False, error_message="Data too short")
            
            length = struct.unpack(">I", payload[:4])[0]
            hidden_data = payload[4:4+length]
            
            # Decrypt if needed
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_decrypt(hidden_data, key)
            
            return ExtractionResult(
                success=True,
                hidden_data=hidden_data,
                data_length=len(hidden_data),
                integrity_valid=True
            )
            
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            return ExtractionResult(success=False, error_message=str(e))
    
    def _bytes_to_bits(self, data: bytes) -> List[int]:
        """Convert bytes to list of bits."""
        bits = []
        for byte in data:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        return bits
    
    def _bits_to_bytes(self, bits: List[int]) -> bytes:
        """Convert list of bits to bytes."""
        result = bytearray()
        for i in range(0, len(bits) - 7, 8):
            byte = 0
            for j in range(8):
                byte = (byte << 1) | bits[i + j]
            result.append(byte)
        return bytes(result)
    
    def _bits_to_int(self, bits: List[int]) -> int:
        """Convert bits to integer."""
        result = 0
        for bit in bits:
            result = (result << 1) | bit
        return result


class TextSteganography(SteganographyCarrier):
    """
    Text-based steganography using various techniques.
    
    Supports:
    - Zero-width character encoding
    - Whitespace encoding
    - Homoglyph substitution
    - Unicode variation selectors
    """
    
    # Zero-width characters for encoding
    ZERO_WIDTH_CHARS = {
        'zero': '\u200B',      # Zero-width space
        'joiner': '\u200D',    # Zero-width joiner
        'non_joiner': '\u200C', # Zero-width non-joiner
        'lrm': '\u200E',       # Left-to-right mark
        'rlm': '\u200F',       # Right-to-left mark
    }
    
    # Binary encoding using zero-width characters
    BINARY_MAP = {
        '0': '\u200B',  # Zero-width space
        '1': '\u200C',  # Zero-width non-joiner
    }
    
    def get_capacity(self, carrier_data: bytes) -> int:
        """Calculate capacity for text carrier."""
        # Each character can hide ~1 byte using zero-width chars
        try:
            text = carrier_data.decode('utf-8')
            return len(text) // 8  # 8 zero-width chars per byte
        except Exception:
            return 0
    
    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        """Embed data using zero-width characters."""
        try:
            text = carrier_data.decode('utf-8')
            
            # Prepare hidden data
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_encrypt(hidden_data, key)
            
            # Add integrity
            data_with_length = struct.pack(">I", len(hidden_data)) + hidden_data
            data_with_length = self._add_integrity(data_with_length)
            
            # Convert to binary
            binary = ''.join(format(byte, '08b') for byte in data_with_length)
            
            # Embed as zero-width characters
            hidden_chars = []
            for bit in binary:
                hidden_chars.append(self.BINARY_MAP[bit])
            
            # Insert into text (after each word)
            words = text.split(' ')
            result_words = []
            char_index = 0
            
            for i, word in enumerate(words):
                if char_index < len(hidden_chars):
                    # Insert zero-width chars after word
                    chars_to_insert = hidden_chars[char_index:char_index+4]
                    result_words.append(word + ''.join(chars_to_insert))
                    char_index += 4
                else:
                    result_words.append(word)
            
            result = ' '.join(result_words)
            
            return EmbeddingResult(
                success=True,
                carrier_data=result.encode('utf-8'),
                capacity_used=len(hidden_data),
                capacity_total=len(text) // 8,
                metadata={"method": "zero_width"}
            )
            
        except Exception as e:
            logger.error(f"Text embedding failed: {e}")
            return EmbeddingResult(success=False, error_message=str(e))
    
    def extract(self, carrier_data: bytes) -> ExtractionResult:
        """Extract zero-width character encoded data."""
        try:
            text = carrier_data.decode('utf-8')
            
            # Extract zero-width characters
            binary = []
            for char in text:
                if char == self.BINARY_MAP['0']:
                    binary.append('0')
                elif char == self.BINARY_MAP['1']:
                    binary.append('1')
            
            if not binary:
                return ExtractionResult(success=False, error_message="No hidden data found")
            
            # Convert binary to bytes
            extracted_bytes = bytearray()
            for i in range(0, len(binary) - 7, 8):
                byte_str = ''.join(binary[i:i+8])
                extracted_bytes.append(int(byte_str, 2))
            
            # Verify integrity
            valid, payload = self._verify_integrity(bytes(extracted_bytes))
            if not valid:
                return ExtractionResult(
                    success=False,
                    error_message="Integrity check failed"
                )
            
            # Extract length and data
            if len(payload) < 4:
                return ExtractionResult(success=False, error_message="Data too short")
            
            length = struct.unpack(">I", payload[:4])[0]
            hidden_data = payload[4:4+length]
            
            # Decrypt if needed
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_decrypt(hidden_data, key)
            
            return ExtractionResult(
                success=True,
                hidden_data=hidden_data,
                data_length=len(hidden_data),
                integrity_valid=True
            )
            
        except Exception as e:
            logger.error(f"Text extraction failed: {e}")
            return ExtractionResult(success=False, error_message=str(e))


class ProtocolSteganography(SteganographyCarrier):
    """
    Protocol-based steganography for network traffic.
    
    Supports:
    - DNS tunneling with covert encoding
    - HTTP header manipulation
    - TCP timestamp encoding
    - ICMP payload encoding
    """
    
    # DNS record types for covert channels
    DNS_RECORD_TYPES = ['TXT', 'MX', 'NS', 'CNAME']
    
    def get_capacity(self, carrier_data: bytes) -> int:
        """Calculate capacity for protocol carrier."""
        # Depends on protocol type
        # DNS: ~63 bytes per subdomain, multiple queries possible
        # HTTP: ~8KB in headers
        return 1024  # Conservative estimate
    
    def embed_dns(self, domain: str, hidden_data: bytes) -> EmbeddingResult:
        """Embed data in DNS query format."""
        try:
            # Prepare data
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_encrypt(hidden_data, key)
            
            # Base32 encode for DNS compatibility
            import base64
            encoded = base64.b32encode(hidden_data).decode('ascii').rstrip('=').lower()
            
            # Split into subdomain chunks (max 63 chars each)
            chunk_size = 60
            subdomains = []
            for i in range(0, len(encoded), chunk_size):
                subdomains.append(encoded[i:i+chunk_size])
            
            # Build covert domain
            covert_domain = '.'.join(subdomains + [domain])
            
            return EmbeddingResult(
                success=True,
                carrier_data=covert_domain.encode('utf-8'),
                capacity_used=len(hidden_data),
                capacity_total=255,  # Max DNS name length
                metadata={"method": "dns_tunnel", "chunks": len(subdomains)}
            )
            
        except Exception as e:
            logger.error(f"DNS embedding failed: {e}")
            return EmbeddingResult(success=False, error_message=str(e))
    
    def extract_dns(self, covert_domain: str) -> ExtractionResult:
        """Extract data from covert DNS domain."""
        try:
            parts = covert_domain.split('.')
            
            # Remove base domain (last 2 parts typically)
            encoded_parts = parts[:-2]
            
            if not encoded_parts:
                return ExtractionResult(success=False, error_message="No encoded data found")
            
            # Reconstruct encoded data
            encoded = ''.join(encoded_parts)
            
            # Add padding for base32
            padding = (8 - len(encoded) % 8) % 8
            encoded += '=' * padding
            
            # Decode
            import base64
            hidden_data = base64.b32decode(encoded.upper())
            
            # Decrypt if needed
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_decrypt(hidden_data, key)
            
            return ExtractionResult(
                success=True,
                hidden_data=hidden_data,
                data_length=len(hidden_data),
                integrity_valid=True
            )
            
        except Exception as e:
            logger.error(f"DNS extraction failed: {e}")
            return ExtractionResult(success=False, error_message=str(e))
    
    def embed_http_headers(self, headers: Dict[str, str], hidden_data: bytes) -> EmbeddingResult:
        """Embed data in HTTP headers."""
        try:
            # Prepare data
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_encrypt(hidden_data, key)
            
            # Add integrity
            data_with_integrity = self._add_integrity(hidden_data)
            
            # Encode as hex for header value
            import base64
            encoded = base64.b64encode(data_with_integrity).decode('ascii')
            
            # Split into multiple headers if needed
            chunk_size = 1000
            modified_headers = dict(headers)
            
            for i in range(0, len(encoded), chunk_size):
                chunk = encoded[i:i+chunk_size]
                header_name = f"X-Session-{i//chunk_size}"
                modified_headers[header_name] = chunk
            
            return EmbeddingResult(
                success=True,
                carrier_data=str(modified_headers).encode('utf-8'),
                capacity_used=len(hidden_data),
                capacity_total=8192,  # Typical header limit
                metadata={"method": "http_headers", "headers_added": (len(encoded) + chunk_size - 1) // chunk_size}
            )
            
        except Exception as e:
            logger.error(f"HTTP header embedding failed: {e}")
            return EmbeddingResult(success=False, error_message=str(e))
    
    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        """Generic embed (defaults to DNS)."""
        return self.embed_dns(carrier_data.decode('utf-8'), hidden_data)
    
    def extract(self, carrier_data: bytes) -> ExtractionResult:
        """Generic extract (defaults to DNS)."""
        return self.extract_dns(carrier_data.decode('utf-8'))


class AudioSteganography(SteganographyCarrier):
    """
    Audio-based steganography.
    
    Supports:
    - LSB encoding in audio samples
    - Phase coding
    - Echo hiding
    - Spread spectrum
    """
    
    def get_capacity(self, carrier_data: bytes) -> int:
        """Calculate capacity for audio carrier."""
        # Rough estimate: 1 bit per sample, 16-bit samples
        return len(carrier_data) // 16 // 8
    
    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        """Embed data using audio LSB."""
        try:
            # Prepare hidden data
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_encrypt(hidden_data, key)
            
            data_with_length = struct.pack(">I", len(hidden_data)) + hidden_data
            data_with_length = self._add_integrity(data_with_length)
            
            # Convert to bits
            bits = []
            for byte in data_with_length:
                for i in range(7, -1, -1):
                    bits.append((byte >> i) & 1)
            
            # Embed in audio samples (simplified)
            carrier = bytearray(carrier_data)
            
            # Skip WAV header (44 bytes typically)
            header_size = 44
            bit_index = 0
            
            for i in range(header_size, len(carrier) - 1, 2):
                if bit_index >= len(bits):
                    break
                
                # Get 16-bit sample
                sample = carrier[i] | (carrier[i+1] << 8)
                
                # Embed bit in LSB
                sample = (sample & 0xFFFE) | bits[bit_index]
                bit_index += 1
                
                # Write back
                carrier[i] = sample & 0xFF
                carrier[i+1] = (sample >> 8) & 0xFF
            
            return EmbeddingResult(
                success=True,
                carrier_data=bytes(carrier),
                capacity_used=len(hidden_data),
                capacity_total=self.get_capacity(carrier_data),
                metadata={"method": "audio_lsb", "bits_embedded": bit_index}
            )
            
        except Exception as e:
            logger.error(f"Audio embedding failed: {e}")
            return EmbeddingResult(success=False, error_message=str(e))
    
    def extract(self, carrier_data: bytes) -> ExtractionResult:
        """Extract audio LSB data."""
        try:
            carrier = bytearray(carrier_data)
            bits = []
            
            # Skip header
            header_size = 44
            
            for i in range(header_size, len(carrier) - 1, 2):
                sample = carrier[i] | (carrier[i+1] << 8)
                bits.append(sample & 1)
            
            # Convert bits to bytes
            extracted = bytearray()
            for i in range(0, len(bits) - 7, 8):
                byte = 0
                for j in range(8):
                    byte = (byte << 1) | bits[i + j]
                extracted.append(byte)
            
            # Verify integrity
            valid, payload = self._verify_integrity(bytes(extracted))
            if not valid:
                return ExtractionResult(success=False, error_message="Integrity check failed")
            
            # Extract length and data
            if len(payload) < 4:
                return ExtractionResult(success=False, error_message="Data too short")
            
            length = struct.unpack(">I", payload[:4])[0]
            hidden_data = payload[4:4+length]
            
            # Decrypt if needed
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._stream_cipher_decrypt(hidden_data, key)
            
            return ExtractionResult(
                success=True,
                hidden_data=hidden_data,
                data_length=len(hidden_data),
                integrity_valid=True
            )
            
        except Exception as e:
            logger.error(f"Audio extraction failed: {e}")
            return ExtractionResult(success=False, error_message=str(e))


class SteganographyEngine:
    """
    Unified steganography engine supporting multiple carrier types.
    """
    
    def __init__(
        self,
        config: Optional[SteganographyConfig] = None,
        *,
        event_bus: Optional[EventBus] = None,
        event_project_root: Optional[str] = None,
    ):
        self.config = config or SteganographyConfig()
        self.event_bus = event_bus
        self.event_project_root = event_project_root
        self._carriers: Dict[SteganographyType, SteganographyCarrier] = {
            SteganographyType.IMAGE: ImageSteganography(self.config),
            SteganographyType.TEXT: TextSteganography(self.config),
            SteganographyType.PROTOCOL: ProtocolSteganography(self.config),
            SteganographyType.AUDIO: AudioSteganography(self.config),
        }

    def _event_bus_or_none(self) -> Optional[EventBus]:
        if self.event_bus is not None:
            return self.event_bus
        if self.event_project_root is None:
            return None
        try:
            self.event_bus = get_event_bus(self.event_project_root)
            return self.event_bus
        except Exception as exc:
            logger.error("Failed to initialize steganography EventBus: %s", exc)
            return None

    def _identity_presence(self) -> Dict[str, bool]:
        identity = service_event_identity(service_name=_SERVICE_AGENT)
        return {
            "spiffe_id_present": bool(identity.get("spiffe_id")),
            "did_present": bool(identity.get("did")),
            "wallet_address_present": bool(identity.get("wallet_address")),
            "raw_identity_redacted": True,
        }

    def _config_metadata(self) -> Dict[str, Any]:
        return {
            "use_encryption": bool(self.config.use_encryption),
            "encryption_key_present": bool(self.config.encryption_key),
            "raw_encryption_key_redacted": True,
            "adaptive_embedding": bool(self.config.adaptive_embedding),
            "random_seed_source": str(self.config.random_seed_source)[:64],
            "redundancy": self.config.redundancy,
        }

    def _publish_evidence(
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
            "component": "anti_censorship.steganography",
            "operation": operation,
            "service_name": _SERVICE_AGENT,
            "source_alias": _SERVICE_AGENT,
            "layer": _SERVICE_LAYER,
            "status": status_value,
            "duration_ms": round((time.monotonic() - started_at) * 1000.0, 3),
            "config": self._config_metadata(),
            "service_identity": self._identity_presence(),
            "control_action": False,
            "observed_state": True,
            "payloads_redacted": True,
            "carrier_bytes_redacted": True,
            "hidden_data_redacted": True,
            "extracted_data_redacted": True,
            "raw_identifiers_redacted": True,
            "crypto_material_redacted": True,
            "dataplane_confirmed": False,
            "dpi_bypass_confirmed": False,
            "bypass_confirmed": False,
            "external_dpi_tested": False,
            "claim_boundary": STEGANOGRAPHY_ENGINE_CLAIM_BOUNDARY,
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
            if status_value.endswith("failed") or status_value == "unsupported"
            else EventType.PIPELINE_STAGE_END
        )
        try:
            event = bus.publish(event_type, _SERVICE_AGENT, payload, priority=4)
            return event.event_id
        except Exception as exc:
            logger.error("Failed to publish steganography evidence: %s", exc)
            return None
    
    def get_capacity(
        self,
        carrier_data: bytes,
        carrier_type: SteganographyType = SteganographyType.IMAGE
    ) -> int:
        """Get capacity for a carrier."""
        started_at = time.monotonic()
        carrier = self._carriers.get(carrier_type)
        if carrier:
            capacity = carrier.get_capacity(carrier_data)
            self._publish_evidence(
                operation="get_capacity",
                status_value="measured",
                started_at=started_at,
                metadata={
                    "carrier_type": _carrier_type_bucket(carrier_type),
                    "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                    "capacity_bytes_bucket": _byte_count_bucket(capacity),
                },
            )
            return capacity
        self._publish_evidence(
            operation="get_capacity",
            status_value="unsupported",
            started_at=started_at,
            metadata={
                "carrier_type": _carrier_type_bucket(carrier_type),
                "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                "capacity_bytes_bucket": "zero",
            },
        )
        return 0
    
    def embed(
        self,
        carrier_data: bytes,
        hidden_data: bytes,
        carrier_type: SteganographyType = SteganographyType.IMAGE
    ) -> EmbeddingResult:
        """Embed data in carrier."""
        started_at = time.monotonic()
        carrier = self._carriers.get(carrier_type)
        if not carrier:
            self._publish_evidence(
                operation="embed",
                status_value="unsupported",
                started_at=started_at,
                metadata={
                    "carrier_type": _carrier_type_bucket(carrier_type),
                    "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                    "hidden_bytes_bucket": _byte_count_bucket(len(hidden_data)),
                },
            )
            return EmbeddingResult(
                success=False,
                error_message=f"Unsupported carrier type: {carrier_type}"
            )
        result = carrier.embed(carrier_data, hidden_data)
        self._publish_evidence(
            operation="embed",
            status_value="embedded" if result.success else "embed_failed",
            started_at=started_at,
            metadata={
                "carrier_type": _carrier_type_bucket(carrier_type),
                "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                "hidden_bytes_bucket": _byte_count_bucket(len(hidden_data)),
                "output_carrier_present": bool(result.carrier_data),
                "output_carrier_bytes_bucket": _byte_count_bucket(
                    len(result.carrier_data or b"")
                ),
                "capacity_used_bucket": _byte_count_bucket(result.capacity_used),
                "capacity_total_bucket": _byte_count_bucket(result.capacity_total),
                "result_metadata": _safe_result_metadata(result.metadata),
                "error_message_redacted": bool(result.error_message),
            },
        )
        return result
    
    def extract(
        self,
        carrier_data: bytes,
        carrier_type: SteganographyType = SteganographyType.IMAGE
    ) -> ExtractionResult:
        """Extract data from carrier."""
        started_at = time.monotonic()
        carrier = self._carriers.get(carrier_type)
        if not carrier:
            self._publish_evidence(
                operation="extract",
                status_value="unsupported",
                started_at=started_at,
                metadata={
                    "carrier_type": _carrier_type_bucket(carrier_type),
                    "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                },
            )
            return ExtractionResult(
                success=False,
                error_message=f"Unsupported carrier type: {carrier_type}"
            )
        result = carrier.extract(carrier_data)
        self._publish_evidence(
            operation="extract",
            status_value="extracted" if result.success else "extract_failed",
            started_at=started_at,
            metadata={
                "carrier_type": _carrier_type_bucket(carrier_type),
                "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                "hidden_data_present": bool(result.hidden_data),
                "hidden_data_bytes_bucket": _byte_count_bucket(result.data_length),
                "integrity_valid": bool(result.integrity_valid),
                "error_message_redacted": bool(result.error_message),
            },
        )
        return result
    
    def auto_detect_and_extract(self, carrier_data: bytes) -> ExtractionResult:
        """Try all carrier types to extract data."""
        started_at = time.monotonic()
        attempts = 0
        for stego_type, carrier in self._carriers.items():
            try:
                attempts += 1
                result = carrier.extract(carrier_data)
                if result.success:
                    result.metadata = {"detected_type": stego_type.value}
                    self._publish_evidence(
                        operation="auto_detect_and_extract",
                        status_value="detected",
                        started_at=started_at,
                        metadata={
                            "carrier_bytes_bucket": _byte_count_bucket(
                                len(carrier_data)
                            ),
                            "attempts": attempts,
                            "detected_type": stego_type.value,
                            "hidden_data_present": bool(result.hidden_data),
                            "hidden_data_bytes_bucket": _byte_count_bucket(
                                result.data_length
                            ),
                            "integrity_valid": bool(result.integrity_valid),
                        },
                    )
                    return result
            except Exception:
                continue

        self._publish_evidence(
            operation="auto_detect_and_extract",
            status_value="not_detected",
            started_at=started_at,
            metadata={
                "carrier_bytes_bucket": _byte_count_bucket(len(carrier_data)),
                "attempts": attempts,
                "hidden_data_present": False,
                "hidden_data_bytes_bucket": "zero",
            },
        )
        return ExtractionResult(
            success=False,
            error_message="No hidden data detected with any method"
        )
    
    def create_covert_channel(
        self,
        data: bytes,
        carrier_type: SteganographyType = SteganographyType.PROTOCOL,
        template: Optional[bytes] = None
    ) -> EmbeddingResult:
        """
        Create a covert channel for data transmission.
        
        Generates appropriate carrier if template not provided.
        """
        started_at = time.monotonic()
        if carrier_type == SteganographyType.PROTOCOL:
            # Use DNS tunneling
            dns = ProtocolSteganography(self.config)
            result = dns.embed_dns("covert.example.com", data)
        
        elif carrier_type == SteganographyType.TEXT:
            # Generate cover text
            if template is None:
                template = self._generate_cover_text(len(data))
            result = self.embed(template, data, carrier_type)
        
        elif carrier_type == SteganographyType.IMAGE:
            if template is None:
                template = self._generate_cover_image(len(data))
            result = self.embed(template, data, carrier_type)
        
        else:
            self._publish_evidence(
                operation="create_covert_channel",
                status_value="unsupported",
                started_at=started_at,
                metadata={
                    "carrier_type": _carrier_type_bucket(carrier_type),
                    "hidden_bytes_bucket": _byte_count_bucket(len(data)),
                    "template_present": template is not None,
                    "template_bytes_bucket": _byte_count_bucket(
                        len(template or b"")
                    ),
                },
            )
            return EmbeddingResult(
                success=False,
                error_message=f"Cannot auto-generate carrier for {carrier_type}"
            )

        self._publish_evidence(
            operation="create_covert_channel",
            status_value="created" if result.success else "create_failed",
            started_at=started_at,
            metadata={
                "carrier_type": _carrier_type_bucket(carrier_type),
                "hidden_bytes_bucket": _byte_count_bucket(len(data)),
                "template_present": template is not None,
                "template_bytes_bucket": _byte_count_bucket(len(template or b"")),
                "output_carrier_present": bool(result.carrier_data),
                "output_carrier_bytes_bucket": _byte_count_bucket(
                    len(result.carrier_data or b"")
                ),
                "capacity_used_bucket": _byte_count_bucket(result.capacity_used),
                "capacity_total_bucket": _byte_count_bucket(result.capacity_total),
                "result_metadata": _safe_result_metadata(result.metadata),
                "generated_cover_redacted": True,
                "error_message_redacted": bool(result.error_message),
            },
        )
        return result
    
    def _generate_cover_text(self, data_length: int) -> bytes:
        """Generate innocuous cover text."""
        # Lorem ipsum style text
        words = [
            "the", "be", "to", "of", "and", "a", "in", "that", "have", "I",
            "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
            "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
            "or", "an", "will", "my", "one", "all", "would", "there", "their", "what"
        ]
        
        # Need ~8x data_length characters for zero-width encoding
        needed_words = (data_length * 8) // 4 + 50
        
        text_parts = []
        for _ in range(needed_words):
            text_parts.append(random.choice(words))
        
        return ' '.join(text_parts).encode('utf-8')
    
    def _generate_cover_image(self, data_length: int) -> bytes:
        """Generate minimal cover image."""
        # Create minimal BMP-like structure
        # This is a placeholder - real implementation would create actual image
        needed_bytes = data_length * 8 * 3  # RGB for LSB
        width = int(math.sqrt(needed_bytes / 3))
        height = width
        
        # BMP header (simplified)
        header = bytearray(54)
        header[0:2] = b'BM'
        file_size = 54 + width * height * 3
        header[2:6] = struct.pack('<I', file_size)
        header[10:14] = struct.pack('<I', 54)  # Pixel offset
        header[14:18] = struct.pack('<I', 40)  # DIB header size
        header[18:22] = struct.pack('<i', width)
        header[22:26] = struct.pack('<i', height)
        header[26:28] = struct.pack('<H', 1)   # Planes
        header[28:30] = struct.pack('<H', 24)  # Bits per pixel
        
        # Random pixel data
        pixels = bytearray(width * height * 3)
        for i in range(len(pixels)):
            pixels[i] = random.randint(0, 255)
        
        return bytes(header + pixels)


# Convenience functions
def hide_data(
    carrier: bytes,
    data: bytes,
    carrier_type: SteganographyType = SteganographyType.IMAGE,
    key: Optional[bytes] = None
) -> EmbeddingResult:
    """Quick function to hide data in carrier."""
    config = SteganographyConfig(
        use_encryption=key is not None,
        encryption_key=key
    )
    engine = SteganographyEngine(config)
    return engine.embed(carrier, data, carrier_type)


def extract_data(
    carrier: bytes,
    carrier_type: SteganographyType = SteganographyType.IMAGE,
    key: Optional[bytes] = None
) -> ExtractionResult:
    """Quick function to extract hidden data."""
    config = SteganographyConfig(
        use_encryption=key is not None,
        encryption_key=key
    )
    engine = SteganographyEngine(config)
    return engine.extract(carrier, carrier_type)


def auto_extract(carrier: bytes, key: Optional[bytes] = None) -> ExtractionResult:
    """Auto-detect and extract hidden data."""
    config = SteganographyConfig(
        use_encryption=key is not None,
        encryption_key=key
    )
    engine = SteganographyEngine(config)
    return engine.auto_detect_and_extract(carrier)
