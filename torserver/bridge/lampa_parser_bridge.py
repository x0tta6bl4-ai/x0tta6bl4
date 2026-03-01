#!/usr/bin/env python3
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, quote, urlparse
from urllib.request import Request, urlopen

BACKEND = os.environ.get("TS_BACKEND", "http://127.0.0.1:8091")

SIZE_RE = re.compile(r"^\s*([0-9]+(?:[\.,][0-9]+)?)\s*([KMGT]?B)\s*$", re.IGNORECASE)
SIZE_MUL = {
    "B": 1,
    "KB": 1024,
    "MB": 1024**2,
    "GB": 1024**3,
    "TB": 1024**4,
}

AAC_HINTS = (
    "aac",
    "aac-lc",
    "he-aac",
    "mp4a",
    "opus",
)
AC3_HINTS = ("ac3", "eac3", "dts", "truehd", "atmos")
WEB_HINTS = ("web-dlrip", "webrip", "web-rip", "avc")
HEAVY_HINTS = ("remux", "2160", "uhd", "hevc", "h265")


def env_bool(name, default):
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


AUDIO_FRIENDLY_SORT = env_bool("AUDIO_FRIENDLY_SORT", True)


def parse_size_to_bytes(value):
    if isinstance(value, (int, float)):
        return int(value)
    if not isinstance(value, str):
        return 0
    m = SIZE_RE.match(value)
    if not m:
        return 0
    n = float(m.group(1).replace(",", "."))
    u = m.group(2).upper()
    return int(n * SIZE_MUL.get(u, 1))


def to_int(value):
    try:
        return int(value)
    except Exception:
        return 0


def to_jackett_item(item):
    return {
        "Title": item.get("Title", ""),
        "Tracker": item.get("Tracker", "TorrServer"),
        "Size": parse_size_to_bytes(item.get("Size", 0)),
        "PublishDate": item.get("CreateDate", ""),
        "Seeders": to_int(item.get("Seed", 0)),
        "Peers": to_int(item.get("Peer", 0)),
        "MagnetUri": item.get("Magnet", ""),
    }


def _title_text(item):
    return str(item.get("Title", "")).lower()


def _audio_friendly_score(item):
    title = _title_text(item)
    size = parse_size_to_bytes(item.get("Size", 0))

    score = 0
    if any(h in title for h in AAC_HINTS):
        score += 120
    if any(h in title for h in AC3_HINTS):
        score -= 110
    if any(h in title for h in WEB_HINTS):
        score += 25
    if any(h in title for h in HEAVY_HINTS):
        score -= 20

    # Smaller WEB rips tend to have browser-friendly audio tracks more often.
    if 0 < size <= 1_000_000_000:
        score += 35
    elif size <= 2_500_000_000:
        score += 20
    elif size >= 6_000_000_000:
        score -= 12

    return score


def _sorted_results(items):
    # Python's sort is stable, so source order is preserved for equal scores.
    return sorted(items, key=_audio_friendly_score, reverse=True)


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        # Keep container logs concise.
        pass

    def _set_cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header(
            "Access-Control-Allow-Headers",
            "Origin,Content-Length,Content-Type,X-Requested-With,Accept,Authorization",
        )
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS")
        self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Access-Control-Max-Age", "43200")

    def do_OPTIONS(self):
        self.send_response(204)
        self._set_cors()
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self):
        self._handle()

    def do_POST(self):
        self._redirect()

    def do_PUT(self):
        self._redirect()

    def do_PATCH(self):
        self._redirect()

    def do_DELETE(self):
        self._redirect()

    def do_HEAD(self):
        self._redirect()

    def _handle(self):
        p = urlparse(self.path)
        if p.path.startswith("/api/v2.0/indexers/") and p.path.endswith("/results"):
            self._handle_jackett_search(p)
            return
        self._redirect()

    def _handle_jackett_search(self, parsed):
        q = parse_qs(parsed.query)
        query = q.get("Query", [""])[0]
        url = f"{BACKEND}/search/?query={quote(query)}"

        results = []
        try:
            req = Request(url, headers={"Accept": "application/json"}, method="GET")
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(data, list):
                if AUDIO_FRIENDLY_SORT:
                    data = _sorted_results(data)
                results = [to_jackett_item(x) for x in data]
        except Exception:
            results = []

        body = json.dumps({"Results": results}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _redirect(self):
        target = f"{BACKEND}{self.path}"
        self.send_response(307)
        self._set_cors()
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()


def main():
    bind = os.environ.get("BIND", "0.0.0.0")
    port = int(os.environ.get("PORT", "8090"))
    srv = ThreadingHTTPServer((bind, port), Handler)
    print(f"lampa-parser-bridge listening on {bind}:{port}, backend={BACKEND}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
