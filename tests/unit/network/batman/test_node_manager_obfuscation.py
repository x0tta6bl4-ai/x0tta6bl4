import unittest
from unittest.mock import MagicMock

from src.network.batman.node_manager import NodeManager
from src.network.obfuscation.faketls import FakeTLSTransport
from src.network.obfuscation.simple import SimpleXORTransport


class TestNodeManagerObfuscation(unittest.TestCase):
    def setUp(self):
        self.nm = NodeManager(mesh_id="mesh-test", local_node_id="node-local")

    def test_heartbeat_no_obfuscation(self):
        # Default state (None)
        result = self.nm.send_heartbeat("node-target")
        self.assertTrue(result)
        # Logic doesn't crash, metric not inc (mock metric check implicit if we mocked it, but integration test verifies flow)

    def test_heartbeat_with_faketls(self):
        transport = FakeTLSTransport(sni="example.com")
        self.nm.obfuscation_transport = transport

        result = self.nm.send_heartbeat("node-target")
        self.assertTrue(result)

        # To verify it actually obfuscated, we can't easily check the internal var unless we mock the transport
        # Let's mock the transport to verify 'obfuscate' was called
        mock_transport = MagicMock()
        self.nm.obfuscation_transport = mock_transport

        self.nm.send_heartbeat("node-target-2")
        mock_transport.obfuscate.assert_called_once()

    def test_topology_update_with_xor(self):
        transport = SimpleXORTransport(key="secret")
        self.nm.obfuscation_transport = transport

        result = self.nm.send_topology_update("node-target", {"links": []})
        self.assertTrue(result)

        mock_transport = MagicMock()
        self.nm.obfuscation_transport = mock_transport
        self.nm.send_topology_update("node-target-2", {"links": []})
        mock_transport.obfuscate.assert_called_once()


if __name__ == "__main__":
    unittest.main()
