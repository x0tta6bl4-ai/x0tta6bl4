#!/bin/bash
#
# ===================================================================
# VPN SERVER FIX SCRIPT — x0tta6bl4
# ===================================================================
# Запуск: ssh root@89.125.1.107 'bash -s' < ./fix_vpn_server.sh
# Или:    scp fix_vpn_server.sh root@89.125.1.107:/tmp/ && ssh root@89.125.1.107 'bash /tmp/fix_vpn_server.sh'
# ===================================================================

set -e

echo "========================================="
echo " VPN Server Fix Script v2.0"
echo " $(date)"
echo "========================================="

# ─────────────────────────────────────────────
# STEP 1: BACKUP
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 1: Creating backups..."
BACKUP_DIR="/root/vpn-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp /usr/local/x-ui/bin/config.json "$BACKUP_DIR/config.json.bak" 2>/dev/null || true
cp /usr/local/x-ui/x-ui.db "$BACKUP_DIR/x-ui.db.bak" 2>/dev/null || true
crontab -l > "$BACKUP_DIR/crontab.bak" 2>/dev/null || true
echo "Backups saved to: $BACKUP_DIR"

# ─────────────────────────────────────────────
# STEP 2: UNBAN ALL IPs (Fail2Ban)
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 2: Unbanning all IPs from Fail2Ban..."
if command -v fail2ban-client &>/dev/null; then
    fail2ban-client unban --all 2>/dev/null || true
    echo "All IPs unbanned"
    
    # Increase ban tolerance for SSH
    if [ -f /etc/fail2ban/jail.local ]; then
        echo "Updating Fail2Ban SSH settings..."
    fi
else
    echo "Fail2Ban not installed, checking iptables..."
    # Flush any banned IPs from iptables
    iptables -F f2b-sshd 2>/dev/null || true
fi
echo "Done"

# ─────────────────────────────────────────────
# STEP 3: REMOVE ALL PROBLEMATIC SCRIPTS
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 3: Removing problematic watchers and cron jobs..."

# Stop and remove systemd watchers
systemctl stop xray-warp-watcher 2>/dev/null || true
systemctl disable xray-warp-watcher 2>/dev/null || true
rm -f /etc/systemd/system/xray-warp-watcher.service
systemctl daemon-reload

# Clean crontab from xray/warp related entries
if crontab -l 2>/dev/null | grep -qE 'apply.*xray|apply.*warp|process_monitor|patch.*xray|xray.*warp|warp.*xray'; then
    crontab -l 2>/dev/null | grep -vE 'apply.*xray|apply.*warp|process_monitor|patch.*xray|xray.*warp|warp.*xray' | crontab -
    echo "Cron entries cleaned"
else
    echo "No problematic cron entries found"
fi

# Remove ExecStartPost from x-ui.service if it kills xray
if grep -q "ExecStartPost" /etc/systemd/system/x-ui.service 2>/dev/null; then
    sed -i '/ExecStartPost/d' /etc/systemd/system/x-ui.service
    systemctl daemon-reload
    echo "ExecStartPost removed from x-ui.service"
fi

echo "Done"

