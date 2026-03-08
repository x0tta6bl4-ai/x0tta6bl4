#!/usr/bin/env python3
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
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
AUDIO_FILTER_MODE = os.environ.get("AUDIO_FILTER_MODE", "prefer").strip().lower() or "prefer"
STREAM_AUDIO_FIX = env_bool("STREAM_AUDIO_FIX", True)
FFMPEG_BIN = os.environ.get("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.environ.get("FFPROBE_BIN", "ffprobe")

UNSAFE_AUDIO_CODECS = {
    "ac3",
    "eac3",
    "dts",
    "dca",
    "truehd",
    "mlp",
}


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


def _has_any(title, hints):
    return any(h in title for h in hints)


def _stream_needs_transcode(path):
    # Use conservative filename-based detection:
    # transcode only when title strongly suggests unsupported browser audio.
    title = unquote(path or "").lower()
    return _has_any(title, AC3_HINTS)


def _probe_audio_codec(url):
    cmd = [
        FFPROBE_BIN,
        "-v",
        "error",
        "-rw_timeout",
        "5000000",
        "-probesize",
        "1048576",
        "-select_streams",
        "a:0",
        "-show_entries",
        "stream=codec_name",
        "-of",
        "default=nokey=1:noprint_wrappers=1",
        url,
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return ""
    if res.returncode != 0:
        return ""
    return (res.stdout or "").strip().lower()


def _is_browser_unsafe(item):
    title = _title_text(item)
    size = parse_size_to_bytes(item.get("Size", 0))

    # Conservative browser-unsafety hints for Chrome native playback.
    if _has_any(title, AC3_HINTS):
        return True
    if _has_any(title, HEAVY_HINTS):
        return True
    if "x265" in title or "10bit" in title:
        return True
    if size >= 7_000_000_000:
        return True
    return False


def _audio_friendly_score(item):
    title = _title_text(item)
    size = parse_size_to_bytes(item.get("Size", 0))

    score = 0
    if _has_any(title, AAC_HINTS):
        score += 120
    if _has_any(title, AC3_HINTS):
        score -= 110
    if _has_any(title, WEB_HINTS):
        score += 25
    if _has_any(title, HEAVY_HINTS):
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


def _apply_audio_policy(items):
    if not AUDIO_FRIENDLY_SORT:
        return items

    safe = [x for x in items if not _is_browser_unsafe(x)]
    unsafe = [x for x in items if _is_browser_unsafe(x)]

    if not safe:
        return _sorted_results(items)

    mode = AUDIO_FILTER_MODE
    if mode == "strict":
        strict = [x for x in safe if _has_any(_title_text(x), AAC_HINTS)]
        if strict:
            return _sorted_results(strict)
        return _sorted_results(safe)

    # default "prefer": keep unsafe results but move them after safe ones
    return _sorted_results(safe) + _sorted_results(unsafe)


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
        if p.path in ("/search", "/search/"):
            self._handle_torrserver_search(p)
            return
        if p.path.startswith("/stream"):
            self._handle_stream_proxy()
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
                data = _apply_audio_policy(data)
                results = [to_jackett_item(x) for x in data]
        except Exception:
            results = []

        body = json.dumps({"Results": results}, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_torrserver_search(self, parsed):
        q = parse_qs(parsed.query)
        query = q.get("query", [""])[0]
        url = f"{BACKEND}/search/?query={quote(query)}"

        results = []
        try:
            req = Request(url, headers={"Accept": "application/json"}, method="GET")
            with urlopen(req, timeout=15) as resp:
                raw = resp.read()
            data = json.loads(raw.decode("utf-8", errors="replace"))
            if isinstance(data, list):
                results = _apply_audio_policy(data)
        except Exception:
            results = []

        body = json.dumps(results, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
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

    def _proxy_backend(self):
        target = f"{BACKEND}{self.path}"
        req_headers = {}
        hop_by_hop = {
            "host",
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        }
        for key, value in self.headers.items():
            if key.lower() not in hop_by_hop:
                req_headers[key] = value

        try:
            req = Request(target, headers=req_headers, method=self.command)
            with urlopen(req, timeout=60) as resp:
                self.send_response(resp.status)
                self._set_cors()

                for h in (
                    "Content-Type",
                    "Content-Length",
                    "Content-Range",
                    "Accept-Ranges",
                    "ETag",
                    "Last-Modified",
                    "Cache-Control",
                ):
                    v = resp.headers.get(h)
                    if v:
                        self.send_header(h, v)
                self.end_headers()

                if self.command != "HEAD":
                    while True:
                        chunk = resp.read(64 * 1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
        except BrokenPipeError:
            return
        except HTTPError as err:
            body = err.read() if hasattr(err, "read") else b""
            self.send_response(err.code)
            self._set_cors()
            self.send_header("Content-Type", err.headers.get("Content-Type", "text/plain; charset=utf-8"))
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD" and body:
                self.wfile.write(body)
        except URLError:
            body = b'{"error":"upstream_unreachable"}'
            self.send_response(502)
            self._set_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)
        except Exception:
            body = b'{"error":"proxy_failed"}'
            self.send_response(500)
            self._set_cors()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

    def _handle_stream_proxy(self):
        parsed = urlparse(self.path)
        query = parse_qs(parsed.query, keep_blank_values=True)

        # Control endpoints must remain native TorrServer API behavior.
        if any(flag in query for flag in ("preload", "stat", "m3u")):
            self._proxy_backend()
            return

        # Only transcode actual play stream calls.
        if "play" not in query:
            self._proxy_backend()
            return

        # When enabled, remux/transcode stream into browser-friendly MP4/AAC for Chrome native playback.
        if not STREAM_AUDIO_FIX:
            self._proxy_backend()
            return

        # Keep native stream (range/seek/duration semantics) unless unsafe audio is likely.
        target = f"{BACKEND}{self.path}"
        needs_transcode = _stream_needs_transcode(parsed.path)
        if not needs_transcode:
            codec = _probe_audio_codec(target)
            if not codec or codec in UNSAFE_AUDIO_CODECS:
                needs_transcode = True

        if not needs_transcode:
            self._proxy_backend()
            return

        cmd = [
            FFMPEG_BIN,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-analyzeduration",
            "0",
            "-probesize",
            "65536",
            "-fflags",
            "+nobuffer",
            "-i",
            target,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-ac",
            "2",
            "-b:a",
            "160k",
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            "-f",
            "mp4",
            "pipe:1",
        ]

        try:
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=0,
            )
        except Exception:
            self._redirect()
            return

        self.send_response(200)
        self._set_cors()
        self.send_header("Content-Type", "video/mp4")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        try:
            while True:
                chunk = proc.stdout.read(64 * 1024) if proc.stdout is not None else b""
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
        except Exception:
            pass
        finally:
            try:
                proc.terminate()
            except Exception:
                pass


def main():
    bind = os.environ.get("BIND", "0.0.0.0")
    port = int(os.environ.get("PORT", "8090"))
    srv = ThreadingHTTPServer((bind, port), Handler)
    print(f"lampa-parser-bridge listening on {bind}:{port}, backend={BACKEND}", flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
