#!/usr/bin/env python3
"""
eBPF Orchestrator - Unified Control Point for x0tta6bl4 eBPF Subsystem

This module provides a single entry point for managing all eBPF components:
- Program loading and lifecycle management
- Network monitoring and metrics collection
- Flow observability (Cilium/Hubble-like)
- Dynamic fallback and self-healing integration
- MAPE-K loop integration

Usage:
    orchestrator = EBPFOrchestrator(interface="eth0")
    await orchestrator.start()
    status = orchestrator.get_status()
    await orchestrator.stop()
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Dict, Any, Optional, List, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

# Local imports with graceful fallback
try:
    from .loader import EBPFLoader, EBPFProgramType, EBPFAttachMode
    loader_available = True
except ImportError:
    loader_available = False
    EBPFLoader = None

try:
    from .bcc_probes import MeshNetworkProbes
    bcc_probes_available = True
except ImportError:
    bcc_probes_available = False
    MeshNetworkProbes = None

try:
    from .metrics_exporter import EBPFMetricsExporter
    metrics_available = True
except ImportError:
    metrics_available = False
    EBPFMetricsExporter = None

try:
    from .performance_monitor import EBPFPerformanceMonitor
    performance_monitor_available = True
except ImportError:
    performance_monitor_available = False
    EBPFPerformanceMonitor = None

try:
    from .cilium_integration import CiliumLikeIntegration, FlowDirection, FlowVerdict
    cilium_available = True
except ImportError:
    cilium_available = False
    CiliumLikeIntegration = None

try:
    from .dynamic_fallback import DynamicFallbackController
    fallback_available = True
except ImportError:
    fallback_available = False
    DynamicFallbackController = None

try:
    from .mape_k_integration import EBPFMAPEKIntegration
    mapek_available = True
except ImportError:
    mapek_available = False
    EBPFMAPEKIntegration = None

if TYPE_CHECKING:
    from .loader import EBPFLoader
    from .mesh_probes import MeshNetworkProbes
    from .metrics_exporter import EBPFMetricsExporter
    from .performance_monitor import EBPFPerformanceMonitor
    from .cilium_integration import CiliumLikeIntegration
    from .dynamic_fallback import DynamicFallbackController
    from .mape_k_integration import EBPFMAPEKIntegration

logger = logging.getLogger(__name__)


class OrchestratorState(Enum):
    """Orchestrator lifecycle states"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class OrchestratorConfig:
    """Configuration for EBPFOrchestrator"""
    interface: str = "eth0"
    programs_dir: Optional[Path] = None
    enable_flow_observability: bool = True
    enable_metrics_export: bool = True
    enable_performance_monitoring: bool = True
    enable_dynamic_fallback: bool = True
    enable_mapek_integration: bool = True
    prometheus_port: int = 9090
    latency_threshold_ms: float = 100.0
    monitoring_interval_seconds: float = 10.0
    auto_load_programs: bool = True


@dataclass
class ComponentStatus:
    """Status of an orchestrator component"""
    name: str
    available: bool
    running: bool
    error: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)


