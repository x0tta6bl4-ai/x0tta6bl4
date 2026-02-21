# x0tta6bl4: WARP + Xray Integration для Обхода Блокировок Google

## 🎯 Архитектура (Kernel-Level Routing)

```
┌─────────────────────────────────────────────────────────┐
│  Клиент (Крым) → VLESS+Reality (443)                     │
└────────────────────────┬────────────────────────────────┘
                         │
              ┌──────────▼──────────┐
              │  Xray (Прямой)      │ (port 10809)
              │  - VLESS Inbound    │
              │  - Reality Security │
              └────────┬─────┬──────┘
                       │     │
         ┌─────────────┘     └──────────────┐
         │                                  │
    ┌────▼──────────────┐      ┌───────────▼─────┐
    │ Tracing Route     │      │ WARP Routing    │
    │                  │      │                 │
    │ Direct:          │      │ Outbound WARP:  │
    │ - ISP sites      │      │ - Google/*      │
    │ - Local (CN ISP) │      │ - Meta/*        │
    │ - Private IPs    │      │ - ByteDance/*   │
    │ - Fastly CDN     │      │ (Cloudflare)    │
    │                  │      │                 │
    │ iptables GID     │      │ Linux WARP CLI  │
    │ bypass for Xray  │      │ UDP 40000       │
    └─────────┬────────┘      └────────┬────────┘
              │                        │
    ┌─────────▼────────────────────────▼──────┐
    │  Output to Internet (89.125.1.107)       │
    │  - Direct: Fast local routes             │
    │  - WARP: Cloudflare exit (masked IP)     │
    └──────────────────────────────────────────┘
```

## 📋 Проблемы Current Setup

1. **Google обнаруживает 89.125.1.107** как датацентр
2. **WARP подключен но не маршрутизирует Google трафик**
3. **Xray не знает про WARP_SOCK5 прокси на 40000**
4. **DNS не маскируется** (утечка через WARP)

## ✅ Решение: 3 Слоя

### Слой 1: eBPF-уровень маршрутизация (Kernel)

```bash
# GID-based bypass для предотвращения loop'ов в Xray
sudo groupadd -f xray_warp || true
sudo usermod -a -G xray_warp nobody || true

# iptables: only Google/Meta/ByteDance → WARP
# Others → Direct (if whitelisted) or Xray default
```

### Слой 2: WARP as SOCKS5 Proxy (user:nobody)

```bash
# WARP слушает на 127.0.0.1:40000 (UDP)
# Xray отправляет трафик через него для Google domains
```

### Слой 3: Xray Routing (Application-Level)

```json
{
  "routing": {
    "rules": [
      {
        "type": "field",
        "outboundTag": "warp-google",
        "domain": [
          "goog",
          "googleapis",
          "google-analytics",
          "youtube.com",
          "accounts.google"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "domain": ["cn-isp-only-sites"]
      }
    ]
  }
}
```

---

## 🔧 Implementation

### Step 1: WARP CLI Configuration

```bash
#!/bin/bash
set -e

# SSH на сервер
SSH_KEY="<set-your-password>"
SERVER="root@89.125.1.107"

# Проверить WARP статус
sshpass -p "$SSH_KEY" ssh -o StrictHostKeyChecking=no $SERVER << 'EOF'
echo "=== WARP Diagnostics ==="

# 1. WARP режим: Local Proxy (не Full Tunnel!)
warp-cli --accept-tos mode proxy

# 2. Configuring WARP Proxy Port
warp-cli --accept-tos proxy port 40000

# 3. Listenning interface
warp-cli --accept-tos proxy listen 127.0.0.1

# 4. Protocol: SOCKS5
warp-cli --accept-tos proxy protocol socks5

# 5. Start
warp-cli --accept-tos connect

sleep 2

# 6. Check
ss -tlnp | grep -E "(40000|warp)"
nc -zv 127.0.0.1 40000 2>&1 || echo "Port not listening (UDP expected)"

# 7. Test DNS resolution
echo "nameserver 1.1.1.1" > /etc/resolv.conf.warp
nslookup google.com 1.1.1.1

EOF
```

### Step 2: Xray Routing Configuration (Enhanced)

