from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "gitmark_memory_bank.py"
SPEC = importlib.util.spec_from_file_location("gitmark_memory_bank", SCRIPT)
assert SPEC is not None
gitmark_memory_bank = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = gitmark_memory_bank
SPEC.loader.exec_module(gitmark_memory_bank)


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_build_index_search_and_context_for_rag_docs(tmp_path: Path) -> None:
    write(
        tmp_path / "AGENTS.md",
        "# Agents\n\nStart from [docs](docs/README.md).\n",
    )
    write(
        tmp_path / "GEMINI.md",
        "# Gemini\n\nUse the local RAG memory graph.\n",
    )
    write(
        tmp_path / "docs" / "README.md",
        "# Docs Index\n\n- [RAG RFC](rfc/RAG-RFC.md)\n- [API](../services/api/README.md)\n",
    )
    write(
        tmp_path / "docs" / "rfc" / "RAG-RFC.md",
        "# Decentralized RAG\n\nIntro.\n\n## Shard Routing\n\nHorizon-2 shard routing and semantic chunking are deferred.\n",
    )
    write(
        tmp_path / "services" / "api" / "README.md",
        "# API Service\n\nRuntime service notes.\n",
    )

    index = gitmark_memory_bank.build_index(
        tmp_path,
        include_paths=("AGENTS.md", "GEMINI.md", "docs", "services"),
        profile="rag",
    )

    paths = {doc["path"] for doc in index["documents"]}
    assert paths == {
        "AGENTS.md",
        "GEMINI.md",
        "docs/README.md",
        "docs/rfc/RAG-RFC.md",
        "services/api/README.md",
    }
    assert index["profile"] == "rag"
    assert index["stats"]["chunk_count"] >= 5
    assert any(chunk["heading"] == "Shard Routing" for chunk in index["chunks"])
    assert {"source": "AGENTS.md", "target": "docs/README.md", "kind": "markdown"} in index[
        "edges"
    ]
    assert {"source": "docs/README.md", "target": "docs/rfc/RAG-RFC.md", "kind": "markdown"} in index[
        "edges"
    ]

    results = gitmark_memory_bank.bm25_search(index, "Horizon-2 RAG shard routing", limit=3)
    assert results[0]["path"] == "docs/rfc/RAG-RFC.md"

    context = gitmark_memory_bank.render_context(results, "Horizon-2 RAG shard routing")
    assert "docs/rfc/RAG-RFC.md" in context
    assert "Horizon-2" in context

    chunk_results = gitmark_memory_bank.bm25_chunk_search(
        index, "Horizon-2 shard routing semantic chunking", limit=3
    )
    assert chunk_results[0]["path"] == "docs/rfc/RAG-RFC.md"
    assert chunk_results[0]["heading"] == "Shard Routing"

    chunk_context = gitmark_memory_bank.render_chunk_context(
        chunk_results, "Horizon-2 shard routing semantic chunking"
    )
    assert "GitMark RAG Context" in chunk_context
    assert "Shard Routing" in chunk_context
    assert "docs/rfc/RAG-RFC.md:" in chunk_context


def test_html_graph_payload_contains_folder_nodes_and_valid_json(tmp_path: Path) -> None:
    write(tmp_path / "AGENTS.md", "# Agents\n\n[Docs](docs/README.md)\n")
    write(tmp_path / "docs" / "README.md", "# Docs\n\n[Runbook](runbooks/vpn.md)\n")
    write(tmp_path / "docs" / "runbooks" / "vpn.md", "# VPN Runbook\n\nEvidence notes.\n")

    index = gitmark_memory_bank.build_index(tmp_path, include_paths=("AGENTS.md", "docs"))
    out_dir = tmp_path / ".gitmark-memory"
    index_path, html_path = gitmark_memory_bank.write_outputs(index, out_dir)

    assert json.loads(index_path.read_text(encoding="utf-8"))["stats"]["document_count"] == 3

    html = html_path.read_text(encoding="utf-8")
    match = re.search(r'<script id="graph-data" type="application/json">(.*?)</script>', html, re.S)
    assert match is not None
    payload = json.loads(match.group(1))

    node_ids = {node["id"] for node in payload["nodes"]}
    assert "folder:[root]" in node_ids
    assert "folder:docs" in node_ids
    assert "folder:docs/runbooks" in node_ids
    assert "showFolder" in html
    assert "showMarkdown" in html
    assert 'id="showFolder" type="checkbox"> структура' in html
    assert 'id="showIndex" type="checkbox"> индексы' in html
    assert 'id="showMarkdown" type="checkbox" checked> ссылки' in html
    assert "function fitVisible" in html
    assert "modeOverview" in html
    assert "pan = null" in html
    assert "focusOnly" in html
    assert "только соседи" in html
    assert "открыть markdown" in html
    assert "data-node" in html


def test_safe_script_json_escapes_script_closer() -> None:
    payload = gitmark_memory_bank.safe_script_json({"excerpt": "</script><script>alert(1)</script>"})

    assert "</script>" not in payload
    assert "<\\/script>" in payload
    assert json.loads(payload)["excerpt"].startswith("</script>")
