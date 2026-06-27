"""
MAPE-K Integration for Geo-Leak Detector
Integrates with x0tta6bl4's existing MAPE-K architecture
"""
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from dataclasses import dataclass

import aiohttp
import structlog

from config.settings import settings
from src.models.database import async_session_maker, MAPEKIntegrationLog


logger = structlog.get_logger()


@dataclass
class MAPEKEvent:
    """MAPE-K event data structure"""
    event_type: str  # monitor, analyze, plan, execute, knowledge
    consciousness_state: Optional[str] = None
    phi_ratio: Optional[float] = None
    node_id: str = "geo-leak-detector"
    data: Optional[Dict[str, Any]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "consciousness_state": self.consciousness_state,
            "phi_ratio": self.phi_ratio,
            "node_id": self.node_id,
            "data": self.data,
            "timestamp": self.timestamp.isoformat()
        }


class MAPEKIntegration:
    """
    Integration with x0tta6bl4's MAPE-K architecture
    
    This class provides bidirectional communication between the
    Geo-Leak Detector and the existing MAPE-K loop in x0tta6bl4.
    """
    
    def __init__(self):
        self.enabled = settings.mapek.enabled
        self.node_id = settings.mapek.node_id
        self.api_endpoint = settings.mapek.api_endpoint
        self.consciousness_threshold = settings.mapek.consciousness_threshold
        
        self.logger = structlog.get_logger().bind(component="mapek_integration")
        
        # Event callbacks
        self.on_consciousness_change: Optional[callable] = None
        self.on_phi_threshold_crossed: Optional[callable] = None
    
    async def report_to_mapek(self, event: MAPEKEvent) -> bool:
        """
        Report an event to the MAPE-K system
        
        Args:
            event: The MAPE-K event to report
            
        Returns:
            True if successful, False otherwise
        """
        if not self.enabled:
            return False
        
        try:
            # Store locally first
            await self._store_event(event)
            
            # Send to external MAPE-K API if configured
            if self.api_endpoint:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.api_endpoint}/report",
                        json=event.to_dict(),
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as resp:
                        if resp.status == 200:
                            self.logger.debug(
                                "Event reported to MAPE-K",
                                event_type=event.event_type
                            )
                            return True
                        else:
                            self.logger.warning(
                                "Failed to report to MAPE-K",
                                status=resp.status,
                                event_type=event.event_type
                            )
                            return False
            
            return True
            
        except Exception as e:
            self.logger.error(
                "Error reporting to MAPE-K",
                error=str(e),
                event_type=event.event_type
            )
            return False
    
    async def _store_event(self, event: MAPEKEvent):
        """Store event in local database"""
        try:
            async with async_session_maker() as session:
                log_entry = MAPEKIntegrationLog(
                    event_type=event.event_type,
                    consciousness_state=event.consciousness_state,
                    phi_ratio=event.phi_ratio,
                    data=event.data
                )
                session.add(log_entry)
                await session.commit()
        except Exception as e:
            self.logger.error("Failed to store MAPE-K event", error=str(e))
    
    async def fetch_consciousness_state(self) -> Optional[Dict[str, Any]]:
        """
        Fetch current consciousness state from MAPE-K
        
        Returns:
            Consciousness state data or None
        """
        if not self.enabled or not self.api_endpoint:
            return None
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.api_endpoint}/consciousness/state",
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.logger.debug(
                            "Fetched consciousness state",
                            state=data.get("state"),
                            phi=data.get("phi_ratio")
                        )
                        return data
                    else:
                        self.logger.warning(
                            "Failed to fetch consciousness state",
                            status=resp.status
                        )
                        return None
                        
        except Exception as e:
            self.logger.error(
                "Error fetching consciousness state",
                error=str(e)
            )
            return None
    
    async def report_leak_to_mapek(self, leak_data: Dict[str, Any]):
        """
        Report a detected leak to MAPE-K for analysis
        
        Args:
            leak_data: Leak event data
        """
        event = MAPEKEvent(
            event_type="analyze",
            node_id=self.node_id,
            data={
                "type": "leak_detected",
                "leak": leak_data,
                "requires_attention": True,
                "severity": leak_data.get("severity", "unknown")
            }
        )
        
        await self.report_to_mapek(event)
    
    async def report_remediation_to_mapek(self, remediation_data: Dict[str, Any]):
        """
        Report a remediation action to MAPE-K
        
        Args:
            remediation_data: Remediation action data
        """
        event = MAPEKEvent(
            event_type="execute",
            node_id=self.node_id,
            data={
                "type": "remediation_executed",
                "remediation": remediation_data
            }
        )
        
        await self.report_to_mapek(event)
    
    async def report_status_to_mapek(self, status_data: Dict[str, Any]):
        """
        Report current status to MAPE-K
        
        Args:
            status_data: Status data
        """
        event = MAPEKEvent(
            event_type="monitor",
            node_id=self.node_id,
            data={
                "type": "status_report",
                "status": status_data
            }
        )
        
        await self.report_to_mapek(event)
    
    async def handle_consciousness_directive(self, directive: Dict[str, Any]):
        """
        Handle a directive from MAPE-K based on consciousness state
        
        Args:
            directive: Directive from MAPE-K
        """
        action = directive.get("action")
        
        if action == "increase_monitoring":
            self.logger.info("MAPE-K directive: Increase monitoring frequency")
            # Implementation: Reduce check interval
            
        elif action == "trigger_killswitch":
            self.logger.critical("MAPE-K directive: Trigger kill-switch")
            # Implementation: Trigger emergency kill-switch
            
        elif action == "reduce_sensitivity":
            self.logger.info("MAPE-K directive: Reduce detection sensitivity")
            # Implementation: Adjust detection thresholds
            
        elif action == "escalate":
            self.logger.warning("MAPE-K directive: Escalate alerts")
            # Implementation: Increase alert severity
        
        else:
            self.logger.debug("Unknown MAPE-K directive", action=action)
    
    async def sync_with_mapek(self):
        """
        Periodic sync with MAPE-K system
        Fetches consciousness state and handles directives
        """
        if not self.enabled:
            return
        
        while True:
            try:
                # Fetch consciousness state
                state = await self.fetch_consciousness_state()
                
                if state:
                    phi_ratio = state.get("phi_ratio", 0.5)
                    
                    # Check if phi ratio crossed threshold
                    if phi_ratio < self.consciousness_threshold:
                        self.logger.warning(
                            "MAPE-K consciousness below threshold",
                            phi_ratio=phi_ratio,
                            threshold=self.consciousness_threshold
                        )
                        
                        if self.on_phi_threshold_crossed:
                            await self.on_phi_threshold_crossed(phi_ratio)
                    
                    # Report our status
                    from src.main import detection_engine, killswitch_manager
                    
                    status = {
                        "detector_running": detection_engine.running if detection_engine else False,
                        "killswitch_enabled": killswitch_manager.enabled if killswitch_manager else False,
                        "total_leaks": 0,  # Would query from DB
                    }
                    
                    await self.report_status_to_mapek(status)
                
                # Wait before next sync
                await asyncio.sleep(60)  # Sync every minute
                
            except Exception as e:
                self.logger.error("Error in MAPE-K sync", error=str(e))
                await asyncio.sleep(60)


