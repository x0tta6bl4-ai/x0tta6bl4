#!/bin/bash
# Crontab setup for x0tta6bl4 GTM Reporting

PROJECT_DIR="/mnt/projects"
LOG_DIR="$PROJECT_DIR/logs"
PYTHON_VAL=".venv/bin/python3"

mkdir -p "$LOG_DIR"

# Add job to crontab if not exists
# Runs everyday at 09:00
CRON_JOB="0 9 * * * cd $PROJECT_DIR && PYTHONPATH=. $PYTHON_VAL src/agents/gtm_agent.py >> $LOG_DIR/gtm_cron.log 2>&1"

(crontab -l 2>/dev/null | grep -v "gtm_agent.py" ; echo "$CRON_JOB") | crontab -

echo "✅ Crontab job added: Every day at 09:00"
crontab -l | grep "gtm_agent.py"
