#!/usr/bin/env python3
"""Compare the sanitized NL server profile with the local workspace.

The script reads local profile files only. It does not connect to NL.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HASH_RE = re.compile(r"^([a-fA-F0-9]{64})\s+(/\S+)")
SKIP_DIRS = {
    ".git",
    "node_modules",
    "СЕМЕЙНЫЙ_АРХИВ_ИТОГ",
    ".tmp",
    ".cache",
    ".venv",
    "venv",
    "vpn_env",
    "__pycache__",
}
SERVER_RUNTIME_PREFIXES = (
    "/usr/local/x-ui/",
    "/etc/x-ui/",
)
SERVER_BACKUP_MARKERS = (".bak-", ".backup", ".old")


@dataclass(frozen=True)
class RemoteArtifact:
    component: str
    sha256: str
    remote_path: str

    @property
    def name(self) -> str:
        return Path(self.remote_path).name


def load_redacted_reviews(root: Path) -> dict[str, list[dict[str, str]]]:
    reviews: dict[str, list[dict[str, str]]] = defaultdict(list)
    redacted_root = root / "services" / "nl-server" / "redacted"
    if not redacted_root.is_dir():
        return reviews

    for meta_path in redacted_root.rglob("*.meta.json"):
        try:
            meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        raw_sha256 = str(meta.get("raw_sha256", "")).lower()
        target_path = str(meta.get("target_path", ""))
        remote_path = str(meta.get("remote_path", ""))
        if not re.fullmatch(r"[a-f0-9]{64}", raw_sha256):
            continue
        if meta.get("raw_saved_locally") is not False or meta.get("deployable") is not False:
            continue

        local_path = root / "services" / "nl-server" / target_path
        reviews[raw_sha256].append(
            {
                "remote_path": remote_path,
                "local_path": str(local_path.relative_to(root)),
                "meta_path": str(meta_path.relative_to(root)),
            }
        )
    return reviews


def load_redacted_templates(root: Path) -> dict[str, list[dict[str, str]]]:
    templates: dict[str, list[dict[str, str]]] = defaultdict(list)
    templates_root = root / "services" / "nl-server" / "templates"
    if not templates_root.is_dir():
        return templates

    for meta_path in templates_root.rglob("*.meta.json"):
        try:
            meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        raw_sha256 = str(meta.get("raw_sha256", "")).lower()
        target_path = str(meta.get("target_path", ""))
        remote_path = str(meta.get("remote_path", ""))
        deployable = meta.get("deployable_to_nl", meta.get("deployable"))
        if not re.fullmatch(r"[a-f0-9]{64}", raw_sha256):
            continue
        if meta.get("raw_saved_locally") is not False or deployable is not False:
            continue

        if target_path.startswith("services/nl-server/"):
            local_path = root / target_path
        else:
            local_path = root / "services" / "nl-server" / target_path
        templates[raw_sha256].append(
            {
                "remote_path": remote_path,
                "local_path": str(local_path.relative_to(root)),
                "meta_path": str(meta_path.relative_to(root)),
            }
        )
    return templates


def load_accepted_local_deltas(root: Path) -> dict[str, list[dict[str, str]]]:
    manifest_path = root / "services" / "nl-server" / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        manifest: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    deltas: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in manifest.get("accepted_local_deltas") or []:
        if not isinstance(row, dict):
            continue
        remote_path = str(row.get("remote_path", ""))
        local_path = str(row.get("local_path", ""))
        remote_sha256 = str(row.get("remote_sha256", "")).lower()
        local_sha256 = str(row.get("local_sha256", "")).lower()
        if row.get("deployable_to_nl") is not False:
            continue
        if not remote_path or not local_path:
            continue
        if not re.fullmatch(r"[a-f0-9]{64}", remote_sha256):
            continue
        if not re.fullmatch(r"[a-f0-9]{64}", local_sha256):
            continue
        deltas[remote_path].append(
            {
                "local_path": local_path,
                "remote_sha256": remote_sha256,
                "local_sha256": local_sha256,
                "reason": str(row.get("reason", "")),
            }
        )
    return deltas


def parse_hash_file(path: Path, component: str) -> list[RemoteArtifact]:
    artifacts: list[RemoteArtifact] = []
    if not path.exists():
        return artifacts
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        match = HASH_RE.match(line.strip())
        if not match:
            continue
        artifacts.append(RemoteArtifact(component, match.group(1).lower(), match.group(2)))
    return artifacts


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def list_local_files(root: Path) -> list[Path]:
    files: list[Path] = []
    try:
        result = subprocess.run(
            [
                "rg",
                "--files",
                "-g",
                "!node_modules/**",
                "-g",
                "!.git/**",
                "-g",
                "!СЕМЕЙНЫЙ_АРХИВ_ИТОГ/**",
                "-g",
                "!.tmp/**",
                "-g",
                "!__pycache__/**",
            ],
            cwd=root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode in (0, 1):
            files.extend(root / line for line in result.stdout.splitlines() if line)
    except OSError:
        pass

    if not files:
        for current, dirs, names in os.walk(root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for name in names:
                files.append(Path(current) / name)

    # Some historical local snapshots are gitignored, but they are useful for
    # drift detection. Include them explicitly without turning on --no-ignore
    # for the whole workspace.
    for backup_dir in root.glob("backup-*"):
        scripts_dir = backup_dir / "scripts"
        if scripts_dir.is_dir():
            files.extend(path for path in scripts_dir.rglob("*") if path.is_file())

    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in files:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        deduped.append(resolved)
    return deduped


def exact_local_path(root: Path, remote_path: str) -> Path | None:
    prefix = "/mnt/projects/"
    if remote_path.startswith(prefix):
        return root / remote_path.removeprefix(prefix)
    return None


def classify_artifact(
    artifact: RemoteArtifact,
    root: Path,
    by_name: dict[str, list[Path]],
    local_hash_cache: dict[Path, str],
    redacted_reviews: dict[str, list[dict[str, str]]],
    redacted_templates: dict[str, list[dict[str, str]]] | None = None,
    accepted_local_deltas: dict[str, list[dict[str, str]]] | None = None,
) -> dict[str, object]:
    if artifact.remote_path.startswith(SERVER_RUNTIME_PREFIXES):
        return {
            "component": artifact.component,
            "remote_path": artifact.remote_path,
            "sha256": artifact.sha256,
            "status": "server_runtime_artifact",
            "local_matches": [],
            "notes": "Runtime binary/database/config metadata only; do not store full artifact in repo.",
        }

    if any(marker in artifact.remote_path for marker in SERVER_BACKUP_MARKERS):
        status_if_missing = "server_backup_only"
    else:
        status_if_missing = "missing_local_source"

    candidates: list[Path] = []
    exact = exact_local_path(root, artifact.remote_path)
    if exact is not None and exact.exists():
        candidates.append(exact)
    candidates.extend(path for path in by_name.get(artifact.name, []) if path not in candidates)

    matches: list[str] = []
    drifts: list[str] = []
    for candidate in candidates:
        if not candidate.is_file():
            continue
        digest = local_hash_cache.get(candidate)
        if digest is None:
            digest = sha256_file(candidate)
            local_hash_cache[candidate] = digest
        rel = str(candidate.relative_to(root))
        if digest == artifact.sha256:
            matches.append(rel)
        else:
            drifts.append(rel)

    if matches:
        exact_match = exact is not None and exact.exists() and str(exact.relative_to(root)) in matches
        return {
            "component": artifact.component,
            "remote_path": artifact.remote_path,
            "sha256": artifact.sha256,
            "status": "exact_match" if exact_match else "same_hash_elsewhere",
            "local_matches": matches,
            "local_drifts": drifts,
            "notes": "",
        }

    reviews = [
        review
        for review in redacted_reviews.get(artifact.sha256, [])
        if review["remote_path"] in {"", artifact.remote_path}
    ]
    if reviews and status_if_missing == "missing_local_source":
        return {
            "component": artifact.component,
            "remote_path": artifact.remote_path,
            "sha256": artifact.sha256,
            "status": "redacted_review_only",
            "local_matches": [review["local_path"] for review in reviews],
            "local_drifts": drifts,
            "metadata": [review["meta_path"] for review in reviews],
            "notes": "Redacted local review copy exists; raw source is not stored locally and this is not deployable source.",
        }

    redacted_templates = redacted_templates or {}
    templates = [
        template
        for template in redacted_templates.get(artifact.sha256, [])
        if template["remote_path"] in {"", artifact.remote_path}
    ]
    if templates and status_if_missing == "missing_local_source":
        return {
            "component": artifact.component,
            "remote_path": artifact.remote_path,
            "sha256": artifact.sha256,
            "status": "redacted_template_only",
            "local_matches": [template["local_path"] for template in templates],
            "local_drifts": drifts,
            "metadata": [template["meta_path"] for template in templates],
            "notes": "Sanitized local template exists; raw production values are not stored locally and this is not deployable source.",
        }

    accepted_local_deltas = accepted_local_deltas or {}
    accepted = [
        delta
        for delta in accepted_local_deltas.get(artifact.remote_path, [])
        if delta["remote_sha256"] == artifact.sha256 and delta["local_path"] in drifts
    ]
    if accepted:
        return {
            "component": artifact.component,
            "remote_path": artifact.remote_path,
            "sha256": artifact.sha256,
            "status": "accepted_local_delta",
            "local_matches": [delta["local_path"] for delta in accepted],
            "local_drifts": [],
            "notes": "; ".join(delta["reason"] for delta in accepted if delta["reason"])
            or "Local file intentionally differs from current NL source and is not deployable.",
        }

    if drifts:
        return {
            "component": artifact.component,
            "remote_path": artifact.remote_path,
            "sha256": artifact.sha256,
            "status": "local_name_drift",
            "local_matches": [],
            "local_drifts": drifts,
            "notes": "Same basename exists locally, but content hash differs.",
        }

    return {
        "component": artifact.component,
        "remote_path": artifact.remote_path,
        "sha256": artifact.sha256,
        "status": status_if_missing,
        "local_matches": [],
        "local_drifts": [],
        "notes": "No local file with the same basename found.",
    }


def load_artifacts(profile: Path) -> list[RemoteArtifact]:
    return [
        *parse_hash_file(profile / "mesh" / "script-hashes.txt", "mesh"),
        *parse_hash_file(profile / "ghost-access" / "script-hashes.txt", "ghost-access"),
        *parse_hash_file(profile / "ghost-vpn" / "file-hashes.txt", "ghost-vpn"),
        *parse_hash_file(profile / "xui" / "file-hashes.txt", "xui"),
    ]


def summarize(rows: list[dict[str, object]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for row in rows:
        counts[str(row["status"])] += 1
    return dict(sorted(counts.items()))


def render_markdown(profile: Path, rows: list[dict[str, object]]) -> str:
    counts = summarize(rows)
    missing_current = [
        row for row in rows
        if row["status"] in {"missing_local_source", "local_name_drift"} and ".bak-" not in str(row["remote_path"])
    ]
    server_only = [row for row in rows if row["status"] == "server_runtime_artifact"]
    backup_only = [row for row in rows if row["status"] == "server_backup_only"]
    redacted_only = [row for row in rows if row["status"] == "redacted_review_only"]
    redacted_templates = [row for row in rows if row["status"] == "redacted_template_only"]
    accepted_local_deltas = [row for row in rows if row["status"] == "accepted_local_delta"]

    lines: list[str] = [
        "# NL Profile Gap Analysis",
        "",
        f"profile: `{profile}`",
        "",
        "## Summary",
        "",
        "```json",
        json.dumps(counts, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Findings",
        "",
    ]

    if missing_current:
        lines.extend(
            [
                "### Missing Or Drifted Current Runtime Sources",
                "",
                "| Component | Remote path | Status | Local candidates |",
                "|---|---|---|---|",
            ]
        )
        for row in missing_current:
            local = ", ".join(row.get("local_drifts", []) or row.get("local_matches", []) or [])
            lines.append(
                f"| {row['component']} | `{row['remote_path']}` | `{row['status']}` | {local or '-'} |"
            )
        lines.append("")

    if server_only:
        lines.extend(
            [
                "### Server Runtime Artifacts",
                "",
                "These should stay as server runtime artifacts, not normal repo source files.",
                "",
                "| Component | Remote path |",
                "|---|---|",
            ]
        )
        for row in server_only:
            lines.append(f"| {row['component']} | `{row['remote_path']}` |")
        lines.append("")

    if redacted_only:
        lines.extend(
            [
                "### Redacted Review Only",
                "",
                "These have sanitized local review copies, but raw source is not stored locally and the redacted files are not deployable.",
                "",
                "| Component | Remote path | Redacted local copy |",
                "|---|---|---|",
            ]
        )
        for row in redacted_only:
            local = ", ".join(f"`{p}`" for p in row.get("local_matches", [])) or "-"
            lines.append(f"| {row['component']} | `{row['remote_path']}` | {local} |")
        lines.append("")

    if redacted_templates:
        lines.extend(
            [
                "### Redacted Templates",
                "",
                "These have sanitized local templates, but raw production values are not stored locally and the templates are not deployable.",
                "",
                "| Component | Remote path | Template local copy |",
                "|---|---|---|",
            ]
        )
        for row in redacted_templates:
            local = ", ".join(f"`{p}`" for p in row.get("local_matches", [])) or "-"
            lines.append(f"| {row['component']} | `{row['remote_path']}` | {local} |")
        lines.append("")

    if accepted_local_deltas:
        lines.extend(
            [
                "### Accepted Local Deltas",
                "",
                "These local files intentionally differ from current NL source and are not deployable without a separate review.",
                "",
                "| Component | Remote path | Local file | Reason |",
                "|---|---|---|---|",
            ]
        )
        for row in accepted_local_deltas:
            local = ", ".join(f"`{p}`" for p in row.get("local_matches", [])) or "-"
            reason = str(row.get("notes", "")).replace("|", "\\|") or "-"
            lines.append(f"| {row['component']} | `{row['remote_path']}` | {local} | {reason} |")
        lines.append("")

    if backup_only:
        lines.extend(
            [
                "### Server Backup Artifacts",
                "",
                "These are backup copies on NL. They are useful for forensic history but should not drive current repo reconciliation.",
                "",
                "| Component | Remote path |",
                "|---|---|",
            ]
        )
        for row in backup_only:
            lines.append(f"| {row['component']} | `{row['remote_path']}` |")
        lines.append("")

    lines.extend(
        [
            "## Full Artifact Table",
            "",
            "| Component | Remote path | Status | Local matches | Local drifts |",
            "|---|---|---|---|---|",
        ]
    )
    for row in rows:
        matches = ", ".join(f"`{p}`" for p in row.get("local_matches", [])) or "-"
        drifts = ", ".join(f"`{p}`" for p in row.get("local_drifts", [])) or "-"
        lines.append(
            f"| {row['component']} | `{row['remote_path']}` | `{row['status']}` | {matches} | {drifts} |"
        )

    lines.extend(
        [
            "",
            "## Recommended Next Work",
            "",
            "1. Create a repo-owned `nl-server-profile` source area for scripts that are current on NL but missing locally.",
            "2. Do not copy secrets or full databases; only bring source code/config templates with explicit redaction metadata.",
            "3. Treat `x-ui` binaries, `/etc/x-ui/x-ui.db`, and generated `/usr/local/x-ui/bin/config.json` as runtime artifacts.",
            "4. Replace backup-only entries with a short retention note instead of trying to reconcile them.",
            "5. Reconstruct `redacted_review_only` files into clean deployable source before considering them repo-owned.",
            "6. Before any future NL write, require: fresh read-only profile, x-ui db/config backup plan, rollback command, and explicit operator approval.",
            "",
            "No NL writes were performed by this analysis.",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--profile",
        default="/mnt/projects/nl-diagnostics/nl-server-profile/latest",
        help="Sanitized NL profile directory",
    )
    parser.add_argument("--root", default="/mnt/projects", help="Local workspace root")
    parser.add_argument("--json-out", help="Optional JSON output path")
    parser.add_argument("--markdown-out", help="Optional Markdown output path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    profile = Path(args.profile).resolve()
    if not profile.is_dir():
        raise SystemExit(f"profile not found: {profile}")

    local_files = list_local_files(root)
    by_name: dict[str, list[Path]] = defaultdict(list)
    for path in local_files:
        by_name[path.name].append(path)

    cache: dict[Path, str] = {}
    artifacts = load_artifacts(profile)
    redacted_reviews = load_redacted_reviews(root)
    redacted_templates = load_redacted_templates(root)
    accepted_local_deltas = load_accepted_local_deltas(root)
    rows = [
        classify_artifact(
            artifact,
            root,
            by_name,
            cache,
            redacted_reviews,
            redacted_templates,
            accepted_local_deltas,
        )
        for artifact in artifacts
    ]
    rows.sort(key=lambda row: (str(row["component"]), str(row["remote_path"])))

    payload = {
        "profile": str(profile),
        "root": str(root),
        "summary": summarize(rows),
        "artifacts": rows,
    }
    markdown = render_markdown(profile, rows)

    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(markdown, encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
