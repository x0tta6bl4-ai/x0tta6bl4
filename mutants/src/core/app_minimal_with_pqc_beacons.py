"""
x0tta6bl4 Minimal App with PQC Beacon Signatures
Enhanced version with Dilithium signatures for Byzantine fault tolerance.
"""
from __future__ import annotations

import asyncio
import logging
import time
import json
import random
import hashlib
from typing import Dict, Any, List, Optional
from collections import defaultdict

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("x0tta6bl4")

# Try to import liboqs for PQC signatures
try:
    from oqs import Signature
    LIBOQS_AVAILABLE = True
    logger.info("✅ liboqs available - PQC signatures enabled")
except ImportError:
    LIBOQS_AVAILABLE = False
    logger.warning("⚠️ liboqs not available - beacon signatures disabled")

app = FastAPI(title="x0tta6bl4-minimal-pqc", version="3.0.0", docs_url="/docs")

# --- Configuration ---
PEER_TIMEOUT = 30.0
HEALTH_CHECK_INTERVAL = 5.0

# --- In-Memory State ---
node_id = "node-01"
peers: Dict[str, Dict] = {}
routes: Dict[str, List[str]] = {}
beacons_received: List[Dict] = []
dead_peers: set = set()

# PQC Signature keys (if liboqs available)
_sig_public_key: Optional[bytes] = None
_sig_private_key: Optional[bytes] = None
_peer_public_keys: Dict[str, bytes] = {}  # peer_id -> public_key

# Initialize PQC signature if available
if LIBOQS_AVAILABLE:
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
            _sig_public_key, _sig_private_key = sig.generate_keypair()
            logger.info("✅ PQC signature keypair generated (ML-DSA-65, NIST FIPS 204)")
        except Exception:
            # Fallback to legacy name if NIST name not supported
            pass
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
            _sig_public_key, _sig_private_key = sig.generate_keypair()
            logger.info("✅ PQC signature keypair generated (Dilithium3, legacy)")
    except Exception as e:
        logger.error(f"Failed to generate PQC keys: {e}")
        LIBOQS_AVAILABLE = False
from inspect import signature as _mutmut_signature
from typing import Annotated
from typing import Callable
from typing import ClassVar


MutantDict = Annotated[dict[str, Callable], "Mutant"]


def _mutmut_trampoline(orig, mutants, call_args, call_kwargs, self_arg = None):
    """Forward call to original or mutated function, depending on the environment"""
    import os
    mutant_under_test = os.environ['MUTANT_UNDER_TEST']
    if mutant_under_test == 'fail':
        from mutmut.__main__ import MutmutProgrammaticFailException
        raise MutmutProgrammaticFailException('Failed programmatically')      
    elif mutant_under_test == 'stats':
        from mutmut.__main__ import record_trampoline_hit
        record_trampoline_hit(orig.__module__ + '.' + orig.__name__)
        result = orig(*call_args, **call_kwargs)
        return result
    prefix = orig.__module__ + '.' + orig.__name__ + '__mutmut_'
    if not mutant_under_test.startswith(prefix):
        result = orig(*call_args, **call_kwargs)
        return result
    mutant_name = mutant_under_test.rpartition('.')[-1]
    if self_arg is not None:
        # call to a class method where self is not bound
        result = mutants[mutant_name](self_arg, *call_args, **call_kwargs)
    else:
        result = mutants[mutant_name](*call_args, **call_kwargs)
    return result

# --- Models ---
class BeaconRequest(BaseModel):
    node_id: str
    timestamp: float
    neighbors: Optional[List[str]] = []
    signature: Optional[str] = None  # Hex-encoded signature
    public_key: Optional[str] = None  # Hex-encoded public key (first beacon only)

class RouteRequest(BaseModel):
    destination: str
    payload: str

# --- PQC Functions ---

