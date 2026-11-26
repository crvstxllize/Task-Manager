import pytest

from panel import deploy
from panel.service import Service

SHA = "a" * 40


def run(**changes):
    record = {
        "event": "push",
        "head_branch": "main",
        "head_sha": SHA,
        "status": "completed",
        "conclusion": "success",
        "head_repository": {"full_name": deploy.REPO},
        "run_number": 1,
        "run_attempt": 1,
    }
    return {**record, **changes}


@pytest.mark.parametrize(
    "invalid",
    [
        {"event": "pull_request"},
        {"head_branch": "feature"},
        {"head_sha": "b" * 40},
        {"head_repository": {"full_name": "fork/Task-Manager"}},
    ],
)
def test_other_runs_do_not_qualify(invalid):
    assert deploy.verdict([run(**invalid)], SHA) == "ожидание"


def test_latest_attempt_and_both_workflows():
    assert deploy.verdict([run(), run(run_attempt=2, status="in_progress")], SHA) == "в процессе"
    assert deploy.verdict([run(), run(run_number=2, conclusion="failure")], SHA) == "ошибка"
    assert not deploy.approved({"ci.yml": "успешно"})
    assert deploy.approved(dict.fromkeys(deploy.WORKFLOWS, deploy.verdict([run()], SHA)))


def test_poll_dedup_after_failure_and_restart(tmp_path, monkeypatch):
    service = Service(tmp_path)
    monkeypatch.setattr(deploy, "head", lambda: SHA)
    monkeypatch.setattr(deploy, "checks", lambda sha: dict.fromkeys(deploy.WORKFLOWS, "успешно"))
    monkeypatch.setattr(deploy, "application", lambda: {"git_sha": "b" * 40})

    def failed(sha, stage, log):
        stage("Сборка образа")
        log("build failed")
        raise RuntimeError("build exit 1")

    monkeypatch.setattr(deploy, "deploy", failed)
    service.poll()
    service.poll()
    assert len(service.history()) == 1
    assert service.execute_one()
    service = Service(tmp_path)
    service.poll()
    assert not service.execute_one()
    (row,) = service.history()
    assert row["status"] == "error" and "build failed" in service.log(row["id"])
    assert service.manual() != row["id"]


def test_github_outage(tmp_path, monkeypatch):
    def offline():
        raise OSError("Нет связи")

    monkeypatch.setattr(deploy, "head", offline)
    service = Service(tmp_path)
    service.poll()
    assert "недоступен" in service.ci["message"] and service.history() == []


def test_failed_compose_build_never_calls_up(tmp_path, monkeypatch):
    import json

    config = {
        "services": {
            "web": {
                "ports": [{"host_ip": "127.0.0.1", "published": "5000", "target": 5000}],
                "volumes": [{"type": "volume", "source": "sqlite-data", "target": "/data"}],
            }
        },
        "volumes": {"sqlite-data": {"name": deploy.VOLUME}},
    }
    commands = tmp_path / "commands"
    git = tmp_path / "git"
    git.write_text("#!/bin/sh\nexit 0\n")
    git.chmod(0o755)
    docker = tmp_path / "docker"
    docker.write_text(
        f'#!/bin/sh\necho "$*" >> "{commands}"\n'
        f"""case "$*" in
            *config*) echo '{json.dumps(config)}';;
            *build*) echo 'build failed'; exit 1;;
            *) exit 2;;
        esac
        """
    )
    docker.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path))
    monkeypatch.setattr(deploy, "checks", lambda sha: dict.fromkeys(deploy.WORKFLOWS, "успешно"))
    monkeypatch.setattr(deploy, "target", lambda: "existing")
    logs = []
    with pytest.raises(RuntimeError, match="кодом 1"):
        deploy.deploy(SHA, logs.append, logs.append)
    assert "build failed" in logs and " build web" in commands.read_text()
    assert " up " not in commands.read_text()
