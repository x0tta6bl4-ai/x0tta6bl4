import json
import sys
import types

import pytest


def _patch_crdt_sync(monkeypatch):
    class _DummyCRDTSync:
        def __init__(self, *args, **kwargs):
            pass

        async def sync(self, *args, **kwargs):
            return None

    dummy_module = types.ModuleType("src.data_sync.crdt_sync")
    dummy_module.CRDTSync = _DummyCRDTSync

    # Ensure both the parent package and module exist in sys.modules
    if "src.data_sync" not in sys.modules:
        sys.modules["src.data_sync"] = types.ModuleType("src.data_sync")

    monkeypatch.setitem(sys.modules, "src.data_sync.crdt_sync", dummy_module)


@pytest.mark.asyncio
async def test_knowledge_storage_store_and_search_happy_path(tmp_path, monkeypatch):
    # Keep VectorIndex lightweight in tests
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

    # Patch vector index to deterministic stub (avoid numpy + persistence complexity)
    class _StubVectorIndex:
        def __init__(self, *args, **kwargs):
            self.docs = {}

        def load(self, *args, **kwargs):
            return None

        def embed(self, text):
            return [0.0, 1.0]

        def add(self, text, metadata, embedding=None):
            doc_id = len(self.docs)
            self.docs[doc_id] = metadata
            return doc_id

        def search(self, query, k=10, threshold=0.7):
            # Always return the first doc
            if not self.docs:
                return []
            first_id = next(iter(self.docs.keys()))
            return [(first_id, 0.9, self.docs[first_id])]

        def get_stats(self):
            return {"total_documents": len(self.docs)}

    monkeypatch.setattr(
        "src.storage.knowledge_storage_v2.VectorIndex", _StubVectorIndex
    )

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    incident = {
        "id": "incident-1",
        "timestamp": 1.0,
        "anomaly_type": "CPU",
        "metrics": {"cpu": 99},
        "root_cause": "overload",
        "recovery_plan": "restart",
        "execution_result": {"success": True, "duration": 1.2},
    }

    inc_id = await ks.store_incident(incident, node_id="n1")
    assert inc_id == "incident-1"

    # Should be retrievable from sqlite
    row = ks._get_incident_from_db("incident-1")
    assert row and row["anomaly_type"] == "CPU"
    assert row["metrics"]["cpu"] == 99

    results = await ks.search_incidents("cpu")
    assert results
    assert results[0]["incident_id"] == "incident-1"


def test_knowledge_storage_get_successful_patterns(tmp_path, monkeypatch):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

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

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    # Insert directly via sqlite to cover pattern query
    import sqlite3

    conn = sqlite3.connect(ks.db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO incidents (incident_id, timestamp, node_id, anomaly_type, metrics, root_cause, recovery_plan, execution_result, signature, ipfs_cid, embedding) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "i1",
            1.0,
            "n",
            "CPU",
            json.dumps({"x": 1}),
            "rc",
            "restart",
            json.dumps({"success": True, "duration": 1.0}),
            None,
            None,
            None,
        ),
    )
    conn.commit()
    conn.close()


@pytest.mark.asyncio
async def test_knowledge_storage_get_successful_patterns_returns_rows(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("RAG_DISABLE_EMBEDDING_MODEL", "true")
    monkeypatch.setenv("RAG_DISABLE_HNSW", "true")
    _patch_crdt_sync(monkeypatch)

    from src.storage.knowledge_storage_v2 import KnowledgeStorageV2

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

    ks = KnowledgeStorageV2(storage_path=tmp_path, use_real_ipfs=False)

    import sqlite3

    conn = sqlite3.connect(ks.db_path)
    cur = conn.cursor()
    cur.execute(
        "INSERT OR REPLACE INTO incidents (incident_id, timestamp, node_id, anomaly_type, metrics, root_cause, recovery_plan, execution_result, signature, ipfs_cid, embedding) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            "i1",
            1.0,
            "n",
            "CPU",
            json.dumps({"x": 1}),
            "rc",
            "restart",
            json.dumps({"success": True, "duration": 1.0}),
            None,
            None,
            None,
        ),
    )
    conn.commit()
    conn.close()

    patterns = await ks.get_successful_patterns("CPU")
    assert patterns
    assert patterns[0]["incident_id"] == "i1"
