# Что показать на защите

1. **Работающее приложение.** Откройте <http://127.0.0.1:5002/>. Покажите создание, завершение и отображение задачи в списке. Сверьте SHA в интерфейсе с `/version`.
2. **Локальный контейнер.** Покажите `docker compose ps` со статусом `healthy` и портами `5002 → 5000`. Откройте `/health` и `/version`. В конфигурации Compose покажите подключение тома к `/data`.
3. **Основной сценарий CI.** В успешном Docker-workflow откройте `Check code quality`, `Test application`, `Build image from the tested commit`, `Deploy built image and wait for health` и `Verify HTTP health, Git revision and task persistence`. В логах последнего шага найдите `Healthcheck passed`, `Verified /version` и `HTTP CRUD passed`. [Подтверждённый прогон main для f379362](https://github.com/crvstxllize/Task-Manager/actions/runs/45466388148)
4. **Обновление с сохранением данных.** Откройте `Verify upgrade preserves tasks`. Сопоставьте строки `Before upgrade` и `After upgrade`: SHA и ID контейнера различаются, том и ID задачи совпадают. В старой версии завершённая задача помечена «Готово», в новой — «Завершена». Строка `Upgrade preserved task_id=` подтверждает сохранность задачи.
5. **ZIP.** При необходимости скачайте артефакт и откройте шаг `Healthcheck - start Flask, wait, verify HTTP CRUD and stop`. [Подтверждённый ZIP-прогон main для f379362](https://github.com/crvstxllize/Task-Manager/actions/runs/45466388287)

На шагах 3 и 4 GitHub Actions выполняет автоматическое развёртывание и обновление во временной тестовой среде. Контейнеры и тестовые данные удаляются после завершения проверки.
