#!/usr/bin/env bash
# Agent Trace — захват трейса текущей сессии Hermes
# Сохраняет последние N сообщений для последующей оценки через self_eval.py
#
# Использование:
#   eval/trace.sh                    # захватить последнюю сессию
#   eval/trace.sh --task "my task"   # с описанием задачи
#   eval/trace.sh --expected "..."   # с ожидаемым ответом
#   eval/trace.sh --output custom.json
#
# Результат: eval/traced/<timestamp>.json

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${SCRIPT_DIR}/traced"
mkdir -p "$OUT_DIR"

TASK="${1:-}"
EXPECTED="${2:-}"
OUTPUT="${3:-${OUT_DIR}/trace-$(date +%Y%m%dT%H%M%S).json}"

# Парсим аргументы
while [[ $# -gt 0 ]]; do
  case "$1" in
    --task) TASK="$2"; shift 2 ;;
    --expected) EXPECTED="$2"; shift 2 ;;
    --output) OUTPUT="$2"; shift 2 ;;
    *) break ;;
  esac
done

# Собираем трейс через session_search (если доступен)
# или через прямые файлы сообщений
if command -v python3 &>/dev/null; then
  python3 - "$OUTPUT" "$TASK" "$EXPECTED" << 'PYEOF'
import json, os, sys, time
from datetime import datetime, timezone
from pathlib import Path

output_path = sys.argv[1]
task_desc = sys.argv[2] if len(sys.argv) > 2 else ""
expected = sys.argv[3] if len(sys.argv) > 3 else ""

# Пытаемся достать последние сообщения из Hermes
# через прямой доступ к БД или через файлы
hermes_home = os.environ.get("HERMES_HOME", str(Path.home() / ".hermes"))
session_dir = Path(hermes_home) / "sessions"

trace = {
    "schema": "x0tta6bl4.agent_trace.v1",
    "timestamp": datetime.now(timezone.utc).isoformat(),
    "task": task_desc,
    "expected": expected,
    "final_answer": "",
    "messages": [],
    "source": "trace.sh",
}

# Ищем последнюю сессию
if session_dir.exists():
    sessions = sorted(session_dir.glob("session_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if sessions:
        last = sessions[0]
        try:
            data = json.loads(last.read_text())
            trace["messages"] = data.get("messages", data.get("history", []))
            print(f"  📂 Loaded session: {last.name}", file=sys.stderr)
        except (json.JSONDecodeError, OSError) as e:
            print(f"  ⚠️  Could not load {last.name}: {e}", file=sys.stderr)

# Если messages пуст — создаём шаблон
if not trace["messages"]:
    print("  ⚠️  No messages found — creating template", file=sys.stderr)
    trace["messages"] = [
        {"role": "user", "content": task_desc or "<!-- describe your task here -->"},
    ]

# Запрашиваем final answer
if not trace["final_answer"]:
    print("  ✏️  Enter the agent's final answer (or press Enter to skip):", file=sys.stderr)
    final = input().strip()
    trace["final_answer"] = final

Path(output_path).write_text(json.dumps(trace, indent=2, ensure_ascii=False))
print(f"\n  💾 Trace saved: {output_path}", file=sys.stderr)
print(output_path)
PYEOF
fi
