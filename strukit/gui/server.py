"""The StruKit window: a small web server on this computer only (127.0.0.1) and a page
that Edge shows as an app window. Nothing is sent anywhere else.

    python -m strukit.gui                  open the StruKit window
    python -m strukit.gui --serve          server only; the address is printed
    python -m strukit.gui --port N         another port (default 8775, then any free port)
    python -m strukit.gui --open <file>    open this project (.strukit)

While a server runs its address is in %LOCALAPPDATA%/strukit/server.json.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .. import __version__, loadcombos, shapes
from . import calc

APP_DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home() / ".local" / "share") / "strukit"
SERVER_JSON = APP_DIR / "server.json"
SETTINGS = APP_DIR / "settings.json"
STATIC = Path(__file__).parent / "static"
FONTS = Path(__file__).parent.parent / "data" / "fonts"
TYPES = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".ttf": "font/ttf", ".svg": "image/svg+xml", ".ico": "image/x-icon"}
_last_ping = [time.time()]
_pinged = [False]
IDLE_S = 180


def load_settings():
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(s):
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(s, indent=1), encoding="utf-8")
    except OSError:
        pass


def remember(path):
    s = load_settings()
    rec = [p for p in s.get("recent", []) if p != path]
    s["recent"] = [path] + rec[:9]
    s["last_dir"] = str(Path(path).parent)
    save_settings(s)


def _file_dialog(save, title, initial_name="", filt_text="StruKit project (*.strukit)\0*.strukit\0All files\0*.*\0\0",
                 def_ext="strukit"):
    """The standard Windows Open / Save window. None when cancelled or not on Windows."""
    if os.name != "nt":
        return None
    import ctypes
    from ctypes import wintypes

    class OFN(ctypes.Structure):
        _fields_ = [("lStructSize", wintypes.DWORD), ("hwndOwner", wintypes.HWND),
                    ("hInstance", wintypes.HINSTANCE), ("lpstrFilter", ctypes.c_void_p),
                    ("lpstrCustomFilter", ctypes.c_void_p), ("nMaxCustFilter", wintypes.DWORD),
                    ("nFilterIndex", wintypes.DWORD), ("lpstrFile", ctypes.c_void_p),
                    ("nMaxFile", wintypes.DWORD), ("lpstrFileTitle", ctypes.c_void_p),
                    ("nMaxFileTitle", wintypes.DWORD), ("lpstrInitialDir", ctypes.c_void_p),
                    ("lpstrTitle", ctypes.c_void_p), ("Flags", wintypes.DWORD),
                    ("nFileOffset", wintypes.WORD), ("nFileExtension", wintypes.WORD),
                    ("lpstrDefExt", ctypes.c_void_p), ("lCustData", wintypes.LPARAM),
                    ("lpfnHook", ctypes.c_void_p), ("lpTemplateName", ctypes.c_void_p),
                    ("pvReserved", ctypes.c_void_p), ("dwReserved", wintypes.DWORD),
                    ("FlagsEx", wintypes.DWORD)]

    filt = ctypes.create_unicode_buffer(filt_text, 256)
    out = ctypes.create_unicode_buffer(initial_name, 2048)
    start = ctypes.create_unicode_buffer(load_settings().get("last_dir") or str(Path.home() / "Documents"))
    ttl = ctypes.create_unicode_buffer(title)
    ext = ctypes.create_unicode_buffer(def_ext)
    ofn = OFN()
    ofn.lStructSize = ctypes.sizeof(OFN)
    ofn.hwndOwner = ctypes.windll.user32.GetForegroundWindow()
    ofn.lpstrFilter = ctypes.addressof(filt)
    ofn.nFilterIndex = 1
    ofn.lpstrFile = ctypes.addressof(out)
    ofn.nMaxFile = len(out)
    ofn.lpstrInitialDir = ctypes.addressof(start)
    ofn.lpstrTitle = ctypes.addressof(ttl)
    ofn.lpstrDefExt = ctypes.addressof(ext)
    if save:
        ofn.Flags = 0x00080000 | 0x00000002 | 0x00000800 | 0x00000008
        ok = ctypes.windll.comdlg32.GetSaveFileNameW(ctypes.byref(ofn))
    else:
        ofn.Flags = 0x00080000 | 0x00001000 | 0x00000800 | 0x00000008
        ok = ctypes.windll.comdlg32.GetOpenFileNameW(ctypes.byref(ofn))
    return out.value if ok else None


def _write_project(path, data):
    """Written to a temporary name and then renamed, so a failed save never damages the file."""
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    remember(str(p))


_pdfs = {}


def api(path, body):
    if path == "/api/info":
        return dict(version=__version__, forms=calc.FORMS, shapes=shapes.labels(),
                    recent=[p for p in load_settings().get("recent", []) if os.path.exists(p)],
                    today=time.strftime("%Y-%m-%d"), combo_sets=loadcombos.SETS)
    if path == "/api/seismic_combos":
        try:
            sds, rho = float(str(body.get("sds", "")).strip()), float(str(body.get("rho", "") or "1.0").strip())
            return loadcombos.seismic(sds, rho, ev=not body.get("no_ev"))
        except ValueError as e:
            msg = str(e)
            return dict(error=msg if msg.startswith(("SDS", "the redundancy")) else "Type SDS as a number, and the redundancy factor as 1.0 or 1.3.")
    if path == "/api/ping":
        _last_ping[0] = time.time(); _pinged[0] = True
        return {}
    if path == "/api/calc":
        return calc.results(body["kind"], body.get("values") or {}, body.get("project") or {})
    if path == "/api/reactions":
        return calc.reactions(body["kind"], body.get("values") or {}, body.get("project") or {})
    if path == "/api/calc_all":
        proj = body.get("project") or {}
        return dict(results=[calc.results(m["kind"], m.get("values") or {}, proj) for m in body.get("members") or []])
    if path in ("/api/pdf", "/api/package"):
        fd, tmp = tempfile.mkstemp(suffix=".pdf", prefix="strukit-")
        os.close(fd)
        extra = {}
        if path == "/api/pdf":
            calc.sheet_pdf(body["kind"], body.get("values") or {}, body.get("project") or {}, tmp)
        else:
            n, skipped = calc.package_pdf(body.get("project") or {}, body.get("members") or [], tmp)
            extra = dict(sheets=n, skipped=skipped)
        token = f"{int(time.time() * 1000):x}"
        _pdfs[token] = tmp
        return dict(url=f"/pdf/{token}.pdf", **extra)
    if path == "/api/open":
        p = body.get("path") or _file_dialog(False, "Open a StruKit project")
        if not p:
            return dict(cancelled=True)
        data = json.loads(Path(p).read_text(encoding="utf-8"))
        if data.get("format") != "strukit-project":
            raise ValueError("that file is not a StruKit project")
        remember(p)
        return dict(path=p, data=data)
    if path == "/api/save":
        p = body.get("path")
        if not p or body.get("as"):
            p = _file_dialog(True, "Save the StruKit project", body.get("suggest") or "")
            if not p:
                if os.name != "nt" and body.get("path"):
                    p = body["path"]
                else:
                    return dict(cancelled=True)
        _write_project(p, body["data"])
        return dict(path=p)
    raise ValueError(f"unknown request {path}")


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, data, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        if path.startswith("/pdf/"):
            f = _pdfs.get(path[5:-4])
            if f and os.path.exists(f):
                return self._send(200, Path(f).read_bytes(), "application/pdf")
            return self._send(404, b"not found", "text/plain")
        if path.startswith("/fonts/"):
            f = FONTS / Path(path).name
        else:
            f = STATIC / ("index.html" if path in ("/", "") else Path(path).name)
        if f.is_file():
            return self._send(200, f.read_bytes(), TYPES.get(f.suffix, "application/octet-stream"))
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            n = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(n) or b"{}")
            out = api(path, body)
            self._send(200, json.dumps(out).encode(), "application/json")
        except Exception as e:                              # shown on the screen, never a silent failure
            traceback.print_exc()
            self._send(200, json.dumps(dict(error=str(e) or type(e).__name__)).encode(), "application/json")


def _edge():
    for base in (os.environ.get("ProgramFiles(x86)"), os.environ.get("ProgramFiles"), os.environ.get("LOCALAPPDATA")):
        if base:
            p = Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe"
            if p.is_file():
                return str(p)
    return None


def open_window(url):
    edge = _edge()
    if edge:
        subprocess.Popen([edge, f"--app={url}", "--window-size=1440,920"],
                         creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    else:
        import webbrowser
        webbrowser.open(url)


def _running_at(port):
    try:
        import urllib.request
        req = urllib.request.Request(f"http://127.0.0.1:{port}/api/info", data=b"{}", method="POST")
        with urllib.request.urlopen(req, timeout=1.5) as r:
            return json.loads(r.read()).get("version")
    except Exception:
        return None


def _free_port(first):
    for port in [first] + list(range(first + 1, first + 20)):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _watchdog(server):
    """Closing the window ends the program: the page pings every few seconds."""
    while True:
        time.sleep(2.0)
        idle = time.time() - _last_ping[0]
        if (_pinged[0] and idle > IDLE_S) or (not _pinged[0] and idle > 120):
            server.shutdown()
            return


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if sys.stderr is None or sys.stdout is None:            # pythonw has no console: keep a log instead
        APP_DIR.mkdir(parents=True, exist_ok=True)
        sys.stdout = sys.stderr = open(APP_DIR / "strukit.log", "a", encoding="utf-8", buffering=1)
    serve_only = "--serve" in argv
    want = int(argv[argv.index("--port") + 1]) if "--port" in argv and argv.index("--port") + 1 < len(argv) else 8775
    query = ""
    if "--open" in argv and argv.index("--open") + 1 < len(argv):
        query = "?open=" + urllib.parse.quote(argv[argv.index("--open") + 1])
    if _running_at(want) == __version__:                    # this build is already open: another window on it
        url = f"http://127.0.0.1:{want}/"
        print(f"{url} (already running)", flush=True)
        if not serve_only:
            open_window(url + query)
        return
    port = _free_port(want)
    url = f"http://127.0.0.1:{port}/"
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    try:
        APP_DIR.mkdir(parents=True, exist_ok=True)
        SERVER_JSON.write_text(json.dumps(dict(url=url, pid=os.getpid(), version=__version__,
                                               started=time.strftime("%Y-%m-%d %H:%M:%S"))), encoding="utf-8")
    except OSError:
        pass
    try:
        if serve_only:
            print(url, flush=True)
        else:
            threading.Thread(target=_watchdog, args=(server,), daemon=True).start()
            open_window(url + query)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    finally:
        try:
            SERVER_JSON.unlink()
        except OSError:
            pass
        for f in _pdfs.values():
            try:
                os.remove(f)
            except OSError:
                pass


if __name__ == "__main__":
    main()
