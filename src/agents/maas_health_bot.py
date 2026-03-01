"""Local-first health bot for MaaS Agent Mesh.

This bot intentionally avoids external AI providers and internet APIs.
It uses only local signals:
 - SOCKS port reachability (Xray/VLESS process health proxy signal)
 - local health URLs
 - local proxy log analysis (delay + connection abort markers)
"""

from __future__ import annotations

import os
import re
import shlex
import socket
import subprocess
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from urllib.parse import urlparse

import httpx


LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
ABORT_MARKERS = (
    "connection upload closed",
    "connection refused",
    "unexpected eof",
    "broken pipe",
)
DELAY_RE = re.compile(r"the delay:\s*(\d+)\s*ms", re.IGNORECASE)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_bool(value: str | None, default: bool) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class HealthBotConfig:
    socks_host: str
    socks_port: int
    socks_probe_timeout_seconds: float
    enable_socks_probe: bool
    proxy_log_path: str
    log_tail_lines: int
    max_delay_ms: int
    max_abort_events: int
    health_urls: list[str]
    health_timeout_seconds: float
    allow_external_urls: bool
    enable_execute: bool
    action_cooldown_seconds: int
    restart_xray_cmd: str
    reroute_cmd: str
    restart_control_plane_cmd: str
    history_size: int

    @classmethod
    def from_env(cls) -> "HealthBotConfig":
        raw_urls = os.getenv(
            "MAAS_HEALTH_BOT_HEALTH_URLS",
            "http://127.0.0.1:8000/health,http://127.0.0.1:8000/health/ready",
        )
        health_urls = [item.strip() for item in raw_urls.split(",") if item.strip()]
        return cls(
            socks_host=os.getenv("MAAS_HEALTH_BOT_SOCKS_HOST", "127.0.0.1"),
            socks_port=max(1, int(os.getenv("MAAS_HEALTH_BOT_SOCKS_PORT", "10808"))),
            socks_probe_timeout_seconds=max(
                0.1, float(os.getenv("MAAS_HEALTH_BOT_SOCKS_TIMEOUT_SECONDS", "1.0"))
            ),
            enable_socks_probe=_parse_bool(
                os.getenv("MAAS_HEALTH_BOT_ENABLE_SOCKS_PROBE"), True
            ),
            proxy_log_path=os.getenv("MAAS_HEALTH_BOT_PROXY_LOG", "/tmp/xray.log"),
            log_tail_lines=max(10, int(os.getenv("MAAS_HEALTH_BOT_LOG_TAIL_LINES", "500"))),
            max_delay_ms=max(1, int(os.getenv("MAAS_HEALTH_BOT_MAX_DELAY_MS", "250"))),
            max_abort_events=max(
                0, int(os.getenv("MAAS_HEALTH_BOT_MAX_ABORT_EVENTS", "5"))
            ),
            health_urls=health_urls,
            health_timeout_seconds=max(
                0.2, float(os.getenv("MAAS_HEALTH_BOT_HEALTH_TIMEOUT_SECONDS", "2.0"))
            ),
            allow_external_urls=_parse_bool(
                os.getenv("MAAS_HEALTH_BOT_ALLOW_EXTERNAL_URLS"), False
            ),
            enable_execute=_parse_bool(
                os.getenv("MAAS_HEALTH_BOT_ENABLE_EXECUTE"), False
            ),
            action_cooldown_seconds=max(
                0,
                int(os.getenv("MAAS_HEALTH_BOT_ACTION_COOLDOWN_SECONDS", "300")),
            ),
            restart_xray_cmd=os.getenv("MAAS_HEALTH_BOT_RESTART_XRAY_CMD", "").strip(),
            reroute_cmd=os.getenv("MAAS_HEALTH_BOT_REROUTE_CMD", "").strip(),
            restart_control_plane_cmd=os.getenv(
                "MAAS_HEALTH_BOT_RESTART_CONTROL_PLANE_CMD", ""
            ).strip(),
            history_size=max(10, int(os.getenv("MAAS_HEALTH_BOT_HISTORY_SIZE", "200"))),
        )


