"""Focused unit coverage for event_sourcing aggregate/command/query/projection/backends."""

from __future__ import annotations

import dataclasses
import json

import pytest

from src.event_sourcing.aggregate import AggregateRoot, InMemoryRepository, UserAggregate, event_handler
from src.event_sourcing.backends import mongodb as mongo_backend
from src.event_sourcing.backends import postgres as pg_backend
from src.event_sourcing.command_bus import (
    Command,
    CommandBus,
    CommandHandler,
    CommandResult,
    RetryMiddleware,
    command_handler,
)
from src.event_sourcing.event_store import Event, EventStore, EventVersion, FileEventStore
from src.event_sourcing.projection import Projection, ProjectionManager, UserSummaryProjection
from src.event_sourcing.query_bus import Query, QueryBus, QueryHandler, QueryResult, query_handler


class DemoAggregate(AggregateRoot):
    def __init__(self, aggregate_id: str = ""):
        self.name = ""
        super().__init__(aggregate_id)

    def rename(self, name: str) -> None:
        self.raise_event("Renamed", {"name": name})

    @event_handler("Renamed")
    def _on_renamed(self, event: Event) -> None:
        self.name = event.data["name"]

    def get_snapshot_state(self):
        return {**super().get_snapshot_state(), "name": self.name}

    def _restore_state(self, state):
        super()._restore_state(state)
        self.name = state.get("name", "")


class NameProjection(Projection):
    def __init__(self, event_store: EventStore):
        self.items = {}
        super().__init__("name_projection", event_store)

    @Projection.handles("Renamed")
    def on_renamed(self, event: Event) -> None:
        self.items[event.aggregate_id] = event.data["name"]

    async def on_reset(self) -> None:
        self.items.clear()


class CounterProjection(Projection):
    def __init__(self, event_store: EventStore):
        self.counter = 0
        super().__init__("counter_projection", event_store)

    async def process_event(self, event: Event) -> bool:
        self.counter += 1
        return await super().process_event(event)

    async def on_reset(self) -> None:
        self.counter = 0


def test_event_version_event_aliases_and_json_roundtrip():
    v1 = EventVersion(1, 2)
    v2 = EventVersion(1, 3)
    assert str(v1) == "1.2"
    assert v1 < v2
    assert v1 == EventVersion.from_dict(v1.to_dict())

    event = Event(
        event_type="UserCreated",
        aggregate_id="u1",
        aggregate_type="User",
        sequence_number=7,
        data={"email": "a@b.c"},
    )
    event.stream_id = "stream-1"
    event.version = 9
    event.payload = {"x": 1}
    assert event.stream_id == "stream-1"
    assert event.version == 9
    assert event.payload == {"x": 1}

    restored = Event.from_json(event.to_json())
    assert restored.event_type == "UserCreated"
    assert restored.aggregate_id == "stream-1"
    assert restored.sequence_number == 9


@pytest.mark.asyncio
async def test_event_store_append_snapshot_and_file_persistence(tmp_path):
    store = EventStore(snapshot_interval=2)
    e1 = Event(event_type="Created", aggregate_type="User", data={"name": "Alice"})
    e2 = Event(event_type="Updated", aggregate_type="User", data={"name": "Bob"})
    version = await store.append("agg-1", [e1, e2], expected_version=0)
    assert version == 2
    assert store.list_streams()[0]["event_count"] == 2

    with pytest.raises(ValueError, match="Version conflict"):
        await store.append("agg-1", Event(event_type="X"), expected_version=0)

    snapshot = await store.create_snapshot_if_needed("agg-1", {"name": "Bob"}, "User")
    assert snapshot is not None
    assert snapshot.sequence_number == 2
    assert await store.get_events_after_snapshot("agg-1") == []

    all_events = await store.get_all_events()
    assert len(all_events) == 2
    typed = await store.get_events_by_type("Created")
    assert len(typed) == 1

    file_path = str(tmp_path / "events.jsonl")
    file_store = FileEventStore(file_path, snapshot_interval=2)
    await file_store.append("agg-file", Event(event_type="Created", data={"a": 1}), expected_version=0)

    loaded_store = FileEventStore(file_path, snapshot_interval=2)
    await loaded_store.load()
    loaded = loaded_store.read_stream("agg-file")
    assert len(loaded) == 1


