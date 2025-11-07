"""
Unit tests for SecurityScanner integration
"""
import pytest
from src.security.scanning import SecurityScanner
import subprocess

class DummyCompletedProcess:
    def __init__(self, stdout):
        self.stdout = stdout

@pytest.fixture(autouse=True)
def patch_subprocess_run(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda *a, **kw: DummyCompletedProcess("scan ok"))

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
