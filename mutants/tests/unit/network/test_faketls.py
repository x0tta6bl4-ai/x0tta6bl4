
import unittest
import struct
from src.network.obfuscation.faketls import FakeTLSTransport

class TestFakeTLS(unittest.TestCase):
    def setUp(self):
        self.transport = FakeTLSTransport(sni="cloudflare.com")

    def test_client_hello_structure(self):
        hello = self.transport.generate_client_hello()
        
        # Check TLS Record Header
        content_type, version, length = struct.unpack("!BHH", hello[:5])
        self.assertEqual(content_type, 0x16) # Handshake
        self.assertEqual(version, 0x0301)    # TLS 1.0 legacy version
        self.assertEqual(length, len(hello) - 5)
        
        # Check Handshake Header
        msg_type = hello[5]
        self.assertEqual(msg_type, 0x01)     # ClientHello
        
        # Check SNI presence
        self.assertIn(b"cloudflare.com", hello)

    def test_app_data_obfuscation(self):
        payload = b"Sensitive Data"
        obfuscated = self.transport.obfuscate(payload)
        
        # Check TLS Record Header
        content_type, version, length = struct.unpack("!BHH", obfuscated[:5])
        self.assertEqual(content_type, 0x17) # Application Data
        self.assertEqual(version, 0x0303)    # TLS 1.2 legacy version
        self.assertEqual(length, len(payload))
        
        # Check payload
        self.assertEqual(obfuscated[5:], payload)

    def test_deobfuscate_full_record(self):
        payload = b"Hidden"
        obfuscated = self.transport.obfuscate(payload)
        deobfuscated = self.transport.deobfuscate(obfuscated)
        self.assertEqual(deobfuscated, payload)

if __name__ == '__main__':
    unittest.main()
