#!/bin/bash
# Script to send Telegram alert via webhook
# Used by Alertmanager webhook receiver
# Дата: 2026-01-08

set -euo pipefail

TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
TELEGRAM_CHAT_ID="${TELEGRAM_CHAT_ID:-}"

if [ -z "$TELEGRAM_BOT_TOKEN" ] || [ -z "$TELEGRAM_CHAT_ID" ]; then
    echo "ERROR: TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set" >&2
    exit 1
fi

# Read alert JSON from stdin
ALERT_JSON=$(cat)

# Parse alert data
ALERT_NAME=$(echo "$ALERT_JSON" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('alerts', [{}])[0].get('labels', {}).get('alertname', 'Unknown'))" 2>/dev/null || echo "Unknown")
SEVERITY=$(echo "$ALERT_JSON" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('alerts', [{}])[0].get('labels', {}).get('severity', 'unknown'))" 2>/dev/null || echo "unknown")
SUMMARY=$(echo "$ALERT_JSON" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('alerts', [{}])[0].get('annotations', {}).get('summary', 'No summary'))" 2>/dev/null || echo "No summary")
DESCRIPTION=$(echo "$ALERT_JSON" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('alerts', [{}])[0].get('annotations', {}).get('description', 'No description'))" 2>/dev/null || echo "No description")
STATUS=$(echo "$ALERT_JSON" | python3 -c "import sys, json; data = json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")

# Format message
if [ "$STATUS" = "resolved" ]; then
    EMOJI="✅"
    STATUS_TEXT="RESOLVED"
else
    if [ "$SEVERITY" = "critical" ]; then
        EMOJI="🚨🚨🚨"
        STATUS_TEXT="CRITICAL"
    else
        EMOJI="⚠️"
        STATUS_TEXT="WARNING"
    fi
fi

MESSAGE="${EMOJI} ${STATUS_TEXT} ALERT: ${ALERT_NAME}

${SUMMARY}

${DESCRIPTION}

Severity: ${SEVERITY}
Status: ${STATUS_TEXT}"

# Send to Telegram
curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
    -d "chat_id=${TELEGRAM_CHAT_ID}" \
    -d "text=$(echo "$MESSAGE" | sed 's/"/\\"/g')" \
    -d "parse_mode=HTML" \
    > /dev/null

exit 0

