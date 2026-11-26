"""Запуск локального HTTP-сервера панели на macOS."""

import argparse
import fcntl
import json
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import deploy
from .service import Service

UI = Path(__file__).parent / "ui"
ADDRESS = "127.0.0.1:8000"


class Handler(BaseHTTPRequestHandler):
    def reply(self, content, mime="application/json", status=200):
        body = content if isinstance(content, bytes) else json.dumps(content).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header(
            "Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        )
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") != ADDRESS:
            return self.send_error(403)
        files = {
            "/": (UI / "index.html", "text/html; charset=utf-8"),
            "/deploy-icon.png": (UI / "deploy-icon.png", "image/png"),
            "/deploy-mark.svg": (UI / "deploy-mark.svg", "image/svg+xml"),
            "/theme.js": (deploy.ROOT / "static/theme.js", "application/javascript"),
            "/panel.js": (UI / "panel.js", "application/javascript"),
            "/panel.css": (UI / "panel.css", "text/css"),
            "/style.css": (deploy.ROOT / "static/style.css", "text/css"),
        }
        if self.path in files:
            file, mime = files[self.path]
            return self.reply(file.read_bytes(), mime)
        service = self.server.service
        if self.path == "/api/state":
            try:
                app = deploy.application()
            except (OSError, ValueError, RuntimeError):
                app = None
            return self.reply(
                {
                    "app": app,
                    "ci": service.ci,
                    "runs": service.history(),
                    "manual_sha": service.manual_sha,
                }
            )
        if match := re.fullmatch(r"/api/runs/(\d+)/log", self.path):
            return self.reply({"log": service.log(int(match[1]))})
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/deploy":
            return self.send_error(404)
        if (
            self.headers.get("Host") != ADDRESS
            or self.headers.get("Origin") != "http://" + ADDRESS
            or self.headers.get("X-Panel-Action") != "deploy"
        ):
            return self.send_error(403)
        try:
            number = self.server.service.manual()
        except (OSError, ValueError, RuntimeError) as exc:
            return self.reply({"error": str(exc)}, status=503)
        self.reply({"id": number}, status=202)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--manual-sha",
        type=deploy.valid_sha,
        help="Проверенный исторический коммит main для ручной демонстрации",
    )
    parser.add_argument("--poll-seconds", type=int, default=240)
    args = parser.parse_args()
    if args.poll_seconds < 30:
        parser.error("Интервал опроса должен быть не меньше 30 секунд")
    state = deploy.ROOT / "instance" / "deployment"
    state.mkdir(parents=True, exist_ok=True)
    with (state / "worker.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with ThreadingHTTPServer(("127.0.0.1", 8000), Handler) as server:
            server.service = Service(state, args.manual_sha, args.poll_seconds)
            server.service.start()
            print("Панель готова · http://" + ADDRESS, flush=True)
            server.serve_forever()


if __name__ == "__main__":
    main()
