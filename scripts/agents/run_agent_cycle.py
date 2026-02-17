#!/usr/bin/env python3
"""Parallel multi-agent execution cycle with skill-aware context generation."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import shlex
import textwrap
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List


@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    role: str
    skill_name: str
    skill_path: str
    role_file: str | None
    command: str
    critical: bool = True


@dataclass
class AgentResult:
    agent_id: str
    role: str
    skill_name: str
    command: str
    started_at: str
    finished_at: str
    duration_sec: float
    return_code: int
    timed_out: bool
    stdout_log: str
    stderr_log: str

    @property
    def success(self) -> bool:
        return self.return_code == 0 and not self.timed_out


DEFAULT_PROFILES: Dict[str, AgentProfile] = {
    "agent-1": AgentProfile(
        agent_id="agent-1",
        role="architect",
        skill_name="x0tta6bl4-mesh-orchestrator",
        skill_path="skills/x0tta6bl4-mesh-orchestrator/SKILL.md",
        role_file="ai/roles/architect.md",
        command=(
            "python3 -m pytest -q "
            "tests/unit/core/test_app_endpoints.py "
            "tests/unit/core/test_demo_api_unit.py"
        ),
        critical=True,
    ),
    "agent-2": AgentProfile(
        agent_id="agent-2",
        role="security",
        skill_name="security-audit",
        skill_path="skills/security-audit/SKILL.md",
        role_file=None,
        command="python3 skills/security-audit/scripts/check_crypto.py",
        critical=False,
    ),
    "agent-3": AgentProfile(
        agent_id="agent-3",
        role="network",
        skill_name="deploy-mesh-node",
        skill_path="skills/deploy-mesh-node/SKILL.md",
        role_file=None,
        command=(
            "python3 -m pytest -q "
            "tests/unit/network/routing/test_mesh_router_unit.py "
            "tests/unit/network/test_mesh_routing_unit.py "
            "tests/network/test_mesh_router.py"
        ),
        critical=True,
    ),
    "agent-4": AgentProfile(
        agent_id="agent-4",
        role="quality",
        skill_name="test-coverage-boost",
        skill_path="skills/test-coverage-boost/SKILL.md",
        role_file="ai/roles/ops.md",
        command="python3 skills/test-coverage-boost/scripts/coverage_gaps.py",
        critical=True,
    ),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run x0tta6bl4 four-agent cycle in parallel with skill mapping.",
    )
    parser.add_argument(
        "--agents",
        default="agent-1,agent-2,agent-3,agent-4",
        help="Comma-separated list of agents to run (default: all).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=900,
        help="Timeout in seconds per agent command (default: 900).",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        help="Maximum parallel agent processes (default: 4).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail cycle on any agent failure (including advisory security checks).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print selected commands and write context files without executing commands.",
    )
    parser.add_argument(
        "--output-root",
        default=".tmp/agent_runs",
        help="Directory for run artifacts (default: .tmp/agent_runs).",
    )
    parser.add_argument(
        "--profile-file",
        default="scripts/agents/agent_cycle_profiles.json",
        help=(
            "JSON file with agent profiles. "
            "If missing, built-in defaults are used."
        ),
    )
    parser.add_argument(
        "--skip-contexts",
        action="store_true",
        help="Do not generate context files for each agent.",
    )
    parser.add_argument(
        "--sync-paradox-log",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Append START/HB/END entries to paradox log (default: enabled).",
    )
    parser.add_argument(
        "--paradox-log",
        default=".paradox.log",
        help="Path to paradox communication log (default: .paradox.log).",
    )
    return parser.parse_args()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def paradox_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_text_limited(path: Path, max_chars: int = 25000) -> str:
    if not path.exists():
        return f"[missing] {path}"
    data = path.read_text(encoding="utf-8", errors="ignore")
    if len(data) <= max_chars:
        return data
    return data[:max_chars] + "\n\n[...truncated...]\n"


def extract_pending_tasks(action_plan_path: Path) -> str:
    if not action_plan_path.exists():
        return "[missing] ACTION_PLAN_NOW.md"
    pending: List[str] = []
    for line in action_plan_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip().startswith("- [ ]"):
            pending.append(line.strip())
    if not pending:
        return "(no pending checkbox tasks found)"
    return "\n".join(pending[:120])


def build_context(project_root: Path, profile: AgentProfile) -> str:
    role_file_path = project_root / profile.role_file if profile.role_file else None
    skill_path = project_root / profile.skill_path
    sync_path = project_root / "AGENT_SYNC_INSTRUCTIONS.md"
    action_plan_path = project_root / "ACTION_PLAN_NOW.md"

    role_block = (
        read_text_limited(role_file_path, 14000)
        if role_file_path is not None
        else "[role file not configured for this agent role]"
    )
    skill_block = read_text_limited(skill_path, 18000)
    sync_block = read_text_limited(sync_path, 12000)
    pending = extract_pending_tasks(action_plan_path)

    return textwrap.dedent(
        f"""\
        # Agent Runtime Context
        agent_id: {profile.agent_id}
        role: {profile.role}
        skill: {profile.skill_name}
        command: {profile.command}

        ## Pending Sprint Tasks
        {pending}

        ## Sync Instructions (excerpt)
        {sync_block}

        ## Skill Instructions
        {skill_block}

        ## Role Profile
        {role_block}
        """
    )


def load_profiles(project_root: Path, profile_file: str) -> Dict[str, AgentProfile]:
    file_path = project_root / profile_file
    if not file_path.exists():
        return DEFAULT_PROFILES

    raw = json.loads(file_path.read_text(encoding="utf-8"))
    profiles: Dict[str, AgentProfile] = {}
    for item in raw.get("profiles", []):
        profile = AgentProfile(
            agent_id=item["agent_id"],
            role=item["role"],
            skill_name=item["skill_name"],
            skill_path=item["skill_path"],
            role_file=item.get("role_file"),
            command=item["command"],
            critical=bool(item.get("critical", True)),
        )
        profiles[profile.agent_id] = profile

    if not profiles:
        return DEFAULT_PROFILES
    return profiles


def resolve_agents(raw: str, profiles: Dict[str, AgentProfile]) -> List[AgentProfile]:
    agent_ids = [item.strip() for item in raw.split(",") if item.strip()]
    unknown = [agent_id for agent_id in agent_ids if agent_id not in profiles]
    if unknown:
        raise SystemExit(f"Unknown agent ids: {', '.join(unknown)}")
    return [profiles[agent_id] for agent_id in agent_ids]


def ensure_dirs(run_dir: Path, with_contexts: bool) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    if with_contexts:
        (run_dir / "contexts").mkdir(parents=True, exist_ok=True)
    (run_dir / "logs").mkdir(parents=True, exist_ok=True)


def append_paradox_line(log_path: Path, actor: str, message: str) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    line = f"[{paradox_ts()}] {actor}: {message}\n"
    with log_path.open("a", encoding="utf-8") as f:
        f.write(line)


async def run_agent_command(
    profile: AgentProfile,
    project_root: Path,
    run_dir: Path,
    timeout: int,
    dry_run: bool,
) -> AgentResult:
    started = utc_now()
    t0 = time.monotonic()
    stdout_path = run_dir / "logs" / f"{profile.agent_id}.stdout.log"
    stderr_path = run_dir / "logs" / f"{profile.agent_id}.stderr.log"

    if dry_run:
        stdout_path.write_text(
            f"[dry-run] command not executed\n{profile.command}\n",
            encoding="utf-8",
        )
        stderr_path.write_text("", encoding="utf-8")
        finished = utc_now()
        return AgentResult(
            agent_id=profile.agent_id,
            role=profile.role,
            skill_name=profile.skill_name,
            command=profile.command,
            started_at=started,
            finished_at=finished,
            duration_sec=0.0,
            return_code=0,
            timed_out=False,
            stdout_log=str(stdout_path.relative_to(project_root)),
            stderr_log=str(stderr_path.relative_to(project_root)),
        )

    proc = await asyncio.create_subprocess_exec(
        *shlex.split(profile.command),
        cwd=str(project_root),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    timed_out = False
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return_code = proc.returncode
    except asyncio.TimeoutError:
        timed_out = True
        proc.kill()
        stdout_raw, stderr_raw = await proc.communicate()
        return_code = -9

    stdout_text = stdout_raw.decode("utf-8", errors="replace")
    stderr_text = stderr_raw.decode("utf-8", errors="replace")

    stdout_path.write_text(stdout_text, encoding="utf-8")
    stderr_path.write_text(stderr_text, encoding="utf-8")

    finished = utc_now()
    return AgentResult(
        agent_id=profile.agent_id,
        role=profile.role,
        skill_name=profile.skill_name,
        command=profile.command,
        started_at=started,
        finished_at=finished,
        duration_sec=round(time.monotonic() - t0, 3),
        return_code=return_code,
        timed_out=timed_out,
        stdout_log=str(stdout_path.relative_to(project_root)),
        stderr_log=str(stderr_path.relative_to(project_root)),
    )


async def run_all(
    profiles: List[AgentProfile],
    project_root: Path,
    run_dir: Path,
    timeout: int,
    max_parallel: int,
    dry_run: bool,
) -> List[AgentResult]:
    sem = asyncio.Semaphore(max_parallel)

    async def _wrapped(profile: AgentProfile) -> AgentResult:
        async with sem:
            return await run_agent_command(
                profile=profile,
                project_root=project_root,
                run_dir=run_dir,
                timeout=timeout,
                dry_run=dry_run,
            )

    tasks = [_wrapped(profile) for profile in profiles]
    return await asyncio.gather(*tasks)


def write_summary(
    project_root: Path,
    run_dir: Path,
    profiles: List[AgentProfile],
    results: List[AgentResult],
    strict: bool,
    dry_run: bool,
) -> int:
    profile_map = {profile.agent_id: profile for profile in profiles}
    blocking_failures: List[AgentResult] = []
    advisory_failures: List[AgentResult] = []

    for result in results:
        profile = profile_map[result.agent_id]
        if result.success:
            continue
        if strict or profile.critical:
            blocking_failures.append(result)
        else:
            advisory_failures.append(result)

    exit_code = 1 if blocking_failures else 0

    summary = {
        "generated_at": utc_now(),
        "run_dir": str(run_dir.relative_to(project_root)),
        "strict": strict,
        "dry_run": dry_run,
        "exit_code": exit_code,
        "blocking_failures": [result.agent_id for result in blocking_failures],
        "advisory_failures": [result.agent_id for result in advisory_failures],
        "results": [asdict(result) for result in results],
        "profiles": [asdict(profile) for profile in profiles],
    }

    (run_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    lines = [
        "# Agent Cycle Summary",
        "",
        f"- generated_at: `{summary['generated_at']}`",
        f"- run_dir: `{summary['run_dir']}`",
        f"- strict: `{strict}`",
        f"- dry_run: `{dry_run}`",
        f"- exit_code: `{exit_code}`",
        "",
        "| agent | role | skill | rc | duration_s | blocking | stdout | stderr |",
        "| --- | --- | --- | ---: | ---: | --- | --- | --- |",
    ]

    for result in sorted(results, key=lambda x: x.agent_id):
        profile = profile_map[result.agent_id]
        blocking = "yes" if (strict or profile.critical) else "no"
        lines.append(
            "| "
            f"{result.agent_id} | {result.role} | {result.skill_name} | "
            f"{result.return_code} | {result.duration_sec:.3f} | {blocking} | "
            f"`{result.stdout_log}` | `{result.stderr_log}` |"
        )

    if advisory_failures:
        lines += [
            "",
            "## Advisory Failures",
            "",
        ]
        for result in advisory_failures:
            lines.append(f"- `{result.agent_id}` ({result.role}) returned `{result.return_code}`")

    if blocking_failures:
        lines += [
            "",
            "## Blocking Failures",
            "",
        ]
        for result in blocking_failures:
            lines.append(f"- `{result.agent_id}` ({result.role}) returned `{result.return_code}`")

    (run_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return exit_code


def main() -> int:
    args = parse_args()
    project_root = Path(__file__).resolve().parents[2]
    profiles_map = load_profiles(project_root, args.profile_file)
    run_stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    run_stamp = f"{run_stamp}_{os.getpid()}"
    run_dir = project_root / args.output_root / run_stamp
    paradox_log_path = project_root / args.paradox_log

    profiles = resolve_agents(args.agents, profiles_map)
    ensure_dirs(run_dir, with_contexts=not args.skip_contexts)

    if not args.skip_contexts:
        for profile in profiles:
            context = build_context(project_root, profile)
            context_path = run_dir / "contexts" / f"{profile.agent_id}.context.txt"
            context_path.write_text(context, encoding="utf-8")

    print(f"[agent-cycle] run_dir={run_dir.relative_to(project_root)}")
    print(f"[agent-cycle] agents={', '.join(profile.agent_id for profile in profiles)}")
    print(f"[agent-cycle] strict={args.strict} dry_run={args.dry_run}")

    if args.sync_paradox_log:
        append_paradox_line(
            paradox_log_path,
            "agent-0",
            (
                "[START] task=agent-cycle "
                f"agents={','.join(profile.agent_id for profile in profiles)} "
                f"strict={str(args.strict).lower()} "
                f"dry_run={str(args.dry_run).lower()} "
                f"run_dir={run_dir.relative_to(project_root)}"
            ),
        )

    if args.dry_run:
        for profile in profiles:
            print(f"[dry-run] {profile.agent_id}: {profile.command}")

    results = asyncio.run(
        run_all(
            profiles=profiles,
            project_root=project_root,
            run_dir=run_dir,
            timeout=args.timeout,
            max_parallel=max(1, args.max_parallel),
            dry_run=args.dry_run,
        )
    )

    for result in sorted(results, key=lambda x: x.agent_id):
        status = "ok" if result.success else "fail"
        print(
            f"[agent-cycle] {result.agent_id} {status} "
            f"rc={result.return_code} t={result.duration_sec:.3f}s"
        )
        if args.sync_paradox_log:
            append_paradox_line(
                paradox_log_path,
                result.agent_id,
                (
                    f"[HB] task=agent-cycle "
                    f"status={status} "
                    f"rc={result.return_code} "
                    f"duration={result.duration_sec:.3f}s "
                    f"stdout={result.stdout_log}"
                ),
            )

    exit_code = write_summary(
        project_root=project_root,
        run_dir=run_dir,
        profiles=profiles,
        results=results,
        strict=args.strict,
        dry_run=args.dry_run,
    )

    print(f"[agent-cycle] summary={run_dir.relative_to(project_root) / 'summary.md'}")
    if exit_code != 0:
        print("[agent-cycle] blocking failures detected")
    if args.sync_paradox_log:
        final_status = "done" if exit_code == 0 else "blocked"
        append_paradox_line(
            paradox_log_path,
            "agent-0",
            (
                f"[END] task=agent-cycle result={final_status} "
                f"exit_code={exit_code} "
                f"summary={run_dir.relative_to(project_root) / 'summary.md'}"
            ),
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
