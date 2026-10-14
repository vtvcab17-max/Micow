"""Máy chủ cục bộ của Micow: phát giao diện web + REST API (chỉ thư viện chuẩn Python).

Mặc định nghe 127.0.0.1:5690. Bản web trên Internet (nếu có) gọi về máy chủ này – mô hình luôn chạy trên máy bạn.
Chỉ các nguồn (Origin) trong danh sách cho phép mới gọi được API từ trình duyệt.
"""
from __future__ import annotations

import io
import json
import mimetypes
import re
import threading
import traceback
import urllib.parse
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import APP_NAME, DEFAULT_PORT, __version__, paths, service, system, uploads
from .jobs import QUEUE
from .lyrics import language_of, parse_lyrics
from .planner import make_blueprint
from .styles import INSTRUMENT_KW, MOODS, genre_list

MAX_UPLOAD = 200 * 2 ** 20
DEFAULT_ORIGINS = ["https://micow.vtvcab17.workers.dev", "https://bravinall.vtvcab17.workers.dev"]
mimetypes.add_type("text/javascript", ".js")
mimetypes.add_type("image/svg+xml", ".svg")
mimetypes.add_type("audio/wav", ".wav")
mimetypes.add_type("audio/midi", ".mid")
mimetypes.add_type("text/plain; charset=utf-8", ".lrc")
mimetypes.add_type("application/manifest+json", ".webmanifest")


def allowed_origin(origin: str) -> bool:
    if not origin:
        return True
    if re.fullmatch(r"https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?", origin):
        return True
    extra = system.settings().get("allowed_origins") or []
    return origin in DEFAULT_ORIGINS or origin in extra


