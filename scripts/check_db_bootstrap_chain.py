#!/usr/bin/env python3
"""Fail-closed DB bootstrap chain check for SQLite and PostgreSQL."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


REPO_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_CONFIG = REPO_ROOT / "alembic.ini"
SCHEMA_PARITY_SCRIPT = REPO_ROOT / "scripts" / "check_orm_schema_parity.py"


def _quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _generate_temp_db_name(prefix: str = "maas_bootstrap") -> str:
    timestamp = int(time.time())
    entropy = uuid.uuid4().hex[:8]
    return f"{prefix}_{timestamp}_{os.getpid()}_{entropy}".lower()


def _run_command(name: str, command: list[str], *, env: dict[str, str], timeout: int) -> None:
    proc = subprocess.run(
        command,
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    if proc.returncode == 0:
        return

    stderr = proc.stderr.strip()
    stdout = proc.stdout.strip()
    details = "\n".join(item for item in [stdout, stderr] if item)
    detail_suffix = f"\n{details}" if details else ""
    raise RuntimeError(f"{name} failed with exit code {proc.returncode}{detail_suffix}")


def _run_bootstrap_for_database(
    database_url: str,
    *,
    label: str,
    timeout: int,
    validate_downgrade: bool = False,
    downgrade_steps: int = 1,
) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = database_url

    _run_command(
        f"{label}: alembic upgrade head",
        ["alembic", "-c", str(ALEMBIC_CONFIG), "upgrade", "head"],
        env=env,
        timeout=timeout,
    )
    _run_command(
        f"{label}: schema parity",
        [sys.executable, str(SCHEMA_PARITY_SCRIPT)],
        env=env,
        timeout=timeout,
    )
    if not validate_downgrade:
        return

    steps = max(1, int(downgrade_steps))
    for step in range(1, steps + 1):
        downgrade_target = f"-{step}"
        _run_command(
            f"{label}: alembic downgrade {downgrade_target}",
            ["alembic", "-c", str(ALEMBIC_CONFIG), "downgrade", downgrade_target],
            env=env,
            timeout=timeout,
        )
        _run_command(
            f"{label}: alembic re-upgrade head (from {downgrade_target})",
            ["alembic", "-c", str(ALEMBIC_CONFIG), "upgrade", "head"],
            env=env,
            timeout=timeout,
        )
        _run_command(
            f"{label}: schema parity after roundtrip {downgrade_target}",
            [sys.executable, str(SCHEMA_PARITY_SCRIPT)],
            env=env,
            timeout=timeout,
        )


def run_sqlite_bootstrap(
    *,
    timeout: int,
    validate_downgrade: bool = False,
    downgrade_steps: int = 1,
) -> None:
    with tempfile.NamedTemporaryFile(prefix="maas_bootstrap_", suffix=".db", delete=False) as tmp_file:
        db_path = Path(tmp_file.name)

    db_url = f"sqlite:///{db_path}"
    try:
        _run_bootstrap_for_database(
            db_url,
            label="sqlite",
            timeout=timeout,
            validate_downgrade=validate_downgrade,
            downgrade_steps=downgrade_steps,
        )
    finally:
        for suffix in ("", "-journal", "-wal", "-shm"):
            target = Path(f"{db_path}{suffix}")
            if target.exists():
                target.unlink()


def _build_postgres_urls(postgres_url: str, temp_db_name: str) -> tuple[URL, URL]:
    parsed = make_url(postgres_url)
    if not parsed.drivername.startswith("postgresql"):
        raise ValueError("--postgres-url must use a postgresql:// DSN")

    admin_database = parsed.database or "postgres"
    admin_url = parsed.set(database=admin_database)
    temp_db_url = parsed.set(database=temp_db_name)
    return admin_url, temp_db_url


def run_postgres_bootstrap(
    postgres_url: str,
    *,
    timeout: int,
    validate_downgrade: bool = False,
    downgrade_steps: int = 1,
) -> None:
    temp_db_name = _generate_temp_db_name()
    admin_url, temp_db_url = _build_postgres_urls(postgres_url, temp_db_name)
    quoted_db = _quote_ident(temp_db_name)

    admin_engine = create_engine(
        admin_url.render_as_string(hide_password=False),
        isolation_level="AUTOCOMMIT",
        pool_pre_ping=True,
    )

    try:
        with admin_engine.connect() as conn:
            conn.execute(text(f"CREATE DATABASE {quoted_db}"))

        _run_bootstrap_for_database(
            temp_db_url.render_as_string(hide_password=False),
            label="postgresql",
            timeout=timeout,
            validate_downgrade=validate_downgrade,
            downgrade_steps=downgrade_steps,
        )
    finally:
        try:
            with admin_engine.connect() as conn:
                conn.execute(
                    text(
                        "SELECT pg_terminate_backend(pid) "
                        "FROM pg_stat_activity "
                        "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                    ),
                    {"database_name": temp_db_name},
                )
                conn.execute(text(f"DROP DATABASE IF EXISTS {quoted_db}"))
        finally:
            admin_engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--postgres-url",
        default=os.getenv("POSTGRES_BOOTSTRAP_DATABASE_URL", ""),
        help="Admin PostgreSQL DSN used to create an ephemeral test database",
    )
    parser.add_argument(
        "--require-postgres",
        action="store_true",
        help="Fail when --postgres-url/POSTGRES_BOOTSTRAP_DATABASE_URL is not provided",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=max(60, int(os.getenv("ALEMBIC_TIMEOUT_SECONDS", "300"))),
        help="Timeout for each alembic/parity command",
    )
    parser.add_argument(
        "--validate-downgrade",
        action="store_true",
        help="Validate migration roundtrip with `alembic downgrade -N` then `upgrade head`",
    )
    parser.add_argument(
        "--downgrade-steps",
        type=int,
        default=max(1, int(os.getenv("DB_BOOTSTRAP_DOWNGRADE_STEPS", "1"))),
        help="Number of revisions for downgrade roundtrip when --validate-downgrade is enabled",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    timeout = max(1, int(args.timeout_seconds))
    downgrade_steps = max(1, int(args.downgrade_steps))
    validate_downgrade = bool(args.validate_downgrade)

    failures: list[str] = []

    print("[db-bootstrap] Checking clean SQLite bootstrap chain...")
    try:
        run_sqlite_bootstrap(
            timeout=timeout,
            validate_downgrade=validate_downgrade,
            downgrade_steps=downgrade_steps,
        )
        print("[db-bootstrap] SQLite bootstrap chain: OK")
    except Exception as exc:
        failures.append(f"sqlite: {exc}")
        print(f"[db-bootstrap] SQLite bootstrap chain: FAIL ({exc})")

    postgres_url = (args.postgres_url or "").strip()
    if postgres_url:
        print("[db-bootstrap] Checking clean PostgreSQL bootstrap chain...")
        try:
            run_postgres_bootstrap(
                postgres_url,
                timeout=timeout,
                validate_downgrade=validate_downgrade,
                downgrade_steps=downgrade_steps,
            )
            print("[db-bootstrap] PostgreSQL bootstrap chain: OK")
        except Exception as exc:
            failures.append(f"postgresql: {exc}")
            print(f"[db-bootstrap] PostgreSQL bootstrap chain: FAIL ({exc})")
    elif args.require_postgres:
        failures.append("postgresql: missing --postgres-url/POSTGRES_BOOTSTRAP_DATABASE_URL")
        print("[db-bootstrap] PostgreSQL bootstrap chain: FAIL (URL is required but missing)")
    else:
        print(
            "[db-bootstrap] PostgreSQL bootstrap chain: SKIP "
            "(set POSTGRES_BOOTSTRAP_DATABASE_URL to enable)"
        )

    if failures:
        print("[db-bootstrap] FAILED")
        for item in failures:
            print(f" - {item}")
        return 1

    print("[db-bootstrap] PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
