import socket
from unittest.mock import MagicMock, call
import pytest
from libx0t.network.obfuscation.simple import XORSocket, SimpleXORTransport
from libx0t.network.obfuscation.base import ObfuscationTransport, TransportManager

# Fixture for a mock socket
@pytest.fixture
def mock_socket():
    sock = MagicMock(spec=socket.socket)
    sock.fileno.return_value = 123
    sock.gettimeout.return_value = None  # Default no timeout
    sock.getsockname.return_value = ("127.0.0.1", 12345) # Mock a return value for getsockname
    return sock

class TestXORSocket:
    """Tests for the XORSocket class."""

    def test_xor_method(self):
        """Test the internal _xor method with various inputs."""
        key = b"abc"
        xor_socket = XORSocket(MagicMock(spec=socket.socket), key)

        # Test with data shorter than key
        assert xor_socket._xor(b"12") == bytes([ord('1')^ord('a'), ord('2')^ord('b')])

        # Test with data longer than key
        assert xor_socket._xor(b"12345") == bytes([
            ord('1')^ord('a'), ord('2')^ord('b'), ord('3')^ord('c'),
            ord('4')^ord('a'), ord('5')^ord('b')
        ])

        # Test with empty data
        assert xor_socket._xor(b"") == b""

        # Test with non-ASCII data
        assert xor_socket._xor(b"\x01\x02\x03") == bytes([1^ord('a'), 2^ord('b'), 3^ord('c')])

    def test_xorsocket_init(self, mock_socket):
        """Test XORSocket initialization."""
        key = b"testkey"
        xor_socket = XORSocket(mock_socket, key)

        assert xor_socket._sock == mock_socket
        assert xor_socket._key == key
        assert xor_socket._key_len == len(key)
        assert xor_socket.timeout is None  # From mock_socket.gettimeout()

        # Test that fileno is copied
        assert xor_socket.fileno() == mock_socket.fileno.return_value

    def test_send_calls_xor_and_sock_send(self, mock_socket):
        """Verify send method XORs data and calls underlying socket's send."""
        key = b"k"
        xor_socket = XORSocket(mock_socket, key)
        original_data = b"hello"
        expected_xored_data = xor_socket._xor(original_data) # Use actual _xor for expected

        xor_socket.send(original_data)

        mock_socket.send.assert_called_once_with(expected_xored_data, 0)
    
    def test_send_with_flags_calls_xor_and_sock_send(self, mock_socket):
        """Verify send method XORs data and calls underlying socket's send with flags."""
        key = b"k"
        xor_socket = XORSocket(mock_socket, key)
        original_data = b"hello"
        flags = socket.MSG_OOB
        expected_xored_data = xor_socket._xor(original_data)

        xor_socket.send(original_data, flags)

        mock_socket.send.assert_called_once_with(expected_xored_data, flags)

    def test_recv_calls_sock_recv_and_xor(self, mock_socket):
        """Verify recv method calls underlying socket's recv and then XORs data."""
        key = b"k"
        xor_socket = XORSocket(mock_socket, key)
        received_xored_data = b"\x01\x02\x03" # Example data that _sock.recv would return
        expected_de_xored_data = xor_socket._xor(received_xored_data) # XOR is symmetric

        mock_socket.recv.return_value = received_xored_data

        result = xor_socket.recv(1024)

        mock_socket.recv.assert_called_once_with(1024, 0)
        assert result == expected_de_xored_data

    def test_recv_with_flags_calls_sock_recv_and_xor(self, mock_socket):
        """Verify recv method calls underlying socket's recv with flags and then XORs data."""
        key = b"k"
        xor_socket = XORSocket(mock_socket, key)
        received_xored_data = b"\x01\x02\x03"
        expected_de_xored_data = xor_socket._xor(received_xored_data)
        flags = socket.MSG_WAITALL

        mock_socket.recv.return_value = received_xored_data

        result = xor_socket.recv(1024, flags)

        mock_socket.recv.assert_called_once_with(1024, flags)
        assert result == expected_de_xored_data

    def test_close_calls_sock_close(self, mock_socket):
        """Verify close method calls underlying socket's close."""
        key = b"k"
        xor_socket = XORSocket(mock_socket, key)
        xor_socket.close()
        mock_socket.close.assert_called_once()

    def test_getattr_delegation(self, mock_socket):
        """Test that other attributes/methods are delegated to the underlying socket."""
        key = b"k"
        xor_socket = XORSocket(mock_socket, key)

        # Test delegation of an actual socket method
        # Store the expected return value from the mock directly
        expected_name = mock_socket.getsockname.return_value
        # Call the method on the XORSocket
        actual_name = xor_socket.getsockname()
        # Assert the mock was called once by the XORSocket and the result matches
        mock_socket.getsockname.assert_called_once()
        assert actual_name == expected_name

class TestSimpleXORTransport:
    """Tests for the SimpleXORTransport class."""

    def test_init_encodes_key(self):
        """Test that the key is correctly encoded to bytes."""
        transport = SimpleXORTransport(key="mykey")
        assert transport.key == b"mykey"

    def test_init_default_key(self):
        """Test default key encoding."""
        transport = SimpleXORTransport()
        assert transport.key == b"x0tta6bl4"

    def test_wrap_socket_returns_xorsocket(self, mock_socket):
        """Verify wrap_socket returns an XORSocket."""
        transport = SimpleXORTransport(key="wrap_key")
        wrapped_sock = transport.wrap_socket(mock_socket)

        assert isinstance(wrapped_sock, XORSocket)
        # Check if the XORSocket was initialized with the correct underlying socket and key
        assert wrapped_sock._sock == mock_socket
        assert wrapped_sock._key == b"wrap_key"

    def test_obfuscate_and_deobfuscate_symmetry(self):
        """Test that obfuscate and deobfuscate are symmetric."""
        transport = SimpleXORTransport(key="sym_key")
        original_data = b"some data to obfuscate"

        obfuscated_data = transport.obfuscate(original_data)
        deobfuscated_data = transport.deobfuscate(obfuscated_data)

        assert original_data != obfuscated_data  # Should actually obfuscate
        assert deobfuscated_data == original_data

    def test_obfuscate_matches_xorsocket_xor(self):
        """Verify that SimpleXORTransport's obfuscate method works like XORSocket's _xor."""
        key = b"match"
        transport = SimpleXORTransport(key="match")
        xor_socket = XORSocket(MagicMock(spec=socket.socket), key) # Dummy XORSocket

        data = b"compare this"
        assert transport.obfuscate(data) == xor_socket._xor(data)

    def test_register_with_transport_manager(self):
        """Test that SimpleXORTransport can be registered and created via TransportManager."""
        TransportManager.register("simple_xor", SimpleXORTransport)
        
        # Test creation with default key
        transport_default = TransportManager.create("simple_xor")
        assert isinstance(transport_default, SimpleXORTransport)
        assert transport_default.key == b"x0tta6bl4"

        # Test creation with custom key
        transport_custom = TransportManager.create("simple_xor", key="custom_xor_key")
        assert isinstance(transport_custom, SimpleXORTransport)
        assert transport_custom.key == b"custom_xor_key"

        # Clean up to avoid affecting other tests
        del TransportManager._transports["simple_xor"]
