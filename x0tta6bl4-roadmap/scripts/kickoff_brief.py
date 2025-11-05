#!/usr/bin/env python3
"""Generate Kick-Off briefing summary for x0tta6bl4 Phase 1.

Usage:
  python3 scripts/kickoff_brief.py --format markdown --all
  python3 scripts/kickoff_brief.py --format text --sections team infra docs

Sections available:
  team, infra, docs, goals, schedule, next-steps
"""
from __future__ import annotations
import argparse, json, datetime, pathlib, sys

DEFAULT_SECTIONS = ["team","infra","docs","goals","schedule","next-steps"]

def section_team():
    return {
        "title": "Team",
        "content": [
            "9 FTE: 4 Mesh, 2 CJDNS, 1 Testing, 1 DevOps, 1 Security",
            "Slack channels active (#mesh-phase1, #standups, #escalation)"
        ]
    }

def section_infra():
    return {
        "title": "Infrastructure",
        "content": [
            "Kubernetes namespace: mtls-demo (pods initializing)",
            "Health scripts ready (health-check.sh / health_check.py)",
            "Terraform plan template ready (provision 50+ nodes)",
            "Monitoring stack spec prepared (Prometheus + Grafana)"
        ]
    }

def section_docs():
    return {
        "title": "Documentation",
        "content": [
            "22 production-ready documents",
            "Decision log updated (10 decisions)",
            "Dashboard artifacts prepared (index.html, metrics.json)"
        ]
    }

def section_goals():
    return {
        "title": "Phase 1 Goals (Weeks 1–2 Focus)",
        "content": [
            "Latency < 50ms (LAN baseline)",
            "Uptime target ≥ 95%",
            "MTTR ≤ 7 seconds",
            "50+ nodes staged rollout: 10 → 25 → 50"
        ]
    }

def section_schedule():
    return {
        "title": "Schedule Milestones",
        "content": [
            "Nov 4: Kick-Off Meeting (30m)",
            "Nov 11: Phase 1 Execution Start",
            "Weekly Standups: Mondays 14:00 UTC",
            "Jan 31: Phase 1 Completion Window"
        ]
    }

def section_next_steps():
    return {
        "title": "Immediate Next Steps",
        "content": [
            "Finalize pod readiness (ensure Running state)",
            "Enable GitHub Pages for dashboard",
            "Publish launch social posts (Twitter, Discord)",
            "Start baseline metrics collection"
        ]
    }

SECTION_BUILDERS = {
    "team": section_team,
    "infra": section_infra,
    "docs": section_docs,
    "goals": section_goals,
    "schedule": section_schedule,
    "next-steps": section_next_steps,
}

def build(sections):
    data = []
    for s in sections:
        builder = SECTION_BUILDERS.get(s)
        if not builder:
            print(f"Unknown section: {s}", file=sys.stderr)
            continue
        data.append(builder())
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "sections": data
    }

def render_markdown(payload):
    lines = [f"# x0tta6bl4 Phase 1 Kick-Off Brief", f"Generated: {payload['generated_at']}"]
    for sec in payload['sections']:
        lines.append(f"\n## {sec['title']}")
        for item in sec['content']:
            lines.append(f"- {item}")
    return "\n".join(lines) + "\n"

def render_text(payload):
    lines = ["x0tta6bl4 Phase 1 Kick-Off Brief", f"Generated: {payload['generated_at']}"]
    for sec in payload['sections']:
        lines.append(f"\n{sec['title'].upper()}")
        for item in sec['content']:
            lines.append(f" * {item}")
    return "\n".join(lines) + "\n"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--format', choices=['markdown','json','text'], default='markdown')
    ap.add_argument('--sections', nargs='*', default=None)
    ap.add_argument('--all', action='store_true')
    ap.add_argument('--outfile', default=None)
    args = ap.parse_args()
    if args.all or args.sections is None:
        sections = DEFAULT_SECTIONS
    else:
        sections = args.sections
    payload = build(sections)
    if args.format == 'json':
        output = json.dumps(payload, indent=2)
    elif args.format == 'markdown':
        output = render_markdown(payload)
    else:
        output = render_text(payload)
    if args.outfile:
        pathlib.Path(args.outfile).write_text(output)
        print(f"Written {args.outfile}")
    else:
        print(output)

if __name__ == '__main__':
    main()
