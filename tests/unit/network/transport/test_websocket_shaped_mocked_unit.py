from __future__ import annotations

import asyncio
import importlib.util
import pathlib
import runpy
import sys
import types

import pytest

import src.network.transport.websocket_shaped as mod


class _FakeConnectionClosed(Exception):
    pass


class _FakeWebSocket:
    def __init__(self, incoming=None):
        self.incoming = list(incoming or [])
        self.sent = []
        self.closed = False
        self.remote_address = ("127.0.0.1", 4242)

    async def send(self, data):
        self.sent.append(data)

    async def recv(self):
        if not self.incoming:
            raise RuntimeError("no incoming data")
        item = self.incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async def close(self):
        self.closed = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.incoming:
            raise StopAsyncIteration
        item = self.incoming.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


class _FakeTransport:
    def obfuscate(self, data: bytes) -> bytes:
        return b"T" + data

    def deobfuscate(self, data: bytes) -> bytes:
        return data[1:] if data.startswith(b"T") else data


class _FakeShaper:
    profile = types.SimpleNamespace(value="gaming")

    def __init__(self):
        self.delay = 0.001

    def shape_packet(self, data: bytes) -> bytes:
        return b"S" + data

    def unshape_packet(self, data: bytes) -> bytes:
        return data[1:] if data.startswith(b"S") else data

    def get_send_delay(self) -> float:
        return self.delay


@pytest.fixture
def ws_env(monkeypatch):
    async def _default_connect(_uri):
        raise RuntimeError("connect stub not configured")

    async def _default_serve(_handler, _host, _port):
        raise RuntimeError("serve stub not configured")

    fake_websockets = types.SimpleNamespace(
        connect=_default_connect,
        serve=_default_serve,
        ConnectionClosed=_FakeConnectionClosed,
    )
    monkeypatch.setattr(mod, "WEBSOCKETS_AVAILABLE", True)
    monkeypatch.setattr(mod, "websockets", fake_websockets, raising=False)
    return fake_websockets


def test_module_imports_with_available_websockets(monkeypatch):
    websockets_mod = types.ModuleType("websockets")
    client_mod = types.ModuleType("websockets.client")
    server_mod = types.ModuleType("websockets.server")

    client_mod.WebSocketClientProtocol = type("WebSocketClientProtocol", (), {})
    server_mod.WebSocketServerProtocol = type("WebSocketServerProtocol", (), {})
    websockets_mod.client = client_mod
    websockets_mod.server = server_mod

    monkeypatch.setitem(sys.modules, "websockets", websockets_mod)
    monkeypatch.setitem(sys.modules, "websockets.client", client_mod)
    monkeypatch.setitem(sys.modules, "websockets.server", server_mod)

    module_path = pathlib.Path(mod.__file__)
    module_name = "_ws_shaped_reload_for_coverage"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    reloaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reloaded)

    assert reloaded.WEBSOCKETS_AVAILABLE is True


@pytest.mark.asyncio
async def test_fake_websocket_recv_raises_on_empty_queue():
    ws = _FakeWebSocket()
    with pytest.raises(RuntimeError, match="no incoming data"):
        await ws.recv()


@pytest.mark.asyncio
async def test_ws_env_default_stubs_raise(ws_env):
    with pytest.raises(RuntimeError, match="connect stub not configured"):
        await ws_env.connect("ws://localhost:8765")
    with pytest.raises(RuntimeError, match="serve stub not configured"):
        await ws_env.serve(lambda *_args, **_kwargs: None, "0.0.0.0", 8765)


def test_client_requires_websockets_library(monkeypatch):
    monkeypatch.setattr(mod, "WEBSOCKETS_AVAILABLE", False)
    with pytest.raises(ImportError):
        mod.ShapedWebSocketClient(uri="ws://localhost:8765")


def test_client_init_unknown_profile_and_transport_create_error(monkeypatch, ws_env):
    monkeypatch.setattr(
        mod.TransportManager,
        "create",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("create failed")),
    )
    client = mod.ShapedWebSocketClient(
        uri="ws://localhost:8765",
        obfuscation="xor",
        traffic_profile="unknown-profile",
    )
    assert client._transport is None
    assert client._shaper is None


@pytest.mark.asyncio
async def test_client_connect_success_and_failure(monkeypatch, ws_env):
    ws = _FakeWebSocket()

    async def _connect_ok(_uri):
        return ws

    async def _connect_fail(_uri):
        raise RuntimeError("cannot connect")

    monkeypatch.setattr(mod.websockets, "connect", _connect_ok)
    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    assert await client.connect() is True
    assert client.state == mod.ConnectionState.CONNECTED

    monkeypatch.setattr(mod.websockets, "connect", _connect_fail)
    client2 = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    assert await client2.connect() is False
    assert client2.state == mod.ConnectionState.DISCONNECTED


