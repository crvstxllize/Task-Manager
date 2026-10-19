"""Временное развёртывание ZIP в чистой среде и HTTP-проверка с очисткой процесса."""

import argparse
import os
import subprocess
import sys
import venv
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile


def environment_python(deployment):
    return deployment / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def prepare(archive_path, deployment):
    if deployment.exists() and any(deployment.iterdir()):
        raise ValueError(f"Deployment directory must be empty: {deployment}")
    deployment.mkdir(parents=True, exist_ok=True)
    with ZipFile(archive_path) as archive:
        for entry in archive.infolist():
            destination = (deployment / entry.filename).resolve()
            if not destination.is_relative_to(deployment.resolve()):
                raise ValueError("Unsafe path in archive")
        archive.extractall(deployment)

    # Новая среда доказывает, что requirements.txt достаточно для запуска.
    venv.EnvBuilder(with_pip=True).create(deployment / ".venv")
    subprocess.run(
        [
            str(environment_python(deployment)),
            "-m",
            "pip",
            "install",
            "-r",
            str(deployment / "requirements.txt"),
        ],
        check=True,
        timeout=180,
    )
    print(f"Deploy to Test: artifact unpacked, clean runtime ready at {deployment}", flush=True)


def check(deployment, port):
    python = environment_python(deployment)
    environment = os.environ.copy()
    environment.update(
        DATABASE_PATH=str(deployment / "instance" / "smoke.sqlite3"),
        FLASK_DEBUG="0",
        PYTHONUNBUFFERED="1",
    )
    environment.pop("PYTHONPATH", None)
    log_path = deployment / "server.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                str(python),
                "-m",
                "flask",
                "--app",
                "app:create_app",
                "--no-debug",
                "run",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--no-reload",
            ],
            cwd=deployment,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        print(f"Test server PID: {process.pid}; URL: http://127.0.0.1:{port}", flush=True)
        try:
            subprocess.run(
                [
                    str(python),
                    str(deployment / "scripts" / "healthcheck.py"),
                    "--url",
                    f"http://127.0.0.1:{port}",
                    "--crud",
                ],
                cwd=deployment,
                env=environment,
                check=True,
                timeout=45,
            )
            if process.poll() is not None:
                raise RuntimeError("Server exited during healthcheck")
        except Exception:
            log.flush()
            print(log_path.read_text(encoding="utf-8"), file=sys.stderr)
            raise
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
            print("Test server stopped.", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    all_parser = commands.add_parser("all", help="Temporary unpack, install, start and check")
    all_parser.add_argument("archive", type=Path)
    all_parser.add_argument("--port", type=int, default=5055)
    prepare_parser = commands.add_parser("prepare", help="Unpack ZIP and install runtime")
    prepare_parser.add_argument("archive", type=Path)
    prepare_parser.add_argument("--directory", type=Path, required=True)
    check_parser = commands.add_parser("check", help="Start and verify prepared app, then stop")
    check_parser.add_argument("--directory", type=Path, required=True)
    check_parser.add_argument("--port", type=int, default=5055)
    arguments = parser.parse_args()
    if arguments.command == "all":
        with TemporaryDirectory(prefix="devops-deploy-") as directory:
            deployment = Path(directory)
            prepare(arguments.archive.resolve(), deployment)
            check(deployment, arguments.port)
        print("Temporary deployment directory removed.", flush=True)
    elif arguments.command == "prepare":
        prepare(arguments.archive.resolve(), arguments.directory.resolve())
    else:
        check(arguments.directory.resolve(), arguments.port)


if __name__ == "__main__":
    main()
