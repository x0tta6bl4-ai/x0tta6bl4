#!/usr/bin/env python3
"""Verify local Codex MCP, skills, and agent baseline wiring."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


ROOT = Path("/mnt/projects")
CODEX_HOME = Path(os.environ.get("CODEX_HOME", "/home/x0ttta6bl4/.codex")).resolve()
SKILLS_ROOT = CODEX_HOME / "skills"


STDIO_MCP_SERVERS = [
    {
        "name": "x0tta-operator",
        "command": "python3",
        "args": ["mcp-server/src/operator_tools.py"],
        "cwd": str(ROOT),
    },
    {
        "name": "spb-readonly",
        "command": "python3",
        "args": ["mcp-server/src/spb_readonly_tools.py"],
        "cwd": str(ROOT),
    },
    {
        "name": "context7",
        "command": "npx",
        "args": ["-y", "@upstash/context7-mcp"],
        "cwd": None,
    },
    {
        "name": "playwright",
        "command": "npx",
        "args": ["-y", "@playwright/mcp@latest", "--headless"],
        "cwd": None,
    },
    {
        "name": "chrome-devtools",
        "command": "npx",
        "args": ["-y", "chrome-devtools-mcp@latest"],
        "cwd": None,
    },
    {
        "name": "codegraph",
        "command": "codegraph",
        "args": ["serve", "--mcp", "--path", str(ROOT), "--no-watch"],
        "cwd": str(ROOT),
    },
    {
        "name": "github",
        "command": "scripts/mcp/github_mcp_stdio.sh",
        "args": [],
        "cwd": str(ROOT),
    },
]


def result(name: str, status: str, **extra: Any) -> dict[str, Any]:
    return {"name": name, "status": status, **extra}


async def check_stdio_mcp(server: dict[str, Any], timeout: int) -> dict[str, Any]:
    started = time.monotonic()
    try:
        params = StdioServerParameters(
            command=server["command"],
            args=server["args"],
            cwd=server.get("cwd"),
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await asyncio.wait_for(session.initialize(), timeout=timeout)
                tools = await asyncio.wait_for(session.list_tools(), timeout=timeout)
        return result(
            server["name"],
            "pass",
            elapsed_sec=round(time.monotonic() - started, 2),
            tool_count=len(tools.tools),
            sample_tools=[tool.name for tool in tools.tools[:8]],
        )
    except Exception as exc:  # noqa: BLE001 - verifier must report any startup failure.
        return result(
            server["name"],
            "fail",
            elapsed_sec=round(time.monotonic() - started, 2),
            error_type=type(exc).__name__,
            error=str(exc),
        )


def check_url_mcp(name: str, url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            return result(name, "pass", url=url, http_status=response.status)
    except urllib.error.HTTPError as exc:
        # Remote MCP endpoints often reject plain GET but are still reachable.
        status = "pass" if exc.code < 500 else "fail"
        return result(name, status, url=url, http_status=exc.code)
    except Exception as exc:  # noqa: BLE001
        return result(name, "fail", url=url, error_type=type(exc).__name__, error=str(exc))


async def check_mcp(timeout: int, skip_slow: bool) -> list[dict[str, Any]]:
    servers = STDIO_MCP_SERVERS
    if skip_slow:
        slow = {"context7", "playwright", "chrome-devtools"}
        servers = [server for server in servers if server["name"] not in slow]
    checks = [await check_stdio_mcp(server, timeout) for server in servers]

    checks.append(check_url_mcp("openaiDeveloperDocs", "https://developers.openai.com/mcp"))
    return checks


def real_skill_dirs() -> list[Path]:
    skills: list[Path] = []
    if SKILLS_ROOT.exists():
        skills.extend(
            path
            for path in sorted(SKILLS_ROOT.iterdir())
            if path.is_dir() and (path / "SKILL.md").exists()
        )
        system_root = SKILLS_ROOT / ".system"
        if system_root.exists():
            skills.extend(
                path
                for path in sorted(system_root.iterdir())
                if path.is_dir() and (path / "SKILL.md").exists()
            )
    return skills


def check_skills() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    skills = real_skill_dirs()
    checks.append(result("skills-count", "pass" if len(skills) >= 27 else "fail", count=len(skills)))

    try:
        import yaml  # type: ignore[import-not-found]
    except Exception as exc:  # noqa: BLE001
        checks.append(result("skills-openai-yaml", "fail", error=str(exc)))
    else:
        errors = []
        for skill in skills:
            yaml_path = skill / "agents" / "openai.yaml"
            try:
                payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if not isinstance(payload, dict):
                    errors.append(f"{yaml_path}: expected object")
            except Exception as exc:  # noqa: BLE001
                errors.append(f"{yaml_path}: {exc}")
        checks.append(result("skills-openai-yaml", "pass" if not errors else "fail", errors=errors))

    py_files: list[Path] = []
    for skill in skills:
        script_root = skill / "scripts"
        if not script_root.exists():
            continue
        for path in script_root.rglob("*.py"):
            if any(part in {"node_modules", ".venv", "__pycache__"} for part in path.parts):
                continue
            py_files.append(path)
    compile_result = subprocess.run(
        ["python3", "-m", "py_compile", *map(str, py_files)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    checks.append(
        result(
            "skills-python-scripts",
            "pass" if compile_result.returncode == 0 else "fail",
            count=len(py_files),
            stderr=compile_result.stderr[-4000:],
        )
    )
    return checks


def orphan_agent_pyc() -> list[str]:
    pycache = ROOT / "scripts" / "agents" / "__pycache__"
    if not pycache.exists():
        return []
    sources = {path.name for path in (ROOT / "scripts" / "agents").glob("*.py")}
    missing = []
    for pyc in pycache.glob("*.pyc"):
        source_name = pyc.name.split(".cpython-", 1)[0] + ".py"
        if source_name not in sources:
            missing.append(source_name)
    return sorted(set(missing))


def check_agents(run_smoke: bool) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    compile_result = subprocess.run(
        ["python3", "-m", "compileall", "-q", "scripts/agents"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    checks.append(
        result(
            "agents-compileall",
            "pass" if compile_result.returncode == 0 else "fail",
            stderr=compile_result.stderr[-4000:],
        )
    )
    orphans = orphan_agent_pyc()
    checks.append(result("agents-orphan-pyc", "pass" if not orphans else "fail", missing_sources=orphans))
    if run_smoke:
        smoke = subprocess.run(
            ["python3", "scripts/agents/test_all_agents.py"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
            timeout=120,
        )
        checks.append(
            result(
                "agents-smoke",
                "pass" if smoke.returncode == 0 else "fail",
                exit_code=smoke.returncode,
                stdout=smoke.stdout[-4000:],
                stderr=smoke.stderr[-2000:],
            )
        )
    return checks


def flatten(sections: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    return [check for checks in sections.values() for check in checks]


def print_human(payload: dict[str, Any]) -> None:
    print(f"status={payload['status']}")
    for section, checks in payload["sections"].items():
        print(f"\n[{section}]")
        for check in checks:
            detail = ""
            if "tool_count" in check:
                detail = f" tools={check['tool_count']}"
            elif "count" in check:
                detail = f" count={check['count']}"
            elif check.get("reason"):
                detail = f" reason={check['reason']}"
            print(f"- {check['status']} {check['name']}{detail}")


async def main_async(args: argparse.Namespace) -> int:
    sections = {
        "mcp": await check_mcp(args.mcp_timeout, args.skip_slow_mcp),
        "skills": check_skills(),
        "agents": check_agents(not args.skip_agent_smoke),
    }
    checks = flatten(sections)
    failed = [check for check in checks if check["status"] == "fail"]
    skipped = [check for check in checks if check["status"] == "skip"]
    strict_failed = skipped if args.strict else []
    payload = {
        "status": "fail" if failed or strict_failed else ("pass-with-skips" if skipped else "pass"),
        "failed": failed,
        "skipped": skipped,
        "strict_failed": strict_failed,
        "sections": sections,
    }
    if args.json:
        print(json.dumps(payload, indent=2, ensure_ascii=True))
    else:
        print_human(payload)
    return 0 if not failed and not strict_failed else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Print full JSON")
    parser.add_argument("--mcp-timeout", type=int, default=80, help="Per MCP initialize/list timeout")
    parser.add_argument("--skip-slow-mcp", action="store_true", help="Skip npx browser/documentation MCPs")
    parser.add_argument("--skip-agent-smoke", action="store_true", help="Skip scripts/agents/test_all_agents.py")
    parser.add_argument("--strict", action="store_true", help="Treat skipped checks as incomplete")
    return parser


def main() -> int:
    return asyncio.run(main_async(build_parser().parse_args()))


if __name__ == "__main__":
    raise SystemExit(main())
