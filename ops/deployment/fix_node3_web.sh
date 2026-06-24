#!/bin/bash
# Install Nginx on Node 3 to fix web serving

IP="62.133.60.252"
PASS="${NODE23_PASS:?Set NODE23_PASS in environment}"

echo "🛠️ Installing Nginx on Node 3..."

# 1. Install Nginx
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "apt-get update >/dev/null 2>&1 && apt-get install -y nginx >/dev/null 2>&1"

# 2. Create Config
CONFIG="server {
    listen 8080;
    server_name _;
    root /opt/x0tta6bl4;
    index landing.html;
    
    location / {
        try_files \$uri \$uri/ =404;
        add_header Access-Control-Allow-Origin *;
    }
}"

echo "$CONFIG" > nginx_node3.conf
sshpass -p "$PASS" scp -o StrictHostKeyChecking=no nginx_node3.conf root@$IP:/etc/nginx/sites-available/x0tta6bl4

# 3. Enable Site
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "ln -sf /etc/nginx/sites-available/x0tta6bl4 /etc/nginx/sites-enabled/ && rm -f /etc/nginx/sites-enabled/default"

# 4. Kill old python servers
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "pkill -f http.server || true"

# 5. Force Open Port (IPTables + UFW)
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "iptables -I INPUT -p tcp --dport 8080 -j ACCEPT"
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "ufw allow 8080/tcp"

# 6. Restart Nginx
sshpass -p "$PASS" ssh -o StrictHostKeyChecking=no root@$IP "systemctl restart nginx && systemctl status nginx --no-pager"

echo "✅ Nginx Deployed on Node 3."
