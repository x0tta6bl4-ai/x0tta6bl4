"""
Perf Buffer Reader for eBPF Telemetry.

High-throughput reader for eBPF perf buffer events.
"""
import logging
import struct
from collections import defaultdict, deque
from typing import Any, Callable, Dict, List

from .models import TelemetryConfig, TelemetryEvent
from .security import SecurityManager

logger = logging.getLogger(__name__)

# Try to import BCC
BCC_AVAILABLE = False
try:
    from bcc import BPF
    BCC_AVAILABLE = True
except ImportError:
    pass


class PerfBufferReader:
    """
    High-throughput reader for eBPF perf buffer events.

    Features:
    - Non-blocking event processing
    - Event batching
    - Custom event handlers
    - Thread-safe queue
    """

    def __init__(self, config: TelemetryConfig, security: SecurityManager):
        self.config = config
        self.security = security
        self.running = False
        self.event_queue: deque = deque(maxlen=config.max_queue_size)
        self.event_handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.stats = {
            "events_received": 0,
            "events_processed": 0,
            "events_dropped": 0,
            "parse_errors": 0,
        }

        logger.info("PerfBufferReader initialized")

    def register_handler(
        self,
        event_type: str,
        handler: Callable[[TelemetryEvent], None]
    ):
        """
        Register event handler.

        Args:
            event_type: Type of event to handle
            handler: Callback function
        """
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")

    def start_reading(self, bpf_program: Any, map_name: str):
        """
        Start reading perf buffer events.

        Args:
            bpf_program: BCC BPF program instance
            map_name: Name of the perf buffer map
        """
        if not BCC_AVAILABLE:
            logger.warning("BCC not available, cannot read perf buffer")
            return

        self.running = True

        def handle_event(cpu, data, size):
            """Handle perf buffer event."""
            try:
                # Parse event header
                if size < 16:
                    self.stats["parse_errors"] += 1
                    return

                # Parse event (simplified - real implementation would match C struct)
                event_type = struct.unpack("I", data[0:4])[0]
                timestamp_ns = struct.unpack("Q", data[4:12])[0]
                cpu_id = struct.unpack("I", data[12:16])[0]

                # Create telemetry event
                event = TelemetryEvent(
                    event_type=f"event_{event_type}",
                    timestamp_ns=timestamp_ns,
                    cpu_id=cpu_id,
                    data={"raw_size": size},
                )

                # Validate event
                is_valid, error = self.security.validate_event(event)
                if not is_valid:
                    logger.warning(f"Invalid event: {error}")
                    return

                # Add to queue
                if len(self.event_queue) >= self.event_queue.maxlen:
                    self.stats["events_dropped"] += 1

                self.event_queue.append(event)
                self.stats["events_received"] += 1

            except Exception as e:
                logger.error(f"Error handling perf event: {e}")
                self.stats["parse_errors"] += 1

        try:
            # Open perf buffer
            bpf_program[map_name].open_perf_buffer(handle_event)

            logger.info(f"Started reading perf buffer: {map_name}")

            # Poll loop
            while self.running:
                bpf_program.perf_buffer_poll(timeout=self.config.poll_timeout)

                # Process queued events
                self._process_events()

        except Exception as e:
            logger.error(f"Error reading perf buffer: {e}")
        finally:
            self.running = False

    def _process_events(self):
        """Process queued events."""
        while self.event_queue:
            event = self.event_queue.popleft()

            # Call registered handlers
            handlers = self.event_handlers.get(event.event_type, [])
            for handler in handlers:
                try:
                    handler(event)
                    self.stats["events_processed"] += 1
                except Exception as e:
                    logger.error(f"Event handler error: {e}")

    def stop_reading(self):
        """Stop reading perf buffer events."""
        self.running = False
        logger.info("Stopped reading perf buffer")

    def get_stats(self) -> Dict[str, Any]:
        """Get reader statistics."""
        return self.stats.copy()
