#!/bin/bash
# x0tta6bl4 AI Navigator Auto-Pilot
# Set this to run weekly: 0 9 * * 1 (Every Monday at 9 AM)

PROJECT_DIR="/mnt/projects"
cd $PROJECT_DIR

echo "[$(date)] 🧭 Starting AI Navigation Auto-Pilot..."

# Ensure PYTHONPATH is set
export PYTHONPATH=$PYTHONPATH:.

# Run the brief generator
python3 scripts/generate_weekly_brief.py

# Optional: Ping or send brief to API/Webhook
# curl -X POST -H "Content-Type: application/json" -d @reports/weekly_brief_latest.md https://api.x0tta6bl4.ai/v1/briefs

echo "[$(date)] ✅ AI Navigation Brief completed."
