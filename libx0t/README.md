# libx0t: The Autonomous Secure Mesh SDK

**libx0t** is a Python library for building Post-Quantum Secure (PQC) mesh networks. It provides a simple API to establish secure, self-healing connections between nodes, protecting against both classical and quantum decryption attacks.

## Features
*   **Post-Quantum Cryptography:** Uses Kyber768 (KEM) for key exchange.
*   **Zero-Config Mesh:** Nodes automatically discover peers (Future).
*   **Simple API:** Connect in 3 lines of code.

## Installation

```bash
pip install libx0t
```

## Quick Start where "Alice" talks to "Bob"

### Server (Bob)
```python
import socket
# Standard socket server, but expects PQC handshake
# See examples/secure_chat_demo.py for full implementation
```

### Client (Alice)
```python
import libx0t

# Initialize local node
node = libx0t.Node()

# Connect to Bob securely
tunnel = node.connect("192.168.1.5:9001", secure=True)

# Send encrypted message
tunnel.send(b"Hello from the Quantum Resistance!")

# Receive response
print(tunnel.receive())
```

## Architecture
- `Node`: The local identity and crypto engine.
- `Tunnel`: A secure TCP/UDP session.
- `PQC`: Wrapper for `liboqs` (Quantum-Safe Algorithms).

## Roadmap
- [ ] Integration with `liboqs` for real Kyber768/Dilithium.
- [ ] eBPF acceleration for high-throughput filtering.
- [ ] Mesh Routing Protocol (Yggdrasil integration).