@pytest.mark.asyncio
async def test_aggregate_and_repository_flow():
    repo = InMemoryRepository(DemoAggregate)
    aggregate = DemoAggregate("u-1")
    aggregate.rename("first")
    assert aggregate.has_uncommitted_events is True

    version = await repo.save(aggregate, expected_version=0)
    assert version == 1
    assert aggregate.has_uncommitted_events is False

    loaded = await repo.get_by_id("u-1")
    assert loaded is not None
    assert loaded.name == "first"

    loaded.rename("next")
    await repo.save(loaded, expected_version=1)
    loaded2 = await repo.get_by_id("u-1")
    assert loaded2.name == "next"

    assert await repo.exists("u-1") is True
    await repo.delete("u-1")
    assert await repo.exists("u-1") is False


def test_regression_user_aggregate_and_projection_initialization():
    user = UserAggregate.create("u-init", "init@example.com", "Init")
    assert user.email == "init@example.com"
    assert user.name == "Init"

    projection = UserSummaryProjection(EventStore())
    assert projection.user_count == 0
    assert projection.active_users == set()


@pytest.mark.asyncio
async def test_command_bus_execute_with_handler_and_decorator(monkeypatch):
    @dataclasses.dataclass
    class EchoCommand(Command):
        value: int = 0

    class EchoHandler(CommandHandler[EchoCommand, int]):
        def validate(self, command: EchoCommand):
            if command.value < 0:
                return "value must be >= 0"
            return None

        async def handle(self, command: EchoCommand):
            return CommandResult(success=True, result=command.value + 1)

    bus = CommandBus()
    bus.register_handler(EchoCommand, EchoHandler())

    ok = await bus.execute(EchoCommand(value=1))
    assert ok.success is True and ok.result == 2

    invalid = await bus.execute(EchoCommand(value=-1))
    assert invalid.success is False
    assert "Validation failed" in (invalid.error or "")

    none = await bus.execute(Command(command_type="NotRegistered"))
    assert none.success is False
    assert "No handler" in (none.error or "")

    retry = RetryMiddleware(max_retries=2, retry_delay_ms=1, exponential_backoff=False)
    retry.add_retryable_error(ValueError)
    sleep_calls = {"count": 0}

    async def _sleep(_t):
        sleep_calls["count"] += 1

    monkeypatch.setattr("asyncio.sleep", _sleep)
    cmd = EchoCommand(value=1)
    assert await retry.on_error(cmd, ValueError("boom")) is None
    assert cmd.metadata["_retry_count"] == 1
    assert sleep_calls["count"] == 1

    @command_handler(EchoCommand)
    def _inline(_command):
        return {"ok": True}

    command_type, fn_handler = _inline._command_handler
    assert command_type is EchoCommand
    wrapped_result = await fn_handler.handle(EchoCommand(value=2))
    assert wrapped_result.success is True
    assert wrapped_result.result == {"ok": True}


@pytest.mark.asyncio
async def test_query_bus_cache_and_decorator():
    @dataclasses.dataclass
    class SumQuery(Query):
        a: int = 0
        b: int = 0

    class SumHandler(QueryHandler[SumQuery, int]):
        def __init__(self):
            self.calls = 0

        async def handle(self, query: SumQuery):
            self.calls += 1
            return QueryResult(success=True, result=query.a + query.b)

    bus = QueryBus(enable_cache=True)
    handler = SumHandler()
    bus.register_handler(SumQuery, handler)

    q = SumQuery(a=2, b=3)
    r1 = await bus.execute(q)
    r2 = await bus.execute(q)
    assert r1.success is True and r1.result == 5
    assert r2.success is True and r2.from_cache is True
    assert handler.calls == 1

    assert bus.invalidate_cache(query=q) == 1
    await bus.execute(q)
    assert handler.calls == 2

    assert bus.invalidate_cache(all=True) >= 0
    assert bus.has_handler("SumQuery") is True
    assert "SumQuery" in bus.get_registered_queries()

    @query_handler(SumQuery)
    def _inline(_query):
        return {"cached": False}

    query_type, fn_handler = _inline._query_handler
    assert query_type is SumQuery
    wrapped = await fn_handler.handle(SumQuery(a=1, b=1))
    assert wrapped.success is True


