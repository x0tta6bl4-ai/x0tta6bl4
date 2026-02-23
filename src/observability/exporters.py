"""
OpenTelemetry Span Exporters

Provides exporters for different backends: OTLP, Jaeger, Console.
"""

import json
import logging
import socket
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional
import struct
import threading
from queue import Queue
import time

logger = logging.getLogger(__name__)


@dataclass
class ExportResult:
    """Result of span export."""
    success: bool
    error: Optional[str] = None
    spans_exported: int = 0


class SpanExporter(ABC):
    """Base class for span exporters."""
    
    @abstractmethod
    def export(self, spans: List[Any]) -> ExportResult:
        """Export a batch of spans."""
        pass
    
    @abstractmethod
    def shutdown(self) -> None:
        """Shutdown the exporter."""
        pass
    
    @abstractmethod
    def force_flush(self, timeout_ms: int = 30000) -> bool:
        """Force flush any buffered spans."""
        pass


class ConsoleSpanExporter(SpanExporter):
    """
    Export spans to console for debugging.
    
    Usage:
        exporter = ConsoleSpanExporter()
        exporter.export([span1, span2])
    """
    
    def __init__(self, output_format: str = "json"):
        self.output_format = output_format
        self._lock = threading.Lock()
    
    def export(self, spans: List[Any]) -> ExportResult:
        """Export spans to console."""
        with self._lock:
            try:
                for span in spans:
                    if self.output_format == "json":
                        output = self._format_json(span)
                    else:
                        output = self._format_pretty(span)
                    print(output)
                
                return ExportResult(success=True, spans_exported=len(spans))
            except Exception as e:
                logger.error(f"Console export failed: {e}")
                return ExportResult(success=False, error=str(e))
    
    def _format_json(self, span: Any) -> str:
        """Format span as JSON."""
        data = {
            "trace_id": span.context.trace_id,
            "span_id": span.context.span_id,
            "name": span.name,
            "kind": span.kind.value if hasattr(span.kind, "value") else str(span.kind),
            "start_time": span.start_time.isoformat(),
            "end_time": span.end_time.isoformat() if span.end_time else None,
            "duration_ms": span.duration_ms(),
            "status": span.status_code.value if hasattr(span.status_code, "value") else str(span.status_code),
            "attributes": span.attributes,
            "events": span.events,
        }
        return json.dumps(data, indent=2)
    
    def _format_pretty(self, span: Any) -> str:
        """Format span as pretty text."""
        duration = f"{span.duration_ms():.2f}ms" if span.duration_ms() else "N/A"
        return (
            f"\n{'='*60}\n"
            f"SPAN: {span.name}\n"
            f"{'='*60}\n"
            f"  Trace ID: {span.context.trace_id}\n"
            f"  Span ID:  {span.context.span_id}\n"
            f"  Kind:     {span.kind.value if hasattr(span.kind, 'value') else span.kind}\n"
            f"  Duration: {duration}\n"
            f"  Status:   {span.status_code.value if hasattr(span.status_code, 'value') else span.status_code}\n"
            f"  Attributes:\n"
            + "\n".join(f"    {k}: {v}" for k, v in span.attributes.items())
            + "\n"
        )
    
    def shutdown(self) -> None:
        """No-op for console exporter."""
        pass
    
    def force_flush(self, timeout_ms: int = 30000) -> bool:
        """No-op for console exporter."""
        return True


