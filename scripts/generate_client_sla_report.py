import argparse
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class SLAReportGenerator:
    """
    Generates SLA reports from real metrics sources.

    Source priority:
    1) JSON metrics file (--metrics-file)
    2) Prometheus HTTP API (--prometheus-url / PROMETHEUS_URL)
    3) Empty report with explicit NO-DATA markers
    """

    PROM_QUERY_MAP = {
        "uptime_percent": "avg_over_time(up[30d]) * 100",
        "avg_mttr_sec": "avg_over_time(x0t_mttr_seconds[30d])",
        "threats_blocked": "sum(increase(x0t_security_events_blocked_total[30d]))",
        "pqc_handshakes": "sum(increase(x0t_pqc_handshakes_total[30d]))",
        "latency_p95_ms": (
            "histogram_quantile(0.95, "
            "sum(rate(http_request_duration_seconds_bucket[5m])) by (le)) * 1000"
        ),
        "throughput_mbps": "avg_over_time(x0t_effective_throughput_mbps[30d])",
        "auto_recovery_success_rate": "avg_over_time(x0t_auto_recovery_success_rate[30d])",
    }

    def __init__(
        self,
        client_id: str,
        prometheus_url: Optional[str] = None,
        metrics_file: Optional[str] = None,
        timeout_sec: float = 5.0,
    ):
        self.client_id = client_id
        self.prometheus_url = prometheus_url.rstrip("/") if prometheus_url else None
        self.metrics_file = metrics_file
        self.timeout_sec = timeout_sec

    def _empty_metrics(self) -> Dict[str, Any]:
        return {
            "uptime_percent": None,
            "avg_mttr_sec": None,
            "threats_blocked": None,
            "pqc_handshakes": None,
            "protocol_integrity": None,
            "latency_p95_ms": None,
            "throughput_mbps": None,
            "auto_recovery_success_rate": None,
            "source": "no-data",
        }

    def _to_float(self, value: Any) -> Optional[float]:
        try:
            if value is None:
                return None
            return float(value)
        except (TypeError, ValueError):
            return None

    def _to_int(self, value: Any) -> Optional[int]:
        try:
            if value is None:
                return None
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def _load_from_json(self, path: str) -> Dict[str, Any]:
        with open(path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)

        metrics = self._empty_metrics()
        metrics.update(
            {
                "uptime_percent": self._to_float(raw.get("uptime_percent", raw.get("uptime"))),
                "avg_mttr_sec": self._to_float(raw.get("avg_mttr_sec")),
                "threats_blocked": self._to_int(raw.get("threats_blocked")),
                "pqc_handshakes": self._to_int(raw.get("pqc_handshakes")),
                "protocol_integrity": raw.get("protocol_integrity", raw.get("pqc_integrity_checks")),
                "latency_p95_ms": self._to_float(raw.get("latency_p95_ms")),
                "throughput_mbps": self._to_float(
                    raw.get("throughput_mbps", raw.get("effective_throughput_mbps"))
                ),
                "auto_recovery_success_rate": self._to_float(raw.get("auto_recovery_success_rate")),
                "source": f"json:{path}",
            }
        )
        return metrics

    def _prometheus_query(self, query: str) -> Optional[float]:
        if not self.prometheus_url:
            return None

        endpoint = f"{self.prometheus_url}/api/v1/query"
        encoded = urllib.parse.urlencode({"query": query})
        url = f"{endpoint}?{encoded}"

        try:
            with urllib.request.urlopen(url, timeout=self.timeout_sec) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
            return None

        if payload.get("status") != "success":
            return None

        result = payload.get("data", {}).get("result", [])
        if not result:
            return None

        value = result[0].get("value")
        if not value or len(value) < 2:
            return None

        return self._to_float(value[1])

    def _load_from_prometheus(self) -> Dict[str, Any]:
        metrics = self._empty_metrics()
        if not self.prometheus_url:
            return metrics

        any_data = False
        for metric_key, prom_query in self.PROM_QUERY_MAP.items():
            result = self._prometheus_query(prom_query)
            if result is not None:
                any_data = True
                metrics[metric_key] = result

        if any_data:
            metrics["source"] = f"prometheus:{self.prometheus_url}"
        return metrics

    def fetch_metrics(self) -> Dict[str, Any]:
        if self.metrics_file:
            return self._load_from_json(self.metrics_file)

        if self.prometheus_url:
            return self._load_from_prometheus()

        return self._empty_metrics()

    def _status_uptime(self, uptime_percent: Optional[float]) -> str:
        if uptime_percent is None:
            return "NO-DATA"
        if uptime_percent >= 99.9:
            return "COMPLIANT"
        return "NON-COMPLIANT"

    def _status_mttr(self, avg_mttr_sec: Optional[float]) -> str:
        if avg_mttr_sec is None:
            return "NO-DATA"
        if avg_mttr_sec < 30:
            return "COMPLIANT"
        return "NON-COMPLIANT"

    def _fmt_num(self, value: Optional[float], decimals: int = 2) -> str:
        if value is None:
            return "N/A"
        return f"{value:.{decimals}f}"

    def _stable_report_hash(self, metrics: Dict[str, Any]) -> str:
        digest_payload = {
            "client_id": self.client_id,
            "period": datetime.now(timezone.utc).strftime("%Y-%m"),
            "metrics": metrics,
        }
        canonical = json.dumps(digest_payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def generate_report_text(self) -> str:
        metrics = self.fetch_metrics()
        generated_at = datetime.now(timezone.utc).isoformat()
        report_hash = self._stable_report_hash(metrics)

        uptime = self._fmt_num(metrics.get("uptime_percent"), 3)
        mttr = self._fmt_num(metrics.get("avg_mttr_sec"), 2)
        latency = self._fmt_num(metrics.get("latency_p95_ms"), 2)
        throughput = self._fmt_num(metrics.get("throughput_mbps"), 2)
        threats_blocked = metrics.get("threats_blocked")
        pqc_handshakes = metrics.get("pqc_handshakes")
        protocol_integrity = metrics.get("protocol_integrity") or "N/A"
        auto_recovery_rate = metrics.get("auto_recovery_success_rate")

        auto_recovery_text = "N/A"
        if auto_recovery_rate is not None:
            auto_recovery_text = f"{auto_recovery_rate:.2f}%"

        threats_text = str(threats_blocked) if threats_blocked is not None else "N/A"
        handshakes_text = str(pqc_handshakes) if pqc_handshakes is not None else "N/A"
        uptime_text = f"{uptime}%" if metrics.get("uptime_percent") is not None else "N/A"
        mttr_text = f"{mttr}s" if metrics.get("avg_mttr_sec") is not None else "N/A"
        latency_text = f"{latency}ms" if metrics.get("latency_p95_ms") is not None else "N/A"
        throughput_text = f"{throughput} Mbps" if metrics.get("throughput_mbps") is not None else "N/A"

        report = f"""
====================================================
x0tta6bl4 ENTERPRISE SLA REPORT
Client ID: {self.client_id}
Period: {datetime.now(timezone.utc).strftime('%B %Y')}
Data Source: {metrics.get('source', 'unknown')}
====================================================

1. NETWORK AVAILABILITY
-----------------------
Uptime: {uptime_text} (Target: 99.9%)
Status: {self._status_uptime(metrics.get('uptime_percent'))}

2. SELF-HEALING PERFORMANCE
---------------------------
Avg. Recovery Time (MTTR): {mttr_text} (Target: <30s)
Auto-Recovery Success Rate: {auto_recovery_text}
Status: {self._status_mttr(metrics.get('avg_mttr_sec'))}

3. SECURITY & POST-QUANTUM SHIELD
---------------------------------
PQC Handshakes: {handshakes_text}
Security Events Blocked: {threats_text}
Protocol Integrity: {protocol_integrity}

4. PERFORMANCE
--------------
Latency (P95): {latency_text}
Effective Throughput: {throughput_text}

====================================================
Generated on (UTC): {generated_at}
Report SHA-256: {report_hash}
"""
        return report.strip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate client SLA report from real metrics.")
    parser.add_argument(
        "--client-id",
        default=os.getenv("SLA_CLIENT_ID", "ENTERPRISE-CLIENT-001"),
        help="Client identifier in report output.",
    )
    parser.add_argument(
        "--prometheus-url",
        default=os.getenv("PROMETHEUS_URL"),
        help="Prometheus base URL, for example http://127.0.0.1:9090",
    )
    parser.add_argument(
        "--metrics-file",
        default=None,
        help="Path to JSON file with pre-collected metrics.",
    )
    parser.add_argument(
        "--timeout-sec",
        type=float,
        default=5.0,
        help="HTTP timeout when querying Prometheus.",
    )
    parser.add_argument(
        "--output",
        default=None,
        help="Optional output path. If omitted, report is printed to stdout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    generator = SLAReportGenerator(
        client_id=args.client_id,
        prometheus_url=args.prometheus_url,
        metrics_file=args.metrics_file,
        timeout_sec=args.timeout_sec,
    )
    report = generator.generate_report_text()

    if args.output:
        with open(args.output, "w", encoding="utf-8") as fh:
            fh.write(report)
    else:
        print(report, end="")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
