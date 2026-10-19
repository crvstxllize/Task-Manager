# DevOps Task Manager

Учебный проект СРС №1 по дисциплине «DevOps инженерия», Satbayev University, 3 курс.
Вариант №1: «Настроить CI/CD-конвейер для веб-приложения на Python Flask».

Цель — пройти проверяемый путь от исходного кода до ZIP-артефакта и реального
временного тестового развёртывания. Приложение создаёт, показывает, завершает,
возвращает в работу и удаляет задачи, считает статистику и сохраняет данные в SQLite.

## Технологии

Python 3.12+, Flask, встроенный sqlite3, HTML5, CSS3, pytest, Ruff и GitHub Actions.
PyYAML нужен только для локальной проверки синтаксиса workflow. Node.js и JavaScript
не требуются: формы работают на сервере с перенаправлением после успешного POST.

Интерфейс на русском языке, светлая пастельная тема, адаптивная сетка, карточки
статистики и прогресс. Внешние шрифты, UI-фреймворки и платные API не используются.

## Структура

```text
.github/workflows/ci.yml  # CI, передача ZIP и временное CD
app.py                   # фабрика приложения, маршруты, SQLite
templates/index.html     # Jinja-шаблон с автоматическим экранированием
static/style.css         # адаптивный интерфейс
tests/
  conftest.py             # отдельная временная БД для каждого теста
  test_app.py             # HTTP, CRUD, валидация, безопасность, сохранение
  test_package.py         # состав и целостность ZIP
scripts/
  package.py              # упаковка только явно разрешённых файлов
  deploy_test.py          # чистая среда, запуск, проверка, остановка
  healthcheck.py          # ожидание /health и полный HTTP CRUD
requirements.txt         # зависимости времени выполнения
requirements-dev.txt     # зависимости разработки и проверки
pyproject.toml           # настройки Ruff и pytest
.gitignore
.gitattributes
README.md
EVIDENCE.md
```

При запуске создаётся `instance/tasks.sqlite3`, при упаковке —
`dist/devops-task-manager.zip`. Эти файлы и `.venv` исключены из Git.

## Запуск в Windows PowerShell

