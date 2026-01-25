"""
Post-Quantum Cryptography Module (Demo Implementation).
Uses AES-GCM for symmetric encryption (simulating Kyber KEM shared secret).
"""
import os
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
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

class PQCCrypto:
    def xǁPQCCryptoǁ__init____mutmut_orig(self):
        self.key = os.urandom(32)  # Simulating shared secret from PQC KEM
    def xǁPQCCryptoǁ__init____mutmut_1(self):
        self.key = None  # Simulating shared secret from PQC KEM
    def xǁPQCCryptoǁ__init____mutmut_2(self):
        self.key = os.urandom(None)  # Simulating shared secret from PQC KEM
    def xǁPQCCryptoǁ__init____mutmut_3(self):
        self.key = os.urandom(33)  # Simulating shared secret from PQC KEM
    
    xǁPQCCryptoǁ__init____mutmut_mutants : ClassVar[MutantDict] = {
    'xǁPQCCryptoǁ__init____mutmut_1': xǁPQCCryptoǁ__init____mutmut_1, 
        'xǁPQCCryptoǁ__init____mutmut_2': xǁPQCCryptoǁ__init____mutmut_2, 
        'xǁPQCCryptoǁ__init____mutmut_3': xǁPQCCryptoǁ__init____mutmut_3
    }
    
    def __init__(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁPQCCryptoǁ__init____mutmut_orig"), object.__getattribute__(self, "xǁPQCCryptoǁ__init____mutmut_mutants"), args, kwargs, self)
        return result 
    
    __init__.__signature__ = _mutmut_signature(xǁPQCCryptoǁ__init____mutmut_orig)
    xǁPQCCryptoǁ__init____mutmut_orig.__name__ = 'xǁPQCCryptoǁ__init__'
    
    def xǁPQCCryptoǁencrypt__mutmut_orig(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_1(self, data: bytes) -> bytes:
        iv = None
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_2(self, data: bytes) -> bytes:
        iv = os.urandom(None)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_3(self, data: bytes) -> bytes:
        iv = os.urandom(13)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_4(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = None
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_5(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(None, modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_6(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), None, backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_7(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=None)
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_8(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_9(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_10(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), )
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_11(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(None), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_12(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(None), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_13(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = None
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_14(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = None
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_15(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) - encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_16(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(None) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_17(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv + encryptor.tag - ciphertext
    
    def xǁPQCCryptoǁencrypt__mutmut_18(self, data: bytes) -> bytes:
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return iv - encryptor.tag + ciphertext
    
    xǁPQCCryptoǁencrypt__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁPQCCryptoǁencrypt__mutmut_1': xǁPQCCryptoǁencrypt__mutmut_1, 
        'xǁPQCCryptoǁencrypt__mutmut_2': xǁPQCCryptoǁencrypt__mutmut_2, 
        'xǁPQCCryptoǁencrypt__mutmut_3': xǁPQCCryptoǁencrypt__mutmut_3, 
        'xǁPQCCryptoǁencrypt__mutmut_4': xǁPQCCryptoǁencrypt__mutmut_4, 
        'xǁPQCCryptoǁencrypt__mutmut_5': xǁPQCCryptoǁencrypt__mutmut_5, 
        'xǁPQCCryptoǁencrypt__mutmut_6': xǁPQCCryptoǁencrypt__mutmut_6, 
        'xǁPQCCryptoǁencrypt__mutmut_7': xǁPQCCryptoǁencrypt__mutmut_7, 
        'xǁPQCCryptoǁencrypt__mutmut_8': xǁPQCCryptoǁencrypt__mutmut_8, 
        'xǁPQCCryptoǁencrypt__mutmut_9': xǁPQCCryptoǁencrypt__mutmut_9, 
        'xǁPQCCryptoǁencrypt__mutmut_10': xǁPQCCryptoǁencrypt__mutmut_10, 
        'xǁPQCCryptoǁencrypt__mutmut_11': xǁPQCCryptoǁencrypt__mutmut_11, 
        'xǁPQCCryptoǁencrypt__mutmut_12': xǁPQCCryptoǁencrypt__mutmut_12, 
        'xǁPQCCryptoǁencrypt__mutmut_13': xǁPQCCryptoǁencrypt__mutmut_13, 
        'xǁPQCCryptoǁencrypt__mutmut_14': xǁPQCCryptoǁencrypt__mutmut_14, 
        'xǁPQCCryptoǁencrypt__mutmut_15': xǁPQCCryptoǁencrypt__mutmut_15, 
        'xǁPQCCryptoǁencrypt__mutmut_16': xǁPQCCryptoǁencrypt__mutmut_16, 
        'xǁPQCCryptoǁencrypt__mutmut_17': xǁPQCCryptoǁencrypt__mutmut_17, 
        'xǁPQCCryptoǁencrypt__mutmut_18': xǁPQCCryptoǁencrypt__mutmut_18
    }
    
    def encrypt(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁPQCCryptoǁencrypt__mutmut_orig"), object.__getattribute__(self, "xǁPQCCryptoǁencrypt__mutmut_mutants"), args, kwargs, self)
        return result 
    
    encrypt.__signature__ = _mutmut_signature(xǁPQCCryptoǁencrypt__mutmut_orig)
    xǁPQCCryptoǁencrypt__mutmut_orig.__name__ = 'xǁPQCCryptoǁencrypt'
    
    def xǁPQCCryptoǁdecrypt__mutmut_orig(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_1(self, data: bytes) -> bytes:
        if len(data) <= 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_2(self, data: bytes) -> bytes:
        if len(data) < 29:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_3(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = None
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_4(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:13]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_5(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = None
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_6(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[13:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_7(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:29]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_8(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = None
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_9(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[29:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_10(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = None
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_11(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(None, modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_12(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), None, backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_13(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=None)
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_14(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_15(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_16(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), )
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_17(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(None), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_18(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(None, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_19(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, None), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_20(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_21(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, ), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_22(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = None
        return decryptor.update(ciphertext) + decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_23(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(ciphertext) - decryptor.finalize()
    
    def xǁPQCCryptoǁdecrypt__mutmut_24(self, data: bytes) -> bytes:
        if len(data) < 28:
            return data # Return raw if too short
            
        iv = data[:12]
        tag = data[12:28]
        ciphertext = data[28:]
        
        cipher = Cipher(algorithms.AES(self.key), modes.GCM(iv, tag), backend=default_backend())
        decryptor = cipher.decryptor()
        return decryptor.update(None) + decryptor.finalize()
    
    xǁPQCCryptoǁdecrypt__mutmut_mutants : ClassVar[MutantDict] = {
    'xǁPQCCryptoǁdecrypt__mutmut_1': xǁPQCCryptoǁdecrypt__mutmut_1, 
        'xǁPQCCryptoǁdecrypt__mutmut_2': xǁPQCCryptoǁdecrypt__mutmut_2, 
        'xǁPQCCryptoǁdecrypt__mutmut_3': xǁPQCCryptoǁdecrypt__mutmut_3, 
        'xǁPQCCryptoǁdecrypt__mutmut_4': xǁPQCCryptoǁdecrypt__mutmut_4, 
        'xǁPQCCryptoǁdecrypt__mutmut_5': xǁPQCCryptoǁdecrypt__mutmut_5, 
        'xǁPQCCryptoǁdecrypt__mutmut_6': xǁPQCCryptoǁdecrypt__mutmut_6, 
        'xǁPQCCryptoǁdecrypt__mutmut_7': xǁPQCCryptoǁdecrypt__mutmut_7, 
        'xǁPQCCryptoǁdecrypt__mutmut_8': xǁPQCCryptoǁdecrypt__mutmut_8, 
        'xǁPQCCryptoǁdecrypt__mutmut_9': xǁPQCCryptoǁdecrypt__mutmut_9, 
        'xǁPQCCryptoǁdecrypt__mutmut_10': xǁPQCCryptoǁdecrypt__mutmut_10, 
        'xǁPQCCryptoǁdecrypt__mutmut_11': xǁPQCCryptoǁdecrypt__mutmut_11, 
        'xǁPQCCryptoǁdecrypt__mutmut_12': xǁPQCCryptoǁdecrypt__mutmut_12, 
        'xǁPQCCryptoǁdecrypt__mutmut_13': xǁPQCCryptoǁdecrypt__mutmut_13, 
        'xǁPQCCryptoǁdecrypt__mutmut_14': xǁPQCCryptoǁdecrypt__mutmut_14, 
        'xǁPQCCryptoǁdecrypt__mutmut_15': xǁPQCCryptoǁdecrypt__mutmut_15, 
        'xǁPQCCryptoǁdecrypt__mutmut_16': xǁPQCCryptoǁdecrypt__mutmut_16, 
        'xǁPQCCryptoǁdecrypt__mutmut_17': xǁPQCCryptoǁdecrypt__mutmut_17, 
        'xǁPQCCryptoǁdecrypt__mutmut_18': xǁPQCCryptoǁdecrypt__mutmut_18, 
        'xǁPQCCryptoǁdecrypt__mutmut_19': xǁPQCCryptoǁdecrypt__mutmut_19, 
        'xǁPQCCryptoǁdecrypt__mutmut_20': xǁPQCCryptoǁdecrypt__mutmut_20, 
        'xǁPQCCryptoǁdecrypt__mutmut_21': xǁPQCCryptoǁdecrypt__mutmut_21, 
        'xǁPQCCryptoǁdecrypt__mutmut_22': xǁPQCCryptoǁdecrypt__mutmut_22, 
        'xǁPQCCryptoǁdecrypt__mutmut_23': xǁPQCCryptoǁdecrypt__mutmut_23, 
        'xǁPQCCryptoǁdecrypt__mutmut_24': xǁPQCCryptoǁdecrypt__mutmut_24
    }
    
    def decrypt(self, *args, **kwargs):
        result = _mutmut_trampoline(object.__getattribute__(self, "xǁPQCCryptoǁdecrypt__mutmut_orig"), object.__getattribute__(self, "xǁPQCCryptoǁdecrypt__mutmut_mutants"), args, kwargs, self)
        return result 
    
    decrypt.__signature__ = _mutmut_signature(xǁPQCCryptoǁdecrypt__mutmut_orig)
    xǁPQCCryptoǁdecrypt__mutmut_orig.__name__ = 'xǁPQCCryptoǁdecrypt'
