"""Build and deploy two Git revisions against one disposable SQLite volume."""

import argparse
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
from zipfile import ZipFile

from healthcheck import TaskSession, check_service

ROOT = Path(__file__).resolve().parents[1]


def run(*args, env=None, capture=False):
    return subprocess.run(
        args, cwd=ROOT, env=env, check=True, text=True, stdout=subprocess.PIPE if capture else None
    ).stdout


def verify_upgrade(old_ref, new_ref):
    old_sha = run("git", "rev-parse", "--verify", f"{old_ref}^{{commit}}", capture=True).strip()
    new_sha = run("git", "rev-parse", "--verify", f"{new_ref}^{{commit}}", capture=True).strip()
    if old_sha == new_sha:
        raise ValueError("Upgrade requires two different Git commits")

    project = f"upgrade-{uuid4().hex}"
    images = []
    with TemporaryDirectory(prefix="task-manager-upgrade-") as temp:
        directory = Path(temp)
        override = directory / "image.yaml"
        override.write_text('services:\n  web:\n    image: "${UPGRADE_IMAGE}"\n', encoding="utf-8")

        def compose(file, env, *args, capture=False):
            return run(
                "docker",
                "compose",
                "-p",
                project,
                "-f",
                str(file),
                "-f",
                str(override),
                *args,
                env=env,
                capture=capture,
            )

        def build(sha):
            archive = directory / f"{sha}.zip"
            run("git", "archive", "--format=zip", "-o", str(archive), sha)
            source = directory / sha
            with ZipFile(archive) as files:
                files.extractall(source)
            image = f"task-manager-{project}:{sha}"
            env = {**os.environ, "GIT_SHA": sha, "TASK_MANAGER_PORT": "0", "UPGRADE_IMAGE": image}
            compose(source / "compose.yaml", env, "build", "web")
            images.append(image)
            return source / "compose.yaml", env

        def deploy(file, env, sha):
            compose(
                file,
                env,
                "up",
                "-d",
                "--no-build",
                "--pull",
                "never",
                "--wait",
                "--wait-timeout",
                "90",
                "web",
            )
            container_id = compose(file, env, "ps", "-q", "web", capture=True).strip()
            details = json.loads(run("docker", "inspect", container_id, capture=True))[0]
            volume = next(mount for mount in details["Mounts"] if mount["Destination"] == "/data")
            if details["Id"] != container_id or details["State"]["Health"]["Status"] != "healthy":
                raise RuntimeError("Expected a healthy replacement container")
            if volume["Type"] != "volume" or volume["Name"] != f"{project}_sqlite-data":
                raise RuntimeError("Expected this run's named SQLite volume")
            port = compose(file, env, "port", "web", "5000", capture=True).strip()
            host, _, number = port.rpartition(":")
            if host != "127.0.0.1" or not number.isdecimal():
                raise RuntimeError(f"Unexpected test binding: {port}")
            url = f"http://{port}"
            check_service(url, expected_sha=sha)
            return container_id, volume["Name"], url

        deployment = None
        try:
            _, old_env = build(old_sha)
            new_file, new_env = build(new_sha)
            # Use the same deployment definition and volume throughout the upgrade.
            deployment = (new_file, old_env)
            old_id, old_volume, old_url = deploy(new_file, old_env, old_sha)
            session = TaskSession(old_url)
            title = f"Upgrade persistence {project}"
            session.post("/tasks", title=title)
            task_id, completed, _ = session.task(title)
            if completed:
                raise RuntimeError("New task unexpectedly completed")
            session.post(f"/tasks/{task_id}/toggle")
            before_id, before_completed, before_status = session.task(title)
            if before_id != task_id or not before_completed:
                raise RuntimeError("Old deployment did not mark the task as completed")
            before = (
                f"Before upgrade: SHA={old_sha} container={old_id} "
                f"volume={old_volume} task_id={task_id} status={before_status}"
            )
            print(before, flush=True)

            deployment = (new_file, new_env)
            new_id, new_volume, new_url = deploy(new_file, new_env, new_sha)
            after_id, after_completed, after_status = TaskSession(new_url).task(title)
            after = (
                f"After upgrade: SHA={new_sha} container={new_id} "
                f"volume={new_volume} task_id={after_id} status={after_status}"
            )
            print(after, flush=True)
            if new_id == old_id or new_volume != old_volume:
                raise RuntimeError("Upgrade must replace the container and retain the volume")
            if after_id != task_id or not after_completed or after_status != "Завершена":
                raise RuntimeError("Upgrade did not retain the completed task")
            result = (
                f"Upgrade preserved task_id={task_id} status={after_status} "
                f"on the same SQLite volume {new_volume}"
            )
            print(result, flush=True)
        except Exception:
            if deployment:
                compose(*deployment, "logs", "--no-color", "web")
            raise
        finally:
            try:
                if deployment:
                    compose(*deployment, "down", "--volumes")
            finally:
                if images:
                    run("docker", "image", "rm", *images)

    if summary := os.environ.get("GITHUB_STEP_SUMMARY"):
        with Path(summary).open("a", encoding="utf-8") as output:
            output.write(
                f"## Verify upgrade preserves tasks\n\n```text\n{before}\n{after}\n{result}\n```\n"
            )
        print(
            "::notice title=Verify upgrade preserves tasks::" + "%0A".join((before, after, result)),
            flush=True,
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old_revision")
    parser.add_argument("new_revision")
    arguments = parser.parse_args()
    verify_upgrade(arguments.old_revision, arguments.new_revision)
