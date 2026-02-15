
try:
    import oqs
    print("oqs imported successfully")
    print(f"Directory of oqs: {dir(oqs)}")
    if hasattr(oqs, 'KeyEncapsulation'):
        print("KeyEncapsulation found in oqs")
    else:
        try:
            from liboqs import KeyEncapsulation
            print("KeyEncapsulation imported from liboqs")
        except ImportError:
            print("KeyEncapsulation NOT found")

except ImportError as e:
    print(f"Failed to import oqs: {e}")
