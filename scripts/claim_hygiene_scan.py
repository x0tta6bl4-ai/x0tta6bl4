#!/usr/bin/env python3
"""Scan current-facing repo surfaces for overbroad public claims.

The scanner is intentionally conservative. It reports high-risk phrases on
claim-bearing surfaces unless nearby text clearly frames the phrase as blocked,
historical, simulated, pending, or otherwise not a current verified claim.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]

TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".html",
    ".json",
    ".md",
    ".rst",
    ".txt",
    ".yaml",
    ".yml",
}

ZONE_PATHS = {
    "authoritative": (
        "AGENTS.md",
        "STATUS_REALITY.md",
        "docs/team/REPO_TRUTH_SURFACE.md",
        "docs/verification",
        "docs/research",
        ".claude/rules",
    ),
    "active_claim_surface": (
        "README.md",
        "index_maas.html",
        "x0tta6bl4.yaml",
        "docs/commercial",
        "docs/product",
        "docs/release",
        "business",
        "go-to-market",
        "web",
    ),
    "aspirational": (
        "plans",
        "deploy",
        "config",
        "charts",
        "chaos",
        "grafana",
    ),
    "legacy": (
        "archive",
        "docs/archive",
        "backups",
        "root_archive",
    ),
}

HIGH_RISK_PATTERNS = (
    ("production-ready", re.compile(r"\bproduction[- ]ready\b", re.IGNORECASE)),
    ("production-proven", re.compile(r"\bproduction[- ]proven\b", re.IGNORECASE)),
    ("fully-integrated", re.compile(r"\bfully integrated\b", re.IGNORECASE)),
    ("unblockable", re.compile(r"\bunblockable\b", re.IGNORECASE)),
    ("field-validated", re.compile(r"\bfield[- ]validated\b", re.IGNORECASE)),
    ("rektor-attested", re.compile(r"\brekor[- ](?:attested|backed)\b", re.IGNORECASE)),
    ("high-pps", re.compile(r"\b(?:5M|8\.8M|1M\+?)\s*PPS\b", re.IGNORECASE)),
    ("uptime-percent", re.compile(r"\b98\.5\s*%\s*uptime\b", re.IGNORECASE)),
    ("mttr", re.compile(r"\b1\.8s\s+MTTR\b", re.IGNORECASE)),
    ("gnn-accuracy", re.compile(r"\b94\s*%\s+GNN\b", re.IGNORECASE)),
    ("production-traffic", re.compile(r"\bproduction traffic\b", re.IGNORECASE)),
    ("full-mobile-core", re.compile(r"\bfull mobile[- ]core\b", re.IGNORECASE)),
    ("carrier-grade", re.compile(r"\bcarrier[- ]grade\b", re.IGNORECASE)),
    ("market-validated", re.compile(r"\bmarket[- ]validated\b", re.IGNORECASE)),
)

CAVEAT_RE = re.compile(
    "|".join(
        re.escape(term)
        for term in (
            "blocked",
            "boundary",
            "caveat",
            "claim restriction",
            "controlled pre-pilot",
            "current release authority",
            "do not claim",
            "do not promote",
            "do not publicly state",
            "evidence gap",
            "evidence-bound",
            "evidence-bounded",
            "hallucinated",
            "historical",
            "horizon-2",
            "horizon_2",
            "not a current",
            "not a claim",
            "not automatic current",
            "not claimed",
            "not_claimed",
            "not counted",
            "not current",
            "not evidence",
            "not measurements",
            "not proof",
            "not production",
            "not verified",
            "no-go",
            "pending",
            "purged",
            "required evidence",
            "requires",
            "scheduled",
            "simulated",
            "simulation",
            "superseded",
            "target",
            "until",
            "unless",
            "without",
            "before claiming",
            "does not confirm",
            "falling short",
            "path to",
            "to benchmark",
            "to reach",
            "unverified",
            "не использовать",
            "без ссылок",
            "галлюцинац",
            "для получения статуса",
            "неподтвержден",
            "отказались",
            "симуляц",
        )
    ),
    re.IGNORECASE,
)


@dataclass(frozen=True)
class Finding:
    zone: str
    path: str
    line: int
    kind: str
    text: str
    caveated: bool


def iter_zone_files(zone: str) -> Iterable[Path]:
    seen: set[Path] = set()
    for rel in ZONE_PATHS[zone]:
        path = ROOT / rel
        if not path.exists():
            continue
        if path.is_file():
            candidates = [path]
        else:
            candidates = [p for p in path.rglob("*") if p.is_file()]
        for candidate in candidates:
            if candidate in seen:
                continue
            seen.add(candidate)
            if candidate.suffix.lower() in TEXT_SUFFIXES:
                yield candidate


def file_has_global_caveat(lines: list[str]) -> bool:
    header = "\n".join(lines[:20])
    return bool(
        CAVEAT_RE.search(header)
        and re.search(
            r"STATUS_REALITY|truth[- ]surface|current gate|release gate|superseded|verified evidence states|v1\.1-hardening-status",
            header,
            re.IGNORECASE,
        )
    )


def is_caveated(lines: list[str], index: int) -> bool:
    if file_has_global_caveat(lines):
        return True
    start = max(0, index - 2)
    end = min(len(lines), index + 3)
    context = "\n".join(lines[start:end])
    return bool(CAVEAT_RE.search(context))


def scan_file(path: Path, zone: str) -> list[Finding]:
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        text = path.read_text(encoding="utf-8", errors="ignore")
    try:
        rel_path = str(path.relative_to(ROOT))
    except ValueError:
        rel_path = str(path)
    lines = text.splitlines()
    findings: list[Finding] = []
    for index, line in enumerate(lines):
        for kind, pattern in HIGH_RISK_PATTERNS:
            if pattern.search(line):
                findings.append(
                    Finding(
                        zone=zone,
                        path=rel_path,
                        line=index + 1,
                        kind=kind,
                        text=line.strip(),
                        caveated=is_caveated(lines, index),
                    )
                )
    return findings


def scan_zone(zone: str) -> list[Finding]:
    findings, _ = scan_zone_with_file_count(zone)
    return findings


def scan_zone_with_file_count(zone: str) -> tuple[list[Finding], int]:
    findings: list[Finding] = []
    files_scanned = 0
    for path in iter_zone_files(zone):
        files_scanned += 1
        findings.extend(scan_file(path, zone))
    return findings, files_scanned


def print_text(findings: list[Finding], *, all_hits: bool) -> None:
    visible = findings if all_hits else [item for item in findings if not item.caveated]
    if not visible:
        print("claim-hygiene: no non-caveated high-risk hits")
        if findings:
            print(f"claim-hygiene: caveated hits suppressed={len(findings)}")
        return
    for item in visible:
        marker = "caveated" if item.caveated else "ACTIVE"
        print(f"{item.path}:{item.line}: {marker} {item.kind}: {item.text}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--zone",
        choices=sorted(ZONE_PATHS),
        default="active_claim_surface",
        help="truth-surface zone to scan",
    )
    parser.add_argument(
        "--fail-on-active",
        action="store_true",
        help="exit non-zero when non-caveated high-risk hits are present",
    )
    parser.add_argument(
        "--all-hits",
        action="store_true",
        help="show caveated hits as well as active hits",
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable findings")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    findings, files_scanned = scan_zone_with_file_count(args.zone)
    active = [item for item in findings if not item.caveated]

    if args.json:
        payload = {
            "zone": args.zone,
            "files_scanned": files_scanned,
            "findings": [asdict(item) for item in findings if args.all_hits or not item.caveated],
            "finding_count": len(findings),
            "active_count": len(active),
        }
        print(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True))
    else:
        print_text(findings, all_hits=args.all_hits)
        print(
            "claim-hygiene summary: "
            f"zone={args.zone} findings={len(findings)} active={len(active)}"
        )

    if args.fail_on_active and active:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
