"""Небольшой Flask Task Manager: SQLite, HTML-формы и отдельная фабрика для тестов."""

import os
import secrets
import sqlite3
from pathlib import Path

from flask import Flask, abort, g, jsonify, redirect, render_template, request, session, url_for

MAX_TASK_LENGTH = 200


def create_app(test_config=None):
    app = Flask(__name__)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE_PATH=os.environ.get("DATABASE_PATH")
        or str(Path(app.instance_path) / "tasks.sqlite3"),
        MAX_CONTENT_LENGTH=16 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    # Относительные пути всегда считаются от корня проекта, а не от текущей папки.
    database = Path(app.config["DATABASE_PATH"])
    if not database.is_absolute():
        database = Path(app.root_path) / database
    database.parent.mkdir(parents=True, exist_ok=True)
    app.config["DATABASE_PATH"] = str(database)

    def get_db():
        if "db" not in g:
            g.db = sqlite3.connect(app.config["DATABASE_PATH"], timeout=10)
            g.db.row_factory = sqlite3.Row
        return g.db

    @app.teardown_appcontext
    def close_db(_error=None):
        db = g.pop("db", None)
        if db is not None:
            db.close()

    with app.app_context():
        db = get_db()
        db.execute(
            """CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL CHECK(length(title) BETWEEN 1 AND 200),
                completed INTEGER NOT NULL DEFAULT 0 CHECK(completed IN (0, 1)),
                created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
            )"""
        )
        db.commit()

    @app.before_request
    def protect_forms():
        if request.method == "POST":
            expected = session.get("csrf_token", "")
            actual = request.form.get("csrf_token", "")
            if not expected or not secrets.compare_digest(expected.encode(), actual.encode()):
                abort(400, description="Форма устарела. Обновите страницу и повторите действие.")

    @app.after_request
    def security_headers(response):
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; style-src 'self'; img-src 'self'; "
            "script-src 'none'; object-src 'none'; base-uri 'self'; "
            "form-action 'self'; frame-ancestors 'none'"
        )
        return response

    def render_dashboard(error=None, title="", status=200):
        session.setdefault("csrf_token", secrets.token_hex(32))
        tasks = get_db().execute("SELECT * FROM tasks ORDER BY completed, id DESC").fetchall()
        total = len(tasks)
        completed = sum(task["completed"] for task in tasks)
        return (
            render_template(
                "index.html",
                tasks=tasks,
                total=total,
                active=total - completed,
                completed=completed,
                progress=round(completed / total * 100) if total else 0,
                error=error,
                title=title,
                max_length=MAX_TASK_LENGTH,
            ),
            status,
        )

    @app.get("/")
    def index():
        return render_dashboard()

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.post("/tasks")
    def add_task():
        title = request.form.get("title", "").strip()
        if not 1 <= len(title) <= MAX_TASK_LENGTH:
            return render_dashboard(
                error=f"Введите задачу длиной от 1 до {MAX_TASK_LENGTH} символов.",
                title=title[:MAX_TASK_LENGTH],
                status=400,
            )
        if any(ord(character) < 32 or ord(character) == 127 for character in title):
            return render_dashboard(
                error="Текст задачи не должен содержать управляющие символы.",
                status=400,
            )
        db = get_db()
        db.execute("INSERT INTO tasks (title) VALUES (?)", (title,))
        db.commit()
        return redirect(url_for("index"), code=303)

    @app.post("/tasks/<int:task_id>/toggle")
    def toggle_task(task_id):
        db = get_db()
        result = db.execute("UPDATE tasks SET completed = 1 - completed WHERE id = ?", (task_id,))
        db.commit()
        if result.rowcount == 0:
            abort(404)
        return redirect(url_for("index"), code=303)

    @app.post("/tasks/<int:task_id>/delete")
    def delete_task(task_id):
        db = get_db()
        result = db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        db.commit()
        if result.rowcount == 0:
            abort(404)
        return redirect(url_for("index"), code=303)

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=5000, debug=False)
