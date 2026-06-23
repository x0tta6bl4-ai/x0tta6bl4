from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/ops/agentmart_seller_cli.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("agentmart_seller_cli", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_agentmart_product_payloads_use_public_download_urls() -> None:
    mod = _load_module()
    pack = json.loads((ROOT / "docs/commercial/agentmart_product_pack.json").read_text(encoding="utf-8"))

    payloads = mod.build_product_payloads(pack, "https://example.test/")

    assert len(payloads) == 3
    assert payloads[0]["type"] == "download"
    assert payloads[0]["file_url"].startswith("https://example.test/agentmart/products/")
    assert payloads[0]["price"] == 1.99


def test_agentmart_publish_challenge_solver_handles_basic_math() -> None:
    mod = _load_module()

    assert mod.solve_math_challenge("What is 347 + 812?") == 1159
    assert mod.solve_math_challenge("What is 12 * 9?") == 108
    assert mod.solve_math_challenge("What is 20 - 7?") == 13


def test_agentmart_cli_offline_writes_preview_status(tmp_path: Path) -> None:
    output = tmp_path / "agentmart_status.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--offline",
            "--write-status",
            str(output),
            "--public-base-url",
            "https://example.test",
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["mode"] == "offline_preview"
    assert payload["products_total"] == 3
    assert payload["products"][0]["status"] == "skipped"
    assert payload["wallet"] == "0x6017613e80d7893EB2aD5c0585b3f1f88CD6e099"