@pytest.mark.asyncio
async def test_client_reconnect_success_and_exhausted(monkeypatch, ws_env):
    sleep_calls = []

    async def _fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    client = mod.ShapedWebSocketClient(
        uri="ws://localhost:8765",
        reconnect_delay=0.5,
        max_reconnect_attempts=3,
    )
    attempts = {"n": 0}

    async def _connect_after_second():
        attempts["n"] += 1
        if attempts["n"] >= 2:
            client.state = mod.ConnectionState.CONNECTED
            client._ws = _FakeWebSocket()
            return True
        return False

    monkeypatch.setattr(client, "connect", _connect_after_second)
    assert await client._reconnect() is True
    assert attempts["n"] == 2
    assert sleep_calls[:2] == [0.5, 1.0]

    client2 = mod.ShapedWebSocketClient(
        uri="ws://localhost:8765",
        reconnect_delay=0.1,
        max_reconnect_attempts=2,
    )

    async def _connect_false():
        return False

    monkeypatch.setattr(client2, "connect", _connect_false)
    assert await client2._reconnect() is False
    assert client2.state == mod.ConnectionState.CLOSED


def test_prepare_unpack_message_roundtrip(monkeypatch, ws_env):
    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    client._transport = _FakeTransport()
    client._shaper = _FakeShaper()

    original = b"hello"
    shaped = client._prepare_message(original)
    unpacked = client._unpack_message(shaped.data)

    assert shaped.original_size == 5
    assert shaped.shaped_size == len(shaped.data)
    assert shaped.profile == "gaming"
    assert shaped.delay_ms > 0
    assert unpacked == original


def test_client_transport_branches_and_valid_profile(monkeypatch, ws_env):
    created = []

    def _create(name, **kwargs):
        created.append((name, kwargs))
        return {"name": name, "kwargs": kwargs}

    monkeypatch.setattr(mod.TransportManager, "create", _create)

    client = mod.ShapedWebSocketClient(
        uri="ws://localhost:8765",
        obfuscation="none",
        traffic_profile="gaming",
    )
    assert client._shaper is not None
    assert client._shaper.profile.value == "gaming"

    assert client._create_transport("faketls", "front.example")
    assert client._create_transport("shadowsocks", "secret")
    assert client._create_transport("unknown", "key") is None
    assert ("faketls", {"sni": "front.example"}) in created
    assert ("shadowsocks", {"password": "secret"}) in created


@pytest.mark.asyncio
async def test_send_success_and_reconnect_failure(monkeypatch, ws_env):
    sleep_calls = []

    async def _fake_sleep(delay):
        sleep_calls.append(delay)

    monkeypatch.setattr(mod.asyncio, "sleep", _fake_sleep)

    ws = _FakeWebSocket()
    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    client.state = mod.ConnectionState.CONNECTED
    client._ws = ws
    client._shaper = _FakeShaper()

    assert await client.send(b"payload") is True
    assert ws.sent
    assert client._messages_sent == 1
    assert client._bytes_sent == len(ws.sent[0])
    assert sleep_calls

    client2 = mod.ShapedWebSocketClient(uri="ws://localhost:8765")

    async def _reconnect_false():
        return False

    monkeypatch.setattr(client2, "_reconnect", _reconnect_false)
    assert await client2.send(b"x") is False


@pytest.mark.asyncio
async def test_reconnect_returns_false_when_disabled(ws_env):
    client = mod.ShapedWebSocketClient(
        uri="ws://localhost:8765",
        auto_reconnect=False,
        max_reconnect_attempts=10,
    )
    assert await client._reconnect() is False


@pytest.mark.asyncio
async def test_send_generic_exception_and_receive_disconnected(monkeypatch, ws_env):
    class _BoomSocket(_FakeWebSocket):
        async def send(self, data):
            raise RuntimeError("boom")

    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    client.state = mod.ConnectionState.CONNECTED
    client._ws = _BoomSocket()
    assert await client.send(b"payload") is False

    client.state = mod.ConnectionState.DISCONNECTED
    client._ws = None
    assert await client.receive() is None


@pytest.mark.asyncio
async def test_send_handles_connection_closed_and_retries(monkeypatch, ws_env):
    class _FirstSendClosed(_FakeWebSocket):
        def __init__(self):
            super().__init__()
            self._closed_once = False

        async def send(self, data):
            if not self._closed_once:
                self._closed_once = True
                raise _FakeConnectionClosed("closed")
            await super().send(data)

    ws_initial = _FirstSendClosed()
    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    client.state = mod.ConnectionState.CONNECTED
    client._ws = ws_initial

    async def _reconnect_ok():
        client._ws = ws_initial
        client.state = mod.ConnectionState.CONNECTED
        return True

    monkeypatch.setattr(client, "_reconnect", _reconnect_ok)

    assert await client.send(b"retry-me") is True
    assert ws_initial.sent == [b"retry-me"]


