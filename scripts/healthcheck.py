"""Проверить готовность сервиса и, при --crud, полный цикл задач через HTTP."""

import argparse
import json
import re
import time
from html import escape
from http.cookiejar import CookieJar
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


class TaskSession:
    """Interact with the same forms and session cookie as a browser."""

    def __init__(self, url):
        self.url = url
        self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
        token = re.search(r'name="csrf_token" value="([^"]+)"', self.page())
        if not token:
            raise RuntimeError("CSRF token missing from rendered form")
        self.token = token[1]

    def page(self):
        with self.opener.open(f"{self.url}/", timeout=5) as response:
            return response.read().decode("utf-8")

    def post(self, path, **fields):
        data = urlencode({"csrf_token": self.token, **fields}).encode()
        with self.opener.open(Request(f"{self.url}{path}", data=data), timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP action failed: {response.status}")

    def task(self, title):
        html = self.page()
        item = f'<span class="task-title">{escape(title)}</span>'
        matches = [
            (classes, row)
            for classes, row in re.findall(
                r'<li class="(task-row[^"]*)"[^>]*>(.*?)</li>', html, re.S
            )
            if item in row
        ]
        if len(matches) != 1:
            raise RuntimeError(f"Expected one rendered task named {title!r}, got {len(matches)}")
        classes, row = matches[0]
        task_id = re.search(r'action="/tasks/(\d+)/toggle"', row)
        if not task_id:
            raise RuntimeError("Rendered task has no toggle action")
        completed = "is-complete" in classes.split()
        label = re.search(r">\s*(В работе|Готово|Завершена)\s*<", row)
        if not label or completed != (label[1] != "В работе"):
            raise RuntimeError("Rendered task status does not match its completion state")
        return task_id[1], completed, label[1]


def check_service(url, timeout=30, crud=False, expected_sha=None):
    opener = build_opener()
    deadline = time.monotonic() + timeout
    last_error = None
    while time.monotonic() < deadline:
        try:
            with opener.open(f"{url}/health", timeout=2) as response:
                payload = json.load(response)
                if response.status != 200 or payload != {"status": "ok"}:
                    raise ValueError(f"Unexpected health response: {response.status} {payload}")
            print('Healthcheck passed: HTTP 200 {"status":"ok"}', flush=True)
            break
        except (OSError, URLError, ValueError) as error:
            last_error = error
            time.sleep(0.3)
    else:
        raise RuntimeError(f"Service not ready after {timeout}s: {last_error}")

    if expected_sha:
        with opener.open(f"{url}/version", timeout=5) as response:
            revision = json.load(response)["git_sha"]
            if response.status != 200 or revision != expected_sha:
                raise RuntimeError(f"Expected revision {expected_sha}, got {revision}")
        print(f"Verified /version: {revision}", flush=True)

    if not crud:
        return

    session = TaskSession(url)
    title = f"HTTP smoke task {time.time_ns()}"
    session.post("/tasks", title=title)
    task_id, completed, _ = session.task(title)
    print(f"Verified created task on a fresh GET /: {title}", flush=True)
    try:
        if completed:
            raise RuntimeError("New task unexpectedly completed")
        for completed in (True, False):
            session.post(f"/tasks/{task_id}/toggle")
            if session.task(title)[:2] != (task_id, completed):
                raise RuntimeError("Task status was not persisted in rendered page")
    finally:
        session.post(f"/tasks/{task_id}/delete")
    if title in session.page():
        raise RuntimeError("Deleted task still visible")
    print("HTTP CRUD passed: create -> complete -> reopen -> delete.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--crud", action="store_true")
    parser.add_argument("--expected-sha")
    arguments = parser.parse_args()
    check_service(
        arguments.url.rstrip("/"), arguments.timeout, arguments.crud, arguments.expected_sha
    )
