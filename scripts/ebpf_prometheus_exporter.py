#!/usr/bin/env python3
import time
import subprocess
import json
import os
from prometheus_client import start_http_server, Counter, Gauge

# Configuration
PROG_NAME = "xdp_mesh_filter_prog"
EXPORT_PORT = 9101
COLLECTION_INTERVAL = 10

# Prometheus Metrics
XDP_RUN_TOTAL = Counter('x0tta6bl4_xdp_runs_total', 'Total number of times XDP program has run', ['prog_name', 'iface'])
XDP_PPS = Gauge('x0tta6bl4_xdp_pps', 'Processed packets per second by XDP program', ['prog_name', 'iface'])

def get_ebpf_stats():
    try:
        # Get program info in JSON
        result = subprocess.run(['sudo', 'bpftool', 'prog', 'show', 'name', PROG_NAME, '--json'], 
                                capture_output=True, text=True, check=True)
        if not result.stdout.strip():
            return None
        
        data = json.loads(result.stdout)
        if isinstance(data, list):
            data = data[0]
            
        return data.get('run_cnt', 0)
    except Exception as e:
        print(f"Error collecting eBPF stats: {e}")
        return None

def get_active_iface():
    try:
        result = subprocess.run(['sudo', 'bpftool', 'net', 'show', '--json'], 
                                capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        # Search for our program in the interfaces
        for entry in data:
            if 'xdp' in entry:
                for xdp_entry in entry['xdp']:
                    if xdp_entry.get('name') == PROG_NAME or str(xdp_entry.get('id')) in str(get_ebpf_stats()):
                        return entry.get('devname', 'unknown')
        return "unknown"
    except:
        return "unknown"

def main():
    print(f"🚀 Starting eBPF Prometheus Exporter on port {EXPORT_PORT}...")
    # Ensure stats are enabled
    subprocess.run(['sudo', 'sysctl', '-w', 'kernel.bpf_stats_enabled=1'], check=True)
    
    start_http_server(EXPORT_PORT)
    
    last_run_cnt = 0
    last_time = time.time()
    iface = get_active_iface()
    
    while True:
        current_run_cnt = get_ebpf_stats()
        current_time = time.time()
        
        if current_run_cnt is not None:
            # Update total counter
            delta_runs = current_run_cnt - last_run_cnt
            if delta_runs >= 0:
                XDP_RUN_TOTAL.labels(prog_name=PROG_NAME, iface=iface).inc(delta_runs)
                
                # Calculate PPS
                pps = delta_runs / (current_time - last_time)
                XDP_PPS.labels(prog_name=PROG_NAME, iface=iface).set(pps)
                
                print(f"[{time.strftime('%H:%M:%S')}] IFACE: {iface} | PPS: {pps:.2f} | Total Runs: {current_run_cnt}")
            
            last_run_cnt = current_run_cnt
            last_time = current_time
        else:
            print(f"[{time.strftime('%H:%M:%S')}] Waiting for {PROG_NAME} to be loaded...")
            iface = get_active_iface() # Re-check if interface changed
            
        time.sleep(COLLECTION_INTERVAL)

if __name__ == "__main__":
    main()
