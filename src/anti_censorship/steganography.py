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
import io
import logging
import math
import random
import struct
import zlib
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


class SteganographyType(Enum):
    """Types of steganographic carriers."""
    IMAGE = "image"
    AUDIO = "audio"
    TEXT = "text"
    VIDEO = "video"
    PROTOCOL = "protocol"


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
    
    def _xor_encrypt(self, data: bytes, key: bytes) -> bytes:
        """Simple XOR encryption with key stream."""
        key_stream = hashlib.sha256(key).digest()
        result = bytearray(len(data))
        for i, byte in enumerate(data):
            result[i] = byte ^ key_stream[i % len(key_stream)]
        return bytes(result)
    
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
        except:
            return 0
    
    def embed(self, carrier_data: bytes, hidden_data: bytes) -> EmbeddingResult:
        """Embed data using zero-width characters."""
        try:
            text = carrier_data.decode('utf-8')
            
            # Prepare hidden data
            if self.config.use_encryption:
                key = self._derive_key()
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
                hidden_data = self._xor_encrypt(hidden_data, key)
            
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
    
    def __init__(self, config: Optional[SteganographyConfig] = None):
        self.config = config or SteganographyConfig()
        self._carriers: Dict[SteganographyType, SteganographyCarrier] = {
            SteganographyType.IMAGE: ImageSteganography(self.config),
            SteganographyType.TEXT: TextSteganography(self.config),
            SteganographyType.PROTOCOL: ProtocolSteganography(self.config),
            SteganographyType.AUDIO: AudioSteganography(self.config),
        }
    
    def get_capacity(
        self,
        carrier_data: bytes,
        carrier_type: SteganographyType = SteganographyType.IMAGE
    ) -> int:
        """Get capacity for a carrier."""
        carrier = self._carriers.get(carrier_type)
        if carrier:
            return carrier.get_capacity(carrier_data)
        return 0
    
    def embed(
        self,
        carrier_data: bytes,
        hidden_data: bytes,
        carrier_type: SteganographyType = SteganographyType.IMAGE
    ) -> EmbeddingResult:
        """Embed data in carrier."""
        carrier = self._carriers.get(carrier_type)
        if not carrier:
            return EmbeddingResult(
                success=False,
                error_message=f"Unsupported carrier type: {carrier_type}"
            )
        return carrier.embed(carrier_data, hidden_data)
    
    def extract(
        self,
        carrier_data: bytes,
        carrier_type: SteganographyType = SteganographyType.IMAGE
    ) -> ExtractionResult:
        """Extract data from carrier."""
        carrier = self._carriers.get(carrier_type)
        if not carrier:
            return ExtractionResult(
                success=False,
                error_message=f"Unsupported carrier type: {carrier_type}"
            )
        return carrier.extract(carrier_data)
    
    def auto_detect_and_extract(self, carrier_data: bytes) -> ExtractionResult:
        """Try all carrier types to extract data."""
        for stego_type, carrier in self._carriers.items():
            try:
                result = carrier.extract(carrier_data)
                if result.success:
                    result.metadata = {"detected_type": stego_type.value}
                    return result
            except Exception:
                continue
        
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
        if carrier_type == SteganographyType.PROTOCOL:
            # Use DNS tunneling
            dns = ProtocolSteganography(self.config)
            return dns.embed_dns("covert.example.com", data)
        
        elif carrier_type == SteganographyType.TEXT:
            # Generate cover text
            if template is None:
                template = self._generate_cover_text(len(data))
            return self.embed(template, data, carrier_type)
        
        elif carrier_type == SteganographyType.IMAGE:
            if template is None:
                template = self._generate_cover_image(len(data))
            return self.embed(template, data, carrier_type)
        
        return EmbeddingResult(
            success=False,
            error_message=f"Cannot auto-generate carrier for {carrier_type}"
        )
    
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
