"""Unit tests for scripts/vpn_status.sh JSON output."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import threading


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "vpn_status.sh"


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


class SocksProbeServer:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen()
        self.port = int(self._sock.getsockname()[1])
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        self._sock.settimeout(0.2)
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except TimeoutError:
                continue
            except OSError:
                break
            with conn:
                try:
                    conn.recv(3)
                    conn.sendall(b"\x05\x00")
                except OSError:
                    pass

    def close(self) -> None:
        self._stop.set()
        self._sock.close()
        self._thread.join(timeout=1)


def _make_fake_path(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir()

    _write_executable(
        bindir / "pgrep",
        "#!/bin/sh\nprintf '1234\\n'\n",
    )
    _write_executable(
        bindir / "ps",
        "#!/bin/sh\nprintf '10240\\n'\n",
    )
    _write_executable(
        bindir / "systemctl",
        "#!/bin/sh\nexit 0\n",
    )
    _write_executable(
        bindir / "journalctl",
        "#!/bin/sh\nprintf 'Network OK | latency=25.0ms | proxy=OK | FIN-WAIT-2=0\\n'\n",
    )
    _write_executable(
        bindir / "ip",
        """#!/bin/sh
case "$*" in
  "link show singbox_tun") exit 0 ;;
  "addr show singbox_tun") printf '    inet 172.18.0.1/30 scope global singbox_tun\\n' ;;
  route\\ get*)
    if [ "${VPN_STATUS_TEST_ROUTE_LOOP:-0}" = "1" ]; then
      printf '89.125.1.107 via 172.18.0.2 dev singbox_tun table 2022\\n'
    else
      printf '89.125.1.107 via 192.168.0.1 dev enp8s0 src 192.168.0.104\\n'
    fi
    ;;
esac
""",
    )
    _write_executable(
        bindir / "ss",
        """#!/bin/sh
if [ "$1" = "-tn" ]; then
  printf 'ESTAB 0 0 192.168.0.104:50000 89.125.1.107:39829\\n'
fi
""",
    )
    _write_executable(
        bindir / "curl",
        """#!/bin/sh
case "$*" in
  *9091*) printf 'vpn_heal_total 0\\nvpn_checks_total 12\\n' ;;
  *) printf '89.125.1.107' ;;
esac
""",
    )
    _write_executable(
        bindir / "ping",
        """#!/bin/sh
printf '5 packets transmitted, 5 received, 0%% packet loss, time 4004ms\\n'
printf 'rtt min/avg/max/mdev = 67.144/67.500/68.000/0.100 ms\\n'
""",
    )
    _write_executable(
        bindir / "cat",
        """#!/bin/sh
if [ "$1" = "/proc/sys/kernel/random/boot_id" ]; then
  printf 'test-boot-id\\n'
else
  /bin/cat "$@"
fi
""",
    )
    return bindir


def _run_json(tmp_path: Path, route_loop: bool = False) -> subprocess.CompletedProcess[str]:
    socks = SocksProbeServer()
    try:
        bindir = _make_fake_path(tmp_path)
        boot_result = tmp_path / "boot.last"
        boot_result.write_text(
            "status=PASS\nboot_id=test-boot-id\ntimestamp=2026-05-27T00:00:00Z\ndetail=test\n",
            encoding="utf-8",
        )
        env = {
            **os.environ,
            "PATH": f"{bindir}:{os.environ['PATH']}",
            "VPN_SOCKS_PORT": str(socks.port),
            "VPN_BOOT_VALIDATE_RESULT_FILE": str(boot_result),
            "VPN_STATUS_TEST_ROUTE_LOOP": "1" if route_loop else "0",
        }
        return subprocess.run(
            ["bash", str(SCRIPT), "--json"],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=20,
        )
    finally:
        socks.close()


def test_vpn_status_json_success(tmp_path: Path) -> None:
    proc = _run_json(tmp_path)
    assert proc.returncode == 0, proc.stderr

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "ok"
    assert payload["failure_domain"] == "none"
    assert payload["recommended_action"] == "observe"
    assert payload["mutation_allowed"] is False
    assert payload["nl_mutation_allowed"] is False
    assert payload["vpn_port"] == 39829
    assert payload["packet_loss_percent"] == 0


def test_vpn_status_json_route_loop_is_local_client_failure(tmp_path: Path) -> None:
    proc = _run_json(tmp_path, route_loop=True)
    assert proc.returncode == 1

    payload = json.loads(proc.stdout)
    assert payload["overall_status"] == "critical"
    assert payload["failure_domain"] == "local_client"
    assert payload["recommended_action"] == "local_soft_heal"
    assert any("Route loop risk" in problem for problem in payload["problems"])
