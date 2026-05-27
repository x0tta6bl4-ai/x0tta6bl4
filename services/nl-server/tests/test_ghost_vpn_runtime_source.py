#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from collections import defaultdict, deque
from enum import Enum, IntEnum
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ObfuscationProfile(Enum):
    SRTP = "srtp"
    DNS = "dns"
    STEAM = "steam"


class MsgType(IntEnum):
    HANDSHAKE_INIT = 1
    HANDSHAKE_RESP = 2
    HANDSHAKE_COOKIE = 3
    DATA = 4
    PING = 5
    PONG = 6
    STRATEGY_SYNC = 7
    STRATEGY_ACK = 8
    PROFILE_SWITCH = 9
    PROFILE_SWITCH_ACK = 10
    DISCONNECT = 11


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def install_runtime_stubs() -> dict[str, types.ModuleType | None]:
    names = [
        "src",
        "src.network",
        "src.network.ghost_vpn_protocol",
        "src.network.transport",
        "src.network.transport.ghost_handshake",
        "src.network.transport.ghost_proto",
        "src.network.tun_handler",
        "src.self_healing",
        "src.self_healing.rpc_bridge",
        "src.self_healing.mape_k",
        "src.anti_censorship",
        "src.anti_censorship.ghost_vpn_adapter",
    ]
    old_modules = {name: sys.modules.get(name) for name in names}

    src = types.ModuleType("src")
    src.__path__ = []
    network = types.ModuleType("src.network")
    network.__path__ = []
    transport = types.ModuleType("src.network.transport")
    transport.__path__ = []
    self_healing = types.ModuleType("src.self_healing")
    self_healing.__path__ = []
    anti_censorship = types.ModuleType("src.anti_censorship")
    anti_censorship.__path__ = []

    protocol = types.ModuleType("src.network.ghost_vpn_protocol")
    protocol.AUTH_TAG_SIZE = 32
    protocol.COOKIE_ROTATION_SECONDS = 30
    protocol.MsgType = MsgType
    protocol.PROFILE_TO_ID = {
        ObfuscationProfile.SRTP: 1,
        ObfuscationProfile.DNS: 2,
        ObfuscationProfile.STEAM: 3,
    }
    protocol.IPPool = DummyIPPool
    protocol.SessionManager = DummySessionManager
    protocol.compute_handshake_auth_tag = lambda *args, **kwargs: b"a" * 32
    protocol.load_auth_key = lambda key=None: key if isinstance(key, bytes) else b"k" * 32
    protocol.pack_handshake_cookie = lambda cookie: cookie
    protocol.pack_handshake_init = lambda client_pub_key, profile, cookie=b"": client_pub_key + cookie
    protocol.pack_handshake_resp = lambda *args, **kwargs: b"handshake-resp"
    protocol.pack_ping = lambda seq: int(seq).to_bytes(4, "big")
    protocol.pack_profile_switch = lambda profile, reason="": f"{profile}:{reason}".encode()
    protocol.pack_profile_switch_ack = lambda profile, latency_ms=0.0: f"{profile}:{latency_ms}".encode()
    protocol.pack_protected_msg = lambda auth_key, msg_type, payload: bytes([int(msg_type)]) + payload
    protocol.pack_strategy_sync = lambda strategy: b"strategy"
    protocol.unpack_handshake_cookie = lambda payload: payload
    protocol.unpack_handshake_init = lambda payload: (ObfuscationProfile.SRTP, b"", b"client")
    protocol.unpack_handshake_resp = lambda payload: (
        b"ciphertext",
        "10.8.0.2",
        ObfuscationProfile.SRTP,
        b"a" * 32,
    )
    protocol.unpack_ping = lambda payload: int.from_bytes(payload[:4] or b"\0\0\0\0", "big")
    protocol.unpack_profile_switch = lambda payload: ("dns", "dpi_detected")
    protocol.unpack_profile_switch_ack = lambda payload: ("dns", 1.0)
    protocol.unpack_protected_msg = lambda auth_key, data: (None, b"")
    protocol.unpack_strategy_sync = lambda payload: ("strategy-id", {})

    ghost_proto = types.ModuleType("src.network.transport.ghost_proto")
    ghost_proto.ObfuscationProfile = ObfuscationProfile
    ghost_proto.GhostTransport = DummyGhostTransport

    ghost_handshake = types.ModuleType("src.network.transport.ghost_handshake")
    ghost_handshake.GhostHandshake = DummyGhostHandshake

    tun_handler = types.ModuleType("src.network.tun_handler")
    tun_handler.TUNInterface = DummyTUNInterface
    tun_handler.IPPacketParser = DummyIPPacketParser

    rpc_bridge = types.ModuleType("src.self_healing.rpc_bridge")
    rpc_bridge.MeshRPCBridge = DummyMeshRPCBridge
    rpc_bridge.HealingEvent = DummyHealingEvent
    rpc_bridge.ProfileHint = DummyProfileHint

    mapek = types.ModuleType("src.self_healing.mape_k")
    mapek.MAPEKMonitor = DummyMAPEKMonitor
    mapek.MAPEKAnalyzer = DummyMAPEKAnalyzer
    mapek.MAPEKPlanner = DummyMAPEKPlanner
    mapek.MAPEKExecutor = DummyMAPEKExecutor
    mapek.MAPEKKnowledge = DummyMAPEKKnowledge

    adapter = types.ModuleType("src.anti_censorship.ghost_vpn_adapter")
    adapter.GhostVPNEvolutionAdapter = None

    for module in (
        src,
        network,
        protocol,
        transport,
        ghost_handshake,
        ghost_proto,
        tun_handler,
        self_healing,
        rpc_bridge,
        mapek,
        anti_censorship,
        adapter,
    ):
        sys.modules[module.__name__] = module

    return old_modules


