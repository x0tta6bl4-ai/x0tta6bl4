#!/bin/bash
source .venv/bin/activate
uvicorn src.core.app:app --host 0.0.0.0 --port 8000 > .logs/server.log 2>&1
