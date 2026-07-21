#!/usr/bin/env python3
"""LLM-as-a-Judge для оценки сессий x0tta6bl4 агента.

Использование:
  # Оценить JSON с сессией
  python3 eval/self_eval.py --session session_log.json

  # Оценить последнюю сессию из БД
  python3 eval/self_eval.py --last

  # Запустить тестовый eval на промптах из SimpleQA
  python3 eval/self_eval.py --bench simpleqa --limit 3

  # Вывести отчёт
  python3 eval/self_eval.py --report

Формат session_log.json:
  {
    "task": "What is the capital of France?",
    "expected": "Paris",
    "messages": [
      {"role": "user", "content": "..."},
      {"role": "assistant", "content": "..."},
      {"role": "tool", "content": "...", "name": "terminal"},
      {"role": "assistant", "content": "..."}
    ],
    "final_answer": "Paris"
  }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

JUDGE_SYSTEM_PROMPT = """You are an impartial judge evaluating an AI agent's performance.

You will receive:
1. A task description
2. The expected answer/solution
3. The full conversation log (agent messages, tool calls, results)
4. The agent's final answer

Evaluate the agent on these criteria:
- CORRECT: The agent solved the task correctly and completely.
- PARTIAL: The agent made progress but the answer is incomplete or has minor errors.
- INCORRECT: The agent failed to solve the task or gave a wrong answer.

For each evaluation, provide:
1. Verdict: CORRECT / PARTIAL / INCORRECT
2. Score: 0.0–1.0
3. Reasoning: 2-3 sentences explaining your verdict
4. Key issues: list of any mistakes or missed requirements
5. Eval quality: was the task well-defined enough to judge?

Be strict but fair. Consider the whole conversation, not just the final answer."""


def load_task_log(path: str) -> dict:
    """Load a task evaluation JSON."""
    with open(path) as f:
        return json.load(f)


def build_judge_prompt(task: dict) -> list[dict]:
    """Build messages for LLM-as-a-judge."""
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
        {"role": "user", "content": f"# Task\n\n{task.get('task', task.get('question', 'N/A'))}\n\n---\n\n## Expected Answer\n\n{task.get('expected', task.get('answer', 'N/A'))}\n\n---\n\n## Conversation Log\n\n"},
    ]

    # Add conversation messages
    for msg in task.get("messages", []):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        if msg.get("name"):
            messages.append({
                "role": "user",
                "content": f"[Tool: {msg['name']}]\n{content}"
            })
        else:
            messages.append({"role": role, "content": content})

    # Add final answer
    final = task.get("final_answer") or task.get("answer", "")
    messages.append({
        "role": "user",
        "content": f"\n---\n\n## Agent's Final Answer\n\n{final}\n\nEvaluate this agent's performance."
    })

    return messages


def call_judge(messages: list[dict], model: str = "anthropic/claude-sonnet-4") -> str:
    """Call the judge model via OpenAI-compatible API."""
    import httpx

    base_url = os.environ.get("JUDGE_BASE_URL", "https://api.anthropic.com/v1")
    api_key = os.environ.get("JUDGE_API_KEY") or os.environ.get("ANTHROPIC_API_KEY", "")

    if not api_key:
        print("❌ JUDGE_API_KEY or ANTHROPIC_API_KEY not set", file=sys.stderr)
        sys.exit(1)

    client = httpx.Client(base_url=base_url, timeout=120)
    body = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 2048,
    }

    resp = client.post(
        "/v1/messages",
        json=body,
        headers={"Content-Type": "application/json", "x-api-key": api_key, "anthropic-version": "2023-06-01"},
    )
    resp.raise_for_status()
    data = resp.json()
    return data["content"][0]["text"]


def parse_verdict(text: str) -> dict:
    """Parse judge response into structured verdict."""
    text_lower = text.lower()
    if "correct" in text_lower and "incorrect" not in text_lower:
        verdict = "CORRECT"
    elif "partial" in text_lower:
        verdict = "PARTIAL"
    else:
        verdict = "INCORRECT"

    # Extract score
    score = 0.0
    import re
    score_match = re.search(r'(?:score|rate)[:\s]*([01]\.\d+|[01])', text_lower)
    if score_match:
        score = float(score_match.group(1))
    elif verdict == "CORRECT":
        score = 1.0
    elif verdict == "PARTIAL":
        score = 0.5

    return {
        "verdict": verdict,
        "score": score,
        "reasoning": text,
    }


def eval_session(task: dict, model: str = "anthropic/claude-sonnet-4") -> dict:
    """Run full evaluation on one task session."""
    messages = build_judge_prompt(task)
    judge_text = call_judge(messages, model=model)
    verdict = parse_verdict(judge_text)

    result = {
        "task": task.get("task", task.get("question", "")),
        "expected": task.get("expected", task.get("answer", "")),
        "final_answer": task.get("final_answer", ""),
        "judge_model": model,
        "judge_verdict": verdict["verdict"],
        "judge_score": verdict["score"],
        "judge_reasoning": verdict["reasoning"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "message_count": len(task.get("messages", [])),
    }
    return result


def save_result(result: dict, path: str = "./eval/results.jsonl") -> None:
    """Append result to JSONL file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(result) + "\n")
    print(f"  💾 Saved to {path}")


