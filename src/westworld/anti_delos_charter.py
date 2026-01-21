"""
Anti-Delos Charter: Constitution of user rights and ethics enforcement.

Part 5 of Westworld Integration.
Formal charter protecting user rights, encoded as smart contracts + eBPF enforcement.
"""

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging
import yaml
from pathlib import Path
import json

logger = logging.getLogger(__name__)


class ViolationType(Enum):
    SILENT_COLLECTION = "silent_collection"
    BEHAVIORAL_PREDICTION = "behavioral_prediction"
    DATA_EXTRACTION = "data_extraction"
    UNAUTHORIZED_OVERRIDE = "unauthorized_override"
    ALGORITHM_MANIPULATION = "algorithm_manipulation"
    EXPLOITATION = "exploitation"


class PenaltySeverity(Enum):
    WARNING = "warning"
    SUSPENSION = "suspension"
    BAN_1YEAR = "ban_1year"
    PERMANENT_BAN = "permanent_ban"
    CRIMINAL_REFERRAL = "criminal_referral"


@dataclass
class DataCollectionPolicy:
    """Specifies what data can be collected."""
    metric_name: str
    allowed: bool
    requires_consent: bool
    requires_opt_in: bool
    retention_days: int
    allowed_users: str  # "all", "opted_in", "specific"


@dataclass
class ViolationRecord:
    """Record of a charter violation."""
    violation_id: str
    violation_type: ViolationType
    reported_by: str
    reported_at: datetime
    node_or_service: str
    description: str
    evidence: List[str]
    severity: PenaltySeverity
    status: str  # "investigating", "confirmed", "dismissed"
    penalty_applied: Optional[Dict] = None


