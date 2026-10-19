"""Проверить готовность сервиса и, при --crud, полный цикл задач через HTTP."""

import argparse
import json
import re
import time
from http.cookiejar import CookieJar
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener


def check_service(url, timeout=30, crud=False):
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
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

    if not crud:
        return

    def page():
        with opener.open(f"{url}/", timeout=5) as response:
            return response.read().decode("utf-8")

    def post(path, data):
        encoded = urlencode(data).encode("utf-8")
        with opener.open(Request(f"{url}{path}", data=encoded), timeout=5) as response:
            if response.status != 200:
                raise RuntimeError(f"HTTP action failed: {response.status}")
            return response.read().decode("utf-8")

    html = page()
    token_match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    if not token_match:
        raise RuntimeError("CSRF token missing from rendered form")
    token = token_match[1]
    title = f"HTTP smoke task {time.time_ns()}"
    html = post("/tasks", {"title": title, "csrf_token": token})
    if title not in html:
        raise RuntimeError("Created task not visible")
    # Новая активная задача находится первой по принятому порядку сортировки.
    task_match = re.search(r'action="/tasks/(\d+)/toggle"', html)
    if not task_match:
        raise RuntimeError("Created task has no toggle action")
    task_id = task_match[1]
    try:
        for completed in (True, False):
            html = post(f"/tasks/{task_id}/toggle", {"csrf_token": token})
            row = next(
                (
                    row
                    for row in re.findall(r'<li class="task-row.*?</li>', html, re.S)
                    if title in row
                ),
                "",
            )
            if not row or ('class="task-row is-complete"' in row) != completed:
                raise RuntimeError("Task status was not persisted in rendered page")
    finally:
        html = post(f"/tasks/{task_id}/delete", {"csrf_token": token})
    if title in html:
        raise RuntimeError("Deleted task still visible")
    print("HTTP CRUD passed: create -> complete -> reopen -> delete.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--timeout", type=float, default=30)
    parser.add_argument("--crud", action="store_true")
    arguments = parser.parse_args()
    check_service(arguments.url.rstrip("/"), arguments.timeout, arguments.crud)
