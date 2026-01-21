#!/usr/bin/env python3
"""
Generate Benchmark Report

Generates human-readable reports from benchmark JSON results.
Supports HTML and Markdown formats.
"""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any


def generate_markdown_report(data: Dict[str, Any]) -> str:
    """Generate Markdown report from benchmark data"""
    report = []
    report.append("# x0tta6bl4 Benchmark Report\n")
    report.append(f"**Date:** {data['timestamp']}\n")
    report.append(f"**Environment:** {data['environment'].get('os', 'Unknown')} {data['environment'].get('os_version', '')}\n")
    report.append("\n---\n")
    
    summary = data.get('summary', {})
    
    # MTTD
    if 'mttd' in summary:
        mttd = summary['mttd']
        status = "✅ PASS" if mttd.get('passed') else "❌ FAIL"
        report.append(f"## MTTD (Mean Time To Detect)\n")
        report.append(f"- **Mean:** {mttd['mean']:.2f}s")
        report.append(f"- **Target:** {mttd['target']}s")
        report.append(f"- **Status:** {status}\n")
    
    # MTTR
    if 'mttr' in summary:
        mttr = summary['mttr']
        status = "✅ PASS" if mttr.get('passed') else "❌ FAIL"
        report.append(f"## MTTR (Mean Time To Repair)\n")
        report.append(f"- **Mean:** {mttr['mean']:.2f}s")
        report.append(f"- **Target:** {mttr['target']}s")
        report.append(f"- **Status:** {status}\n")
    
    # PQC Handshake
    if 'pqc_handshake' in summary:
        pqc = summary['pqc_handshake']
        status = "✅ PASS" if pqc.get('passed') else "❌ FAIL"
        report.append(f"## PQC Handshake Latency\n")
        report.append(f"- **p95:** {pqc['p95']:.3f}ms")
        report.append(f"- **Target:** {pqc['target_p95']}ms")
        report.append(f"- **Status:** {status}\n")
    
    # Accuracy
    if 'accuracy' in summary:
        acc = summary['accuracy']
        status = "✅ PASS" if acc.get('passed') else "❌ FAIL"
        report.append(f"## Anomaly Detection Accuracy\n")
        report.append(f"- **Mean:** {acc['mean']:.2%}")
        report.append(f"- **Target:** {acc['target']:.0%}")
        report.append(f"- **Status:** {status}\n")
    
    # Auto-Resolution
    if 'auto_resolution' in summary:
        auto = summary['auto_resolution']
        status = "✅ PASS" if auto.get('passed') else "❌ FAIL"
        report.append(f"## Auto-Resolution Rate\n")
        report.append(f"- **Mean:** {auto['mean']:.2%}")
        report.append(f"- **Target:** {auto['target']:.0%}")
        report.append(f"- **Status:** {status}\n")
    
    # Root Cause
    if 'root_cause' in summary:
        rc = summary['root_cause']
        status = "✅ PASS" if rc.get('passed') else "❌ FAIL"
        report.append(f"## Root Cause Accuracy\n")
        report.append(f"- **Mean:** {rc['mean']:.2%}")
        report.append(f"- **Target:** {rc['target']:.0%}")
        report.append(f"- **Status:** {status}\n")
    
    return "\n".join(report)


def generate_html_report(data: Dict[str, Any]) -> str:
    """Generate HTML report from benchmark data"""
    html = []
    html.append("<!DOCTYPE html>")
    html.append("<html><head>")
    html.append("<title>x0tta6bl4 Benchmark Report</title>")
    html.append("<style>")
    html.append("body { font-family: Arial, sans-serif; margin: 20px; }")
    html.append("h1 { color: #333; }")
    html.append("h2 { color: #666; margin-top: 30px; }")
    html.append(".pass { color: green; }")
    html.append(".fail { color: red; }")
    html.append("table { border-collapse: collapse; width: 100%; margin: 20px 0; }")
    html.append("th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }")
    html.append("th { background-color: #f2f2f2; }")
    html.append("</style>")
    html.append("</head><body>")
    html.append("<h1>x0tta6bl4 Benchmark Report</h1>")
    html.append(f"<p><strong>Date:</strong> {data['timestamp']}</p>")
    html.append(f"<p><strong>Environment:</strong> {data['environment'].get('os', 'Unknown')}</p>")
    
    summary = data.get('summary', {})
    
    html.append("<h2>Summary</h2>")
    html.append("<table>")
    html.append("<tr><th>Metric</th><th>Value</th><th>Target</th><th>Status</th></tr>")
    
    for metric_name, metric_data in summary.items():
        if isinstance(metric_data, dict) and 'passed' in metric_data:
            status_class = "pass" if metric_data['passed'] else "fail"
            status_text = "✅ PASS" if metric_data['passed'] else "❌ FAIL"
            
            if 'mean' in metric_data:
                value = f"{metric_data['mean']:.3f}"
                target = str(metric_data.get('target', 'N/A'))
            elif 'p95' in metric_data:
                value = f"p95={metric_data['p95']:.3f}ms"
                target = f"{metric_data.get('target_p95', 'N/A')}ms"
            else:
                continue
            
            html.append(f"<tr>")
            html.append(f"<td>{metric_name.upper()}</td>")
            html.append(f"<td>{value}</td>")
            html.append(f"<td>{target}</td>")
            html.append(f"<td class='{status_class}'>{status_text}</td>")
            html.append(f"</tr>")
    
    html.append("</table>")
    html.append("</body></html>")
    
    return "\n".join(html)


def main():
    """Main report generator"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate benchmark report")
    parser.add_argument(
        "input_file",
        type=Path,
        help="Input JSON benchmark file"
    )
    parser.add_argument(
        "--format",
        choices=["markdown", "html"],
        default="markdown",
        help="Output format"
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output file (default: input_file with new extension)"
    )
    
    args = parser.parse_args()
    
    # Read input
    with open(args.input_file) as f:
        data = json.load(f)
    
    # Generate report
    if args.format == "markdown":
        report = generate_markdown_report(data)
        extension = ".md"
    else:
        report = generate_html_report(data)
        extension = ".html"
    
    # Write output
    if args.output:
        output_file = args.output
    else:
        output_file = args.input_file.with_suffix(extension)
    
    with open(output_file, "w") as f:
        f.write(report)
    
    print(f"✅ Report generated: {output_file}")


if __name__ == "__main__":
    main()

