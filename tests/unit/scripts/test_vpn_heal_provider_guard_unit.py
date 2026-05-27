"""Unit tests for scripts/vpn_heal.sh provider guard wiring."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "vpn_heal.sh"


def _write_fake_ss(path: Path, mutation_marker: Path) -> None:
    path.write_text(
        f"""#!/bin/sh
for arg in "$@"; do
  if [ "$arg" = "-K" ]; then
    echo mutation > "{mutation_marker}"
    exit 0
  fi
done
exit 0
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_fake_guard(path: Path, args_file: Path, *, block_only_when_require_fresh: bool = False) -> None:
    condition = '"--require-fresh" in sys.argv' if block_only_when_require_fresh else "True"
    path.write_text(
        f"""from __future__ import annotations

import json
import sys
from pathlib import Path

Path({str(args_file)!r}).write_text(json.dumps(sys.argv[1:]), encoding="utf-8")
if {condition}:
    print("BLOCK: stale_snapshot_age_seconds=9999")
    raise SystemExit(10)
print("ALLOW: ok")
""",
        encoding="utf-8",
    )


def _run_heal(
    tmp_path: Path,
    env_overrides: dict[str, str],
) -> tuple[subprocess.CompletedProcess[str], Path]:
    mutation_marker = tmp_path / "ss-k-called"
    fake_ss = tmp_path / "ss"
    _write_fake_ss(fake_ss, mutation_marker)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{tmp_path}:{env.get('PATH', '')}",
            "VPN_SERVER": "203.0.113.10",
            "VPN_SOCKS_HOST": "127.0.0.1",
            "VPN_SOCKS_PORT": "9",
        }
    )
    env.update(env_overrides)

    return (
        subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=ROOT,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=10,
        ),
        mutation_marker,
    )


def test_forced_heal_requires_fresh_snapshot_before_mutation(tmp_path: Path) -> None:
    guard_args_file = tmp_path / "guard-args.json"
    fake_guard = tmp_path / "provider_guard.py"
    _write_fake_guard(fake_guard, guard_args_file, block_only_when_require_fresh=True)

    result, mutation_marker = _run_heal(
        tmp_path,
        {
            "VPN_HEAL_FORCE": "1",
            "VPN_PROVIDER_GUARD_SCRIPT": str(fake_guard),
        },
    )

    guard_args = json.loads(guard_args_file.read_text(encoding="utf-8"))
    assert result.returncode == 3
    assert "--check" in guard_args
    assert "--require-fresh" in guard_args
    assert "Provider guard blocked local heal" in result.stdout
    assert not mutation_marker.exists()


def test_forced_heal_require_fresh_can_be_disabled_explicitly(tmp_path: Path) -> None:
    guard_args_file = tmp_path / "guard-args.json"
    fake_guard = tmp_path / "provider_guard.py"
    _write_fake_guard(fake_guard, guard_args_file)

    result, mutation_marker = _run_heal(
        tmp_path,
        {
            "VPN_HEAL_FORCE": "1",
            "VPN_HEAL_REQUIRE_FRESH_SNAPSHOT": "0",
            "VPN_PROVIDER_GUARD_SCRIPT": str(fake_guard),
        },
    )

    guard_args = json.loads(guard_args_file.read_text(encoding="utf-8"))
    assert result.returncode == 3
    assert "--check" in guard_args
    assert "--require-fresh" not in guard_args
    assert "Provider guard blocked local heal" in result.stdout
    assert not mutation_marker.exists()
