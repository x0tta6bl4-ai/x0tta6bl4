import hashlib
import json
import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.core.agent_thinking import AgentThinkingCoach

logger = logging.getLogger(__name__)


def _safe_hash(value: object) -> str:
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _safe_count_bucket(value: int) -> str:
    if value <= 0:
        return "0"
    if value <= 3:
        return "1-3"
    if value <= 10:
        return "4-10"
    if value <= 100:
        return "11-100"
    if value <= 1000:
        return "101-1000"
    return "1000+"


def _safe_number_band(value: object) -> str:
    if not isinstance(value, (int, float)):
        return "non_numeric"
    if value < 0:
        return "negative"
    if value == 0:
        return "0"
    if value <= 1:
        return "0-1"
    if value <= 10:
        return "1-10"
    if value <= 100:
        return "10-100"
    if value <= 1000:
        return "100-1000"
    return "1000+"


@dataclass
class SecurityViolation:
    timestamp: datetime
    violation_type: str
    severity: str
    description: str
    source: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RateLimitPolicy:
    max_requests: int
    window_seconds: int
    burst_size: int = 0


class SecretVaultManager:
    def __init__(self):
        self.secrets: Dict[str, str] = {}
        self.access_log: List[Dict] = []
        self.lock = threading.Lock()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="production-secret-vault-manager",
            role="security",
            capabilities=("zero-trust", "ops"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "production_secret_vault_init",
                "goal": "Initialize local production secret vault safely",
                "signals": {"secret_count_bucket": "0"},
                "safety_boundary": (
                    "Keep raw secret keys, values, accessors, and hashed stored "
                    "secret values out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_secret_keys": True,
                    "redact_secret_values": True,
                    "redact_stored_hashes": True,
                    "redact_accessors": True,
                    "preserve_secret_operation_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and rotation bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def store_secret(self, key: str, value: str, rotation_days: int = 90) -> None:
        with self.lock:
            self.secrets[key] = {
                "value": hashlib.sha256(value.encode()).hexdigest()[:32],
                "created_at": datetime.utcnow().isoformat(),
                "rotation_days": rotation_days,
            }
            self._record_thinking(
                "production_secret_stored",
                "Store local production secret safely",
                {
                    "secret_key_hash": _safe_hash(key),
                    "secret_value_length_band": _safe_number_band(len(value)),
                    "rotation_days_band": _safe_number_band(rotation_days),
                    "secret_count_bucket": _safe_count_bucket(len(self.secrets)),
                },
            )

    def retrieve_secret(self, key: str, accessor: str = "unknown") -> Optional[str]:
        with self.lock:
            if key not in self.secrets:
                self._record_thinking(
                    "production_secret_retrieved",
                    "Report missing local production secret safely",
                    {
                        "secret_key_hash": _safe_hash(key),
                        "accessor_hash": _safe_hash(accessor),
                        "hit": False,
                    },
                )
                return None
            value = self.secrets[key]["value"]
            self._record_thinking(
                "production_secret_retrieved",
                "Retrieve local production secret safely",
                {
                    "secret_key_hash": _safe_hash(key),
                    "accessor_hash": _safe_hash(accessor),
                    "hit": True,
                    "stored_value_present": bool(value),
                },
            )
            return value

    def rotate_secret(self, key: str, new_value: str) -> bool:
        with self.lock:
            if key not in self.secrets:
                self._record_thinking(
                    "production_secret_rotation_failed",
                    "Report missing secret rotation safely",
                    {"secret_key_hash": _safe_hash(key), "hit": False},
                )
                return False
            self.secrets[key]["value"] = hashlib.sha256(new_value.encode()).hexdigest()[
                :32
            ]
            self._record_thinking(
                "production_secret_rotated",
                "Rotate local production secret safely",
                {
                    "secret_key_hash": _safe_hash(key),
                    "new_value_length_band": _safe_number_band(len(new_value)),
                    "success": True,
                },
            )
            return True


class RateLimiter:
    def __init__(self):
        self.policies: Dict[str, RateLimitPolicy] = {}
        self.buckets: Dict[str, deque] = defaultdict(deque)
        self.lock = threading.Lock()

    def set_policy(self, resource: str, policy: RateLimitPolicy) -> None:
        with self.lock:
            self.policies[resource] = policy

    def is_allowed(self, resource: str, client_id: str) -> bool:
        with self.lock:
            if resource not in self.policies:
                return True
            policy = self.policies[resource]
            bucket_key = f"{resource}:{client_id}"
            bucket = self.buckets[bucket_key]

            now = datetime.utcnow().timestamp()
            while bucket and bucket[0] < now - policy.window_seconds:
                bucket.popleft()

            if len(bucket) < policy.max_requests:
                bucket.append(now)
                return True
            return False


class InputValidator:
    def __init__(self, max_string_length: int = 10000, max_array_length: int = 1000):
        self.max_string_length = max_string_length
        self.max_array_length = max_array_length
        self.validation_failures: List[Dict] = []
        self.lock = threading.Lock()

    def validate_string(self, value: str, max_length: Optional[int] = None) -> bool:
        limit = max_length or self.max_string_length
        if not isinstance(value, str) or len(value) > limit:
            return False
        return True

    def validate_array(self, value: List, max_length: Optional[int] = None) -> bool:
        limit = max_length or self.max_array_length
        if not isinstance(value, list) or len(value) > limit:
            return False
        return True

    def validate_json(self, value: str) -> bool:
        try:
            json.loads(value)
            return True
        except Exception:
            return False

    def validate_ipv4(self, value: str) -> bool:
        parts = value.split(".")
        if len(parts) != 4:
            return False
        for part in parts:
            try:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            except Exception:
                return False
        return True


class RequestAuditor:
    def __init__(self):
        self.requests: deque = deque(maxlen=10000)
        self.violations: List[SecurityViolation] = []
        self.lock = threading.Lock()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="production-request-auditor",
            role="security",
            capabilities=("monitoring", "ops", "zero-trust"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "production_request_auditor_init",
                "goal": "Initialize request auditing safely",
                "signals": {"request_count_bucket": "0", "violation_count_bucket": "0"},
                "safety_boundary": (
                    "Keep raw request paths, client IPs, descriptions, and metadata "
                    "out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_request_paths": True,
                    "redact_client_ips": True,
                    "redact_descriptions": True,
                    "redact_metadata": True,
                    "preserve_audit_decision": True,
                },
                "safety_boundary": "Use hashes, counts, status bands, and duration bands.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def log_request(
        self,
        method: str,
        path: str,
        client_ip: str,
        status_code: int,
        duration_ms: float,
    ) -> None:
        with self.lock:
            self.requests.append(
                {
                    "method": method,
                    "path": path,
                    "client_ip": client_ip,
                    "status_code": status_code,
                    "duration_ms": duration_ms,
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )
            self._record_thinking(
                "production_request_logged",
                "Log production request safely",
                {
                    "method_hash": _safe_hash(method),
                    "path_hash": _safe_hash(path),
                    "client_ip_hash": _safe_hash(client_ip),
                    "status_code_band": _safe_number_band(status_code),
                    "duration_band": _safe_number_band(duration_ms),
                    "request_count_bucket": _safe_count_bucket(len(self.requests)),
                },
            )

    def detect_suspicious_patterns(self) -> List[Dict]:
        with self.lock:
            suspicious = []
            requests_by_ip = defaultdict(list)
            for req in self.requests:
                requests_by_ip[req["client_ip"]].append(req)

            for ip, reqs in requests_by_ip.items():
                if len(reqs) > 100:
                    suspicious.append(
                        {"type": "high_request_rate", "ip": ip, "count": len(reqs)}
                    )
            self._record_thinking(
                "production_suspicious_patterns_detected",
                "Detect suspicious request patterns safely",
                {
                    "request_count_bucket": _safe_count_bucket(len(self.requests)),
                    "client_count_bucket": _safe_count_bucket(len(requests_by_ip)),
                    "suspicious_count_bucket": _safe_count_bucket(len(suspicious)),
                    "suspicious_type_counts": {
                        item["type"]: _safe_count_bucket(int(item["count"]))
                        for item in suspicious[:20]
                    },
                },
            )
            return suspicious


class ProductionHardeningManager:
    def __init__(self):
        self.secret_vault = SecretVaultManager()
        self.rate_limiter = RateLimiter()
        self.input_validator = InputValidator()
        self.request_auditor = RequestAuditor()
        self.thinking_coach = AgentThinkingCoach(
            agent_id="production-hardening-manager",
            role="security",
            capabilities=("monitoring", "ops", "zero-trust"),
        )
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": "production_hardening_manager_init",
                "goal": "Initialize production hardening controls safely",
                "signals": {
                    "secret_vault_present": True,
                    "rate_limiter_present": True,
                    "input_validator_present": True,
                    "request_auditor_present": True,
                },
                "safety_boundary": (
                    "Keep raw secrets, request paths, client IPs, and violation "
                    "metadata out of thinking context."
                ),
            }
        )

    def _record_thinking(
        self,
        task_type: str,
        goal: str,
        signals: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        self.last_thinking_context = self.thinking_coach.prepare_task(
            {
                "task_type": task_type,
                "goal": goal,
                "signals": signals or {},
                "constraints": {
                    "redact_secrets": True,
                    "redact_request_paths": True,
                    "redact_client_ips": True,
                    "redact_violation_metadata": True,
                    "preserve_hardening_decision": True,
                },
                "safety_boundary": "Use hashes, counts, booleans, and control status.",
            }
        )
        return self.last_thinking_context

    def get_thinking_status(self) -> Dict[str, Any]:
        return {
            "thinking": self.thinking_coach.status(),
            "last_thinking_context": self.last_thinking_context,
        }

    def get_security_status(self) -> Dict:
        suspicious_patterns = self.request_auditor.detect_suspicious_patterns()
        status = {
            "timestamp": datetime.utcnow().isoformat(),
            "suspicious_patterns": suspicious_patterns,
        }
        self._record_thinking(
            "production_security_status_reported",
            "Report production hardening status safely",
            {
                "suspicious_count_bucket": _safe_count_bucket(
                    len(suspicious_patterns)
                ),
                "secret_count_bucket": _safe_count_bucket(
                    len(self.secret_vault.secrets)
                ),
                "policy_count_bucket": _safe_count_bucket(
                    len(self.rate_limiter.policies)
                ),
            },
        )
        return status


_manager = None


def get_hardening_manager() -> ProductionHardeningManager:
    global _manager
    if _manager is None:
        _manager = ProductionHardeningManager()
    return _manager


__all__ = [
    "SecurityViolation",
    "RateLimitPolicy",
    "SecretVaultManager",
    "RateLimiter",
    "InputValidator",
    "RequestAuditor",
    "ProductionHardeningManager",
    "get_hardening_manager",
]
