"""
SQLAlchemy models for Geo-Leak Detector
"""
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional, List

from sqlalchemy import (
    Column, String, DateTime, Float, Integer, 
    Boolean, Text, JSON, ForeignKey, Index, Enum as SQLEnum
)
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import declarative_base, sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID, INET
import uuid

from config.settings import settings


Base = declarative_base()


class LeakSeverity(str, PyEnum):
    """Leak severity levels"""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class LeakType(str, PyEnum):
    """Types of geolocation leaks"""
    IP_LEAK = "ip_leak"
    DNS_LEAK = "dns_leak"
    WEBRTC_LEAK = "webrtc_leak"
    GEOLOCATION_LEAK = "geolocation_leak"
    FINGERPRINT_LEAK = "fingerprint_leak"
    TIMEZONE_LEAK = "timezone_leak"
    WEBGL_LEAK = "webgl_leak"
    FONT_LEAK = "font_leak"
    CANVAS_LEAK = "canvas_leak"
    IPV6_LEAK = "ipv6_leak"


class RemediationStatus(str, PyEnum):
    """Remediation action status"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


class LeakEvent(Base):
    """Model for detected leak events"""
    __tablename__ = "leak_events"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    leak_type = Column(SQLEnum(LeakType), nullable=False, index=True)
    severity = Column(SQLEnum(LeakSeverity), nullable=False, index=True)
    message = Column(Text, nullable=False)
    detected_value = Column(Text, nullable=False)
    expected_value = Column(Text, nullable=True)
    source_ip = Column(String(45), nullable=True, index=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    
    # Geolocation data
    detected_country = Column(String(2), nullable=True)
    detected_city = Column(String(100), nullable=True)
    detected_isp = Column(String(255), nullable=True)
    
    # Remediation
    remediation_action = Column(Text, nullable=True)
    remediation_status = Column(SQLEnum(RemediationStatus), default=RemediationStatus.PENDING)
    remediation_timestamp = Column(DateTime, nullable=True)
    remediation_result = Column(Text, nullable=True)
    
    # Resolution tracking
    resolved = Column(Boolean, default=False, index=True)
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(String(100), nullable=True)
    
    # Metadata
    check_source = Column(String(50), nullable=True)  # Which check detected it
    raw_data = Column(JSON, nullable=True)  # Full response data
    
    # Relationships
    alerts = relationship("AlertLog", back_populates="leak_event", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_leak_events_timestamp', 'timestamp'),
        Index('idx_leak_events_type_severity', 'leak_type', 'severity'),
        Index('idx_leak_events_resolved', 'resolved'),
    )
    
    def to_dict(self) -> dict:
        return {
            "id": str(self.id),
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "leak_type": self.leak_type.value if self.leak_type else None,
            "severity": self.severity.value if self.severity else None,
            "message": self.message,
            "detected_value": self.detected_value,
            "expected_value": self.expected_value,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "detected_country": self.detected_country,
            "detected_city": self.detected_city,
            "detected_isp": self.detected_isp,
            "remediation_action": self.remediation_action,
            "remediation_status": self.remediation_status.value if self.remediation_status else None,
            "remediation_timestamp": self.remediation_timestamp.isoformat() if self.remediation_timestamp else None,
            "remediation_result": self.remediation_result,
            "resolved": self.resolved,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolved_by": self.resolved_by,
            "check_source": self.check_source,
            "raw_data": self.raw_data,
        }


class AlertLog(Base):
    """Model for alert delivery log"""
    __tablename__ = "alert_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    leak_event_id = Column(UUID(as_uuid=True), ForeignKey("leak_events.id"), nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    channel = Column(String(50), nullable=False)  # telegram, webhook, email
    status = Column(String(20), nullable=False)  # sent, failed, pending
    response_code = Column(Integer, nullable=True)
    response_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Relationships
    leak_event = relationship("LeakEvent", back_populates="alerts")
    
    __table_args__ = (
        Index('idx_alert_logs_event', 'leak_event_id'),
        Index('idx_alert_logs_timestamp', 'timestamp'),
    )


class DetectionStatus(Base):
    """Model for tracking detection system status"""
    __tablename__ = "detection_status"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    check_type = Column(String(50), nullable=False)  # ip, dns, webrtc, etc.
    status = Column(String(20), nullable=False)  # ok, warning, error
    response_time_ms = Column(Float, nullable=True)
    error_message = Column(Text, nullable=True)
    
    __table_args__ = (
        Index('idx_detection_status_timestamp', 'timestamp'),
        Index('idx_detection_status_type', 'check_type'),
    )


class SystemConfig(Base):
    """Model for system configuration"""
    __tablename__ = "system_config"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(String(100), nullable=True)
    
    __table_args__ = (
        Index('idx_system_config_key', 'key'),
    )


class MAPEKIntegrationLog(Base):
    """Model for MAPE-K integration events"""
    __tablename__ = "mapek_integration_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    event_type = Column(String(50), nullable=False)  # monitor, analyze, plan, execute, knowledge
    consciousness_state = Column(String(50), nullable=True)
    phi_ratio = Column(Float, nullable=True)
    data = Column(JSON, nullable=True)
    
    __table_args__ = (
        Index('idx_mapek_logs_timestamp', 'timestamp'),
        Index('idx_mapek_logs_event_type', 'event_type'),
    )


# Database engine and session
engine = create_async_engine(
    settings.database.async_url,
    echo=settings.api.debug,
    future=True,
)

async_session_maker = sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)


async def init_db():
    """Initialize database tables"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_db() -> AsyncSession:
    """Dependency for getting database session"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