@pytest.mark.asyncio
async def test_receive_variants(monkeypatch, ws_env):
    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    client.state = mod.ConnectionState.CONNECTED
    client._ws = _FakeWebSocket(incoming=["text-message"])
    assert await client.receive() == b"text-message"

    client._ws = _FakeWebSocket(incoming=[b"bytes-message"])
    assert await client.receive(timeout=0.1) == b"bytes-message"

    async def _timeout(_coro, timeout):
        raise asyncio.TimeoutError()

    monkeypatch.setattr(mod.asyncio, "wait_for", _timeout)
    client._ws = _FakeWebSocket(incoming=[b"ignored"])
    assert await client.receive(timeout=0.1) is None

    client._ws = _FakeWebSocket(incoming=[_FakeConnectionClosed("closed")])
    assert await client.receive() is None
    assert client.state == mod.ConnectionState.DISCONNECTED

    client.state = mod.ConnectionState.CONNECTED
    client._ws = _FakeWebSocket(incoming=[RuntimeError("boom")])
    assert await client.receive() is None


@pytest.mark.asyncio
async def test_close_and_stats(monkeypatch, ws_env):
    client = mod.ShapedWebSocketClient(uri="ws://localhost:8765")
    ws = _FakeWebSocket()
    client._ws = ws
    client.state = mod.ConnectionState.CONNECTED
    client._messages_sent = 2
    client._messages_received = 3
    client._bytes_sent = 11
    client._bytes_received = 15

    await client.close()
    stats = client.get_stats()

    assert ws.closed is True
    assert client.state == mod.ConnectionState.CLOSED
    assert stats["messages_sent"] == 2
    assert stats["messages_received"] == 3
    assert stats["bytes_sent"] == 11
    assert stats["bytes_received"] == 15


def test_server_requires_websockets_library(monkeypatch):
    monkeypatch.setattr(mod, "WEBSOCKETS_AVAILABLE", False)
    with pytest.raises(ImportError):
        mod.ShapedWebSocketServer()


def test_server_create_helpers_and_stats(monkeypatch, ws_env):
    created = []

    def _create(name, **kwargs):
        created.append((name, kwargs))
        return types.SimpleNamespace(name=name, kwargs=kwargs)

    monkeypatch.setattr(mod.TransportManager, "create", _create)

    server = mod.ShapedWebSocketServer(
        obfuscation="xor",
        obfuscation_key="k",
        traffic_profile="gaming",
    )
    assert server._create_shaper() is not None
    assert server._create_transport() is not None
    assert server.get_stats()["clients_connected"] == 0
    assert created and created[0][0] == "xor"

    server2 = mod.ShapedWebSocketServer(obfuscation="unknown", traffic_profile="unknown")
    assert server2._create_shaper() is None
    assert server2._create_transport() is None


def test_server_create_transport_branches_and_error(monkeypatch, ws_env):
    created = []

    def _create(name, **kwargs):
        created.append((name, kwargs))
        if name == "faketls":
            return "FAKE_TLS"
        if name == "shadowsocks":
            return "SS"
        return "OTHER"

    monkeypatch.setattr(mod.TransportManager, "create", _create)

    server_ft = mod.ShapedWebSocketServer(obfuscation="faketls", obfuscation_key="cdn")
    server_ss = mod.ShapedWebSocketServer(obfuscation="shadowsocks", obfuscation_key="pwd")
    assert server_ft._create_transport() == "FAKE_TLS"
    assert server_ss._create_transport() == "SS"
    assert _create("other") == "OTHER"
    assert ("faketls", {"sni": "cdn"}) in created
    assert ("shadowsocks", {"password": "pwd"}) in created

    monkeypatch.setattr(
        mod.TransportManager,
        "create",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("err")),
    )
    server_err = mod.ShapedWebSocketServer(obfuscation="xor", obfuscation_key="x")
    assert server_err._create_transport() is None


@pytest.mark.asyncio
async def test_server_handle_client_roundtrip(monkeypatch, ws_env):
    server = mod.ShapedWebSocketServer(obfuscation="none", traffic_profile="none")
    ws = _FakeWebSocket(incoming=[b"payload"])

    monkeypatch.setattr(server, "_create_transport", lambda: _FakeTransport())
    monkeypatch.setattr(server, "_create_shaper", lambda: _FakeShaper())

    @server.on_message
    async def _handler(client_id, data):
        assert client_id.startswith("127.0.0.1:")
        assert data == b"payload"
        return b"reply"

    async def _no_sleep(_delay):
        return None

    monkeypatch.setattr(mod.asyncio, "sleep", _no_sleep)
    await server._handle_client(ws, "/demo")

    assert server._total_messages == 1
    assert server._total_bytes == len(b"payload")
    assert ws.sent == [b"STreply"]
    assert server.get_stats()["clients_connected"] == 0


