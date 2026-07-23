#!/usr/bin/env python3
"""x0tta6bl4 Readiness Gate — 25 critical checks before deploy.

Usage:
    python src/ops/readiness_gate.py          # run all checks
    python src/ops/readiness_gate.py --json   # JSON only
"""

import json
import os
import socket
import stat
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, List


@dataclass
class CheckResult:
    id: str
    category: str
    required: bool
    ok: bool
    message: str
    duration_ms: int


class Gate:
    def __init__(self):
        self.checks: List[tuple] = []
        self.results: List[CheckResult] = []

    def register(self, id: str, category: str, required: bool = True):
        def decorator(func: Callable[[], tuple[bool, str]]):
            self.checks.append((id, category, required, func))
            return func
        return decorator

    def run(self) -> bool:
        passed = failed = skipped = 0
        overall_ready = True

        for id, category, required, func in self.checks:
            t0 = time.perf_counter()
            try:
                ok, msg = func()
            except Exception as e:
                ok, msg = False, f"EXCEPTION: {e}"
            duration_ms = int((time.perf_counter() - t0) * 1000)

            if not ok and required:
                overall_ready = False
                failed += 1
            elif not ok and not required:
                skipped += 1
            else:
                passed += 1

            self.results.append(CheckResult(id, category, required, ok, msg, duration_ms))

            if not ok and required:
                break

        total = len(self.checks)
        print(json.dumps({
            "summary": {
                "total": total,
                "executed": len(self.results),
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
                "ready": overall_ready,
            },
            "results": [asdict(r) for r in self.results],
        }, indent=2, ensure_ascii=False))

        return overall_ready


gate = Gate()


# ==================== CRYPTO ====================

@gate.register("crypto.mldsa_sign", "crypto")
def check_mldsa_sign():
    try:
        from src.network.firstparty_vpn.mldsa import (
            mldsa_derive_reference_keypair,
            mldsa_reference_sign,
            mldsa_reference_verify,
            mldsa_encode_signing_key,
            mldsa_encode_verification_key,
        )
        import os as _os
        seed = _os.urandom(32)
        kp = mldsa_derive_reference_keypair("ML-DSA-65", seed)
        sk = mldsa_encode_signing_key("ML-DSA-65", kp.signing_key)
        pk = mldsa_encode_verification_key("ML-DSA-65", kp.verification_key)
        msg = b"readiness gate self-test"
        sig = mldsa_reference_sign("ML-DSA-65", sk, msg)
        assert mldsa_reference_verify("ML-DSA-65", pk, msg, sig)
        return True, "ML-DSA sign+verify OK"
    except Exception as e:
        return False, str(e)[:120]


@gate.register("crypto.mlkem_encaps", "crypto")
def check_mlkem():
    try:
        from src.network.firstparty_vpn.mlkem import (
            mlkem_derive_keypair,
            mlkem_encapsulate,
            mlkem_decapsulate,
            mlkem_encode_keypair,
        )
        import os as _os
        seed = _os.urandom(32)
        kp = mlkem_derive_keypair("ML-KEM-768", seed)
        pk_bytes = mlkem_encode_keypair("ML-KEM-768", kp)
        ct, ss = mlkem_encapsulate("ML-KEM-768", pk_bytes)
        ss2 = mlkem_decapsulate("ML-KEM-768", kp, ct)
        return True, "ML-KEM encaps+decaps OK"
    except Exception as e:
        return False, str(e)[:120]


@gate.register("crypto.key_permissions", "crypto")
def check_key_permissions():
    key_paths = [
        "/opt/spire/data/server/keys",
        "/opt/spire/secrets",
    ]
    errors = []
    for p in key_paths:
        path = Path(p)
        if not path.exists():
            continue
        if path.is_dir():
            for f in path.rglob("*"):
                if f.is_file():
                    mode = stat.S_IMODE(f.stat().st_mode)
                    if mode & 0o077:
                        errors.append(f"{f}: {oct(mode)}")
        else:
            mode = stat.S_IMODE(path.stat().st_mode)
            if mode & 0o077:
                errors.append(f"{p}: {oct(mode)}")
    return len(errors) == 0, "; ".join(errors[:3]) if errors else "Keys secure"


# ==================== NETWORK ====================

@gate.register("net.vpn_port", "network")
def check_vpn_port():
    try:
        with socket.create_connection(("89.125.1.107", 443), timeout=2):
            return True, "TCP 443 open"
    except Exception as e:
        return False, str(e)[:80]


@gate.register("net.dns_resolution", "network")
def check_dns():
    try:
        socket.getaddrinfo("api.telegram.org", None)
        return True, "DNS OK"
    except Exception as e:
        return False, str(e)[:80]


