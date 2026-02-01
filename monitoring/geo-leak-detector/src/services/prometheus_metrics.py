"""
Prometheus Metrics for Geo-Leak Detector
Exports metrics for monitoring and alerting
"""
from prometheus_client import Counter, Gauge, Histogram, Info, generate_latest
from prometheus_client.core import CollectorRegistry
from typing import Optional
import time

from config.settings import settings


class GeoLeakMetrics:
    """Prometheus metrics collector for Geo-Leak Detector"""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        
        # Info metric
        self.info = Info(
            'geo_leak_detector',
            'Geo-Leak Detector information',
            registry=self.registry
        )
        self.info.info({
            'version': settings.version,
            'environment': settings.environment,
            'node_id': settings.mapek.node_id
        })
        
        # Leak counters by type
        self.leaks_total = Counter(
            'geo_leak_detector_leaks_total',
            'Total number of detected leaks',
            ['leak_type', 'severity'],
            registry=self.registry
        )
        
        # Leak counter by country (for geo analysis)
        self.leaks_by_country = Counter(
            'geo_leak_detector_leaks_by_country',
            'Detected leaks by country',
            ['country', 'leak_type'],
            registry=self.registry
        )
        
        # Current status gauges
        self.detector_running = Gauge(
            'geo_leak_detector_running',
            'Whether the detector is running (1) or not (0)',
            registry=self.registry
        )
        
        self.last_check_timestamp = Gauge(
            'geo_leak_detector_last_check_timestamp',
            'Timestamp of the last check',
            registry=self.registry
        )
        
        self.total_leaks_detected = Gauge(
            'geo_leak_detector_total_leaks',
            'Total number of leaks detected (current session)',
            registry=self.registry
        )
        
        self.unresolved_leaks = Gauge(
            'geo_leak_detector_unresolved_leaks',
            'Number of unresolved leaks',
            registry=self.registry
        )
        
        # Check performance metrics
        self.check_duration = Histogram(
            'geo_leak_detector_check_duration_seconds',
            'Duration of leak checks',
            ['check_type'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.check_errors = Counter(
            'geo_leak_detector_check_errors_total',
            'Total number of check errors',
            ['check_type', 'error_type'],
            registry=self.registry
        )
        
        # Remediation metrics
        self.remediation_actions_total = Counter(
            'geo_leak_detector_remediation_actions_total',
            'Total number of remediation actions',
            ['action_type', 'status'],
            registry=self.registry
        )
        
        self.killswitch_triggered = Counter(
            'geo_leak_detector_killswitch_triggered_total',
            'Number of times kill-switch was triggered',
            ['leak_type'],
            registry=self.registry
        )
        
        # Alert metrics
        self.alerts_sent_total = Counter(
            'geo_leak_detector_alerts_sent_total',
            'Total number of alerts sent',
            ['channel', 'severity', 'status'],
            registry=self.registry
        )
        
        # MAPE-K integration metrics
        self.mapek_events_total = Counter(
            'geo_leak_detector_mapek_events_total',
            'Total MAPE-K integration events',
            ['event_type'],
            registry=self.registry
        )
        
        self.mapek_phi_ratio = Gauge(
            'geo_leak_detector_mapek_phi_ratio',
            'Current consciousness phi ratio from MAPE-K',
            registry=self.registry
        )
        
        # Detection status by type
        self.detection_status = Gauge(
            'geo_leak_detector_status',
            'Status of each detector (1=ok, 0=error)',
            ['detector_type'],
            registry=self.registry
        )
        
        # Redis connection status
        self.redis_connected = Gauge(
            'geo_leak_detector_redis_connected',
            'Redis connection status (1=connected, 0=disconnected)',
            registry=self.registry
        )
        
        # Database connection status
        self.database_connected = Gauge(
            'geo_leak_detector_database_connected',
            'Database connection status (1=connected, 0=disconnected)',
            registry=self.registry
        )
    
    def record_leak(self, leak_type: str, severity: str, country: Optional[str] = None):
        """Record a detected leak"""
        self.leaks_total.labels(
            leak_type=leak_type,
            severity=severity
        ).inc()
        
        if country:
            self.leaks_by_country.labels(
                country=country,
                leak_type=leak_type
            ).inc()
    
    def record_check_duration(self, check_type: str, duration_seconds: float):
        """Record check duration"""
        self.check_duration.labels(check_type=check_type).observe(duration_seconds)
    
    def record_check_error(self, check_type: str, error_type: str):
        """Record a check error"""
        self.check_errors.labels(
            check_type=check_type,
            error_type=error_type
        ).inc()
    
    def record_remediation(self, action_type: str, success: bool):
        """Record a remediation action"""
        status = 'success' if success else 'failed'
        self.remediation_actions_total.labels(
            action_type=action_type,
            status=status
        ).inc()
    
    def record_killswitch(self, leak_type: str):
        """Record kill-switch trigger"""
        self.killswitch_triggered.labels(leak_type=leak_type).inc()
    
    def record_alert(self, channel: str, severity: str, success: bool):
        """Record an alert"""
        status = 'sent' if success else 'failed'
        self.alerts_sent_total.labels(
            channel=channel,
            severity=severity,
            status=status
        ).inc()
    
    def record_mapek_event(self, event_type: str):
        """Record a MAPE-K integration event"""
        self.mapek_events_total.labels(event_type=event_type).inc()
    
    def update_detector_status(self, running: bool):
        """Update detector running status"""
        self.detector_running.set(1 if running else 0)
    
    def update_last_check(self):
        """Update last check timestamp"""
        self.last_check_timestamp.set(time.time())
    
    def update_total_leaks(self, count: int):
        """Update total leaks count"""
        self.total_leaks_detected.set(count)
    
    def update_unresolved_leaks(self, count: int):
        """Update unresolved leaks count"""
        self.unresolved_leaks.set(count)
    
    def update_mapek_phi(self, phi_ratio: float):
        """Update MAPE-K phi ratio"""
        self.mapek_phi_ratio.set(phi_ratio)
    
    def update_detection_status(self, detector_type: str, ok: bool):
        """Update detection status for a specific detector"""
        self.detection_status.labels(detector_type=detector_type).set(1 if ok else 0)
    
    def update_redis_status(self, connected: bool):
        """Update Redis connection status"""
        self.redis_connected.set(1 if connected else 0)
    
    def update_database_status(self, connected: bool):
        """Update database connection status"""
        self.database_connected.set(1 if connected else 0)
    
    def get_metrics(self) -> bytes:
        """Get metrics in Prometheus format"""
        return generate_latest(self.registry)


# Global metrics instance
metrics = GeoLeakMetrics()
