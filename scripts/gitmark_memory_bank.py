#!/usr/bin/env python3
"""Build and query a lightweight Markdown memory graph for agent workflows."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from html import escape
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any, Iterable
from urllib.parse import unquote, urlparse


SCHEMA_VERSION = 2
DEFAULT_OUT_DIR = ".gitmark-memory"
DEFAULT_INDEX_NAME = "index.json"
DEFAULT_HTML_NAME = "graph.html"
DEFAULT_CHUNK_CHAR_LIMIT = 1800
DEFAULT_CONTEXT_CHUNK_LIMIT = 6
RAG_PROFILE_INCLUDE_PATHS = (
    "AGENTS.md",
    "GEMINI.md",
    "README.md",
    "docs",
    "services",
    "src",
    "scripts",
    "skills",
    ".gemini",
    ".claude",
    "plans",
    "infra",
    "deploy",
    "deployment",
    "monitoring",
    "sdk",
    "examples",
)

DEFAULT_SKIP_DIRS = {
    ".Trash-1000",
    ".agent-coord",
    ".agent_coordination",
    ".artifacts",
    ".benchmarks",
    ".cache",
    ".git",
    ".codegraph",
    ".gitmark-memory",
    ".hypothesis",
    ".kilo",
    ".logs",
    ".mypy_cache",
    ".playwright-cli",
    ".playwright-mcp",
    ".pnpm-store",
    ".pytest_cache",
    ".ruff_cache",
    ".runtime",
    ".swarm",
    ".tmp",
    ".venv",
    ".venv_dao",
    ".worktrees",
    "__pycache__",
    "data",
    "dist",
    "evidence",
    "mutants",
    "htmlcov",
    "node_modules",
    "third_party",
    "user_data",
    "venv",
    "target",
    "другие проекты",
}

ARCHIVE_PARTS = {"archive", "docs_old", "root_artifacts_20260215", "root_artifacts_20260308"}
DEFAULT_SKIP_PREFIXES = (".venv", "venv-", "tmp-")

ENTRYPOINT_NAMES = {"AGENTS.md", "CLAUDE.md", "GEMINI.md"}
INDEX_NAMES = {"README.md", "index.md"}

TOKEN_RE = re.compile(r"[\wа-яА-ЯёЁ][\wа-яА-ЯёЁ._/-]*", re.UNICODE)
HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
MD_LINK_RE = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")
WIKI_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass(frozen=True)
class Document:
    doc_id: str
    path: str
    title: str
    kind: str
    cluster: str
    role: str
    headings: list[str]
    links: list[str]
    tokens: list[str]
    term_freq: dict[str, int]
    excerpt: str
    size_bytes: int
    mtime: str
    chunks: list[dict[str, Any]]


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def normalize_path(path: str) -> str:
    return path.replace(os.sep, "/").strip("/")


def tokenize(text: str) -> list[str]:
    return [token.lower() for token in TOKEN_RE.findall(text)]


def text_excerpt(text: str, limit: int = 360) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "..."


def strip_markdown_noise(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]+\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"^[-*+]\s+", " ", text, flags=re.M)
    text = re.sub(r"^\s*>\s?", " ", text, flags=re.M)
    return text


def slugify_anchor(text: str) -> str:
    slug = re.sub(r"[^\wа-яА-ЯёЁ -]+", "", text.lower(), flags=re.UNICODE)
    slug = re.sub(r"\s+", "-", slug.strip())
    return slug or "section"


def split_long_text(text: str, *, limit: int = DEFAULT_CHUNK_CHAR_LIMIT) -> list[str]:
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(compact) <= limit:
        return [compact] if compact else []
    parts: list[str] = []
    current: list[str] = []
    current_len = 0
    paragraphs = re.split(r"\n\s*\n", compact)
    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > limit:
            if current:
                parts.append("\n\n".join(current))
                current = []
                current_len = 0
            for start in range(0, len(paragraph), limit):
                parts.append(paragraph[start : start + limit].strip())
            continue
        projected = current_len + len(paragraph) + (2 if current else 0)
        if current and projected > limit:
            parts.append("\n\n".join(current))
            current = [paragraph]
            current_len = len(paragraph)
        else:
            current.append(paragraph)
            current_len = projected
    if current:
        parts.append("\n\n".join(current))
    return parts


def chunks_from_markdown(
    text: str,
    *,
    rel_path: str,
    title: str,
    kind: str,
    cluster: str,
    role: str,
) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    current_heading = title
    current_level = 1
    current_anchor = slugify_anchor(title)
    current_start_line = 1
    buffer: list[str] = []
    ordinal = 0

    def flush(end_line: int) -> None:
        nonlocal ordinal, buffer
        raw_section = "\n".join(buffer).strip()
        cleaned = strip_markdown_noise(raw_section)
        for part_idx, part in enumerate(split_long_text(cleaned)):
            tokens = tokenize(f"{rel_path} {title} {current_heading} {part}")
            if not tokens:
                continue
            suffix = f"-p{part_idx + 1}" if part_idx else ""
            chunk_id = f"{rel_path}#{current_anchor}-{ordinal + 1}{suffix}"
            chunks.append(
                {
                    "id": chunk_id,
                    "path": rel_path,
                    "title": title,
                    "heading": current_heading,
                    "heading_level": current_level,
                    "anchor": current_anchor,
                    "ordinal": ordinal,
                    "part": part_idx + 1,
                    "kind": kind,
                    "cluster": cluster,
                    "role": role,
                    "line_start": current_start_line,
                    "line_end": end_line,
                    "text": text_excerpt(part, DEFAULT_CHUNK_CHAR_LIMIT),
                    "excerpt": text_excerpt(part, 420),
                    "tokens": tokens,
                    "term_freq": dict(Counter(tokens)),
                    "token_count": len(tokens),
                }
            )
            ordinal += 1
        buffer = []

    lines = text.splitlines()
    for line_no, line in enumerate(lines, 1):
        match = HEADING_RE.match(line)
        if match:
            flush(line_no - 1)
            current_heading = match.group(2).strip()
            current_level = len(match.group(1))
            current_anchor = slugify_anchor(current_heading)
            current_start_line = line_no
            buffer = []
        else:
            buffer.append(line)
    flush(len(lines))

    if not chunks:
        cleaned = strip_markdown_noise(text)
        tokens = tokenize(f"{rel_path} {title} {cleaned}")
        if tokens:
            chunks.append(
                {
                    "id": f"{rel_path}#{slugify_anchor(title)}-1",
                    "path": rel_path,
                    "title": title,
                    "heading": title,
                    "heading_level": 1,
                    "anchor": slugify_anchor(title),
                    "ordinal": 0,
                    "part": 1,
                    "kind": kind,
                    "cluster": cluster,
                    "role": role,
                    "line_start": 1,
                    "line_end": len(lines),
                    "text": text_excerpt(cleaned, DEFAULT_CHUNK_CHAR_LIMIT),
                    "excerpt": text_excerpt(cleaned, 420),
                    "tokens": tokens,
                    "term_freq": dict(Counter(tokens)),
                    "token_count": len(tokens),
                }
            )
    return chunks


def should_skip_dir(name: str, *, include_archive: bool) -> bool:
    if name in DEFAULT_SKIP_DIRS:
        return True
    if name.startswith(DEFAULT_SKIP_PREFIXES):
        return True
    if not include_archive and name in ARCHIVE_PARTS:
        return True
    return False


def is_markdown_file(path: Path) -> bool:
    return path.name.endswith((".md", ".mdx")) or path.name in ENTRYPOINT_NAMES


def iter_markdown_under(base: Path, *, include_archive: bool) -> Iterable[Path]:
    if base.is_file():
        if is_markdown_file(base):
            yield base
        return
    if not base.is_dir():
        return
    for dirpath, dirnames, filenames in os.walk(base):
        dirnames[:] = [
            name for name in dirnames if not should_skip_dir(name, include_archive=include_archive)
        ]
        for filename in filenames:
            if is_markdown_file(Path(filename)):
                yield Path(dirpath) / filename


def iter_markdown_files(
    root: Path, *, include_archive: bool, include_paths: Iterable[str] = ()
) -> Iterable[Path]:
    seen: set[Path] = set()
    raw_include_paths = [path for path in include_paths if path]
    bases = [root / path for path in raw_include_paths] if raw_include_paths else [root]
    for base in bases:
        for path in iter_markdown_under(base, include_archive=include_archive):
            try:
                resolved = path.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            yield path


def title_from_markdown(text: str, path: Path) -> str:
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            return match.group(2).strip()
    return path.stem if path.name not in ENTRYPOINT_NAMES else path.name


def headings_from_markdown(text: str, limit: int = 24) -> list[str]:
    headings: list[str] = []
    for line in text.splitlines():
        match = HEADING_RE.match(line)
        if match:
            level = len(match.group(1))
            title = match.group(2).strip()
            headings.append(f"h{level}: {title}")
            if len(headings) >= limit:
                break
    return headings


def classify_kind(rel_path: str) -> str:
    path = normalize_path(rel_path)
    parts = path.split("/")
    name = parts[-1]
    lowered = path.lower()
    if name in ENTRYPOINT_NAMES:
        return "entrypoint"
    if name in INDEX_NAMES:
        return "index"
    if "runbook" in lowered or "/operations/" in lowered or "/05-operations/" in lowered:
        return "runbook"
    if "/verification/" in lowered or "evidence" in lowered or "diagnostic" in lowered:
        return "evidence"
    if "/rfc/" in lowered or "decision" in lowered or "adr" in lowered:
        return "decision"
    if "/architecture/" in lowered or "/01-architecture/" in lowered:
        return "architecture"
    if parts and parts[0] == "services":
        return "service"
    if parts and parts[0] in {"scripts", "infra", "deploy", "deployment"}:
        return "ops"
    return "document"


def cluster_for_path(rel_path: str) -> str:
    parts = normalize_path(rel_path).split("/")
    if len(parts) == 1:
        return "[root]"
    if parts[0] == "docs" and len(parts) > 1:
        return "/".join(parts[:2])
    if parts[0] == "services" and len(parts) > 1:
        return "/".join(parts[:2])
    return parts[0]


def role_for_path(rel_path: str, kind: str) -> str:
    name = Path(rel_path).name
    if name in ENTRYPOINT_NAMES:
        return "entry"
    if name in INDEX_NAMES:
        return "index"
    return kind


def extract_raw_links(text: str) -> list[str]:
    links: list[str] = []
    for match in MD_LINK_RE.finditer(text):
        links.append(match.group(1).strip())
    for match in WIKI_LINK_RE.finditer(text):
        links.append(match.group(1).strip())
    return links


def resolve_markdown_link(source_rel: str, href: str, known_paths: set[str]) -> str | None:
    href = href.strip()
    if not href or href.startswith("#"):
        return None
    parsed = urlparse(href)
    if parsed.scheme or parsed.netloc:
        return None
    clean = unquote(parsed.path).strip()
    if not clean:
        return None
    source_dir = Path(source_rel).parent
    candidates: list[str] = []
    base = normalize_path(str((source_dir / clean).as_posix()))
    candidates.append(base)
    if not Path(base).suffix:
        candidates.extend([f"{base}.md", f"{base}/README.md", f"{base}/index.md"])
    if clean.startswith("/"):
        absolute = normalize_path(clean)
        candidates.extend([absolute, f"{absolute}.md", f"{absolute}/README.md"])
    for candidate in candidates:
        if candidate in known_paths:
            return candidate
    return None


def document_from_path(root: Path, path: Path) -> Document | None:
    rel_path = normalize_path(str(path.relative_to(root)))
    try:
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    cleaned = strip_markdown_noise(text)
    title = title_from_markdown(text, path)
    kind = classify_kind(rel_path)
    cluster = cluster_for_path(rel_path)
    role = role_for_path(rel_path, kind)
    tokens = tokenize(f"{rel_path} {title} {cleaned}")
    term_freq = dict(Counter(tokens))
    stat = path.stat()
    return Document(
        doc_id=rel_path,
        path=rel_path,
        title=title,
        kind=kind,
        cluster=cluster,
        role=role,
        headings=headings_from_markdown(text),
        links=extract_raw_links(text),
        tokens=tokens,
        term_freq=term_freq,
        excerpt=text_excerpt(cleaned),
        size_bytes=stat.st_size,
        mtime=datetime.fromtimestamp(stat.st_mtime, UTC).replace(microsecond=0).isoformat().replace(
            "+00:00", "Z"
        ),
        chunks=chunks_from_markdown(
            text,
            rel_path=rel_path,
            title=title,
            kind=kind,
            cluster=cluster,
            role=role,
        ),
    )


def build_index(
    root: Path,
    *,
    include_archive: bool = False,
    include_paths: Iterable[str] = (),
    profile: str | None = None,
) -> dict[str, Any]:
    root = root.resolve()
    docs = [
        doc
        for path in sorted(
            iter_markdown_files(root, include_archive=include_archive, include_paths=include_paths)
        )
        if (doc := document_from_path(root, path)) is not None
    ]
    known_paths = {doc.path for doc in docs}
    edges: list[dict[str, str]] = []
    edge_seen: set[tuple[str, str, str]] = set()

    def add_edge(source: str, target: str, kind: str) -> None:
        key = (source, target, kind)
        if source == target or key in edge_seen:
            return
        edge_seen.add(key)
        edges.append({"source": source, "target": target, "kind": kind})

    for doc in docs:
        parent = parent_index_for_doc(doc.path, known_paths)
        if parent:
            add_edge(parent, doc.path, "index")
        for href in doc.links:
            target = resolve_markdown_link(doc.path, href, known_paths)
            if target:
                add_edge(doc.path, target, "markdown")

    inbound = Counter(edge["target"] for edge in edges)
    outbound = Counter(edge["source"] for edge in edges)
    df = Counter()
    for doc in docs:
        for term in doc.term_freq:
            df[term] += 1

    doc_payloads = []
    chunk_payloads = []
    for doc in docs:
        doc_payloads.append(
            {
                "id": doc.doc_id,
                "path": doc.path,
                "title": doc.title,
                "kind": doc.kind,
                "cluster": doc.cluster,
                "role": doc.role,
                "headings": doc.headings,
                "links": doc.links[:64],
                "tokens": doc.tokens,
                "term_freq": doc.term_freq,
                "token_count": len(doc.tokens),
                "excerpt": doc.excerpt,
                "size_bytes": doc.size_bytes,
                "mtime": doc.mtime,
                "inbound_count": inbound[doc.path],
                "outbound_count": outbound[doc.path],
            }
        )
        for chunk in doc.chunks:
            chunk_payloads.append(
                {
                    **chunk,
                    "doc_inbound_count": inbound[doc.path],
                    "doc_outbound_count": outbound[doc.path],
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": utc_now(),
        "root": str(root),
        "include_archive": include_archive,
        "include_paths": list(include_paths),
        "profile": profile,
        "documents": doc_payloads,
        "chunks": chunk_payloads,
        "edges": edges,
        "stats": {
            "document_count": len(docs),
            "chunk_count": len(chunk_payloads),
            "edge_count": len(edges),
            "clusters": dict(Counter(doc.cluster for doc in docs)),
            "kinds": dict(Counter(doc.kind for doc in docs)),
            "vocabulary_size": len(df),
        },
    }


def parent_index_for_doc(path: str, known_paths: set[str]) -> str | None:
    p = Path(path)
    candidates: list[str] = []
    for parent in [p.parent, *p.parents]:
        if str(parent) in {".", ""}:
            continue
        candidates.append(normalize_path(str(parent / "README.md")))
        candidates.append(normalize_path(str(parent / "index.md")))
    candidates.extend(["AGENTS.md", "GEMINI.md", "CLAUDE.md", "README.md"])
    for candidate in candidates:
        if candidate in known_paths and candidate != path:
            return candidate
    return None


def load_index(index_path: Path) -> dict[str, Any]:
    return json.loads(index_path.read_text(encoding="utf-8"))


def bm25_search(index: dict[str, Any], query: str, limit: int = 10) -> list[dict[str, Any]]:
    docs = index.get("documents") or []
    terms = tokenize(query)
    if not terms:
        return []
    n_docs = max(1, len(docs))
    avg_len = sum(int(doc.get("token_count") or 0) for doc in docs) / n_docs
    df: Counter[str] = Counter()
    for doc in docs:
        for term in set((doc.get("term_freq") or {}).keys()):
            df[term] += 1
    query_compact = " ".join(terms)
    scored: list[dict[str, Any]] = []
    for doc in docs:
        tf = doc.get("term_freq") or {}
        length = max(1, int(doc.get("token_count") or 1))
        score = 0.0
        for term in terms:
            freq = int(tf.get(term) or 0)
            if freq <= 0:
                continue
            idf = math.log(1 + (n_docs - df[term] + 0.5) / (df[term] + 0.5))
            denom = freq + 1.5 * (1 - 0.75 + 0.75 * (length / max(avg_len, 1.0)))
            score += idf * (freq * 2.5) / denom
        haystacks = [
            str(doc.get("path") or "").lower(),
            str(doc.get("title") or "").lower(),
            str(doc.get("excerpt") or "").lower(),
        ]
        if query.lower() in " ".join(haystacks):
            score += 2.0
        if query_compact and query_compact in " ".join(haystacks):
            score += 0.75
        if score > 0:
            scored.append({**doc, "score": round(score, 6)})
    scored.sort(
        key=lambda row: (
            -float(row.get("score") or 0),
            -int(row.get("inbound_count") or 0),
            str(row.get("path") or ""),
        )
    )
    return scored[:limit]


def bm25_chunk_search(
    index: dict[str, Any],
    query: str,
    *,
    limit: int = DEFAULT_CONTEXT_CHUNK_LIMIT,
    max_per_doc: int = 2,
) -> list[dict[str, Any]]:
    chunks = index.get("chunks") or []
    terms = tokenize(query)
    if not terms:
        return []
    n_chunks = max(1, len(chunks))
    avg_len = sum(int(chunk.get("token_count") or 0) for chunk in chunks) / n_chunks
    df: Counter[str] = Counter()
    for chunk in chunks:
        for term in set((chunk.get("term_freq") or {}).keys()):
            df[term] += 1
    query_lower = query.lower()
    query_compact = " ".join(terms)
    scored: list[dict[str, Any]] = []
    for chunk in chunks:
        tf = chunk.get("term_freq") or {}
        length = max(1, int(chunk.get("token_count") or 1))
        score = 0.0
        for term in terms:
            freq = int(tf.get(term) or 0)
            if freq <= 0:
                continue
            idf = math.log(1 + (n_chunks - df[term] + 0.5) / (df[term] + 0.5))
            denom = freq + 1.5 * (1 - 0.72 + 0.72 * (length / max(avg_len, 1.0)))
            score += idf * (freq * 2.5) / denom
        haystacks = {
            "path": str(chunk.get("path") or "").lower(),
            "title": str(chunk.get("title") or "").lower(),
            "heading": str(chunk.get("heading") or "").lower(),
            "text": str(chunk.get("text") or "").lower(),
        }
        joined = " ".join(haystacks.values())
        if query_lower in joined:
            score += 2.0
        if query_compact and query_compact in joined:
            score += 0.75
        if any(term in haystacks["heading"] for term in terms):
            score += 0.45
        if any(term in haystacks["path"] for term in terms):
            score += 0.25
        if length < 18:
            score *= 0.62
        elif length < 36:
            score *= 0.82
        if score > 0:
            scored.append({**chunk, "score": round(score, 6)})
    scored.sort(
        key=lambda row: (
            -float(row.get("score") or 0),
            -int(row.get("doc_inbound_count") or 0),
            str(row.get("path") or ""),
            int(row.get("ordinal") or 0),
        )
    )
    if max_per_doc <= 0:
        return scored[:limit]
    selected: list[dict[str, Any]] = []
    per_doc: Counter[str] = Counter()
    for row in scored:
        path = str(row.get("path") or "")
        if per_doc[path] >= max_per_doc:
            continue
        selected.append(row)
        per_doc[path] += 1
        if len(selected) >= limit:
            break
    return selected


def render_context(results: list[dict[str, Any]], query: str) -> str:
    lines = [f"# GitMark Memory Context", "", f"Query: `{query}`", ""]
    if not results:
        lines.append("No matching documents found.")
        return "\n".join(lines)
    for idx, doc in enumerate(results, 1):
        lines.extend(
            [
                f"## {idx}. {doc.get('title')} (`{doc.get('path')}`)",
                "",
                f"- score: `{doc.get('score')}`",
                f"- kind: `{doc.get('kind')}`",
                f"- cluster: `{doc.get('cluster')}`",
                f"- links: inbound `{doc.get('inbound_count')}`, outbound `{doc.get('outbound_count')}`",
            ]
        )
        headings = doc.get("headings") or []
        if headings:
            lines.append(f"- headings: {', '.join(f'`{h}`' for h in headings[:6])}")
        excerpt = str(doc.get("excerpt") or "").strip()
        if excerpt:
            lines.extend(["", excerpt])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_chunk_context(results: list[dict[str, Any]], query: str) -> str:
    lines = ["# GitMark RAG Context", "", f"Query: `{query}`", ""]
    if not results:
        lines.append("No matching chunks found.")
        return "\n".join(lines)
    for idx, chunk in enumerate(results, 1):
        path = chunk.get("path")
        heading = chunk.get("heading") or chunk.get("title")
        line_start = chunk.get("line_start")
        location = f"{path}:{line_start}" if line_start else str(path)
        lines.extend(
            [
                f"## {idx}. {heading} (`{location}`)",
                "",
                f"- score: `{chunk.get('score')}`",
                f"- document: `{chunk.get('title')}`",
                f"- kind: `{chunk.get('kind')}`",
                f"- cluster: `{chunk.get('cluster')}`",
                f"- chunk: `{chunk.get('id')}`",
            ]
        )
        text = str(chunk.get("text") or chunk.get("excerpt") or "").strip()
        if text:
            lines.extend(["", text])
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(index: dict[str, Any], out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / DEFAULT_INDEX_NAME
    html_path = out_dir / DEFAULT_HTML_NAME
    index_path.write_text(json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    html_path.write_text(render_html(index), encoding="utf-8")
    return index_path, html_path


def safe_script_json(payload: dict[str, Any]) -> str:
    """Return JSON that is safe to embed in a non-executed script tag."""
    return (
        json.dumps(payload, ensure_ascii=False)
        .replace("</", "<\\/")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def graph_nodes_and_edges(index: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    documents = index.get("documents", [])
    nodes: list[dict[str, Any]] = [
        {
            "id": "folder:[root]",
            "path": "[root]",
            "title": "[root]",
            "kind": "root",
            "cluster": "[root]",
            "role": "root",
            "node_type": "folder",
            "headings": [],
            "excerpt": "Repository root",
            "inbound_count": 0,
            "outbound_count": 0,
            "child_count": 0,
        }
    ]
    graph_edges: list[dict[str, str]] = []
    seen_nodes = {"folder:[root]"}
    seen_edges: set[tuple[str, str, str]] = set()

    def add_node(node: dict[str, Any]) -> None:
        node_id = str(node["id"])
        if node_id in seen_nodes:
            return
        seen_nodes.add(node_id)
        nodes.append(node)

    def add_edge(source: str, target: str, kind: str) -> None:
        key = (source, target, kind)
        if source == target or key in seen_edges:
            return
        seen_edges.add(key)
        graph_edges.append({"source": source, "target": target, "kind": kind})

    folder_child_counts: Counter[str] = Counter()
    known_folders: set[str] = set()
    for doc in documents:
        path = str(doc.get("path") or "")
        parent = normalize_path(str(Path(path).parent))
        folder = "[root]" if parent in {"", "."} else parent
        folder_child_counts[folder] += 1
        parts = [] if folder == "[root]" else folder.split("/")
        for idx in range(1, len(parts) + 1):
            known_folders.add("/".join(parts[:idx]))

    for folder in sorted(known_folders):
        parent_path = normalize_path(str(Path(folder).parent))
        parent_id = "folder:[root]" if parent_path in {"", "."} else f"folder:{parent_path}"
        folder_id = f"folder:{folder}"
        add_node(
            {
                "id": folder_id,
                "path": folder,
                "title": folder,
                "kind": "folder",
                "cluster": folder.split("/")[0],
                "role": "folder",
                "node_type": "folder",
                "headings": [],
                "excerpt": f"Folder with {folder_child_counts[folder]} indexed Markdown document(s).",
                "inbound_count": 0,
                "outbound_count": folder_child_counts[folder],
                "child_count": folder_child_counts[folder],
            }
        )
        add_edge(parent_id, folder_id, "folder")

    for doc in documents:
        path = str(doc.get("path") or "")
        parent = normalize_path(str(Path(path).parent))
        folder_id = "folder:[root]" if parent in {"", "."} else f"folder:{parent}"
        doc_id = f"doc:{path}"
        add_node(
            {
                key: doc.get(key)
                for key in (
                    "path",
                    "title",
                    "kind",
                    "cluster",
                    "role",
                    "headings",
                    "excerpt",
                    "inbound_count",
                    "outbound_count",
                )
            }
            | {
                "id": doc_id,
                "node_type": "document",
                "child_count": 0,
            }
        )
        add_edge(folder_id, doc_id, "contains")

    for edge in index.get("edges", []):
        add_edge(f"doc:{edge['source']}", f"doc:{edge['target']}", str(edge.get("kind") or "markdown"))

    inbound = Counter(edge["target"] for edge in graph_edges)
    outbound = Counter(edge["source"] for edge in graph_edges)
    for node in nodes:
        node["graph_inbound_count"] = inbound[str(node["id"])]
        node["graph_outbound_count"] = outbound[str(node["id"])]
    return nodes, graph_edges


def render_html(index: dict[str, Any]) -> str:
    graph_nodes, graph_edges = graph_nodes_and_edges(index)
    graph_data = {
        "generated_at": index.get("generated_at"),
        "root": index.get("root"),
        "profile": index.get("profile"),
        "include_paths": index.get("include_paths"),
        "stats": index.get("stats"),
        "documents": index.get("documents", []),
        "nodes": graph_nodes,
        "edges": graph_edges,
    }
    data_json = safe_script_json(graph_data)
    return f"""<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<link rel="icon" href="data:,">