Откройте терминал в корне проекта:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe app.py
```

Откройте <http://127.0.0.1:5000>. Остановка — Ctrl+C.
Активация окружения не требуется, поэтому менять ExecutionPolicy не нужно.
Если окружение уже настроено, достаточно последней команды.

Для запуска нужны только зависимости из `requirements.txt`; dev-зависимости нужны
для тестов и проверки кода.

Путь к БД можно задать перед запуском:

```powershell
$env:DATABASE_PATH = Join-Path $PWD "instance\my-tasks.sqlite3"
.\.venv\Scripts\python.exe app.py
```

Путь по умолчанию привязан к папке проекта, поэтому обычный перезапуск сохраняет
задачи. Относительный DATABASE_PATH также считается от корня проекта. Каталоги
создаются автоматически. Для возврата к умолчанию:

```powershell
Remove-Item Env:DATABASE_PATH -ErrorAction SilentlyContinue
```

SQL-запросы параметризованы. Текст обрезается по краям и проверяется: 1–200 символов,
без управляющих символов. Jinja экранирует пользовательский ввод. Изменения доступны
только через POST с CSRF-токеном. SECRET_KEY берётся из окружения или генерируется
при запуске; после перезапуска обновите страницу, чтобы получить новый токен формы.
Для будущего постоянного развёртывания задайте стабильный случайный SECRET_KEY
через окружение, не коммитьте его в Git.

Сервер слушает только 127.0.0.1, debug и reloader отключены. Аутентификация в объём
этой СРС не входит: это локальный однопользовательский учебный сервис. Flask development
server подходит для демонстрации и временного теста; постоянный production требует
WSGI-сервера, HTTPS и отдельной настройки доступа. Docker — следующий этап, он здесь
намеренно не добавлен.

## Маршруты

| Метод | Путь | Результат |
| --- | --- | --- |
| GET | / | Задачи, статистика, форма |
| POST | /tasks | Создание |
| POST | /tasks/ID/toggle | Завершение / возврат в работу |
| POST | /tasks/ID/delete | Удаление |
| GET | /health | HTTP 200 и JSON `{"status":"ok"}` |

После успешного POST возвращается 303 на главную, при ошибке текста — 400,
при отсутствии задачи — 404. /health подтверждает доступность HTTP-приложения;
это проверка liveness, а не исчерпывающая диагностика БД.

## Локальные проверки

```powershell
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe scripts\package.py
.\.venv\Scripts\python.exe scripts\deploy_test.py all dist\devops-task-manager.zip
```

Последняя команда распакует ZIP в отдельный временный каталог, создаст новое
виртуальное окружение, установит runtime-зависимости, запустит сервер на 127.0.0.1:5055,
дождётся /health и выполнит создание → завершение → возврат → удаление через HTTP.
Процесс останавливается в finally, временный каталог удаляется при выходе.
Для установки зависимостей в новую среду нужен интернет.

Во втором терминале при работающем обычном приложении:

```powershell
Invoke-RestMethod http://127.0.0.1:5000/health
.\.venv\Scripts\python.exe scripts\healthcheck.py --url http://127.0.0.1:5000 --crud
```

Healthcheck требует HTTP 200 и точный JSON, повторяет запросы до 30 секунд и
возвращает ненулевой exit code при ошибке. HTTP CRUD создаёт свою задачу и удаляет её.
Все pytest-тесты используют tmp_path и не затрагивают пользовательскую БД.
Проверяется также сохранение данных между двумя экземплярами приложения.

Для синтаксической проверки YAML:

```powershell
.\.venv\Scripts\python.exe -c "from pathlib import Path; import yaml; d=yaml.load(Path('.github/workflows/ci.yml').read_text(encoding='utf-8'), Loader=yaml.BaseLoader); assert set(d['on']) == {'push', 'pull_request', 'workflow_dispatch'}; assert len(d['jobs']) == 2; print('Workflow YAML OK')"
```

BaseLoader сохраняет ключ on строкой. Это проверка синтаксиса и основных секций,
а не замена реального запуска GitHub Actions.

## CI/CD в GitHub Actions

Workflow `.github/workflows/ci.yml` запускается на push, pull_request и вручную
через workflow_dispatch. Платформа runner — ubuntu-latest, Python — 3.12.
Команды проекта написаны на Python и работают также в Windows PowerShell.

Порядок: **Checkout → Setup Python → Install Dependencies → Quality Check →
Tests → Package Artifact → Deploy to Test → Healthcheck**.

1. **Quality, tests and ZIP artifact** получает код, устанавливает dev-зависимости,
   выполняет `ruff check .`, `ruff format --check .` и pytest.
2. Только после успеха проверок `scripts/package.py` создаёт ZIP.
   `actions/upload-artifact@v4` сохраняет его под именем devops-task-manager на 14 дней.
3. **Deploy to Test and Healthcheck** зависит от первого job и получает именно
   опубликованный ZIP через `actions/download-artifact@v4`.
4. **Deploy to Test** распаковывает ZIP в отдельный каталог runner.temp/devops-test,
   создаёт чистую .venv и устанавливает только requirements.txt.
5. **Healthcheck** запускает Flask именно из распакованного приложения в фоне,
   ждёт HTTP 200 и JSON от /health, затем проверяет весь CRUD по HTTP.
   PYTHONPATH убирается, используется собственная тестовая БД.
6. finally завершает процесс при успехе и при ошибке, при необходимости через kill.
   При сбое печатается лог сервера. Неуспех проверки делает job красным.
   Каталог находится на одноразовом runner и исчезает после его уничтожения.

Это настоящее, но кратковременное тестовое развёртывание внутри runner.
Постоянного публичного URL нет. Это не публикация на production-хостинг.
Общий таймаут job — 10 минут; сервер и HTTP-проверки также имеют свои таймауты.
Новые запуски той же ветки отменяют устаревшие.

Справочная документация:
[Flask installation](https://flask.palletsprojects.com/en/stable/installation/),
[GitHub workflow artifacts](https://docs.github.com/en/actions/concepts/workflows-and-actions/workflow-artifacts).

## Что находится в артефакте

ZIP содержит приложение, шаблон, CSS, зафиксированные зависимости, скрипты проверки,
тесты, workflow и документацию. Зависимости описаны requirements.txt и устанавливаются
при развёртывании; виртуальное окружение и бинарные пакеты в ZIP не вкладываются.
Это переносимый исходный дистрибутив, для его установки нужен Python и доступ к PyPI.

Упаковщик использует явный список RELEASE_FILES, а не рекурсивное копирование папки.
Поэтому .venv, .git, SQLite, .env, кэши и логи не попадут в архив даже при наличии
в рабочей папке. После добавления нового обязательного файла обновите RELEASE_FILES.
Скачать: GitHub → Actions → успешный запуск → Artifacts → devops-task-manager.
GitHub может выдать внешнюю ZIP-обёртку, внутри которой лежит наш ZIP.

## Первые два запуска CI/CD

Удалённый репозиторий не создавался и push автоматически не выполнялся.
В GitHub создайте пустой репозиторий без README, .gitignore и лицензии.
Подставьте свой настоящий URL. Выполняйте push только когда готовы опубликовать код.

Первый запуск:

```powershell
git status
# Только если Git ещё не инициализирован:
git init -b main
git add .
git commit -m "feat: add Flask task manager and CI-CD pipeline"
git remote add origin https://github.com/YOUR_LOGIN/devops-task-manager.git
git push -u origin main
```

Если origin уже существует, проверьте `git remote -v` и используйте его.
Если Git попросит имя и email, настройте их локально в этом репозитории своими данными,
после чего повторите commit. Не подставляйте вымышленные персональные данные.

Дождитесь завершения первого запуска во вкладке Actions. Для второго запуска
можно выбрать Actions → Flask CI-CD → Run workflow → main → Run workflow.
Вариант вторым реальным push, без бессмысленного пустого коммита:

```powershell
Add-Content -Path README.md -Encoding UTF8 -Value "`nКонтрольное изменение для второго запуска CI/CD СРС №1."
git add README.md
git commit -m "docs: record second CI-CD verification"
git push
```

Дождитесь результата второго запуска. Не выдавайте локальные проверки за успешный
GitHub Actions: реальный результат подтверждается только страницей запуска в GitHub.

## Защита

Покажите интерфейс и полный цикл задачи, статистику, сохранение после перезапуска,
JSON /health, успешные локальные Ruff и pytest, YAML workflow и два реальных запуска
Actions. Откройте шаги упаковки, тестового развёртывания и healthcheck, скачайте ZIP,
покажите его состав. Объясните разницу между CI, упаковкой и временным CD.
Список нужных скриншотов — в EVIDENCE.md.

Повторная проверка CI/CD.
