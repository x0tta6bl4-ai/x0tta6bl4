"""Minimal secure chat demo over x0t tunnel primitives.

Run in two terminals:
1) python -m libx0t.examples.secure_chat listen --host 127.0.0.1 --port 9090
2) python -m libx0t.examples.secure_chat connect --host 127.0.0.1 --port 9090
"""

from __future__ import annotations

import argparse
import socket

from libx0t.core import Node
from libx0t.crypto import PQC


def _encrypt(data: bytes, secure: bool) -> bytes:
    if not secure:
        return data
    return b"ENC[" + data + b"]"


def _decrypt(data: bytes) -> bytes:
    if data.startswith(b"ENC[") and data.endswith(b"]"):
        return data[4:-1]
    return data


def run_listener(host: str, port: int, once: bool) -> int:
    """Start a tiny server that speaks the demo handshake and echoes payloads."""
    pqc = PQC()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind((host, port))
        server.listen(1)
        print(f"[listener] waiting on {host}:{port}")

        conn, addr = server.accept()
        with conn:
            print(f"[listener] peer connected: {addr[0]}:{addr[1]}")
            hello = conn.recv(1024)

            secure = False
            if hello == b"CLIENT_HELLO":
                secure = True
                public_key, private_key = pqc.generate_keypair()
                conn.sendall(public_key)
                ciphertext = conn.recv(4096)
                _ = pqc.decapsulate(ciphertext, private_key)
                print("[listener] pqc handshake complete")
            else:
                print("[listener] insecure mode")

            while True:
                payload = conn.recv(4096)
                if not payload:
                    break
                plaintext = _decrypt(payload)
                text = plaintext.decode("utf-8", errors="replace")
                print(f"[peer] {text}")

                reply = f"ACK: {text}".encode("utf-8")
                conn.sendall(_encrypt(reply, secure=secure))

                if once:
                    break

    return 0


def run_client(host: str, port: int, message: str | None, insecure: bool) -> int:
    """Connect to a listener and send one message or work interactively."""
    node = Node()
    tunnel = node.connect(f"{host}:{port}", secure=not insecure)
    print("[client] connected")

    try:
        if message is not None:
            tunnel.send(message.encode("utf-8"))
            response = _decrypt(tunnel.receive()).decode("utf-8", errors="replace")
            print(f"[listener] {response}")
            return 0

        while True:
            raw = input("message (or 'exit'): ").strip()
            if not raw or raw.lower() in {"exit", "quit"}:
                return 0

            tunnel.send(raw.encode("utf-8"))
            response = _decrypt(tunnel.receive()).decode("utf-8", errors="replace")
            print(f"[listener] {response}")
    finally:
        tunnel.close()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="x0t secure chat demo")
    sub = parser.add_subparsers(dest="mode", required=True)

    listen = sub.add_parser("listen", help="start listener")
    listen.add_argument("--host", default="127.0.0.1")
    listen.add_argument("--port", type=int, default=9090)
    listen.add_argument(
        "--once",
        action="store_true",
        help="handle exactly one message and exit",
    )

    connect = sub.add_parser("connect", help="connect to listener")
    connect.add_argument("--host", default="127.0.0.1")
    connect.add_argument("--port", type=int, default=9090)
    connect.add_argument("--message", help="single message mode")
    connect.add_argument(
        "--insecure",
        action="store_true",
        help="skip pqc handshake (for debug)",
    )

    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "listen":
        return run_listener(args.host, args.port, args.once)
    return run_client(args.host, args.port, args.message, args.insecure)


if __name__ == "__main__":
    raise SystemExit(main())

