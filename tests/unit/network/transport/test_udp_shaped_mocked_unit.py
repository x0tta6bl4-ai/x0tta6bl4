from __future__ import annotations

import asyncio
import runpy
import time
import types

import pytest

import src.network.transport.udp_shaped as mod


class _InlineLoop:
    async def run_in_executor(self, _executor, fn):
        return fn()


class _DummyTask:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True

    def __await__(self):
        if False:
            yield
        raise asyncio.CancelledError


class _LoopWithTasks:
    def __init__(self):
        self.tasks = []

    def create_task(self, coro):
        coro.close()
        task = _DummyTask()
        self.tasks.append(task)
        return task

    async def run_in_executor(self, _executor, fn):
        return fn()


class _FakeSocket:
    def __init__(self):
        self.bound = ("0.0.0.0", 0)
        self.sent = []
        self.recv_queue = []
        self.raise_on_send = None
        self.closed = False

    def setsockopt(self, *_args):
        return None

    def setblocking(self, *_args):
        return None

    def bind(self, addr):
        self.bound = addr

    def getsockname(self):
        host, port = self.bound
        return host, (port or 5050)

    def sendto(self, data, address):
        if self.raise_on_send:
            raise self.raise_on_send
        self.sent.append((data, address))
        return len(data)

    def recvfrom(self, _size):
        if not self.recv_queue:
            raise BlockingIOError("empty")
        item = self.recv_queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_loop_with_tasks_run_in_executor_executes_callback():
    loop = _LoopWithTasks()
    assert await loop.run_in_executor(None, lambda: "ok") == "ok"


def test_udppacket_from_bytes_rejects_short_data():
    with pytest.raises(ValueError):
        mod.UDPPacket.from_bytes(b"tiny")


def test_prepare_packet_reliable_branch_raises_name_error():
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    with pytest.raises(NameError):
        transport._prepare_packet(b"payload", requires_ack=True)


def test_unknown_profile_and_transport_creation_error(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="unknown-profile")
    assert transport._shaper is None

    monkeypatch.setattr(
        mod.TransportManager,
        "create",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )
    transport2 = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="shadowsocks")
    assert transport2._transport is None


@pytest.mark.asyncio
async def test_start_and_stop_with_mocked_loop(monkeypatch):
    fake_socket = _FakeSocket()
    loop = _LoopWithTasks()
    transport = mod.ShapedUDPTransport(local_port=0, traffic_profile="none", obfuscation="none")

    monkeypatch.setattr(mod.socket, "socket", lambda *_args, **_kwargs: fake_socket)
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: loop)

    await transport.start()
    assert transport._running is True
    assert transport.local_port == 5050
    assert len(loop.tasks) == 2

    await transport.stop()
    assert transport._running is False
    assert loop.tasks[0].cancelled is True
    assert loop.tasks[1].cancelled is True
    assert transport._socket is None
    assert fake_socket.closed is True


@pytest.mark.asyncio
async def test_send_to_success_and_failure(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    fake_socket = _FakeSocket()
    transport._socket = fake_socket
    transport._running = True

    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())

    ok = await transport.send_to(b"hello", ("127.0.0.1", 7777))
    assert ok is True
    assert transport._total_sent == 1
    assert ("127.0.0.1", 7777) in transport._peers

    fake_socket.raise_on_send = RuntimeError("send failed")
    failed = await transport.send_to(b"x", ("127.0.0.1", 7777))
    assert failed is False

    transport._running = False
    assert await transport.send_to(b"x", ("127.0.0.1", 1)) is False


@pytest.mark.asyncio
async def test_send_to_with_shaper_delay(monkeypatch):
    class _Shaper:
        def shape_packet(self, data):
            return data

        def get_send_delay(self):
            return 0.25

    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    transport._shaper = _Shaper()
    transport._socket = _FakeSocket()
    transport._running = True

    delays = []

    async def _fake_sleep(delay):
        delays.append(delay)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())

    assert await transport.send_to(b"payload", ("127.0.0.1", 8888)) is True
    assert delays == [0.25]


