#!/usr/bin/env python3
"""Build a public-source shortlist for future secondary VPN exit providers.

The shortlist is planning evidence only. It names provider/region options from
public documentation, but it does not create endpoints, store secrets, contact
NL/SPB, or enable failover.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


ROOT = Path("/mnt/projects")
DIAGNOSTICS_DIR = ROOT / "nl-diagnostics"
DEFAULT_JSON_OUT = DIAGNOSTICS_DIR / "secondary-exit-provider-shortlist-2026-05-28.json"
DEFAULT_MARKDOWN_OUT = DIAGNOSTICS_DIR / "secondary-exit-provider-shortlist-2026-05-28.md"


SOURCE_CHECK_DATE = "2026-05-28"

BLOCKING_SOURCES = [
    {
        "id": "cloudflare-russia-throttling-2025",
        "title": "Cloudflare: Russian ISPs throttled Cloudflare-protected services",
        "url": "https://blog.cloudflare.com/russian-internet-users-are-unable-to-access-the-open-internet/",
        "checked_at": SOURCE_CHECK_DATE,
        "planning_signal": "App/CDN failures can look like VPN failures even when the VPN server is healthy.",
    },
    {
        "id": "cloudflare-q1-2026-disruptions",
        "title": "Cloudflare: Q1 2026 Internet disruption review",
        "url": "https://blog.cloudflare.com/q1-2026-internet-disruption-summary/",
        "checked_at": SOURCE_CHECK_DATE,
        "planning_signal": "Government-directed shutdowns and non-server outages remain active operational risks.",
    },
    {
        "id": "access-now-keepiton-2025",
        "title": "Access Now/#KeepItOn: 2025 shutdown report",
        "url": "https://www.accessnow.org/tag/keepiton/",
        "checked_at": SOURCE_CHECK_DATE,
        "planning_signal": "The global pattern favors multi-path diagnostics rather than one-server assumptions.",
    },
    {
        "id": "freedom-house-tunnel-vision-2025",
        "title": "Freedom House: Tunnel Vision report",
        "url": (
            "https://freedomhouse.org/report/special-report/2025/"
            "tunnel-vision-anti-censorship-tools-end-end-encryption-and-fight-free"
        ),
        "checked_at": SOURCE_CHECK_DATE,
        "planning_signal": "VPN and circumvention tools are blocked in multiple countries, so provider diversity matters.",
    },
]

PROVIDER_SOURCES = [
    {
        "id": "hetzner-cloud-locations",
        "provider": "Hetzner",
        "url": "https://docs.hetzner.com/cloud/general/locations/",
        "checked_at": SOURCE_CHECK_DATE,
    },
    {
        "id": "upcloud-locations",
        "provider": "UpCloud",
        "url": "https://upcloud.com/docs/getting-started/locations/",
        "checked_at": SOURCE_CHECK_DATE,
    },
    {
        "id": "ovhcloud-public-cloud-regions",
        "provider": "OVHcloud",
        "url": "https://www.ovhcloud.com/en/public-cloud/regions-availability/",
        "checked_at": SOURCE_CHECK_DATE,
    },
    {
        "id": "digitalocean-regional-availability",
        "provider": "DigitalOcean",
        "url": "https://docs.digitalocean.com/platform/regional-availability/",
        "checked_at": SOURCE_CHECK_DATE,
    },
    {
        "id": "scaleway-product-availability",
        "provider": "Scaleway",
        "url": "https://www.scaleway.com/en/docs/account/reference-content/products-availability/",
        "checked_at": SOURCE_CHECK_DATE,
    },
]

SHORTLIST = [
    {
        "label": "upcloud-fi-hel",
        "provider": "UpCloud",
        "country": "Finland",
        "region": "Helsinki",
        "region_slugs": ["fi-hel1", "fi-hel2"],
        "priority": 1,
        "source_id": "upcloud-locations",
        "expected_tcp_ports": [443],
        "status": "shortlist_ready_no_endpoint",
        "why": [
            "not NL and not SPB/Russia",
            "separate provider/account can be used",
            "near enough to European users for emergency fallback",
        ],
        "risk_notes": [
            "verify current stock in provider console before provisioning",
            "do not choose UpCloud Amsterdam for this fallback",
            "do not store profile URI, UUID, private key, token, or subscription link in repo",
        ],
    },
    {
        "label": "ovhcloud-pl-waw",
        "provider": "OVHcloud",
        "country": "Poland",
        "region": "Warsaw",
        "region_slugs": ["WAW"],
        "priority": 2,
        "source_id": "ovhcloud-public-cloud-regions",
        "expected_tcp_ports": [443],
        "status": "shortlist_ready_no_endpoint",
        "why": [
            "not NL and not SPB/Russia",
            "large European provider with a Poland Public Cloud region",
            "good candidate for provider and country diversity",
        ],
        "risk_notes": [
            "verify instance flavor availability at order time",
            "keep the future endpoint public metadata only until probe config generation",
            "do not reuse the NL account or any existing VPN secret material",
        ],
    },
    {
        "label": "hetzner-de-or-fi",
        "provider": "Hetzner",
        "country": "Germany or Finland",
        "region": "Nuremberg/Falkenstein/Helsinki",
        "region_slugs": ["nbg1", "fsn1", "hel1"],
        "priority": 3,
        "source_id": "hetzner-cloud-locations",
        "expected_tcp_ports": [443],
        "status": "shortlist_ready_no_endpoint",
        "why": [
            "not NL and not SPB/Russia",
            "simple VPS footprint in Germany/Finland",
            "useful as a low-cost emergency profile if provider independence is confirmed",
        ],
        "risk_notes": [
            "verify this is not the current NL provider before choosing it",
            "verify current stock in provider console before provisioning",
            "prefer a fresh project/account and avoid reusing NL automation credentials",
        ],
    },
    {
        "label": "digitalocean-de-fra-or-uk-lon",
        "provider": "DigitalOcean",
        "country": "Germany or United Kingdom",
        "region": "Frankfurt or London",
        "region_slugs": ["fra1", "lon1"],
        "priority": 4,
        "source_id": "digitalocean-regional-availability",
        "expected_tcp_ports": [443],
        "status": "shortlist_ready_no_endpoint",
        "why": [
            "not NL and not SPB/Russia",
            "mainstream cloud with documented non-NL European regions",
            "useful if we want a provider very different from small EU VPS hosts",
        ],
        "risk_notes": [
            "avoid Amsterdam even though it is available",
            "larger cloud IP ranges may have stronger VPN/proxy reputation signals",
            "verify outbound policy and public IPv4 availability before provisioning",
        ],
    },
    {
        "label": "scaleway-pl-waw-or-fr-par",
        "provider": "Scaleway",
        "country": "Poland or France",
        "region": "Warsaw or Paris",
        "region_slugs": ["WAW", "PAR"],
        "priority": 5,
        "source_id": "scaleway-product-availability",
        "expected_tcp_ports": [443],
        "status": "shortlist_ready_no_endpoint",
        "why": [
            "not NL and not SPB/Russia",
            "European provider with Warsaw and Paris regions",
            "useful as a second EU-sovereign option after OVHcloud/UpCloud",
        ],
        "risk_notes": [
            "avoid Amsterdam for this fallback",
            "check exact instance product availability in the chosen zone",
            "keep all VPN secrets outside repository and reports",
        ],
    },
]


def build_payload() -> dict[str, Any]:
    source_ids = {source["id"] for source in PROVIDER_SOURCES}
    options = sorted(SHORTLIST, key=lambda row: int(row["priority"]))
    invalid_source_refs = [row["label"] for row in options if row["source_id"] not in source_ids]
    endpoint_count = 0
    safe = not invalid_source_refs and all(row["status"] == "shortlist_ready_no_endpoint" for row in options)
    status = "shortlist_ready_no_endpoint" if safe and options else "shortlist_needs_attention"

    return {
        "schema_version": 1,
        "source": "nl-diagnostics/build_secondary_exit_provider_shortlist.py",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_check_date": SOURCE_CHECK_DATE,
        "status": status,
        "ok": safe,
        "summary": {
            "shortlist_count": len(options),
            "source_count": len(PROVIDER_SOURCES) + len(BLOCKING_SOURCES),
            "endpoint_count": endpoint_count,
            "candidate_configured": False,
            "candidate_file_action": (
                "after provisioning one shortlisted server, put only public host/IP metadata in "
                "nl-diagnostics/secondary-exit-candidates.example.json"
            ),
            "invalid_source_refs": invalid_source_refs,
            "nl_write_allowed": False,
            "spb_fallback_allowed": False,
            "automatic_failover_allowed": False,
        },
        "selection_rules": [
            "Do not use NL, Amsterdam, SPB, Russia, or the current NL provider/account as the secondary exit.",
            "Use a fresh provider project/account when practical.",
            "Expose only a public TCP health target, normally TCP 443, before any client profile test.",
            "Do not store raw VPN URI, UUID, private key, bot token, subscription link, or NL/SPB endpoint in repo.",
            "Keep failover manual; this shortlist does not permit a switch.",
        ],
        "blocking_context": BLOCKING_SOURCES,
        "provider_sources": PROVIDER_SOURCES,
        "shortlist": options,
        "next_steps": [
            "Pick one option from priority 1-3 unless provider independence check fails.",
            "Provision the smallest suitable server with public TCP 443 reachability.",
            "Add only public metadata to secondary-exit-candidates.example.json.",
            "Run the scorer and refresh; do not generate profile secrets in the repository.",
        ],
        "mutation_allowed": False,
        "nl_mutation_allowed": False,
        "spb_fallback_allowed": False,
        "automatic_failover_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Secondary Exit Provider Shortlist",
        "",
        f"generated_at: `{payload['generated_at']}`",
        f"source_check_date: `{payload['source_check_date']}`",
        f"status: `{payload['status']}`",
        f"ok: `{str(payload['ok']).lower()}`",
        "",
        "## Summary",
        "",
        "```text",
        f"shortlist_count={summary.get('shortlist_count')}",
        f"source_count={summary.get('source_count')}",
        f"endpoint_count={summary.get('endpoint_count')}",
        f"candidate_configured={str(summary.get('candidate_configured')).lower()}",
        f"candidate_file_action={summary.get('candidate_file_action')}",
        f"invalid_source_refs={','.join(summary.get('invalid_source_refs') or []) or 'none'}",
        "nl_write_allowed=false",
        "spb_fallback_allowed=false",
        "automatic_failover_allowed=false",
        "```",
        "",
        "## Selection Rules",
        "",
    ]
    lines.extend(f"- {value}" for value in payload["selection_rules"])
    lines.extend(
        [
            "",
            "## Blocking Context",
            "",
            "| Source | Planning Signal | URL |",
            "|---|---|---|",
        ]
    )
    for row in payload["blocking_context"]:
        lines.append(f"| `{row['id']}` | {row['planning_signal']} | {row['url']} |")

    lines.extend(
        [
            "",
            "## Provider Options",
            "",
            "| Priority | Label | Provider | Country | Region | Slugs | Ports | Status |",
            "|---:|---|---|---|---|---|---|---|",
        ]
    )
    source_by_id = {row["id"]: row for row in payload["provider_sources"]}
    for row in payload["shortlist"]:
        source = source_by_id.get(row["source_id"], {})
        lines.append(
            "| "
            f"{row['priority']} | "
            f"`{row['label']}` | "
            f"{row['provider']} | "
            f"{row['country']} | "
            f"{row['region']} | "
            f"`{','.join(row['region_slugs'])}` | "
            f"`{','.join(str(port) for port in row['expected_tcp_ports'])}` | "
            f"`{row['status']}` |"
        )
        lines.extend(
            [
                "",
                f"Source: {source.get('url', 'missing')}",
                "",
                "Why:",
            ]
        )
        lines.extend(f"- {value}" for value in row["why"])
        lines.append("")
        lines.append("Risk notes:")
        lines.extend(f"- {value}" for value in row["risk_notes"])
        lines.append("")

    lines.extend(["## Next Steps", ""])
    lines.extend(f"- {value}" for value in payload["next_steps"])
    lines.extend(["", "No NL or SPB writes were performed by this provider shortlist."])
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build secondary exit provider shortlist")
    parser.add_argument("--json-out", default=str(DEFAULT_JSON_OUT))
    parser.add_argument("--markdown-out", default=str(DEFAULT_MARKDOWN_OUT))
    args = parser.parse_args()

    payload = build_payload()
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if args.markdown_out:
        Path(args.markdown_out).write_text(render_markdown(payload), encoding="utf-8")
    if not args.json_out and not args.markdown_out:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