```json
{
  "log": {
    "loglevel": "warning"
  },
  "inbounds": [
    {
      "port": 10809,
      "protocol": "vless",
      "settings": {
        "clients": [
          {
            "id": "your-uuid",
            "flow": "xtls-rprx-vision"
          }
        ],
        "decryption": "none"
      },
      "streamSettings": {
        "network": "tcp",
        "security": "reality",
        "realitySettings": {
          "show": false,
          "dest": "microsoft.com:443",
          "xver": 0,
          "serverNames": [
            "microsoft.com",
            "bing.com",
            "office.com",
            "outlook.com"
          ],
          "privateKey": "YOUR_PRIVATE_KEY",
          "minClientVer": "",
          "maxClientVer": "",
          "maxTimeDiff": 0,
          "shortIds": ["0011aabbccdd"]
        }
      }
    }
  ],
  "outbounds": [
    {
      "protocol": "freedom",
      "tag": "direct",
      "settings": {}
    },
    {
      "protocol": "socks",
      "tag": "warp-google",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 40000
          }
        ]
      }
    },
    {
      "protocol": "socks",
      "tag": "warp-meta",
      "settings": {
        "servers": [
          {
            "address": "127.0.0.1",
            "port": 40000
          }
        ]
      }
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNameMatch",
    "rules": [
      {
        "type": "field",
        "outboundTag": "warp-google",
        "domain": [
          "goog",
          "googleapis.com",
          "google.com",
          "google.ru",
          "google.co.uk",
          "accounts.google.com",
          "youtube.com",
          "youtube-nocookie.com",
          "yt.be",
          "youtu.be",
          "googleusercontent.com",
          "googleapis.com",
          "gstatic.com",
          "google-analytics.com",
          "analytics.google.com",
          "recaptcha.net",
          "recaptcha.google.com"
        ]
      },
      {
        "type": "field",
        "outboundTag": "warp-meta",
        "domain": [
          "facebook.com",
          "instagram.com",
          "whatsapp.com",
          "meta.com",
          "fb.com",
          "fbcdn.net"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "domain": [
          "cn",
          "local",
          "internal"
        ]
      },
      {
        "type": "field",
        "outboundTag": "direct",
        "ip": [
          "10.0.0.0/8",
          "172.16.0.0/12",
          "192.168.0.0/16",
          "127.0.0.0/8"
        ]
      }
    ]
  }
}
```

### Step 3: iptables GID-Based Bypass (Prevent Loop)

```bash
#!/bin/bash

# 1. Create xray user with specific GID
sudo groupadd -f xray_warp 2>/dev/null || true
GID=$(getent group xray_warp | cut -d: -f3)

# 2. Create iptables rules to bypass Xray traffic
# This prevents infinite loops where Xray traffic gets caught by Xray rules

sudo iptables -t mangle -N XRAY_WARP 2>/dev/null || true

# Bypass Xray's own traffic (GID check)
sudo iptables -t mangle -A XRAY_WARP -m owner --gid-owner $GID -j RETURN

# Mark packets destined for WARP proxy
sudo iptables -t mangle -A XRAY_WARP -p tcp --dport 40000 -j MARK --set-mark 0x1
sudo iptables -t mangle -A XRAY_WARP -p udp --dport 40000 -j MARK --set-mark 0x1

# Route marked packets directly (bypass Xray)
sudo ip rule add fwmark 0x1 table 100
sudo ip route add local 0.0.0.0/0 dev lo table 100

# Alternative: Use REDIRECT for local WARP proxy
sudo iptables -t nat -A OUTPUT -m owner ! --gid-owner $GID -p tcp --dport 10809 -j REDIRECT --to-port 10809

# Save rules
sudo iptables-save | sudo tee /etc/iptables/rules.v4
```

### Step 4: DNS Leak Prevention

```bash
#!/bin/bash

# 1. Override resolv.conf
cat > /etc/resolv.conf << 'EOF'
# WARP DNS (Cloudflare)
nameserver 1.1.1.1
nameserver 1.0.0.1
nameserver 2606:4700:4700::1111
nameserver 2606:4700:4700::1001

# Fallback
nameserver 8.8.8.8
nameserver 8.8.4.4
EOF

# Make immutable
sudo chattr +i /etc/resolv.conf

# 2. Ensure WARP uses these nameservers
warp-cli --accept-tos dns overrides --add 1.1.1.1
warp-cli --accept-tos dns overrides --add 8.8.8.8

# 3. Test DNS leaks
echo "Testing DNS resolution through WARP..."
dig @1.1.1.1 +short google.com
dig @8.8.8.8 +short google.com
```

### Step 5: Monitoring & Logs

```bash
#!/bin/bash

# Monitor WARP proxy traffic
sudo tcpdump -i lo -n 'tcp port 40000 or udp port 40000' -A | head -100

# Check Xray logs
docker logs x0t-node --tail 50 | grep -E "(route|WARP|google|error)"

# Verify iptables rules
sudo iptables-save | grep -A 5 XRAY_WARP
sudo iptables -t mangle -L -n -v

# Connection tracking
ss -tnp | grep -E "(40000|10809|ESTABLISHED)"

# Test connectivity through WARP
curl -v --socks5 127.0.0.1:40000 https://google.com 2>&1 | head -20
```