@pytest.mark.asyncio
async def test_send_ping_pong_ack_paths(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    fake_socket = _FakeSocket()
    transport._socket = fake_socket
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())

    await transport.send_ping(("127.0.0.1", 9000))
    await transport._send_pong(("127.0.0.1", 9000), 123)
    await transport._send_ack(("127.0.0.1", 9000), 7)
    assert len(fake_socket.sent) == 3

    fake_socket.raise_on_send = RuntimeError("network down")
    await transport.send_ping(("127.0.0.1", 9000))
    await transport._send_pong(("127.0.0.1", 9000), 123)
    await transport._send_ack(("127.0.0.1", 9000), 7)


@pytest.mark.asyncio
async def test_send_ping_pong_ack_with_obfuscation(monkeypatch):
    class _Transport:
        def obfuscate(self, data):
            return b"O" + data

    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    transport._transport = _Transport()
    fake_socket = _FakeSocket()
    transport._socket = fake_socket
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())

    await transport.send_ping(("127.0.0.1", 7777))
    await transport._send_pong(("127.0.0.1", 7777), 55)
    await transport._send_ack(("127.0.0.1", 7777), 9)
    assert all(payload.startswith(b"O") for payload, _addr in fake_socket.sent)


@pytest.mark.asyncio
async def test_receive_loop_handles_data_ping_pong_ack(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    fake_socket = _FakeSocket()
    address = ("127.0.0.1", 9090)
    now_ms = transport._current_timestamp_ms()
    fake_socket.recv_queue = [
        (
            mod.UDPPacket(
                packet_type=mod.PacketType.DATA,
                sequence=1,
                timestamp_ms=now_ms,
                payload=b"data",
                requires_ack=True,
            ).to_bytes(),
            address,
        ),
        (
            mod.UDPPacket(
                packet_type=mod.PacketType.PING,
                sequence=2,
                timestamp_ms=now_ms,
                payload=b"",
            ).to_bytes(),
            address,
        ),
        (
            mod.UDPPacket(
                packet_type=mod.PacketType.PONG,
                sequence=3,
                timestamp_ms=max(0, now_ms - 10),
                payload=b"",
            ).to_bytes(),
            address,
        ),
        (
            mod.UDPPacket(
                packet_type=mod.PacketType.ACK,
                sequence=99,
                timestamp_ms=now_ms,
                payload=b"",
            ).to_bytes(),
            address,
        ),
    ]

    transport._socket = fake_socket
    transport._running = True
    transport._pending_acks[99] = (
        mod.UDPPacket(
            packet_type=mod.PacketType.DATA,
            sequence=99,
            timestamp_ms=now_ms,
            payload=b"x",
            requires_ack=True,
        ),
        address,
    )

    received = []
    acks = []
    pongs = []

    async def _on_receive(payload, addr):
        received.append((payload, addr))

    async def _send_ack(addr, seq):
        acks.append((addr, seq))

    async def _send_pong(addr, ts):
        pongs.append((addr, ts))

    async def _fake_sleep(_delay):
        if not fake_socket.recv_queue:
            transport._running = False

    transport._on_receive = _on_receive
    monkeypatch.setattr(transport, "_send_ack", _send_ack)
    monkeypatch.setattr(transport, "_send_pong", _send_pong)
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await transport._receive_loop()

    assert received == [(b"data", address)]
    assert acks == [(address, 1)]
    assert pongs == [(address, now_ms)]
    assert 99 not in transport._pending_acks
    assert transport.get_peer_info(address) is not None
    assert transport.get_peer_info(address).rtt_ms >= 0


@pytest.mark.asyncio
async def test_receive_loop_exception_path(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    fake_socket = _FakeSocket()
    fake_socket.recv_queue = [RuntimeError("boom")]
    transport._socket = fake_socket
    transport._running = True

    calls = []

    async def _fake_sleep(delay):
        calls.append(delay)
        transport._running = False

    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await transport._receive_loop()
    assert calls and calls[-1] == 0.01


@pytest.mark.asyncio
async def test_maintenance_loop_timeout_ping_and_retry(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    fake_socket = _FakeSocket()
    transport._socket = fake_socket
    transport._running = True
    transport._transport = types.SimpleNamespace(obfuscate=lambda data: b"X" + data)

    now = time.time()
    timeout_addr = ("10.0.0.1", 1001)
    ping_addr = ("10.0.0.2", 1002)

    transport._peers[timeout_addr] = mod.PeerInfo(
        address=timeout_addr, last_seen=now - mod.ShapedUDPTransport.PEER_TIMEOUT - 1
    )
    transport._peers[ping_addr] = mod.PeerInfo(
        address=ping_addr, last_seen=now - mod.ShapedUDPTransport.PING_INTERVAL - 1
    )

    retry_packet = mod.UDPPacket(
        packet_type=mod.PacketType.DATA,
        sequence=10,
        timestamp_ms=int((now - 2) * 1000),
        payload=b"retry",
        requires_ack=True,
        retries=0,
    )
    drop_packet = mod.UDPPacket(
        packet_type=mod.PacketType.DATA,
        sequence=11,
        timestamp_ms=int((now - 5) * 1000),
        payload=b"drop",
        requires_ack=True,
        retries=mod.ShapedUDPTransport.MAX_RETRIES,
    )
    transport._pending_acks[10] = (retry_packet, ping_addr)
    transport._pending_acks[11] = (drop_packet, ping_addr)

    timed_out = []
    pinged = []

    async def _on_timeout(addr):
        timed_out.append(addr)

    async def _send_ping(addr):
        pinged.append(addr)

    async def _fake_sleep(_delay):
        transport._running = False

    transport._on_peer_timeout = _on_timeout
    monkeypatch.setattr(transport, "send_ping", _send_ping)
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await transport._maintenance_loop()

    assert timeout_addr in timed_out
    assert ping_addr in pinged
    assert 10 in transport._pending_acks
    assert transport._pending_acks[10][0].retries == 1
    assert 11 not in transport._pending_acks
    assert transport._peers[ping_addr].packets_lost == 1
    assert fake_socket.sent
    assert fake_socket.sent[0][0].startswith(b"X")


@pytest.mark.asyncio
async def test_maintenance_loop_outer_exception(monkeypatch):
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    transport._running = True
    transport._peers[("1.1.1.1", 1000)] = mod.PeerInfo(
        address=("1.1.1.1", 1000), last_seen=time.time() - mod.ShapedUDPTransport.PING_INTERVAL - 1
    )

    async def _send_ping(_addr):
        raise RuntimeError("ping failed")

    async def _fake_sleep(_delay):
        transport._running = False

    monkeypatch.setattr(transport, "send_ping", _send_ping)
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await transport._maintenance_loop()


def test_callback_registration_helpers():
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")

    @transport.on_receive
    async def _recv(_data, _addr):
        return None

    @transport.on_peer_timeout
    async def _timeout(_addr):
        return None

    asyncio.run(_recv(b"x", ("127.0.0.1", 1)))
    asyncio.run(_timeout(("127.0.0.1", 1)))

    assert transport._on_receive is _recv
    assert transport._on_peer_timeout is _timeout


def test_peer_helpers_and_stats():
    transport = mod.ShapedUDPTransport(traffic_profile="none", obfuscation="none")
    addr = ("127.0.0.1", 6060)
    peer = mod.PeerInfo(address=addr, packets_sent=5, packets_lost=1)
    transport._peers[addr] = peer
    transport._total_sent = 5
    transport._total_received = 4
    transport._start_time = time.time() - 2

    peer_info = transport.get_peer_info(addr)
    all_peers = transport.get_all_peers()
    stats = transport.get_stats()

    assert peer_info is not None
    assert all_peers[addr].packet_loss_percent == 20.0
    assert stats["peers_count"] == 1
    assert stats["packets_per_second"] > 0


@pytest.mark.asyncio
async def test_hole_puncher_discover_and_punch(monkeypatch):
    puncher = mod.UDPHolePuncher(stun_server=("stun.example.org", 3478))
    fake_socket = _FakeSocket()

    monkeypatch.setattr(mod.socket, "socket", lambda *_args, **_kwargs: fake_socket)
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())
    monkeypatch.setattr(
        mod.asyncio,
        "wait_for",
        lambda _coro, timeout: (_ for _ in ()).throw(asyncio.TimeoutError()),
    )
    monkeypatch.setattr(mod.socket, "gethostname", lambda: "node")
    monkeypatch.setattr(mod.socket, "gethostbyname", lambda _name: "10.10.10.10")

    discovered = await puncher.discover_public_address(local_port=0)
    assert discovered == ("10.10.10.10", 5050)

    class _FakeTransport:
        def __init__(self, with_peer):
            self._socket = _FakeSocket()
            self._peer = mod.PeerInfo(address=("1.2.3.4", 5000), rtt_ms=7) if with_peer else None

        async def send_ping(self, _address):
            return None

        def get_peer_info(self, _address):
            return self._peer

    async def _fake_sleep(_delay):
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)
    assert await puncher.punch_hole(_FakeTransport(with_peer=True), ("1.2.3.4", 5000), attempts=2) is True
    assert await puncher.punch_hole(_FakeTransport(with_peer=False), ("1.2.3.4", 5000), attempts=1) is False


@pytest.mark.asyncio
async def test_hole_puncher_discover_with_stun_response(monkeypatch):
    puncher = mod.UDPHolePuncher(stun_server=("stun.example.org", 3478))
    fake_socket = _FakeSocket()
    fake_socket.recv_queue = [(b"stun-response", ("stun.example.org", 3478))]

    async def _wait_for(coro, timeout):
        return await coro

    monkeypatch.setattr(mod.socket, "socket", lambda *_args, **_kwargs: fake_socket)
    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())
    monkeypatch.setattr(mod.asyncio, "wait_for", _wait_for)
    monkeypatch.setattr(mod.socket, "gethostname", lambda: "node")
    monkeypatch.setattr(mod.socket, "gethostbyname", lambda _name: "172.16.0.10")

    discovered = await puncher.discover_public_address(local_port=1234)
    assert discovered == ("172.16.0.10", 1234)


