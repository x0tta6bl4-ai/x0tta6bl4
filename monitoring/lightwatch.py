#!/usr/bin/env python3
"""
lightwatch.py - Lightweight system resource watcher.

Purpose:
  Continuously (default: every 5s) logs CPU, Memory, Disk usage and top processes.
  Emits structured JSON lines and rotating plain-text summary for quick tailing.

Design goals:
  - Very low overhead (psutil if available, fallback to /proc parsing)
  - Safe on constrained systems (single thread, no heavy shelling out)
  - Threshold-based WARN lines (configurable via env or CLI)
  - Log rotation (simple size cap) without external deps

Outputs:
  - monitoring/resource_metrics.log      (JSON lines newest appended)
  - monitoring/resource_metrics.summary  (human readable last snapshot)

Configuration precedence: CLI args > ENV vars > defaults
  Interval:          --interval / LIGHTWATCH_INTERVAL (int seconds, default 5)
  CPU warn percent:  --cpu-warn / LIGHTWATCH_CPU_WARN (default 85)
  Mem warn percent:  --mem-warn / LIGHTWATCH_MEM_WARN (default 85)
  Load warn:         --load-warn / LIGHTWATCH_LOAD_WARN (default: cores * 2)
  Disk path:         --disk-path / LIGHTWATCH_DISK_PATH (default mount root '/')
  Log max bytes:     --max-log-size / LIGHTWATCH_MAX_LOG_SIZE (default 5_000_000)

Exit codes:
  0 - normal termination (Ctrl+C)
  1 - fatal initialization error

Example:
  python monitoring/lightwatch.py --interval 3 --cpu-warn 90 --mem-warn 90 &
  tail -f monitoring/resource_metrics.summary

"""
from __future__ import annotations
import os
import sys
import time
import json
import argparse
import datetime as dt
from typing import List, Tuple, Dict, Any

try:
    import psutil  # type: ignore
    HAVE_PSUTIL = True
except Exception:
    HAVE_PSUTIL = False

LOG_JSON = os.path.join(os.path.dirname(__file__), 'resource_metrics.log')
LOG_SUMMARY = os.path.join(os.path.dirname(__file__), 'resource_metrics.summary')

DEFAULT_INTERVAL = int(os.getenv('LIGHTWATCH_INTERVAL', '5'))
DEFAULT_CPU_WARN = int(os.getenv('LIGHTWATCH_CPU_WARN', '85'))
DEFAULT_MEM_WARN = int(os.getenv('LIGHTWATCH_MEM_WARN', '85'))
DEFAULT_LOAD_WARN = os.getenv('LIGHTWATCH_LOAD_WARN')  # derive later
DEFAULT_DISK_PATH = os.getenv('LIGHTWATCH_DISK_PATH', '/')
DEFAULT_MAX_LOG_SIZE = int(os.getenv('LIGHTWATCH_MAX_LOG_SIZE', str(5_000_000)))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description='Lightweight system resource watcher')
    p.add_argument('--interval', type=int, default=DEFAULT_INTERVAL, help='Seconds between samples')
    p.add_argument('--cpu-warn', type=int, default=DEFAULT_CPU_WARN, help='CPU percent warning threshold')
    p.add_argument('--mem-warn', type=int, default=DEFAULT_MEM_WARN, help='Memory percent warning threshold')
    p.add_argument('--load-warn', type=float, default=None, help='Load average (1m) warning threshold')
    p.add_argument('--disk-path', type=str, default=DEFAULT_DISK_PATH, help='Disk path to monitor')
    p.add_argument('--max-log-size', type=int, default=DEFAULT_MAX_LOG_SIZE, help='Max JSON log size before truncation')
    return p.parse_args()


def get_load_average() -> Tuple[float, float, float]:
    if hasattr(os, 'getloadavg'):
        try:
            return os.getloadavg()
        except OSError:
            return (0.0, 0.0, 0.0)
    return (0.0, 0.0, 0.0)


def get_disk_usage(path: str) -> Dict[str, Any]:
    try:
        st = os.statvfs(path)
        total = st.f_frsize * st.f_blocks
        free = st.f_frsize * st.f_bavail
        used = total - free
        pct = round((used / total) * 100, 2) if total else 0.0
        return {'path': path, 'total_bytes': total, 'used_bytes': used, 'free_bytes': free, 'percent': pct}
    except Exception as e:
        return {'path': path, 'error': str(e)}


def fallback_mem() -> Dict[str, Any]:
    try:
        with open('/proc/meminfo', 'r') as f:
            data = f.read().splitlines()
        kv = {}
        for line in data:
            if ':' in line:
                k, v = line.split(':', 1)
                kv[k.strip()] = v.strip()
        total_kb = int(kv.get('MemTotal', '0 kB').split()[0])
        avail_kb = int(kv.get('MemAvailable', '0 kB').split()[0])
        used_kb = total_kb - avail_kb
        pct = round((used_kb / total_kb) * 100, 2) if total_kb else 0.0
        return {'total_mb': round(total_kb/1024, 2), 'used_mb': round(used_kb/1024, 2), 'available_mb': round(avail_kb/1024, 2), 'percent': pct}
    except Exception as e:
        return {'error': str(e)}


