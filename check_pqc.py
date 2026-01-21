import sys
import os

# Add the src directory to the python path to allow importing the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

try:
    from src.security import post_quantum_liboqs
    print(f"LIBOQS_AVAILABLE = {post_quantum_liboqs.LIBOQS_AVAILABLE}")
    if post_quantum_liboqs.LIBOQS_AVAILABLE:
        print("Success: liboqs-python is installed and available.")
    else:
        print("Failure: liboqs-python is not available. The fallback/stub will be used.")
except Exception as e:
    print(f"An error occurred: {e}")