def restore_modules(old_modules: dict[str, types.ModuleType | None]) -> None:
    for name, module in old_modules.items():
        if module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = module


class DummyIPPool:
    available = 253

    def __init__(self, subnet: str = "10.8.0") -> None:
        self.subnet = subnet


class DummySessionManager:
    def __init__(self, ip_pool=None, session_timeout: int = 120) -> None:
        self.ip_pool = ip_pool or DummyIPPool()
        self.session_timeout = session_timeout
        self.sessions = {}
        self.active_count = 0

    def cleanup_expired(self):
        return []

    def get_session(self, addr):
        return None

    def get_session_by_ip(self, ip_addr):
        return None


class DummyGhostTransport:
    def __init__(self, shared_secret: bytes = b"", profile: ObfuscationProfile = ObfuscationProfile.SRTP) -> None:
        self.profile = profile

    def get_send_socket_ttl(self):
        return 64

    def wrap_packet(self, packet: bytes, is_reliable: bool = False):
        return packet

    def unwrap_packet(self, packet: bytes):
        return [packet]

    def apply_negotiated_strategy(self, strategy, auth_key):
        return None


class DummyGhostHandshake:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def client_init(self):
        return b"pub", b"priv"

    def client_final(self, ciphertext, private_key):
        return b"shared"

    def server_respond(self, client_pub_key):
        return b"ciphertext", b"shared"


class DummyTUNInterface:
    def __init__(self, *args, **kwargs) -> None:
        self.is_up = False

    async def create(self):
        self.is_up = True
        return True

    async def set_address(self, address):
        return None

    async def read_packet(self):
        return b""

    def write_packet_sync(self, packet):
        return None

    def close(self):
        self.is_up = False


class DummyIPPacketParser:
    @staticmethod
    def parse(packet):
        return None


class DummyMeshRPCBridge:
    def __init__(self, *args, **kwargs) -> None:
        self.node_id = "dummy"
        self.event_history = []

    def on_event(self, callback):
        return None

    async def handle_rpc_request(self, payload):
        return {"ok": True}

    def get_best_profile(self):
        return None


class DummyHealingEvent:
    pass


