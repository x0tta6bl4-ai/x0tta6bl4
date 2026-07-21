"""HTML Report Generator for x0tta6bl4 Validation Framework.

Generates human-readable HTML reports from validation results.

Reference: validation/spec/report_template.md
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


def generate_html_report(
    summary_path: Path,
    output_path: Path,
    baseline_comparison: Optional[dict] = None,
) -> Path:
    """Generate HTML report from summary.json.

    Args:
        summary_path: Path to summary.json
        output_path: Path to write report.html
        baseline_comparison: Optional comparison with baseline

    Returns:
        Path to generated report
    """
    with open(summary_path) as f:
        summary = json.load(f)

    verdict = summary.get("overall_verdict", "UNKNOWN")
    invariants = summary.get("invariants", {})
    sla_results = summary.get("sla_results", [])
    latency = summary.get("latency", {})
    regressions = summary.get("regressions", [])

    verdict_class = verdict.lower()

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Validation Report — {verdict}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; border-radius: 8px; padding: 30px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        h1 {{ color: #333; margin-bottom: 10px; }}
        .verdict {{ font-size: 24px; font-weight: bold; padding: 10px 20px; border-radius: 4px; display: inline-block; margin: 10px 0; }}
        .pass {{ background: #d4edda; color: #155724; }}
        .warning {{ background: #fff3cd; color: #856404; }}
        .fail {{ background: #f8d7da; color: #721c24; }}
        .unknown {{ background: #e2e3e5; color: #383d41; }}
        h2 {{ color: #555; margin: 20px 0 10px; border-bottom: 1px solid #eee; padding-bottom: 5px; }}
        table {{ width: 100%; border-collapse: collapse; margin: 10px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #eee; }}
        th {{ background: #f8f9fa; font-weight: 600; }}
        .pass-cell {{ color: #28a745; }}
        .warn-cell {{ color: #ffc107; }}
        .fail-cell {{ color: #dc3545; }}
        .meta {{ color: #666; font-size: 14px; margin: 20px 0; }}
        .section {{ margin: 20px 0; }}
        .regression {{ background: #fff3cd; padding: 10px; border-radius: 4px; margin: 10px 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Validation Report</h1>
        <div class="verdict {verdict_class}">{verdict}</div>

        <div class="meta">
            <p><strong>Commit:</strong> {summary.get('git_commit', 'unknown')}</p>
            <p><strong>Timestamp:</strong> {summary.get('timestamp', 'unknown')}</p>
            <p><strong>Generated:</strong> {datetime.now().isoformat()}</p>
        </div>

        <h2>Invariants</h2>
        <table>
            <tr><th>Metric</th><th>Value</th></tr>
            <tr><td>Verified</td><td class="pass-cell">{invariants.get('verified', 0)}</td></tr>
            <tr><td>Violated</td><td class="fail-cell">{invariants.get('violated', 0)}</td></tr>
            <tr><td>Skipped</td><td>{invariants.get('skipped', 0)}</td></tr>
        </table>

        <h2>SLA Results</h2>
        <table>
            <tr><th>Rule</th><th>Verdict</th><th>Measured</th></tr>
"""

    for r in sla_results:
        v = r.get("verdict", "UNKNOWN").lower()
        v_class = f"{v}-cell" if v in ("pass", "warning", "fail") else ""
        html += f'            <tr><td>{r.get("rule", "")}</td><td class="{v_class}">{r.get("verdict", "")}</td><td>{r.get("measured", "")}</td></tr>\n'

    html += """        </table>

        <h2>Latency</h2>
        <table>
            <tr><th>Target</th><th>Median (ms)</th><th>95% CI</th><th>N</th></tr>
"""

    for target, stats in latency.items():
        median = stats.get("median_ms", "N/A")
        ci_lower = stats.get("ci_lower_ms", "N/A")
        ci_upper = stats.get("ci_upper_ms", "N/A")
        n = stats.get("n", "N/A")
        ci_str = f"[{ci_lower}, {ci_upper}]" if ci_lower != "N/A" else "N/A"
        html += f'            <tr><td>{target}</td><td>{median}</td><td>{ci_str}</td><td>{n}</td></tr>\n'

    html += """        </table>
"""

    if regressions:
        html += """
        <h2>Regressions</h2>
"""
        for r in regressions:
            html += f'        <div class="regression"><strong>{r.get("metric", "")}</strong>: {r.get("change_pct", 0)}% change ({r.get("severity", "")})</div>\n'

    if baseline_comparison:
        html += """
        <h2>Baseline Comparison</h2>
        <table>
            <tr><th>Metric</th><th>Baseline</th><th>Current</th><th>Change</th><th>Severity</th></tr>
"""
        for c in baseline_comparison.get("comparisons", []):
            html += f'            <tr><td>{c.get("metric", "")}</td><td>{c.get("baseline", "")}</td><td>{c.get("current", "")}</td><td>{c.get("change_pct", 0)}%</td><td>{c.get("severity", "")}</td></tr>\n'
        html += """        </table>
"""

    html += """
    </div>
</body>
</html>"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write(html)

    return output_path
