# x0tta6bl4 Xray VPS Deployment Plan

## Table of Contents

1. [Pre-Deployment Checklist](#pre-deployment-checklist)
2. [Deployment Procedures](#deployment-procedures)
3. [Health Check Procedures](#health-check-procedures)
4. [Rollback Procedures](#rollback-procedures)
5. [Emergency Procedures](#emergency-procedures)
6. [Post-Deployment Verification](#post-deployment-verification)

---

## Pre-Deployment Checklist

### 1. Server Requirements Verification

```bash
# Check system requirements
./scripts/check-requirements.sh
```

| Requirement | Minimum | Recommended | Check Command |
|-------------|---------|-------------|---------------|
| RAM | 512MB | 1GB | `free -h` |
| Disk Space | 1GB | 5GB | `df -h` |
| CPU Cores | 1 | 2+ | `nproc` |
| OS Version | Ubuntu 20.04 | Ubuntu 22.04 | `lsb_release -a` |
| Kernel Version | 4.9+ | 5.10+ | `uname -r` |

### 2. Network Requirements

- [ ] Clean IP (not blacklisted)
- [ ] Ports 443, 8443, 8388, 9443, 8080 available
- [ ] Outbound internet access
- [ ] DNS resolution working
- [ ] NTP time synchronization enabled

```bash
# Verify network requirements
./scripts/check-network.sh
```

### 3. Security Checklist

- [ ] Root access secured (SSH key only)
- [ ] Firewall configured (UFW/Firewalld)
- [ ] Fail2ban installed (optional)
- [ ] Automatic updates configured (optional)
- [ ] Backup strategy in place

### 4. Backup Current Configuration

```bash
# Create pre-deployment backup
sudo bash scripts/backup-config.sh --pre-deployment
```

Backup includes:
- Current Xray configuration
- TLS certificates
- System settings
- Firewall rules
- Service definitions

---

## Deployment Procedures

### Phase 1: Environment Preparation (5 minutes)

```bash
#!/bin/bash
# Phase 1: Environment Preparation

set -euo pipefail

echo "=== Phase 1: Environment Preparation ==="

# 1.1 Update system packages
log_info "Updating system packages..."
apt-get update && apt-get upgrade -y

# 1.2 Install prerequisites
log_info "Installing prerequisites..."
apt-get install -y curl wget unzip jq openssl uuid-runtime qrencode \
    net-tools iptables-persistent ntp

# 1.3 Synchronize time
log_info "Synchronizing system time..."
timedatectl set-ntp true
ntpd -q -g || chronyc makestep || true

# 1.4 Create backup directory
mkdir -p /root/xray-backups/pre-deployment-$(date +%Y%m%d-%H%M%S)

# 1.5 Save current state
cp -r /usr/local/etc/xray /root/xray-backups/pre-deployment-$(date +%Y%m%d-%H%M%S)/ 2>/dev/null || true
cp -r /etc/ssl/xray /root/xray-backups/pre-deployment-$(date +%Y%m%d-%H%M%S)/ 2>/dev/null || true

echo "✓ Phase 1 complete"
```

### Phase 2: Xray Installation (10 minutes)

```bash
#!/bin/bash
# Phase 2: Xray Core Installation

echo "=== Phase 2: Xray Core Installation ==="

# 2.1 Download Xray
XRAY_VERSION="25.1.30"
ARCH=$(uname -m)
case $ARCH in
    x86_64) ARCH="64" ;;
    aarch64|arm64) ARCH="arm64-v8a" ;;
    *) echo "Unsupported architecture: $ARCH"; exit 1 ;;
esac

wget -q --show-progress \
    "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-${ARCH}.zip" \
    -O /tmp/xray.zip

# 2.2 Install Xray
unzip -o /tmp/xray.zip -d /usr/local/xray/
chmod +x /usr/local/xray/xray
ln -sf /usr/local/xray/xray /usr/local/bin/xray

# 2.3 Verify installation
if xray -version; then
    echo "✓ Xray installed successfully"
else
    echo "✗ Xray installation failed"
    exit 1
fi
```

### Phase 3: Configuration Deployment (5 minutes)

```bash
#!/bin/bash
# Phase 3: Configuration Deployment

echo "=== Phase 3: Configuration Deployment ==="

# 3.1 Generate credentials
UUID_VLESS=$(cat /proc/sys/kernel/random/uuid)
UUID_TROJAN=$(cat /proc/sys/kernel/random/uuid)
PASSWORD_SS=$(openssl rand -base64 32)

# 3.2 Generate Reality keys
KEYS=$(xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep "Private" | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEYS" | grep "Public" | awk '{print $3}')
SHORT_ID=$(openssl rand -hex 8)

# 3.3 Create directories
mkdir -p /usr/local/etc/xray
mkdir -p /var/log/xray
mkdir -p /etc/ssl/xray
mkdir -p /root/xray-clients

# 3.4 Deploy configuration
cp configs/server-config.json /usr/local/etc/xray/config.json

# 3.5 Replace placeholders
sed -i "s/REPLACE_WITH_UUID_VLESS/$UUID_VLESS/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_UUID_TROJAN/$UUID_TROJAN/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_PRIVATE_KEY/$PRIVATE_KEY/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_PUBLIC_KEY/$PUBLIC_KEY/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_SHORT_ID/$SHORT_ID/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_SS_PASSWORD/$PASSWORD_SS/g" /usr/local/etc/xray/config.json

# 3.6 Generate certificates
openssl req -x509 -newkey rsa:4096 \
    -keyout /etc/ssl/xray/xray.key \
    -out /etc/ssl/xray/xray.crt \
    -days 365 \
    -nodes \
    -subj "/C=US/ST=State/L=City/O=x0tta6bl4/OU=VPS/CN=xray.local"

chmod 600 /etc/ssl/xray/xray.key
chmod 644 /etc/ssl/xray/xray.crt

# 3.7 Validate configuration
if xray -test -config /usr/local/etc/xray/config.json; then
    echo "✓ Configuration valid"
else
    echo "✗ Configuration invalid"
    exit 1
fi
```

### Phase 4: Service Activation (3 minutes)

```bash
#!/bin/bash
# Phase 4: Service Activation

echo "=== Phase 4: Service Activation ==="

# 4.1 Create systemd service
cat > /etc/systemd/system/xray.service << 'EOF'
[Unit]
Description=Xray Service
Documentation=https://github.com/xtls
After=network.target nss-lookup.target

[Service]
Type=simple
User=root
NoNewPrivileges=true
ExecStart=/usr/local/bin/xray run -config /usr/local/etc/xray/config.json
Restart=on-failure
RestartPreventExitStatus=23
LimitNOFILE=65535

[Install]
WantedBy=multi-user.target
EOF

# 4.2 Reload systemd
systemctl daemon-reload

# 4.3 Enable and start service
systemctl enable xray
systemctl start xray

# 4.4 Wait for service to be ready
sleep 3

# 4.5 Verify service status
if systemctl is-active --quiet xray; then
    echo "✓ Xray service active"
else
    echo "✗ Xray service failed to start"
    systemctl status xray --no-pager
    exit 1
fi
```

### Phase 5: Firewall Configuration (2 minutes)

```bash
#!/bin/bash
# Phase 5: Firewall Configuration

echo "=== Phase 5: Firewall Configuration ==="

# 5.1 Configure UFW (if available)
if command -v ufw &> /dev/null; then
    ufw allow 443/tcp
    ufw allow 8443/tcp
    ufw allow 8388/tcp
    ufw allow 8388/udp
    ufw allow 9443/tcp
    ufw allow 8080/tcp
    echo "✓ UFW configured"
fi

# 5.2 Configure FirewallD (if available)
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --permanent --add-port=443/tcp
    firewall-cmd --permanent --add-port=8443/tcp
    firewall-cmd --permanent --add-port=8388/tcp
    firewall-cmd --permanent --add-port=8388/udp
    firewall-cmd --permanent --add-port=9443/tcp
    firewall-cmd --permanent --add-port=8080/tcp
    firewall-cmd --reload
    echo "✓ FirewallD configured"
fi

# 5.3 Configure iptables
iptables -A INPUT -p tcp --dport 443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8388 -j ACCEPT
iptables -A INPUT -p udp --dport 8388 -j ACCEPT
iptables -A INPUT -p tcp --dport 9443 -j ACCEPT
iptables -A INPUT -p tcp --dport 8080 -j ACCEPT
```

### Phase 6: System Optimization (2 minutes)

```bash
#!/bin/bash
# Phase 6: System Optimization

echo "=== Phase 6: System Optimization ==="

# 6.1 Kernel parameters for BBR
cat >> /etc/sysctl.conf << 'EOF'
# Xray optimizations
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 87380 134217728
net.ipv4.tcp_wmem = 4096 65536 134217728
net.core.netdev_max_backlog = 250000
net.ipv4.tcp_congestion_control = bbr
net.ipv4.tcp_notsent_lowat = 16384
net.ipv4.tcp_fastopen = 3
EOF

sysctl -p

# 6.2 Load BBR module
modprobe tcp_bbr

# 6.3 File descriptor limits
cat >> /etc/security/limits.conf << 'EOF'
* soft nofile 65535
* hard nofile 65535
root soft nofile 65535
root hard nofile 65535
EOF

echo "✓ System optimized"
```

---

## Health Check Procedures

### Automated Health Checks

```bash
#!/bin/bash
# health-check.sh - Comprehensive health check

set -euo pipefail

HEALTH_STATUS="HEALTHY"

# Check 1: Service Status
check_service() {
    if ! systemctl is-active --quiet xray; then
        echo "FAIL: Xray service not running"
        HEALTH_STATUS="UNHEALTHY"
        return 1
    fi
    echo "PASS: Xray service running"
}

# Check 2: Configuration Validity
check_config() {
    if ! xray -test -config /usr/local/etc/xray/config.json &>/dev/null; then
        echo "FAIL: Configuration invalid"
        HEALTH_STATUS="UNHEALTHY"
        return 1
    fi
    echo "PASS: Configuration valid"
}

# Check 3: Port Listening
check_ports() {
    local ports=(443 8443 8388 9443 8080)
    local any_listening=false
    
    for port in "${ports[@]}"; do
        if ss -tlnp | grep -q ":$port "; then
            echo "PASS: Port $port listening"
            any_listening=true
        fi
    done
    
    if [[ "$any_listening" == "false" ]]; then
        echo "FAIL: No ports listening"
        HEALTH_STATUS="UNHEALTHY"
        return 1
    fi
}

# Check 4: Memory Usage
check_memory() {
    local mem_usage=$(free | awk '/^Mem:/{printf "%.0f", $3/$2 * 100}')
    if [[ $mem_usage -gt 90 ]]; then
        echo "WARN: High memory usage: ${mem_usage}%"
    else
        echo "PASS: Memory usage: ${mem_usage}%"
    fi
}

# Check 5: Disk Space
check_disk() {
    local disk_usage=$(df / | awk 'NR==2 {print $5}' | sed 's/%//')
    if [[ $disk_usage -gt 90 ]]; then
        echo "WARN: High disk usage: ${disk_usage}%"
    else
        echo "PASS: Disk usage: ${disk_usage}%"
    fi
}

# Check 6: Recent Errors
check_errors() {
    local recent_errors=$(tail -100 /var/log/xray/error.log 2>/dev/null | grep -c "error\|Error" || echo "0")
    if [[ $recent_errors -gt 10 ]]; then
        echo "WARN: $recent_errors recent errors in log"
    else
        echo "PASS: Error rate acceptable"
    fi
}

# Run all checks
echo "=== Health Check ==="
check_service
check_config
check_ports
check_memory
check_disk
check_errors

echo ""
echo "Overall Status: $HEALTH_STATUS"

if [[ "$HEALTH_STATUS" == "HEALTHY" ]]; then
    exit 0
else
    exit 1
fi
```

### Continuous Health Monitoring

```bash
#!/bin/bash
# monitor.sh - Continuous monitoring with alerts

INTERVAL=60  # Check every 60 seconds
ALERT_EMAIL="admin@example.com"
LOG_FILE="/var/log/xray/health-monitor.log"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

while true; do
    if ! systemctl is-active --quiet xray; then
        log "ALERT: Xray service down! Attempting restart..."
        systemctl restart xray
        sleep 5
        
        if systemctl is-active --quiet xray; then
            log "INFO: Xray service restarted successfully"
        else
            log "CRITICAL: Xray service failed to restart"
            # Send alert (configure as needed)
            # echo "Xray service down on $(hostname)" | mail -s "Xray Alert" "$ALERT_EMAIL"
        fi
    fi
    
    # Check for high error rate
    ERROR_COUNT=$(tail -1000 /var/log/xray/error.log 2>/dev/null | grep -c "error" || echo "0")
    if [[ $ERROR_COUNT -gt 100 ]]; then
        log "WARN: High error rate detected: $ERROR_COUNT errors in last 1000 lines"
    fi
    
    sleep $INTERVAL
done
```

---

## Rollback Procedures

### Automatic Rollback Triggers

Rollback is automatically triggered when:
1. Configuration validation fails
2. Service fails to start after deployment
3. Health checks fail for 5 consecutive minutes
4. Critical error rate detected

### Manual Rollback

```bash
#!/bin/bash
# rollback.sh - Rollback to previous version

set -euo pipefail

ROLLBACK_VERSION=""
BACKUP_DIR="/root/xray-backups"

# Find latest backup if version not specified
if [[ -z "$ROLLBACK_VERSION" ]]; then
    ROLLBACK_VERSION=$(ls -1 "$BACKUP_DIR" | grep "pre-deployment" | sort | tail -1)
fi

if [[ -z "$ROLLBACK_VERSION" ]]; then
    echo "No backup found for rollback"
    exit 1
fi

BACKUP_PATH="$BACKUP_DIR/$ROLLBACK_VERSION"

echo "=== Rolling back to: $ROLLBACK_VERSION ==="

# Step 1: Stop service
echo "Stopping Xray service..."
systemctl stop xray

# Step 2: Restore configuration
if [[ -d "$BACKUP_PATH/xray" ]]; then
    echo "Restoring configuration..."
    rm -rf /usr/local/etc/xray
    cp -r "$BACKUP_PATH/xray" /usr/local/etc/
fi

# Step 3: Restore certificates
if [[ -d "$BACKUP_PATH/ssl" ]]; then
    echo "Restoring certificates..."
    rm -rf /etc/ssl/xray
    cp -r "$BACKUP_PATH/ssl" /etc/ssl/xray
fi

# Step 4: Restore service file
if [[ -f "$BACKUP_PATH/xray.service" ]]; then
    echo "Restoring service file..."
    cp "$BACKUP_PATH/xray.service" /etc/systemd/system/
    systemctl daemon-reload
fi

# Step 5: Start service
echo "Starting Xray service..."
systemctl start xray
sleep 3

# Step 6: Verify rollback
if systemctl is-active --quiet xray; then
    echo "✓ Rollback successful - Service running"
else
    echo "✗ Rollback failed - Service not running"
    exit 1
fi
```

### Emergency Rollback

For emergency situations where the server is inaccessible:

```bash
#!/bin/bash
# emergency-rollback.sh - Emergency rollback procedure

# This script should be run from a rescue environment or console

# 1. Mount root filesystem (if in rescue mode)
# mount /dev/sda1 /mnt

# 2. Restore from backup
# cp -r /mnt/root/xray-backups/[TIMESTAMP]/xray /mnt/usr/local/etc/

# 3. Chroot and restart
# chroot /mnt
# systemctl restart xray
```

---

## Emergency Procedures

### Complete Service Failure

```bash
#!/bin/bash
# emergency-restore.sh - Complete service restoration

echo "=== Emergency Service Restoration ==="

# 1. Collect diagnostic info
mkdir -p /tmp/xray-emergency-$(date +%Y%m%d-%H%M%S)
cp /var/log/xray/*.log /tmp/xray-emergency-$(date +%Y%m%d-%H%M%S)/
systemctl status xray > /tmp/xray-emergency-$(date +%Y%m%d-%H%M%S)/status.txt

# 2. Stop service
systemctl stop xray

# 3. Reset to default configuration
cp configs/server-config.json /usr/local/etc/xray/config.json

# 4. Regenerate keys
KEYS=$(xray x25519)
PRIVATE_KEY=$(echo "$KEYS" | grep "Private" | awk '{print $3}')
PUBLIC_KEY=$(echo "$KEYS" | grep "Public" | awk '{print $3}')
UUID=$(cat /proc/sys/kernel/random/uuid)
SHORT_ID=$(openssl rand -hex 8)

sed -i "s/REPLACE_WITH_UUID_VLESS/$UUID/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_PRIVATE_KEY/$PRIVATE_KEY/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_PUBLIC_KEY/$PUBLIC_KEY/g" /usr/local/etc/xray/config.json
sed -i "s/REPLACE_WITH_SHORT_ID/$SHORT_ID/g" /usr/local/etc/xray/config.json

# 5. Start service
systemctl start xray

# 6. Verify
if systemctl is-active --quiet xray; then
    echo "✓ Emergency restoration complete"
    echo "New UUID: $UUID"
    echo "New Public Key: $PUBLIC_KEY"
    echo "New Short ID: $SHORT_ID"
else
    echo "✗ Emergency restoration failed"
    exit 1
fi
```

### Certificate Expiration

```bash
#!/bin/bash
# renew-certs.sh - Certificate renewal

echo "=== Certificate Renewal ==="

# Backup old certificates
cp /etc/ssl/xray/xray.crt /etc/ssl/xray/xray.crt.bak.$(date +%Y%m%d)
cp /etc/ssl/xray/xray.key /etc/ssl/xray/xray.key.bak.$(date +%Y%m%d)

# Generate new certificates
openssl req -x509 -newkey rsa:4096 \
    -keyout /etc/ssl/xray/xray.key \
    -out /etc/ssl/xray/xray.crt \
    -days 365 \
    -nodes \
    -subj "/C=US/ST=State/L=City/O=x0tta6bl4/OU=VPS/CN=xray.local"

chmod 600 /etc/ssl/xray/xray.key
chmod 644 /etc/ssl/xray/xray.crt

# Restart service
systemctl restart xray

echo "✓ Certificates renewed"
```

---

## Post-Deployment Verification

### Complete Verification Checklist

```bash
#!/bin/bash
# post-deploy-verify.sh - Post-deployment verification

echo "=== Post-Deployment Verification ==="

ERRORS=0

# 1. Service verification
if systemctl is-active --quiet xray; then
    echo "✓ Service is running"
else
    echo "✗ Service is not running"
    ((ERRORS++))
fi

# 2. Port verification
for port in 443 8443 8388 9443 8080; do
    if ss -tlnp | grep -q ":$port "; then
        echo "✓ Port $port is listening"
    else
        echo "✗ Port $port is not listening"
        ((ERRORS++))
    fi
done

# 3. Configuration verification
if xray -test -config /usr/local/etc/xray/config.json &>/dev/null; then
    echo "✓ Configuration is valid"
else
    echo "✗ Configuration is invalid"
    ((ERRORS++))
fi

# 4. Client configs verification
if [[ -d /root/xray-clients ]]; then
    echo "✓ Client configurations generated"
    ls -la /root/xray-clients/
else
    echo "✗ Client configurations not found"
    ((ERRORS++))
fi

# 5. Log verification
if [[ -f /var/log/xray/access.log && -f /var/log/xray/error.log ]]; then
    echo "✓ Log files created"
else
    echo "✗ Log files not found"
    ((ERRORS++))
fi

# 6. Certificate verification
if [[ -f /etc/ssl/xray/xray.crt && -f /etc/ssl/xray/xray.key ]]; then
    echo "✓ TLS certificates exist"
    openssl x509 -in /etc/ssl/xray/xray.crt -noout -dates
else
    echo "✗ TLS certificates not found"
    ((ERRORS++))
fi

# 7. Firewall verification
if ufw status | grep -q "443"; then
    echo "✓ Firewall configured (UFW)"
elif firewall-cmd --list-ports | grep -q "443"; then
    echo "✓ Firewall configured (FirewallD)"
else
    echo "⚠ Firewall rules may need verification"
fi

# Summary
echo ""
echo "=== Verification Summary ==="
if [[ $ERRORS -eq 0 ]]; then
    echo "✓ All checks passed - Deployment successful"
    exit 0
else
    echo "✗ $ERRORS check(s) failed - Review required"
    exit 1
fi
```

### Client Connection Testing

```bash
#!/bin/bash
# test-client-connection.sh - Test client connections

SERVER_IP=$(curl -s -4 ifconfig.me)

echo "=== Client Connection Testing ==="
echo "Server IP: $SERVER_IP"

# Test VLESS Reality (requires client config)
echo ""
echo "To test connections, use the following:"
echo ""
echo "1. VLESS Reality:"
echo "   Import /root/xray-clients/vless-reality.json to your client"
echo "   Server: $SERVER_IP:443"
echo ""
echo "2. Trojan:"
echo "   Import /root/xray-clients/trojan.json to your client"
echo "   Server: $SERVER_IP:9443"
echo ""
echo "3. Shadowsocks:"
echo "   Import /root/xray-clients/shadowsocks.txt to your client"
echo "   Server: $SERVER_IP:8388"
echo ""

# Generate connection URLs
echo "=== Connection URLs ==="
for file in /root/xray-clients/*.txt; do
    if [[ -f "$file" ]]; then
        echo "$(basename $file):"
        cat "$file"
        echo ""
    fi
done
```

---

## Deployment Timeline

| Phase | Duration | Description |
|-------|----------|-------------|
| Pre-deployment | 5 min | Check requirements, backup current state |
| Phase 1 | 5 min | Environment preparation |
| Phase 2 | 10 min | Xray installation |
| Phase 3 | 5 min | Configuration deployment |
| Phase 4 | 3 min | Service activation |
| Phase 5 | 2 min | Firewall configuration |
| Phase 6 | 2 min | System optimization |
| Verification | 5 min | Post-deployment verification |
| **Total** | **~37 min** | **Complete deployment** |

---

## Rollback Timeline

| Scenario | Duration | Description |
|----------|----------|-------------|
| Automatic | 2 min | Triggered by health check failure |
| Manual | 5 min | User-initiated rollback |
| Emergency | 10 min | Complete service restoration |
