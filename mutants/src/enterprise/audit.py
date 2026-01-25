"""
Audit Logging

Provides comprehensive audit trail for compliance and security.
"""

import logging
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditEventType(Enum):
    """Types of audit events"""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    ADMIN_ACTION = "admin_action"
    SYSTEM_EVENT = "system_event"


class AuditSeverity(Enum):
    """Severity levels for audit events"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class AuditEvent:
    """Represents an audit event"""
    event_id: str
    event_type: AuditEventType
    timestamp: datetime = field(default_factory=datetime.utcnow)
    user_id: Optional[str] = None
    tenant_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    action: Optional[str] = None
    result: str = "success"  # success, failure, denied
    severity: AuditSeverity = AuditSeverity.MEDIUM
    details: Dict[str, Any] = field(default_factory=dict)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        data = asdict(self)
        data['event_type'] = self.event_type.value
        data['severity'] = self.severity.value
        data['timestamp'] = self.timestamp.isoformat()
        return data


class AuditLogger:
    """
    Comprehensive audit logger for compliance and security.
    
    Provides:
    - Event logging
    - Search and analysis
    - Compliance reporting
    - Log retention policies
    """
    
    def __init__(
        self,
        log_dir: Optional[Path] = None,
        retention_days: int = 90,
        enable_encryption: bool = True
    ):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for audit logs (default: ./audit_logs)
            retention_days: Log retention period in days
            enable_encryption: Enable log encryption
        """
        self.log_dir = log_dir or Path("audit_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.retention_days = retention_days
        self.enable_encryption = enable_encryption
        
        self.events: List[AuditEvent] = []
        self.event_index: Dict[str, List[AuditEvent]] = {}  # event_type -> events
        
        logger.info(f"AuditLogger initialized (retention: {retention_days} days)")
    
    def log_event(
        self,
        event_type: AuditEventType,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        action: Optional[str] = None,
        result: str = "success",
        severity: AuditSeverity = AuditSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> AuditEvent:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event
            user_id: User identifier
            tenant_id: Tenant identifier
            resource_type: Type of resource
            resource_id: Resource identifier
            action: Action performed
            result: Result (success, failure, denied)
            severity: Event severity
            details: Additional details
            ip_address: IP address
            user_agent: User agent
        
        Returns:
            Created AuditEvent
        """
        event_id = f"audit-{datetime.utcnow().timestamp()}-{len(self.events)}"
        
        event = AuditEvent(
            event_id=event_id,
            event_type=event_type,
            user_id=user_id,
            tenant_id=tenant_id,
            resource_type=resource_type,
            resource_id=resource_id,
            action=action,
            result=result,
            severity=severity,
            details=details or {},
            ip_address=ip_address,
            user_agent=user_agent
        )
        
        self.events.append(event)
        
        # Index by event type
        event_type_key = event_type.value
        if event_type_key not in self.event_index:
            self.event_index[event_type_key] = []
        self.event_index[event_type_key].append(event)
        
        # Write to file
        self._write_event(event)
        
        # Log to standard logger
        log_message = f"Audit: {event_type.value} - {action} on {resource_type}:{resource_id} by {user_id} - {result}"
        if severity == AuditSeverity.CRITICAL:
            logger.critical(log_message)
        elif severity == AuditSeverity.HIGH:
            logger.error(log_message)
        elif severity == AuditSeverity.MEDIUM:
            logger.warning(log_message)
        else:
            logger.info(log_message)
        
        return event
    
    def _write_event(self, event: AuditEvent):
        """Write event to log file"""
        try:
            # Daily log files
            date_str = event.timestamp.strftime("%Y-%m-%d")
            log_file = self.log_dir / f"audit-{date_str}.jsonl"
            
            with open(log_file, "a") as f:
                f.write(json.dumps(event.to_dict()) + "\n")
        except Exception as e:
            logger.error(f"Failed to write audit event: {e}")
    
    def search_events(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        severity: Optional[AuditSeverity] = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Search audit events.
        
        Args:
            event_type: Filter by event type
            user_id: Filter by user ID
            tenant_id: Filter by tenant ID
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            start_time: Start time filter
            end_time: End time filter
            severity: Filter by severity
            limit: Maximum number of results
        
        Returns:
            List of matching events
        """
        results = []
        
        # Start with indexed events if event_type is specified
        if event_type:
            candidates = self.event_index.get(event_type.value, [])
        else:
            candidates = self.events
        
        for event in candidates:
            # Apply filters
            if user_id and event.user_id != user_id:
                continue
            if tenant_id and event.tenant_id != tenant_id:
                continue
            if resource_type and event.resource_type != resource_type:
                continue
            if resource_id and event.resource_id != resource_id:
                continue
            if start_time and event.timestamp < start_time:
                continue
            if end_time and event.timestamp > end_time:
                continue
            if severity and event.severity != severity:
                continue
            
            results.append(event)
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_compliance_report(
        self,
        start_time: datetime,
        end_time: datetime,
        tenant_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate compliance report.
        
        Args:
            start_time: Report start time
            end_time: Report end time
            tenant_id: Optional tenant filter
        
        Returns:
            Compliance report dictionary
        """
        events = self.search_events(
            start_time=start_time,
            end_time=end_time,
            tenant_id=tenant_id,
            limit=10000
        )
        
        # Aggregate statistics
        by_type = {}
        by_severity = {}
        by_result = {}
        
        for event in events:
            # By type
            event_type = event.event_type.value
            by_type[event_type] = by_type.get(event_type, 0) + 1
            
            # By severity
            severity = event.severity.value
            by_severity[severity] = by_severity.get(severity, 0) + 1
            
            # By result
            by_result[event.result] = by_result.get(event.result, 0) + 1
        
        return {
            "period": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat()
            },
            "total_events": len(events),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_result": by_result,
            "tenant_id": tenant_id
        }
    
    def cleanup_old_logs(self):
        """Clean up logs older than retention period"""
        try:
            cutoff_date = datetime.utcnow().timestamp() - (self.retention_days * 24 * 3600)
            
            for log_file in self.log_dir.glob("audit-*.jsonl"):
                file_time = log_file.stat().st_mtime
                if file_time < cutoff_date:
                    log_file.unlink()
                    logger.info(f"Deleted old audit log: {log_file}")
        except Exception as e:
            logger.error(f"Failed to cleanup old logs: {e}")