class OTLPSpanExporter(SpanExporter):
    """
    Export spans via OTLP protocol.
    
    Supports both gRPC and HTTP transports.
    
    Usage:
        exporter = OTLPSpanExporter(
            endpoint="http://localhost:4317",
            headers={"api-key": "secret"}
        )
    """
    
    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        headers: Optional[Dict[str, str]] = None,
        timeout: int = 30,
        use_ssl: bool = False,
    ):
        self.endpoint = endpoint.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self.use_ssl = use_ssl
        self._client = None
    
    def _convert_span_to_otlp(self, span: Any) -> Dict[str, Any]:
        """Convert internal span to OTLP format."""
        # Convert attributes to OTLP format
        attributes = {}
        for key, value in span.attributes.items():
            if isinstance(value, bool):
                attributes[key] = {"bool_value": value}
            elif isinstance(value, int):
                attributes[key] = {"int_value": value}
            elif isinstance(value, float):
                attributes[key] = {"double_value": value}
            else:
                attributes[key] = {"string_value": str(value)}
        
        # Convert events to OTLP format
        events = []
        for event in span.events:
            events.append({
                "time_unix_nano": int(datetime.fromisoformat(event["timestamp"]).timestamp() * 1e9),
                "name": event["name"],
                "attributes": {
                    k: {"string_value": str(v)}
                    for k, v in event.get("attributes", {}).items()
                },
            })
        
        # Map span kind to OTLP
        kind_map = {
            "internal": 1,  # SPAN_KIND_INTERNAL
            "server": 2,    # SPAN_KIND_SERVER
            "client": 3,    # SPAN_KIND_CLIENT
            "producer": 4,  # SPAN_KIND_PRODUCER
            "consumer": 5,  # SPAN_KIND_CONSUMER
        }
        kind_value = kind_map.get(
            span.kind.value if hasattr(span.kind, "value") else str(span.kind),
            1
        )
        
        # Map status to OTLP
        status_code_map = {
            "unset": 0,  # STATUS_CODE_UNSET
            "ok": 1,     # STATUS_CODE_OK
            "error": 2,  # STATUS_CODE_ERROR
        }
        status_value = status_code_map.get(
            span.status_code.value if hasattr(span.status_code, "value") else str(span.status_code),
            0
        )
        
        return {
            "trace_id": self._hex_to_bytes(span.context.trace_id),
            "span_id": self._hex_to_bytes(span.context.span_id),
            "parent_span_id": self._hex_to_bytes(span.parent.context.span_id) if span.parent else None,
            "name": span.name,
            "kind": kind_value,
            "start_time_unix_nano": int(span.start_time.timestamp() * 1e9),
            "end_time_unix_nano": int(span.end_time.timestamp() * 1e9) if span.end_time else 0,
            "attributes": attributes,
            "events": events,
            "status": {
                "code": status_value,
                "message": span.status_description or "",
            },
        }
    
    def _hex_to_bytes(self, hex_str: str) -> bytes:
        """Convert hex string to bytes."""
        return bytes.fromhex(hex_str)
    
    def export(self, spans: List[Any]) -> ExportResult:
        """Export spans via OTLP."""
        try:
            # Convert spans to OTLP format
            otlp_spans = [self._convert_span_to_otlp(s) for s in spans]
            
            # Build OTLP request
            request_data = {
                "resource_spans": [{
                    "resource": {
                        "attributes": [
                            {"key": "service.name", "value": {"string_value": "maas-x0tta6bl4"}}
                        ]
                    },
                    "scope_spans": [{
                        "scope": {"name": "maas-tracer"},
                        "spans": otlp_spans,
                    }],
                }]
            }
            
            # Send via HTTP (simplified - in production use grpc or proper HTTP client)
            import urllib.request
            
            url = f"{self.endpoint}/v1/traces"
            data = json.dumps(request_data).encode("utf-8")
            
            req = urllib.request.Request(
                url,
                data=data,
                headers={
                    "Content-Type": "application/json",
                    **self.headers,
                },
            )
            
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                if response.status == 200:
                    return ExportResult(success=True, spans_exported=len(spans))
                else:
                    return ExportResult(
                        success=False,
                        error=f"OTLP export failed with status {response.status}",
                    )
        
        except Exception as e:
            logger.error(f"OTLP export failed: {e}")
            return ExportResult(success=False, error=str(e))
    
    def shutdown(self) -> None:
        """Shutdown the exporter."""
        self._client = None
    
    def force_flush(self, timeout_ms: int = 30000) -> bool:
        """No-op for synchronous exporter."""
        return True


