#!/bin/bash
# x0tta6bl4 AI Editor Configuration Script
# Fixes proxy and authorization issues for Cursor, Windsurf, and Kilocode.

set -e

# Hardcode the verified active Xray port
SOCKS_PORT=10818

echo "🔧 Configuring AI Editors for x0tta6bl4..."

# 1. Configure System Environment for IDEs
cat <<EOF > .env.ide
HTTP_PROXY=socks5://127.0.0.1:$SOCKS_PORT
HTTPS_PROXY=socks5://127.0.0.1:$SOCKS_PORT
NO_PROXY=localhost,127.0.0.1,::1,x0tta6bl4.mesh
SPIFFE_ENDPOINT_SOCKET=/tmp/spire-agent/public/api.sock
BUN_CONFIG_VERBOSE=true
EOF

echo "✅ Generated .env.ide for manual import if needed."

# 2. Fix SPIFFE Socket Permissions
if [ -S /tmp/spire-agent/public/api.sock ]; then
    echo "🔐 Ensuring SPIFFE socket is accessible..."
    sudo chmod 666 /tmp/spire-agent/public/api.sock || echo "⚠️ Could not change socket permissions. Run with sudo if needed."
fi

# 3. Create General VS Code / Kilocode Fix
mkdir -p .vscode
cat <<EOF > .vscode/tasks.json
{
    "version": "2.0.0",
    "tasks": [
        {
            "label": "Fix AI Proxy & Bun",
            "type": "shell",
            "command": "export HTTP_PROXY=socks5://127.0.0.1:$SOCKS_PORT && export HTTPS_PROXY=socks5://127.0.0.1:$SOCKS_PORT && export BUN_CONFIG_VERBOSE=true",
            "problemMatcher": []
        }
    ]
}
EOF

echo "✅ Created .vscode/tasks.json with proxy & Bun debug helpers."

# 4. Instructions for Authorization
echo "🔑 AUTHENTICATION FIX:"
echo "For Cursor/Windsurf/Kilocode to work with x0tta6bl4 APIs:"
echo "1. Ensure SPIRE agent is running: './scripts/spire/run-agent.sh'"
echo "2. Check your SVID: 'spire-agent health' and 'spire-agent api fetch svid'"
echo "3. Kilocode specific: The error 'socket connection closed' usually means your local Xray/Reality client is not running on $SOCKS_PORT, or Bun drops the HTTP proxy tunnel. We switched to socks5://."

echo ""
echo "🚀 AI Editors are now configured to route through the x0tta6bl4 mesh."
echo "Note: If your local proxy port is different from $SOCKS_PORT, update .vscode/settings.json manually."
