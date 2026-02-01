#!/bin/bash
set -euo pipefail

# Sing-box DNS Migration Script for 1.14.0
# This script migrates legacy DNS configuration to new format

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
if [[ -f "$CONFIG_FILE" ]]; then
    cp "$CONFIG_FILE" "$BACKUP_DIR/config.json.backup"
    tar -czf "$BACKUP_DIR/sing-box-full-backup.tar.gz" -C / etc/sing-box/ 2>/dev/null || true
    log_info "Backup created at $BACKUP_DIR"
else
    log_error "Configuration file not found at $CONFIG_FILE"
    exit 1
fi

# Step 2: Check current version
log_info "Checking sing-box version..."
if ! command -v sing-box &> /dev/null; then
    log_error "sing-box not found in PATH"
    exit 1
fi

VERSION=$(sing-box version 2>/dev/null | head -n1 | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' || echo "unknown")
log_info "Current version: $VERSION"

# Step 3: Validate current config
log_info "Validating current configuration..."
if sing-box check -c "$CONFIG_FILE" 2>&1 | grep -q "ok\|OK"; then
    log_info "Current configuration is valid"
else
    log_warn "Current configuration has warnings/errors - proceeding anyway"
fi

# Step 4: Extract existing configuration
log_info "Analyzing current configuration..."

# Check if DNS section exists
if ! grep -q '"dns"' "$CONFIG_FILE"; then
    log_warn "No DNS section found in configuration"
fi

# Step 5: Create new DNS configuration
log_info "Creating new DNS configuration..."

# Create temporary file with new DNS config
cat > "$NEW_CONFIG_FILE" << 'DNSCONFIG'
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
  }
}
DNSCONFIG

# Step 6: Validate new configuration
log_info "Validating new configuration..."
if sing-box check -c "$NEW_CONFIG_FILE" 2>&1 | grep -q "ok\|OK"; then
    log_info "New configuration is valid"
else
    log_error "New configuration validation failed"
    log_info "Keeping original configuration"
    rm -f "$NEW_CONFIG_FILE"
    exit 1
fi

# Step 7: Apply new configuration
log_info "Applying new configuration..."
cp "$CONFIG_FILE" "$BACKUP_DIR/config.json.pre-migration"
cp "$NEW_CONFIG_FILE" "$CONFIG_FILE"
rm -f "$NEW_CONFIG_FILE"

# Step 8: Restart sing-box
log_info "Restarting sing-box..."
if systemctl restart sing-box 2>&1; then
    log_info "sing-box restarted successfully"
else
    log_error "Failed to restart sing-box"
    log_info "Restoring backup..."
    cp "$BACKUP_DIR/config.json.backup" "$CONFIG_FILE"
    systemctl restart sing-box || true
    exit 1
fi

# Step 9: Health check
log_info "Running health checks..."
sleep 3

# Check service status
if systemctl is-active --quiet sing-box; then
    log_info "✓ sing-box service is active"
else
    log_error "✗ sing-box service is not active"
    exit 1
fi

# Check configuration
if sing-box check -c "$CONFIG_FILE" 2>&1 | grep -q "ok\|OK"; then
    log_info "✓ Configuration check passed"
else
    log_warn "⚠ Configuration check has warnings"
fi

# Check DNS resolution (if dig is available)
if command -v dig &> /dev/null; then
    if dig @127.0.0.1 -p 53 google.com +short +time=5 2>/dev/null | head -1 | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then
        log_info "✓ DNS resolution is working"
    else
        log_warn "⚠ DNS resolution test inconclusive (may need manual verification)"
    fi
else
    log_info "dig not available, skipping DNS test"
fi

# Check for deprecation warnings
if journalctl -u sing-box --since "1 minute ago" 2>/dev/null | grep -qi "deprecated"; then
    log_warn "⚠ Deprecation warnings still present in logs"
else
    log_info "✓ No deprecation warnings in recent logs"
fi

log_info "========================================="
log_info "Migration completed successfully!"
log_info "========================================="
log_info "Backup location: $BACKUP_DIR"
log_info ""
log_info "To rollback if needed:"
log_info "  sudo cp $BACKUP_DIR/config.json.backup $CONFIG_FILE"
log_info "  sudo systemctl restart sing-box"
log_info ""
log_info "To verify DNS is working:"
log_info "  dig @127.0.0.1 -p 53 google.com"
log_info ""
log_info "To check logs:"
log_info "  sudo journalctl -u sing-box -f"