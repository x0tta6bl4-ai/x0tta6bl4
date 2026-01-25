
import unittest
from src.network.obfuscation.domain_fronting import DomainFrontingTransport

class TestDomainFronting(unittest.TestCase):
    def setUp(self):
        self.transport = DomainFrontingTransport(
            front_domain="allowed.com",
            backend_domain="hidden.com"
        )

    def test_obfuscate_format(self):
        data = b"Secret"
        obfuscated = self.transport.obfuscate(data)
        
        # Check structure
        self.assertIn(b"POST /data HTTP/1.1", obfuscated)
        self.assertIn(b"Host: hidden.com", obfuscated)
        self.assertIn(b"Content-Length: 6", obfuscated)
        self.assertIn(b"\r\n\r\nSecret", obfuscated)
        
    def test_deobfuscate(self):
        response = b"HTTP/1.1 200 OK\r\nContent-Length: 5\r\n\r\nReply"
        data = self.transport.deobfuscate(response)
        self.assertEqual(data, b"Reply")

if __name__ == '__main__':
    unittest.main()
