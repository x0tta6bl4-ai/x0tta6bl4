"""
Security Scanning Integration for x0tta6bl4
Integrates Bandit, Safety, Trivy for automated security checks
"""
from __future__ import annotations

import logging
import subprocess
from src.core.security.subprocess_validator import safe_run

logger = logging.getLogger(__name__)


class SecurityScanner:
    def run_bandit(self, target: str = "src/") -> str:
        logger.info(f"Running Bandit on {target}")
        result = safe_run(
            ["bandit", "-r", target], capture_output=True, text=True
        )
        return result.stdout

    def run_safety(self, requirements: str = "requirements.consolidated.txt") -> str:
        logger.info(f"Running Safety on {requirements}")
        result = safe_run(
            ["safety", "check", "-r", requirements], capture_output=True, text=True
        )
        return result.stdout

    def run_trivy(self, image: str) -> str:
        logger.info(f"Running Trivy on image {image}")
        result = safe_run(
            ["trivy", "image", image], capture_output=True, text=True
        )
        return result.stdout

