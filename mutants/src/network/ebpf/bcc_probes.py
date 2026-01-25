#!/usr/bin/env python3
"""
x0tta6bl4 BCC eBPF Probes for Network Metrics
Provides latency and congestion monitoring for mesh networking

Requirements:
- bcc (pip install bcc)
- prometheus_client (for metrics export)

Usage:
    python bcc_probes.py --interface eth0 --prometheus-port 9090
"""

import argparse
import signal
import sys
from typing import Dict
from bcc import BPF
from prometheus_client import start_http_server, Gauge, Counter
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Prometheus metrics
PACKET_LATENCY = Gauge('mesh_packet_latency_ns', 'Packet latency in nanoseconds', ['interface'])
QUEUE_CONGESTION = Gauge('mesh_queue_congestion', 'Queue congestion level', ['interface'])
PACKET_DROPS = Counter('mesh_packet_drops_total', 'Total packet drops', ['interface', 'reason'])

class MeshNetworkProbes:
    def __init__(self, interface: str, prometheus_port: int = 9090):
        self.interface = interface
        self.prometheus_port = prometheus_port

        # Current metrics
        self.current_latency = 0.0
        self.current_congestion = 0.0

        # Start Prometheus server
        start_http_server(prometheus_port)
        logger.info(f"Prometheus metrics on port {prometheus_port}")

        # Load eBPF programs
        self.load_latency_probe()
        self.load_congestion_probe()

    def load_latency_probe(self):
        """Load eBPF program for packet latency measurement"""
        bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/netdevice.h>
#include <linux/skbuff.h>

BPF_HASH(start_time, u64, u64);  // packet_id -> start_time

// Ingress hook
SEC("tracepoint/net/netif_receive_skb")
int ingress_latency(struct trace_event_raw_netif_receive_skb *ctx) {
    u64 packet_id = bpf_ktime_get_ns();  // Simple ID
    u64 ts = packet_id;
    start_time.update(&packet_id, &ts);
    return 0;
}

// Egress hook
SEC("tracepoint/net/net_dev_xmit")
int egress_latency(struct trace_event_raw_net_dev_template *ctx) {
    u64 packet_id = bpf_ktime_get_ns();  // Match with ingress
    u64 *start = start_time.lookup(&packet_id);
    if (start) {
        u64 latency = packet_id - *start;
        // Output latency (in userspace we'll read this)
        bpf_trace_printk("latency: %llu\\n", latency);
        start_time.delete(&packet_id);
    }
    return 0;
}
"""

        self.latency_bpf = BPF(text=bpf_text)
        logger.info("Loaded latency probe")

    def load_congestion_probe(self):
        """Load eBPF program for queue congestion monitoring"""
        bpf_text = """
#include <uapi/linux/ptrace.h>
#include <linux/netdevice.h>

BPF_HASH(queue_len, u32, u32);  // ifindex -> queue length

SEC("kprobe/dev_queue_xmit")
int queue_congestion(struct pt_regs *ctx) {
    struct net_device *dev = (struct net_device *)PT_REGS_PARM1(ctx);
    u32 ifindex = dev->ifindex;
    u32 qlen = dev->qdisc->q.qlen;  // Queue length
    queue_len.update(&ifindex, &qlen);
    bpf_trace_printk("queue_len ifindex=%u len=%u\\n", ifindex, qlen);
    return 0;
}
"""

        self.congestion_bpf = BPF(text=bpf_text)
        logger.info("Loaded congestion probe")

    def run(self):
        """Main monitoring loop"""
        logger.info("Starting mesh network probes...")

        try:
            while True:
                # Read latency events
                for event in self.latency_bpf.trace_read():
                    if 'latency:' in event:
                        latency_ns = int(event.split(':')[1])
                        PACKET_LATENCY.labels(interface=self.interface).set(latency_ns)
                        self.current_latency = latency_ns

                # Read congestion events
                for event in self.congestion_bpf.trace_read():
                    if 'queue_len' in event:
                        parts = event.split()
                        ifindex = int(parts[1].split('=')[1])
                        qlen = int(parts[2].split('=')[1])
                        QUEUE_CONGESTION.labels(interface=self.interface).set(qlen)
                        self.current_congestion = qlen

                time.sleep(1)  # Poll every second

        except KeyboardInterrupt:
            logger.info("Stopping probes...")
            self.cleanup()

    def get_current_metrics(self) -> Dict[str, float]:
        """Get current metrics snapshot"""
        # Note: In real implementation, these would be thread-safe shared variables
        return {
            'avg_latency_ns': getattr(self, 'current_latency', 0),
            'queue_congestion': getattr(self, 'current_congestion', 0),
        }

    def cleanup(self):
        """Clean up eBPF programs"""
        if hasattr(self, 'latency_bpf'):
            self.latency_bpf.cleanup()
        if hasattr(self, 'congestion_bpf'):
            self.congestion_bpf.cleanup()

def main():
    parser = argparse.ArgumentParser(description='x0tta6bl4 Mesh Network eBPF Probes')
    parser.add_argument('--interface', '-i', required=True, help='Network interface to monitor')
    parser.add_argument('--prometheus-port', '-p', type=int, default=9090, help='Prometheus metrics port')

    args = parser.parse_args()

    probes = MeshNetworkProbes(args.interface, args.prometheus_port)

    def signal_handler(sig, frame):
        probes.cleanup()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    probes.run()

if __name__ == '__main__':
    main()