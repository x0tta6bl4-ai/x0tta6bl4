# eBPF Telemetry Module - Installation Guide

## Overview

The eBPF Telemetry Module provides comprehensive telemetry collection from eBPF programs with high-performance map reading, perf buffer event processing, and Prometheus metrics export.

## System Requirements

### Minimum Requirements
- **OS**: Linux kernel 5.8+ (for eBPF ring buffer support)
- **Python**: 3.8+
- **RAM**: 2GB minimum, 4GB recommended
- **CPU**: 2 cores minimum, 4+ cores recommended

### Recommended Requirements
- **OS**: Linux kernel 5.15+ or 6.x
- **Python**: 3.10+
- **RAM**: 8GB+
- **CPU**: 4+ cores

## Prerequisites

### 1. Kernel Configuration

Ensure your kernel has eBPF support enabled:

```bash
# Check kernel version
uname -r

# Check eBPF support
ls /proc/sys/kernel/bpf*
cat /proc/config.gz | gunzip | grep BPF
```

Required kernel config options:
```
CONFIG_BPF=y
CONFIG_BPF_SYSCALL=y
CONFIG_BPF_JIT=y
CONFIG_HAVE_EBPF_JIT=y
CONFIG_BPF_EVENTS=y
```

### 2. System Permissions

eBPF requires elevated privileges. You have two options:

**Option A: Run as root (simplest for development)**
```bash
sudo -i
```

**Option B: Configure capabilities (recommended for production)**
```bash
# Add user to required groups
sudo usermod -a -G bpf $USER
sudo usermod -a -G perf $USER

# Set capabilities for the binary
sudo setcap cap_bpf,cap_perfmon,cap_net_admin,cap_sys_admin+ep /usr/bin/python3
```

## Installation Steps

### Step 1: Install System Dependencies

#### Ubuntu/Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    clang \
    llvm \
    libelf-dev \
    libbpf-dev \
    linux-headers-$(uname -r) \
    bpfcc-tools \
    libbpfcc-dev \
    python3-dev \
    python3-pip \
    bpftool
```

#### RHEL/CentOS/Fedora
```bash
sudo dnf install -y \
    clang \
    llvm \
    elfutils-libelf-devel \
    bpftrace \
    bpftrace-tools \
    python3-devel \
    python3-pip \
    bpftool \
    kernel-devel \
    kernel-headers
```

#### Arch Linux
```bash
sudo pacman -S \
    clang \
    llvm \
    libelf \
    bpftrace \
    python \
    python-pip \
    bpftool \
    linux-headers
```

### Step 2: Install Python Dependencies

```bash
# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate

# Install core dependencies
pip install --upgrade pip
pip install bcc prometheus-client

# Install optional dependencies for enhanced features
pip install numpy pandas  # For data analysis
pip install psutil  # For system monitoring
pip install pyyaml  # For configuration files
```

### Step 3: Install the Telemetry Module

```bash
# Navigate to the project directory
cd /path/to/x0tta6bl4

# Install in development mode
pip install -e .

# Or install from the specific module
pip install -e src/network/ebpf/
```

### Step 4: Verify Installation

```bash
# Test BCC availability
python3 -c "from bcc import BPF; print('BCC available')"

# Test Prometheus client
python3 -c "from prometheus_client import start_http_server; print('Prometheus client available')"

# Test telemetry module
python3 -c "from src.network.ebpf.telemetry_module import EBPFTelemetryCollector; print('Telemetry module available')"
```

## Configuration

### Environment Variables

Create a `.env` file or set environment variables:

```bash
# Prometheus configuration
export PROMETHEUS_PORT=9090
export PROMETHEUS_HOST=0.0.0.0

# Collection settings
export COLLECTION_INTERVAL=1.0
export BATCH_SIZE=100
export MAX_QUEUE_SIZE=10000

# Performance settings
export MAX_WORKERS=4
export READ_TIMEOUT=5.0
export POLL_TIMEOUT=100

# Security settings
export ENABLE_VALIDATION=true
export ENABLE_SANITIZATION=true
export MAX_METRIC_VALUE=1e15

# Logging
export LOG_LEVEL=INFO
export LOG_EVENTS=false
```

### Configuration File

Create `telemetry_config.yaml`:

```yaml
# Telemetry Module Configuration
collection:
  interval: 1.0  # seconds
  batch_size: 100
  max_queue_size: 10000

performance:
  max_workers: 4
  read_timeout: 5.0  # seconds
  poll_timeout: 100  # milliseconds

prometheus:
  port: 9090
  host: "0.0.0.0"

security:
  enable_validation: true
  enable_sanitization: true
  max_metric_value: 1e15
  sanitize_paths: true

error_handling:
  max_retries: 3
  retry_delay: 0.5  # seconds
  enable_fallback: true

logging:
  level: "INFO"
  events: false
```

## Docker Installation

### Dockerfile

```dockerfile
FROM ubuntu:22.04

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    clang \
    llvm \
    libelf-dev \
    libbpf-dev \
    linux-headers-generic \
    bpfcc-tools \
    libbpfcc-dev \
    python3-dev \
    python3-pip \
    bpftool \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

# Copy telemetry module
COPY src/network/ebpf/ /app/ebpf/
WORKDIR /app

# Run as non-root user (requires capabilities)
RUN useradd -m -s /bin/bash telemetry
USER telemetry

# Expose Prometheus port
EXPOSE 9090

# Run the application
CMD ["python3", "-m", "ebpf.telemetry_module"]
```

### Docker Compose

```yaml
version: '3.8'

