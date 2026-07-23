#!/bin/bash
# AI 3D CAD Studio — запуск
cd "$(dirname "$0")"
exec /home/x0ttta6bl4/.codex/skills/cad/.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8095 --reload
