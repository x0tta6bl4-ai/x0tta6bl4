#!/usr/bin/env python3
"""Aggregate monetization progress from tracker_structure.csv.

Reads CSV, computes expected vs collected, gap, and daily pace suggestion.
Usage:
  python progress_aggregator.py --csv tracker_structure.csv --collected 0 --days-left 27
Optionally append --update <value> for a channel (not implemented: this is read-only summary for now).
"""
import csv
import argparse
from pathlib import Path
from typing import List, Dict

TARGET_TOTAL = 1_000_000  # RUB


def read_rows(path: Path) -> List[Dict[str, str]]:
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [r for r in reader]


def parse_int(s: str) -> int:
    try:
        return int(float(s))
    except Exception:
        return 0


def summarize(rows: List[Dict[str, str]], collected_override: int, days_left: int) -> Dict:
    expected_sum = 0
    planned_sum = 0
    collected = 0
    channel_stats = []
    for r in rows:
        planned = parse_int(r.get('Planned RUB', '0'))
        expected = parse_int(r.get('Expected RUB', '0'))
        revenue = parse_int(r.get('Revenue Collected RUB', '0'))
        planned_sum += planned
        expected_sum += expected
        collected += revenue
        channel_stats.append({
            'channel': r.get('Channel','?'),
            'planned': planned,
            'expected': expected,
            'revenue': revenue,
            'status': r.get('Status',''),
            'next_action': r.get('Next Action','')
        })
    if collected_override >= 0:
        collected = collected_override
    gap_expected = max(expected_sum - collected, 0)
    gap_target = max(TARGET_TOTAL - collected, 0)
    # Pace suggestions
    daily_needed_target = gap_target / days_left if days_left > 0 else gap_target
    daily_needed_expected = gap_expected / days_left if days_left > 0 else gap_expected

    return {
        'target_total': TARGET_TOTAL,
        'planned_total': planned_sum,
        'expected_total': expected_sum,
        'collected_total': collected,
        'gap_expected': gap_expected,
        'gap_target': gap_target,
        'days_left': days_left,
        'daily_needed_target': round(daily_needed_target,2),
        'daily_needed_expected': round(daily_needed_expected,2),
        'channels': channel_stats,
    }


def human_report(data: Dict) -> str:
    lines = []
    lines.append(f"ЦЕЛЬ: {data['target_total']} RUB, собрано: {data['collected_total']} RUB")
    lines.append(f"План сумма: {data['planned_total']} RUB, ожидаемая (вероятностная): {data['expected_total']} RUB")
    lines.append(f"Gap до ожидаемого: {data['gap_expected']} RUB; Gap до цели: {data['gap_target']} RUB")
    lines.append(f"Осталось дней: {data['days_left']}")
    lines.append(f"Нужный темп (до цели): {data['daily_needed_target']}/день; до ожидаемого: {data['daily_needed_expected']}/день")
    lines.append("\nКаналы:")
    for c in data['channels']:
        lines.append(f" - {c['channel']}: planned={c['planned']} expected={c['expected']} collected={c['revenue']} status={c['status']} next={c['next_action']}")
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--collected', type=int, default=-1, help='Override collected total if you track externally')
    ap.add_argument('--days-left', type=int, default=27)
    args = ap.parse_args()

    rows = read_rows(Path(args.csv))
    summary = summarize(rows, args.collected, args.days_left)
    print(human_report(summary))

if __name__ == '__main__':
    main()
