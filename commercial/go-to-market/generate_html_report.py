#!/usr/bin/env python3
"""Generate HTML progress report from tracker CSV.

Usage:
  python generate_html_report.py --csv tracker_structure.csv --output progress_report.html --days-left 27 --collected 0
"""
import csv
import argparse
from pathlib import Path
from datetime import datetime

TARGET_TOTAL = 1_000_000

CSS = """
body{font-family:system-ui,Arial,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:0}
header{padding:32px 24px;background:linear-gradient(135deg,#1f2937,#0d1117 60%);}h1{margin:0;font-size:1.9rem}
section{max-width:1100px;margin:24px auto;padding:0 24px}
table{width:100%;border-collapse:collapse;margin-top:16px;font-size:0.9rem}
th,td{padding:8px 10px;border:1px solid #30363d;text-align:left}
th{background:#161b22}
.tag{display:inline-block;padding:2px 8px;border-radius:12px;font-size:0.7rem;background:#23863622;border:1px solid #23863655;color:#58a6ff}
.status-Prospecting{background:#3b82f622;border-color:#3b82f655;color:#3b82f6}
.status-Design{background:#8b5cf622;border-color:#8b5cf655;color:#c084fc}
.status-Pre-launch{background:#f59e0b22;border-color:#f59e0b55;color:#fbbf24}
.status-Drafting{background:#f9731622;border-color:#f9731655;color:#fb923c}
footer{padding:40px 24px;text-align:center;font-size:0.75rem;opacity:0.65}
.badge{background:#23863622;padding:4px 6px;border-radius:6px;margin-right:4px}
.metrics{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-top:24px}
.metric{background:#161b22;padding:12px;border-radius:10px;border:1px solid #30363d}
.metric h3{margin:0 0 4px 0;font-size:0.85rem;font-weight:600;opacity:.8}
.metric p{margin:0;font-size:1.1rem;font-weight:600}
.warning{color:#f87171}
.success{color:#34d399}
"""


def parse_int(s: str) -> int:
    try:
        return int(float(s))
    except Exception:
        return 0


def load_rows(path: Path):
    with path.open('r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return [r for r in reader]


def compute(rows, collected_override: int, days_left: int):
    planned_total = 0
    expected_total = 0
    collected_total = 0
    enriched = []
    for r in rows:
        planned = parse_int(r.get('Planned RUB','0'))
        expected = parse_int(r.get('Expected RUB','0'))
        collected = parse_int(r.get('Revenue Collected RUB','0'))
        planned_total += planned
        expected_total += expected
        collected_total += collected
        enriched.append({
            'channel': r.get('Channel','?'),
            'planned': planned,
            'expected': expected,
            'collected': collected,
            'status': r.get('Status',''),
            'next_action': r.get('Next Action','')
        })
    if collected_override >= 0:
        collected_total = collected_override
    gap_target = max(TARGET_TOTAL - collected_total,0)
    gap_expected = max(expected_total - collected_total,0)
    daily_needed_target = gap_target / days_left if days_left>0 else gap_target
    daily_needed_expected = gap_expected / days_left if days_left>0 else gap_expected
    return {
        'planned_total': planned_total,
        'expected_total': expected_total,
        'collected_total': collected_total,
        'gap_target': gap_target,
        'gap_expected': gap_expected,
        'daily_needed_target': daily_needed_target,
        'daily_needed_expected': daily_needed_expected,
        'days_left': days_left,
        'channels': enriched
    }


def render_html(data):
    dt = datetime.utcnow().isoformat()+"Z"
    def fmt(n):
        return f"{int(n):,}".replace(',', ' ')
    html = ["<!DOCTYPE html><html lang='ru'><head><meta charset='UTF-8'><title>Отчет прогресса</title><style>"+CSS+"</style></head><body>"]
    html.append("<header><h1>Монетизация: прогресс цели 1 000 000 RUB</h1><p>Сгенерировано: "+dt+"</p></header>")
    html.append("<section><div class='metrics'>")
    html.append(f"<div class='metric'><h3>Собрано</h3><p>{fmt(data['collected_total'])} RUB</p></div>")
    html.append(f"<div class='metric'><h3>Ожидаемое (вероятностное)</h3><p>{fmt(data['expected_total'])} RUB</p></div>")
    html.append(f"<div class='metric'><h3>Gap до цели</h3><p class='{'success' if data['gap_target']==0 else 'warning'}'>{fmt(data['gap_target'])} RUB</p></div>")
    html.append(f"<div class='metric'><h3>Дней осталось</h3><p>{data['days_left']}</p></div>")
    html.append(f"<div class='metric'><h3>Темп до цели</h3><p>{int(data['daily_needed_target'])} RUB/день</p></div>")
    html.append(f"<div class='metric'><h3>Темп до ожидаемого</h3><p>{int(data['daily_needed_expected'])} RUB/день</p></div>")
    html.append("</div></section>")
    # Table
    html.append("<section><h2>Каналы</h2><table><thead><tr><th>Канал</th><th>Planned</th><th>Expected</th><th>Collected</th><th>Status</th><th>Next</th></tr></thead><tbody>")
    for c in data['channels']:
        html.append(f"<tr><td>{c['channel']}</td><td>{fmt(c['planned'])}</td><td>{fmt(c['expected'])}</td><td>{fmt(c['collected'])}</td><td><span class='tag status-{c['status']}'>{c['status']}</span></td><td>{c['next_action']}</td></tr>")
    html.append("</tbody></table></section>")
    html.append("<footer>© 2025 x0tta6bl4 • Автоотчет монетизации • Обновлено: "+dt+"</footer></body></html>")
    return '\n'.join(html)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True)
    ap.add_argument('--output', default='progress_report.html')
    ap.add_argument('--days-left', type=int, default=27)
    ap.add_argument('--collected', type=int, default=-1)
    args = ap.parse_args()
    rows = load_rows(Path(args.csv))
    data = compute(rows, args.collected, args.days_left)
    html = render_html(data)
    Path(args.output).write_text(html, encoding='utf-8')
    print(f"HTML report written: {args.output}")

if __name__ == '__main__':
    main()
