# SPIRE Setup Guide

This guide covers setting up SPIRE (SPIFFE Runtime Environment) for local development and testing of mTLS and workload identity features.

## Prerequisites

- Docker and Docker Compose installed
- Linux or macOS (Docker Desktop on macOS supports Unix domain sockets)
- Python 3.9+
- `pyspiffe` Python package (optional, for SPIRE integration tests)

## Quick Start

### 1. Start SPIRE Services

```bash
chmod +x scripts/spire/start-spire.sh
scripts/spire/start-spire.sh
```

This will:
- Create necessary directories
- Start SPIRE server and agent containers
- Wait for services to be ready
- Create the agent socket at `/tmp/spire-agent/public/api.sock`

### 2. Verify SPIRE is Running

```bash
# Check if socket exists and is accessible
ls -la /tmp/spire-agent/public/api.sock

# Check Docker containers
docker ps | grep spire
```

### 3. Run Tests

```bash
# Run SPIRE integration tests
pytest tests/integration/test_spire_integration.py -v

# Run all tests including SPIRE
pytest tests/ -v -k "spire or mTLS"
```

## Configuration

### Server Configuration

**File**: `scripts/spire/server-config.conf`

Key settings:
- `bind_port`: SPIRE server port (default: 8081)
- `trust_domain`: Trust domain for SPIFFE IDs (default: example.com)
- `default_x509_svid_ttl`: X.509 SVID time-to-live (default: 1h)

### Agent Configuration

**File**: `scripts/spire/agent-config.conf`

Key settings:
- `socket_path`: Path to Workload API socket (default: /spire-agent-socket-dir/api.sock)
- `server_address`: SPIRE server address (default: spire-server)
- `server_port`: SPIRE server port (default: 8081)

## Using SPIRE in Your Code

### Python Integration

```python
from src.security.spire_integration import SPIREClient, SPIREConfig

# Create SPIRE client
config = SPIREConfig(trust_domain="example.com")
client = SPIREClient(config)

# Check if SPIRE is available
if client.is_available():
    # Fetch X.509 SVID
    context = client.fetch_x509_context()
    cert = context["certificate"]
    key = context["key"]
```

### Workload Registration

When SPIRE agent is running, register workloads:

```bash
# Register a workload
docker-compose -f docker-compose.spire.yml exec spire-server \
  spire-server entry create \
    -parentID spiffe://example.com/spire/agent/docker/$(hostname) \
    -spiffeID spiffe://example.com/myworkload \
    -selector docker:image-sha256:abc123...
```

## Troubleshooting

### SPIRE Agent Socket Not Available

```bash
# Check agent logs
docker-compose -f docker-compose.spire.yml logs spire-agent

# Verify permissions on socket directory
ls -la /tmp/spire-agent/public/

# Recreate directory if needed
rm -rf /tmp/spire-agent/public
mkdir -p /tmp/spire-agent/public
chmod 777 /tmp/spire-agent/public
```

### Connection Refused

```bash
# Check if services are running
docker-compose -f docker-compose.spire.yml ps

# Check server logs
docker-compose -f docker-compose.spire.yml logs spire-server

# Restart services
docker-compose -f docker-compose.spire.yml restart
```

### Python Import Errors

Install required dependencies:

```bash
pip install pyspiffe grpcio protobuf
```

## Cleanup

Stop and remove SPIRE services:

```bash
docker-compose -f docker-compose.spire.yml down

# Remove volumes (persistent data)
docker-compose -f docker-compose.spire.yml down -v

# Remove socket directory
rm -rf /tmp/spire-agent/public
```

## Production Deployment

For production:

1. **Use persistent storage**: Configure proper database backend instead of SQLite
2. **Enable TLS**: Configure mutual TLS between server and agent
3. **Set up monitoring**: Use Prometheus metrics from SPIRE
4. **Configure UpstreamAuthority**: Use intermediate CA or root CA provider
5. **Scale agents**: Deploy agents on all nodes needing workload identity

See [SPIRE documentation](https://spiffe.io/docs/latest/spire-about/) for production setup.

## Metrics and Monitoring

SPIRE exposes Prometheus metrics on port 8088:

```bash
# Access metrics
curl http://localhost:8088/metrics

# Monitor from Prometheus
docker-compose -f docker-compose.spire.yml exec spire-server \
  curl http://localhost:8088/metrics
```

## Testing

### Unit Tests

```bash
# Test SPIRE client without agent running
pytest tests/unit/ -k spire

# This uses mocks and doesn't require SPIRE
```

### Integration Tests

```bash
# Test with actual SPIRE agent running
pytest tests/integration/test_spire_integration.py -v -m integration

# This requires SPIRE services to be running
```

### End-to-End Tests

```bash
# Run with Docker Compose
docker-compose -f docker-compose.spire.yml run x0tta6bl4-test

# Or manually after starting SPIRE
scripts/spire/start-spire.sh
pytest tests/ -v
```