services:
  ebpf-telemetry:
    build: .
    container_name: ebpf-telemetry
    privileged: true  # Required for eBPF
    network_mode: host  # Required for network monitoring
    volumes:
      - ./config:/app/config
      - ./logs:/app/logs
    environment:
      - PROMETHEUS_PORT=9090
      - COLLECTION_INTERVAL=1.0
      - LOG_LEVEL=INFO
    restart: unless-stopped

  prometheus:
    image: prom/prometheus:latest
    container_name: prometheus
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus-data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    restart: unless-stopped

  grafana:
    image: grafana/grafana:latest
    container_name: grafana
    ports:
      - "3000:3000"
    volumes:
      - grafana-data:/var/lib/grafana
    environment:
      - GF_SECURITY_ADMIN_PASSWORD=admin
    restart: unless-stopped

volumes:
  prometheus-data:
  grafana-data:
```

## Kubernetes Installation

### Deployment Manifest

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: ebpf-telemetry
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: ebpf-telemetry
  template:
    metadata:
      labels:
        app: ebpf-telemetry
    spec:
      hostNetwork: true
      hostPID: true
      containers:
      - name: telemetry
        image: your-registry/ebpf-telemetry:latest
        securityContext:
          privileged: true
          capabilities:
            add:
            - BPF
            - PERFMON
            - NET_ADMIN
            - SYS_ADMIN
        env:
        - name: PROMETHEUS_PORT
          value: "9090"
        - name: COLLECTION_INTERVAL
          value: "1.0"
        - name: LOG_LEVEL
          value: "INFO"
        volumeMounts:
        - name: sys
          mountPath: /sys
          readOnly: true
        - name: proc
          mountPath: /proc
          readOnly: true
        resources:
          limits:
            memory: "2Gi"
            cpu: "2"
          requests:
            memory: "512Mi"
            cpu: "500m"
      volumes:
      - name: sys
        hostPath:
          path: /sys
      - name: proc
        hostPath:
          path: /proc
```

## Troubleshooting

### Issue: BCC not available

**Error**: `ImportError: No module named 'bcc'`

**Solution**:
```bash
# Install BCC
sudo apt-get install bpfcc-tools libbpfcc-dev

# Or install from source
git clone https://github.com/iovisor/bcc.git
mkdir bcc/build; cd bcc/build
cmake ..
make
sudo make install
```

### Issue: Permission denied

**Error**: `PermissionError: [Errno 13] Permission denied`

**Solution**:
```bash
# Run with sudo
sudo python3 your_script.py

# Or set capabilities
sudo setcap cap_bpf+ep /usr/bin/python3
```

### Issue: Kernel too old

**Error**: `Kernel version too old`

**Solution**:
```bash
# Check kernel version
uname -r

# Upgrade kernel (Ubuntu)
sudo apt-get install --install-recommends linux-generic-hwe-22.04

# Reboot
sudo reboot
```

### Issue: bpftool not found

**Error**: `FileNotFoundError: bpftool not available`

**Solution**:
```bash
# Install bpftool
sudo apt-get install bpftool

# Or build from source
git clone https://github.com/libbpf/bpftool.git
cd bpftool
make
sudo make install
```

### Issue: Prometheus port already in use

**Error**: `OSError: [Errno 98] Address already in use`

**Solution**:
```bash
# Find process using port 9090
sudo lsof -i :9090

# Kill the process or change port
export PROMETHEUS_PORT=9091
```

## Performance Tuning

### For High-Throughput Environments

```python
from src.network.ebpf.telemetry_module import TelemetryConfig, EBPFTelemetryCollector

config = TelemetryConfig(
    collection_interval=0.1,  # 100ms
    batch_size=1000,
    max_queue_size=100000,
    max_workers=8,
    read_timeout=2.0,
    poll_timeout=50
)

collector = EBPFTelemetryCollector(config)
```

### For Low-Latency Environments

```python
config = TelemetryConfig(
    collection_interval=0.05,  # 50ms
    batch_size=50,
    max_queue_size=5000,
    max_workers=2,
    read_timeout=1.0,
    poll_timeout=10
)
```

### For Resource-Constrained Environments

```python
config = TelemetryConfig(
    collection_interval=5.0,  # 5 seconds
    batch_size=50,
    max_queue_size=1000,
    max_workers=1,
    read_timeout=10.0,
    poll_timeout=500
)
```

## Security Hardening

### 1. Enable Validation and Sanitization

```python
config = TelemetryConfig(
    enable_validation=True,
    enable_sanitization=True,
    sanitize_paths=True
)
```

### 2. Set Resource Limits

```python
config = TelemetryConfig(
    max_metric_value=1e12,
    max_queue_size=10000
)
```

### 3. Use Non-Root User with Capabilities

```bash
# Create dedicated user
sudo useradd -r -s /bin/false ebpf-telemetry

# Set capabilities
sudo setcap cap_bpf,cap_perfmon+ep /usr/bin/python3
```

## Verification

After installation, verify everything works:

```bash
# Run basic test
python3 -m src.network.ebpf.telemetry_module

# Check Prometheus endpoint
curl http://localhost:9090/metrics

# Check logs
tail -f /var/log/ebpf-telemetry.log
```

## Next Steps

- Read the [Usage Guide](TELEMETRY_USAGE.md) for examples
- Review the [Architecture Documentation](TELEMETRY_ARCHITECTURE.md)
- Configure Prometheus to scrape metrics
- Set up Grafana dashboards

## Support

For issues and questions:
- Check the troubleshooting section above
- Review logs: `tail -f /var/log/ebpf-telemetry.log`
- Enable debug logging: `export LOG_LEVEL=DEBUG`
