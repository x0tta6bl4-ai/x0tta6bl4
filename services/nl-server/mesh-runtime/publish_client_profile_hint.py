#!/usr/bin/env python3
from __future__ import annotations

import json
import time
from pathlib import Path

STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
RUNTIME_STATE_PATH = STATE_DIR / "runtime-state.json"
HINT_PATH = STATE_DIR / "client-profile-hint.json"


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def load_runtime_state() -> dict:
    if not RUNTIME_STATE_PATH.exists():
        return {}
    try:
        payload = json.loads(RUNTIME_STATE_PATH.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def choose_hint(state: dict) -> dict:
    probes = state.get("probes", {})
    listener_status = probes.get("public_listener_status", {})
    mode = state.get("mode", "unknown")

    available_public = [
        int(port)
        for port, ok in listener_status.items()
        if ok and port.isdigit()
    ]
    available_public = sorted(set(available_public))

    if mode == "fallback":
        return {
            "recommended_profile": "ghost-fallback",
            "transport_family": "ghostvpn",
            "candidate_ports": [4433, 4434],
            "reason": state.get("reason"),
        }

    if mode in {"anti_block", "degraded"}:
        candidates = [port for port in available_public if port != 443]
        if not candidates and 443 in available_public:
            candidates = [443]
        return {
            "recommended_profile": "anti-block-public-ingress",
            "transport_family": "xray-vless",
            "candidate_ports": candidates,
            "reason": state.get("reason"),
        }

    candidates = [443] if 443 in available_public else available_public
    return {
        "recommended_profile": "stable-primary",
        "transport_family": "xray-vless",
        "candidate_ports": candidates,
        "reason": state.get("reason"),
    }


def main() -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = load_runtime_state()
    hint = choose_hint(state)
    payload = {
        "generated_at": now_iso(),
        "source": "vps-client-profile-hint",
        "runtime_mode": state.get("mode"),
        "recommended_action": state.get("recommended_action"),
        **hint,
    }
    HINT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
