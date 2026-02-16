import sqlite3

import pytest


def _patch_crdt_sync(monkeypatch):
    import sys
    import types

    class _DummyCRDTSync:
        def __init__(self, *args, **kwargs):
            pass

        async def sync(self, *args, **kwargs):
            return None

    dummy_module = types.ModuleType("src.data_sync.crdt_sync")
    dummy_module.CRDTSync = _DummyCRDTSync
    if "src.data_sync" not in sys.modules:
        sys.modules["src.data_sync"] = types.ModuleType("src.data_sync")
    monkeypatch.setitem(sys.modules, "src.data_sync.crdt_sync", dummy_module)


@pytest.mark.asyncio
async def test_knowledge_storage_v2_crdt_sync_async_and_sync_branches(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    # Dummy CRDTSync module
    import sys
    import types

    class _DummyCRDTSync:
        def __init__(self, *args, **kwargs):
            pass

        async def sync(self, *args, **kwargs):
            return None

    dummy_module = types.ModuleType("src.data_sync.crdt_sync")
    dummy_module.CRDTSync = _DummyCRDTSync
    if "src.data_sync" not in sys.modules:
        sys.modules["src.data_sync"] = types.ModuleType("src.data_sync")
    monkeypatch.setitem(sys.modules, "src.data_sync.crdt_sync", dummy_module)

    # Light vector index
    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def embed(self, text):
            return [0.0]

        def add(self, *args, **kwargs):
            return 0

        def search(self, *args, **kwargs):
            return []

        def save(self, *args, **kwargs):
            return None

        def get_stats(self):
            return {"total_documents": 0}

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    # async sync path (already coroutine)
    incident = {
        "id": "i1",
        "timestamp": 1.0,
        "anomaly_type": "A",
        "metrics": {},
        "root_cause": "r",
        "recovery_plan": "p",
        "execution_result": {"success": True},
    }
    await ks.store_incident(incident, node_id="n")

    # sync (non-async) path
    class _SyncCRDT:
        def sync(self, *args, **kwargs):
            return None

    ks.crdt_sync = _SyncCRDT()

    incident2 = dict(incident)
    incident2["id"] = "i2"
    await ks.store_incident(incident2, node_id="n")


@pytest.mark.asyncio
async def test_knowledge_storage_v2_handles_ipfs_and_vector_failures(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")

    # Dummy CRDTSync module to avoid node_id requirements
    import sys
    import types

    class _DummyCRDTSync:
        def __init__(self, *args, **kwargs):
            pass

        def sync(self, *args, **kwargs):
            raise RuntimeError("sync fail")

    dummy_module = types.ModuleType("src.data_sync.crdt_sync")
    dummy_module.CRDTSync = _DummyCRDTSync
    if "src.data_sync" not in sys.modules:
        sys.modules["src.data_sync"] = types.ModuleType("src.data_sync")
    monkeypatch.setitem(sys.modules, "src.data_sync.crdt_sync", dummy_module)

    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def embed(self, text):
            raise RuntimeError("embed fail")

        def add(self, *args, **kwargs):
            raise RuntimeError("add fail")

        def search(self, *args, **kwargs):
            return []

        def save(self, *args, **kwargs):
            raise RuntimeError("save fail")

        def get_stats(self):
            raise RuntimeError("stats fail")

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    async def _ipfs_add_fail(data, pin=True):
        raise RuntimeError("ipfs fail")

    ks.ipfs_client.add = _ipfs_add_fail

    incident = {
        "id": "i3",
        "timestamp": 1.0,
        "anomaly_type": "A",
        "metrics": {},
        "root_cause": "r",
        "recovery_plan": "p",
        "execution_result": {"success": True},
    }

    # Should not raise despite failures in IPFS/vector/crdt
    await ks.store_incident(incident, node_id="n")

    # save_index/get_stats should not raise
    ks.save_index()
    assert ks.get_stats() == {}


def test_knowledge_storage_v2_get_incident_from_db_error(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    # VectorIndex stub
    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            pass

        def load(self, *args, **kwargs):
            return None

        def embed(self, text):
            return [0.0]

        def add(self, *args, **kwargs):
            return 0

        def search(self, *args, **kwargs):
            return []

        def get_stats(self):
            return {}

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    # Break db path to force exception
    ks.db_path = tmp_path / "missing" / "nope.db"
    assert ks._get_incident_from_db("x") is None
