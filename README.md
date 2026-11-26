# DevOps Task Manager

[![Docker test deployment](https://github.com/crvstxllize/Task-Manager/actions/workflows/docker-test.yml/badge.svg?branch=main&event=push)](https://github.com/crvstxllize/Task-Manager/actions/workflows/docker-test.yml?query=branch%3Amain)
[![Flask CI-CD](https://github.com/crvstxllize/Task-Manager/actions/workflows/ci.yml/badge.svg?branch=main&event=push)](https://github.com/crvstxllize/Task-Manager/actions/workflows/ci.yml?query=branch%3Amain)

Учебный проект Satbayev University по автоматическому развёртыванию веб-приложения с Docker. Task Manager создаёт и хранит задачи в SQLite. Панель релиза показывает версию, Git SHA и доступность сервиса. Интерфейс поддерживает светлую и тёмную темы.

## Запуск через Docker Compose

Нужны Git, запущенный Docker Desktop и Docker Compose. Откройте терминал в чистой рабочей копии нужного коммита.

**Windows PowerShell**

```powershell
$env:GIT_SHA = git rev-parse HEAD
docker compose up -d --build --wait
docker compose ps
Invoke-RestMethod http://127.0.0.1:5002/health
Invoke-RestMethod http://127.0.0.1:5002/version
```

**macOS**

```sh
export GIT_SHA="$(git rev-parse HEAD)"
docker compose up -d --build --wait
docker compose ps
curl -fsS http://127.0.0.1:5002/health
curl -fsS http://127.0.0.1:5002/version
```

Откройте <http://127.0.0.1:5002/>. Compose публикует **5002 → 5000**. Браузер обращается к порту 5002 на хосте, Flask слушает порт 5000 в контейнере. Чтобы выбрать другой внешний порт, задайте `$env:TASK_MANAGER_PORT = '5010'` в PowerShell или `export TASK_MANAGER_PORT=5010` на macOS. Если сайт уже запущен для защиты, сначала проверьте, какой Compose-проект обслуживает этот порт.

В штатной конфигурации том `devops-task-manager_sqlite-data` подключается к `/data`. SQLite хранит задачи в `/data/tasks.sqlite3`, поэтому пересоздание контейнера с тем же томом сохраняет записи. `docker compose stop` останавливает сервис с сохранением данных. Команда `docker compose down -v` удаляет том и задачи.

`GET /health` возвращает HTTP 200 и `{"status":"ok"}`. `GET /version` возвращает версию приложения и полный `git_sha`, переданный при сборке. Тот же SHA записывается в метку Docker-образа.

## Конвейер GitHub Actions

```text
Git checkout → Ruff → pytest → Docker build → Compose up → healthy → HTTP CRUD
                                                              ↓
    Старый образ → завершённая задача в SQLite → новый образ + тот же том
                                                              ↓
               Новый контейнер и SHA → прежние ID и статус задачи → очистка
```

**Docker test deployment** запускается для PR в `main` и при push в `main` или `defense/final-v1`. Это автоматическое развёртывание и обновление во временной тестовой среде GitHub Actions. Для проверки обновления workflow собирает два образа из Git: `af400ff` и ревизию текущего запуска. Он создаёт задачу через HTTP в старой версии, завершает её и сверяет ID и статус в новом контейнере. Для каждого прогона создаётся отдельный именованный том SQLite. Тестовые контейнер, сеть и том удаляются после проверки. Сайт для показа запускается локально через Compose.

Отдельный **Flask CI-CD** сохраняет ZIP-артефакт и проверяет запуск из распакованной копии. Порядок показа логов и ссылки на подтверждённые прогоны собраны в [EVIDENCE.md](EVIDENCE.md).

## Сценарий живого показа

1. **Сайт.** Откройте Task Manager, добавьте задачу, завершите её и покажите SHA в панели релиза.
2. **Контейнер.** Выполните `docker compose ps` из папки запуска. Покажите `healthy`, привязку порта и ответы `/health` и `/version`.
3. **Логи Actions.** Откройте успешный Docker-workflow. Покажите Ruff, pytest, сборку образа, запуск Compose и HTTP CRUD.
4. **Сохранность данных.** Раскройте `Verify upgrade preserves tasks`. Сравните SHA и ID двух контейнеров. Покажите одинаковый том, ID задачи и подтверждённый статус завершения.

## Проверки без Docker

Активируйте отдельное окружение Python 3.12 и установите зависимости командой `python -m pip install -r requirements-dev.txt`. Запустите `python -m ruff check .`, `python -m ruff format --check .` и `python -m pytest -q`. Для запуска Flask без Docker используйте `python app.py` и <http://127.0.0.1:5000/>. В этом режиме по умолчанию используется `instance/tasks.sqlite3`. Тесты используют временные базы.

## Локальная панель развёртывания на macOS

[Запуск панели, проверка обновления и сценарий защиты на 60 секунд](PANEL.md).