class MAPEKLeakAdapter:
    """
    Adapter to convert leak events to MAPE-K compatible format
    """
    
    @staticmethod
    def adapt_leak_event(leak_event) -> Dict[str, Any]:
        """
        Convert a leak event to MAPE-K format
        
        Args:
            leak_event: LeakEvent from core detector
            
        Returns:
            MAPE-K compatible dictionary
        """
        return {
            "timestamp": leak_event.timestamp.isoformat(),
            "type": "security_event",
            "subtype": "geolocation_leak",
            "severity": leak_event.severity.value,
            "details": {
                "leak_type": leak_event.leak_type.value,
                "detected_value": leak_event.detected_value,
                "expected_value": leak_event.expected_value,
                "source_ip": leak_event.source_ip,
                "location": {
                    "country": leak_event.detected_country,
                    "city": leak_event.detected_city,
                    "isp": leak_event.detected_isp
                }
            },
            "requires_action": leak_event.severity.value in ["warning", "critical"],
            "auto_remediated": False  # Set by killswitch
        }
    
    @staticmethod
    def adapt_killswitch_result(result) -> Dict[str, Any]:
        """
        Convert a kill-switch result to MAPE-K format
        
        Args:
            result: KillSwitchResult
            
        Returns:
            MAPE-K compatible dictionary
        """
        return {
            "timestamp": result.timestamp.isoformat(),
            "type": "remediation_action",
            "subtype": "killswitch",
            "severity": "critical" if not result.success else "info",
            "details": {
                "action": result.action.value,
                "success": result.success,
                "message": result.message,
                "details": result.details
            },
            "requires_action": not result.success
        }


# Global integration instance
mapek_integration = MAPEKIntegration()


async def initialize_mapek_integration():
    """Initialize MAPE-K integration"""
    if settings.mapek.enabled:
        logger.info("Initializing MAPE-K integration")
        
        # Start sync loop
        asyncio.create_task(mapek_integration.sync_with_mapek())
        
        # Report initialization
        await mapek_integration.report_to_mapek(MAPEKEvent(
            event_type="knowledge",
            node_id=settings.mapek.node_id,
            data={
                "type": "service_initialized",
                "service": "geo-leak-detector",
                "version": settings.version
            }
        ))
        
        logger.info("MAPE-K integration initialized")
    else:
        logger.info("MAPE-K integration disabled")
