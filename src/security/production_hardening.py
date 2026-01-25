import logging
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Any
from collections import defaultdict, deque
import json

logger = logging.getLogger(__name__)


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
    
    def store_secret(self, key: str, value: str, rotation_days: int = 90) -> None:
        with self.lock:
            self.secrets[key] = {
                "value": hashlib.sha256(value.encode()).hexdigest()[:32],
                "created_at": datetime.utcnow().isoformat(),
                "rotation_days": rotation_days,
            }
    
    def retrieve_secret(self, key: str, accessor: str = "unknown") -> Optional[str]:
        with self.lock:
            if key not in self.secrets:
                return None
            return self.secrets[key]["value"]
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        with self.lock:
            if key not in self.secrets:
                return False
            self.secrets[key]["value"] = hashlib.sha256(new_value.encode()).hexdigest()[:32]
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
        except:
            return False
    
    def validate_ipv4(self, value: str) -> bool:
        parts = value.split('.')
        if len(parts) != 4:
            return False
        for part in parts:
            try:
                num = int(part)
                if num < 0 or num > 255:
                    return False
            except:
                return False
        return True


class RequestAuditor:
    def __init__(self):
        self.requests: deque = deque(maxlen=10000)
        self.violations: List[SecurityViolation] = []
        self.lock = threading.Lock()
    
    def log_request(self, method: str, path: str, client_ip: str, 
                   status_code: int, duration_ms: float) -> None:
        with self.lock:
            self.requests.append({
                "method": method,
                "path": path,
                "client_ip": client_ip,
                "status_code": status_code,
                "duration_ms": duration_ms,
                "timestamp": datetime.utcnow().isoformat()
            })
    
    def detect_suspicious_patterns(self) -> List[Dict]:
        with self.lock:
            suspicious = []
            requests_by_ip = defaultdict(list)
            for req in self.requests:
                requests_by_ip[req["client_ip"]].append(req)
            
            for ip, reqs in requests_by_ip.items():
                if len(reqs) > 100:
                    suspicious.append({
                        "type": "high_request_rate",
                        "ip": ip,
                        "count": len(reqs)
                    })
            return suspicious


class ProductionHardeningManager:
    def __init__(self):
        self.secret_vault = SecretVaultManager()
        self.rate_limiter = RateLimiter()
        self.input_validator = InputValidator()
        self.request_auditor = RequestAuditor()
    
    def get_security_status(self) -> Dict:
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "suspicious_patterns": self.request_auditor.detect_suspicious_patterns(),
        }


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