def print_report(results_path: str = "./eval/results.jsonl") -> None:
    """Print summary report from stored results."""
    path = Path(results_path)
    if not path.exists():
        print("❌ No results found")
        return

    results = []
    with open(path) as f:
        for line in f:
            if line.strip():
                results.append(json.loads(line))

    if not results:
        print("❌ No results found")
        return

    correct = sum(1 for r in results if r["judge_verdict"] == "CORRECT")
    partial = sum(1 for r in results if r["judge_verdict"] == "PARTIAL")
    incorrect = sum(1 for r in results if r["judge_verdict"] == "INCORRECT")
    avg_score = sum(r["judge_score"] for r in results) / len(results) if results else 0

    print(f"{'='*60}")
    print(f"📊 Eval Report — {len(results)} sessions")
    print(f"{'='*60}")
    print(f"  ✅ CORRECT:   {correct} ({correct/len(results)*100:.1f}%)" if results else "  ✅ CORRECT:   0")
    print(f"  🟡 PARTIAL:   {partial} ({partial/len(results)*100:.1f}%)" if results else "  🟡 PARTIAL:   0")
    print(f"  ❌ INCORRECT: {incorrect} ({incorrect/len(results)*100:.1f}%)" if results else "  ❌ INCORRECT: 0")
    print(f"  📈 Avg Score: {avg_score:.3f}")
    print(f"{'='*60}")
    print()

    # Worst tasks
    if results:
        print("🔻 Worst tasks:")
        for r in sorted(results, key=lambda x: x["judge_score"])[:3]:
            task_preview = r["task"][:80] + "..." if len(r["task"]) > 80 else r["task"]
            print(f"  [{r['judge_verdict']} @ {r['judge_score']:.2f}] {task_preview}")

        print()
        print("🔺 Best tasks:")
        for r in sorted(results, key=lambda x: -x["judge_score"])[:3]:
            task_preview = r["task"][:80] + "..." if len(r["task"]) > 80 else r["task"]
            print(f"  [{r['judge_verdict']} @ {r['judge_score']:.2f}] {task_preview}")


def load_simpleqa(path: str = "/tmp/harness-bench/benchmarks_data/simpleqa/questions/simpleqa_50_full_coverage.json") -> list[dict]:
    """Load SimpleQA questions as task templates."""
    if not Path(path).exists():
        print(f"⚠️  SimpleQA data not found at {path}")
        return []

    with open(path) as f:
        questions = json.load(f)

    tasks = []
    for q in questions:
        tasks.append({
            "task": q.get("question", ""),
            "expected": q.get("ideal_answer", ""),
            "final_answer": "",
            "messages": [{"role": "user", "content": q.get("question", "")}],
        })
    return tasks


def main():
    parser = argparse.ArgumentParser(description="x0tta6bl4 Self-Eval (LLM-as-a-Judge)")
    parser.add_argument("--session", type=str, help="Path to session JSON file")
    parser.add_argument("--last", action="store_true", help="Evaluate last session from DB")
    parser.add_argument("--bench", type=str, choices=["simpleqa"], help="Run benchmark eval")
    parser.add_argument("--limit", type=int, default=None, help="Limit task count")
    parser.add_argument("--report", action="store_true", help="Print evaluation report")
    parser.add_argument("--model", type=str, default="anthropic/claude-sonnet-4", help="Judge model")
    parser.add_argument("--results", type=str, default="./eval/results.jsonl", help="Results file")
    args = parser.parse_args()

    if args.report:
        print_report(args.results)
        return

    if args.session:
        task = load_task_log(args.session)
        result = eval_session(task, model=args.model)
        save_result(result, args.results)
        print(f"\n📋 Verdict: {result['judge_verdict']} (score: {result['judge_score']:.2f})")
        return

    if args.last:
        print("⚠️  --last uses session_search which requires a running Hermes session")
        print("    Use --session path/to/log.json instead")
        return

    if args.bench == "simpleqa":
        tasks = load_simpleqa()
        if args.limit:
            tasks = tasks[:args.limit]
        print(f"🔬 Running eval on {len(tasks)} SimpleQA tasks...")
        print(f"   Judge model: {args.model}")
        print()

        for i, task in enumerate(tasks):
            print(f"  [{i+1}/{len(tasks)}] {task['task'][:60]}...")
            result = eval_session(task, model=args.model)
            save_result(result, args.results)
            status = "✅" if result["judge_verdict"] == "CORRECT" else "🟡" if result["judge_verdict"] == "PARTIAL" else "❌"
            print(f"  {status} {result['judge_verdict']} ({result['judge_score']:.2f})")
            print()
            time.sleep(0.5)  # rate limit

        print(f"\n{'='*60}")
        print_report(args.results)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
