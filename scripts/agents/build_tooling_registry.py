#!/usr/bin/env python3
"""Build a unified tooling registry for agents, skills, MCP, and session tools."""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / ".agent-coord" / "tooling_registry.json"
QUEUE_PATH = ROOT / "plans" / "ROADMAP_AGENT_QUEUE.json"
MICRONICHE_REGISTRY_PATH = ROOT / "go-to-market" / "microniche_agent_registry.json"
MCP_PATH = ROOT / ".mcp.json"
OPERATOR_MCP_PATH = ROOT / "mcp-server" / "src" / "operator_tools.py"
SKILLS_DIR = Path("/home/x0ttta6bl4/.codex/skills/.system")


SESSION_TOOL_CATALOG = {
    "developer_tools": [
        {"name": "exec_command", "purpose": "run shell commands in the shared workspace", "status": "available"},
        {"name": "apply_patch", "purpose": "edit files with structured patch hunks", "status": "available"},
        {"name": "list_mcp_resources", "purpose": "list MCP-provided structured resources", "status": "available"},
        {"name": "list_mcp_resource_templates", "purpose": "list parameterized MCP resources", "status": "available"},
        {"name": "read_mcp_resource", "purpose": "read a concrete MCP resource", "status": "available"},
        {"name": "update_plan", "purpose": "maintain a visible task plan", "status": "available"},
        {"name": "view_image", "purpose": "inspect a local image file", "status": "available"},
        {"name": "spawn_agent", "purpose": "delegate bounded sidecar work to a subagent", "status": "available"},
        {"name": "send_input", "purpose": "send follow-up input to an existing subagent", "status": "available"},
        {"name": "wait_agent", "purpose": "wait for a subagent result", "status": "available"},
        {"name": "resume_agent", "purpose": "re-open a previous subagent", "status": "available"},
        {"name": "close_agent", "purpose": "close a finished subagent", "status": "available"},
        {"name": "request_user_input", "purpose": "UI-backed short question prompt", "status": "unavailable_in_default_mode"},
    ],
    "system_tools": [
        {"name": "web.search_query", "purpose": "search the public web", "status": "available"},
        {"name": "web.open", "purpose": "open a search result or URL", "status": "available"},
        {"name": "web.click", "purpose": "follow a discovered link", "status": "available"},
        {"name": "web.find", "purpose": "locate text in opened content", "status": "available"},
        {"name": "web.finance", "purpose": "fetch market data", "status": "available"},
        {"name": "web.weather", "purpose": "fetch weather data", "status": "available"},
        {"name": "web.sports", "purpose": "fetch sports schedules/standings", "status": "available"},
        {"name": "web.time", "purpose": "fetch time by UTC offset", "status": "available"},
    ],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def list_skills() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not SKILLS_DIR.exists():
        return items
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.exists():
            continue
        description = ""
        for line in skill_md.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("description:"):
                description = line.split(":", 1)[1].strip().strip('"')
                break
        items.append(
            {
                "name": skill_dir.name,
                "path": str(skill_md),
                "description": description,
                "status": "installed",
            }
        )
    return items


def list_coord_agents() -> list[dict[str, Any]]:
    queue = load_json(QUEUE_PATH)
    agents = queue.get("agents", {})
    rows: list[dict[str, Any]] = []
    for name, payload in sorted(agents.items()):
        rows.append(
            {
                "name": name,
                "kind": "roadmap_agent",
                "lane": payload.get("lane", ""),
                "preferred_mode": payload.get("preferred_mode", ""),
                "allowed_modes": payload.get("allowed_modes", []),
            }
        )
    microniche = load_json(MICRONICHE_REGISTRY_PATH)
    for payload in sorted(microniche.get("agents", []), key=lambda row: row.get("agent_name", "")):
        name = payload.get("agent_name", "")
        if not name:
            continue
        rows.append(
            {
                "name": name,
                "kind": "microniche_agent",
                "lane": payload.get("lane", ""),
                "preferred_mode": "verification",
                "allowed_modes": ["verification"],
                "status": payload.get("status", ""),
                "priority": payload.get("priority", ""),
                "offer_id": payload.get("offer_id"),
                "offer_name": payload.get("offer_name", ""),
            }
        )
    return rows


def mcp_snapshot() -> dict[str, Any]:
    payload = load_json(MCP_PATH)
    servers = payload.get("mcpServers", {})
    entries = []
    for name, cfg in sorted(servers.items()):
        entries.append(
            {
                "name": name,
                "command": cfg.get("command", ""),
                "args": cfg.get("args", []),
                "cwd": cfg.get("cwd", ""),
                "env_keys": sorted((cfg.get("env") or {}).keys()),
                "configured": True,
            }
        )
    declared = inspect_operator_mcp()
    return {
        "config_path": str(MCP_PATH),
        "configured_servers": entries,
        "declared_resources": declared.get("resources", []),
        "declared_resource_templates": declared.get("resource_templates", []),
        "declared_tools": declared.get("tools", []),
        "declared_inspection_error": declared.get("error"),
        "runtime_resources_visible_in_this_session": [],
        "runtime_templates_visible_in_this_session": [],
        "note": "MCP server config and declared capabilities can exist even when the current host session has not mounted live MCP resources/templates.",
    }


def inspect_operator_mcp() -> dict[str, Any]:
    if not OPERATOR_MCP_PATH.exists():
        return {}
    try:
        spec = importlib.util.spec_from_file_location("operator_tools", str(OPERATOR_MCP_PATH))
        if spec is None or spec.loader is None:
            return {"error": "could_not_load_operator_mcp_spec"}
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        resources = asyncio.run(module.list_resources()) if hasattr(module, "list_resources") else []
        templates = (
            asyncio.run(module.list_resource_templates()) if hasattr(module, "list_resource_templates") else []
        )
        return {
            "resources": [str(resource.uri).rstrip("/") for resource in resources],
            "resource_templates": [template.uriTemplate for template in templates],
            "tools": sorted(getattr(module, "TOOL_HANDLERS", {}).keys()),
        }
    except Exception as exc:
        return {"error": str(exc)}


def build_registry(active_subagents: list[str]) -> dict[str, Any]:
    return {
        "_updated": utc_now(),
        "description": "Unified registry of agent lanes, active subagents, installed skills, MCP configuration, and available session tools.",
        "sources": {
            "roadmap_queue": str(QUEUE_PATH),
            "mcp_config": str(MCP_PATH),
            "skills_dir": str(SKILLS_DIR),
            "commercial_offer_registry": str(ROOT / "go-to-market" / "offer_verification_registry.json"),
            "commercial_offer_registry_human": str(ROOT / "UNIFIED_MICRONICHES_2026.md"),
            "offer_public_sync_registry": str(ROOT / "go-to-market" / "offer_public_sync_registry.json"),
            "offer_public_publish_pack": str(ROOT / "go-to-market" / "offer_public_publish_pack.json"),
            "offer_public_stage_plan": str(ROOT / "go-to-market" / "offer_public_stage_plan.json"),
            "microniche_agent_registry": str(ROOT / "go-to-market" / "microniche_agent_registry.json"),
            "green_offer_launch_registry": str(ROOT / "go-to-market" / "green_offer_launch_registry.json"),
            "upwork_green_batch_pack": str(ROOT / "go-to-market" / "upwork" / "green_upwork_batch_pack.json"),
            "upwork_submission_worksheet": str(ROOT / "go-to-market" / "upwork" / "green_upwork_submission_worksheet.json"),
            "upwork_response_variants": str(ROOT / "go-to-market" / "upwork" / "green_upwork_response_variants.json"),
            "upwork_response_cards": str(ROOT / "go-to-market" / "upwork" / "green_upwork_response_cards.json"),
            "upwork_job_intake_rules": str(ROOT / "go-to-market" / "upwork" / "green_upwork_job_intake_rules.json"),
        },
        "coordination_agents": list_coord_agents(),
        "active_subagents": [
            {"name": name, "kind": "session_subagent", "status": "active"} for name in active_subagents
        ],
        "skills": list_skills(),
        "mcp": mcp_snapshot(),
        "tool_catalog": SESSION_TOOL_CATALOG,
        "front_door_commands": [
            "bash scripts/agent-coord.sh status",
            "bash scripts/agent-coord.sh session_start <agent> \"summary\"",
            "bash scripts/agent-coord.sh next_task <agent>",
            "bash scripts/agent-coord.sh inbox <agent>",
            "bash scripts/agent-coord.sh send <from> <to> \"subject\" \"body\"",
            "bash scripts/agent-coord.sh claim_hygiene_scan --zone active_claim_surface --fail-on-active",
            "python3 scripts/show_microniche_agent_registry.py",
            "python3 scripts/show_offer_verification_registry.py --status green",
            "python3 scripts/show_offer_public_sync_registry.py --priority P0",
            "python3 scripts/show_offer_public_publish_pack.py --wave wave-1-p0-primary",
            "python3 scripts/export_offer_public_publish_wave.py --export-all",
            "python3 scripts/show_offer_public_stage_plan.py --wave wave-1-p0-primary --commands both",
            "bash go-to-market/publish_waves/wave-1-p0-primary.stage.sh status",
            "bash scripts/run_offer_verification_operator.sh status --status green",
            "python3 scripts/show_green_offer_launch_readiness.py",
            "bash scripts/run_green_offer_launch_operator.sh status",
            "python3 scripts/show_upwork_green_batch_pack.py",
            "bash scripts/run_upwork_green_batch_operator.sh status",
            "python3 scripts/show_upwork_submission_worksheet.py",
            "bash scripts/run_upwork_submission_operator.sh status",
            "python3 scripts/show_upwork_response_variants.py",
            "bash scripts/run_upwork_response_variants_operator.sh status",
            "python3 scripts/show_upwork_response_cards.py",
            "bash scripts/run_upwork_response_cards_operator.sh status",
            "python3 scripts/show_upwork_job_intake_route.py --job-file /tmp/job.txt",
            "bash scripts/run_upwork_job_intake_operator.sh status --job-file /tmp/job.txt",
            "bash scripts/agent-coord.sh integrity show --limit 10",
            "bash scripts/agent-coord.sh strategy_agents --limit 5",
            "bash scripts/agent-coord.sh strategy_shapes --limit 5",
            "bash scripts/agent-coord.sh strategy_recent --kind success --limit 5",
            "bash scripts/agent-coord.sh strategy_recent --kind failure --limit 5",
            "bash scripts/agent-coord.sh strategy_failure_signatures --limit 5 --all-agents",
            "bash scripts/agent-coord.sh memory_recall --query \"<task summary>\" --limit 5",
            "bash scripts/agent-coord.sh tool_audit_template --source-of-truth \"<sources>\" [memory/skill/subagent flags]",
            "bash scripts/agent-coord.sh session_end_template --source-of-truth \"<sources>\" [memory/skill/subagent flags] [verification/result flags] --output-file /tmp/handoff.json",
            "bash scripts/agent-coord.sh session_end_submit <agent> --source-of-truth \"<sources>\" [memory/skill/subagent flags] [verification/result flags]",
        ],
        "selection_order": [
            "structured local truth / MCP",
            "memory recall across integrity + strategy layers",
            "claim hygiene scan for commercial / README / landing / status tasks",
            "commercial offer registry for sales / outreach / Upwork launch tasks",
            "offer public-sync registry for deciding what still needs to be published on the public branch",
            "offer public-publish pack for exact P0/P1 file waves before commit/push",
            "offer public wave-file export for direct path manifests per publish wave",
            "offer public stage-plan for safe rehearsal and batched git-add commands per wave",
            "green-offer launch readiness for asset-complete outbound tasks",
            "Upwork green batch pack for first proposal batch execution",
            "Upwork submission worksheet for final pre-send fit/questions/red-flags check",
            "Upwork response variants for choosing the right opening/body emphasis per job type",
            "Upwork response cards for final copy-paste proposal text",
            "Upwork job-intake routing from raw post text to proposal/variant/card",
            "matching skill",
            "subagent / delegated sidecar",
            "web",
            "shell/manual path",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build unified tooling registry")
    parser.add_argument("--active-subagent", action="append", default=[], help="Active subagent name")
    parser.add_argument("--json", action="store_true", help="Print JSON to stdout as well")
    args = parser.parse_args()

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = build_registry(args.active_subagent)
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, ensure_ascii=True))
    else:
        print(str(OUT_PATH))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
