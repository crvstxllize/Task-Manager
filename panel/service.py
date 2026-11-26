"""Последовательная очередь и журнал, сохраняемые между запусками панели."""

import sqlite3
import threading
from contextlib import contextmanager
from time import gmtime, strftime

from . import deploy


def stamp():
    return strftime("%Y-%m-%dT%H:%M:%SZ", gmtime())


class Service:
    def __init__(self, directory, manual_sha=None, interval=240):
        directory.mkdir(exist_ok=True, parents=True)
        self.db = directory / "panel.sqlite3"
        self.manual_sha = manual_sha
        self.interval = interval
        self.wake = threading.Event()
        self.ci = {"message": "Подключение к GitHub"}
        with self.connection() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS runs (
                    id INTEGER PRIMARY KEY, sha TEXT, source TEXT, created TEXT,
                    status TEXT, stage TEXT, log TEXT DEFAULT ''
                );
                UPDATE runs SET status='error', stage='Исполнитель был остановлен'
                WHERE status='running';
            """)

    @contextmanager
    def connection(self):
        db = sqlite3.connect(self.db, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, sha, source):
        deploy.valid_sha(sha)
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            active = db.execute(
                "SELECT id FROM runs WHERE sha=? AND status IN ('queued','running')", (sha,)
            ).fetchone()
            if active:
                return active[0]
            if source == "auto":
                # A deliberate successful manual rollback opens a new upgrade cycle.
                last = db.execute(
                    """SELECT id FROM runs WHERE sha=? AND source='auto'
                    AND id > COALESCE((SELECT MAX(id) FROM runs WHERE source='manual'
                    AND status='success'),0) ORDER BY id DESC LIMIT 1""",
                    (sha,),
                ).fetchone()
                if last:
                    return last[0]
            row = db.execute(
                """INSERT INTO runs(sha,source,created,status,stage)
                VALUES(?,?,?,'queued','В очереди')""",
                (sha, source, stamp()),
            )
        self.wake.set()
        return row.lastrowid

    def manual(self):
        sha = self.manual_sha or deploy.head()
        if not deploy.approved(deploy.checks(sha)):
            raise ValueError("Для коммита ещё нет двух успешных push-проверок")
        return self.enqueue(sha, "manual")

    def poll(self):
        try:
            sha = deploy.head()
            checks = deploy.checks(sha)
            self.ci = {"sha": sha, "checks": checks, "updated": stamp(), "message": "Проверки main"}
        except Exception as exc:
            self.ci = {"updated": stamp(), "message": f"GitHub временно недоступен · {exc}"}
            return
        if deploy.approved(checks):
            try:
                installed = deploy.application()["git_sha"]
            except (OSError, ValueError, RuntimeError):
                installed = None
            if installed != sha:
                self.enqueue(sha, "auto")

    def execute_one(self):
        with self.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM runs WHERE status='queued' ORDER BY id LIMIT 1"
            ).fetchone()
            if not row:
                return False
            db.execute("UPDATE runs SET status='running' WHERE id=?", (row["id"],))

        def stage(name):
            with self.connection() as db:
                db.execute(
                    "UPDATE runs SET stage=?,log=log||? WHERE id=?",
                    (name, f"\n[{stamp()}] {name}\n", row["id"]),
                )

        def log(line):
            with self.connection() as db:
                db.execute("UPDATE runs SET log=log||? WHERE id=?", (line + "\n", row["id"]))

        try:
            deploy.deploy(row["sha"], stage, log)
            status, label = "success", "Развёрнуто"
        except Exception as error:
            status, label = "error", "Ошибка"
            log(str(error))
        with self.connection() as db:
            db.execute("UPDATE runs SET stage=?,status=? WHERE id=?", (label, status, row["id"]))
        return True

    def history(self):
        with self.connection() as db:
            return [
                dict(r)
                for r in db.execute(
                    "SELECT id,sha,source,created,status,stage FROM runs ORDER BY id DESC"
                )
            ]

    def log(self, number):
        with self.connection() as db:
            row = db.execute("SELECT log FROM runs WHERE id=?", (number,)).fetchone()
            return row[0] if row else ""

    def start(self):
        def worker():
            while True:
                self.wake.clear()
                if not self.execute_one():
                    self.wake.wait(2)

        def monitor():
            while True:
                self.poll()
                threading.Event().wait(self.interval)

        for job in (worker, monitor):
            threading.Thread(target=job, daemon=True).start()