class JaegerExporter(SpanExporter):
    """
    Export spans to Jaeger via UDP agent.
    
    Usage:
        exporter = JaegerExporter(
            agent_host="localhost",
            agent_port=6831,
        )
    """
    
    def __init__(
        self,
        agent_host: str = "localhost",
        agent_port: int = 6831,
        service_name: str = "maas-x0tta6bl4",
    ):
        self.agent_host = agent_host
        self.agent_port = agent_port
        self.service_name = service_name
        self._socket = None
    
    def _get_socket(self) -> socket.socket:
        """Get or create UDP socket."""
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket
    
    def _convert_span_to_jaeger(self, span: Any) -> Dict[str, Any]:
        """Convert internal span to Jaeger format."""
        # Convert attributes to Jaeger tags
        tags = []
        for key, value in span.attributes.items():
            tag = {"key": key}
            if isinstance(value, bool):
                tag["type"] = "bool"
                tag["value"] = value
            elif isinstance(value, int):
                tag["type"] = "int64"
                tag["value"] = value
            elif isinstance(value, float):
                tag["type"] = "float64"
                tag["value"] = value
            else:
                tag["type"] = "string"
                tag["value"] = str(value)
            tags.append(tag)
        
        # Convert events to Jaeger logs
        logs = []
        for event in span.events:
            logs.append({
                "timestamp": int(datetime.fromisoformat(event["timestamp"]).timestamp() * 1e6),
                "fields": [
                    {"key": "event", "value": event["name"]},
                    *[{"key": k, "value": str(v)} for k, v in event.get("attributes", {}).items()],
                ],
            })
        
        return {
            "traceId": span.context.trace_id,
            "spanId": span.context.span_id,
            "parentSpanId": span.parent.context.span_id if span.parent else None,
            "operationName": span.name,
            "startTime": int(span.start_time.timestamp() * 1e6),
            "duration": int(span.duration_ms() * 1000) if span.duration_ms() else 0,
            "tags": tags,
            "logs": logs,
        }
    
    def export(self, spans: List[Any]) -> ExportResult:
        """Export spans to Jaeger via UDP."""
        try:
            jaeger_spans = [self._convert_span_to_jaeger(s) for s in spans]
            
            # Build Jaeger thrift message (simplified)
            # In production, use jaeger-client library
            message = {
                "service": self.service_name,
                "spans": jaeger_spans,
            }
            
            # Send via UDP
            sock = self._get_socket()
            data = json.dumps(message).encode("utf-8")
            sock.sendto(data, (self.agent_host, self.agent_port))
            
            return ExportResult(success=True, spans_exported=len(spans))
        
        except Exception as e:
            logger.error(f"Jaeger export failed: {e}")
            return ExportResult(success=False, error=str(e))
    
    def shutdown(self) -> None:
        """Close the socket."""
        if self._socket:
            self._socket.close()
            self._socket = None
    
    def force_flush(self, timeout_ms: int = 30000) -> bool:
        """No-op for UDP exporter."""
        return True


class MultiSpanExporter(SpanExporter):
    """
    Export spans to multiple exporters.
    
    Usage:
        exporter = MultiSpanExporter([
            ConsoleSpanExporter(),
            OTLPSpanExporter(endpoint="http://localhost:4317"),
        ])
    """
    
    def __init__(self, exporters: List[SpanExporter]):
        self.exporters = exporters
    
    def export(self, spans: List[Any]) -> ExportResult:
        """Export to all exporters."""
        total_exported = 0
        errors = []
        
        for exporter in self.exporters:
            result = exporter.export(spans)
            if result.success:
                total_exported += result.spans_exported
            else:
                errors.append(f"{exporter.__class__.__name__}: {result.error}")
        
        if errors:
            return ExportResult(
                success=False,
                error="; ".join(errors),
                spans_exported=total_exported,
            )
        
        return ExportResult(success=True, spans_exported=total_exported)
    
    def shutdown(self) -> None:
        """Shutdown all exporters."""
        for exporter in self.exporters:
            try:
                exporter.shutdown()
            except Exception as e:
                logger.error(f"Failed to shutdown {exporter.__class__.__name__}: {e}")
    
    def force_flush(self, timeout_ms: int = 30000) -> bool:
        """Force flush all exporters."""
        success = True
        for exporter in self.exporters:
            try:
                if not exporter.force_flush(timeout_ms):
                    success = False
            except Exception as e:
                logger.error(f"Failed to flush {exporter.__class__.__name__}: {e}")
                success = False
        return success