def collect_metrics(disk_path: str) -> Dict[str, Any]:
    ts = dt.datetime.utcnow().isoformat() + 'Z'
    load1, load5, load15 = get_load_average()

    if HAVE_PSUTIL:
        cpu_pct = psutil.cpu_percent(interval=None)
        per_core = psutil.cpu_percent(interval=None, percpu=True)
        mem = psutil.virtual_memory()
        mem_info = {
            'total_mb': round(mem.total/1024/1024, 2),
            'used_mb': round(mem.used/1024/1024, 2),
            'available_mb': round(mem.available/1024/1024, 2),
            'percent': mem.percent
        }
        top_procs = []
        for p in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                info = p.info
                top_procs.append(info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        # sort by cpu then mem
        top_procs.sort(key=lambda x: (-x.get('cpu_percent', 0), -x.get('memory_percent', 0)))
        top_sample = top_procs[:8]
    else:
        cpu_pct = 0.0
        per_core = []
        mem_info = fallback_mem()
        top_sample = []

    disk = get_disk_usage(disk_path)

    return {
        'timestamp': ts,
        'cpu_percent': cpu_pct,
        'cpu_per_core': per_core,
        'load_avg': {'1m': load1, '5m': load5, '15m': load15},
        'memory': mem_info,
        'disk': disk,
        'top_processes': top_sample,
    }


def rotate_if_needed(path: str, max_bytes: int) -> None:
    try:
        if os.path.exists(path) and os.path.getsize(path) > max_bytes:
            # Simple truncation: keep last 25% of file
            with open(path, 'rb') as f:
                data = f.read()
            keep = data[int(len(data)*0.75):]
            with open(path, 'wb') as f:
                f.write(keep)
    except Exception:
        pass


def write_summary(metrics: Dict[str, Any]) -> None:
    try:
        mem = metrics['memory']
        disk = metrics['disk']
        lines = [
            f"Timestamp: {metrics['timestamp']}",
            f"CPU: {metrics['cpu_percent']}% | Load(1/5/15): {metrics['load_avg']['1m']:.2f}/{metrics['load_avg']['5m']:.2f}/{metrics['load_avg']['15m']:.2f}",
            f"Mem: {mem.get('used_mb','?')}MB/{mem.get('total_mb','?')}MB ({mem.get('percent','?')}%) Avail: {mem.get('available_mb','?')}MB",
            f"Disk[{disk.get('path')}] Used: {disk.get('used_bytes','?')} / {disk.get('total_bytes','?')} ({disk.get('percent','?')}%) Free: {disk.get('free_bytes','?')}",
            "Top Processes (pid name cpu% mem%)" ,
        ]
        for p in metrics.get('top_processes', []):
            lines.append(f"  {p.get('pid')} {p.get('name','?')[:22]:22} {p.get('cpu_percent',0):5.1f} {p.get('memory_percent',0):5.1f}")
        with open(LOG_SUMMARY, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')
    except Exception:
        pass


def main() -> int:
    args = parse_args()
    cores = os.cpu_count() or 1
    load_warn = args.load_warn if args.load_warn is not None else (cores * 2.0)

    print(f"[lightwatch] starting interval={args.interval}s cpu_warn={args.cpu_warn}% mem_warn={args.mem_warn}% load_warn={load_warn} disk={args.disk_path}")
    print(f"[lightwatch] log files: {LOG_JSON}, {LOG_SUMMARY}")

    while True:
        start = time.time()
        m = collect_metrics(args.disk_path)
        rotate_if_needed(LOG_JSON, args.max_log_size)
        try:
            with open(LOG_JSON, 'a', encoding='utf-8') as f:
                f.write(json.dumps(m, ensure_ascii=False) + '\n')
        except Exception as e:
            print(f"[lightwatch][error] cannot write json log: {e}", file=sys.stderr)
        write_summary(m)

        # Emit warnings
        mem_pct = m['memory'].get('percent', 0)
        cpu_pct = m['cpu_percent']
        load1 = m['load_avg']['1m']
        disk_pct = m['disk'].get('percent', 0)
        if cpu_pct >= args.cpu_warn:
            print(f"[WARN] High CPU {cpu_pct:.1f}%")
        if isinstance(mem_pct, (int, float)) and mem_pct >= args.mem_warn:
            print(f"[WARN] High Memory {mem_pct:.1f}%")
        if load1 >= load_warn:
            print(f"[WARN] High Load1 {load1:.2f} (warn {load_warn})")
        if isinstance(disk_pct, (int, float)) and disk_pct >= 90:
            print(f"[WARN] Disk critical {disk_pct:.1f}%")

        # Sleep remainder
        elapsed = time.time() - start
        to_sleep = max(0, args.interval - elapsed)
        try:
            time.sleep(to_sleep)
        except KeyboardInterrupt:
            print('[lightwatch] received Ctrl+C, exiting.')
            return 0
        except Exception:
            pass

    return 0


if __name__ == '__main__':
    sys.exit(main())
