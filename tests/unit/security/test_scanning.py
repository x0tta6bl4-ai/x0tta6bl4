"""
Unit tests for SecurityScanner integration
"""

import subprocess
import shutil

import pytest

from src.security.scanning import SecurityScanner


class DummyCompletedProcess:
    def __init__(self, stdout):
        self.stdout = stdout


@pytest.fixture(autouse=True)
def patch_subprocess_run(monkeypatch):
    original = shutil.which
    monkeypatch.setattr(shutil, "which", lambda command:
                        f"/usr/bin/{command}" if command in {"bandit", "safety", "trivy"}
                        else original(command))
    monkeypatch.setattr(
        subprocess, "run", lambda *a, **kw: DummyCompletedProcess("scan ok")
    )


def test_bandit_scan():
    scanner = SecurityScanner()
    out = scanner.run_bandit("src/")
    assert "scan ok" in out


def test_safety_scan():
    scanner = SecurityScanner()
    out = scanner.run_safety("requirements.consolidated.txt")
    assert "scan ok" in out


def test_trivy_scan():
    scanner = SecurityScanner()
    out = scanner.run_trivy("test-image:latest")
    assert "scan ok" in out