class EBPFOrchestrator:
    """
    Unified control point for x0tta6bl4 eBPF subsystem.
    
    Manages all eBPF components through a single interface:
    - EBPFLoader: Program loading and attachment
    - MeshNetworkProbes: BCC-based network monitoring
    - EBPFMetricsExporter: Prometheus metrics export
    - CiliumLikeIntegration: Flow observability
    - DynamicFallbackController: Automatic rerouting
    - EBPFMAPEKIntegration: Self-healing integration
    
    Example:
        >>> config = OrchestratorConfig(interface="eth0")
        >>> orchestrator = EBPFOrchestrator(config)
        >>> await orchestrator.start()
        >>> print(orchestrator.get_status())
        >>> await orchestrator.stop()
    """
    
    def __init__(self, config: Optional[OrchestratorConfig] = None):
        """
        Initialize the eBPF orchestrator.
        
        Args:
            config: Configuration options. Uses defaults if not provided.
        """
        self.config = config or OrchestratorConfig()
        self.state = OrchestratorState.STOPPED
        self.start_time: Optional[float] = None
        
        # Component instances (initialized lazily)
        self._loader: Optional[EBPFLoader] = None
        self._probes: Optional[MeshNetworkProbes] = None
        self._metrics_exporter: Optional[EBPFMetricsExporter] = None
        self._performance_monitor: Optional[EBPFPerformanceMonitor] = None
        self._cilium: Optional[CiliumLikeIntegration] = None
        self._fallback: Optional[DynamicFallbackController] = None
        self._mapek: Optional[EBPFMAPEKIntegration] = None
        
        # Background tasks
        self._monitoring_task: Optional[asyncio.Task[None]] = None
        self._metrics_task: Optional[asyncio.Task[None]] = None
        
        # Loaded programs tracking
        self._loaded_programs: List[str] = []
        
        logger.info(f"EBPFOrchestrator initialized for interface: {self.config.interface}")
    
    # ==================== Lifecycle Management ====================
    
    async def start(self) -> bool:
        """
        Start all eBPF components.
        
        Returns:
            True if started successfully, False otherwise
        """
        if self.state == OrchestratorState.RUNNING:
            logger.warning("Orchestrator already running")
            return True
        
        self.state = OrchestratorState.STARTING
        self.start_time = time.time()
        
        try:
            # Initialize components
            await self._initialize_components()
            
            # Load eBPF programs if configured
            if self.config.auto_load_programs:
                await self._load_programs()
            
            # Start background tasks
            await self._start_background_tasks()
            
            self.state = OrchestratorState.RUNNING
            logger.info("✅ EBPFOrchestrator started successfully")
            return True
            
        except Exception as e:
            self.state = OrchestratorState.ERROR
            logger.error(f"❌ Failed to start orchestrator: {e}")
            return False
    
    async def stop(self) -> bool:
        """
        Stop all eBPF components gracefully.
        
        Returns:
            True if stopped successfully
        """
        if self.state == OrchestratorState.STOPPED:
            logger.warning("Orchestrator already stopped")
            return True
        
        self.state = OrchestratorState.STOPPING
        
        try:
            # Stop background tasks
            await self._stop_background_tasks()
            
            # Cleanup components
            await self._cleanup_components()
            
            self.state = OrchestratorState.STOPPED
            logger.info("✅ EBPFOrchestrator stopped successfully")
            return True
            
        except Exception as e:
            self.state = OrchestratorState.ERROR
            logger.error(f"❌ Error stopping orchestrator: {e}")
            return False
    
    async def restart(self) -> bool:
        """Restart the orchestrator."""
        await self.stop()
        return await self.start()
    
    # ==================== Component Initialization ====================
    
    async def _initialize_components(self):
        """Initialize all available components."""
        
        # EBPFLoader
        if loader_available:
            try:
                self._loader = EBPFLoader(self.config.programs_dir)
                logger.info("✅ EBPFLoader initialized")
            except Exception as e:
                logger.warning(f"⚠️ EBPFLoader initialization failed: {e}")
        
        # Metrics Exporter
        if metrics_available and self.config.enable_metrics_export:
            try:
                self._metrics_exporter = EBPFMetricsExporter()
                logger.info("✅ EBPFMetricsExporter initialized")
            except Exception as e:
                logger.warning(f"⚠️ EBPFMetricsExporter initialization failed: {e}")
        
        # Performance Monitor
        if performance_monitor_available and self.config.enable_performance_monitoring:
            try:
                self._performance_monitor = EBPFPerformanceMonitor(self.config.prometheus_port)
                logger.info("✅ EBPFPerformanceMonitor initialized")
            except Exception as e:
                logger.warning(f"⚠️ EBPFPerformanceMonitor initialization failed: {e}")
        
        # Cilium-like Integration
        if cilium_available and self.config.enable_flow_observability:
            try:
                self._cilium = CiliumLikeIntegration(
                    interface=self.config.interface,
                    enable_flow_observability=True,
                    enable_policy_enforcement=True
                )
                logger.info("✅ CiliumLikeIntegration initialized")
            except Exception as e:
                logger.warning(f"⚠️ CiliumLikeIntegration initialization failed: {e}")
        
        # Dynamic Fallback
        if fallback_available and self.config.enable_dynamic_fallback:
            try:
                self._fallback = DynamicFallbackController(
                    latency_threshold_ms=self.config.latency_threshold_ms
                )
                logger.info("✅ DynamicFallbackController initialized")
            except Exception as e:
                logger.warning(f"⚠️ DynamicFallbackController initialization failed: {e}")
        
        # MAPE-K Integration
        if mapek_available and self.config.enable_mapek_integration:
            try:
                self._mapek = EBPFMAPEKIntegration(self._metrics_exporter)
                logger.info("✅ EBPFMAPEKIntegration initialized")
            except Exception as e:
                logger.warning(f"⚠️ EBPFMAPEKIntegration initialization failed: {e}")
    
    async def _load_programs(self):
        """Load eBPF programs from programs directory."""
        if not self._loader:
            logger.warning("Loader not available, skipping program loading")
            return
        
        try:
            self._loaded_programs = self._loader.load_programs()
            logger.info(f"Loaded {len(self._loaded_programs)} eBPF programs")
        except Exception as e:
            logger.warning(f"Failed to load programs: {e}")
    
    async def _cleanup_components(self):
        """Cleanup all components."""
        
        # Cleanup loader
        if self._loader:
            try:
                self._loader.cleanup()
                logger.info("✅ EBPFLoader cleaned up")
            except Exception as e:
                logger.warning(f"⚠️ EBPFLoader cleanup error: {e}")
        
        # Shutdown Cilium integration
        if self._cilium:
            try:
                self._cilium.shutdown()
                logger.info("✅ CiliumLikeIntegration shut down")
            except Exception as e:
                logger.warning(f"⚠️ CiliumLikeIntegration shutdown error: {e}")
        
        # Clear references
        self._loader = None
        self._probes = None
        self._metrics_exporter = None
        self._performance_monitor = None
        self._cilium = None
        self._fallback = None
        self._mapek = None
        self._loaded_programs = []
    
    # ==================== Background Tasks ====================
    
    async def _start_background_tasks(self):
        """Start background monitoring and metrics tasks."""
        
        # Performance monitoring task
        if self._performance_monitor:
            await self._performance_monitor.start_monitoring()
        
        # Monitoring task
        self._monitoring_task = asyncio.create_task(
            self._monitoring_loop(),
            name="ebpf_monitoring"
        )
        
        # Metrics export task
        if self._metrics_exporter:
            self._metrics_task = asyncio.create_task(
                self._metrics_export_loop(),
                name="ebpf_metrics"
            )
        
        logger.info("Background tasks started")
    
    async def _stop_background_tasks(self):
        """Stop background tasks."""
        
        # Stop performance monitor
        if self._performance_monitor:
            await self._performance_monitor.stop_monitoring()
        
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        if self._metrics_task:
            self._metrics_task.cancel()
            try:
                await self._metrics_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Background tasks stopped")
    
    async def _monitoring_loop(self):
        """Main monitoring loop."""
        while self.state == OrchestratorState.RUNNING:
            try:
                # Collect metrics from loader
                if self._loader:
                    stats = self._loader.get_stats()
                    
                    # Update fallback controller with latency data
                    if self._fallback and 'avg_latency_ns' in stats:
                        latency_ms = stats.get('avg_latency_ns', 0) / 1e6
                        self._fallback.update_latency(
                            self.config.interface,
                            latency_ms
                        )
                        self._fallback.check_recovery(self.config.interface)
                    
                    # Check for anomalies via MAPE-K
                    if self._mapek:
                        metrics = self._mapek.get_metrics_for_mapek()
                        anomaly = self._mapek.check_anomalies(metrics)
                        if anomaly:
                            self._mapek.trigger_mapek_alert(anomaly)
                
                await asyncio.sleep(self.config.monitoring_interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitoring loop error: {e}")
                await asyncio.sleep(5)
    
    async def _metrics_export_loop(self):
        """Metrics export loop."""
        while self.state == OrchestratorState.RUNNING:
            try:
                if self._metrics_exporter:
                    # Export eBPF metrics
                    metrics = self._metrics_exporter.export_metrics()
                    
                    # Export Cilium metrics if available
                    if self._cilium:
                        self._cilium.export_metrics_to_prometheus()
                
                await asyncio.sleep(15)  # Export every 15 seconds
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Metrics export error: {e}")
                await asyncio.sleep(5)
    
    # ==================== Status and Metrics ====================
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get comprehensive status of all components.
        
        Returns:
            Dict with status of all subsystems
        """
        uptime = time.time() - self.start_time if self.start_time else 0
        
        return {
            'state': self.state.value,
            'uptime_seconds': uptime,
            'interface': self.config.interface,
            'components': self._get_component_statuses(),
            'programs': self._get_program_status(),
            'metrics': self._get_aggregated_metrics()
        }
    
    def _get_component_statuses(self) -> Dict[str, ComponentStatus]:
        """Get status of each component."""
        return {
            'loader': ComponentStatus(
                name='EBPFLoader',
                available=loader_available,
                running=self._loader is not None,
                metrics={'loaded_programs': len(self._loaded_programs)}
            ),
            'metrics_exporter': ComponentStatus(
                name='EBPFMetricsExporter',
                available=metrics_available,
                running=self._metrics_exporter is not None
            ),
            'cilium': ComponentStatus(
                name='CiliumLikeIntegration',
                available=cilium_available,
                running=self._cilium is not None,
                metrics=self._cilium.get_flow_metrics() if self._cilium else {}
            ),
            'fallback': ComponentStatus(
                name='DynamicFallbackController',
                available=fallback_available,
                running=self._fallback is not None,
                metrics={'active_fallbacks': self._fallback.get_fallback_status() if self._fallback else {}}
            ),
            'mapek': ComponentStatus(
                name='EBPFMAPEKIntegration',
                available=mapek_available,
                running=self._mapek is not None
            ),
            'performance_monitor': ComponentStatus(
                name='EBPFPerformanceMonitor',
                available=performance_monitor_available,
                running=self._performance_monitor is not None,
                metrics=self._performance_monitor.get_performance_report() if self._performance_monitor else {}
            )
        }
    
    def _get_program_status(self) -> List[Dict[str, Any]]:
        """Get status of loaded eBPF programs."""
        if not self._loader:
            return []
        return self._loader.list_loaded_programs()
    
    def _get_aggregated_metrics(self) -> Dict[str, Any]:
        """Get aggregated metrics from all sources."""
        metrics = {}
        
        # Loader stats
        if self._loader:
            metrics['ebpf_stats'] = self._loader.get_stats()
        
        # Flow metrics
        if self._cilium:
            metrics['flow_metrics'] = self._cilium.get_flow_metrics()
        
        # MAPE-K metrics
        if self._mapek:
            metrics['mapek_metrics'] = self._mapek.get_metrics_for_mapek()
        
        # Performance monitor metrics
        if self._performance_monitor:
            metrics['performance_metrics'] = self._performance_monitor.get_performance_report()
        
        return metrics
    
    # ==================== Program Management ====================
    
    def load_program(
        self,
        program_path: str,
        program_type: str = "xdp"
    ) -> Optional[str]:
        """
        Load a specific eBPF program.
        
        Args:
            program_path: Path to the .o file
            program_type: Type of program (xdp, tc, etc.)
        
        Returns:
            Program ID if successful, None otherwise
        """
        if not self._loader:
            logger.error("Loader not available")
            return None
        
        try:
            prog_type = EBPFProgramType(program_type)
            program_id = self._loader.load_program(program_path, prog_type)
            self._loaded_programs.append(program_id)
            return program_id
        except Exception as e:
            logger.error(f"Failed to load program: {e}")
            return None
    
    def attach_program(
        self,
        program_id: str,
        interface: Optional[str] = None,
        mode: str = "skb"
    ) -> bool:
        """
        Attach a loaded program to an interface.
        
        Args:
            program_id: ID of the loaded program
            interface: Network interface (defaults to config interface)
            mode: Attach mode (skb, drv, hw)
        
        Returns:
            True if successful
        """
        if not self._loader:
            logger.error("Loader not available")
            return False
        
        try:
            iface = interface or self.config.interface
            attach_mode = EBPFAttachMode(mode)
            return self._loader.attach_to_interface(program_id, iface, attach_mode)
        except Exception as e:
            logger.error(f"Failed to attach program: {e}")
            return False
    
    def detach_program(
        self,
        program_id: str,
        interface: Optional[str] = None
    ) -> bool:
        """
        Detach a program from an interface.
        
        Args:
            program_id: ID of the program
            interface: Network interface
        
        Returns:
            True if successful
        """
        if not self._loader:
            logger.error("Loader not available")
            return False
        
        try:
            iface = interface or self.config.interface
            return self._loader.detach_from_interface(program_id, iface)
        except Exception as e:
            logger.error(f"Failed to detach program: {e}")
            return False
    
    # ==================== Flow Observability ====================
    
    def get_flows(
        self,
        source_ip: Optional[str] = None,
        destination_ip: Optional[str] = None,
        protocol: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Get network flows (Hubble-like).
        
        Args:
            source_ip: Filter by source IP
            destination_ip: Filter by destination IP
            protocol: Filter by protocol
            limit: Maximum flows to return
        
        Returns:
            List of flow events
        """
        if not self._cilium:
            logger.warning("Cilium integration not available")
            return []
        
        return self._cilium.get_hubble_like_flows(
            source_ip=source_ip,
            destination_ip=destination_ip,
            protocol=protocol,
            limit=limit
        )
    
    def record_flow(
        self,
        source_ip: str,
        destination_ip: str,
        source_port: int,
        destination_port: int,
        protocol: str,
        bytes_count: int,
        packets: int
    ):
        """
        Record a network flow event.
        
        Args:
            source_ip: Source IP address
            destination_ip: Destination IP address
            source_port: Source port
            destination_port: Destination port
            protocol: Protocol (TCP, UDP, etc.)
            bytes_count: Bytes transferred
            packets: Packets transferred
        """
        if not self._cilium:
            return
        
        self._cilium.record_flow(
            source_ip=source_ip,
            destination_ip=destination_ip,
            source_port=source_port,
            destination_port=destination_port,
            protocol=protocol,
            direction=FlowDirection.EGRESS,
            verdict=FlowVerdict.FORWARDED,
            bytes=bytes_count,
            packets=packets
        )
    
    # ==================== Health Checks ====================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on all components.
        
        Returns:
            Health status dict
        """
        health = {
            'healthy': True,
            'state': self.state.value,
            'checks': {}
        }
        
        # Check loader
        if self._loader:
            try:
                programs = self._loader.list_loaded_programs()
                health['checks']['loader'] = {
                    'status': 'healthy',
                    'programs_loaded': len(programs)
                }
            except Exception as e:
                health['checks']['loader'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health['healthy'] = False
        
        # Check metrics exporter
        if self._metrics_exporter:
            try:
                summary = self._metrics_exporter.get_metrics_summary()
                health['checks']['metrics'] = {
                    'status': 'healthy',
                    'registered_maps': summary.get('registered_maps', 0)
                }
            except Exception as e:
                health['checks']['metrics'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health['healthy'] = False
        
        # Check Cilium integration
        if self._cilium:
            try:
                flow_metrics = self._cilium.get_flow_metrics()
                health['checks']['cilium'] = {
                    'status': 'healthy',
                    'flows_processed': flow_metrics.get('flows_processed_total', 0)
                }
            except Exception as e:
                health['checks']['cilium'] = {
                    'status': 'unhealthy',
                    'error': str(e)
                }
                health['healthy'] = False
        
        return health


# ==================== Factory Functions ====================

def create_orchestrator(
    interface: str = "eth0",
    **kwargs
) -> EBPFOrchestrator:
    """
    Factory function to create an EBPFOrchestrator.
    
    Args:
        interface: Network interface to monitor
        **kwargs: Additional configuration options
    
    Returns:
        Configured EBPFOrchestrator instance
    """
    config = OrchestratorConfig(interface=interface, **kwargs)
    return EBPFOrchestrator(config)


# ==================== CLI Entry Point ====================

async def main():
    """Main entry point for standalone execution."""
    import argparse
    
    parser = argparse.ArgumentParser(description='x0tta6bl4 eBPF Orchestrator')
    parser.add_argument('-i', '--interface', default='eth0', help='Network interface')
    parser.add_argument('-p', '--prometheus-port', type=int, default=9090, help='Prometheus port')
    parser.add_argument('--no-flows', action='store_true', help='Disable flow observability')
    parser.add_argument('--no-fallback', action='store_true', help='Disable dynamic fallback')
    
    args = parser.parse_args()
    
    config = OrchestratorConfig(
        interface=args.interface,
        prometheus_port=args.prometheus_port,
        enable_flow_observability=not args.no_flows,
        enable_dynamic_fallback=not args.no_fallback
    )
    
    orchestrator = EBPFOrchestrator(config)
    
    try:
        await orchestrator.start()
        
        # Keep running until interrupted
        while True:
            status = orchestrator.get_status()
            logger.info(f"Status: {status['state']}, Uptime: {status['uptime_seconds']:.0f}s")
            await asyncio.sleep(30)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await orchestrator.stop()


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    asyncio.run(main())