@pytest.mark.asyncio
async def test_projection_and_manager_end_to_end():
    store = EventStore()
    summary = NameProjection(store)
    stats = CounterProjection(store)
    manager = ProjectionManager(store)
    manager.register(summary)
    manager.register(stats)

    await manager.start_all()

    await store.append(
        "u-1",
        [
            Event(event_type="Renamed", aggregate_type="User", data={"name": "X"}),
            Event(event_type="Renamed", aggregate_type="User", data={"name": "Y"}),
            Event(event_type="Unknown", aggregate_type="User", data={}),
        ],
        expected_version=0,
    )

    assert summary.items["u-1"] == "Y"
    assert stats.counter >= 3

    manager.pause_projection("name_projection")
    assert manager.get_projection_status("name_projection")["status"] == "paused"
    manager.resume_projection("name_projection")
    assert manager.get_projection_status("name_projection")["status"] in {"running", "error", "paused"}

    caught = await manager.catch_up_all()
    assert "name_projection" in caught and "counter_projection" in caught
    assert manager.get_lagging_projections(max_lag=1000) == []

    await manager.reset_all()
    assert summary.items == {}
    await manager.stop_all()
    assert manager.get_status()["running_projections"] == 0


def test_mongodb_and_postgres_configs_and_helper_converters():
    mongo_cfg = mongo_backend.MongoDBConfig(
        host="db.local",
        port=27018,
        database="events",
        user="u",
        password="p",
        replica_set="rs0",
    )
    uri = mongo_cfg.to_uri()
    assert uri.startswith("mongodb://u:p@db.local:27018/events")
    assert "replicaSet=rs0" in uri

    pg_cfg = pg_backend.PostgresConfig(
        host="pg.local",
        port=5433,
        database="events",
        user="alice",
        password="secret",
        schema="event_store",
    )
    assert pg_cfg.to_dsn() == "postgresql://alice:***@pg.local:5433/events"
    assert "secret" in pg_cfg._unsafe_dsn()
    assert "password='***'" in repr(pg_cfg)
    assert pg_backend.PostgresEventStore._validate_schema_name("event_store") == "event_store"
    with pytest.raises(ValueError, match="Invalid schema name"):
        pg_backend.PostgresEventStore._validate_schema_name("bad-name")

    event = Event(
        event_id="ev-1",
        aggregate_id="a-1",
        aggregate_type="Agg",
        event_type="Created",
        sequence_number=3,
        data={"x": 1},
    )
    mongo_store = mongo_backend.MongoDBEventStore.__new__(mongo_backend.MongoDBEventStore)
    doc = mongo_backend.MongoDBEventStore._event_to_doc(mongo_store, event)
    restored_event = mongo_backend.MongoDBEventStore._doc_to_event(mongo_store, doc)
    assert restored_event.event_id == "ev-1"
    assert restored_event.sequence_number == 3

    pg_store = pg_backend.PostgresEventStore.__new__(pg_backend.PostgresEventStore)
    row = {
        "event_id": "ev-2",
        "aggregate_id": "a-2",
        "aggregate_type": "Agg",
        "event_type": "Updated",
        "sequence_number": 4,
        "data": json.dumps({"y": 2}),
        "metadata": json.dumps(event.metadata.to_dict()),
    }
    row_event = pg_backend.PostgresEventStore._row_to_event(pg_store, row)
    assert row_event.event_type == "Updated"
    assert row_event.data == {"y": 2}
