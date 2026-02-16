
from oqs import Signature
try:
    s1 = Signature("ML-DSA-65")
    print("ML-DSA-65 available")
    name1 = "ML-DSA-65"
except:
    print("ML-DSA-65 NOT available")
    name1 = None

try:
    s2 = Signature("Dilithium3")
    print("Dilithium3 available")
    name2 = "Dilithium3"
except:
    print("Dilithium3 NOT available")
    name2 = None

if name1 and name2:
    msg = b"test"
    sig1 = Signature(name1)
    pub1 = sig1.generate_keypair()
    sign1 = sig1.sign(msg)
    
    # Try verifying with name2
    verifier = Signature(name2)
    try:
        if verifier.verify(msg, sign1, pub1):
            print(f"{name2} verified {name1} signature")
        else:
            print(f"{name2} FAILED to verify {name1} signature")
    except Exception as e:
        print(f"Error verifying: {e}")
