import unittest

from src.network.obfuscation.shadowsocks import ShadowsocksTransport


class TestShadowsocks(unittest.TestCase):
    def test_encrypt_decrypt(self):
        transport = ShadowsocksTransport(password="secret")
        data = b"Sensitive Data"

        encrypted = transport.obfuscate(data)
        self.assertNotEqual(data, encrypted)
        # Check salt (32) + nonce (12) + tag (16) + data
        self.assertEqual(len(encrypted), 32 + 12 + len(data) + 16)

        decrypted = transport.deobfuscate(encrypted)
        self.assertEqual(data, decrypted)

    def test_different_keys(self):
        t1 = ShadowsocksTransport(password="key1")
        t2 = ShadowsocksTransport(password="key2")

        data = b"Test"
        encrypted = t1.obfuscate(data)

        # Should fail
        with self.assertRaises(Exception):
            t2.deobfuscate(encrypted)


if __name__ == "__main__":
    unittest.main()