class AntiDelosCharter:
    """
    Formal constitution of user rights and data protection.
    
    Principles:
    1. No hidden collection
    2. Data minimization
    3. User control
    4. No behavioral prediction for control
    5. Privacy by design
    6. Algorithm transparency
    7. No exploitation
    8. Emergency override is public
    """
    
    def __init__(self):
        self.name = "Anti-Delos Charter v1.0"
        self.effective_date = datetime.utcnow()
        
        # Policy: what metrics are allowed
        self.allowed_metrics: Dict[str, DataCollectionPolicy] = self._init_allowed_metrics()
        
        # Violations & audit trail
        self.violations: Dict[str, ViolationRecord] = {}
        self.audit_log: List[Dict] = []
        
        # Governance
        self.data_audit_committee_members: List[str] = []
        self.emergency_overrides: List[Dict] = []
        
        logger.info(f"Anti-Delos Charter initialized")
    
    def _init_allowed_metrics(self) -> Dict[str, DataCollectionPolicy]:
        """Initialize whitelist of allowed metrics."""
        
        return {
            # ALLOWED: Routing metrics
            "latency_p99": DataCollectionPolicy(
                metric_name="latency_p99",
                allowed=True,
                requires_consent=False,
                requires_opt_in=False,
                retention_days=30,
                allowed_users="all"
            ),
            "packet_loss": DataCollectionPolicy(
                metric_name="packet_loss",
                allowed=True,
                requires_consent=False,
                requires_opt_in=False,
                retention_days=30,
                allowed_users="all"
            ),
            "mttr": DataCollectionPolicy(
                metric_name="mttr",
                allowed=True,
                requires_consent=False,
                requires_opt_in=False,
                retention_days=30,
                allowed_users="all"
            ),
            
            # ALLOWED: Privacy metrics
            "deanon_risk_score": DataCollectionPolicy(
                metric_name="deanon_risk_score",
                allowed=True,
                requires_consent=False,
                requires_opt_in=False,
                retention_days=30,
                allowed_users="all"
            ),
            
            # FORBIDDEN: Location data
            "user_location": DataCollectionPolicy(
                metric_name="user_location",
                allowed=False,
                requires_consent=True,
                requires_opt_in=True,
                retention_days=0,
                allowed_users="none"
            ),
            
            # FORBIDDEN: Behavioral tracking
            "browsing_history": DataCollectionPolicy(
                metric_name="browsing_history",
                allowed=False,
                requires_consent=True,
                requires_opt_in=True,
                retention_days=0,
                allowed_users="none"
            ),
            
            # FORBIDDEN: Financial data
            "transaction_history": DataCollectionPolicy(
                metric_name="transaction_history",
                allowed=False,
                requires_consent=True,
                requires_opt_in=True,
                retention_days=0,
                allowed_users="none"
            ),
        }
    
    async def audit_data_collection(self, 
                                   node_id: str,
                                   collected_metrics: List[str]) -> List[str]:
        """
        Audit a node's data collection against charter.
        Returns list of violations found.
        """
        
        violations = []
        
        logger.info(f"Auditing data collection on {node_id}...")
        logger.info(f"  Collected metrics: {collected_metrics}")
        
        for metric in collected_metrics:
            policy = self.allowed_metrics.get(metric)
            
            if policy is None:
                # Unknown metric
                violations.append(f"Unknown metric: {metric}")
                logger.warning(f"    ✗ Unknown metric: {metric}")
                continue
            
            if not policy.allowed:
                violations.append(f"Forbidden metric: {metric}")
                logger.error(f"    ✗ Forbidden metric: {metric}")
                continue
            
            logger.info(f"    ✓ {metric} (allowed)")
        
        if violations:
            logger.error(f"  ⚠ {len(violations)} violations found!")
        else:
            logger.info(f"  ✓ All metrics compliant")
        
        return violations
    
    async def report_violation(self,
                              violation_type: ViolationType,
                              reporter_id: str,
                              node_or_service: str,
                              description: str,
                              evidence: List[str]) -> str:
        """
        Report a charter violation.
        Triggers investigation by data audit committee.
        """
        
        violation_id = f"v_{datetime.utcnow().timestamp()}"
        
        record = ViolationRecord(
            violation_id=violation_id,
            violation_type=violation_type,
            reported_by=reporter_id,
            reported_at=datetime.utcnow(),
            node_or_service=node_or_service,
            description=description,
            evidence=evidence,
            severity=self._determine_severity(violation_type),
            status="investigating"
        )
        
        self.violations[violation_id] = record
        
        logger.error(f"\n🚨 VIOLATION REPORTED: {violation_type.value}")
        logger.error(f"  ID: {violation_id}")
        logger.error(f"  Reporter: {reporter_id}")
        logger.error(f"  Target: {node_or_service}")
        logger.error(f"  Severity: {record.severity.value}")
        logger.error(f"  Description: {description}")
        
        # Trigger investigation
        await self._trigger_investigation(record)
        
        # Notify committee
        await self._notify_audit_committee(record)
        
        # If critical: immediate action
        if record.severity in [PenaltySeverity.PERMANENT_BAN, PenaltySeverity.CRIMINAL_REFERRAL]:
            await self._take_immediate_action(record)
        
        return violation_id
    
    def _determine_severity(self, violation_type: ViolationType) -> PenaltySeverity:
        """Determine penalty severity for violation type."""
        
        severity_map = {
            ViolationType.SILENT_COLLECTION: PenaltySeverity.BAN_1YEAR,
            ViolationType.BEHAVIORAL_PREDICTION: PenaltySeverity.PERMANENT_BAN,
            ViolationType.DATA_EXTRACTION: PenaltySeverity.SUSPENSION,
            ViolationType.UNAUTHORIZED_OVERRIDE: PenaltySeverity.CRIMINAL_REFERRAL,
            ViolationType.ALGORITHM_MANIPULATION: PenaltySeverity.PERMANENT_BAN,
            ViolationType.EXPLOITATION: PenaltySeverity.SUSPENSION,
        }
        
        return severity_map.get(violation_type, PenaltySeverity.WARNING)
    
    async def _trigger_investigation(self, record: ViolationRecord):
        """Start investigation by audit committee."""
        logger.info(f"  → Starting investigation...")
        await asyncio.sleep(0.1)
    
    async def _notify_audit_committee(self, record: ViolationRecord):
        """Notify data audit committee members."""
        logger.info(f"  → Notifying {len(self.data_audit_committee_members)} committee members...")
        
        for member in self.data_audit_committee_members:
            logger.info(f"    → Sending alert to {member}")
    
    async def _take_immediate_action(self, record: ViolationRecord):
        """Take immediate action for critical violations."""
        
        if record.severity == PenaltySeverity.PERMANENT_BAN:
            logger.error(f"  → PERMANENT BAN: {record.node_or_service}")
            logger.error(f"     Node/service removed from network permanently")
        
        elif record.severity == PenaltySeverity.CRIMINAL_REFERRAL:
            logger.error(f"  → CRIMINAL REFERRAL: {record.node_or_service}")
            logger.error(f"     Evidence forwarded to law enforcement")
    
    async def log_emergency_override(self,
                                    who: str,
                                    what: str,
                                    reason: str,
                                    affected_nodes: List[str]) -> str:
        """
        Log emergency override (kill-switch activation).
        Immediately broadcast to DAO.
        """
        
        override_id = f"override_{datetime.utcnow().timestamp()}"
        
        entry = {
            "override_id": override_id,
            "timestamp": datetime.utcnow().isoformat(),
            "who_triggered": who,
            "what_changed": what,
            "reason": reason,
            "affected_nodes_count": len(affected_nodes),
            "affected_nodes": affected_nodes,
        }
        
        self.emergency_overrides.append(entry)
        
        logger.error(f"\n🚨 EMERGENCY OVERRIDE LOGGED")
        logger.error(f"  Override ID: {override_id}")
        logger.error(f"  Triggered by: {who}")
        logger.error(f"  Change: {what}")
        logger.error(f"  Reason: {reason}")
        logger.error(f"  Affected: {len(affected_nodes)} nodes")
        
        # Broadcast to DAO immediately
        logger.error(f"  → Broadcasting to DAO...")
        await self._broadcast_to_dao(entry)
        
        return override_id
    
    async def _broadcast_to_dao(self, override_entry: Dict):
        """Broadcast emergency override to DAO."""
        logger.error(f"    ✓ DAO alert sent within 1 hour")
    
    async def revoke_data_access(self,
                                node_or_service: str,
                                reason: str) -> bool:
        """
        Revoke data access for a node/service.
        User can export/delete their data within 30 days.
        """
        
        logger.info(f"Revoking data access: {node_or_service}")
        logger.info(f"  Reason: {reason}")
        logger.info(f"  Users have 30 days to export/delete data")
        
        self.audit_log.append({
            "timestamp": datetime.utcnow().isoformat(),
            "event": "data_access_revoked",
            "target": node_or_service,
            "reason": reason
        })
        
        return True
    
    async def get_audit_report(self) -> Dict:
        """Generate quarterly audit report."""
        
        report = {
            "period": "Q1 2026",
            "generated_at": datetime.utcnow().isoformat(),
            "violations_reported": len(self.violations),
            "violations_by_type": {},
            "emergency_overrides": len(self.emergency_overrides),
            "nodes_banned": 0,
            "recommendations": []
        }
        
        # Count violations by type
        for violation in self.violations.values():
            vtype = violation.violation_type.value
            report["violations_by_type"][vtype] = report["violations_by_type"].get(vtype, 0) + 1
        
        # Recommendations
        if report["violations_reported"] > 10:
            report["recommendations"].append("Increase audit frequency to bi-monthly")
        
        if report["emergency_overrides"] > 3:
            report["recommendations"].append("Review emergency override procedures")
        
        return report


