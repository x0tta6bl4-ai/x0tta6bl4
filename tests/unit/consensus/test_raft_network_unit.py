from unittest.mock import AsyncMock

import pytest

from src.consensus.raft_network import RaftNetworkServer


@pytest.mark.asyncio
async def test_server_start_fails_when_transport_does_not_bind(monkeypatch):
    server = RaftNetworkServer("node-1", listen_address="127.0.0.1:0", use_grpc=False)

    async def _no_server():
        server.server = None

    monkeypatch.setattr(server, "_start_http_server", _no_server)

    with pytest.raises(RuntimeError, match="failed to start"):
        await server.start()


@pytest.mark.asyncio
async def test_server_stop_cleans_up_http_runner():
    server = RaftNetworkServer("node-1", listen_address="127.0.0.1:0", use_grpc=False)
    runner = AsyncMock()
    del runner.stop
    server.server = runner

    await server.stop()

    runner.cleanup.assert_awaited_once()
    assert server.server is None


@pytest.mark.asyncio
async def test_handle_request_vote_without_handler_fails_closed():
    server = RaftNetworkServer("node-1", listen_address="127.0.0.1:0", use_grpc=False)

    result = await server.handle_request_vote(
        {
            "term": 2,
            "candidate_id": "node-2",
            "last_log_index": 3,
            "last_log_term": 2,
        }
    )

    assert result == {"term": 0, "vote_granted": False, "reason": "No handler"}