class DummyProfileHint:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs

    def model_dump(self):
        return dict(self.kwargs)


class DummyMAPEKKnowledge:
    def record(self, *args, **kwargs):
        return None


class DummyMAPEKMonitor:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def check(self, metrics):
        return {"anomaly_detected": False}


class DummyMAPEKAnalyzer:
    pass


class DummyMAPEKPlanner:
    def __init__(self, *args, **kwargs) -> None:
        pass

    def plan(self, issue):
        return "observe"


class DummyMAPEKExecutor:
    def __init__(self, *args, **kwargs) -> None:
        self.callback = None

    def set_switch_profile_callback(self, callback):
        self.callback = callback

    def execute(self, action, context):
        return True


class GhostVpnRuntimeSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.old_modules = install_runtime_stubs()
        cls.server = load_module(
            "ghost_vpn_server_runtime_test",
            ROOT / "ghost-vpn" / "ghost_vpn_server.py",
        )
        cls.client = load_module(
            "ghost_vpn_client_runtime_test",
            ROOT / "ghost-vpn" / "ghost_vpn_client.py",
        )

    @classmethod
    def tearDownClass(cls) -> None:
        restore_modules(cls.old_modules)

    def test_server_handshake_rate_limit_window(self) -> None:
        server = object.__new__(self.server.GhostVPNServer)
        server.handshake_rate_limit = 2
        server.handshake_rate_window = 10.0
        server._handshake_attempts = defaultdict(deque)

        self.assertTrue(server._allow_handshake(("203.0.113.10", 1111), now=100.0))
        self.assertTrue(server._allow_handshake(("203.0.113.10", 2222), now=101.0))
        self.assertFalse(server._allow_handshake(("203.0.113.10", 3333), now=102.0))
        self.assertTrue(server._allow_handshake(("203.0.113.10", 4444), now=112.0))

    def test_server_cookie_context_is_stable_and_addr_bound(self) -> None:
        context_a = self.server.GhostVPNServer._cookie_context(
            ("203.0.113.10", 4433),
            ObfuscationProfile.SRTP,
            b"client-public",
        )
        context_b = self.server.GhostVPNServer._cookie_context(
            ("203.0.113.11", 4433),
            ObfuscationProfile.SRTP,
            b"client-public",
        )

        self.assertEqual(context_a, self.server.GhostVPNServer._cookie_context(
            ("203.0.113.10", 4433),
            ObfuscationProfile.SRTP,
            b"client-public",
        ))
        self.assertNotEqual(context_a, context_b)
        self.assertIn(b"203.0.113.10", context_a)

    def test_client_route_helpers_are_pure_for_ip_inputs(self) -> None:
        client = object.__new__(self.client.GhostVPNClient)
        client.assigned_ip = "10.8.0.42"
        client.server_addr = ("198.51.100.7", 4433)

        self.assertEqual(client._vpn_gateway(), "10.8.0.1")
        self.assertEqual(client._server_route_target(), "198.51.100.7")

    def test_client_next_profile_wraps_safely(self) -> None:
        self.assertEqual(self.client._next_profile_idx(0, 3), 1)
        self.assertEqual(self.client._next_profile_idx(2, 3), 0)
        self.assertEqual(self.client._next_profile_idx(9, 0), 0)

    def test_tcp_transport_frames_datagrams(self) -> None:
        writer = FakeWriter()
        transport = self.client.GhostTCPTransport(
            reader=object(),
            writer=writer,
            protocol=object(),
        )

        transport.sendto(b"payload")

        self.assertEqual(writer.chunks, [b"\x00\x07payload"])


class FakeWriter:
    def __init__(self) -> None:
        self.chunks: list[bytes] = []
        self.closed = False

    def is_closing(self) -> bool:
        return self.closed

    def write(self, data: bytes) -> None:
        self.chunks.append(data)

    def close(self) -> None:
        self.closed = True

    def get_extra_info(self, name, default=None):
        return default


if __name__ == "__main__":
    unittest.main()
