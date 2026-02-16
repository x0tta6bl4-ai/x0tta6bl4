"""Unit tests for libx0t secure chat demo helpers."""

from libx0t.examples.secure_chat import _decrypt, _encrypt, build_parser


def test_encrypt_decrypt_secure_roundtrip() -> None:
    message = b"hello"
    encrypted = _encrypt(message, secure=True)
    assert encrypted == b"ENC[hello]"
    assert _decrypt(encrypted) == message


def test_encrypt_insecure_passthrough() -> None:
    message = b"plain"
    encrypted = _encrypt(message, secure=False)
    assert encrypted == message
    assert _decrypt(encrypted) == message


def test_parser_has_listen_and_connect_modes() -> None:
    parser = build_parser()

    listen_args = parser.parse_args(["listen"])
    assert listen_args.mode == "listen"
    assert listen_args.host == "127.0.0.1"
    assert listen_args.port == 9090
    assert listen_args.once is False

    connect_args = parser.parse_args(["connect", "--message", "ping"])
    assert connect_args.mode == "connect"
    assert connect_args.host == "127.0.0.1"
    assert connect_args.port == 9090
    assert connect_args.message == "ping"
    assert connect_args.insecure is False

