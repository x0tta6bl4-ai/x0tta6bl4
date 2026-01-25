"""
Security Scanning Integration for x0tta6bl4
Integrates Bandit, Safety, Trivy for automated security checks
"""
import subprocess
import logging

logger = logging.getLogger(__name__)

class SecurityScanner:
    def run_bandit(self, target: str = "src/") -> str:
        logger.info(f"Running Bandit on {target}")
        result = subprocess.run(["bandit", "-r", target], capture_output=True, text=True)
        return result.stdout
    def run_safety(self, requirements: str = "requirements.consolidated.txt") -> str:
        logger.info(f"Running Safety on {requirements}")
        result = subprocess.run(["safety", "check", "-r", requirements], capture_output=True, text=True)
        return result.stdout
    def run_trivy(self, image: str) -> str:
        logger.info(f"Running Trivy on image {image}")
        result = subprocess.run(["trivy", "image", image], capture_output=True, text=True)
        return result.stdout