class BatchSpanProcessor:
    """
    Batches spans before export.
    
    Collects spans and exports them in batches for efficiency.
    """
    
    def __init__(
        self,
        exporter: SpanExporter,
        max_queue_size: int = 2048,
        schedule_delay_ms: int = 5000,
        max_export_batch_size: int = 512,
        export_timeout_ms: int = 30000,
    ):
        self.exporter = exporter
        self.max_queue_size = max_queue_size
        self.schedule_delay_ms = schedule_delay_ms
        self.max_export_batch_size = max_export_batch_size
        self.export_timeout_ms = export_timeout_ms
        
        self._queue: Queue = Queue(maxsize=max_queue_size)
        self._shutdown = False
        self._worker_thread = threading.Thread(target=self._worker, daemon=True)
        self._worker_thread.start()
    
    def _worker(self) -> None:
        """Background worker for batch export."""
        batch = []
        last_export = time.time()
        
        while not self._shutdown:
            try:
                # Get span from queue with timeout
                try:
                    span = self._queue.get(timeout=0.1)
                    batch.append(span)
                except:
                    pass
                
                # Check if we should export
                should_export = (
                    len(batch) >= self.max_export_batch_size or
                    (time.time() - last_export) * 1000 >= self.schedule_delay_ms
                )
                
                if should_export and batch:
                    self.exporter.export(batch)
                    batch = []
                    last_export = time.time()
            
            except Exception as e:
                logger.error(f"Batch export error: {e}")
        
        # Final export on shutdown
        if batch:
            self.exporter.export(batch)
    
    def on_end(self, span: Any) -> None:
        """Add span to batch queue."""
        if not self._shutdown:
            try:
                self._queue.put_nowait(span)
            except:
                logger.warning("Span queue full, dropping span")
    
    def shutdown(self) -> None:
        """Shutdown the processor."""
        self._shutdown = True
        self._worker_thread.join(timeout=5)
        self.exporter.shutdown()
    
    def force_flush(self, timeout_ms: int = 30000) -> bool:
        """Force flush all pending spans."""
        # Wait for queue to empty
        start = time.time()
        while not self._queue.empty():
            if (time.time() - start) * 1000 > timeout_ms:
                return False
            time.sleep(0.1)
        return self.exporter.force_flush(timeout_ms)


def get_exporter(config: Any) -> SpanExporter:
    """Get exporter based on configuration."""
    exporter_type = getattr(config, "exporter_type", "console")
    
    if exporter_type == "otlp":
        return OTLPSpanExporter(
            endpoint=config.otlp_endpoint,
        )
    elif exporter_type == "jaeger":
        return JaegerExporter(
            agent_host=config.jaeger_agent_host,
            agent_port=config.jaeger_agent_port,
            service_name=config.service_name,
        )
    elif exporter_type == "console":
        return ConsoleSpanExporter()
    elif exporter_type == "multi":
        return MultiSpanExporter([
            ConsoleSpanExporter(),
            OTLPSpanExporter(endpoint=config.otlp_endpoint),
        ])
    else:
        logger.warning(f"Unknown exporter type: {exporter_type}, using console")
        return ConsoleSpanExporter()
