
import unittest
import socket
from src.network.obfuscation.simple import SimpleXORTransport

class TestObfuscation(unittest.TestCase):
    def test_xor_symmetric(self):
        transport = SimpleXORTransport(key="secret")
        original = b"Hello World"
        obfuscated = transport.obfuscate(original)
        self.assertNotEqual(original, obfuscated)
        self.assertEqual(original, transport.deobfuscate(obfuscated))
        
    def test_transport_manager(self):
        from src.network.obfuscation import TransportManager
        t = TransportManager.create("xor", key="test")
        self.assertIsNotNone(t)
        self.assertIsInstance(t, SimpleXORTransport)

if __name__ == '__main__':
    unittest.main()