<title>GitMark Memory Bank</title>
<style>
:root {{ color-scheme: dark; --bg:#070807; --panel:#111411; --text:#d9f7e8; --muted:#88a296; --accent:#29f59f; --edge:#234237; }}
* {{ box-sizing: border-box; }}
body {{ margin:0; background:var(--bg); color:var(--text); font:13px/1.45 ui-monospace,SFMono-Regular,Menlo,Consolas,monospace; overflow:hidden; }}
header {{ position:fixed; top:0; left:0; right:0; height:42px; display:flex; align-items:center; gap:14px; padding:7px 12px; background:rgba(10,12,10,.92); border-bottom:1px solid #1c2a22; z-index:3; }}
header strong {{ color:#fff; }}
.pill {{ padding:3px 8px; border:1px solid #214534; border-radius:6px; color:var(--muted); }}
.pill.on {{ background:var(--accent); color:#03160d; border-color:var(--accent); font-weight:700; }}
#search {{ margin-left:auto; width:min(360px,28vw); background:#0c100d; color:var(--text); border:1px solid #1d2a22; border-radius:6px; padding:7px 10px; }}
#canvas {{ position:fixed; inset:42px 0 0 0; width:100vw; height:calc(100vh - 42px); }}
.legend, .controls, .details, .hint {{ position:fixed; z-index:4; background:rgba(13,16,14,.88); border:1px solid #1d2a22; border-radius:8px; box-shadow:0 8px 30px rgba(0,0,0,.35); }}
.legend {{ left:12px; top:54px; padding:10px 12px; min-width:210px; }}
.controls {{ right:12px; top:54px; width:min(360px,30vw); padding:10px 12px; }}
.details {{ right:12px; top:254px; width:min(420px,34vw); max-height:calc(100vh - 320px); overflow:auto; padding:12px; }}
.hint {{ left:50%; bottom:16px; transform:translateX(-50%); padding:7px 12px; color:var(--muted); }}
.row {{ display:flex; align-items:center; gap:7px; margin:3px 0; }}
.controls .row {{ justify-content:space-between; }}
.checks {{ display:grid; grid-template-columns:1fr 1fr; gap:5px 12px; margin-top:8px; }}
.modes {{ display:flex; gap:6px; margin-top:8px; }}
.modes button {{ flex:1; }}
button.active {{ background:var(--accent); color:#03160d; border-color:var(--accent); font-weight:700; }}
.links {{ margin-top:10px; border-top:1px solid #26382f; padding-top:8px; }}
.links div {{ margin:4px 0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
.dot {{ width:9px; height:9px; border-radius:50%; display:inline-block; }}
.muted {{ color:var(--muted); }}
a {{ color:#66ffd0; }}
pre {{ white-space:pre-wrap; color:#c8e9da; }}
button {{ background:#142018; color:var(--text); border:1px solid #284637; border-radius:6px; padding:5px 8px; cursor:pointer; }}
label {{ color:var(--muted); display:block; margin:4px 0; }}
input[type="checkbox"] {{ accent-color:var(--accent); }}
</style>
</head>
<body>
<header>
  <strong>GitMark</strong>
  <span>Memory Bank</span>
  <span class="pill on">Граф</span>
  <span class="pill">Документы: {len(index.get('documents', []))}</span>
  <span class="pill">Узлы: <span id="nodeCount">0</span>/{len(graph_data['nodes'])}</span>
  <span class="pill">Связи: <span id="edgeCount">0</span>/{len(graph_data['edges'])}</span>
  <input id="search" placeholder="фильтр файлов..." autocomplete="off">
</header>
<canvas id="canvas"></canvas>
<aside class="legend" id="legend"></aside>
<aside class="controls">
  <div class="row"><b>Фильтры</b><button id="fit">центр</button></div>
  <div class="checks">
    <label><input id="showFolder" type="checkbox"> структура</label>
    <label><input id="showMarkdown" type="checkbox" checked> ссылки</label>
    <label><input id="showIndex" type="checkbox"> индексы</label>
    <label><input id="freeMode" type="checkbox" checked> гравитация</label>
    <label><input id="focusOnly" type="checkbox"> только соседи</label>
  </div>
  <div class="modes">
    <button id="modeOverview" class="active">обзор</button>
    <button id="modeMap">карта</button>
    <button id="modeFull">всё</button>
  </div>
</aside>
<aside class="details" id="details"><b>Выберите узел</b><p class="muted">Клик по точке покажет документ, заголовки и команду для контекста.</p></aside>
<div class="hint">центр = entrypoint | drag = таскать | колесо = zoom | клик = открыть карточку</div>
<script id="graph-data" type="application/json">{data_json}</script>
<script>
const data = JSON.parse(document.getElementById('graph-data').textContent);
const canvas = document.getElementById('canvas');
const ctx = canvas.getContext('2d');
const details = document.getElementById('details');
const search = document.getElementById('search');
const showFolder = document.getElementById('showFolder');
const showMarkdown = document.getElementById('showMarkdown');
const showIndex = document.getElementById('showIndex');
const freeMode = document.getElementById('freeMode');
const focusOnly = document.getElementById('focusOnly');
const nodeCount = document.getElementById('nodeCount');
const edgeCount = document.getElementById('edgeCount');
const modeButtons = {{
  overview: document.getElementById('modeOverview'),
  map: document.getElementById('modeMap'),
  full: document.getElementById('modeFull')
}};
const colors = {{
  root:'#ffffff', folder:'#18b879',
  entrypoint:'#29f59f', index:'#27d88f', runbook:'#50d0d4', evidence:'#a777ff',
  decision:'#ffb562', architecture:'#8ee668', service:'#6aa8ff', ops:'#d1d1d1', document:'#7e8f87'
}};
function hashText(s) {{
  let h = 2166136261;
  for (let i = 0; i < String(s).length; i++) {{
    h ^= String(s).charCodeAt(i);
    h = Math.imul(h, 16777619);
  }}
  return h >>> 0;
}}
const clusters = [...new Set(data.nodes.map(n => n.cluster || '[root]'))].sort();
const clusterSlot = new Map(clusters.map((name, i) => [name, i]));
const nodes = data.nodes.map((d, i) => ({{
  ...d, vx:0, vy:0, r: d.kind==='root' ? 18 : (d.node_type==='folder'
    ? Math.max(7, Math.min(15, 6 + (d.child_count||0)*.5 + (d.graph_outbound_count||0)*.15))
    : Math.max(4, Math.min(15, 4 + (d.inbound_count||0)*1.1 + (d.outbound_count||0)*.35)))
}}));
for (const n of nodes) {{
  const slot = clusterSlot.get(n.cluster || '[root]') || 0;
  const baseAngle = clusters.length ? (Math.PI * 2 * slot / clusters.length) : 0;
  const h = hashText(n.path || n.id || '');
  const jitter = ((h % 1000) / 1000 - .5) * .62;
  const depth = Math.max(0, String(n.path || '').split('/').length - 1);
  const ring = n.kind==='root' ? 0 : (n.kind==='entrypoint' ? 80 : (n.node_type==='folder' ? 170 + depth * 28 : 320 + (h % 220)));
  n.x = Math.cos(baseAngle + jitter) * ring + Math.cos(h % 628 / 100) * 32;
  n.y = Math.sin(baseAngle + jitter) * ring + Math.sin(h % 628 / 100) * 32;
}}
const byId = new Map(nodes.map(n => [n.id, n]));
const edges = data.edges.map(e => ({{...e, source:byId.get(e.source), target:byId.get(e.target)}})).filter(e => e.source && e.target);
const neighbors = new Map(nodes.map(n => [n.id, new Set()]));
for (const e of edges) {{
  neighbors.get(e.source.id).add(e.target.id);
  neighbors.get(e.target.id).add(e.source.id);
}}
let scale = 1, ox = 0, oy = 0, drag = null, pan = null, selected = null, filter = '', simTicks = 0, statTick = 0;
function fitVisible() {{
  const visible = nodes.filter(nodeVisible);
  if (!visible.length) return;
  let minX=Infinity, minY=Infinity, maxX=-Infinity, maxY=-Infinity;
  for (const n of visible) {{
    minX = Math.min(minX, n.x - n.r * 2);
    minY = Math.min(minY, n.y - n.r * 2);
    maxX = Math.max(maxX, n.x + n.r * 2);
    maxY = Math.max(maxY, n.y + n.r * 2);
  }}
  const w = canvas.width/devicePixelRatio, h = canvas.height/devicePixelRatio;
  const graphW = Math.max(80, maxX - minX), graphH = Math.max(80, maxY - minY);
  const marginX = w < 900 ? 32 : 330;
  const marginY = h < 700 ? 72 : 150;
  scale = Math.max(.28, Math.min(2.2, Math.min((w - marginX) / graphW, (h - marginY) / graphH)));
  const cx = (minX + maxX) / 2, cy = (minY + maxY) / 2;
  ox = -cx * scale;
  oy = -cy * scale;
  restartSim();
}}
function resize() {{ canvas.width = innerWidth * devicePixelRatio; canvas.height = (innerHeight-42) * devicePixelRatio; canvas.style.top='42px'; fitVisible(); }}
resize(); addEventListener('resize', resize);
function passes(n) {{ return !filter || (n.path+' '+n.title+' '+n.cluster+' '+n.kind).toLowerCase().includes(filter); }}
function selectedSet() {{
  if (!selected) return null;
  return new Set([selected.id, ...(neighbors.get(selected.id) || [])]);
}}
function inFocus(n) {{
  const set = selectedSet();
  return !set || set.has(n.id);
}}
function nodeVisible(n) {{
  if (!passes(n)) return false;
  if (!showFolder.checked && n.node_type==='folder' && n.kind!=='root') return false;
  if (focusOnly.checked && selected && !inFocus(n)) return false;
  return true;
}}
function edgeVisible(e) {{
  if (!nodeVisible(e.source)||!nodeVisible(e.target)) return false;
  if (focusOnly.checked && selected && e.source !== selected && e.target !== selected) return false;
  if ((e.kind==='folder'||e.kind==='contains') && !showFolder.checked) return false;
  if (e.kind==='markdown' && !showMarkdown.checked) return false;
  if (e.kind==='index' && !showIndex.checked) return false;
  return true;
}}
function restartSim() {{ simTicks = 0; }}
function setMode(mode) {{
  showFolder.checked = mode !== 'overview';
  showMarkdown.checked = mode !== 'map';
  showIndex.checked = mode === 'full';
  focusOnly.checked = false;
  freeMode.checked = true;
  for (const [name, btn] of Object.entries(modeButtons)) btn.classList.toggle('active', name === mode);
  restartSim();
  setTimeout(fitVisible, 40);
}}
function updateCounts() {{
  if (statTick++ % 12) return;
  let visibleNodes = 0, visibleEdges = 0;
  for (const n of nodes) if (nodeVisible(n)) visibleNodes++;
  for (const e of edges) if (edgeVisible(e)) visibleEdges++;
  nodeCount.textContent = String(visibleNodes);
  edgeCount.textContent = String(visibleEdges);
}}
function sim() {{
  if (simTicks++ > 240 && !drag) return;
  for (const n of nodes) {{ n.fx = 0; n.fy = 0; }}
  for (const e of edges) {{
    const a=e.source,b=e.target; if (!edgeVisible(e)) continue;
    const dx=b.x-a.x, dy=b.y-a.y, dist=Math.hypot(dx,dy)||1, target=e.kind==='index'?86:132;
    const strength=(e.kind==='folder'||e.kind==='contains') ? 0.006 : 0.004;
    const f=(dist-target)*strength; const ux=dx/dist, uy=dy/dist;
    a.vx += f*ux; a.vy += f*uy; b.vx -= f*ux; b.vy -= f*uy;
  }}
  for (let i=0;i<nodes.length;i++) for (let j=i+1;j<nodes.length;j++) {{
    const a=nodes[i],b=nodes[j]; if(!nodeVisible(a)||!nodeVisible(b)) continue;
    const dx=b.x-a.x, dy=b.y-a.y, d2=dx*dx+dy*dy+30, f=70/d2;
    a.vx -= dx*f; a.vy -= dy*f; b.vx += dx*f; b.vy += dy*f;
  }}
  for (const n of nodes) {{
    const gravity = !freeMode.checked ? 0.0008 : (n.kind==='root' ? 0.035 : (n.kind==='entrypoint' ? 0.014 : (n.node_type==='folder' ? 0.005 : 0.002)));
    n.vx += -n.x*gravity; n.vy += -n.y*gravity;
    const speed = Math.hypot(n.vx, n.vy);
    if (speed > 18) {{ n.vx = n.vx / speed * 18; n.vy = n.vy / speed * 18; }}
    n.vx *= .86; n.vy *= .86;
    if (drag !== n) {{ n.x += n.vx; n.y += n.vy; }}
  }}
}}
function world(px, py) {{ return {{x:(px - canvas.width/devicePixelRatio/2 - ox)/scale, y:(py - (canvas.height/devicePixelRatio)/2 - oy)/scale}}; }}
function screen(n) {{ return {{x:canvas.width/devicePixelRatio/2 + ox + n.x*scale, y:(canvas.height/devicePixelRatio)/2 + oy + n.y*scale}}; }}
function inView(p, pad=90) {{ const w=canvas.width/devicePixelRatio, h=canvas.height/devicePixelRatio; return p.x>-pad && p.x<w+pad && p.y>-pad && p.y<h+pad; }}
function labelPriority(n) {{
  if (selected===n) return 9999;
  if (n.kind==='root') return 9000;
  if (n.kind==='entrypoint') return 8000;
  if (n.node_type==='folder') return 5000 + (n.child_count||0);
  return (n.inbound_count||0)*8 + (n.outbound_count||0)*2;
}}
function wantsLabel(n) {{
  if (selected===n || n.kind==='root' || n.kind==='entrypoint') return true;
  if (selected && inFocus(n)) return true;
  if (filter) return true;
  if (n.node_type==='folder') return (n.child_count||0) >= 18 || scale > 1.55;
  if (n.role==='index') return scale > 1.35;
  return scale > 1.95 && ((n.inbound_count||0) + (n.outbound_count||0)) > 1;
}}
function drawLabels(items) {{
  const placed = [];
  let count = 0;
  items.sort((a,b) => b.priority-a.priority);
  ctx.font=`${{Math.max(9, Math.min(12, 10.5*scale))}}px ui-monospace`;
  for (const item of items) {{
    if (count >= 130) break;
    const text = item.n.title.slice(0, item.n.node_type==='folder' ? 34 : 46);
    const w = ctx.measureText(text).width + 12, h = 14;
    const box = {{x:item.p.x + 8, y:item.p.y - 18, w, h}};
    if (box.x < 0 || box.y < 42 || box.x + box.w > canvas.width/devicePixelRatio || box.y + box.h > canvas.height/devicePixelRatio) continue;
    if (placed.some(b => !(box.x+box.w<b.x || b.x+b.w<box.x || box.y+box.h<b.y || b.y+b.h<box.y))) continue;
    placed.push(box); count++;
    ctx.fillStyle='rgba(2,8,5,.62)';
    ctx.fillRect(box.x-3, box.y-1, box.w, box.h);
    ctx.fillStyle='#dff8ed';
    ctx.fillText(text, box.x, box.y + 10);
  }}
}}
function draw() {{
  sim();
  updateCounts();
  ctx.setTransform(1,0,0,1,0,0);
  ctx.clearRect(0,0,canvas.width,canvas.height);
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  ctx.lineWidth=1;
  let drawnEdges = 0;
  for (const e of edges) {{
    if(!edgeVisible(e)) continue;
    const a=screen(e.source), b=screen(e.target);
    if(!inView(a) || !inView(b)) continue;
    if(++drawnEdges > 950) break;
    const active = selected && (e.source===selected || e.target===selected);
    const dim = selected && !active && !focusOnly.checked;
    ctx.strokeStyle=e.kind==='folder'
      ? 'rgba(52,255,160,' + (active ? .42 : (dim ? .035 : .13)) + ')'
      : (e.kind==='contains'
        ? 'rgba(52,255,160,' + (active ? .32 : (dim ? .025 : .055)) + ')'
        : (e.kind==='index'
          ? 'rgba(58,255,170,' + (active ? .55 : (dim ? .045 : .25)) + ')'
          : 'rgba(120,150,135,' + (active ? .62 : (dim ? .04 : .17)) + ')'));
    ctx.lineWidth = active ? 2 : 1;
    ctx.beginPath(); ctx.moveTo(a.x,a.y); ctx.lineTo(b.x,b.y); ctx.stroke();
  }}
  ctx.lineWidth=1;
  const labelItems = [];
  for (const n of nodes) {{
    if(!nodeVisible(n)) continue;
    const p=screen(n), c=colors[n.kind]||colors.document;
    if(!inView(p)) continue;
    ctx.beginPath(); ctx.fillStyle=c; ctx.globalAlpha=selected===n?1:.86;
    if(selected && selected!==n && !inFocus(n) && !focusOnly.checked) ctx.globalAlpha=.22;
    if (n.node_type==='folder') {{ ctx.rect(p.x-n.r*scale,p.y-n.r*scale,n.r*2*scale,n.r*2*scale); }} else {{ ctx.arc(p.x,p.y,n.r*scale,0,Math.PI*2); }}
    ctx.fill();
    ctx.globalAlpha=.35; ctx.strokeStyle=c; ctx.beginPath(); ctx.arc(p.x,p.y,(n.r+5)*scale,0,Math.PI*2); ctx.stroke(); ctx.globalAlpha=1;
    if (wantsLabel(n)) labelItems.push({{n, p, priority: labelPriority(n)}});
  }}
  drawLabels(labelItems);
  requestAnimationFrame(draw);
}}
function show(n) {{
  selected=n;
  const heads=(n.headings||[]).slice(0,10).map(h=>`<li>${{escapeHtml(h)}}</li>`).join('');
  const linked = edges
    .filter(e => e.source===n || e.target===n)
    .filter(e => edgeVisible({{...e, source:e.source, target:e.target}}) || e.kind==='markdown')
    .slice(0,12)
    .map(e => {{
      const other = e.source===n ? e.target : e.source;
      return `<div><span class="muted">${{escapeHtml(e.kind)}}</span> <a href="#" data-node="${{escapeHtml(other.id)}}">${{escapeHtml(other.title || other.path)}}</a></div>`;
    }}).join('');
  const openLink = n.node_type==='document'
    ? `<p><a href="/${{encodeURI(n.path)}}" target="_blank" rel="noreferrer">открыть markdown</a></p>`
    : '';
  const contextCommand = n.node_type==='document'
    ? `<pre>python3 scripts/gitmark_memory_bank.py context "${{escapeHtml(n.title.replaceAll('"',''))}}"</pre>`
    : `<pre>python3 scripts/gitmark_memory_bank.py search "${{escapeHtml(n.path.replaceAll('"',''))}}"</pre>`;
  details.innerHTML = `<b>${{escapeHtml(n.title)}}</b><p><code>${{escapeHtml(n.path)}}</code></p>
  <p><span class="pill">${{n.kind}}</span> <span class="pill">${{n.cluster}}</span></p>
  <p class="muted">graph in ${{n.graph_inbound_count||0}} | graph out ${{n.graph_outbound_count||0}}</p>
  ${{openLink}}<p>${{escapeHtml(n.excerpt||'')}}</p>${{heads?'<ul>'+heads+'</ul>':''}}
  ${{linked?'<div class="links"><b>Связи</b>'+linked+'</div>':''}}
  ${{contextCommand}}`;
  details.querySelectorAll('[data-node]').forEach(a => a.addEventListener('click', ev => {{
    ev.preventDefault();
    const next = byId.get(a.getAttribute('data-node'));
    if (next) {{ show(next); fitVisible(); restartSim(); }}
  }}));
  if (focusOnly.checked) setTimeout(fitVisible, 40);
  restartSim();
}}
function escapeHtml(s) {{ return String(s).replace(/[&<>"']/g, m => ({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[m])); }}
canvas.addEventListener('mousedown', e => {{
  const p=world(e.offsetX,e.offsetY);
  drag = nodes.filter(nodeVisible).find(n => Math.hypot(n.x-p.x,n.y-p.y) < n.r/scale + 8) || null;
  if (drag) show(drag);
  else pan = {{x:e.clientX, y:e.clientY, ox, oy}};
}});
canvas.addEventListener('mousemove', e => {{
  if(drag) {{ const p=world(e.offsetX,e.offsetY); drag.x=p.x; drag.y=p.y; drag.vx=drag.vy=0; restartSim(); }}
  else if(pan) {{ ox = pan.ox + (e.clientX - pan.x); oy = pan.oy + (e.clientY - pan.y); }}
}});
canvas.addEventListener('mouseup', () => {{ drag=null; pan=null; }});
canvas.addEventListener('mouseleave', () => {{ drag=null; pan=null; }});
canvas.addEventListener('wheel', e => {{ e.preventDefault(); const factor=e.deltaY<0?1.1:.9; scale=Math.max(.25,Math.min(4,scale*factor)); }}, {{passive:false}});
search.addEventListener('input', () => {{ filter=search.value.toLowerCase().trim(); restartSim(); setTimeout(fitVisible, 40); }});
for (const el of [showFolder, showMarkdown, showIndex, freeMode, focusOnly]) el.addEventListener('change', () => {{ restartSim(); setTimeout(fitVisible, 40); }});
modeButtons.overview.addEventListener('click', () => setMode('overview'));
modeButtons.map.addEventListener('click', () => setMode('map'));
modeButtons.full.addEventListener('click', () => setMode('full'));
document.getElementById('fit').addEventListener('click', fitVisible);
const kinds = Object.entries(colors).map(([k,c]) => `<div class="row"><span class="dot" style="background:${{c}}"></span>${{k}}</div>`).join('');
document.getElementById('legend').innerHTML = `<b>Легенда</b>${{kinds}}<hr><div class="muted">root: ${{escapeHtml(data.root||'')}}</div><div class="muted">generated: ${{escapeHtml(data.generated_at||'')}}</div>`;
setTimeout(fitVisible, 80);
draw();
</script>
</body>
</html>
"""


def command_build(args: argparse.Namespace) -> int:
    include_paths = tuple(args.include_path or ())
    profile = args.profile
    if profile == "rag" and not include_paths:
        include_paths = RAG_PROFILE_INCLUDE_PATHS
    index = build_index(
        Path(args.root),
        include_archive=args.include_archive,
        include_paths=include_paths,
        profile=profile,
    )
    index_path, html_path = write_outputs(index, Path(args.out_dir))
    print(json.dumps({
        "index": str(index_path),
        "graph": str(html_path),
        "documents": index["stats"]["document_count"],
        "chunks": index["stats"]["chunk_count"],
        "edges": index["stats"]["edge_count"],
    }, ensure_ascii=False, indent=2))
    return 0


def command_search(args: argparse.Namespace) -> int:
    index = load_index(Path(args.index))
    if args.chunks:
        results = bm25_chunk_search(
            index,
            args.query,
            limit=args.limit,
            max_per_doc=args.max_per_doc,
        )
    else:
        results = bm25_search(index, args.query, limit=args.limit)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for idx, row in enumerate(results, 1):
            if args.chunks:
                print(
                    f"{idx}. {row['score']:.3f} {row['path']}:{row.get('line_start')} — {row.get('heading')}"
                )
            else:
                print(f"{idx}. {row['score']:.3f} {row['path']} — {row['title']}")
    return 0 if results else 1


def command_context(args: argparse.Namespace) -> int:
    index = load_index(Path(args.index))
    if args.documents:
        results = bm25_search(index, args.query, limit=args.limit)
        print(render_context(results, args.query))
    else:
        results = bm25_chunk_search(
            index,
            args.query,
            limit=args.limit,
            max_per_doc=args.max_per_doc,
        )
        print(render_chunk_context(results, args.query))
    return 0 if results else 1


def command_graph(args: argparse.Namespace) -> int:
    index = load_index(Path(args.index))
    html_path = Path(args.out)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(render_html(index), encoding="utf-8")
    print(str(html_path))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build and query a GitMark-style Markdown memory bank.")
    parser.add_argument("--root", default=".", help="Repository root for build mode.")
    parser.add_argument("--out-dir", default=DEFAULT_OUT_DIR, help="Output directory for build mode.")
    parser.add_argument("--index", default=f"{DEFAULT_OUT_DIR}/{DEFAULT_INDEX_NAME}", help="Index JSON path.")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build index.json and graph.html.")
    build.add_argument("--root", default=".")
    build.add_argument("--out-dir", default=DEFAULT_OUT_DIR)
    build.add_argument("--include-archive", action="store_true")
    build.add_argument(
        "--profile",
        choices=["rag"],
        help="Use a maintained include-path set. The rag profile indexes project docs, agent instructions, skills, services, scripts, and supporting runbooks.",
    )
    build.add_argument(
        "--include-path",
        action="append",
        default=[],
        help="Limit the build to a file or directory relative to --root. Can be passed multiple times.",
    )
    build.set_defaults(func=command_build)

    search = sub.add_parser("search", help="Search the memory bank.")
    search.add_argument("query")
    search.add_argument("--index", default=f"{DEFAULT_OUT_DIR}/{DEFAULT_INDEX_NAME}")
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--chunks", action="store_true", help="Search section chunks instead of whole documents.")
    search.add_argument("--max-per-doc", type=int, default=2, help="Maximum chunk hits per document when --chunks is used. Use 0 to disable.")
    search.add_argument("--json", action="store_true")
    search.set_defaults(func=command_search)

    context = sub.add_parser("context", help="Render top-k RAG chunks as agent context.")
    context.add_argument("query")
    context.add_argument("--index", default=f"{DEFAULT_OUT_DIR}/{DEFAULT_INDEX_NAME}")
    context.add_argument("--limit", type=int, default=DEFAULT_CONTEXT_CHUNK_LIMIT)
    context.add_argument("--max-per-doc", type=int, default=2)
    context.add_argument("--documents", action="store_true", help="Use legacy whole-document context.")
    context.set_defaults(func=command_context)

    graph = sub.add_parser("graph", help="Regenerate graph.html from index.json.")
    graph.add_argument("--index", default=f"{DEFAULT_OUT_DIR}/{DEFAULT_INDEX_NAME}")
    graph.add_argument("--out", default=f"{DEFAULT_OUT_DIR}/{DEFAULT_HTML_NAME}")
    graph.set_defaults(func=command_graph)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
