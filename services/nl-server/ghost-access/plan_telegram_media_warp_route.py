#!/usr/bin/env python3
from __future__ import annotations

import argparse
import copy
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any


PLAN_ID = "nl-telegram-media-warp-route-plan-2026-06-02"
DEFAULT_CONFIG_SUMMARY = Path(
    "nl-diagnostics/nl-server-profile/20260527T173222Z/xui/config-summary.json"
)
DEFAULT_RUNTIME_SUMMARY = Path(
    "nl-diagnostics/nl-server-profile/20260527T173222Z/mesh/runtime-state-summary.json"
)
DEFAULT_JSON_OUT = Path("nl-diagnostics/nl-telegram-media-warp-route-plan-2026-06-02.json")
DEFAULT_MARKDOWN_OUT = Path("nl-diagnostics/nl-telegram-media-warp-route-plan-2026-06-02.md")
XRAY_CONFIG_PATH = "/usr/local/x-ui/bin/config.json"
WARP_OUTBOUND_TAG = "warp"
DIRECT_OUTBOUND_TAG = "direct"

TELEGRAM_MEDIA_IPV4_CIDRS = [
    "91.108.4.0/22",
    "91.108.8.0/22",
    "91.108.12.0/22",
    "91.108.16.0/22",
    "91.108.20.0/22",
    "91.108.56.0/22",
    "149.154.160.0/20",
]


class TelegramMediaWarpPlanError(ValueError):
    pass


def utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_json_allowing_command_header(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise TelegramMediaWarpPlanError(f"missing input: {path}") from exc
    payload_text = "\n".join(
        line for line in text.splitlines() if not line.lstrip().startswith("#")
    ).strip()
    if not payload_text:
        raise TelegramMediaWarpPlanError(f"input is empty after comment stripping: {path}")
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise TelegramMediaWarpPlanError(f"input is not valid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise TelegramMediaWarpPlanError(f"input must be a JSON object: {path}")
    return payload


def telegram_media_warp_rule() -> dict[str, Any]:
    return {
        "type": "field",
        "ip": list(TELEGRAM_MEDIA_IPV4_CIDRS),
        "outboundTag": WARP_OUTBOUND_TAG,
    }


def rule_covers_telegram_media(rule: dict[str, Any]) -> bool:
    return (
        rule.get("outboundTag") == WARP_OUTBOUND_TAG
        and set(rule.get("ip") or []) >= set(TELEGRAM_MEDIA_IPV4_CIDRS)
    )


def find_direct_catchall_index(rules: list[Any]) -> int | None:
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict):
            continue
        if rule.get("outboundTag") != DIRECT_OUTBOUND_TAG:
            continue
        networks = set(rule.get("network") or [])
        if {"tcp", "udp"}.issubset(networks):
            return index
    return None


def apply_telegram_media_warp_rule(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    next_config = copy.deepcopy(config)
    routing = next_config.setdefault("routing", {})
    if not isinstance(routing, dict):
        raise TelegramMediaWarpPlanError("routing must be an object")
    rules = routing.setdefault("rules", [])
    if not isinstance(rules, list):
        raise TelegramMediaWarpPlanError("routing.rules must be a list")

    for index, rule in enumerate(rules):
        if isinstance(rule, dict) and rule_covers_telegram_media(rule):
            return next_config, {
                "changed": False,
                "reason": "telegram_media_warp_rule_already_present",
                "rule_index": index,
            }

    insert_at = find_direct_catchall_index(rules)
    if insert_at is None:
        insert_at = len(rules)
        insert_reason = "append_no_direct_catchall_found"
    else:
        insert_reason = "insert_before_direct_catchall"
    rules.insert(insert_at, telegram_media_warp_rule())
    routing.setdefault("domainStrategy", "IPIfNonMatch")
    routing.setdefault("domainMatcher", "hybrid")
    return next_config, {
        "changed": True,
        "reason": insert_reason,
        "rule_index": insert_at,
    }


def outbounds_from_summary(summary: dict[str, Any]) -> list[str]:
    tags = summary.get("outbound_tags") or []
    return [str(item) for item in tags] if isinstance(tags, list) else []


def runtime_hot_path(runtime_summary: dict[str, Any]) -> dict[str, Any]:
    hot = runtime_summary.get("hot_path_summary")
    if isinstance(hot, dict):
        return hot
    probes = runtime_summary.get("probes")
    if isinstance(probes, dict):
        transport = probes.get("transport_summary")
        if isinstance(transport, dict):
            return {
                "telegram_media_status": transport.get("telegram_media_status"),
                "warp_status": "healthy" if probes.get("warp_ok") else "unknown",
            }
    return {}


def build_plan(
    *,
    config_summary: dict[str, Any],
    runtime_summary: dict[str, Any],
    config_patch: dict[str, Any] | None = None,
    generated_at: str | None = None,
) -> dict[str, Any]:
    outbound_tags = outbounds_from_summary(config_summary)
    route_count = config_summary.get("routing_rule_count")
    hot_path = runtime_hot_path(runtime_summary)
    warp_present = WARP_OUTBOUND_TAG in outbound_tags
    direct_present = DIRECT_OUTBOUND_TAG in outbound_tags
    routing_present = isinstance(route_count, int) and route_count > 0
    ready = warp_present and direct_present and routing_present
    blockers: list[str] = []
    if not warp_present:
        blockers.append("xray_warp_outbound_missing")
    if not direct_present:
        blockers.append("xray_direct_outbound_missing")
    if not routing_present:
        blockers.append("xray_routing_rules_missing")

    return {
        "plan_id": PLAN_ID,
        "generated_at": generated_at or utc_now(),
        "decision": (
            "TELEGRAM_MEDIA_WARP_ROUTE_READY_TO_STAGE"
            if ready
            else "TELEGRAM_MEDIA_WARP_ROUTE_BLOCKED"
        ),
        "problem": {
            "symptom": "telegram_media_slow",
            "likely_failure_domain": "telegram_media_egress_route",
            "selected_bypass": "route Telegram media/data-center IPv4 ranges through existing Xray WARP outbound",
        },
        "current_evidence": {
            "xray_outbound_tags": outbound_tags,
            "xray_routing_rule_count": route_count,
            "telegram_media_status": hot_path.get("telegram_media_status"),
            "warp_status": hot_path.get("warp_status"),
            "runtime_reason": runtime_summary.get("reason"),
        },
        "target_rule": telegram_media_warp_rule(),
        "target_rule_source": {
            "basis": "Telegram AS / data-center IPv4 ranges used by current local probes and public AS/CIDR references",
            "refresh_required_before_deploy": True,
            "ipv6_deferred": True,
        },
        "config_patch_preview": config_patch,
        "rollout": {
            "applies_to": XRAY_CONFIG_PATH,
            "mutation_scope": "routing.rules only",
            "requires_explicit_operator_confirm": "APPLY_TELEGRAM_MEDIA_WARP_ROUTE",
            "requires_fresh_readonly_snapshot": True,
            "requires_config_backup": True,
            "requires_xray_config_test_before_restart": True,
            "restart_scope": ["x-ui"],
            "forbidden_restarts": [
                "ghost-access-nl-xhttp.service",
                "ghost-access-nl-https-ws.service",
                "telegram-bot-simple.service",
                "nginx",
            ],
            "rollback": "restore config backup, run xray config test, restart x-ui once",
        },
        "operator_steps": [
            "take a fresh read-only snapshot and confirm warp-svc is active plus 127.0.0.1:40000 accepts SOCKS",
            "backup /usr/local/x-ui/bin/config.json",
            "insert target_rule before the final direct tcp/udp catch-all rule",
            "run xray -test against the staged config",
            "restart only x-ui in a maintenance window",
            "test Telegram media through client profiles and compare direct vs WARP egress",
            "rollback from backup if Telegram media or normal browsing regresses",
        ],
        "blockers": blockers,
        "privacy": {
            "output_privacy_ok": True,
            "raw_subscription_url_stored": False,
            "raw_uuid_stored": False,
            "raw_ip_user_stored": False,
            "raw_credentials_stored": False,
            "raw_client_rows_stored": False,
        },
    }


def render_markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# NL Telegram Media WARP Route Plan - 2026-06-02",
        "",
        "## Decision",
        "",
        f"`{plan.get('decision')}`",
        "",
        "## Selected Bypass",
        "",
        str((plan.get("problem") or {}).get("selected_bypass") or ""),
        "",
        "## Current Evidence",
        "",
        "```json",
        json.dumps(plan.get("current_evidence") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Target Xray Rule",
        "",
        "```json",
        json.dumps(plan.get("target_rule") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Rollout Guard",
        "",
        "```json",
        json.dumps(plan.get("rollout") or {}, indent=2, ensure_ascii=False),
        "```",
        "",
        "## Operator Steps",
        "",
    ]
    for index, step in enumerate(plan.get("operator_steps") or [], start=1):
        lines.append(f"{index}. {step}")
    blockers = plan.get("blockers") or []
    if blockers:
        lines.extend(["", "## Blockers", "", "```json", json.dumps(blockers, indent=2), "```"])
    return "\n".join(lines).rstrip() + "\n"


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Build a safe plan to route Telegram media ranges through Xray WARP outbound."
    )
    p.add_argument("--config-summary", type=Path, default=DEFAULT_CONFIG_SUMMARY)
    p.add_argument("--runtime-summary", type=Path, default=DEFAULT_RUNTIME_SUMMARY)
    p.add_argument("--config", type=Path, default=None, help="optional full Xray config for patch preview")
    p.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT)
    p.add_argument("--markdown-out", type=Path, default=DEFAULT_MARKDOWN_OUT)
    p.add_argument("--write", action="store_true")
    p.add_argument("--json", action="store_true")
    return p


def run(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        config_summary = load_json_allowing_command_header(args.config_summary)
        runtime_summary = load_json_allowing_command_header(args.runtime_summary)
        patch_preview = None
        if args.config is not None:
            config = load_json_allowing_command_header(args.config)
            _, patch_preview = apply_telegram_media_warp_rule(config)
        plan = build_plan(
            config_summary=config_summary,
            runtime_summary=runtime_summary,
            config_patch=patch_preview,
        )
        if args.write:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.markdown_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(
                json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            args.markdown_out.write_text(render_markdown(plan), encoding="utf-8")
        if args.json:
            print(json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(f"decision={plan['decision']} blockers={len(plan['blockers'])}")
        return 0
    except TelegramMediaWarpPlanError as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True))
        else:
            print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(run())