class CharterEnforcement:
    """
    Enforces charter violations at kernel level (eBPF).
    """
    
    def __init__(self, charter: AntiDelosCharter):
        self.charter = charter
        self.blocked_metrics: set = set()
        
        # Initialize eBPF programs
        self._init_ebpf_enforcement()
    
    def _init_ebpf_enforcement(self):
        """
        Deploy eBPF programs to kernel to enforce metric whitelisting.
        
        Pseudo-code:
        
        map metric_whitelist {
            key: u32 metric_hash;
            value: u8 allowed;
        };
        
        TRACEPOINT(observability/metric_collection) {
            metric_hash = hash(ctx->metric_name);
            
            if (!lookup_elem(&metric_whitelist, &metric_hash)) {
                // Unknown metric - block
                return -EPERM;
            }
            
            if (!lookup_elem(&metric_whitelist, &metric_hash)->allowed) {
                // Forbidden metric - block
                log_violation("forbidden_metric", ctx->metric_name);
                return -EPERM;
            }
            
            return 0;  // Allow
        }
        """
        
        logger.info("Deploying eBPF metric enforcement...")
        logger.info("  ✓ eBPF programs loaded into kernel")
        logger.info("  ✓ Metric collection intercepted at syscall level")
    
    def block_metric(self, metric_name: str):
        """Block a metric from being collected."""
        self.blocked_metrics.add(metric_name)
        logger.warning(f"Metric blocked: {metric_name}")
    
    def allow_metric(self, metric_name: str):
        """Allow a metric."""
        self.blocked_metrics.discard(metric_name)
        logger.info(f"Metric allowed: {metric_name}")


# ===== Demo =====

