#!/usr/bin/env python3
"""Run a real Go-agent control-loop smoke against a local MaaS API.

This verifier starts a temporary MaaS HTTP API, builds the Go agent, runs the
agent binary with a temporary config, approves the pending node, and waits for:

1. agent registration through /api/v1/maas/{mesh_id}/nodes/register
2. agent node-config fetch through /api/v1/maas/{mesh_id}/node-config/{node_id}
3. agent heartbeat through /api/v1/maas/{mesh_id}/nodes/{node_id}/heartbeat
4. operator heal call after that real-agent heartbeat, with production/customer
   claims still fail-closed

It uses a temporary SQLite database and temporary EventBus working directory.
No real API keys, join tokens, shared database, production network state, or
customer traffic are used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.database import Base, MeshNode, User


SCHEMA = "x0tta6bl4.maas_real_agent_control_loop_smoke.v1"
READY_DECISION = "MAAS_REAL_AGENT_CONTROL_LOOP_SMOKE_READY"
BLOCKED_DECISION = "MAAS_REAL_AGENT_CONTROL_LOOP_SMOKE_BLOCKED"
CLAIM_BOUNDARY = (
    "Local real-agent smoke only. It proves a locally built Go agent can talk "
    "to a temporary MaaS API for registration, approved node-config fetch, and "
    "heartbeat persistence, then lets an operator heal a locally forced offline "
    "node while post-heal traffic/customer/external/SLO/production claims remain "
    "fail-closed. It "
    "does not prove external infrastructure provisioning, customer traffic "
    "delivery, VPN availability, external DPI bypass, payment settlement "
    "finality, production SLOs, or production readiness."
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8", errors="replace")).hexdigest()


def _redacted_id(value: Any) -> dict[str, Any]:
    text = str(value or "")
    return {
        "present": bool(text),
        "sha256": _sha256_text(text) if text else None,
        "raw_value_redacted": True,
    }


def _free_tcp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _free_udp_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _http_json(
    method: str,
    url: str,
    *,
    body: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
    timeout: float = 20.0,
) -> tuple[int, dict[str, Any], str]:
    data = None
    request_headers = {"Accept": "application/json", **dict(headers or {})}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers["Content-Type"] = "application/json"
    request = Request(url, data=data, headers=request_headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return response.status, json.loads(raw or "{}"), raw
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(raw or "{}")
        except json.JSONDecodeError:
            parsed = {}
        return exc.code, parsed, raw


def _wait_until(
    predicate: Callable[[], Any],
    *,
    timeout_seconds: float,
    interval_seconds: float = 0.2,
) -> Any:
    deadline = time.monotonic() + timeout_seconds
    last_value: Any = None
    while time.monotonic() < deadline:
        last_value = predicate()
        if last_value:
            return last_value
        time.sleep(interval_seconds)
    return last_value


def _spawn_output_reader(proc: subprocess.Popen[str], lines: list[str]) -> threading.Thread:
    def read_output() -> None:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            lines.append(line.rstrip("\n"))

    thread = threading.Thread(target=read_output, daemon=True)
    thread.start()
    return thread


def _stop_process(proc: subprocess.Popen[str], *, timeout_seconds: float = 5.0) -> None:
    if proc.poll() is not None:
        return
    try:
        proc.send_signal(signal.SIGTERM)
        proc.wait(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=timeout_seconds)


def _start_local_tcp_listener(
    host: str = "127.0.0.1",
) -> tuple[socket.socket, int, threading.Event, threading.Thread]:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind((host, 0))
    sock.listen(16)
    sock.settimeout(0.2)
    port = int(sock.getsockname()[1])
    stop_event = threading.Event()

    def accept_loop() -> None:
        while not stop_event.is_set():
            try:
                conn, _addr = sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                conn.close()
            except OSError:
                pass

    thread = threading.Thread(target=accept_loop, daemon=True)
    thread.start()
    return sock, port, stop_event, thread


def _stop_local_tcp_listener(
    sock: socket.socket | None,
    stop_event: threading.Event | None,
    thread: threading.Thread | None,
) -> None:
    if stop_event is not None:
        stop_event.set()
    if sock is not None:
        try:
            sock.close()
        except OSError:
            pass
    if thread is not None:
        thread.join(timeout=1.0)


def _stage(
    name: str,
    *,
    ok: bool,
    details: Mapping[str, Any] | None = None,
    http_status_code: int | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "http_status_code": http_status_code,
        "details": dict(details or {}),
    }


def _make_report(
    *,
    event_project_root: Path,
    db_path: Path,
    api_port: int,
    agent_node_id: str,
    dataplane_probe_target: str,
    requested_dataplane_probe_target: str | None = None,
    local_listener_target: bool = False,
) -> dict[str, Any]:
    requested_target = requested_dataplane_probe_target or dataplane_probe_target
    target_host = dataplane_probe_target.rsplit(":", 1)[0]
    return {
        "schema": SCHEMA,
        "decision": BLOCKED_DECISION,
        "ready": False,
        "duration_ms": None,
        "stages": [],
        "entities": {
            "mesh": {"present": False, "raw_value_redacted": True},
            "node": _redacted_id(agent_node_id),
        },
        "api": {
            "local_host": "127.0.0.1",
            "port": api_port,
            "temporary_uvicorn": True,
        },
        "database": {
            "temporary_sqlite": True,
            "path": str(db_path),
        },
        "agent": {
            "binary_built": False,
            "process_started": False,
            "node_runtime_credential_hash_stored": False,
            "node_runtime_credential_expiry_stored": False,
            "node_runtime_credential_rotation_observed": False,
            "raw_node_runtime_credential_redacted": True,
            "config_file_temporary": True,
            "node_config_fetch_observed": False,
            "heartbeat_observed": False,
            "operator_heal_observed": False,
        },
        "healing_surface": {
            "observed": False,
            "post_action_revalidation_present": False,
            "dataplane_confirmed": False,
            "post_action_dataplane_revalidated": False,
            "restored_dataplane_claim_allowed": False,
            "traffic_delivery_claim_allowed": False,
            "customer_traffic_claim_allowed": False,
            "external_reachability_claim_allowed": False,
            "production_slo_claim_allowed": False,
            "production_readiness_claim_allowed": False,
            "raw_target_redacted": True,
        },
        "dataplane_probe_target": {
            "sha256": _sha256_text(dataplane_probe_target),
            "requested_sha256": _sha256_text(requested_target),
            "raw_value_redacted": True,
            "requested_raw_value_redacted": True,
            "local_listener_target": bool(local_listener_target),
            "loopback_lab_target": target_host in {"127.0.0.1", "::1", "localhost"},
        },
        "event_project_root": str(event_project_root),
        "claim_boundary": CLAIM_BOUNDARY,
    }


def _fail(report: dict[str, Any], stage: str, details: Mapping[str, Any]) -> dict[str, Any]:
    report["decision"] = BLOCKED_DECISION
    report["ready"] = False
    report["failure"] = {
        "stage": stage,
        "details": dict(details),
    }
    return report


def run_verification(
    *,
    work_dir: str,
    dataplane_probe_target: str = "127.0.0.1",
    timeout_seconds: float = 45.0,
    use_local_listener_target: bool = True,
) -> dict[str, Any]:
    started = time.monotonic()
    work_path = Path(work_dir)
    work_path.mkdir(parents=True, exist_ok=True)
    db_path = work_path / "maas-real-agent-smoke.db"
    api_port = _free_tcp_port()
    api_url = f"http://127.0.0.1:{api_port}"
    agent_node_id = f"agent-{uuid.uuid4().hex[:16]}"
    requested_dataplane_probe_target = dataplane_probe_target
    listener_sock: socket.socket | None = None
    listener_stop: threading.Event | None = None
    listener_thread: threading.Thread | None = None
    if use_local_listener_target:
        listener_sock, listener_port, listener_stop, listener_thread = (
            _start_local_tcp_listener()
        )
        dataplane_probe_target = f"127.0.0.1:{listener_port}"
    report = _make_report(
        event_project_root=work_path,
        db_path=db_path,
        api_port=api_port,
        agent_node_id=agent_node_id,
        dataplane_probe_target=dataplane_probe_target,
        requested_dataplane_probe_target=requested_dataplane_probe_target,
        local_listener_target=use_local_listener_target,
    )

    def finalize(result: dict[str, Any]) -> dict[str, Any]:
        result["duration_ms"] = round((time.monotonic() - started) * 1000, 3)
        return result

    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    server_lines: list[str] = []
    agent_lines: list[str] = []
    server_proc: subprocess.Popen[str] | None = None
    agent_proc: subprocess.Popen[str] | None = None

    try:
        env = os.environ.copy()
        env.update(
            {
                "DATABASE_URL": f"sqlite:///{db_path}",
                "PYTHONPATH": str(ROOT),
                "MAAS_LIGHT_MODE": "true",
                "LOG_LEVEL": "WARNING",
                "X0TTA6BL4_MESH_HEAL_POST_ACTION_PROBE": "1",
            }
        )
        server_proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "uvicorn",
                "src.core.app:app",
                "--host",
                "127.0.0.1",
                "--port",
                str(api_port),
                "--log-level",
                "warning",
                "--lifespan",
                "off",
            ],
            cwd=str(work_path),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _spawn_output_reader(server_proc, server_lines)
        ready = _wait_until(
            lambda: _http_json("GET", f"{api_url}/health", timeout=1.0)[0] == 200,
            timeout_seconds=min(60.0, timeout_seconds),
        )
        report["stages"].append(
            _stage("local_maas_api_started", ok=bool(ready), details={"url": api_url})
        )
        if not ready:
            return finalize(
                _fail(
                    report,
                    "local_maas_api_started",
                    {
                        "server_exit_code": server_proc.poll(),
                        "server_output_tail": server_lines[-20:],
                    },
                )
            )

        status_code, register_body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/auth/register",
            body={
                "email": f"real-agent-{uuid.uuid4().hex}@test.local",
                "password": f"pw-{uuid.uuid4().hex}",
                "name": "Real Agent Smoke",
            },
        )
        report["stages"].append(
            _stage(
                "operator_register",
                ok=status_code == 200,
                http_status_code=status_code,
                details={"api_key_returned": bool(register_body.get("access_token"))},
            )
        )
        api_key = str(register_body.get("access_token") or "")
        if status_code != 200 or not api_key:
            return finalize(
                _fail(report, "operator_register", {"response_preview": raw[:500]})
            )

        db = SessionLocal()
        try:
            operator_user = db.query(User).filter(User.email == register_body.get("email")).first()
            if operator_user is not None:
                operator_user.role = "operator"
                db.commit()
            operator_role_assigned = operator_user is not None
        finally:
            db.close()
        report["stages"].append(
            _stage(
                "temporary_operator_role_assigned",
                ok=operator_role_assigned,
                details={
                    "temporary_sqlite_only": True,
                    "operator_role_required_for_revoke": True,
                },
            )
        )
        if not operator_role_assigned:
            return finalize(
                _fail(
                    report,
                    "temporary_operator_role_assigned",
                    {"registered_email_present": bool(register_body.get("email"))},
                )
            )

        status_code, deploy_body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/mesh/deploy",
            body={
                "name": "Real Agent Control Loop Smoke",
                "nodes": 1,
                "billing_plan": "starter",
                "pqc_enabled": True,
                "join_token_ttl_sec": 3600,
            },
            headers={"X-API-Key": api_key},
        )
        mesh_id = str(deploy_body.get("mesh_id") or "")
        join_config = deploy_body.get("join_config") or {}
        join_token = str(
            join_config.get("enrollment_token")
            or join_config.get("token")
            or ""
        )
        report["entities"]["mesh"] = _redacted_id(mesh_id)
        report["stages"].append(
            _stage(
                "mesh_deploy",
                ok=status_code in {200, 201} and bool(mesh_id and join_token),
                http_status_code=status_code,
                details={
                    "mesh_id_present": bool(mesh_id),
                    "join_token_present": bool(join_token),
                    "raw_join_token_redacted": True,
                },
            )
        )
        if status_code not in {200, 201} or not mesh_id or not join_token:
            return finalize(_fail(report, "mesh_deploy", {"response_preview": raw[:500]}))

        agent_binary = work_path / "x0t-agent"
        build = subprocess.run(
            ["go", "build", "-o", str(agent_binary), "."],
            cwd=str(ROOT / "agent"),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
            check=False,
        )
        report["agent"]["binary_built"] = build.returncode == 0
        report["stages"].append(
            _stage(
                "go_agent_build",
                ok=build.returncode == 0,
                details={
                    "exit_code": build.returncode,
                    "output_tail": build.stdout.splitlines()[-20:],
                },
            )
        )
        if build.returncode != 0:
            return finalize(_fail(report, "go_agent_build", {"exit_code": build.returncode}))

        listen_port = _free_udp_port()
        multicast_port = _free_udp_port()
        config_path = work_path / "agent.yaml"
        config_path.write_text(
            "\n".join(
                [
                    f'node_id: "{agent_node_id}"',
                    f'api_endpoint: "{api_url}"',
                    f'join_token: "{join_token}"',
                    f'mesh_id: "{mesh_id}"',
                    f"listen_port: {listen_port}",
                    'bind_addr: "127.0.0.1"',
                    'multicast_group: "239.255.77.77"',
                    f"multicast_port: {multicast_port}",
                    f'dataplane_probe_target: "{dataplane_probe_target}"',
                    "heartbeat_interval_sec: 1",
                    "pqc_enabled: true",
                    'obfuscation: "none"',
                    'traffic_profile: "none"',
                    'log_level: "debug"',
                    "",
                ]
            ),
            encoding="utf-8",
        )

        agent_proc = subprocess.Popen(
            [str(agent_binary), "--config", str(config_path)],
            cwd=str(work_path),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        _spawn_output_reader(agent_proc, agent_lines)
        report["agent"]["process_started"] = True
        report["stages"].append(
            _stage(
                "go_agent_started",
                ok=agent_proc.poll() is None,
                details={"pid_present": agent_proc.pid > 0},
            )
        )

        def pending_node_seen() -> bool:
            db = SessionLocal()
            try:
                node = (
                    db.query(MeshNode)
                    .filter(MeshNode.mesh_id == mesh_id, MeshNode.id == agent_node_id)
                    .first()
                )
                return node is not None and node.status in {"pending", "pending_approval"}
            finally:
                db.close()

        pending = _wait_until(
            pending_node_seen,
            timeout_seconds=min(15.0, timeout_seconds),
        )
        report["stages"].append(
            _stage(
                "agent_registration_pending",
                ok=bool(pending),
                details={"node_id_present": True, "raw_node_id_redacted": True},
            )
        )
        if not pending:
            return finalize(
                _fail(
                    report,
                    "agent_registration_pending",
                    {
                        "agent_exit_code": agent_proc.poll(),
                        "agent_output_tail": agent_lines[-30:],
                    },
                )
            )

        def agent_runtime_credential_metadata_seen() -> dict[str, bool]:
            db = SessionLocal()
            try:
                node = (
                    db.query(MeshNode)
                    .filter(MeshNode.mesh_id == mesh_id, MeshNode.id == agent_node_id)
                    .first()
                )
                return {
                    "hash_present": bool(
                        node is not None
                        and isinstance(node.runtime_credential_hash, str)
                        and len(node.runtime_credential_hash) == 64
                    ),
                    "expires_at_present": bool(
                        node is not None
                        and node.runtime_credential_expires_at is not None
                    ),
                    "rotated_at_present": bool(
                        node is not None
                        and node.runtime_credential_rotated_at is not None
                    ),
                }
            finally:
                db.close()

        credential_metadata = agent_runtime_credential_metadata_seen()
        credential_hash_stored = credential_metadata["hash_present"]
        credential_expiry_stored = credential_metadata["expires_at_present"]
        report["agent"]["node_runtime_credential_hash_stored"] = (
            credential_hash_stored
        )
        report["agent"]["node_runtime_credential_expiry_stored"] = (
            credential_expiry_stored
        )
        report["stages"].append(
            _stage(
                "agent_node_runtime_credential_metadata_stored",
                ok=credential_hash_stored and credential_expiry_stored,
                details={
                    **credential_metadata,
                    "raw_node_runtime_credential_redacted": True,
                },
            )
        )
        if not credential_hash_stored or not credential_expiry_stored:
            return finalize(
                _fail(
                    report,
                    "agent_node_runtime_credential_metadata_stored",
                    {"raw_node_runtime_credential_redacted": True},
                )
            )

        status_code, approve_body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{agent_node_id}/approve",
            headers={"X-API-Key": api_key},
        )
        approved = status_code == 200 and str(approve_body.get("status")) == "approved"
        report["stages"].append(
            _stage(
                "operator_approved_agent_node",
                ok=approved,
                http_status_code=status_code,
                details={"status": approve_body.get("status")},
            )
        )
        if not approved:
            return finalize(
                _fail(report, "operator_approved_agent_node", {"response_preview": raw[:500]})
            )

        status_code, _body, raw = _http_json(
            "GET",
            f"{api_url}/api/v1/maas/{mesh_id}/node-config/{agent_node_id}",
            headers={"Authorization": f"Bearer {join_token}"},
        )
        report["stages"].append(
            _stage(
                "enrollment_token_node_config_rejected",
                ok=status_code == 401,
                http_status_code=status_code,
                details={
                    "join_token_reuse_attempted": True,
                    "raw_join_token_redacted": True,
                },
            )
        )
        if status_code != 401:
            return finalize(
                _fail(
                    report,
                    "enrollment_token_node_config_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        heartbeat_probe = {
            "status": "healthy",
            "latency_ms": 1.0,
            "traffic_mbps": 0.0,
            "active_connections": 0,
            "dataplane_probe_target": dataplane_probe_target,
        }

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{agent_node_id}/heartbeat",
            body=heartbeat_probe,
        )
        report["stages"].append(
            _stage(
                "missing_heartbeat_credential_rejected",
                ok=status_code == 401,
                http_status_code=status_code,
                details={"node_runtime_credential_required": True},
            )
        )
        if status_code != 401:
            return finalize(
                _fail(
                    report,
                    "missing_heartbeat_credential_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{agent_node_id}/heartbeat",
            body=heartbeat_probe,
            headers={"X-API-Key": f"x0tn_wrong_{uuid.uuid4().hex}"},
        )
        report["stages"].append(
            _stage(
                "wrong_heartbeat_credential_rejected",
                ok=status_code == 401,
                http_status_code=status_code,
                details={
                    "wrong_node_runtime_credential_rejected": True,
                    "raw_wrong_credential_redacted": True,
                },
            )
        )
        if status_code != 401:
            return finalize(
                _fail(
                    report,
                    "wrong_heartbeat_credential_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        secondary_node_id = f"agent-negative-{uuid.uuid4().hex[:12]}"
        status_code, secondary_body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/register",
            body={
                "node_id": secondary_node_id,
                "enrollment_token": join_token,
                "device_class": "edge",
            },
        )
        secondary_runtime_credential = str(secondary_body.get("api_key") or "")
        secondary_registered = status_code == 200 and bool(
            secondary_runtime_credential
        )
        report["stages"].append(
            _stage(
                "secondary_node_registered_for_negative_acl",
                ok=secondary_registered,
                http_status_code=status_code,
                details={
                    "secondary_node_id_present": bool(secondary_node_id),
                    "secondary_runtime_credential_present": bool(
                        secondary_runtime_credential
                    ),
                    "raw_secondary_runtime_credential_redacted": True,
                },
            )
        )
        if not secondary_registered:
            return finalize(
                _fail(
                    report,
                    "secondary_node_registered_for_negative_acl",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{secondary_node_id}/approve",
            headers={"X-API-Key": api_key},
        )
        secondary_approved = status_code == 200
        report["stages"].append(
            _stage(
                "secondary_node_approved_for_negative_acl",
                ok=secondary_approved,
                http_status_code=status_code,
                details={"approval_required_before_revocation_check": True},
            )
        )
        if not secondary_approved:
            return finalize(
                _fail(
                    report,
                    "secondary_node_approved_for_negative_acl",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, rotated_secondary_body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{secondary_node_id}/runtime-credential/rotate",
            body={"ttl_seconds": 3600},
            headers={"X-API-Key": secondary_runtime_credential},
        )
        rotated_secondary_credential = str(
            rotated_secondary_body.get("node_runtime_credential")
            or rotated_secondary_body.get("api_key")
            or ""
        )
        secondary_rotated = (
            status_code == 200
            and bool(rotated_secondary_credential)
            and rotated_secondary_credential != secondary_runtime_credential
        )
        report["agent"]["node_runtime_credential_rotation_observed"] = (
            secondary_rotated
        )
        report["stages"].append(
            _stage(
                "secondary_node_runtime_credential_rotated",
                ok=secondary_rotated,
                http_status_code=status_code,
                details={
                    "new_runtime_credential_present": bool(rotated_secondary_credential),
                    "old_runtime_credential_invalidated_expected": True,
                    "raw_runtime_credentials_redacted": True,
                },
            )
        )
        if not secondary_rotated:
            return finalize(
                _fail(
                    report,
                    "secondary_node_runtime_credential_rotated",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{secondary_node_id}/heartbeat",
            body=heartbeat_probe,
            headers={"X-API-Key": secondary_runtime_credential},
        )
        report["stages"].append(
            _stage(
                "old_rotated_runtime_credential_rejected",
                ok=status_code == 401,
                http_status_code=status_code,
                details={"old_runtime_credential_invalidated": True},
            )
        )
        if status_code != 401:
            return finalize(
                _fail(
                    report,
                    "old_rotated_runtime_credential_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )
        secondary_runtime_credential = rotated_secondary_credential

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{agent_node_id}/heartbeat",
            body={**heartbeat_probe, "node_id": secondary_node_id},
            headers={"X-API-Key": secondary_runtime_credential},
        )
        report["stages"].append(
            _stage(
                "heartbeat_path_body_node_mismatch_rejected",
                ok=status_code == 409,
                http_status_code=status_code,
                details={
                    "path_node_and_body_node_mismatch_rejected": True,
                    "raw_node_ids_redacted": True,
                },
            )
        )
        if status_code != 409:
            return finalize(
                _fail(
                    report,
                    "heartbeat_path_body_node_mismatch_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{agent_node_id}/heartbeat",
            body=heartbeat_probe,
            headers={"X-API-Key": secondary_runtime_credential},
        )
        report["stages"].append(
            _stage(
                "cross_node_credential_rejected",
                ok=status_code == 401,
                http_status_code=status_code,
                details={
                    "credential_bound_to_different_node": True,
                    "raw_secondary_runtime_credential_redacted": True,
                },
            )
        )
        if status_code != 401:
            return finalize(
                _fail(
                    report,
                    "cross_node_credential_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{secondary_node_id}/revoke",
            headers={"X-API-Key": api_key},
        )
        secondary_revoked = status_code == 200
        report["stages"].append(
            _stage(
                "secondary_node_revoked_for_negative_acl",
                ok=secondary_revoked,
                http_status_code=status_code,
                details={"revoked_node_must_lose_runtime_access": True},
            )
        )
        if not secondary_revoked:
            return finalize(
                _fail(
                    report,
                    "secondary_node_revoked_for_negative_acl",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        status_code, _body, raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{secondary_node_id}/heartbeat",
            body=heartbeat_probe,
            headers={"X-API-Key": secondary_runtime_credential},
        )
        report["stages"].append(
            _stage(
                "revoked_node_credential_rejected",
                ok=status_code == 403,
                http_status_code=status_code,
                details={"revoked_node_runtime_access_rejected": True},
            )
        )
        if status_code != 403:
            return finalize(
                _fail(
                    report,
                    "revoked_node_credential_rejected",
                    {"response_preview": raw[:500], "actual_status": status_code},
                )
            )

        config_observed = _wait_until(
            lambda: any("node config fetched" in line for line in agent_lines),
            timeout_seconds=min(20.0, timeout_seconds),
        )
        report["agent"]["node_config_fetch_observed"] = bool(config_observed)
        report["stages"].append(
            _stage(
                "agent_node_config_fetch_observed",
                ok=bool(config_observed),
                details={"observed_in_agent_stdout": bool(config_observed)},
            )
        )
        if not config_observed:
            return finalize(
                _fail(
                    report,
                    "agent_node_config_fetch_observed",
                    {"agent_output_tail": agent_lines[-40:]},
                )
            )

        def heartbeat_seen() -> dict[str, Any] | None:
            db = SessionLocal()
            try:
                node = (
                    db.query(MeshNode)
                    .filter(MeshNode.mesh_id == mesh_id, MeshNode.id == agent_node_id)
                    .first()
                )
                if (
                    node is not None
                    and node.status == "approved"
                    and node.last_seen is not None
                    and node.ip_address == dataplane_probe_target
                ):
                    return {
                        "status": node.status,
                        "last_seen_present": True,
                        "dataplane_probe_target_hash": _sha256_text(node.ip_address),
                    }
                return None
            finally:
                db.close()

        heartbeat = _wait_until(
            heartbeat_seen,
            timeout_seconds=min(20.0, timeout_seconds),
        )
        report["agent"]["heartbeat_observed"] = bool(heartbeat)
        report["stages"].append(
            _stage(
                "agent_heartbeat_persisted",
                ok=bool(heartbeat),
                details=heartbeat
                or {
                    "status": "missing",
                    "raw_dataplane_probe_target_redacted": True,
                },
            )
        )
        if not heartbeat:
            return finalize(
                _fail(
                    report,
                    "agent_heartbeat_persisted",
                    {"agent_output_tail": agent_lines[-40:]},
                )
            )

        def mark_agent_offline_for_heal() -> dict[str, Any] | None:
            db = SessionLocal()
            try:
                node = (
                    db.query(MeshNode)
                    .filter(MeshNode.mesh_id == mesh_id, MeshNode.id == agent_node_id)
                    .first()
                )
                if node is None:
                    return None
                previous_status = str(node.status)
                node.status = "offline"
                db.commit()
                return {
                    "previous_status": previous_status,
                    "offline_status_persisted": True,
                    "raw_node_id_redacted": True,
                }
            finally:
                db.close()

        offline_for_heal = mark_agent_offline_for_heal()
        report["stages"].append(
            _stage(
                "agent_node_marked_offline_for_local_heal",
                ok=bool(offline_for_heal),
                details=offline_for_heal
                or {
                    "offline_status_persisted": False,
                    "raw_node_id_redacted": True,
                },
            )
        )
        if not offline_for_heal:
            return finalize(
                _fail(
                    report,
                    "agent_node_marked_offline_for_local_heal",
                    {"raw_node_id_redacted": True},
                )
            )

        status_code, heal_body, _raw = _http_json(
            "POST",
            f"{api_url}/api/v1/maas/{mesh_id}/nodes/{agent_node_id}/heal",
            headers={"X-API-Key": api_key},
        )
        revalidation = (
            heal_body.get("post_action_dataplane_revalidation")
            if isinstance(heal_body, dict)
            else None
        )
        if not isinstance(revalidation, dict):
            revalidation = {}
        rendered_heal = json.dumps(heal_body, sort_keys=True)

        def post_heal_node_state() -> dict[str, Any]:
            db = SessionLocal()
            try:
                node = (
                    db.query(MeshNode)
                    .filter(MeshNode.mesh_id == mesh_id, MeshNode.id == agent_node_id)
                    .first()
                )
                return {
                    "status": str(node.status) if node is not None else None,
                    "last_seen_present": bool(
                        node is not None and node.last_seen is not None
                    ),
                    "raw_node_id_redacted": True,
                }
            finally:
                db.close()

        post_heal_state = post_heal_node_state()
        try:
            components_healed = int(heal_body.get("components_healed") or 0)
        except (TypeError, ValueError):
            components_healed = 0
        healing_surface = {
            "observed": status_code == 200,
            "status": heal_body.get("status") if isinstance(heal_body, dict) else None,
            "healing_claim": heal_body.get("healing_claim")
            if isinstance(heal_body, dict)
            else None,
            "components_healed": components_healed,
            "post_heal_node_status": post_heal_state["status"],
            "post_action_revalidation_present": bool(revalidation),
            "dataplane_confirmed": (
                heal_body.get("dataplane_confirmed") is True
                if isinstance(heal_body, dict)
                else False
            ),
            "post_action_dataplane_revalidated": (
                heal_body.get("post_action_dataplane_revalidated") is True
                if isinstance(heal_body, dict)
                else False
            ),
            "restored_dataplane_claim_allowed": (
                heal_body.get("restored_dataplane_claim_allowed") is True
                if isinstance(heal_body, dict)
                else False
            ),
            "traffic_delivery_claim_allowed": revalidation.get(
                "traffic_delivery_claim_allowed"
            )
            is True,
            "customer_traffic_claim_allowed": revalidation.get(
                "customer_traffic_claim_allowed"
            )
            is True,
            "external_reachability_claim_allowed": revalidation.get(
                "external_reachability_claim_allowed"
            )
            is True,
            "production_slo_claim_allowed": revalidation.get(
                "production_slo_claim_allowed"
            )
            is True,
            "production_readiness_claim_allowed": revalidation.get(
                "production_readiness_claim_allowed"
            )
            is True,
            "raw_target_redacted": dataplane_probe_target not in rendered_heal,
        }
        report["healing_surface"] = healing_surface
        heal_checked = (
            status_code == 200
            and healing_surface["status"] == "healed"
            and healing_surface["healing_claim"] == "local_control_action_applied"
            and healing_surface["components_healed"] > 0
            and healing_surface["post_heal_node_status"] == "healthy"
            and healing_surface["post_action_revalidation_present"] is True
            and healing_surface["dataplane_confirmed"] is True
            and healing_surface["post_action_dataplane_revalidated"] is True
            and healing_surface["restored_dataplane_claim_allowed"] is True
            and healing_surface["traffic_delivery_claim_allowed"] is False
            and healing_surface["customer_traffic_claim_allowed"] is False
            and healing_surface["external_reachability_claim_allowed"] is False
            and healing_surface["production_slo_claim_allowed"] is False
            and healing_surface["production_readiness_claim_allowed"] is False
            and healing_surface["raw_target_redacted"] is True
        )
        report["agent"]["operator_heal_observed"] = heal_checked
        report["stages"].append(
            _stage(
                "operator_heal_after_real_agent_heartbeat",
                ok=heal_checked,
                http_status_code=status_code,
                details=healing_surface,
            )
        )
        if not heal_checked:
            return finalize(
                _fail(
                    report,
                    "operator_heal_after_real_agent_heartbeat",
                    {
                        "actual_status": status_code,
                        "healing_surface": healing_surface,
                        "raw_response_redacted": True,
                    },
                )
            )

        report["decision"] = READY_DECISION
        report["ready"] = True
        return finalize(report)
    except (OSError, subprocess.SubprocessError, TimeoutError, URLError) as exc:
        return finalize(
            _fail(
                report,
                "unexpected_runtime_error",
                {
                    "exception_type": exc.__class__.__name__,
                    "message": str(exc)[:500],
                },
            )
        )
    finally:
        if agent_proc is not None:
            _stop_process(agent_proc)
        if server_proc is not None:
            _stop_process(server_proc)
        _stop_local_tcp_listener(listener_sock, listener_stop, listener_thread)
        engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--work-dir",
        default="",
        help="Temporary verifier working directory. Defaults to a temp directory.",
    )
    parser.add_argument("--dataplane-probe-target", default="127.0.0.1")
    parser.add_argument(
        "--no-local-listener-target",
        action="store_false",
        dest="use_local_listener_target",
        help=(
            "Use the supplied dataplane probe target directly instead of a "
            "temporary local TCP listener."
        ),
    )
    parser.set_defaults(use_local_listener_target=True)
    parser.add_argument("--timeout-seconds", type=float, default=45.0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.work_dir:
        report = run_verification(
            work_dir=args.work_dir,
            dataplane_probe_target=args.dataplane_probe_target,
            timeout_seconds=args.timeout_seconds,
            use_local_listener_target=args.use_local_listener_target,
        )
    else:
        with tempfile.TemporaryDirectory(prefix="maas-real-agent-smoke-") as tmpdir:
            report = run_verification(
                work_dir=tmpdir,
                dataplane_probe_target=args.dataplane_probe_target,
                timeout_seconds=args.timeout_seconds,
                use_local_listener_target=args.use_local_listener_target,
            )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["ready"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