class MaasHealthBot:
    """Rule-based health bot with optional local self-heal commands."""

    def __init__(self, config: HealthBotConfig):
        self.config = config
        self._history: deque[dict[str, Any]] = deque(maxlen=config.history_size)
        self._lock = Lock()
        self._last_action_at: dict[str, float] = {}

    def _tail_log_lines(self) -> list[str]:
        path = Path(self.config.proxy_log_path)
        if not path.exists():
            return []
        try:
            lines = path.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError:
            return []
        return lines[-self.config.log_tail_lines :]

    def _probe_socks(self) -> dict[str, Any]:
        if not self.config.enable_socks_probe:
            return {
                "name": "socks_port_reachability",
                "status": "skip",
                "detail": "SOCKS probe disabled by config",
            }
        try:
            with socket.create_connection(
                (self.config.socks_host, self.config.socks_port),
                timeout=self.config.socks_probe_timeout_seconds,
            ):
                return {
                    "name": "socks_port_reachability",
                    "status": "ok",
                    "detail": f"{self.config.socks_host}:{self.config.socks_port} reachable",
                }
        except OSError as exc:
            return {
                "name": "socks_port_reachability",
                "status": "fail",
                "detail": f"{self.config.socks_host}:{self.config.socks_port} unreachable: {exc}",
            }

    def _probe_health_url(self, url: str) -> dict[str, Any]:
        host = (urlparse(url).hostname or "").strip().lower()
        if host and host not in LOCAL_HOSTS and not self.config.allow_external_urls:
            return {
                "name": f"health_url:{url}",
                "status": "skip",
                "detail": "external URLs are disabled (local-only mode)",
            }
        try:
            response = httpx.get(url, timeout=self.config.health_timeout_seconds)
            if response.status_code >= 500:
                return {
                    "name": f"health_url:{url}",
                    "status": "fail",
                    "detail": f"HTTP {response.status_code}",
                }
            return {
                "name": f"health_url:{url}",
                "status": "ok",
                "detail": f"HTTP {response.status_code}",
            }
        except Exception as exc:
            return {
                "name": f"health_url:{url}",
                "status": "fail",
                "detail": f"request error: {exc}",
            }

    def _analyze_proxy_log(self) -> list[dict[str, Any]]:
        lines = self._tail_log_lines()
        if not lines:
            return [
                {
                    "name": "proxy_log_presence",
                    "status": "warn",
                    "detail": f"log not found or unreadable: {self.config.proxy_log_path}",
                }
            ]

        lower_lines = [line.lower() for line in lines]
        abort_events = sum(
            1
            for line in lower_lines
            if any(marker in line for marker in ABORT_MARKERS)
        )
        abort_status = "ok" if abort_events <= self.config.max_abort_events else "fail"

        latest_delay_ms: int | None = None
        for line in reversed(lines):
            match = DELAY_RE.search(line)
            if match:
                latest_delay_ms = int(match.group(1))
                break

        delay_signal: dict[str, Any]
        if latest_delay_ms is None:
            delay_signal = {
                "name": "proxy_delay_ms",
                "status": "warn",
                "detail": "no delay metric found in recent logs",
                "value": None,
                "threshold_max": self.config.max_delay_ms,
            }
        else:
            delay_signal = {
                "name": "proxy_delay_ms",
                "status": "ok" if latest_delay_ms <= self.config.max_delay_ms else "fail",
                "detail": f"latest delay={latest_delay_ms}ms",
                "value": latest_delay_ms,
                "threshold_max": self.config.max_delay_ms,
            }

        return [
            {
                "name": "proxy_abort_events",
                "status": abort_status,
                "detail": f"{abort_events} abort-like events in last {len(lines)} log lines",
                "value": abort_events,
                "threshold_max": self.config.max_abort_events,
            },
            delay_signal,
        ]

    def _proposed_actions(self, signals: list[dict[str, Any]]) -> list[dict[str, str]]:
        failing = {item["name"] for item in signals if item.get("status") == "fail"}
        actions: list[dict[str, str]] = []
        if "socks_port_reachability" in failing or "proxy_abort_events" in failing:
            actions.append(
                {
                    "id": "restart_xray",
                    "reason": "proxy path degraded (SOCKS unreachable or high abort events)",
                }
            )
        if "proxy_delay_ms" in failing:
            actions.append(
                {
                    "id": "mesh_reroute",
                    "reason": "proxy delay exceeded threshold",
                }
            )
        if any(name.startswith("health_url:") for name in failing):
            actions.append(
                {
                    "id": "restart_control_plane",
                    "reason": "local API health endpoint returned failures",
                }
            )
        return actions

    def _command_for_action(self, action_id: str) -> str:
        if action_id == "restart_xray":
            return self.config.restart_xray_cmd
        if action_id == "mesh_reroute":
            return self.config.reroute_cmd
        if action_id == "restart_control_plane":
            return self.config.restart_control_plane_cmd
        return ""

    def _execute_action(
        self, action_id: str, *, dry_run: bool, reason: str
    ) -> dict[str, Any]:
        command = self._command_for_action(action_id)
        report: dict[str, Any] = {
            "id": action_id,
            "reason": reason,
            "command": command or None,
            "attempted": False,
            "success": False,
            "detail": "",
        }
        if not command:
            report["detail"] = "no command configured"
            return report
        if dry_run:
            report["detail"] = "dry-run mode; command not executed"
            return report
        if not self.config.enable_execute:
            report["detail"] = (
                "execute disabled by config (set MAAS_HEALTH_BOT_ENABLE_EXECUTE=true)"
            )
            return report

        cooldown_left = self._cooldown_left_seconds(action_id)
        if cooldown_left > 0:
            report["detail"] = (
                f"action cooldown active ({cooldown_left}s remaining of "
                f"{self.config.action_cooldown_seconds}s)"
            )
            return report

        report["attempted"] = True
        self._mark_action_attempt(action_id)
        try:
            completed = subprocess.run(
                shlex.split(command),
                capture_output=True,
                text=True,
                timeout=20,
                check=False,
            )
            report["success"] = completed.returncode == 0
            output = (completed.stdout or completed.stderr or "").strip()
            report["detail"] = output[:300] if output else f"exit={completed.returncode}"
        except Exception as exc:
            report["detail"] = f"execution error: {exc}"
        return report

    def _cooldown_left_seconds(self, action_id: str) -> int:
        cooldown = self.config.action_cooldown_seconds
        if cooldown <= 0:
            return 0
        with self._lock:
            last = self._last_action_at.get(action_id)
        if last is None:
            return 0
        elapsed = time.monotonic() - last
        if elapsed >= cooldown:
            return 0
        return int(cooldown - elapsed) + 1

    def _mark_action_attempt(self, action_id: str) -> None:
        with self._lock:
            self._last_action_at[action_id] = time.monotonic()

    def run_once(self, *, auto_heal: bool, dry_run: bool) -> dict[str, Any]:
        signals: list[dict[str, Any]] = []
        signals.append(self._probe_socks())
        signals.extend(self._analyze_proxy_log())
        for url in self.config.health_urls:
            signals.append(self._probe_health_url(url))

        failing = [item for item in signals if item.get("status") == "fail"]
        status = "healthy" if not failing else "degraded"
        proposed = self._proposed_actions(signals)

        executed_actions: list[dict[str, Any]] = []
        if auto_heal and proposed:
            for action in proposed:
                executed_actions.append(
                    self._execute_action(
                        action["id"], dry_run=dry_run, reason=action["reason"]
                    )
                )

        report: dict[str, Any] = {
            "timestamp": _utc_now(),
            "engine": "local-rule-engine",
            "external_ai_providers_used": False,
            "status": status,
            "signals": signals,
            "auto_heal": auto_heal,
            "dry_run": dry_run,
            "proposed_actions": proposed,
            "executed_actions": executed_actions,
        }
        with self._lock:
            self._history.append(report)
        return report

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        limit = max(1, limit)
        with self._lock:
            items = list(self._history)
        return items[-limit:][::-1]
