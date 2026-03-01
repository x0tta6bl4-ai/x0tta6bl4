#!/usr/bin/env python3
"""
x0tta6bl4 STABLE eBPF Monitor (v2.1)
Minimalist BPF program to monitor packets without complex kernel header dependencies.
Compatible with Ubuntu 24.04+
"""

from bcc import BPF
import time
import sys
import os

# Minimal BPF program - just count packets
bpf_text = """
BPF_HASH(stats, u32, u64);

int count_packets(struct __sk_buff *skb) {
    u32 key = 0;
    u64 *val, next_val = 1;

    val = stats.lookup(&key);
    if (val) {
        next_val = *val + 1;
    }
    stats.update(&key, &next_val);
    return 1;
}
"""

def main(interface="singbox_tun"):
    print(f"[*] Starting Stable eBPF Monitor on {interface}...")
    
    # Check if interface exists
    import subprocess
    res = subprocess.run(["ip", "addr", "show", interface], capture_output=True)
    if res.returncode != 0:
        print(f"[!] Interface {interface} not found. Waiting...")        return

    try:
        b = BPF(text=bpf_text)
        fn = b.load_func("count_packets", BPF.SOCKET_FILTER)
        BPF.attach_raw_socket(fn, interface)
        
        print(f"[*] Securely attached to {interface}. Monitoring active.")
        
        while True:
            try:
                time.sleep(5)
                for k, v in b["stats"].items():
                    print(f"[eBPF] Total Packets: {v.value}")
            except KeyboardInterrupt:
                break
    except Exception as e:
        print(f"[!] eBPF Failure: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()
