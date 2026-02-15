import base64
import sys
import os
import argparse
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add project root to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'src')))

try:
    from security.post_quantum import LibOQSBackend, LIBOQS_AVAILABLE
except ImportError as e:
    logger.error(f"Failed to import LibOQSBackend: {e}. Ensure src is in PYTHONPATH and liboqs-python is installed.")
    sys.exit(1)

if not LIBOQS_AVAILABLE:
    logger.error("liboqs-python is not available. Real PQC signing/verification cannot be performed.")
    sys.exit(1)

class PQCSigner:
    def __init__(self, sig_algorithm: str = "ML-DSA-65"):
        self.pq_backend = LibOQSBackend(sig_algorithm=sig_algorithm)
        logger.info(f"PQC Signer backend initialized with {sig_algorithm}.")

    def generate_keypair(self):
        return self.pq_backend.generate_signature_keypair()

    def sign_data(self, data: bytes, private_key: bytes) -> str:
        """Подпись данных PQC ключом и возврат base64-кодированной подписи."""
        signature = self.pq_backend.sign(data, private_key)
        return base64.b64encode(signature).decode('utf-8')

    def verify_data(self, data: bytes, sig_b64: str, public_key: bytes) -> bool:
        """Верификация PQC подписи."""
        signature = base64.b64decode(sig_b64)
        return self.pq_backend.verify(data, signature, public_key)

def main():
    parser = argparse.ArgumentParser(description='x0tta6bl4 PQC Signer/Verifier')
    parser.add_argument('--algorithm', type=str, default="ML-DSA-65",
                        help='PQC Signature Algorithm (e.g., ML-DSA-65, Falcon-512)')

    subparsers = parser.add_subparsers(dest='command', help='Available commands')

    # Generate keys command
    parser_gen = subparsers.add_parser('generate-keys', help='Generate PQC key pair')
    parser_gen.add_argument('--only-private', action='store_true', help='Output only the private key in hex format')
    parser_gen.add_argument('--only-public', action='store_true', help='Output only the public key in hex format')

    # Sign command
    parser_sign = subparsers.add_parser('sign', help='Sign data from file or stdin')
    parser_sign.add_argument('--file', type=str, help='Path to file to sign')
    parser_sign.add_argument('--data', type=str, help='String data to sign')
    parser_sign.add_argument('--private-key', type=str, help='Hex-encoded private key for signing')

    # Verify command
    parser_verify = subparsers.add_parser('verify', help='Verify data against a signature')
    parser_verify.add_argument('--file', type=str, help='Path to file that was signed')
    parser_verify.add_argument('--data', type=str, help='String data that was signed')
    parser_verify.add_argument('--signature', type=str, required=True, help='Base64-encoded signature')
    parser_verify.add_argument('--public-key', type=str, required=True, help='Hex-encoded public key for verification')

    args = parser.parse_args()

    signer = PQCSigner(args.algorithm) # Always initialize signer backend

    if args.command == 'generate-keys':
        if args.only_private or args.only_public:
            logging.disable(logging.CRITICAL) # Disable logging for clean output
            
        keypair = signer.generate_keypair()
        if args.only_private:
            print(keypair.private_key.hex())
        elif args.only_public:
            print(keypair.public_key.hex())
        else:
            print(f"Algorithm: {args.algorithm}")
            print(f"Public Key (hex): {keypair.public_key.hex()}")
            print(f"Private Key (hex): {keypair.private_key.hex()}")
            print("NOTE: For production, secure storage of private keys is critical.")
        sys.exit(0)
    
    # Data to be signed/verified
    input_data = b''
    if args.file:
        try:
            with open(args.file, 'rb') as f:
                input_data = f.read()
        except FileNotFoundError:
            logger.error(f"File not found: {args.file}")
            sys.exit(1)
    elif args.data:
        input_data = args.data.encode('utf-8')
    else:
        if args.command in ['sign', 'verify']:
            logger.error("No data/file provided for signing or verification.")
            parser.print_help()
            sys.exit(1)

    if args.command == 'sign':
        if not args.private_key:
            logger.error("Private key must be provided with --private-key for signing.")
            sys.exit(1)
        private_key_bytes = bytes.fromhex(args.private_key)
        signed_data_b64 = signer.sign_data(input_data, private_key_bytes)
        print(signed_data_b64)
    elif args.command == 'verify':
        if not args.public_key:
            logger.error("Public key must be provided with --public-key for verification.")
            sys.exit(1)
        public_key_bytes = bytes.fromhex(args.public_key)
        is_valid = signer.verify_data(input_data, args.signature, public_key_bytes)
        print(f"Signature valid: {is_valid}")
        sys.exit(0 if is_valid else 1)
    else:
        parser.print_help()
        sys.exit(1)

if __name__ == "__main__":
    main()