# ─────────────────────────────────────────────
# STEP 4: VERIFY WARP IS WORKING
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 4: Checking WARP proxy..."
WARP_IP=$(curl -s --connect-timeout 5 --socks5 127.0.0.1:40000 https://ifconfig.me 2>/dev/null || echo "FAILED")
if [ "$WARP_IP" = "FAILED" ] || [ -z "$WARP_IP" ]; then
    echo "WARNING: WARP socks proxy not working on 127.0.0.1:40000"
    echo "Checking if warp-svc is running..."
    if pgrep -f "warp-svc" > /dev/null; then
        echo "warp-svc is running, restarting..."
        systemctl restart warp-svc 2>/dev/null || true
        sleep 3
        WARP_IP=$(curl -s --connect-timeout 5 --socks5 127.0.0.1:40000 https://ifconfig.me 2>/dev/null || echo "STILL_FAILED")
    else
        echo "warp-svc not running, starting..."
        systemctl start warp-svc 2>/dev/null || true
        warp-cli connect 2>/dev/null || true
        sleep 3
        WARP_IP=$(curl -s --connect-timeout 5 --socks5 127.0.0.1:40000 https://ifconfig.me 2>/dev/null || echo "STILL_FAILED")
    fi
fi
echo "WARP IP: $WARP_IP"

# ─────────────────────────────────────────────
# STEP 5: INSERT XRAY TEMPLATE CONFIG INTO X-UI DB
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 5: Setting up xrayTemplateConfig in x-ui database..."
echo "Stopping x-ui to ensure DB access..."
systemctl stop x-ui 2>/dev/null || true


python3 << 'PYEOF_DB'
import sqlite3
import json
import sys
import os

DB_PATH = "/usr/local/x-ui/x-ui.db"

# Template configuration
template_config = {
  "log": {
    "access": "none",
    "dnsLog": False,
    "error": "",
    "loglevel": "warning"
  },
  "dns": {
    "servers": [
      "1.1.1.1",
      "8.8.8.8",
      "1.0.0.1"
    ],
    "queryStrategy": "UseIPv4"
  },
  "outbounds": [
    {
      "tag": "direct",
      "protocol": "freedom",
      "settings": {
        "domainStrategy": "AsIs"
      }
    },
    {
      "tag": "warp",
      "protocol": "socks",
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
      "tag": "blocked",
      "protocol": "blackhole",
      "settings": {}
    }
  ],
  "routing": {
    "domainStrategy": "IPIfNonMatch"
  }
}

try:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Check if setting exists
    try:
        cursor.execute("SELECT value FROM settings WHERE key='xrayTemplateConfig'")
        row = cursor.fetchone()
    except sqlite3.OperationalError:
        # Table might not exist or DB empty
        print("Table 'settings' not found/DB issue. Attempting initialization and restore...")
        
        # Initialize Schema (simplified for x-ui)
        cursor.execute('''CREATE TABLE IF NOT EXISTS settings (id INTEGER PRIMARY KEY AUTOINCREMENT, key TEXT, value TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, password TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS inbounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            up INTEGER DEFAULT 0,
            down INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0,
            remark TEXT,
            enable INTEGER DEFAULT 1,
            expiry_time INTEGER DEFAULT 0,
            listen TEXT,
            port INTEGER,
            protocol TEXT,
            settings TEXT,
            stream_settings TEXT,
            tag TEXT,
            sniffing TEXT
        )''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS client_traffics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            inbound_id INTEGER,
            enable INTEGER DEFAULT 1,
            email TEXT,
            up INTEGER DEFAULT 0,
            down INTEGER DEFAULT 0,
            expiry_time INTEGER DEFAULT 0,
            total INTEGER DEFAULT 0
        )''')
        
        # Restore Admin user (admin/admin)
        # We don't want to reset admin if it exists, but since we are re-initing...
        cursor.execute("INSERT OR IGNORE INTO users (id, username, password) VALUES (1, 'admin', 'admin')")
        
        # Restore Inbounds from config.json
        try:
            with open("/usr/local/x-ui/bin/config.json", 'r') as f:
                current_config = json.load(f)
                
            inbounds = current_config.get("inbounds", [])
            for ib in inbounds:
                if ib.get("protocol") == "vless" and ib.get("port") == 39829:
                    print(f"Restoring inbound on port {ib['port']}...")
                    cursor.execute('''INSERT INTO inbounds (
                        user_id, remark, enable, port, protocol, settings, stream_settings, tag, sniffing
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (
                        1, # admin user_id
                        f"Restored-{ib['port']}",
                        1,
                        ib['port'],
                        ib['protocol'],
                        json.dumps(ib['settings']),
                        json.dumps(ib.get('streamSettings', {})),
                        ib.get('tag', ''),
                        json.dumps(ib.get('sniffing', {}))
                    ))
                    print("Inbound restored!")
        except Exception as e:
            print(f"Failed to restore inbounds from config: {e}")
            
        row = None
    
    value = json.dumps(template_config, indent=2)
    
    if row:
        cursor.execute("UPDATE settings SET value=? WHERE key='xrayTemplateConfig'", (value,))
        print("Template updated in database")
    else:
        cursor.execute("INSERT INTO settings (key, value) VALUES ('xrayTemplateConfig', ?)", (value,))
        print("Template inserted into database")
        
    conn.commit()
    conn.close()
    
except Exception as e:
    print(f"Error updating database: {e}")
    sys.exit(1)
PYEOF_DB

# ─────────────────────────────────────────────
# STEP 6: APPLY FULL WARP ROUTING TO ACTIVE CONFIG
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 6: Applying WARP routing to active config..."

python3 << 'PYEOF'
import json
import sys
import os

CONFIG_PATH = "/usr/local/x-ui/bin/config.json"

try:
    with open(CONFIG_PATH, 'r') as f:
        config = json.load(f)
except Exception as e:
    print(f"ERROR: Cannot read config: {e}")
    sys.exit(1)

# === DNS ===
config["dns"] = {
    "servers": ["1.1.1.1", "8.8.8.8", "1.0.0.1"],
    "queryStrategy": "UseIPv4"
}

# === OUTBOUNDS ===
# Keep existing outbounds but ensure warp and blocked exist
outbound_tags = {o.get("tag"): o for o in config.get("outbounds", [])}

if "warp" not in outbound_tags:
    config.setdefault("outbounds", []).append({
        "tag": "warp",
        "protocol": "socks",
        "settings": {
            "servers": [{"address": "127.0.0.1", "port": 40000}]
        }
    })
    print("Added WARP outbound")

if "blocked" not in outbound_tags:
    config.setdefault("outbounds", []).append({
        "tag": "blocked",
        "protocol": "blackhole",
        "settings": {}
    })
    print("Added blocked outbound")

# === ROUTING ===
routing = config.setdefault("routing", {})
routing["domainStrategy"] = "IPIfNonMatch"

# Build new rules
new_rules = []

# Keep API rule if exists
for rule in routing.get("rules", []):
    if rule.get("outboundTag") == "api" or rule.get("inboundTag") == ["api"]:
        new_rules.append(rule)
        break

# Block private IPs
new_rules.append({
    "type": "field",
    "outboundTag": "blocked",
    "ip": ["geoip:private"]
})

# Block BitTorrent
new_rules.append({
    "type": "field",
    "outboundTag": "blocked",
    "protocol": ["bittorrent"]
})

# WARP domains - comprehensive list
new_rules.append({
    "type": "field",
    "outboundTag": "warp",
    "domain": [
        # Google & YouTube
        "geosite:google",
        "geosite:youtube",
        "domain:google.com",
        "domain:googleapis.com",
        "domain:googleusercontent.com",
        "domain:gstatic.com",
        "domain:googlevideo.com",
        "domain:google-analytics.com",
        "domain:recaptcha.net",
        "domain:g.co",
        "domain:goo.gl",
        "domain:youtube.com",
        "domain:youtu.be",
        "domain:ytimg.com",
        "domain:yt3.ggpht.com",
        "domain:firebaseapp.com",
        "domain:firebaseio.com",
        "domain:firebase.google.com",
        "domain:chrome.com",
        "domain:chromium.org",
        "domain:android.com",
        "domain:play.google.com",
        "domain:gemini.google.com",
        "domain:bard.google.com",
        "domain:deepmind.google",
        "domain:deepmind.com",
        # Spotify
        "geosite:spotify",
        "domain:spotify.com",
        "domain:scdn.co",
        "domain:spotifycdn.com",
        # Meta & Instagram
        "geosite:facebook",
        "geosite:instagram",
        "domain:instagram.com",
        "domain:cdninstagram.com",
        "domain:facebook.com",
        "domain:fbcdn.net",
        "domain:fb.com",
        "domain:meta.com",
        "domain:threads.net",
        "domain:messenger.com",
        "domain:whatsapp.com",
        "domain:whatsapp.net",
        "domain:wa.me",
        # Twitter/X
        "geosite:twitter",
        "domain:twitter.com",
        "domain:x.com",
        "domain:twimg.com",
        "domain:t.co",
        "domain:abs.twimg.com",
        # TikTok
        "geosite:tiktok",
        "domain:tiktok.com",
        "domain:tiktokcdn.com",
        "domain:tiktokv.com",
        "domain:musical.ly",
        "domain:bytedance.com",
        # LinkedIn, Pinterest, Reddit
        "domain:linkedin.com",
        "domain:licdn.com",
        "domain:pinterest.com",
        "domain:pinimg.com",
        "domain:reddit.com",
        "domain:redditmedia.com",
        "domain:redditstatic.com",
        "domain:redd.it",
        "domain:tumblr.com",
        # AI Services
        "geosite:openai",
        "domain:openai.com",
        "domain:chatgpt.com",
        "domain:chat.openai.com",
        "domain:oaiusercontent.com",
        "domain:oaistatic.com",
        "domain:anthropic.com",
        "domain:claude.ai",
        "domain:midjourney.com",
        "domain:huggingface.co",
        "domain:perplexity.ai",
        "domain:replicate.com",
        "domain:stability.ai",
        "domain:cohere.ai",
        "domain:cohere.com",
        "domain:cursor.sh",
        "domain:cursor.com",
        "domain:v0.dev",
        "domain:bolt.new",
        "domain:replit.com",
        # Telegram
        "geosite:telegram",
        "domain:telegram.org",
        "domain:t.me",
        "domain:telegram.me",
        "domain:web.telegram.org",
        "domain:core.telegram.org",
        "domain:desktop.telegram.org",
        "domain:updates.telegram.org",
        # Signal, Discord, Viber
        "domain:signal.org",
        "domain:signal.art",
        "domain:whispersystems.org",
        "geosite:discord",
        "domain:discord.com",
        "domain:discordapp.com",
        "domain:discord.gg",
        "domain:discord.media",
        "domain:discordapp.net",
        "domain:viber.com",
        "domain:zoom.us",
        "domain:zoom.com",
        "domain:zoomcdn.com",
        # Streaming
        "geosite:netflix",
        "domain:netflix.com",
        "domain:nflxvideo.net",
        "domain:nflximg.net",
        "domain:nflxso.net",
        "domain:twitch.tv",
        "domain:ttvnw.net",
        "domain:jtvnw.net",
        "domain:soundcloud.com",
        "domain:sndcdn.com",
        "domain:deezer.com",
        "domain:dailymotion.com",
        "domain:vimeo.com",
        "domain:vimeocdn.com",
        # News
        "domain:bbc.com",
        "domain:bbc.co.uk",
        "domain:bbci.co.uk",
        "domain:cnn.com",
        "domain:medium.com",
        "domain:reuters.com",
        "domain:nytimes.com",
        "domain:theguardian.com",
        "domain:washingtonpost.com",
        "domain:dw.com",
        "domain:meduza.io",
        "domain:currenttime.tv",
        "domain:rferl.org",
        "domain:svoboda.org",
        "domain:mediazona.ca",
        "domain:holod.media",
        "domain:novayagazeta.eu",
        # Dev Tools
        "geosite:github",
        "domain:github.com",
        "domain:githubusercontent.com",
        "domain:githubassets.com",
        "domain:copilot.github.com",
        "domain:githubcopilot.com",
        "domain:gitlab.com",
        "domain:bitbucket.org",
        "domain:stackoverflow.com",
        "domain:sstatic.net",
        "domain:stackexchange.com",
        "domain:notion.so",
        "domain:notion.site",
        "domain:figma.com",
        "domain:canva.com",
        "domain:slack.com",
        "domain:grammarly.com",
        "domain:dropbox.com",
        "domain:trello.com",
        "domain:atlassian.com",
        "domain:vercel.com",
        "domain:netlify.com",
        "domain:netlify.app",
        "domain:heroku.com",
        "domain:npmjs.com",
        "domain:npmjs.org",
        "domain:pypi.org",
        "domain:docker.com",
        "domain:docker.io",
        "domain:registry.npmjs.org",
        "domain:hub.docker.com",
        "domain:ghcr.io",
        "domain:pkg.dev",
        # CDN/Cloud
        "domain:amazonaws.com",
        "domain:cloudfront.net",
        "domain:cloudflare.com",
        "domain:cdnjs.cloudflare.com",
        "domain:akamaized.net",
        "domain:fastly.net"
    ]
})

# WARP IP ranges (Telegram DCs, Google DNS)
new_rules.append({
    "type": "field",
    "outboundTag": "warp",
    "ip": [
        "8.8.8.8",
        "8.8.4.4",
        "149.154.160.0/20",
        "91.108.4.0/22",
        "91.108.8.0/22",
        "91.108.12.0/22",
        "91.108.16.0/22",
        "91.108.20.0/22",
        "91.108.56.0/22",
        "95.161.64.0/20"
    ]
})

routing["rules"] = new_rules
config["routing"] = routing

# Write config
with open(CONFIG_PATH, 'w') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)

total_domains = len(new_rules[3]["domain"])
total_ips = len(new_rules[4]["ip"])
print(f"Config updated: {total_domains} domains + {total_ips} IP ranges via WARP")
print(f"Total routing rules: {len(new_rules)}")
PYEOF

echo "Done"

# ─────────────────────────────────────────────
# STEP 7: RESTART XRAY (NOT x-ui, to avoid config overwrite)
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 7: Restarting Xray (gentle)..."

# Find and kill xray, let x-ui restart it with our patched config
XRAY_PID=$(pgrep -f "xray-linux-amd64" 2>/dev/null || true)
if [ -n "$XRAY_PID" ]; then
    echo "Killing xray PID=$XRAY_PID..."
    kill "$XRAY_PID" 2>/dev/null || true
    sleep 2
fi

# Restart x-ui which will restart xray with the config
systemctl restart x-ui
sleep 3

# ─────────────────────────────────────────────
# STEP 8: RE-APPLY WARP ROUTING (x-ui may regenerate config)
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 8: Re-applying WARP routing after x-ui restart..."
sleep 5

# Run the same Python script again to ensure routing is in place
python3 << 'PYEOF2'
import json

CONFIG_PATH = "/usr/local/x-ui/bin/config.json"

with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

# Check if WARP routing is present
has_warp = False
for rule in config.get("routing", {}).get("rules", []):
    if rule.get("outboundTag") == "warp" and "domain" in rule:
        if len(rule["domain"]) > 50:
            has_warp = True
            break

if not has_warp:
    print("WARP routing was stripped by x-ui, will re-apply in next step...")
else:
    domains = 0
    for rule in config.get("routing", {}).get("rules", []):
        if rule.get("outboundTag") == "warp" and "domain" in rule:
            domains = len(rule["domain"])
    print(f"WARP routing is present ({domains} domains)")
PYEOF2

# Check and Apply WARP routing if needed
python3 << 'PYEOF3'
import json
import sys

CONFIG_PATH = "/usr/local/x-ui/bin/config.json"

with open(CONFIG_PATH, 'r') as f:
    config = json.load(f)

has_warp_domains = False
for rule in config.get("routing", {}).get("rules", []):
    if rule.get("outboundTag") == "warp" and "domain" in rule:
        if len(rule["domain"]) > 50:
            has_warp_domains = True
            break

if not has_warp_domains:
    print("WARNING: WARP routing still not present, applying directly...")
    
    # Ensure outbounds exist
    outbound_tags = [o.get("tag") for o in config.get("outbounds", [])]
    if "warp" not in outbound_tags:
        config.setdefault("outbounds", []).append({
            "tag": "warp", "protocol": "socks",
            "settings": {"servers": [{"address": "127.0.0.1", "port": 40000}]}
        })
    if "blocked" not in outbound_tags:
        config.setdefault("outbounds", []).append({
            "tag": "blocked", "protocol": "blackhole", "settings": {}
        })
    
    # Build routing
    routing = config.setdefault("routing", {})
    routing["domainStrategy"] = "IPIfNonMatch"
    
    existing_rules = routing.get("rules", [])
    api_rules = [r for r in existing_rules if r.get("outboundTag") == "api"]
    
    new_rules = api_rules + [
        {"type": "field", "outboundTag": "blocked", "ip": ["geoip:private"]},
        {"type": "field", "outboundTag": "blocked", "protocol": ["bittorrent"]},
        {"type": "field", "outboundTag": "warp", "domain": [
            "geosite:google", "geosite:youtube", "geosite:spotify", "geosite:netflix",
            "geosite:facebook", "geosite:twitter", "geosite:instagram", "geosite:whatsapp",
            "geosite:telegram", "geosite:discord", "geosite:tiktok", "geosite:openai",
            "geosite:github",
            "domain:google.com", "domain:googleapis.com", "domain:googleusercontent.com",
            "domain:gstatic.com", "domain:googlevideo.com", "domain:youtube.com",
            "domain:youtu.be", "domain:ytimg.com", "domain:spotify.com",
            "domain:instagram.com", "domain:cdninstagram.com", "domain:facebook.com",
            "domain:fbcdn.net", "domain:fb.com", "domain:meta.com", "domain:threads.net",
            "domain:whatsapp.com", "domain:whatsapp.net", "domain:wa.me",
            "domain:twitter.com", "domain:x.com", "domain:twimg.com", "domain:t.co",
            "domain:tiktok.com", "domain:tiktokcdn.com",
            "domain:linkedin.com", "domain:licdn.com",
            "domain:reddit.com", "domain:redditmedia.com",
            "domain:openai.com", "domain:chatgpt.com", "domain:oaiusercontent.com",
            "domain:anthropic.com", "domain:claude.ai",
            "domain:midjourney.com", "domain:huggingface.co", "domain:perplexity.ai",
            "domain:cursor.sh", "domain:cursor.com", "domain:replit.com",
            "domain:telegram.org", "domain:t.me", "domain:web.telegram.org",
            "domain:signal.org", "domain:discord.com", "domain:discordapp.com",
            "domain:viber.com", "domain:zoom.us",
            "domain:netflix.com", "domain:nflxvideo.net", "domain:twitch.tv",
            "domain:soundcloud.com", "domain:vimeo.com",
            "domain:bbc.com", "domain:bbc.co.uk", "domain:meduza.io", "domain:dw.com",
            "domain:novayagazeta.eu", "domain:medium.com",
            "domain:github.com", "domain:githubusercontent.com", "domain:githubassets.com",
            "domain:gitlab.com", "domain:stackoverflow.com",
            "domain:notion.so", "domain:figma.com", "domain:canva.com", "domain:slack.com",
            "domain:vercel.com", "domain:netlify.com", "domain:npmjs.com",
            "domain:pypi.org", "domain:docker.com", "domain:docker.io",
            "domain:amazonaws.com", "domain:cloudfront.net", "domain:cloudflare.com"
        ]},
        {"type": "field", "outboundTag": "warp", "ip": [
            "8.8.8.8", "8.8.4.4",
            "149.154.160.0/20", "91.108.4.0/22", "91.108.8.0/22",
            "91.108.12.0/22", "91.108.16.0/22", "91.108.20.0/22",
            "91.108.56.0/22", "95.161.64.0/20"
        ]}
    ]
    
    routing["rules"] = new_rules
    config["routing"] = routing
    config["dns"] = {"servers": ["1.1.1.1", "8.8.8.8", "1.0.0.1"], "queryStrategy": "UseIPv4"}
    
    with open(CONFIG_PATH, 'w') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    
    # Gentle restart of xray
    import subprocess
    subprocess.run(["pkill", "-USR1", "-f", "xray-linux"], capture_output=True)
    
    print(f"WARP routing applied ({len(new_rules[3]['domain'])} domains)")
else:
    print("WARP routing confirmed!")
PYEOF3

echo "Done"

# ─────────────────────────────────────────────
# STEP 9: FINAL VERIFICATION
# ─────────────────────────────────────────────
echo ""
echo ">>> STEP 9: Final verification..."
echo ""

# Check xray is running
XRAY_PID=$(pgrep -f "xray-linux-amd64" 2>/dev/null || echo "NOT_RUNNING")
echo "Xray PID: $XRAY_PID"

# Check port
ss -tlnp | grep 39829 && echo "Port 39829: OPEN" || echo "Port 39829: CLOSED"

# Check WARP
WARP_TEST=$(curl -s --connect-timeout 5 --socks5 127.0.0.1:40000 https://ifconfig.me 2>/dev/null || echo "FAILED")
echo "WARP test: $WARP_TEST"

# Check config
python3 -c "
import json
c = json.load(open('/usr/local/x-ui/bin/config.json'))
outbounds = [o.get('tag','?') for o in c.get('outbounds',[])]
warp_domains = 0
for r in c.get('routing',{}).get('rules',[]):
    if r.get('outboundTag') == 'warp' and 'domain' in r:
        warp_domains = len(r['domain'])
has_dns = 'servers' in c.get('dns',{})
print(f'Outbounds: {outbounds}')
print(f'WARP domains: {warp_domains}')
print(f'DNS configured: {has_dns}')
print(f'Domain strategy: {c.get(\"routing\",{}).get(\"domainStrategy\",\"NONE\")}')
"

# Check cron is clean
echo ""
echo "Cron check:"
crontab -l 2>/dev/null | grep -c "xray\|warp" && echo "WARNING: Still has xray/warp cron entries!" || echo "Cron: CLEAN"

# Check no watcher running
echo "Watcher check:"
systemctl is-active xray-warp-watcher 2>/dev/null || echo "Watcher: STOPPED (good)"

echo ""
echo "========================================="
echo " FIX COMPLETE"
echo " $(date)"
echo "========================================="
echo ""
echo "next steps:"
echo "1. Check VPN from your client device"
echo "2. Run: curl -s --socks5 127.0.0.1:10808 https://ipinfo.io/ip"
echo "   Should show: 89.125.1.107"
echo "========================================="
