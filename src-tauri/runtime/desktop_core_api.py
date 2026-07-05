#!/usr/bin/env python3
"""Standalone local Core API for the packaged x0tta6bl4 desktop app.

This server intentionally uses only the Python standard library. It gives the
installed Ubuntu package a real local API surface even when the full source tree
is not installed under /opt/x0tta6bl4 yet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse


STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
STARTED_AT = time.time()
SCHEMA = "x0tta6bl4.packaged_desktop_core_api.v1"
CLAIM_BOUNDARY = (
    "Packaged desktop Core API exposes local Ubuntu node and control-panel "
    "state only. It does not prove production readiness, customer traffic, "
    "external DPI bypass, settlement finality, or live mesh dataplane delivery."
)
SENSITIVE_KEY_PARTS = {
    "api_key",
    "authorization",
    "bearer",
    "credential",
    "email",
    "install_command",
    "key",
    "link",
    "node_id",
    "password",
    "private",
    "secret",
    "token",
    "url",
    "vless",
    "wallet",
}
SENSITIVE_KEY_NAMES = {
    "did",
    "hostname",
    "id",
    "mesh_id",
    "owner_id",
    "peer_id",
    "spiffe_id",
    "svid",
}
IDENTIFIER_LIST_KEYS = {"peers", "peer_ids", "nodes", "users"}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_text(value: Any) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()


def redacted_identifier(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {"present": False, "redacted": True}
    return {"present": True, "sha256": sha256_text(value), "redacted": True}


def redact_value(value: Any, *, key: str = "") -> Any:
    key_lower = key.lower()
    if key_lower in SENSITIVE_KEY_NAMES or any(part in key_lower for part in SENSITIVE_KEY_PARTS):
        return redacted_identifier(value)
    if isinstance(value, dict):
        return {
            str(child_key): redact_value(child_value, key=str(child_key))
            for child_key, child_value in value.items()
        }
    if isinstance(value, list):
        if key_lower in IDENTIFIER_LIST_KEYS:
            return [
                redact_value(item, key=key) if isinstance(item, dict) else redacted_identifier(item)
                for item in value
            ]
        return [redact_value(item, key=key) for item in value]
    return value


def read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def runtime_files() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        read_json(STATE_DIR / "runtime-state.json"),
        read_json(STATE_DIR / "client-profile-hint.json"),
        read_json(STATE_DIR / "listener-loss-signal.json"),
    )


def claim_gate(surface: str, claims: list[str] | tuple[str, ...]) -> dict[str, Any]:
    return {
        "schema": "x0tta6bl4.desktop_claim_gate.v1",
        "surface": surface,
        "claims_allowed": [],
        "claims_blocked": list(claims),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def mesh_status() -> dict[str, Any]:
    runtime, hint, signal = runtime_files()
    return {
        "schema": SCHEMA,
        "status": "observed" if (runtime or hint or signal) else "missing",
        "mode": runtime.get("mode") or hint.get("runtime_mode"),
        "recommended_action": runtime.get("recommended_action") or hint.get("recommended_action"),
        "recommended_profile": hint.get("recommended_profile"),
        "listener_signal_status": signal.get("status"),
        "state_paths": {
            "runtime_state": str(STATE_DIR / "runtime-state.json"),
            "client_profile_hint": str(STATE_DIR / "client-profile-hint.json"),
            "listener_signal": str(STATE_DIR / "listener-loss-signal.json"),
        },
        "cross_plane_claim_gate": claim_gate(
            "packaged_desktop_core_api.mesh_status",
            ("dataplane_delivery", "traffic_delivery", "customer_traffic"),
        ),
    }


def live_snapshot(limit: int = 25) -> dict[str, Any]:
    runtime, hint, signal = runtime_files()
    runtime_events = []
    if runtime:
        runtime_events.append(
            {
                "type": "local_runtime_state",
                "surface": "mesh",
                "timestamp_utc": runtime.get("updated_at_utc") or utc_now(),
                "data": {
                    "mode": runtime.get("mode"),
                    "recommended_action": runtime.get("recommended_action"),
                    "node_id": redacted_identifier(runtime.get("node_id")),
                },
            }
        )
    if signal:
        runtime_events.append(
            {
                "type": "local_listener_signal",
                "surface": "mesh",
                "timestamp_utc": signal.get("updated_at_utc") or utc_now(),
                "data": {"status": signal.get("status"), "source": signal.get("source")},
            }
        )

    runtime_events = runtime_events[: max(1, min(limit, 100))]
    return {
        "schema": "x0tta6bl4.platform.live_snapshot.v1",
        "status": "observed" if (runtime or hint or signal) else "missing",
        "timestamp_utc": utc_now(),
        "local_state": {
            "runtime_state": redact_value(runtime),
            "client_profile_hint": redact_value(hint),
            "listener_signal": redact_value(signal),
            "raw_values_redacted": True,
        },
        "routers": {
            "mode": "packaged-desktop-core-api",
            "full_core_required_for_mutations": True,
        },
        "event_bus": {
            "status": "local_runtime_only",
            "recent_events": runtime_events,
            "recent_by_surface": {"mesh": runtime_events},
            "surface_counts": {"mesh": len(runtime_events)},
            "payloads_redacted": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
        "cross_plane_claim_gate": claim_gate(
            "packaged_desktop_core_api.live_snapshot",
            (
                "production_readiness",
                "dataplane_delivery",
                "customer_traffic",
                "dpi_bypass",
                "settlement_finality",
            ),
        ),
    }


def action_catalog() -> dict[str, Any]:
    actions = [
        ("mesh.refresh_runtime", "mesh", "Refresh local mesh runtime"),
        ("marketplace.refresh_snapshot", "marketplace", "Refresh marketplace snapshot"),
        ("billing.prepare_invoice", "billing", "Prepare local billing handoff"),
        ("wallet.open_ledger_status", "wallet", "Open local ledger status"),
        ("dao.prepare_proposal", "dao", "Prepare DAO proposal handoff"),
        ("readiness.snapshot", "ops", "Open local readiness snapshot"),
        ("vpn.refresh_status", "ops", "Refresh VPN/readiness status"),
    ]
    return {
        "schema": "x0tta6bl4.desktop_control_action_catalog.v1",
        "status": "available",
        "confirmation_phrase": "CONFIRM LOCAL ACTION",
        "actions": [
            {
                "action_id": action_id,
                "surface": surface,
                "label": label,
                "requires_confirmation": False,
                "requires_full_core_api": action_id != "mesh.refresh_runtime",
                "claim_boundary": CLAIM_BOUNDARY,
            }
            for action_id, surface, label in actions
        ],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def action_result(action_id: str) -> dict[str, Any]:
    return {
        "schema": "x0tta6bl4.desktop_control_action_result.v1",
        "status": "observed",
        "action_id": action_id,
        "execution_source": "packaged-desktop-core-api",
        "dry_run": True,
        "executed": action_id == "mesh.refresh_runtime",
        "mutation_performed": False,
        "message": "Packaged desktop Core API handled this as a local read-only control action.",
        "live_snapshot": live_snapshot(limit=10) if action_id == "mesh.refresh_runtime" else None,
        "claim_boundary": CLAIM_BOUNDARY,
        "timestamp": utc_now(),
    }


def ledger_status() -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "status": "desktop_read_only",
        "mode": "packaged-local",
        "settlement_finality_confirmed": False,
        "cross_plane_claim_gate": claim_gate(
            "packaged_desktop_core_api.ledger_status",
            ("settlement_finality", "production_readiness"),
        ),
    }


def node_readiness(mesh_id: str, node_id: str) -> dict[str, Any]:
    runtime, _hint, signal = runtime_files()
    return {
        "schema": SCHEMA,
        "status": "observed" if runtime else "missing",
        "mesh_id": redacted_identifier(mesh_id),
        "node_id": redacted_identifier(node_id),
        "local_runtime_mode": runtime.get("mode"),
        "listener_signal_status": signal.get("status"),
        "production_ready": False,
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_values_redacted": True,
    }


def node_telemetry(mesh_id: str, node_id: str) -> dict[str, Any]:
    runtime, hint, signal = runtime_files()
    return {
        "schema": SCHEMA,
        "status": "observed" if runtime else "missing",
        "mesh_id": redacted_identifier(mesh_id),
        "node_id": redacted_identifier(node_id),
        "runtime_state": redact_value(runtime),
        "client_profile_hint": redact_value(hint),
        "listener_signal": redact_value(signal),
        "claim_boundary": CLAIM_BOUNDARY,
        "raw_values_redacted": True,
    }


def get_payload(path: str, query: dict[str, list[str]]) -> Any:
    runtime, _hint, _signal = runtime_files()
    peers = runtime.get("peers") if isinstance(runtime.get("peers"), list) else []

    if path in {"/health", "/health/live", "/health/ready"}:
        return {"schema": SCHEMA, "status": "ok", "ready": True, "timestamp_utc": utc_now()}
    if path == "/status":
        return {
            "schema": SCHEMA,
            "status": "ok",
            "mode": "packaged-desktop-core-api",
            "uptime_s": round(time.time() - STARTED_AT, 3),
            "runtime_state_present": bool(runtime),
            "claim_boundary": CLAIM_BOUNDARY,
        }
    if path == "/mesh/status":
        return mesh_status()
    if path == "/mesh/peers":
        return {
            "schema": SCHEMA,
            "status": "observed",
            "count": len(peers),
            "peers": redact_value(peers, key="peers"),
            "raw_values_redacted": True,
            "cross_plane_claim_gate": claim_gate(
                "packaged_desktop_core_api.mesh_peers",
                ("dataplane_delivery", "customer_traffic"),
            ),
        }
    if path == "/api/v1/platform/live-snapshot":
        limit = int((query.get("limit") or ["25"])[0])
        return live_snapshot(limit=limit)
    if path == "/api/v1/actions":
        return action_catalog()
    if path == "/api/v1/ledger/status":
        return ledger_status()
    if path == "/api/v1/ledger/search":
        return {"schema": SCHEMA, "status": "desktop_read_only", "results": [], "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/maas/marketplace/status":
        return {
            "schema": SCHEMA,
            "status": "desktop_read_only",
            "mode": "packaged-local",
            "listings_endpoint": "/api/v1/maas/marketplace/search",
            "claim_boundary": CLAIM_BOUNDARY,
        }
    if path == "/api/v1/maas/marketplace/search":
        return []
    if path == "/api/v1/maas/billing/billing/plans":
        return [
            {"name": "free", "limits": {"meshes": 1, "nodes_per_mesh": 3, "bandwidth_gb": 10}},
            {"name": "pro", "limits": {"meshes": 10, "nodes_per_mesh": 50, "bandwidth_gb": 1000}},
            {"name": "enterprise", "limits": {"meshes": "custom", "nodes_per_mesh": "custom", "bandwidth_gb": "custom"}},
        ]
    if path == "/api/v1/maas/billing/billing/estimate":
        return {"schema": SCHEMA, "status": "prepared", "estimated_total_cents": 0, "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/maas/billing/usage":
        return {"schema": SCHEMA, "status": "desktop_read_only", "owner_id": "local-desktop", "meshes": [], "total_node_hours": 0}
    if path == "/api/v1/maas/governance/readiness":
        return {"schema": SCHEMA, "status": "desktop_read_only", "ready": False, "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/maas/governance/proposals":
        return {"schema": SCHEMA, "proposals": []}
    if path == "/api/v1/maas/agents/health/status":
        return {"schema": SCHEMA, "status": "desktop_read_only", "agent_mesh_ready": False, "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/service-identity/status":
        return {"schema": SCHEMA, "status": "desktop_read_only", "spiffe_domain": "spiffe://x0tta6bl4.mesh", "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/service-identity/event-trace-filter":
        return {"schema": SCHEMA, "status": "desktop_read_only", "filters": [], "payloads_redacted": True}
    if path == "/api/v1/service-identity/event-traces":
        return {"schema": SCHEMA, "status": "desktop_read_only", "events": [], "payloads_redacted": True}
    if path == "/api/v1/vpn/readiness":
        return {"schema": SCHEMA, "status": "desktop_read_only", "ready": False, "runtime_state_present": bool(runtime), "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/vpn/status":
        return {
            "schema": SCHEMA,
            "status": "observed" if runtime else "missing",
            "runtime_state": redact_value(runtime),
            "claim_boundary": CLAIM_BOUNDARY,
            "raw_values_redacted": True,
        }
    if path == "/api/v1/vpn/users":
        return {"schema": SCHEMA, "status": "desktop_read_only", "users": [], "claim_boundary": CLAIM_BOUNDARY}
    if path == "/api/v1/maas/provisioning/readiness":
        return {"schema": SCHEMA, "status": "desktop_read_only", "ready": False, "claim_boundary": CLAIM_BOUNDARY}
    if "/api/v1/maas/nodes/" in path and path.endswith("/nodes/pending"):
        return {"schema": SCHEMA, "status": "desktop_read_only", "nodes": []}
    if "/api/v1/maas/nodes/" in path and path.endswith("/nodes/all"):
        return {
            "schema": SCHEMA,
            "status": "desktop_read_only",
            "nodes": redact_value(peers, key="nodes"),
            "raw_values_redacted": True,
        }
    if "/api/v1/maas/nodes/" in path and path.endswith("/readiness"):
        parts = path.split("/")
        return node_readiness(parts[5] if len(parts) > 5 else "local-mesh", parts[-2] if len(parts) > 2 else "local-node")
    if "/api/v1/maas/nodes/" in path and path.endswith("/telemetry"):
        parts = path.split("/")
        return node_telemetry(parts[5] if len(parts) > 5 else "local-mesh", parts[-2] if len(parts) > 2 else "local-node")
    return None


class Handler(BaseHTTPRequestHandler):
    server_version = "x0tta6bl4DesktopCore/0.1"

    def _headers(
        self,
        status: HTTPStatus,
        content_type: str = "application/json",
        content_length: int | None = None,
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        if content_length is not None:
            self.send_header("Content-Length", str(content_length))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-API-Key, X-Agent-Token")
        self.end_headers()

    def _json(self, status: HTTPStatus, payload: Any) -> None:
        body = json.dumps(payload, indent=2, sort_keys=True).encode("utf-8") + b"\n"
        self._headers(status, content_length=len(body))
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self._headers(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/metrics":
            body = (
                "# HELP x0tta6bl4_packaged_desktop_core_api_up Packaged desktop Core API status.\n"
                "# TYPE x0tta6bl4_packaged_desktop_core_api_up gauge\n"
                "x0tta6bl4_packaged_desktop_core_api_up 1\n"
            ).encode("utf-8")
            self._headers(HTTPStatus.OK, "text/plain; version=0.0.4", len(body))
            self.wfile.write(body)
            return
        payload = get_payload(parsed.path, parse_qs(parsed.query))
        if payload is None:
            self._json(HTTPStatus.NOT_FOUND, {"schema": SCHEMA, "status": "not_found", "path": parsed.path})
            return
        self._json(HTTPStatus.OK, payload)

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or "0")
        raw_body = self.rfile.read(length) if length else b"{}"
        try:
            payload = json.loads(raw_body.decode("utf-8") or "{}")
        except Exception:
            payload = {}
        if parsed.path == "/api/v1/actions/execute":
            action_id = payload.get("action_id") if isinstance(payload, dict) else None
            self._json(HTTPStatus.OK, action_result(str(action_id or "unknown")))
            return
        self._json(
            HTTPStatus.ACCEPTED,
            {
                "schema": SCHEMA,
                "status": "mutation_requires_full_core_api",
                "path": parsed.path,
                "claim_boundary": CLAIM_BOUNDARY,
            },
        )

    def log_message(self, fmt: str, *args: Any) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="Run packaged x0tta6bl4 desktop Core API.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
