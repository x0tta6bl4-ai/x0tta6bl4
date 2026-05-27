#!/usr/bin/env python3
from __future__ import annotations

import json
import logging
import subprocess
import time
from datetime import datetime
from pathlib import Path

STATE_DIR = Path("/opt/x0tta6bl4-mesh/state")
STATE_PATH = STATE_DIR / "runtime-state.json"
LOG_DIR = Path("/opt/x0tta6bl4-mesh/logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
ALERT_FILE = LOG_DIR / "alerts.json"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_DIR / "auto_monitor.log"), logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def run_runtime_state() -> dict:
    subprocess.run(
        ["python3", "/opt/x0tta6bl4-mesh/scripts/build_runtime_state.py"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def send_alert(level: str, message: str) -> None:
    alert = {"timestamp": datetime.now().isoformat(), "level": level, "message": message}
    alerts = []
    if ALERT_FILE.exists():
        try:
            alerts = json.loads(ALERT_FILE.read_text(encoding="utf-8"))
        except Exception:
            alerts = []
    alerts.append(alert)
    ALERT_FILE.write_text(json.dumps(alerts[-100:], ensure_ascii=False, indent=2), encoding="utf-8")
    if level == "CRITICAL":
        logger.error(message)
    elif level == "WARNING":
        logger.warning(message)
    else:
        logger.info(message)


def format_secondary_failures(state: dict) -> str:
    failures = state.get("probes", {}).get("secondary_listener_failures", [])
    chunks = []
    if failures:
        chunks.append("secondary_failures=" + ",".join(str(port) for port in failures))
    auxiliary = state.get("probes", {}).get("xui_auxiliary_listener_status", {})
    aux_failures = [port for port, ok in auxiliary.items() if not ok]
    if aux_failures:
        chunks.append("xui_aux_failures=" + ",".join(aux_failures))
    detector = state.get("probes", {}).get("listener_loss_detector", {})
    if detector.get("present"):
        detector_bits = [f"listener_detector_status={detector.get('status', 'unknown')}"]
        confidence = detector.get("confidence")
        if confidence is not None:
            detector_bits.append(f"confidence={confidence}")
        if detector.get("stale"):
            detector_bits.append("stale=true")
        chunks.append(" ".join(detector_bits))
    if not chunks:
        return ""
    return " " + " ".join(chunks)


def monitor_loop() -> None:
    logger.info("Запуск auto monitor в режиме runtime-state-first")
    while True:
        try:
            state = run_runtime_state()
            if not state:
                send_alert("WARNING", "runtime-state unavailable")
                time.sleep(60)
                continue

            mode = state.get("mode", "unknown")
            action = state.get("recommended_action", "observe")
            reason = state.get("reason", "-")
            suffix = format_secondary_failures(state)

            if mode == "fallback":
                send_alert("CRITICAL", f"VPN fallback active: {reason}{suffix}")
            elif mode == "degraded":
                send_alert("WARNING", f"VPN degraded: {reason}; action={action}{suffix}")
            elif mode == "anti_block":
                send_alert("INFO", f"VPN anti-block mode active: {reason}{suffix}")
            else:
                logger.info("VPN primary path healthy%s", suffix)

            time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Остановка мониторинга")
            break
        except Exception as exc:
            logger.error("Ошибка в цикле мониторинга: %s", exc)
            time.sleep(60)


if __name__ == "__main__":
    monitor_loop()
