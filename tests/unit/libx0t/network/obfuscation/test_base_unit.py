import socket
from unittest.mock import MagicMock
import pytest
from libx0t.network.obfuscation.base import ObfuscationTransport, TransportManager

# --- Mock Implementation for ObfuscationTransport ---
class MockObfuscationTransport(ObfuscationTransport):
    def __init__(self, key: str = "default_key"):
        self.key = key
        self.wrapped_socket = None

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        self.wrapped_socket = sock
        return sock  # In a mock, we can just return the original or a mock of it

    def obfuscate(self, data: bytes) -> bytes:
        return b"obfuscated_" + data + b"_" + self.key.encode()

    def deobfuscate(self, data: bytes) -> bytes:
        return data.replace(b"obfuscated_", b"").replace(b"_" + self.key.encode(), b"")

class AnotherMockTransport(ObfuscationTransport):
    def __init__(self, config: str = "default_config"):
        self.config = config
        self.wrapped_socket = None

    def wrap_socket(self, sock: socket.socket) -> socket.socket:
        self.wrapped_socket = sock
        return sock

    def obfuscate(self, data: bytes) -> bytes:
        return b"another_obf_" + data

    def deobfuscate(self, data: bytes) -> bytes:
        return data.replace(b"another_obf_", b"")

# --- Tests for ObfuscationTransport (via Mock) ---
def test_mock_obfuscation_transport_implementation():
    """Verify mock implementation adheres to ABC and functions as expected."""
    transport = MockObfuscationTransport(key="test_key")
    assert isinstance(transport, ObfuscationTransport)

    mock_sock = MagicMock(spec=socket.socket)
    wrapped_sock = transport.wrap_socket(mock_sock)
    assert wrapped_sock is mock_sock
    assert transport.wrapped_socket is mock_sock

    original_data = b"hello world"
    obfuscated_data = transport.obfuscate(original_data)
    assert obfuscated_data == b"obfuscated_hello world_test_key"
    deobfuscated_data = transport.deobfuscate(obfuscated_data)
    assert deobfuscated_data == original_data

# --- Tests for TransportManager ---
class TestTransportManager:

    @pytest.fixture(autouse=True)
    def reset_transports(self):
        """Reset TransportManager._transports before each test to ensure isolation."""
        original_transports = TransportManager._transports.copy()
        TransportManager._transports = {}
        yield
        # Restore original transports after test completes
        TransportManager._transports = original_transports

    def test_register_transport(self):
        """Test that a transport class can be registered."""
        TransportManager.register("mock", MockObfuscationTransport)
        assert "mock" in TransportManager._transports
        assert TransportManager._transports["mock"] == MockObfuscationTransport

    def test_create_registered_transport(self):
        """Test creating an instance of a registered transport."""
        TransportManager.register("mock", MockObfuscationTransport)
        transport = TransportManager.create("mock", key="special")
        assert isinstance(transport, MockObfuscationTransport)
        assert transport.key == "special"

    def test_create_unregistered_transport(self):
        """Test that creating an unregistered transport returns None."""
        transport = TransportManager.create("non_existent_transport")
        assert transport is None

    def test_create_with_no_kwargs(self):
        """Test creating a transport without passing kwargs."""
        TransportManager.register("mock_no_kwargs", MockObfuscationTransport)
        transport = TransportManager.create("mock_no_kwargs")
        assert isinstance(transport, MockObfuscationTransport)
        assert transport.key == "default_key"  # Assumes default constructor behavior

    def test_register_multiple_transports(self):
        """Test registering and creating multiple different transports."""
        TransportManager.register("mock1", MockObfuscationTransport)
        TransportManager.register("mock2", AnotherMockTransport)

        transport1 = TransportManager.create("mock1", key="one")
        transport2 = TransportManager.create("mock2", config="cfg_two")

        assert isinstance(transport1, MockObfuscationTransport)
        assert transport1.key == "one"
        assert isinstance(transport2, AnotherMockTransport)
        assert transport2.config == "cfg_two"

    def test_register_overwrite(self):
        """Test that registering a new class with an existing name overwrites the old one."""
        TransportManager.register("mock", MockObfuscationTransport)
        assert TransportManager._transports["mock"] == MockObfuscationTransport
        
        TransportManager.register("mock", AnotherMockTransport)
        assert TransportManager._transports["mock"] == AnotherMockTransport
        
        transport = TransportManager.create("mock")
        assert isinstance(transport, AnotherMockTransport)
