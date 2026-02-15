# Environment Variables Reference

## Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `X0TTA6BL4_NODE_ID` | Unique node identifier | `node-eu-west-01` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@localhost:5432/x0tta6bl4` |
| `ADMIN_TOKEN` | Admin API authentication token | (generate with `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`) |

## Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `X0TTA6BL4_PRODUCTION` | `false` | Enable production mode |
| `X0TTA6BL4_SPIFFE` | `false` | Enable SPIFFE/SPIRE identity |
| `X0TTA6BL4_FORCE_MOCK_SPIFFE` | `false` | Mock SPIFFE for testing |
| `YGGDRASIL_PEERS` | (empty) | Comma-separated Yggdrasil peer addresses |
| `PROMETHEUS_PORT` | `9090` | Prometheus metrics port |
| `GRAFANA_PORT` | `3000` | Grafana dashboard port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG/INFO/WARNING/ERROR) |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection for caching |
| `STRIPE_WEBHOOK_SECRET` | (empty) | Stripe webhook signing secret |
| `TELEGRAM_BOT_TOKEN` | (empty) | Telegram bot API token |

## Security Notes
- Never commit `.env` files to git
- Generate tokens with `secrets.token_urlsafe(32)` (not random strings)
- Rotate `ADMIN_TOKEN` after every team member departure
- Use separate `.env` files for dev/staging/production