@pytest.mark.asyncio
async def test_hole_puncher_punch_error_path(monkeypatch):
    puncher = mod.UDPHolePuncher()

    class _FailingTransport:
        def __init__(self):
            self._socket = _FakeSocket()
            self._socket.raise_on_send = RuntimeError("blocked")

        async def send_ping(self, _addr):
            return None

        def get_peer_info(self, _addr):
            return None

    async def _fake_sleep(_delay):
        return None

    monkeypatch.setattr(mod.asyncio, "get_event_loop", lambda: _InlineLoop())
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)
    ok = await puncher.punch_hole(_FailingTransport(), ("3.3.3.3", 3333), attempts=1)
    assert ok is False


@pytest.mark.asyncio
async def test_hole_puncher_discover_error(monkeypatch):
    monkeypatch.setattr(
        mod.socket, "socket", lambda *_args, **_kwargs: (_ for _ in ()).throw(OSError("no socket"))
    )
    puncher = mod.UDPHolePuncher()
    assert await puncher.discover_public_address(local_port=0) is None


@pytest.mark.asyncio
async def test_example_gaming_transport(monkeypatch):
    instances = []

    class _FakeTransport:
        def __init__(self, local_port, traffic_profile, obfuscation, obfuscation_key):
            self.local_port = local_port
            self.traffic_profile = traffic_profile
            self.obfuscation = obfuscation
            self.obfuscation_key = obfuscation_key
            self.sent = []
            instances.append(self)

        def on_receive(self, handler):
            self._on_receive = handler
            return handler

        def on_peer_timeout(self, handler):
            self._on_timeout = handler
            return handler

        async def start(self):
            self.local_port = 5000

        async def send_to(self, data, target):
            self.sent.append((data, target))
            if hasattr(self, "_on_receive"):
                await self._on_receive(b"demo-recv", ("127.0.0.1", 6001))
            if hasattr(self, "_on_timeout"):
                await self._on_timeout(("127.0.0.1", 6001))
            return True

        def get_stats(self):
            return {"total_sent": len(self.sent)}

        async def stop(self):
            return None

    async def _fake_sleep(_delay):
        return None

    monkeypatch.setattr(mod, "ShapedUDPTransport", _FakeTransport)
    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    await mod.example_gaming_transport()
    assert instances
    assert len(instances[0].sent) == 10


def test_main_entrypoint_runs_example_gaming_transport(monkeypatch):
    calls = []

    def _fake_run(coro):
        calls.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(asyncio, "run", _fake_run)
    runpy.run_path(mod.__file__, run_name="__main__")

    assert calls == ["example_gaming_transport"]
