"""Проверка GitHub Actions и развёртывание одного проверенного коммита."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

REPO = "crvstxllize/Task-Manager"
PROJECT = "devops-task-manager"
VOLUME = PROJECT + "_sqlite-data"
APP = "http://127.0.0.1:5000"
ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ("ci.yml", "docker-test.yml")


def read_json(url, headers=None, timeout=8):
    with urlopen(Request(url, headers=headers or {}), timeout=timeout) as response:
        return json.load(response)


def github(path):
    headers = {"Accept": "application/vnd.github+json"}
    if token := os.getenv("GITHUB_TOKEN"):
        headers["Authorization"] = f"Bearer {token}"
    return read_json(f"https://api.github.com/repos/{REPO}/{path}", headers)


def valid_sha(sha):
    if not re.fullmatch("[0-9a-f]{40}", sha):
        raise ValueError("Ожидался полный SHA коммита")
    return sha


def head():
    return valid_sha(github("git/ref/heads/main")["object"]["sha"])


def verdict(runs, sha):
    eligible = [
        run
        for run in runs
        if run["head_sha"] == sha
        and run["event"] == "push"
        and run["head_branch"] == "main"
        and run["head_repository"]
        and run["head_repository"]["full_name"] == REPO
    ]
    if not eligible:
        return "ожидание"
    run = max(eligible, key=lambda r: (r["run_number"], r["run_attempt"]))
    if run["status"] != "completed":
        return "в процессе"
    return "успешно" if run["conclusion"] == "success" else "ошибка"


def checks(sha):
    query = urlencode({"event": "push", "branch": "main", "head_sha": valid_sha(sha)})
    return {
        name: verdict(github(f"actions/workflows/{name}/runs?{query}")["workflow_runs"], sha)
        for name in WORKFLOWS
    }


def approved(states):
    return all(states.get(name) == "успешно" for name in WORKFLOWS)


def application():
    if read_json(APP + "/health", timeout=2) != {"status": "ok"}:
        raise RuntimeError("Ошибка /health")
    return read_json(APP + "/version", timeout=2)


def output(*args):
    return subprocess.check_output(args, text=True, timeout=30, stderr=subprocess.DEVNULL).strip()


def target():
    labels = json.loads(output("docker", "volume", "inspect", VOLUME))[0]["Labels"]
    if (
        labels.get("com.docker.compose.project") != PROJECT
        or labels.get("com.docker.compose.volume") != "sqlite-data"
    ):
        raise RuntimeError("Не совпадают метки существующего тома SQLite")
    ids = output(
        "docker",
        "ps",
        "-aq",
        "--filter",
        f"label=com.docker.compose.project={PROJECT}",
        "--filter",
        "label=com.docker.compose.service=web",
    ).split()
    for cid in ids:
        info = json.loads(output("docker", "inspect", cid))[0]
        mounts = [m for m in info["Mounts"] if m["Destination"] == "/data"]
        ports = info["HostConfig"]["PortBindings"]
        if (
            len(ids) != 1
            or len(mounts) != 1
            or mounts[0].get("Name") != VOLUME
            or ports != {"5000/tcp": [{"HostIp": "127.0.0.1", "HostPort": "5000"}]}
        ):
            raise RuntimeError("Порт или том существующего web-контейнера не совпадает")
    return ids[0] if ids else "отсутствует"


def deploy(sha, stage, log):
    stage("Проверка CI")
    if not approved(checks(sha)):
        raise RuntimeError("Для SHA требуются две успешные проверки push в main")
    # Do not pass credentials or Compose overrides from the panel to child processes.
    env = {k: os.environ[k] for k in ("HOME", "PATH", "TMPDIR", "LANG") if k in os.environ}
    env.update(GIT_SHA=sha, TASK_MANAGER_PORT="5000", GIT_TERMINAL_PROMPT="0")
    with tempfile.TemporaryDirectory(prefix="task-manager-release-") as folder:

        def run(*cmd):
            with subprocess.Popen(
                cmd,
                cwd=folder,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            ) as process:
                for line in process.stdout:
                    log(line.rstrip())
                if process.wait():
                    raise RuntimeError(f"{cmd[0]} завершился с кодом {process.returncode}")

        stage("Получение исходников")
        run(
            "git",
            "clone",
            "--quiet",
            "--single-branch",
            "--branch",
            "main",
            f"https://github.com/{REPO}.git",
            ".",
        )
        run("git", "merge-base", "--is-ancestor", sha, "origin/main")
        run("git", "checkout", "--quiet", "--detach", sha)
        compose = ["docker", "compose", "-p", PROJECT, "-f", "compose.yaml"]
        config = json.loads(
            subprocess.check_output(
                [*compose, "config", "--format", "json"], cwd=folder, env=env, text=True
            )
        )
        web = config["services"]["web"]
        if (
            [(p.get("host_ip"), str(p["published"]), p["target"]) for p in web["ports"]]
            != [("127.0.0.1", "5000", 5000)]
            or [(v["type"], v["source"], v["target"]) for v in web["volumes"]]
            != [("volume", "sqlite-data", "/data")]
            or config["volumes"]["sqlite-data"]["name"] != VOLUME
        ):
            raise RuntimeError("Конфигурация коммита не соответствует локальному порту и тому")
        log(f"До обновления: {target()}; том {VOLUME}")
        stage("Сборка образа")
        run(*compose, "--progress", "plain", "build", "web")
        target()
        stage("Обновление контейнера")
        run(
            *compose,
            "up",
            "-d",
            "--no-deps",
            "--no-build",
            "--pull",
            "never",
            "--wait",
            "--wait-timeout",
            "90",
            "web",
        )
        stage("Проверка приложения")
        run(
            sys.executable,
            str(ROOT / "scripts/healthcheck.py"),
            "--url",
            APP,
            "--expected-sha",
            sha,
        )
        log(f"После обновления: {target()}; том {VOLUME}")
