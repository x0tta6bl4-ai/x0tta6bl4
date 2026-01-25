# Monitoring Toolkit

## lightwatch.py
Low-overhead resource monitor for constrained environments.

### Features
- CPU %, per-core, load averages
- Memory usage (psutil or /proc fallback)
- Disk usage for a target mount/path
- Top 8 processes by CPU (and memory)
- JSON log + live summary file for tailing
- Simple log size rotation
- Threshold warnings (CPU, Mem, Load, Disk)

### Quick Start
```bash
python monitoring/lightwatch.py &
# or with custom thresholds
python monitoring/lightwatch.py --interval 3 --cpu-warn 90 --mem-warn 90 --disk-path /mnt/AC74CC2974CBF3DC/
```
Tail live summary:
```bash
tail -f monitoring/resource_metrics.summary
```
Stop:
```bash
pkill -f lightwatch.py
```

### ENV Configuration (alternative)
Set any before running:
- LIGHTWATCH_INTERVAL
- LIGHTWATCH_CPU_WARN
- LIGHTWATCH_MEM_WARN
- LIGHTWATCH_LOAD_WARN
- LIGHTWATCH_DISK_PATH
- LIGHTWATCH_MAX_LOG_SIZE

### Suggested Thresholds
- CPU_WARN: 85
- MEM_WARN: 85
- LOAD_WARN: cores * 2
- Disk critical >= 90%

### Systemd (optional)
Create `/etc/systemd/system/lightwatch.service`:
```
[Unit]
Description=Lightweight resource watcher
After=network.target

[Service]
Type=simple
WorkingDirectory=/mnt/AC74CC2974CBF3DC/monitoring
ExecStart=/usr/bin/env python3 lightwatch.py --interval 5
Restart=always

[Install]
WantedBy=multi-user.target
```
Enable:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now lightwatch.service
```

### Interpreting Warnings
- High CPU: sustained >90% => investigate top processes
- High Memory: >90% may trigger OOM killer soon
- High Load: if > cores*2 and CPU <50% => possible IO wait
- Disk critical: >90% must prune caches, old backups, duplicate environments

### Safe Practices
- Prefer `du -sh target/* | sort -h | tail` instead of recursive `du -ah /`.
- Avoid simultaneous heavy index operations.
- Limit parallel large file deletions (IO spikes).

### Recovery Playbook
1. Check summary file for culprit processes.
2. If single runaway process: `kill -15 PID` (then -9 if needed).
3. Free disk space if critical: remove old backups, caches, duplicate venvs.
4. If memory pressure persists: reduce open VSCode windows / Chrome tabs.

### Extending
Add exporters (Prometheus) or integrate with existing dashboards by tailing JSON lines and forwarding.

---
Created: 2025-11-04