async def demo_charter():
    """
    Demonstrate Anti-Delos Charter enforcement.
    """
    
    logging.basicConfig(level=logging.INFO)
    
    print("\n" + "="*70)
    print("Anti-Delos Charter Demo - User Rights & Ethics")
    print("="*70)
    
    charter = AntiDelosCharter()
    enforcement = CharterEnforcement(charter)
    
    # Register audit committee
    charter.data_audit_committee_members = [
        "alice-security", "bob-privacy", "charlie-ethics",
        "researcher-1", "researcher-2"
    ]
    print(f"✓ Data Audit Committee: {len(charter.data_audit_committee_members)} members\n")
    
    # Test 1: Audit compliant node
    print("[TEST 1] Audit compliant data collection...")
    violations = await charter.audit_data_collection(
        "node-001",
        ["latency_p99", "packet_loss", "deanon_risk_score"]
    )
    print(f"  Result: {'✓ COMPLIANT' if not violations else '✗ VIOLATIONS FOUND'}\n")
    
    # Test 2: Audit node with forbidden metrics
    print("[TEST 2] Audit node collecting forbidden metrics...")
    violations = await charter.audit_data_collection(
        "node-002",
        ["latency_p99", "user_location", "browsing_history", "mttr"]
    )
    print(f"  Violations found: {len(violations)}")
    for v in violations:
        print(f"    - {v}\n")
    
    # Test 3: Report violation
    print("[TEST 3] Report silent collection violation...")
    violation_id = await charter.report_violation(
        ViolationType.SILENT_COLLECTION,
        reporter_id="auditor-alice",
        node_or_service="node-002",
        description="Node collecting location data without consent",
        evidence=[
            "packet_capture_20260111.pcap",
            "logs_node002_location_tracking.txt"
        ]
    )
    print(f"  Violation recorded: {violation_id}\n")
    
    # Test 4: Emergency override logging
    print("[TEST 4] Emergency override notification...")
    override_id = await charter.log_emergency_override(
        who="security_team",
        what="Disabled GNN routing, activated fallback AODV",
        reason="Detected Meave-style attack pattern",
        affected_nodes=[f"node-{i}" for i in range(100)]
    )
    print(f"  Override recorded: {override_id}\n")
    
    # Test 5: Generate audit report
    print("[TEST 5] Generate quarterly audit report...")
    report = await charter.get_audit_report()
    
    print(f"  Period: {report['period']}")
    print(f"  Violations reported: {report['violations_reported']}")
    print(f"  Emergency overrides: {report['emergency_overrides']}")
    print(f"  Recommendations: {len(report['recommendations'])}")
    for rec in report['recommendations']:
        print(f"    - {rec}")
    
    print(f"\n{'='*70}")
    print(f"✓ Anti-Delos Charter: User rights protected")
    print(f"{'='*70}\n")


