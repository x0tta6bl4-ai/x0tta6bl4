
try:
    from oqs import Signature
    sig = Signature("Dilithium3")
    pub = sig.generate_keypair()
    msg = b"test message"
    signature = sig.sign(msg)
    
    # Try verify with 2 args (stateful?)
    try:
        if sig.verify(msg, signature):
             print("Success: verify(msg, signature)")
        else:
             print("Failed: verify(msg, signature) returned False")
    except Exception as e:
        print(f"Failed verify(msg, signature): {e}")

    # Try verify with 3 args (stateless?)
    try:
        sig2 = Signature("Dilithium3")
        # sig2 has no keys set initially
        if sig2.verify(msg, signature, pub):
             print("Success: verify(msg, signature, pub)")
        else:
             print("Failed: verify(msg, signature, pub) returned False")
    except Exception as e:
        print(f"Failed verify(msg, signature, pub): {e}")

except Exception as e:
    print(f"Error: {e}")
