
try:
    import oqs
    print("oqs imported successfully")
    
    # Try different ways to access KeyEncapsulation
    KeyEncapsulation = getattr(oqs, 'KeyEncapsulation', None)
    if not KeyEncapsulation:
        try:
            from liboqs import KeyEncapsulation
        except ImportError:
            print("KeyEncapsulation import failed")
            exit(1)

    print(f"KeyEncapsulation: {KeyEncapsulation}")
    
    # Try getting enabled mechanisms
    try:
        if hasattr(oqs, 'get_enabled_KEM_mechanisms'):
             print(f"KEMs: {oqs.get_enabled_KEM_mechanisms()}")
        elif hasattr(KeyEncapsulation, 'get_enabled_KEM_mechanisms'):
             print(f"KEMs (class): {KeyEncapsulation.get_enabled_KEM_mechanisms()}")
        else:
             print("Cannot find get_enabled_KEM_mechanisms")
    except Exception as e:
        print(f"Error getting mechanisms: {e}")

    # Try instantiating ML-KEM-768
    try:
        kem = KeyEncapsulation("ML-KEM-768")
        print("ML-KEM-768 instantiated successfully")
    except Exception as e:
        print(f"Failed to instantiate ML-KEM-768: {e}")
        # Try legacy name
        try:
            kem = KeyEncapsulation("Kyber768")
            print("Kyber768 instantiated successfully")
        except Exception as e2:
            print(f"Failed to instantiate Kyber768: {e2}")

except Exception as e:
    print(f"Overall failure: {e}")
