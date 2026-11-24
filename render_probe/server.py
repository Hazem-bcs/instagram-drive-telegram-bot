"""Bounded startup test of one public video; no credentials or download endpoint."""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

result = {"status": "pending"}
VIDEO = "https://www.youtube.com/watch?v=nYYitW53CXI"


def probe():
    started = time.monotonic()
    try:
        import imageio_ffmpeg
        with tempfile.TemporaryDirectory() as directory:
            proc = subprocess.run(
                [sys.executable, "-m", "yt_dlp", "--ignore-config", "--no-playlist",
                 "--socket-timeout", "15", "--retries", "0", "--fragment-retries", "0",
                 "--max-filesize", "25M", "--no-progress", "--ffmpeg-location",
                 imageio_ffmpeg.get_ffmpeg_exe(), "--merge-output-format", "mp4",
                 "-f", "bv[ext=mp4][height<=360][filesize<15M]+ba[ext=m4a][filesize<10M]/b[ext=mp4][height<=360][filesize<25M]",
                 "-o", str(pathlib.Path(directory) / "sample.%(ext)s"), VIDEO],
                capture_output=True, text=True, timeout=150)
            file = pathlib.Path(directory) / "sample.mp4"
            if proc.returncode == 0 and file.is_file() and file.stat().st_size > 0:
                result.update(status="success", bytes=file.stat().st_size)
            else:
                error = (proc.stdout + proc.stderr).lower()
                category = ("sign_in_required" if any(s in error for s in ("sign in", "not a bot", "bot verification"))
                            else "format_unavailable" if "requested format" in error
                            else "upstream_rejected" if "403" in error or "429" in error
                            else "download_failed")
                result.update(status="failed", reason=category)
    except subprocess.TimeoutExpired:
        result.update(status="failed", reason="timeout")
    except Exception:
        result.update(status="failed", reason="internal_error")
    finally:
        result["seconds"] = round(time.monotonic() - started, 2)
        print("RENDER_PROBE " + json.dumps(result), flush=True)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path not in ("/", "/health"):
            self.send_error(404)
            return
        data = json.dumps({"service": "render-probe", **result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


if __name__ == "__main__":
    server = ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "10000"))), Handler)
    threading.Thread(target=probe, daemon=True).start()
    server.serve_forever()
