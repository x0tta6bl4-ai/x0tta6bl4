#!/bin/bash
# Cron task script for GTM Agent reporting
export PYTHONPATH=$PYTHONPATH:/mnt/projects
python3 /mnt/projects/src/agents/gtm_agent.py