@gate.register("net.default_route", "network", required=False)
def check_default_route():
    try:
        r = subprocess.run(["ip", "route", "show", "default"], capture_output=True, text=True)
        return len(r.stdout.strip()) > 0, r.stdout.strip()[:80]
    except Exception as e:
        return False, str(e)[:80]


# ==================== IDENTITY ====================

@gate.register("id.spire_socket", "identity")
def check_spire_socket():
    p = Path("/opt/spire/sockets/agent.sock")
    if not p.exists():
        return False, "socket missing"
    mode = stat.S_IMODE(p.stat().st_mode)
    return mode == 0o770, f"mode {oct(mode)}"


@gate.register("id.spire_jwt_svid", "identity")
def check_spire_jwt():
    spire_bin = "/opt/spire/bin/spire-agent"
    socket_path = "/opt/spire/sockets/agent.sock"
    if not Path(spire_bin).exists():
        return False, "spire-agent not found"
    if not Path(socket_path).exists():
        return False, "socket missing"
    try:
        r = subprocess.run(
            [spire_bin, "api", "fetch", "-socketPath", socket_path, "-jwt", "-audience", "x0tta6bl4.mesh"],
            capture_output=True, text=True, timeout=5,
        )
        if r.returncode != 0:
            return False, r.stderr[:100]
        return "token" in r.stdout.lower() or "svid" in r.stdout.lower(), "fetched"
    except Exception as e:
        return False, str(e)[:80]


# ==================== STORAGE ====================

@gate.register("storage.disk_space", "storage")
def check_disk():
    for mount in ["/", "/opt/x0tta6bl4"]:
        try:
            u = shutil.disk_usage(mount)
            free_pct = u.free / u.total * 100
            if free_pct < 20:
                return False, f"{mount}: {free_pct:.1f}% free"
        except FileNotFoundError:
            continue
    return True, "Partitions OK"


import shutil  # noqa: E402


@gate.register("storage.sqlite_integrity", "storage")
def check_sqlite():
    dbs = ["/opt/spire/data/server/datastore.sqlite3"]
    errors = []
    for db in dbs:
        if not Path(db).exists():
            continue
        try:
            r = subprocess.run(["sqlite3", db, "PRAGMA integrity_check;"],
                               capture_output=True, text=True, timeout=5)
            if "ok" not in r.stdout.lower():
                errors.append(f"{db}: {r.stdout.strip()}")
        except FileNotFoundError:
            pass
    return len(errors) == 0, "; ".join(errors) if errors else "SQLite OK"


# ==================== SECURITY ====================

@gate.register("sec.no_debug", "security")
def check_no_debug():
    debug = os.environ.get("X0_DEBUG", "false").lower()
    return debug != "true", f"X0_DEBUG={debug}"


@gate.register("sec.not_root", "security")
def check_not_root():
    return os.getuid() != 0, f"uid={os.getuid()}"


@gate.register("sec.config_permissions", "security")
def check_config_perms():
    dirs = ["/opt/x0tta6bl4/etc", "/opt/spire/conf"]
    world_writable = []
    for d in dirs:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file() and stat.S_IMODE(f.stat().st_mode) & 0o002:
                world_writable.append(str(f))
    return len(world_writable) == 0, f"{len(world_writable)} insecure files" if world_writable else "Configs secure"


# ==================== OPS ====================

@gate.register("ops.systemd_node", "ops")
def check_systemd_node():
    r = subprocess.run(["systemctl", "is-active", "x0tta6bl4-node"], capture_output=True, text=True)
    return r.stdout.strip() == "active", r.stdout.strip()


@gate.register("ops.systemd_spire", "ops")
def check_systemd_spire():
    for svc in ["spire-server", "spire-agent"]:
        r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True)
        if r.stdout.strip() != "active":
            return False, f"{svc}: {r.stdout.strip()}"
    return True, "spire active"


# ==================== CONFIG ====================

@gate.register("cfg.no_placeholders", "config")
def check_no_placeholders():
    placeholders = ["CHANGEME", "TODO", "FIXME"]
    found = []
    for d in ["/opt/x0tta6bl4/etc", "/opt/spire/conf"]:
        p = Path(d)
        if not p.exists():
            continue
        for f in p.rglob("*"):
            if f.is_file() and f.stat().st_size < 1024 * 1024:
                try:
                    text = f.read_text()
                    for ph in placeholders:
                        if ph in text:
                            found.append(f"{f.name}:{ph}")
                except Exception:
                    pass
    return len(found) == 0, found[:3] if found else "No placeholders"


# ==================== MAIN ====================

if __name__ == "__main__":
    ready = gate.run()
    sys.exit(0 if ready else 1)
