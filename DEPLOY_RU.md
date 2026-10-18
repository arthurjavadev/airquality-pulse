# AirQuality Pulse - обновление GitHub и Render

## Что важно заранее

- Существующий адрес: https://airquality-pulse.onrender.com
- Репозиторий: https://github.com/arthurjavadev/airquality-pulse
- Если сайт уже опубликован, НЕ создавайте второй Web Service в Render.
- Новая версия добавляет RabbitMQ, SQL и отдельные процессы. Они не заработают в облаке автоматически после загрузки ZIP.
- Сначала убедитесь, что все тесты в GitHub Actions зелёные. Только затем разрешайте деплой.
- Не добавляйте платные услуги без отдельного решения о расходах.

## Способ 1 - загрузка в GitHub через браузер

1. Скачайте ZIP финального проекта и распакуйте его.
2. Откройте https://github.com/arthurjavadev/airquality-pulse
3. Выберите `Add file` -> `Upload files`.
4. Перетащите **содержимое** распакованной папки, сохраняя структуру `src`, `tests`, `migrations`, `.github`.
5. При совпадении путей загрузка должна заменить соответствующие файлы. Проверьте список изменений до коммита.
6. Введите сообщение `Add event messaging and complete AirQuality Pulse pipeline`.
7. Нажмите `Commit changes` и откройте вкладку `Actions`.
8. Убедитесь, что тесты прошли. Если появилась ошибка, откройте logs и исправьте её до релиза.

Если GitHub не позволяет загрузить нужные папки через веб-форму, используйте Способ 2.

## Способ 2 - Git через терминал, более надёжный

Если `git` уже установлен:

```bash
git clone https://github.com/arthurjavadev/airquality-pulse.git
cd airquality-pulse
```

Распакуйте архив. Скопируйте **всё содержимое** распакованного проекта в папку
`airquality-pulse`, заменяя старые файлы, включая скрытые `.github` и `.python-version`.

Затем выполните:

```bash
git status
git add -A
git commit -m "Add event messaging and complete AirQuality Pulse pipeline"
git push origin main
```

Не удаляйте папку `.git`. Она принадлежит уже клонированному репозиторию.
Не копируйте `.env` с паролями и локальную SQLite базу.

## Существующий Render Web Service

1. Откройте https://dashboard.render.com и выберите существующий Web Service `airquality-pulse`.
2. Убедитесь, что источник GitHub и ветка `main` не изменились.
3. В `Settings` -> `Auto-Deploy` выберите `After CI Checks Pass`.
4. Используйте `Build Command`: `pip install -r requirements.txt`.
5. Используйте `Start Command`: `gunicorn --workers 1 src.app:app`.
6. Используйте `Health Check Path`: `/health`.
7. Python 3.12 задаётся файлом `.python-version`. Если в Render переменная
   `PYTHON_VERSION` уже установлена, она имеет приоритет. Выберите совместимую версию 3.12.x.
8. После зелёного статуса GitHub Actions дождитесь завершения Render Deploy -> Live.

Проверка публичного приложения:

```text
https://airquality-pulse.onrender.com/
https://airquality-pulse.onrender.com/health
https://airquality-pulse.onrender.com/metrics
https://airquality-pulse.onrender.com/metrics/prometheus
https://airquality-pulse.onrender.com/api/echo?city=Berlin
```

До подключения общей БД `/api/air-quality?city=Berlin` вернёт 404 с сообщением,
что ещё нет сохранённой аналитики. Это ожидаемо, и форма с выводом `Berlin` продолжит работать.

## Как запустить ВСЮ архитектуру бесплатно на своём компьютере

1. Установите Docker Engine + Compose.
2. Распакуйте финальный проект.
3. Откройте терминал в его корне.
4. Выполните:

```bash
docker compose up --build -d
docker compose logs -f collector analyzer
```

Когда коллекция завершится, откройте:

```text
http://localhost:8000/
http://localhost:8000/api/air-quality?city=Berlin
http://localhost:15672/
```

Для RabbitMQ используйте логин `airquality` и пароль `local_dev_only` только локально.
Сервис `web` должен показывать итоговый прогноз после поступления события и анализа.

## Весь проект в облаке

Для реальной непрерывной архитектуры нужны:

1. Общая **постоянная PostgreSQL** для Web Application, Data Collector, Data Analyzer.
2. Доступный этим процессам **RabbitMQ broker** (внешний managed RabbitMQ или выделенная VM).
3. **Отдельный scheduler/collector**, запускаемый периодически (например, Render Cron Job).
4. **Отдельный analyzer worker**, работающий непрерывно (Render Background Worker или VM).
5. Общий `DATABASE_URL` для всех трёх приложений и `RABBITMQ_URL` для collector/analyzer.
6. Однократный запуск `python -m src.migrate` с доступом к PostgreSQL.

Команды:

```bash
python -m src.migrate
python -m src.collector_worker --cities Berlin,Frankfurt,London,Paris
python -m src.consumer
gunicorn --workers 1 src.app:app
```

Хостинг Render Cron Jobs и Background Workers не входит в бесплатный тип службы.
Managed RabbitMQ также нужно организовать отдельно. Не создавайте платные сервисы,
пока не утвердили бюджет. Доступный в Render бесплатный PostgreSQL имеет
ограниченный срок хранения. Локальная SQLite на бесплатном веб-сервисе Render
не годится для постоянных данных, поскольку файловая система временная.

## Проверка работы очереди

После запуска Docker Compose:

1. В интерфейсе RabbitMQ откройте `Queues`.
2. Убедитесь, что существует `airquality.analysis` и `airquality.analysis.dead`.
3. Запустите дополнительный сбор:

```bash
docker compose run --rm collector python -m src.collector_worker --cities Berlin
```

4. Посмотрите логи `docker compose logs --tail=100 collector analyzer`.
5. Убедитесь, что Data Analyzer записал отчёт в PostgreSQL, а сообщения были подтверждены.
6. Если обработка ошибки закончилась DLQ, найдите неудачное сообщение там.

## Откат

При ошибках после обновления не сохраняйте частично работающую конфигурацию:

- В Render откройте `Deploys` и выберите последний рабочий релиз, затем `Rollback`.
- В GitHub верните проблемные изменения через новый revert commit после проверки причины.
- Отменяйте только те миграции, для которых подтвержден безопасный обратный путь.
- Не удаляйте PostgreSQL и RabbitMQ volumes без намеренного решения удалить данные.

## Критерии проекта

- Web Application - Flask, HTML form, reports and REST API.
- Data Collector - отдельный процесс, Open-Meteo GET, SQL persistence.
- Data Analyzer - отдельный процесс, агрегирование по SQL.
- Data persistence - SQLAlchemy, Alembic, PostgreSQL/SQLite.
- Unit/integration tests - pytest, тестовая SQLite и test doubles.
- Continuous Integration - GitHub Actions.
- Continuous Delivery - Render after successful CI checks.
- Production monitoring - `/health`, `/metrics`, Prometheus text.
- Event collaboration - RabbitMQ producer, durable queue and independent consumer.

Примечание: в бесплатном Render Web Service реально будет работать только веб-часть.
Полная архитектура проверяется локально через Docker Compose либо в отдельной облачной конфигурации.
