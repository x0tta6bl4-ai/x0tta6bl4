"""
Quantum-Ready Upgrade: Post-Quantum Audit

Provides security audit for post-quantum cryptography,
migration planning, and rollback strategy.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PQAlgorithmStatus(Enum):
    """Post-quantum algorithm status"""

    VALIDATED = "validated"
    DEPRECATED = "deprecated"
    PENDING = "pending"
    FAILED = "failed"


class AuditSeverity(Enum):
    """Audit finding severity"""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PQAlgorithmAudit:
    """Post-quantum algorithm audit result"""

    algorithm_name: str
    status: PQAlgorithmStatus
    version: str
    security_level: int  # NIST security level (1-5)
    performance_score: float  # 0.0-1.0
    compliance: bool
    findings: List[Dict[str, Any]] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)
    last_audited: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MigrationPlan:
    """Migration plan for quantum-ready upgrade"""

    plan_id: str
    source_algorithm: str
    target_algorithm: str
    migration_steps: List[Dict[str, Any]] = field(default_factory=list)
    rollback_steps: List[Dict[str, Any]] = field(default_factory=list)
    estimated_downtime: float = 0.0  # seconds
    risk_level: str = "low"
    created_at: datetime = field(default_factory=datetime.utcnow)


class QuantumAuditor:
    """
    Post-quantum cryptography auditor.

    Provides:
    - Security audit for PQC algorithms
    - Algorithm validation
    - Performance benchmarks
    - Compliance checking
    - Migration planning
    """

    def __init__(self):
        self.audit_results: Dict[str, PQAlgorithmAudit] = {}
        self.migration_plans: Dict[str, MigrationPlan] = {}
        logger.info("QuantumAuditor initialized")

    def audit_algorithm(
        self, algorithm_name: str, version: str, security_level: int
    ) -> PQAlgorithmAudit:
        """
        Audit a post-quantum algorithm.

        Args:
            algorithm_name: Algorithm name (e.g., "ML-KEM-768")
            version: Algorithm version
            security_level: NIST security level

        Returns:
            PQAlgorithmAudit result
        """
        logger.info(f"Auditing PQC algorithm: {algorithm_name} v{version}")

        # Perform audit checks
        findings = []
        recommendations = []
        compliance = True

        # Check NIST standardization status
        nist_status = self._check_nist_status(algorithm_name)
        if nist_status != "standardized":
            findings.append(
                {
                    "severity": AuditSeverity.MEDIUM,
                    "finding": f"Algorithm {algorithm_name} not yet NIST standardized",
                    "recommendation": "Monitor NIST updates",
                }
            )
            if nist_status == "deprecated":
                compliance = False

        # Check security level
        if security_level < 3:
            findings.append(
                {
                    "severity": AuditSeverity.HIGH,
                    "finding": f"Security level {security_level} may be insufficient",
                    "recommendation": "Consider upgrading to level 3+",
                }
            )

        # Performance benchmark
        performance_score = self._benchmark_algorithm(algorithm_name)
        if performance_score < 0.5:
            findings.append(
                {
                    "severity": AuditSeverity.LOW,
                    "finding": "Performance may be suboptimal",
                    "recommendation": "Consider performance optimizations",
                }
            )

        # Determine status
        if (
            compliance
            and len(
                [
                    f
                    for f in findings
                    if f["severity"] in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]
                ]
            )
            == 0
        ):
            status = PQAlgorithmStatus.VALIDATED
        elif not compliance:
            status = PQAlgorithmStatus.FAILED
        else:
            status = PQAlgorithmStatus.PENDING

        audit = PQAlgorithmAudit(
            algorithm_name=algorithm_name,
            status=status,
            version=version,
            security_level=security_level,
            performance_score=performance_score,
            compliance=compliance,
            findings=findings,
            recommendations=recommendations,
        )

        self.audit_results[algorithm_name] = audit
        logger.info(f"Audit complete: {algorithm_name} - {status.value}")

        return audit

    def _check_nist_status(self, algorithm_name: str) -> str:
        """Check NIST standardization status"""
        # NIST standardized algorithms
        nist_standardized = {
            "ML-KEM-768": "standardized",
            "ML-KEM-1024": "standardized",
            "ML-DSA-65": "standardized",
            "ML-DSA-87": "standardized",
        }

        return nist_standardized.get(algorithm_name, "pending")

    def _benchmark_algorithm(self, algorithm_name: str) -> float:
        """Benchmark algorithm performance"""
        # Simulated performance scores
        performance_scores = {
            "ML-KEM-768": 0.8,
            "ML-KEM-1024": 0.7,
            "ML-DSA-65": 0.75,
            "ML-DSA-87": 0.7,
        }

        return performance_scores.get(algorithm_name, 0.5)

    def create_migration_plan(
        self, source_algorithm: str, target_algorithm: str
    ) -> MigrationPlan:
        """
        Create migration plan for quantum-ready upgrade.

        Args:
            source_algorithm: Current algorithm
            target_algorithm: Target algorithm

        Returns:
            MigrationPlan
        """
        plan_id = f"migration-{source_algorithm}-to-{target_algorithm}"

        # Define migration steps
        migration_steps = [
            {
                "step": 1,
                "action": "Audit current algorithm",
                "description": f"Audit {source_algorithm} for vulnerabilities",
            },
            {
                "step": 2,
                "action": "Validate target algorithm",
                "description": f"Validate {target_algorithm} meets requirements",
            },
            {
                "step": 3,
                "action": "Deploy hybrid mode",
                "description": "Deploy hybrid (classical + PQC) for transition",
            },
            {
                "step": 4,
                "action": "Monitor performance",
                "description": "Monitor performance and security metrics",
            },
            {
                "step": 5,
                "action": "Full migration",
                "description": f"Complete migration to {target_algorithm}",
            },
        ]

        # Define rollback steps
        rollback_steps = [
            {
                "step": 1,
                "action": "Revert to hybrid mode",
                "description": "Revert to hybrid (classical + PQC)",
            },
            {
                "step": 2,
                "action": "Revert to source algorithm",
                "description": f"Revert to {source_algorithm}",
            },
            {
                "step": 3,
                "action": "Verify system stability",
                "description": "Verify system is stable after rollback",
            },
        ]

        # Estimate downtime
        estimated_downtime = 300.0  # 5 minutes

        # Determine risk level
        risk_level = "low"  # Can be adjusted based on algorithm compatibility

        plan = MigrationPlan(
            plan_id=plan_id,
            source_algorithm=source_algorithm,
            target_algorithm=target_algorithm,
            migration_steps=migration_steps,
            rollback_steps=rollback_steps,
            estimated_downtime=estimated_downtime,
            risk_level=risk_level,
        )

        self.migration_plans[plan_id] = plan
        logger.info(f"Created migration plan: {plan_id}")

        return plan

    def get_audit_summary(self) -> Dict[str, Any]:
        """Get audit summary"""
        total_algorithms = len(self.audit_results)
        validated = sum(
            1
            for a in self.audit_results.values()
            if a.status == PQAlgorithmStatus.VALIDATED
        )
        failed = sum(
            1
            for a in self.audit_results.values()
            if a.status == PQAlgorithmStatus.FAILED
        )

        return {
            "total_algorithms": total_algorithms,
            "validated": validated,
            "failed": failed,
            "pending": total_algorithms - validated - failed,
            "compliance_rate": (
                (validated / total_algorithms * 100) if total_algorithms > 0 else 0.0
            ),
        }