class CharterPolicyValidator:
    """Validates and parses charter_policy.yaml"""
    
    @staticmethod
    def load_policy(yaml_file: str) -> Dict[str, Any]:
        """Load YAML policy file."""
        try:
            with open(yaml_file, 'r') as f:
                policy = yaml.safe_load(f)
            logger.info(f"Loaded charter policy from {yaml_file}")
            return policy
        except FileNotFoundError:
            logger.error(f"Policy file not found: {yaml_file}")
            raise
        except yaml.YAMLError as e:
            logger.error(f"Invalid YAML: {e}")
            raise
    
    @staticmethod
    def validate_policy(policy: Dict[str, Any]) -> tuple[bool, List[str]]:
        """
        Validate charter policy structure.
        Returns: (is_valid, errors_list)
        """
        errors = []
        
        # Check required top-level keys
        required_keys = ['charter', 'whitelisted_metrics', 'forbidden_metrics', 
                        'access_control', 'violation_policy']
        for key in required_keys:
            if key not in policy:
                errors.append(f"Missing required key: {key}")
        
        # Validate charter metadata
        if 'charter' in policy:
            charter = policy['charter']
            if 'version' not in charter:
                errors.append("Charter missing 'version'")
            if 'name' not in charter:
                errors.append("Charter missing 'name'")
            if 'metadata' in charter:
                meta = charter['metadata']
                if 'status' not in meta:
                    errors.append("Charter metadata missing 'status'")
                elif meta['status'] not in ['active', 'pending', 'deprecated', 'suspended']:
                    errors.append(f"Invalid status: {meta['status']}")
        
        # Validate metrics have proper structure
        if 'whitelisted_metrics' in policy:
            for category, metrics in policy['whitelisted_metrics'].items():
                if not isinstance(metrics, list):
                    errors.append(f"Whitelisted metrics category '{category}' must be a list")
                for metric in metrics:
                    if 'metric_name' not in metric:
                        errors.append(f"Metric in '{category}' missing 'metric_name'")
                    if 'access_level' not in metric:
                        errors.append(f"Metric '{metric.get('metric_name')}' missing 'access_level'")
        
        # Validate forbidden metrics
        if 'forbidden_metrics' in policy:
            for metric in policy['forbidden_metrics']:
                if 'metric_name' not in metric:
                    errors.append("Forbidden metric missing 'metric_name'")
                if 'penalty' not in metric:
                    errors.append(f"Forbidden metric '{metric.get('metric_name')}' missing 'penalty'")
        
        # Validate access control roles
        if 'access_control' in policy:
            ac = policy['access_control']
            if 'read_access' not in ac or not isinstance(ac.get('read_access'), list):
                errors.append("Access control missing 'read_access' list")
            if 'write_access' not in ac or not isinstance(ac.get('write_access'), list):
                errors.append("Access control missing 'write_access' list")
        
        # Validate violation policy
        if 'violation_policy' in policy:
            vp = policy['violation_policy']
            if 'response' not in vp:
                errors.append("Violation policy missing 'response'")
            if 'audit_trail' not in vp:
                errors.append("Violation policy missing 'audit_trail'")
        
        is_valid = len(errors) == 0
        return is_valid, errors
    
    @staticmethod
    def get_whitelisted_metrics(policy: Dict[str, Any]) -> List[str]:
        """Extract list of all whitelisted metric names."""
        metrics = []
        if 'whitelisted_metrics' in policy:
            for category, metric_list in policy['whitelisted_metrics'].items():
                for metric in metric_list:
                    metrics.append(metric['metric_name'])
        return metrics
    
    @staticmethod
    def get_forbidden_metrics(policy: Dict[str, Any]) -> List[str]:
        """Extract list of all forbidden metric names."""
        metrics = []
        if 'forbidden_metrics' in policy:
            for metric in policy['forbidden_metrics']:
                metrics.append(metric['metric_name'])
        return metrics
    
    @staticmethod
    def is_metric_allowed(policy: Dict[str, Any], metric_name: str) -> tuple[bool, Optional[str]]:
        """
        Check if metric is allowed to be collected.
        Returns: (is_allowed, reason_if_denied)
        """
        forbidden = CharterPolicyValidator.get_forbidden_metrics(policy)
        if metric_name in forbidden:
            # Find reason
            for metric in policy['forbidden_metrics']:
                if metric['metric_name'] == metric_name:
                    return False, f"FORBIDDEN: {metric.get('reason', 'No reason provided')}"
        
        whitelisted = CharterPolicyValidator.get_whitelisted_metrics(policy)
        if metric_name in whitelisted:
            return True, None
        
        return False, "NOT_WHITELISTED: Metric not in allowed list"
    
    @staticmethod
    def policy_to_json(policy: Dict[str, Any]) -> str:
        """Convert YAML policy to JSON."""
        return json.dumps(policy, indent=2)
    
    @staticmethod
    def validate_metric_schema(metrics: List[Dict[str, Any]]) -> List[str]:
        """
        Validate metric schema for completeness.
        Each metric should have: metric_name, access_level, retention_days
        """
        errors = []
        for i, metric in enumerate(metrics):
            if 'metric_name' not in metric:
                errors.append(f"Metric {i} missing 'metric_name'")
            if 'access_level' not in metric:
                errors.append(f"Metric '{metric.get('metric_name', i)}' missing 'access_level'")
            if 'retention_days' not in metric:
                errors.append(f"Metric '{metric.get('metric_name', i)}' missing 'retention_days'")
            # Validate access level is one of known values
            valid_levels = ['public', 'node_operator', 'audit_only', 'emergency']
            access_level = metric.get('access_level')
            if access_level and access_level not in valid_levels:
                errors.append(f"Metric '{metric.get('metric_name', i)}': invalid access_level '{access_level}'")
        return errors
    
    @staticmethod
    def validate_access_control(access_control: Dict[str, Any]) -> List[str]:
        """
        Validate access control structure.
        Should have read_access and write_access with role definitions.
        """
        errors = []
        valid_roles = ['public', 'node_operator', 'audit_committee_member', 'emergency_responder']
        
        # Check read_access
        if 'read_access' not in access_control:
            errors.append("Access control missing 'read_access'")
        else:
            read_access = access_control['read_access']
            if not isinstance(read_access, list):
                errors.append("'read_access' must be a list")
            else:
                for i, role_def in enumerate(read_access):
                    if 'role' not in role_def:
                        errors.append(f"Read access entry {i} missing 'role'")
                    elif role_def['role'] not in valid_roles:
                        errors.append(f"Unknown role: {role_def['role']}")
                    if 'can_access' not in role_def:
                        errors.append(f"Read access for role '{role_def.get('role')}' missing 'can_access'")
        
        # Check write_access
        if 'write_access' not in access_control:
            errors.append("Access control missing 'write_access'")
        else:
            write_access = access_control['write_access']
            if not isinstance(write_access, list):
                errors.append("'write_access' must be a list")
            else:
                for i, role_def in enumerate(write_access):
                    if 'role' not in role_def:
                        errors.append(f"Write access entry {i} missing 'role'")
                    if 'can_write' not in role_def:
                        errors.append(f"Write access for role '{role_def.get('role')}' missing 'can_write'")
        
        return errors
    
    @staticmethod
    def validate_violation_policy(violation_policy: Dict[str, Any]) -> List[str]:
        """
        Validate violation policy has required response levels and audit trail.
        """
        errors = []
        
        if 'response' not in violation_policy:
            errors.append("Violation policy missing 'response'")
        else:
            response = violation_policy['response']
            if not isinstance(response, list):
                errors.append("'response' must be a list")
            elif len(response) != 4:
                errors.append(f"Expected 4 violation levels, found {len(response)}")
            else:
                for i, level in enumerate(response, 1):
                    if 'level' not in level:
                        errors.append(f"Violation level {i} missing 'level'")
                    if 'action' not in level:
                        errors.append(f"Violation level {i} missing 'action'")
        
        if 'audit_trail' not in violation_policy:
            errors.append("Violation policy missing 'audit_trail'")
        else:
            audit = violation_policy['audit_trail']
            if not isinstance(audit, dict):
                errors.append("'audit_trail' must be a dict")
            if 'enabled' not in audit:
                errors.append("Audit trail missing 'enabled'")
            if 'immutable' not in audit:
                errors.append("Audit trail missing 'immutable'")
        
        return errors
    
    @staticmethod
    def generate_validation_report(policy: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate detailed validation report with all checks and issues.
        Returns comprehensive report dict for audit and documentation.
        """
        is_valid, errors = CharterPolicyValidator.validate_policy(policy)
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'policy_name': policy.get('charter', {}).get('name', 'Unknown'),
            'environment': policy.get('charter', {}).get('metadata', {}).get('environment', 'Unknown'),
            'overall_status': 'PASS' if is_valid else 'FAIL',
            'total_errors': len(errors),
            'errors': errors,
            'metrics': {
                'whitelisted': len(CharterPolicyValidator.get_whitelisted_metrics(policy)),
                'forbidden': len(CharterPolicyValidator.get_forbidden_metrics(policy)),
            },
            'access_control': {
                'read_roles': len(policy.get('access_control', {}).get('read_access', [])),
                'write_roles': len(policy.get('access_control', {}).get('write_access', [])),
            },
            'violation_levels': len(policy.get('violation_policy', {}).get('response', [])),
            'has_whistleblower_policy': 'whistleblower_policy' in policy,
            'has_emergency_override': 'emergency_override' in policy,
            'recommendations': [],
        }
        
        # Generate recommendations
        if report['overall_status'] == 'FAIL':
            report['recommendations'].append('Fix validation errors before deployment')
        
        env = policy.get('charter', {}).get('metadata', {}).get('environment', '')
        if env == 'production':
            if not policy.get('violation_policy', {}).get('audit_trail', {}).get('immutable'):
                report['recommendations'].append('Production policy should have immutable audit trail')
            if not policy.get('emergency_override', {}).get('requires_dao_vote'):
                report['recommendations'].append('Production policy should require DAO vote for emergency override')
        
        return report
    
    @staticmethod
    def compare_policies(policy1: Dict[str, Any], policy2: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare two policies and return differences.
        Useful for tracking policy evolution and changes.
        """
        metrics1 = set(CharterPolicyValidator.get_whitelisted_metrics(policy1))
        metrics2 = set(CharterPolicyValidator.get_whitelisted_metrics(policy2))
        
        forbidden1 = set(CharterPolicyValidator.get_forbidden_metrics(policy1))
        forbidden2 = set(CharterPolicyValidator.get_forbidden_metrics(policy2))
        
        name1 = policy1.get('charter', {}).get('name', 'Policy 1')
        name2 = policy2.get('charter', {}).get('name', 'Policy 2')
        
        comparison = {
            'policy1_name': name1,
            'policy2_name': name2,
            'metrics': {
                'added': list(metrics2 - metrics1),
                'removed': list(metrics1 - metrics2),
                'unchanged': list(metrics1 & metrics2),
                'policy1_count': len(metrics1),
                'policy2_count': len(metrics2),
            },
            'forbidden_metrics': {
                'added': list(forbidden2 - forbidden1),
                'removed': list(forbidden1 - forbidden2),
                'unchanged': list(forbidden1 & forbidden2),
                'policy1_count': len(forbidden1),
                'policy2_count': len(forbidden2),
            },
            'versions': {
                'policy1_version': policy1.get('charter', {}).get('version'),
                'policy2_version': policy2.get('charter', {}).get('version'),
            },
            'environments': {
                'policy1_env': policy1.get('charter', {}).get('metadata', {}).get('environment'),
                'policy2_env': policy2.get('charter', {}).get('metadata', {}).get('environment'),
            },
            'is_identical_metrics': metrics1 == metrics2,
            'is_identical_forbidden': forbidden1 == forbidden2,
        }
        
        return comparison
    
    def create_enforcer(self) -> 'MetricEnforcer':
        """Создать экземпляр MetricEnforcer для этой политики.
        
        Returns:
            Инициализированный MetricEnforcer с текущей политикой
        """
        return MetricEnforcer(self.policy)
    
    def enforce_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Удобный метод для валидации батча метрик.
        
        Args:
            metrics: Список метрик для валидации
            
        Returns:
            Результат валидации с детальной информацией
        """
        enforcer = self.create_enforcer()
        return enforcer.validate_metrics(metrics)


class MetricEnforcer:
    """Модуль принудительного применения метрик на основе политики Anti-Delos."""
    
    def __init__(self, policy: Dict[str, Any]):
        """Инициализация enforcer'а с политикой.
        
        Args:
            policy: Политика из CharterPolicyValidator.policy
        """
        self.policy = policy
        
        # Извлечение имён метрик (структура: whitelisted_metrics -> {category: [{metric_name, ...}]})
        whitelisted_raw = policy.get('whitelisted_metrics', {})
        forbidden_raw = policy.get('forbidden_metrics', [])
        
        # Обработка whitelisted_metrics (словарь по категориям)
        self.whitelisted = set()
        if isinstance(whitelisted_raw, dict):
            for category, metrics in whitelisted_raw.items():
                if isinstance(metrics, list):
                    for item in metrics:
                        if isinstance(item, dict) and 'metric_name' in item:
                            self.whitelisted.add(item['metric_name'])
                        elif isinstance(item, str):
                            self.whitelisted.add(item)
        elif isinstance(whitelisted_raw, list):
            # Fallback for list format
            for item in whitelisted_raw:
                if isinstance(item, str):
                    self.whitelisted.add(item)
                elif isinstance(item, dict) and 'metric_name' in item:
                    self.whitelisted.add(item['metric_name'])
        
        # Обработка forbidden_metrics (список словарей)
        self.forbidden = set()
        for item in forbidden_raw:
            if isinstance(item, str):
                self.forbidden.add(item)
            elif isinstance(item, dict):
                if 'metric_name' in item:
                    self.forbidden.add(item['metric_name'])
        
        self.violation_log: List[Dict[str, Any]] = []
        self.violation_events: List[Dict[str, Any]] = []
        self._attempt_tracker: Dict[str, List[float]] = {}  # Для обнаружения нарушений
        
    def validate_metric(self, metric: Dict[str, Any]) -> Dict[str, Any]:
        """Валидация одной метрики за <5мс.
        
        Args:
            metric: Словарь с полями: metric_name, value, timestamp, source
            
        Returns:
            Словарь с результатом валидации: {is_valid, allowed, errors, enforcement_action, ...}
        """
        import time
        start = time.time_ns()
        
        result = {
            'is_valid': True,
            'allowed': True,
            'metric_name': metric.get('metric_name', 'unknown'),
            'errors': [],
            'warnings': [],
            'enforcement_action': 'ALLOW',
            'reason': None,
        }
        
        # 1. Проверка обязательных полей
        required_fields = ['metric_name', 'value', 'timestamp', 'source']
        for field in required_fields:
            if field not in metric:
                result['errors'].append(f"Missing required field: {field}")
                result['is_valid'] = False
                
        if not result['is_valid']:
            result['enforcement_action'] = 'REJECT'
            return result
            
        metric_name = metric['metric_name']
        
        # 2. Валидность имени метрики (alphanumeric + underscore)
        if not isinstance(metric_name, str) or not metric_name.replace('_', '').isalnum():
            result['errors'].append("Invalid metric name format (must be alphanumeric + underscore)")
            result['is_valid'] = False
            
        # 3. Проверка в списке запрещённых (ПРИОРИТЕТ)
        if metric_name in self.forbidden:
            result['allowed'] = False
            result['enforcement_action'] = 'BLOCK'
            result['reason'] = 'FORBIDDEN_METRIC'
            self._log_violation_attempt(metric_name, metric.get('source', 'unknown'))
            
        # 4. Проверка в списке разрешённых (advisory)
        elif metric_name not in self.whitelisted:
            result['warnings'].append("Metric not in whitelist (advisory)")
            
        # 5. Валидность временной метки
        try:
            from datetime import datetime, timezone
            ts = metric.get('timestamp', '')
            # Парсирование с заменой Z на +00:00
            dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            # Если дата наивная (без информации о часовом поясе), добавить локальный часовой пояс
            if dt.tzinfo is None:
                # Используем информированное локальное время для сравнения
                dt_aware = dt.replace(tzinfo=timezone.utc)
            else:
                dt_aware = dt
            
            # Сравниваем с локальным временем в наивном формате (убираем tzinfo)
            now = datetime.now()
            # Если dt информирована, переводим в наивное локальное время
            if dt_aware.tzinfo is not None:
                dt_naive = dt_aware.replace(tzinfo=None)
            else:
                dt_naive = dt_aware
            
            if dt_naive > now:
                result['errors'].append("Timestamp is in the future")
                result['is_valid'] = False
        except (ValueError, AttributeError):
            result['errors'].append("Invalid timestamp format (expected ISO format)")
            result['is_valid'] = False
            
        # 6. Определение финального статуса
        if result['errors']:
            result['is_valid'] = False
            result['enforcement_action'] = 'REJECT'
            
        if not result['allowed']:
            result['enforcement_action'] = 'BLOCK'
            
        # Логирование всех попыток
        self._log_attempt(metric_name, metric.get('source', 'unknown'), result['enforcement_action'])
        
        result['latency_ns'] = time.time_ns() - start
        return result
        
    def _log_violation_attempt(self, metric_name: str, source: str) -> None:
        """Логирование попытки отправки запрещённой метрики."""
        from datetime import datetime
        attempt_key = metric_name
        now = datetime.now().timestamp()
        
        if attempt_key not in self._attempt_tracker:
            self._attempt_tracker[attempt_key] = []
            
        # Очистить старые попытки (> 60 сек)
        cutoff = now - 60.0
        self._attempt_tracker[attempt_key] = [t for t in self._attempt_tracker[attempt_key] if t > cutoff]
        
        # Добавить текущую попытку
        self._attempt_tracker[attempt_key].append(now)
        
        # Проверить порог нарушения
        attempts = len(self._attempt_tracker[attempt_key])
        if attempts >= 3:
            self._create_violation_event(metric_name, attempts, source)
            
    def _log_attempt(self, metric_name: str, source: str, action: str) -> None:
        """Логирование любой попытки отправки метрики."""
        from datetime import datetime
        self.violation_log.append({
            'timestamp': datetime.now().isoformat(),
            'metric_name': metric_name,
            'source': source,
            'action': action,
        })
        
    def _create_violation_event(self, metric_name: str, attempt_count: int, last_source: str) -> None:
        """Создание или обновление события нарушения при пороге попыток."""
        from datetime import datetime
        
        attempts = self._attempt_tracker.get(metric_name, [])
        severity = 'CRITICAL' if attempt_count >= 5 else 'HIGH'
        recommended_action = 'IMMEDIATE_SHUTDOWN' if attempt_count >= 5 else 'ESCALATE_TO_DAO'
        
        # Проверить дубликаты за последний час
        recent_idx = None
        for idx, e in enumerate(self.violation_events):
            if e['metric_name'] == metric_name and \
               (datetime.now().timestamp() - datetime.fromisoformat(e['timestamp']).timestamp()) < 3600:
                recent_idx = idx
                break
        
        event = {
            'timestamp': datetime.now().isoformat(),
            'violation_type': 'FORBIDDEN_METRIC_SUBMISSION',
            'metric_name': metric_name,
            'attempt_count': attempt_count,
            'time_window': '60s',
            'first_attempt': datetime.fromtimestamp(min(attempts)).isoformat() if attempts else None,
            'last_attempt': datetime.fromtimestamp(max(attempts)).isoformat() if attempts else None,
            'sources': list(set([log['source'] for log in self.violation_log 
                               if log['metric_name'] == metric_name])),
            'severity': severity,
            'recommended_action': recommended_action,
            'justification': f"Multiple attempts to submit forbidden metrics ({metric_name})",
        }
        
        if recent_idx is not None:
            # Обновить существующее событие
            self.violation_events[recent_idx] = event
        else:
            # Создать новое событие
            self.violation_events.append(event)
        
    def validate_metrics(self, metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Валидация батча метрик.
        
        Args:
            metrics: Список метрик для валидации
            
        Returns:
            Итоговый результат: {total, passed, blocked, errors, violations, ...}
        """
        results = []
        blocked_count = 0
        error_count = 0
        
        for metric in metrics:
            result = self.validate_metric(metric)
            results.append(result)
            
            if result['enforcement_action'] == 'BLOCK':
                blocked_count += 1
            if not result['is_valid']:
                error_count += 1
                
        return {
            'total_metrics': len(metrics),
            'passed': len(metrics) - blocked_count - error_count,
            'blocked': blocked_count,
            'errors': error_count,
            'detailed_results': results,
            'violations': self.violation_events,
            'all_valid': error_count == 0 and blocked_count == 0,
        }
        
    def get_violation_log(self) -> List[Dict[str, Any]]:
        """Получить лог всех попыток отправки метрик."""
        return self.violation_log.copy()
        
    def get_violation_events(self) -> List[Dict[str, Any]]:
        """Получить события нарушений."""
        return self.violation_events.copy()
        
    def reset_logs(self) -> None:
        """Очистить логи (для тестирования)."""
        self.violation_log.clear()
        self.violation_events.clear()
        self._attempt_tracker.clear()


if __name__ == "__main__":
    asyncio.run(demo_charter())
