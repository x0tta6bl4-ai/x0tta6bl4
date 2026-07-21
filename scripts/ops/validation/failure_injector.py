"""Failure Injector Engine for x0tta6bl4 Validation Framework.

Decouples test suites from failure logic.
Test scenarios invoke inject_failure(F_x) and the engine handles the rest.

Reference: docs/architecture/BENCHMARK_SPEC.md §3
"""

import subprocess
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from .failure_taxonomy import FailureType, get_failure

logger = logging.getLogger(__name__)


@dataclass
class InjectionResult:
    success: bool
    failure_id: str
    target: str
    duration_ms: float
    error: Optional[str] = None
    cleanup_cmd: Optional[str] = None


@dataclass
class FailureInjector:
    """Generic failure injector that works with any target."""

    dry_run: bool = False
    _active_injections: dict[str, subprocess.Popen] = field(default_factory=dict)

    def inject(
        self,
        failure_id: str,
        target: str,
        duration_sec: float = 10.0,
        intensity: float = 0.2,
        **kwargs,
    ) -> InjectionResult:
        """Inject a failure into the target.

        Args:
            failure_id: Failure type ID (F1-F10)
            target: Target to inject failure into (IP, hostname, or 'local')
            duration_sec: How long to maintain the failure
            intensity: Failure intensity (0.0-1.0), meaning depends on failure type
            **kwargs: Additional parameters for specific failure types

        Returns:
            InjectionResult with success status and cleanup command
        """
        failure = get_failure(failure_id)
        start = time.monotonic()

        try:
            if self.dry_run:
                logger.info("[DRY RUN] Would inject %s into %s for %.1fs", failure_id, target, duration_sec)
                return InjectionResult(
                    success=True,
                    failure_id=failure_id,
                    target=target,
                    duration_ms=0,
                )

            cmd = self._build_inject_command(failure, target, duration_sec, intensity, **kwargs)
            logger.info("Injecting %s (%s) into %s: %s", failure_id, failure.name, target, cmd)

            proc = subprocess.run(
                cmd,
                shell=True,
                capture_output=True,
                text=True,
                timeout=30,
            )

            if proc.returncode != 0:
                return InjectionResult(
                    success=False,
                    failure_id=failure_id,
                    target=target,
                    duration_ms=(time.monotonic() - start) * 1000,
                    error=proc.stderr.strip(),
                )

            self._active_injections[failure_id] = proc
            cleanup = self._build_cleanup_command(failure, target, **kwargs)

            return InjectionResult(
                success=True,
                failure_id=failure_id,
                target=target,
                duration_ms=(time.monotonic() - start) * 1000,
                cleanup_cmd=cleanup,
            )

        except subprocess.TimeoutExpired:
            return InjectionResult(
                success=False,
                failure_id=failure_id,
                target=target,
                duration_ms=(time.monotonic() - start) * 1000,
                error="Injection command timed out after 30s",
            )
        except Exception as e:
            return InjectionResult(
                success=False,
                failure_id=failure_id,
                target=target,
                duration_ms=(time.monotonic() - start) * 1000,
                error=str(e),
            )

    def cleanup(self, failure_id: str, target: str, **kwargs) -> bool:
        """Cleanup a previously injected failure."""
        failure = get_failure(failure_id)
        cmd = self._build_cleanup_command(failure, target, **kwargs)

        if self.dry_run:
            logger.info("[DRY RUN] Would cleanup %s on %s: %s", failure_id, target, cmd)
            return True

        try:
            proc = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
            return proc.returncode == 0
        except Exception as e:
            logger.error("Cleanup failed for %s: %s", failure_id, e)
            return False

    def cleanup_all(self) -> dict[str, bool]:
        """Cleanup all active injections."""
        results = {}
        for failure_id in list(self._active_injections.keys()):
            results[failure_id] = self.cleanup(failure_id, "local")
            self._active_injections.pop(failure_id, None)
        return results

    def _build_inject_command(
        self,
        failure: FailureType,
        target: str,
        duration_sec: float,
        intensity: float,
        **kwargs,
    ) -> str:
        """Build the shell command to inject a specific failure type."""
        if failure.id == "F1":
            # Node Crash: kill process
            pid = kwargs.get("pid")
            if pid:
                return f"kill -9 {pid}"
            service = kwargs.get("service", "xray")
            return f"systemctl stop {service}"

        elif failure.id == "F3":
            # Network Partition: block traffic with iptables
            return f"iptables -A INPUT -s {target} -j DROP && iptables -A OUTPUT -d {target} -j DROP"

        elif failure.id == "F4":
            # Synthetic Packet Loss: netem
            loss_pct = int(intensity * 100)
            iface = kwargs.get("iface", "eth0")
            return f"tc qdisc add dev {iface} root netem loss {loss_pct}%"

        elif failure.id == "F5":
            # High Latency: netem delay
            delay_ms = int(intensity * 500)
            jitter_ms = int(delay_ms * 0.3)
            iface = kwargs.get("iface", "eth0")
            return f"tc qdisc add dev {iface} root netem delay {delay_ms}ms {jitter_ms}ms"

        elif failure.id == "F6":
            # DNS Failure: block DNS
            return "iptables -A OUTPUT -p udp --dport 53 -j DROP && iptables -A OUTPUT -p tcp --dport 53 -j DROP"

        else:
            return f"echo 'Manual injection required for {failure.id}'"

    def _build_cleanup_command(self, failure: FailureType, target: str, **kwargs) -> str:
        """Build the shell command to cleanup a specific failure type."""
        if failure.id == "F1":
            service = kwargs.get("service", "xray")
            return f"systemctl start {service}"

        elif failure.id == "F3":
            return f"iptables -D INPUT -s {target} -j DROP && iptables -D OUTPUT -d {target} -j DROP"

        elif failure.id in ("F4", "F5"):
            iface = kwargs.get("iface", "eth0")
            return f"tc qdisc del dev {iface} root"

        elif failure.id == "F6":
            return "iptables -D OUTPUT -p udp --dport 53 -j DROP && iptables -D OUTPUT -p tcp --dport 53 -j DROP"

        else:
            return f"echo 'Manual cleanup required for {failure.id}'"