---

## 🚀 Deployment Script

```bash
#!/bin/bash
set -e

SSH_KEY="<set-your-password>"
SERVER="root@89.125.1.107"

echo "🔧 Deploying WARP + Xray Integration..."

# Copy configs to server
sshpass -p "$SSH_KEY" scp -o StrictHostKeyChecking=no \
  xray-config.json \
  $SERVER:/usr/local/etc/xray/config.json

# Execute setup
sshpass -p "$SSH_KEY" ssh -o StrictHostKeyChecking=no $SERVER << 'SETUP_SCRIPT'
#!/bin/bash
set -e

echo "1️⃣ Configuring WARP in Proxy Mode..."
warp-cli --accept-tos mode proxy
warp-cli --accept-tos proxy port 40000
warp-cli --accept-tos proxy listen 127.0.0.1
sleep 2

echo "2️⃣ Starting WARP..."
warp-cli --accept-tos connect
sleep 3

echo "3️⃣ Setting up iptables GID bypass..."
# Create group
groupadd -f xray_warp || true
GID=$(getent group xray_warp | cut -d: -f3)

# Clear old rules
iptables -t mangle -F XRAY_WARP 2>/dev/null || true
iptables -t mangle -X XRAY_WARP 2>/dev/null || true

# Create new rules
iptables -t mangle -N XRAY_WARP
iptables -t mangle -A XRAY_WARP -m owner --gid-owner $GID -j RETURN
iptables -t mangle -A XRAY_WARP -p tcp --dport 40000 -j MARK --set-mark 0x1
iptables -t mangle -A XRAY_WARP -p udp --dport 40000 -j MARK --set-mark 0x1

echo "4️⃣ Fixing DNS resolution..."
cat > /etc/resolv.conf << 'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF
chattr +i /etc/resolv.conf || true

echo "5️⃣ Reloading Xray with new config..."
docker restart x0t-node
sleep 3

echo "✅ Integration complete!"
ps aux | grep warp
netstat -tlnp | grep 40000
docker logs x0t-node --tail 10

SETUP_SCRIPT

echo "✅ Deployment successful!"
```

---

## 🧪 Testing

```bash
#!/bin/bash

echo "=== Testing WARP + Xray ==="

# Test 1: WARP proxy connectivity
echo "1. Testing WARP SOCKS5 proxy..."
curl -v --socks5 127.0.0.1:40000 https://ifconfig.me 2>&1 | grep -E "(Connected|IP)"

# Test 2: Google access
echo "2. Testing Google through client..."
# From your Crimea client
curl -v -x socks5://yourVLESSupper@ip:443 https://google.com 2>&1 | grep -E "(HTTP|Connected)"

# Test 3: IP leak check
echo "3. IP leak test (should show WARP IP, not 89.125.1.107)..."
curl -s --socks5 127.0.0.1:40000 https://api.ipify.org 2>&1

# Test 4: DNS leak test
echo "4. DNS leak test..."
dig @127.0.0.1 google.com +short

# Test 5: Xray route verification
echo "5. Checking active routes..."
ss -tnp | grep -E "(10809|40000)"
iptables -L -n -v | grep -E "(XRAY|google)"

# Test 6: Performance
echo "6. Latency to Google..."
ping -c 3 google.com
curl -w "Time: %{time_total}s\n" -o /dev/null -s https://google.com

```

---

## 📊 Expected Results

**Before:** 
- Google: Blocked (403 Forbidden) from 89.125.1.107
- Ping: ~150ms (route → block)

**After:**
- Google: ✅ Accessible (200 OK) via WARP
- Ping: ~50-80ms (Cloudflare exit)
- IP: Masked (not 89.125.1.107)
- DNS: Cloudflare (1.1.1.1)

---

## 🔒 Security Considerations

1. **WARP is UDP (port 2408)** - Make sure firewall allows it
2. **GID bypass** - Prevents routing loops but verify iptables rules
3. **DNS masking** - Ensure `/etc/resolv.conf` is immutable
4. **Split tunneling** - Only Google/Meta through WARP, rest direct
5. **Monitoring** - Check logs for connection errors

---

## 📝 Troubleshooting

| Issue | Solution |
|-------|----------|
| WARP proxy not listening | `warp-cli --accept-tos mode proxy` then restart |
| Google still blocked | Check routing rules in Xray config |
| DNS leaks | Fix `/etc/resolv.conf` and run `chattr +i` |
| Xray crashes after changes | Check JSON syntax: `jq . xray-config.json` |
| iptables loop | Ensure GID bypass rule comes first |
