# Sing-box 1.14.0 Migration Guide

## Overview
This guide provides step-by-step instructions for migrating sing-box DNS configuration from legacy format to 1.14.0+ format.

## Pre-Migration Checklist

### 1. Backup Current Configuration
```bash
# Create backup directory
mkdir -p /etc/sing-box/backups/$(date +%Y%m%d_%H%M%S)

# Backup current config
cp /etc/sing-box/config.json /etc/sing-box/backups/$(date +%Y%m%d_%H%M%S)/

# Backup entire sing-box directory
tar -czf /etc/sing-box/backups/sing-box-full-$(date +%Y%m%d_%H%M%S).tar.gz /etc/sing-box/
```

### 2. Verify Current Version
```bash
sing-box version
# Should show 1.12.0 or higher for this migration
```

### 3. Test Current Health
```bash
# Check if sing-box is running
systemctl status sing-box

# Test connectivity
sing-box check -c /etc/sing-box/config.json

# Check logs for errors
journalctl -u sing-box -n 50 --no-pager
```

## Migration Steps

### Step 1: Legacy DNS Configuration (OLD)
```json
{
  "dns": {
    "servers": [
      "8.8.8.8",
      "8.8.4.4",
      "1.1.1.1"
    ]
  }
}
```

### Step 2: New DNS Configuration (1.14.0+)
```json
{
  "dns": {
    "servers": [
      {
        "tag": "google-dns",
        "address": "8.8.8.8",
        "address_resolver": "local-dns"
      },
      {
        "tag": "google-dns-backup",
        "address": "8.8.4.4",
        "address_resolver": "local-dns"
      },
      {
        "tag": "cloudflare-dns",
        "address": "1.1.1.1",
        "address_resolver": "local-dns"
      },
      {
        "tag": "local-dns",
        "address": "local"
      }
    ],
    "rules": [
      {
        "geosite": "cn",
        "server": "local-dns"
      }
    ],
    "final": "google-dns",
    "strategy": "ipv4_only",
    "disable_cache": false,
    "disable_expire": false
  }
}
```

### Step 3: Full Configuration Example
```json
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "dns": {
    "servers": [
      {
        "tag": "google-dns",
        "address": "8.8.8.8",
        "address_resolver": "local-dns"
      },
      {
        "tag": "google-dns-backup",
        "address": "8.8.4.4",
        "address_resolver": "local-dns"
      },
      {
        "tag": "cloudflare-dns",
        "address": "1.1.1.1",
        "address_resolver": "local-dns"
      },
      {
        "tag": "local-dns",
        "address": "local"
      }
    ],
    "rules": [
      {
        "geosite": "cn",
        "server": "local-dns"
      },
      {
        "domain_suffix": ".local",
        "server": "local-dns"
      }
    ],
    "final": "google-dns",
    "strategy": "ipv4_only",
    "disable_cache": false,
    "disable_expire": false
  },
  "inbounds": [
    {
      "type": "vless",
      "tag": "vless-in",
      "listen": "0.0.0.0",
      "listen_port": 443,
      "users": [
        {
          "uuid": "YOUR_UUID_HERE",
          "flow": "xtls-rprx-vision"
        }
      ],
      "tls": {
        "enabled": true,
        "server_name": "www.google.com",
        "reality": {
          "enabled": true,
          "handshake": {
            "server": "www.google.com",
            "server_port": 443
          },
          "private_key": "YOUR_PRIVATE_KEY",
          "short_id": ["YOUR_SHORT_ID"]
        }
      }
    }
  ],
  "outbounds": [
    {
      "type": "direct",
      "tag": "direct"
    },
    {
      "type": "block",
      "tag": "block"
    }
  ],
  "route": {
    "rules": [
      {
        "protocol": "dns",
        "outbound": "dns-out"
      }
    ],
    "final": "direct",
    "auto_detect_interface": true
  }
}
```

## Deployment Script

Create `/usr/local/bin/migrate-sing-box-dns.sh`:

```bash
#!/bin/bash
set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
BACKUP_DIR="/etc/sing-box/backups/$(date +%Y%m%d_%H%M%S)"
CONFIG_FILE="/etc/sing-box/config.json"
NEW_CONFIG_FILE="/etc/sing-box/config.json.new"

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Step 1: Create backup
log_info "Creating backup..."
mkdir -p "$BACKUP_DIR"
cp "$CONFIG_FILE" "$BACKUP_DIR/config.json.backup"
tar -czf "$BACKUP_DIR/sing-box-full-backup.tar.gz" /etc/sing-box/ 2>/dev/null || true
log_info "Backup created at $BACKUP_DIR"

# Step 2: Check current version
log_info "Checking sing-box version..."
if ! command -v sing-box &> /dev/null; then
    log_error "sing-box not found"
    exit 1
fi

VERSION=$(sing-box version | head -n1 | grep -oP '\d+\.\d+\.\d+' || echo "unknown")
log_info "Current version: $VERSION"

# Step 3: Validate current config
log_info "Validating current configuration..."
if sing-box check -c "$CONFIG_FILE" 2>&1; then
    log_info "Current configuration is valid"
else
    log_warn "Current configuration has warnings/errors"
fi

# Step 4: Create new configuration
log_info "Creating new configuration..."
cat > "$NEW_CONFIG_FILE" << 'EOF'
{
  "log": {
    "level": "warn",
    "timestamp": true
  },
  "dns": {
    "servers": [
      {
        "tag": "google-dns",
        "address": "8.8.8.8",
        "address_resolver": "local-dns"
      },
      {
        "tag": "google-dns-backup",
        "address": "8.8.4.4",
        "address_resolver": "local-dns"
      },
      {
        "tag": "cloudflare-dns",
        "address": "1.1.1.1",
        "address_resolver": "local-dns"
      },
      {
        "tag": "local-dns",
        "address": "local"
      }
    ],
    "rules": [
      {
        "geosite": "cn",
        "server": "local-dns"
      }
    ],
    "final": "google-dns",
    "strategy": "ipv4_only",
    "disable_cache": false,
    "disable_expire": false
  }
}
EOF

# Step 5: Validate new configuration
log_info "Validating new configuration..."
if sing-box check -c "$NEW_CONFIG_FILE" 2>&1; then
    log_info "New configuration is valid"
else
    log_error "New configuration validation failed"
    exit 1
fi

# Step 6: Apply new configuration
log_info "Applying new configuration..."
cp "$CONFIG_FILE" "$BACKUP_DIR/config.json.pre-migration"
cp "$NEW_CONFIG_FILE" "$CONFIG_FILE"

# Step 7: Restart sing-box
log_info "Restarting sing-box..."
if systemctl restart sing-box 2>&1; then
    log_info "sing-box restarted successfully"
else
    log_error "Failed to restart sing-box"
    log_info "Restoring backup..."
    cp "$BACKUP_DIR/config.json.backup" "$CONFIG_FILE"
    systemctl restart sing-box
    exit 1
fi

# Step 8: Health check
log_info "Running health checks..."
sleep 2

# Check service status
if systemctl is-active --quiet sing-box; then
    log_info "sing-box service is active"
else
    log_error "sing-box service is not active"
    exit 1
fi

# Check connectivity
if sing-box check -c "$CONFIG_FILE" 2>&1 | grep -q "ok"; then
    log_info "Configuration check passed"
else
    log_warn "Configuration check has warnings"
fi

# Check DNS resolution
if dig @127.0.0.1 -p 53 google.com +short +time=5 2>/dev/null | head -1 | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
    log_info "DNS resolution is working"
else
    log_warn "DNS resolution test inconclusive"
fi

log_info "Migration completed successfully!"
log_info "Backup location: $BACKUP_DIR"
log_info "To rollback: cp $BACKUP_DIR/config.json.backup $CONFIG_FILE && systemctl restart sing-box"
```

Make it executable:
```bash
chmod +x /usr/local/bin/migrate-sing-box-dns.sh
```

## Rollback Procedure

If issues occur after migration:

```bash
# Stop sing-box
systemctl stop sing-box

# Restore backup
cp /etc/sing-box/backups/BACKUP_TIMESTAMP/config.json.backup /etc/sing-box/config.json

# Restart sing-box
systemctl start sing-box

# Verify
systemctl status sing-box
sing-box check -c /etc/sing-box/config.json
```

## Post-Migration Verification

### 1. Check Logs
```bash
journalctl -u sing-box -f
```

### 2. Test DNS Resolution
```bash
# Test through sing-box DNS
dig @127.0.0.1 -p 53 google.com

# Test with specific server
dig @8.8.8.8 google.com
```

### 3. Check Configuration
```bash
sing-box check -c /etc/sing-box/config.json
```

### 4. Monitor Metrics
```bash
# Check if metrics endpoint is available
curl -s http://localhost:9090/metrics | grep sing_box
```

## Troubleshooting

### Issue: "legacy DNS servers is deprecated"
**Solution**: Configuration has been migrated. Verify with:
```bash
grep -A5 '"dns"' /etc/sing-box/config.json
```

### Issue: DNS resolution fails
**Solution**: 
1. Check firewall rules
2. Verify DNS servers are reachable
3. Check sing-box logs for errors

### Issue: Service won't start
**Solution**:
1. Check configuration syntax: `sing-box check -c /etc/sing-box/config.json`
2. Restore from backup
3. Check for port conflicts

## References

- [Sing-box Documentation](https://sing-box.sagernet.org/)
- [DNS Configuration Guide](https://sing-box.sagernet.org/configuration/dns/)
- [Migration Notes](https://sing-box.sagernet.org/migration/)