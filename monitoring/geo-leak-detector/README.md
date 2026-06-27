# Geo-Leak Detector for x0tta6bl4

Real-time geolocation leak detection system with multi-vector monitoring (IP, DNS, WebRTC), automated kill-switch, and MAPE-K integration.

## Features

- **Multi-Vector Leak Detection**: IP, DNS, WebRTC, IPv6
- **Real-Time Monitoring**: Continuous checks with configurable intervals
- **Automated Kill-Switch**: Emergency network isolation on critical leaks
- **Telegram Alerts**: Instant notifications for security events
- **Prometheus Metrics**: Full observability and monitoring
- **MAPE-K Integration**: Integration with x0tta6bl4's consciousness engine
- **WebSocket Dashboard**: Real-time event streaming
- **PostgreSQL Storage**: Persistent leak event logging
- **Redis Pub/Sub**: Real-time alert distribution

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Geo-Leak Detector                            │
├─────────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ IP Leak     │  │ DNS Leak    │  │ WebRTC Leak │             │
│  │ Detector    │  │ Detector    │  │ Detector    │             │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘             │
│         └─────────────────┼─────────────────┘                   │
│                           ▼                                     │
│              ┌─────────────────────┐                           │
│              │  Leak Detection     │                           │
│              │  Engine             │                           │
│              └──────────┬──────────┘                           │
│                         ▼                                       │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ PostgreSQL  │  │ Redis       │  │ Telegram    │             │
│  │ Storage     │  │ Pub/Sub     │  │ Alerts      │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│                                                                 │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │ Kill-Switch │  │ Prometheus  │  │ MAPE-K      │             │
│  │ Manager     │  │ Metrics     │  │ Integration │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Docker Compose (Recommended)

```bash
cd monitoring/geo-leak-detector/docker

# Copy and edit environment variables
cp .env.example .env
nano .env

# Start services
docker-compose up -d

# Check status
docker-compose ps
curl http://localhost:8080/api/v1/health
```

### Manual Installation

```bash
cd monitoring/geo-leak-detector
sudo ./scripts/install.sh
```

## Configuration

Environment variables (via `.env` file or system environment):

```bash
# Database
GEO_DB_HOST=localhost
GEO_DB_PORT=5432
GEO_DB_NAME=geo_leak_detector
GEO_DB_USER=geo_user
GEO_DB_PASSWORD=changeme

# Redis
GEO_REDIS_HOST=localhost
GEO_REDIS_PORT=6379

# Telegram Alerts
GEO_TELEGRAM_ENABLED=true
GEO_TELEGRAM_BOT_TOKEN=your_bot_token
GEO_TELEGRAM_CHAT_ID=your_chat_id

# Detection Settings
GEO_CHECK_INTERVAL=30
GEO_AUTO_REMEDIATE=true
GEO_EXPECTED_EXIT_IPS=1.2.3.4,5.6.7.8
GEO_EXPECTED_DNS_SERVERS=127.0.0.1

# MAPE-K Integration
GEO_MAPEK_ENABLED=true
GEO_MAPEK_NODE_ID=geo-leak-detector
```

## API Endpoints

### Health & Status
- `GET /api/v1/health` - Health check
- `GET /api/v1/status` - System status
- `GET /api/v1/config` - Current configuration

### Leak Events
- `GET /api/v1/leaks` - List leak events
- `GET /api/v1/leaks/{id}` - Get specific leak
- `POST /api/v1/leaks/{id}/resolve` - Mark as resolved
- `GET /api/v1/leaks/stats/summary` - Statistics

### Detection Control
- `POST /api/v1/detection/start` - Start monitoring
- `POST /api/v1/detection/stop` - Stop monitoring
- `POST /api/v1/detection/check` - Run manual check

### Kill-Switch
- `POST /api/v1/killswitch/trigger` - Trigger kill-switch
- `POST /api/v1/killswitch/restore` - Restore network

### WebSocket
- `WS /api/v1/ws` - Real-time events
- `WS /api/v1/ws/leaks` - Leak events only

### Metrics
- `GET /api/v1/metrics` - Prometheus metrics

## MAPE-K Integration

The Geo-Leak Detector integrates with x0tta6bl4's MAPE-K architecture:

```python
# Report leak to MAPE-K
await mapek_integration.report_leak_to_mapek(leak_data)

# Report status
await mapek_integration.report_status_to_mapek(status_data)

# Handle consciousness directives
await mapek_integration.handle_consciousness_directive(directive)
```

## Telegram Bot Setup

1. Create bot with [@BotFather](https://t.me/botfather)
2. Get chat ID:
   ```bash
   curl https://api.telegram.org/bot<TOKEN>/getUpdates
   ```
3. Configure environment variables

## Kill-Switch Actions

When a critical leak is detected:

1. **Block All Traffic** - iptables/nftables block
2. **Kill VPN** - Stop OpenVPN, WireGuard, WARP
3. **Kill Browsers** - Terminate Firefox, Chrome, etc.
4. **Flush DNS** - Clear caches, restart DNS services
5. **Disable IPv6** - Kernel-level IPv6 disable

## Monitoring

### Prometheus Metrics

- `geo_leak_detector_leaks_total` - Total leaks by type/severity
- `geo_leak_detector_check_duration_seconds` - Check latency
- `geo_leak_detector_killswitch_triggered_total` - Kill-switch triggers
- `geo_leak_detector_alerts_sent_total` - Alerts by channel

### Grafana Dashboard

Import `docker/grafana-dashboard.json` for visualization.

## Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest tests/

# Run locally
python src/main.py
```

## Security Considerations

- Requires `NET_ADMIN` capability for kill-switch
- Store Telegram token securely
- Use strong database passwords
- Enable TLS for production

## License

Part of x0tta6bl4 project.