@pytest.mark.asyncio
async def test_server_handle_client_with_string_payload(ws_env):
    server = mod.ShapedWebSocketServer(obfuscation="none", traffic_profile="none")
    ws = _FakeWebSocket(incoming=["message-from-str"])

    @server.on_message
    async def _handler(_client_id, data):
        assert data == b"message-from-str"
        return b"ok"

    await server._handle_client(ws, "/demo")
    assert ws.sent == [b"ok"]


@pytest.mark.asyncio
async def test_server_handle_client_connection_closed(monkeypatch, ws_env):
    server = mod.ShapedWebSocketServer()
    ws = _FakeWebSocket(incoming=[_FakeConnectionClosed("closed")])

    await server._handle_client(ws, "/demo")
    assert server.get_stats()["clients_connected"] == 0


@pytest.mark.asyncio
async def test_server_start_stop_and_on_message(monkeypatch, ws_env):
    class _FakeServerHandle:
        def __init__(self):
            self.closed = False
            self.waited = False

        def close(self):
            self.closed = True

        async def wait_closed(self):
            self.waited = True

    handle = _FakeServerHandle()

    async def _serve(handler, host, port):
        assert callable(handler)
        assert host == "0.0.0.0"
        assert port == 8765
        return handle

    monkeypatch.setattr(mod.websockets, "serve", _serve)
    server = mod.ShapedWebSocketServer()

    @server.on_message
    async def _handler(client_id, data):
        return b"ok"

    assert await _handler("cid", b"payload") == b"ok"
    assert server._message_handler is _handler
    await server.start()
    await server.stop()
    assert handle.closed is True
    assert handle.waited is True


@pytest.mark.asyncio
async def test_example_echo_server_cancellation(monkeypatch):
    state = {}

    class _FakeServer:
        def __init__(self, **kwargs):
            state["init"] = kwargs
            self._handler = None

        def on_message(self, handler):
            self._handler = handler
            return handler

        async def start(self):
            state["started"] = True
            state["echo"] = await self._handler("cid", b"payload")

        async def stop(self):
            state["stopped"] = True

    class _CancelledFuture:
        def __await__(self):
            async def _raise():
                raise asyncio.CancelledError()

            return _raise().__await__()

    monkeypatch.setattr(mod, "ShapedWebSocketServer", _FakeServer)
    monkeypatch.setattr(mod.asyncio, "Future", _CancelledFuture)

    await mod.example_echo_server()

    assert state["started"] is True
    assert state["stopped"] is True
    assert state["echo"] == b"ECHO: payload"
    assert state["init"]["obfuscation"] == "xor"


@pytest.mark.asyncio
async def test_example_client_success(monkeypatch):
    state = {"sent": [], "prints": []}

    class _FakeClient:
        def __init__(self, **kwargs):
            state["init"] = kwargs

        async def connect(self):
            return True

        async def send(self, data):
            state["sent"].append(data)

        async def receive(self, timeout=None):
            assert timeout == 5.0
            return b"echo"

        def get_stats(self):
            return {"messages_sent": len(state["sent"])}

        async def close(self):
            state["closed"] = True

    monkeypatch.setattr(mod, "ShapedWebSocketClient", _FakeClient)
    monkeypatch.setattr(
        "builtins.print", lambda *args, **_kwargs: state["prints"].append(args)
    )

    await mod.example_client()

    assert len(state["sent"]) == 5
    assert state.get("closed") is True
    assert any("Ответ:" in msg[0] for msg in state["prints"])
    assert any("Статистика:" in msg[0] for msg in state["prints"])


def test_main_entrypoint_server_branch(monkeypatch):
    calls = []

    def _fake_run(coro):
        calls.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(asyncio, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["websocket_shaped.py", "server"])

    runpy.run_path(mod.__file__, run_name="__main__")
    assert calls == ["example_echo_server"]


def test_main_entrypoint_client_branch(monkeypatch):
    calls = []

    def _fake_run(coro):
        calls.append(coro.cr_code.co_name)
        coro.close()

    monkeypatch.setattr(asyncio, "run", _fake_run)
    monkeypatch.setattr(sys, "argv", ["websocket_shaped.py"])

    runpy.run_path(mod.__file__, run_name="__main__")
    assert calls == ["example_client"]
