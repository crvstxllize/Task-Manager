import sqlite3

import pytest

from app import create_app


def read_tasks(app):
    with sqlite3.connect(app.config["DATABASE_PATH"]) as db:
        db.row_factory = sqlite3.Row
        return db.execute("SELECT * FROM tasks ORDER BY id").fetchall()


def test_home(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "DevOps Task Manager" in response.text
    assert 'data-stat="total">0<' in response.text


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.is_json
    assert response.json == {"status": "ok"}


def test_create_task(client, app, csrf):
    response = client.post("/tasks", data={"title": "  Настроить CI/CD  ", "csrf_token": csrf})
    assert response.status_code == 303
    task = read_tasks(app)[0]
    assert task["title"] == "Настроить CI/CD"
    assert task["completed"] == 0
    assert task["created_at"].endswith("Z")
    assert "Настроить CI/CD" in client.get("/").text


def test_toggle_both_directions(client, app, csrf):
    client.post("/tasks", data={"title": "Проверить статус", "csrf_token": csrf})
    task_id = read_tasks(app)[0]["id"]
    for expected in (1, 0):
        response = client.post(f"/tasks/{task_id}/toggle", data={"csrf_token": csrf})
        assert response.status_code == 303
        assert read_tasks(app)[0]["completed"] == expected


def test_delete_task(client, app, csrf):
    client.post("/tasks", data={"title": "Удалить меня", "csrf_token": csrf})
    task_id = read_tasks(app)[0]["id"]
    response = client.post(f"/tasks/{task_id}/delete", data={"csrf_token": csrf})
    assert response.status_code == 303
    assert read_tasks(app) == []


@pytest.mark.parametrize("title", ["", "   ", "a" * 201, "hello\x00world", "line\nbreak"])
def test_invalid_title(client, app, csrf, title):
    response = client.post("/tasks", data={"title": title, "csrf_token": csrf})
    assert response.status_code == 400
    assert read_tasks(app) == []


def test_safe_output_and_sql_parameters(client, app, csrf):
    title = "<script>alert('x')</script>'); DROP TABLE tasks;--"
    client.post("/tasks", data={"title": title, "csrf_token": csrf})
    response = client.get("/")
    assert title not in response.text
    assert "&lt;script&gt;" in response.text
    assert read_tasks(app)[0]["title"] == title


def test_statistics(client, app, csrf):
    for title in ("Активная", "Готовая"):
        client.post("/tasks", data={"title": title, "csrf_token": csrf})
    client.post(f"/tasks/{read_tasks(app)[1]['id']}/toggle", data={"csrf_token": csrf})
    page = client.get("/").text
    assert 'data-stat="total">2<' in page
    assert 'data-stat="active">1<' in page
    assert 'data-stat="completed">1<' in page


@pytest.mark.parametrize("action", ["toggle", "delete"])
def test_missing_task(client, csrf, action):
    assert client.post(f"/tasks/999/{action}", data={"csrf_token": csrf}).status_code == 404


def test_csrf_required(client, app):
    assert client.post("/tasks", data={"title": "Запрос без токена"}).status_code == 400
    assert read_tasks(app) == []


def test_get_cannot_mutate(client):
    for path in ("/tasks", "/tasks/1/toggle", "/tasks/1/delete"):
        assert client.get(path).status_code == 405


def test_database_persists_between_app_instances(app, client, csrf):
    client.post("/tasks", data={"title": "Сохранённая задача", "csrf_token": csrf})
    restarted = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "another-test-secret",
            "DATABASE_PATH": app.config["DATABASE_PATH"],
        }
    )
    assert "Сохранённая задача" in restarted.test_client().get("/").text


def test_database_path_environment(monkeypatch, tmp_path):
    path = tmp_path / "nested" / "environment.sqlite3"
    monkeypatch.setenv("DATABASE_PATH", str(path))
    configured = create_app({"TESTING": True})
    assert configured.config["DATABASE_PATH"] == str(path)
    assert path.is_file()


def test_security_headers(client):
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "form-action 'self'" in response.headers["Content-Security-Policy"]


@pytest.mark.parametrize("token", ["wrong-token", "кириллица", ""])
def test_invalid_csrf_rejected(client, app, csrf, token):
    response = client.post("/tasks", data={"title": "Не сохранять", "csrf_token": token})
    assert response.status_code == 400
    assert read_tasks(app) == []
