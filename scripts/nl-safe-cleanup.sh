#!/bin/bash
# nl-safe-cleanup.sh — Безопасная чистка NL сервера
# НЕ ТРОГАЕТ: x-ui, xray, warp, fail2ban, nginx, SSH

set -e

echo "=== NL Server Safe Cleanup ==="
echo "Before: $(df -h / | tail -1 | awk '{print $4}') free"

# 1. Old rootfs backup (6.4GB)
echo "[1] Removing old rootfs backup..."
rm -f /root/full-rootfs-*.tar.zst 2>/dev/null && echo "  Removed rootfs backup" || echo "  Not found"

# 2. Old migration prep (1.9GB)
echo "[2] Removing old migration prep..."
rm -rf /root/migration-prep-* 2>/dev/null && echo "  Removed migration prep" || echo "  Not found"

# 3. Old incident reports
echo "[3] Removing old incident reports..."
rm -rf /root/vpn-instability-* 2>/dev/null && echo "  Removed incident reports" || echo "  Not found"

# 4. Old x0tta backups
echo "[4] Removing old x0tta backups..."
rm -rf /root/x0tta-firstparty-vpn-legacy-path-backups-* 2>/dev/null && echo "  Removed old backups" || echo "  Not found"
rm -rf /root/x0tta-vpn-fix-* 2>/dev/null && echo "  Removed vpn fixes" || echo "  Not found"

# 5. Old routing fix
echo "[5] Removing old routing fix..."
rm -rf /root/gemini-routing-fix-* 2>/dev/null && echo "  Removed routing fix" || echo "  Not found"

# 6. Old ghost-access artifacts
echo "[6] Removing old ghost-access artifacts..."
rm -rf /root/ghost-access-* 2>/dev/null && echo "  Removed ghost-access artifacts" || echo "  Not found"

# 7. Clean old logs (keep last 7 days)
echo "[7] Cleaning old logs..."
find /var/log -name "*.gz" -mtime +7 -delete 2>/dev/null
find /var/log -name "*.1" -mtime +7 -delete 2>/dev/null
find /var/log -name "*.old" -mtime +7 -delete 2>/dev/null
echo "  Cleaned old log files"

# 8. Vacuum journal (keep 100MB)
echo "[8] Vacuuming journal..."
journalctl --vacuum-size=100M 2>/dev/null || true
echo "  Journal vacuumed"

# 9. Docker cleanup
echo "[9] Cleaning Docker..."
docker system prune -f 2>/dev/null || true
docker volume prune -f 2>/dev/null || true
echo "  Docker cleaned"

# 10. Clean apt cache
echo "[10] Cleaning apt cache..."
apt-get clean 2>/dev/null || true
apt-get autoremove -y 2>/dev/null || true
echo "  Apt cleaned"

# Summary
echo ""
echo "=== Cleanup Complete ==="
echo "After: $(df -h / | tail -1 | awk '{print $4}') free"
echo ""
echo "Services still running:"
systemctl is-active x-ui xray warp-svc fail2ban nginx 2>/dev/null
