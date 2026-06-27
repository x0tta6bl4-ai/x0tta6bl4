import hashlib
import json

from src.coordination.state import AgentCoordinator, AgentRole


def test_create_file_lock_uses_sha256_filename(tmp_path):
    coordinator = AgentCoordinator(project_root=str(tmp_path))
    coordinator.register_agent("codex", AgentRole.CODER)

    path = "src/example.py"
    assert coordinator.acquire_lock("codex", path) is True

    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()
    lock_file = tmp_path / ".agent_coordination" / "locks" / f"{digest}.lock"
    assert lock_file.exists()


def test_release_lock_removes_legacy_lock_files_by_path(tmp_path):
    coordinator = AgentCoordinator(project_root=str(tmp_path))
    coordinator.register_agent("codex", AgentRole.CODER)

    path = "src/example.py"
    other_path = "src/other.py"
    assert coordinator.acquire_lock("codex", path) is True

    lock_dir = tmp_path / ".agent_coordination" / "locks"
    legacy_file = lock_dir / "legacy.lock"
    legacy_file.write_text(
        json.dumps({"path": path, "agent_id": "old-agent"}),
        encoding="utf-8",
    )
    unrelated_legacy_file = lock_dir / "legacy-other.lock"
    unrelated_legacy_file.write_text(
        json.dumps({"path": other_path, "agent_id": "old-agent"}),
        encoding="utf-8",
    )

    assert coordinator.release_lock("codex", path) is True
    assert not legacy_file.exists()
    assert unrelated_legacy_file.exists()