def x_sign_beacon__mutmut_orig(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_1(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE and _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_2(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_3(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is not None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_4(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b"XXXX"  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_5(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = None  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_6(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature(None)  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_7(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("XXML-DSA-65XX")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_8(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ml-dsa-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_9(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = None  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_10(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature(None)  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_11(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("XXDilithium3XX")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_12(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_13(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("DILITHIUM3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_14(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(None)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_15(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = None
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_16(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(None)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_17(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(None)
        return b""

# --- PQC Functions ---

def x_sign_beacon__mutmut_18(beacon_data: bytes) -> bytes:
    """Sign beacon data with PQC signature."""
    if not LIBOQS_AVAILABLE or _sig_private_key is None:
        return b""  # No signature if PQC not available
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_secret_key(_sig_private_key)
        signature = sig.sign(beacon_data)
        return signature
    except Exception as e:
        logger.error(f"Failed to sign beacon: {e}")
        return b"XXXX"

x_sign_beacon__mutmut_mutants : ClassVar[MutantDict] = {
'x_sign_beacon__mutmut_1': x_sign_beacon__mutmut_1, 
    'x_sign_beacon__mutmut_2': x_sign_beacon__mutmut_2, 
    'x_sign_beacon__mutmut_3': x_sign_beacon__mutmut_3, 
    'x_sign_beacon__mutmut_4': x_sign_beacon__mutmut_4, 
    'x_sign_beacon__mutmut_5': x_sign_beacon__mutmut_5, 
    'x_sign_beacon__mutmut_6': x_sign_beacon__mutmut_6, 
    'x_sign_beacon__mutmut_7': x_sign_beacon__mutmut_7, 
    'x_sign_beacon__mutmut_8': x_sign_beacon__mutmut_8, 
    'x_sign_beacon__mutmut_9': x_sign_beacon__mutmut_9, 
    'x_sign_beacon__mutmut_10': x_sign_beacon__mutmut_10, 
    'x_sign_beacon__mutmut_11': x_sign_beacon__mutmut_11, 
    'x_sign_beacon__mutmut_12': x_sign_beacon__mutmut_12, 
    'x_sign_beacon__mutmut_13': x_sign_beacon__mutmut_13, 
    'x_sign_beacon__mutmut_14': x_sign_beacon__mutmut_14, 
    'x_sign_beacon__mutmut_15': x_sign_beacon__mutmut_15, 
    'x_sign_beacon__mutmut_16': x_sign_beacon__mutmut_16, 
    'x_sign_beacon__mutmut_17': x_sign_beacon__mutmut_17, 
    'x_sign_beacon__mutmut_18': x_sign_beacon__mutmut_18
}

def sign_beacon(*args, **kwargs):
    result = _mutmut_trampoline(x_sign_beacon__mutmut_orig, x_sign_beacon__mutmut_mutants, args, kwargs)
    return result 

sign_beacon.__signature__ = _mutmut_signature(x_sign_beacon__mutmut_orig)
x_sign_beacon__mutmut_orig.__name__ = 'x_sign_beacon'

def x_verify_beacon__mutmut_orig(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_1(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_2(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return False  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_3(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature and len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_4(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_5(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) != 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_6(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 1:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_7(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning(None)
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_8(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("XXBeacon has no signatureXX")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_9(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_10(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("BEACON HAS NO SIGNATURE")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_11(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return True
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_12(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = None  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_13(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature(None)  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_14(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("XXML-DSA-65XX")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_15(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ml-dsa-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_16(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = None  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_17(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature(None)  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_18(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("XXDilithium3XX")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_19(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_20(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("DILITHIUM3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_21(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(None)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_22(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = None
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_23(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(None, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_24(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, None)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_25(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_26(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, )
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return False

def x_verify_beacon__mutmut_27(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(None)
        return False

def x_verify_beacon__mutmut_28(beacon_data: bytes, signature: bytes, public_key: bytes) -> bool:
    """Verify beacon signature."""
    if not LIBOQS_AVAILABLE:
        return True  # Accept if PQC not available (backward compatibility)
    
    if not signature or len(signature) == 0:
        logger.warning("Beacon has no signature")
        return False
    
    try:
        # Use NIST name, fallback to legacy if needed
        try:
            sig = Signature("ML-DSA-65")  # NIST FIPS 204 Level 3
        except Exception:
            sig = Signature("Dilithium3")  # Legacy fallback
        sig.set_public_key(public_key)
        is_valid = sig.verify(beacon_data, signature)
        return is_valid
    except Exception as e:
        logger.error(f"Failed to verify beacon signature: {e}")
        return True

x_verify_beacon__mutmut_mutants : ClassVar[MutantDict] = {
'x_verify_beacon__mutmut_1': x_verify_beacon__mutmut_1, 
    'x_verify_beacon__mutmut_2': x_verify_beacon__mutmut_2, 
    'x_verify_beacon__mutmut_3': x_verify_beacon__mutmut_3, 
    'x_verify_beacon__mutmut_4': x_verify_beacon__mutmut_4, 
    'x_verify_beacon__mutmut_5': x_verify_beacon__mutmut_5, 
    'x_verify_beacon__mutmut_6': x_verify_beacon__mutmut_6, 
    'x_verify_beacon__mutmut_7': x_verify_beacon__mutmut_7, 
    'x_verify_beacon__mutmut_8': x_verify_beacon__mutmut_8, 
    'x_verify_beacon__mutmut_9': x_verify_beacon__mutmut_9, 
    'x_verify_beacon__mutmut_10': x_verify_beacon__mutmut_10, 
    'x_verify_beacon__mutmut_11': x_verify_beacon__mutmut_11, 
    'x_verify_beacon__mutmut_12': x_verify_beacon__mutmut_12, 
    'x_verify_beacon__mutmut_13': x_verify_beacon__mutmut_13, 
    'x_verify_beacon__mutmut_14': x_verify_beacon__mutmut_14, 
    'x_verify_beacon__mutmut_15': x_verify_beacon__mutmut_15, 
    'x_verify_beacon__mutmut_16': x_verify_beacon__mutmut_16, 
    'x_verify_beacon__mutmut_17': x_verify_beacon__mutmut_17, 
    'x_verify_beacon__mutmut_18': x_verify_beacon__mutmut_18, 
    'x_verify_beacon__mutmut_19': x_verify_beacon__mutmut_19, 
    'x_verify_beacon__mutmut_20': x_verify_beacon__mutmut_20, 
    'x_verify_beacon__mutmut_21': x_verify_beacon__mutmut_21, 
    'x_verify_beacon__mutmut_22': x_verify_beacon__mutmut_22, 
    'x_verify_beacon__mutmut_23': x_verify_beacon__mutmut_23, 
    'x_verify_beacon__mutmut_24': x_verify_beacon__mutmut_24, 
    'x_verify_beacon__mutmut_25': x_verify_beacon__mutmut_25, 
    'x_verify_beacon__mutmut_26': x_verify_beacon__mutmut_26, 
    'x_verify_beacon__mutmut_27': x_verify_beacon__mutmut_27, 
    'x_verify_beacon__mutmut_28': x_verify_beacon__mutmut_28
}

def verify_beacon(*args, **kwargs):
    result = _mutmut_trampoline(x_verify_beacon__mutmut_orig, x_verify_beacon__mutmut_mutants, args, kwargs)
    return result 

verify_beacon.__signature__ = _mutmut_signature(x_verify_beacon__mutmut_orig)
x_verify_beacon__mutmut_orig.__name__ = 'x_verify_beacon'

def x_get_beacon_data__mutmut_orig(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_1(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = None
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_2(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "XXnode_idXX": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_3(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "NODE_ID": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_4(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "XXtimestampXX": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_5(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "TIMESTAMP": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_6(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "XXneighborsXX": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_7(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "NEIGHBORS": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_8(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(None)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_9(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode(None)

def x_get_beacon_data__mutmut_10(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(None, sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_11(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=None).encode('utf-8')

def x_get_beacon_data__mutmut_12(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(sort_keys=True).encode('utf-8')

def x_get_beacon_data__mutmut_13(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, ).encode('utf-8')

def x_get_beacon_data__mutmut_14(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=False).encode('utf-8')

def x_get_beacon_data__mutmut_15(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('XXutf-8XX')

def x_get_beacon_data__mutmut_16(node_id: str, timestamp: float, neighbors: List[str]) -> bytes:
    """Serialize beacon data for signing."""
    data = {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": sorted(neighbors)  # Sort for deterministic signing
    }
    return json.dumps(data, sort_keys=True).encode('UTF-8')

x_get_beacon_data__mutmut_mutants : ClassVar[MutantDict] = {
'x_get_beacon_data__mutmut_1': x_get_beacon_data__mutmut_1, 
    'x_get_beacon_data__mutmut_2': x_get_beacon_data__mutmut_2, 
    'x_get_beacon_data__mutmut_3': x_get_beacon_data__mutmut_3, 
    'x_get_beacon_data__mutmut_4': x_get_beacon_data__mutmut_4, 
    'x_get_beacon_data__mutmut_5': x_get_beacon_data__mutmut_5, 
    'x_get_beacon_data__mutmut_6': x_get_beacon_data__mutmut_6, 
    'x_get_beacon_data__mutmut_7': x_get_beacon_data__mutmut_7, 
    'x_get_beacon_data__mutmut_8': x_get_beacon_data__mutmut_8, 
    'x_get_beacon_data__mutmut_9': x_get_beacon_data__mutmut_9, 
    'x_get_beacon_data__mutmut_10': x_get_beacon_data__mutmut_10, 
    'x_get_beacon_data__mutmut_11': x_get_beacon_data__mutmut_11, 
    'x_get_beacon_data__mutmut_12': x_get_beacon_data__mutmut_12, 
    'x_get_beacon_data__mutmut_13': x_get_beacon_data__mutmut_13, 
    'x_get_beacon_data__mutmut_14': x_get_beacon_data__mutmut_14, 
    'x_get_beacon_data__mutmut_15': x_get_beacon_data__mutmut_15, 
    'x_get_beacon_data__mutmut_16': x_get_beacon_data__mutmut_16
}

def get_beacon_data(*args, **kwargs):
    result = _mutmut_trampoline(x_get_beacon_data__mutmut_orig, x_get_beacon_data__mutmut_mutants, args, kwargs)
    return result 

get_beacon_data.__signature__ = _mutmut_signature(x_get_beacon_data__mutmut_orig)
x_get_beacon_data__mutmut_orig.__name__ = 'x_get_beacon_data'

# --- Background Tasks ---

async def x_health_check_loop__mutmut_orig():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_1():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while False:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_2():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = None
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_3():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = None
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_4():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(None):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_5():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = None
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_6():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get(None, 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_7():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", None)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_8():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get(0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_9():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", )
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_10():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("XXlast_seenXX", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_11():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("LAST_SEEN", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_12():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 1)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_13():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = None
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_14():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time + last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_15():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed >= PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_16():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_17():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(None)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_18():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(None)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_19():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(None)
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_20():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id not in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_21():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id not in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_22():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(None)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_23():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(None, exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_24():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=None)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_25():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(exc_info=True)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_26():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", )
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_27():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=False)
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# --- Background Tasks ---

async def x_health_check_loop__mutmut_28():
    """Check peer health and prune dead peers."""
    global peers, dead_peers
    
    while True:
        try:
            current_time = time.time()
            newly_dead = []
            
            for peer_id, peer_info in list(peers.items()):
                last_seen = peer_info.get("last_seen", 0)
                elapsed = current_time - last_seen
                
                if elapsed > PEER_TIMEOUT:
                    if peer_id not in dead_peers:
                        newly_dead.append(peer_id)
                        dead_peers.add(peer_id)
                        logger.warning(f"🔴 Peer {peer_id} marked as DEAD")
            
            for peer_id in newly_dead:
                if peer_id in peers:
                    del peers[peer_id]
                    if peer_id in _peer_public_keys:
                        del _peer_public_keys[peer_id]
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check error: {e}", exc_info=True)
            await asyncio.sleep(None)

x_health_check_loop__mutmut_mutants : ClassVar[MutantDict] = {
'x_health_check_loop__mutmut_1': x_health_check_loop__mutmut_1, 
    'x_health_check_loop__mutmut_2': x_health_check_loop__mutmut_2, 
    'x_health_check_loop__mutmut_3': x_health_check_loop__mutmut_3, 
    'x_health_check_loop__mutmut_4': x_health_check_loop__mutmut_4, 
    'x_health_check_loop__mutmut_5': x_health_check_loop__mutmut_5, 
    'x_health_check_loop__mutmut_6': x_health_check_loop__mutmut_6, 
    'x_health_check_loop__mutmut_7': x_health_check_loop__mutmut_7, 
    'x_health_check_loop__mutmut_8': x_health_check_loop__mutmut_8, 
    'x_health_check_loop__mutmut_9': x_health_check_loop__mutmut_9, 
    'x_health_check_loop__mutmut_10': x_health_check_loop__mutmut_10, 
    'x_health_check_loop__mutmut_11': x_health_check_loop__mutmut_11, 
    'x_health_check_loop__mutmut_12': x_health_check_loop__mutmut_12, 
    'x_health_check_loop__mutmut_13': x_health_check_loop__mutmut_13, 
    'x_health_check_loop__mutmut_14': x_health_check_loop__mutmut_14, 
    'x_health_check_loop__mutmut_15': x_health_check_loop__mutmut_15, 
    'x_health_check_loop__mutmut_16': x_health_check_loop__mutmut_16, 
    'x_health_check_loop__mutmut_17': x_health_check_loop__mutmut_17, 
    'x_health_check_loop__mutmut_18': x_health_check_loop__mutmut_18, 
    'x_health_check_loop__mutmut_19': x_health_check_loop__mutmut_19, 
    'x_health_check_loop__mutmut_20': x_health_check_loop__mutmut_20, 
    'x_health_check_loop__mutmut_21': x_health_check_loop__mutmut_21, 
    'x_health_check_loop__mutmut_22': x_health_check_loop__mutmut_22, 
    'x_health_check_loop__mutmut_23': x_health_check_loop__mutmut_23, 
    'x_health_check_loop__mutmut_24': x_health_check_loop__mutmut_24, 
    'x_health_check_loop__mutmut_25': x_health_check_loop__mutmut_25, 
    'x_health_check_loop__mutmut_26': x_health_check_loop__mutmut_26, 
    'x_health_check_loop__mutmut_27': x_health_check_loop__mutmut_27, 
    'x_health_check_loop__mutmut_28': x_health_check_loop__mutmut_28
}

def health_check_loop(*args, **kwargs):
    result = _mutmut_trampoline(x_health_check_loop__mutmut_orig, x_health_check_loop__mutmut_mutants, args, kwargs)
    return result 

health_check_loop.__signature__ = _mutmut_signature(x_health_check_loop__mutmut_orig)
x_health_check_loop__mutmut_orig.__name__ = 'x_health_check_loop'

# --- Endpoints ---

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "ok",
        "version": "3.0.0",
        "node_id": node_id,
        "pqc_enabled": LIBOQS_AVAILABLE,
        "peers_count": len(peers)
    }

@app.post("/mesh/beacon")
async def receive_beacon(req: BeaconRequest):
    """
    Receive beacon from another node with PQC signature verification.
    
    Byzantine Fault Tolerance: Verifies signature before accepting beacon.
    """
    global peers, dead_peers, _peer_public_keys
    
    # Serialize beacon data for verification
    beacon_data = get_beacon_data(
        req.node_id,
        req.timestamp,
        req.neighbors or []
    )
    
    # Verify signature if PQC is available
    if LIBOQS_AVAILABLE:
        if not req.signature or not req.public_key:
            logger.warning(f"⚠️ Beacon from {req.node_id} has no signature - rejecting")
            raise HTTPException(
                status_code=400,
                detail="Beacon must include signature and public_key when PQC is enabled"
            )
        
        signature = bytes.fromhex(req.signature)
        public_key = bytes.fromhex(req.public_key)
        
        # Store public key if first time seeing this peer
        if req.node_id not in _peer_public_keys:
            _peer_public_keys[req.node_id] = public_key
            logger.info(f"📝 Stored PQC public key for {req.node_id}")
        else:
            # Verify public key hasn't changed (prevent key rotation attacks)
            if _peer_public_keys[req.node_id] != public_key:
                logger.warning(f"⚠️ Public key changed for {req.node_id} - possible attack!")
                raise HTTPException(
                    status_code=403,
                    detail="Public key changed - possible Byzantine attack"
                )
        
        # Verify signature
        is_valid = verify_beacon(beacon_data, signature, public_key)
        if not is_valid:
            logger.warning(f"❌ Invalid signature from {req.node_id} - rejecting")
            raise HTTPException(
                status_code=403,
                detail="Invalid beacon signature - possible Byzantine attack"
            )
        
        logger.debug(f"✅ Verified PQC signature from {req.node_id}")
    
    # If peer was dead, mark as recovered
    if req.node_id in dead_peers:
        dead_peers.remove(req.node_id)
        logger.info(f"✅ Peer {req.node_id} RECOVERED")
    
    # Register/update peer
    peers[req.node_id] = {
        "last_seen": time.time(),
        "neighbors": req.neighbors or []
    }
    
    beacons_received.append({
        "node_id": req.node_id,
        "timestamp": req.timestamp,
        "neighbors": req.neighbors,
        "received_at": time.time(),
        "signature_verified": LIBOQS_AVAILABLE
    })
    
    return {
        "accepted": True,
        "local_node": node_id,
        "peers_count": len(peers),
        "signature_verified": LIBOQS_AVAILABLE
    }

@app.get("/mesh/beacon/sign")
async def get_signed_beacon(neighbors: Optional[str] = None):
    """
    Generate a signed beacon for this node.
    
    Useful for testing and for other nodes to get our public key.
    """
    if not LIBOQS_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PQC signatures not available (liboqs not installed)"
        )
    
    neighbors_list = neighbors.split(",") if neighbors else []
    timestamp = time.time()
    
    # Serialize beacon data
    beacon_data = get_beacon_data(node_id, timestamp, neighbors_list)
    
    # Sign beacon
    signature = sign_beacon(beacon_data)
    
    return {
        "node_id": node_id,
        "timestamp": timestamp,
        "neighbors": neighbors_list,
        "signature": signature.hex(),
        "public_key": _sig_public_key.hex() if _sig_public_key else None
    }

@app.get("/mesh/peers")
async def get_peers():
    """Get list of known peers with PQC status."""
    current_time = time.time()
    peer_status = {}
    
    for peer_id, peer_info in peers.items():
        last_seen = peer_info.get("last_seen", 0)
        elapsed = current_time - last_seen
        is_alive = elapsed < PEER_TIMEOUT
        has_pqc_key = peer_id in _peer_public_keys
        
        peer_status[peer_id] = {
            "last_seen": last_seen,
            "elapsed_seconds": elapsed,
            "is_alive": is_alive,
            "neighbors": peer_info.get("neighbors", []),
            "has_pqc_key": has_pqc_key
        }
    
    return {
        "count": len(peers),
        "peers": list(peers.keys()),
        "details": peer_status,
        "dead_peers": list(dead_peers),
        "pqc_enabled": LIBOQS_AVAILABLE
    }

@app.get("/mesh/status")
async def get_status():
    """Get mesh status with PQC info."""
    return {
        "node_id": node_id,
        "status": "online",
        "peers_count": len(peers),
        "dead_peers_count": len(dead_peers),
        "beacons_received": len(beacons_received),
        "pqc_enabled": LIBOQS_AVAILABLE,
        "pqc_algorithm": "Dilithium3" if LIBOQS_AVAILABLE else None,
        "peers_with_pqc": len(_peer_public_keys)
    }

@app.post("/mesh/route")
async def route_message(req: RouteRequest):
    """Route a message to destination."""
    if req.destination == node_id:
        return {
            "status": "delivered",
            "hops": 0,
            "latency_ms": 0
        }
    
    if req.destination in dead_peers:
        return {
            "status": "unreachable",
            "error": f"Destination {req.destination} is dead"
        }
    
    if req.destination in peers:
        latency = random.uniform(10, 50)
        return {
            "status": "delivered",
            "hops": 1,
            "latency_ms": latency,
            "path": [node_id, req.destination]
        }
    
    return {
        "status": "unreachable",
        "error": f"No route to {req.destination}"
    }

@app.get("/metrics")
async def metrics():
    """Prometheus-compatible metrics with PQC stats."""
    import os
    try:
        import psutil
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        memory_bytes = mem_info.rss
    except:
        memory_bytes = 0
    
    current_time = time.time()
    alive_peers = sum(
        1 for p in peers.values()
        if (current_time - p.get("last_seen", 0)) < PEER_TIMEOUT
    )
    
    metrics_str = f"""# HELP mesh_peers_count Number of known peers
# TYPE mesh_peers_count gauge
mesh_peers_count {len(peers)}

# HELP mesh_dead_peers_count Number of dead peers
# TYPE mesh_dead_peers_count gauge
mesh_dead_peers_count {len(dead_peers)}

# HELP mesh_alive_peers_count Number of alive peers
# TYPE mesh_alive_peers_count gauge
mesh_alive_peers_count {alive_peers}

# HELP mesh_beacons_total Total beacons received
# TYPE mesh_beacons_total counter
mesh_beacons_total {len(beacons_received)}

# HELP mesh_pqc_enabled PQC signatures enabled (1=yes, 0=no)
# TYPE mesh_pqc_enabled gauge
mesh_pqc_enabled {1 if LIBOQS_AVAILABLE else 0}

# HELP mesh_peers_with_pqc Number of peers with PQC keys
# TYPE mesh_peers_with_pqc gauge
mesh_peers_with_pqc {len(_peer_public_keys)}

# HELP process_resident_memory_bytes Resident memory size
# TYPE process_resident_memory_bytes gauge
process_resident_memory_bytes {memory_bytes}
"""
    return metrics_str

@app.on_event("startup")
async def startup():
    """Start background tasks."""
    global node_id
    import os
    
    node_id = os.getenv("NODE_ID", "node-01")
    logger.info(f"🚀 x0tta6bl4 minimal with PQC beacons started as {node_id}")
    
    if LIBOQS_AVAILABLE:
        logger.info("🔐 PQC beacon signatures enabled (Dilithium3)")
    else:
        logger.warning("⚠️ PQC beacon signatures disabled (liboqs not available)")
    
    # Start background tasks
    asyncio.create_task(health_check_loop())
    logger.info("✅ Background tasks started: health_check")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)