class Handler(BaseHTTPRequestHandler):
    server_version = f"{APP_NAME}/{__version__}"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):  # yên lặng, trừ lỗi
        pass

    # ---------- tiện ích ----------
    def _cors(self):
        origin = self.headers.get("Origin", "")
        if origin and allowed_origin(origin):
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _json(self, data, code=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _err(self, msg, code=400):
        self._json({"error": msg}, code)

    def _body(self) -> bytes:
        n = int(self.headers.get("Content-Length") or 0)
        if n > MAX_UPLOAD:
            raise ValueError("Tệp quá lớn (tối đa 200 MB)")
        return self.rfile.read(n) if n else b""

    def _jbody(self) -> dict:
        b = self._body()
        return json.loads(b.decode("utf-8")) if b else {}

    def _file(self, path: Path, download: str | None = None):
        if not path.is_file():
            return self._err("Không thấy tệp", 404)
        size = path.stat().st_size
        ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        rng = self.headers.get("Range")
        start, end = 0, size - 1
        code = 200
        if rng:
            m = re.match(r"bytes=(\d*)-(\d*)", rng)
            if m:
                if m.group(1):
                    start = int(m.group(1))
                    end = int(m.group(2)) if m.group(2) else size - 1
                elif m.group(2):
                    start = max(0, size - int(m.group(2)))
                end = min(end, size - 1)
                code = 206
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(end - start + 1))
        if code == 206:
            self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        if download:
            q = urllib.parse.quote(download)
            self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{q}")
        self.send_header("Cache-Control", "no-cache" if path.suffix in (".html", ".js", ".css") else "max-age=60")
        self._cors()
        self.end_headers()
        if self.command == "HEAD":
            return
        with open(path, "rb") as f:
            f.seek(start)
            left = end - start + 1
            while left > 0:
                chunk = f.read(min(1 << 16, left))
                if not chunk:
                    break
                try:
                    self.wfile.write(chunk)
                except (BrokenPipeError, ConnectionResetError):
                    return
                left -= len(chunk)

    # ---------- định tuyến ----------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, PATCH, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Filename")
        self.send_header("Access-Control-Max-Age", "600")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_DELETE(self):
        self._dispatch("DELETE")

    def do_PATCH(self):
        self._dispatch("PATCH")

    def _dispatch(self, method: str):
        u = urllib.parse.urlparse(self.path)
        p = u.path
        q = urllib.parse.parse_qs(u.query)
        try:
            if p.startswith("/api/") and not allowed_origin(self.headers.get("Origin", "")):
                return self._err("Nguồn không được phép gọi Micow (thêm vào allowed_origins trong settings.json)", 403)
            if p.startswith("/api/"):
                return self._api(method, p[5:].strip("/"), q)
            if p.startswith("/files/") and method == "GET" or (p.startswith("/files/") and method == "HEAD"):
                parts = p[len("/files/"):].split("/", 1)
                if len(parts) != 2 or not re.fullmatch(r"[\w\-]+", parts[0]):
                    return self._err("Đường dẫn sai", 404)
                base = (paths.library() / parts[0]).resolve()
                f = (base / urllib.parse.unquote(parts[1])).resolve()
                if base not in f.parents:
                    return self._err("Đường dẫn sai", 404)
                dl = q.get("download", [None])[0]
                return self._file(f, dl)
            if method in ("GET", "HEAD"):
                rel = urllib.parse.unquote(p.lstrip("/")) or "index.html"
                root = paths.web_dir().resolve()
                f = (root / rel).resolve()
                if root != f and root not in f.parents:
                    return self._err("Không thấy", 404)
                if f.is_dir():
                    f = f / "index.html"
                return self._file(f)
            return self._err("Không hỗ trợ", 405)
        except (ValueError, KeyError, FileNotFoundError) as e:
            return self._err(str(e), 400)
        except Exception as e:  # noqa: BLE001
            traceback.print_exc()
            return self._err(f"Lỗi máy chủ: {e}", 500)

    def _api(self, method: str, route: str, q: dict):
        seg = route.split("/")
        if route == "health":
            return self._json({"app": APP_NAME, "version": __version__, "ok": True, "ecosystem": "Bravinall"})
        if route == "system":
            return self._json(system.info())
        if route == "settings":
            if method == "POST":
                return self._json(system.save_settings(self._jbody()))
            return self._json(system.settings())
        if route == "styles":
            return self._json({"genres": genre_list(), "moods": list(MOODS), "instruments": list(INSTRUMENT_KW)})
        if route == "engines":
            return self._json(service.engines_info())
        if seg[0] == "engines" and len(seg) == 3 and method == "POST":
            from .engines import get
            eng = get(seg[1])
            if seg[2] == "install":
                return self._json(service.start_install(seg[1], self._jbody()).to_dict())
            if seg[2] == "start" and hasattr(eng, "start"):
                job = QUEUE.submit("install", {"engine": seg[1], "action": "start"},
                                   lambda job: (eng.start(job=job), {"message": "Đã khởi động"})[1])
                return self._json(job.to_dict())
            if seg[2] == "stop" and hasattr(eng, "stop"):
                eng.stop()
                return self._json({"ok": True})
            return self._err("Không hỗ trợ", 404)
        if route == "plan" and method == "POST":
            b = self._jbody()
            ref = None
            for c in b.get("clips") or []:
                up = uploads.get_upload(c.get("id", ""))
                if up and c.get("use", "style") in ("style", "loop", "chop", "kit"):
                    ref = up.get("analysis")
                    break
            bp = make_blueprint(b.get("mode", "song"), b.get("style", ""), b.get("lyrics", ""), b.get("title", ""),
                                b.get("genre") or None, b.get("bpm") or None, b.get("key") or None,
                                b.get("duration") or None, None, int(b.get("seed") or 0), ref)
            d = bp.to_dict()
            d["language"] = language_of(b.get("lyrics", ""))
            d["lyric_sections"] = [s.to_dict() for s in parse_lyrics(b.get("lyrics", ""))]
            return self._json(d)
        if route == "upload" and method == "POST":
            name = self.headers.get("X-Filename") or q.get("name", ["clip.wav"])[0]
            name = urllib.parse.unquote(name)
            return self._json(uploads.add_upload(self._body(), name))
        if route == "uploads":
            return self._json(uploads.list_uploads())
        if seg[0] == "uploads" and len(seg) >= 2:
            if method == "DELETE":
                return self._json({"ok": uploads.delete_upload(seg[1])})
            if len(seg) == 3 and seg[2] == "audio":
                if not re.fullmatch(r"[\w\-]+", seg[1]):
                    return self._err("Sai mã", 404)
                return self._file(paths.uploads() / seg[1] / "clip.wav")
            m = uploads.get_upload(seg[1])
            if m:
                ear = paths.uploads() / seg[1] / "ear.json"
                if ear.exists():
                    m["ear"] = json.loads(ear.read_text(encoding="utf-8"))
            return self._json(m) if m else self._err("Không thấy clip", 404)
        if route == "generate" and method == "POST":
            return self._json(service.start_generate(self._jbody()).to_dict())
        if route == "capcut" and method == "POST":
            return self._json(service.start_cut(self._jbody()).to_dict())
        if route == "ear/listen" and method == "POST":
            ids = [i for i in (self._jbody().get("ids") or []) if re.fullmatch(r"[\w\-]+", str(i))]
            return self._json(service.start_listen(ids).to_dict())
        if route == "ear/label" and method == "POST":
            from .ear import save_label
            b = self._jbody()
            if not uploads.get_upload(b.get("id", "")):
                return self._err("Không thấy bài", 404)
            return self._json(save_label(b["id"], b["hook_start"], b["hook_end"], b.get("peak_start"), b.get("peak_end")))
        if route == "ear/report":
            from .ear.nn import WEIGHTS
            rp = WEIGHTS / "report.json"
            return self._json(json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {})
        if route == "jobs":
            return self._json(QUEUE.list())
        if seg[0] == "jobs" and len(seg) >= 2:
            job = QUEUE.get(seg[1])
            if not job:
                return self._err("Không thấy công việc", 404)
            if len(seg) == 3 and seg[2] == "cancel" and method == "POST":
                job.cancel.set()
                return self._json(job.to_dict())
            return self._json(job.to_dict())
        if route == "library":
            return self._json(service.library())
        if seg[0] == "library" and len(seg) >= 2:
            if method == "DELETE":
                return self._json({"ok": service.delete_item(seg[1])})
            if len(seg) == 3 and seg[2] == "rename" and method in ("POST", "PATCH"):
                m = service.rename_item(seg[1], self._jbody().get("title", ""))
                return self._json(m) if m else self._err("Không thấy bài", 404)
            if len(seg) == 3 and seg[2] == "zip":
                return self._zip(seg[1])
            m = service.library_item(seg[1])
            return self._json(m) if m else self._err("Không thấy bài", 404)
        return self._err("Không có API này", 404)

    def _zip(self, item_id: str):
        meta = service.library_item(item_id)
        if not meta:
            return self._err("Không thấy bài", 404)
        base = paths.library() / item_id
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            for f in base.rglob("*"):
                if f.is_file():
                    z.write(f, f.relative_to(base))
        data = buf.getvalue()
        name = re.sub(r"[^\w\- ]+", "", meta.get("title", "micow")).strip() or "micow"
        self.send_response(200)
        self.send_header("Content-Type", "application/zip")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Content-Disposition", f"attachment; filename*=UTF-8''{urllib.parse.quote(name)}.zip")
        self._cors()
        self.end_headers()
        self.wfile.write(data)


def make_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    srv = ThreadingHTTPServer((host, port), Handler)
    srv.daemon_threads = True
    return srv


def serve(host: str = "127.0.0.1", port: int = DEFAULT_PORT, open_browser: bool = False) -> None:
    srv = make_server(host, port)
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '') else host}:{port}/"
    print(f"♪ {APP_NAME} {__version__} – hệ sinh thái Bravinall")
    print(f"  Giao diện: {url}")
    print(f"  Dữ liệu:   {paths.home()}")
    if host in ("0.0.0.0", ""):
        print("  Đang mở cho mạng LAN – chỉ dùng trong mạng tin cậy.")
    print("  Nhấn Ctrl+C để dừng.")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nĐã dừng Micow.")
    finally:
        try:
            from .engines.acestep import AceStepEngine
            AceStepEngine().stop()
        except Exception:
            pass
        srv.server_close()
