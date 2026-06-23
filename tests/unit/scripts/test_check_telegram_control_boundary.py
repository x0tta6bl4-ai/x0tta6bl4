from __future__ import annotations

from pathlib import Path

from scripts.ops.check_telegram_control_boundary import scan_root


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_allows_sales_bot_without_mesh_control_import(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/sales/telegram_bot.py",
        """
from telegram.ext import CommandHandler
from src.services.xray_manager import XrayManager

def start_command():
    return XrayManager
""",
    )

    findings, scanned = scan_root(
        tmp_path,
        ("src/sales/telegram_bot.py",),
    )

    assert scanned == ["src/sales/telegram_bot.py"]
    assert findings == []


def test_blocks_direct_mesh_control_import(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "telegram_bot.py",
        """
from src.mesh.network_manager import MeshNetworkManager

def handler():
    return MeshNetworkManager()
""",
    )

    findings, _ = scan_root(tmp_path, ("telegram_bot.py",))

    assert [item.kind for item in findings] == ["forbidden-import"]
    assert findings[0].detail == "src.mesh.network_manager"


def test_blocks_direct_control_call(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "telegram_bot.py",
        """
def handler(manager):
    return manager.trigger_aggressive_healing()
""",
    )

    findings, _ = scan_root(tmp_path, ("telegram_bot.py",))

    assert [item.kind for item in findings] == ["forbidden-call"]
    assert findings[0].detail == "manager.trigger_aggressive_healing"


def test_blocks_infrastructure_mutation_command(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "scripts/telegram_webhook_server.py",
        """
def handler():
    return "kubectl delete pod mesh-node"
""",
    )

    findings, _ = scan_root(
        tmp_path,
        ("scripts/telegram_webhook_server.py",),
    )

    assert [item.kind for item in findings] == ["kubectl-mutation"]
