# Telegram-бот AI-фотосессий

Production-ready каркас Telegram-бота для генерации AI-фотосессий по текстовому описанию.

## Стек

- Python 3.11+
- aiogram 3
- PostgreSQL через SQLAlchemy 2 async
- Alembic
- Redis для FSM
- httpx
- pydantic-settings
- Docker Compose
- pytest

## Архитектура

Handlers в `app/bot/handlers` не вызывают WaveSpeed напрямую. Они получают `GenerationService`, а сервис уже использует `WavespeedClient`; записи пользователей и генераций сохраняются через репозитории PostgreSQL.

Основной поток:

1. `/start` сохраняет или обновляет Telegram-пользователя и показывает меню.
2. «Создать фотосессию» переводит пользователя в FSM-состояние ожидания описания.
3. После текста handler валидирует prompt, создаёт запись генерации и вызывает `GenerationService.generate_image`.
4. `GenerationService` улучшает prompt, отправляет запрос в WaveSpeed и ждёт завершения через polling.
5. Handler отправляет пользователю изображение и сохраняет итоговый статус генерации.

## Запуск через Docker

### 1. Создать `.env`

Создайте `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Для Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

Заполните в `.env` реальные значения:

- `BOT_TOKEN`
- `WAVESPEED_API_KEY`
- `TELEGRAM_PROXY`, если нужен прокси для Telegram API
- `POSTGRES_PASSWORD`
- `ADMIN_IDS`
- `SUPPORT_CHAT_ID`, если нужен чат поддержки

Для Docker Compose значения подключения должны соответствовать настройкам PostgreSQL:

```env
DATABASE_URL=postgresql+asyncpg://postgres:postgres@postgres:5432/photo_bot
REDIS_URL=redis://redis:6379/0
TELEGRAM_PROXY=socks5://213.159.196.77:1080
POSTGRES_DB=photo_bot
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
```

### 2. Запустить проект

Запустите бота, PostgreSQL и Redis:

```bash
docker compose up --build
```

Контейнер `bot` автоматически выполняет миграции перед стартом polling:

```bash
alembic upgrade head
```

Для запуска в фоне используйте:

```bash
docker compose up -d --build
```

### 3. Применить миграции вручную

Если контейнеры уже запущены:

```bash
docker compose exec bot alembic upgrade head
```

Если нужно запустить одноразовый контейнер только для миграций:

```bash
docker compose run --rm bot alembic upgrade head
```

### 4. Смотреть логи

Логи бота:

```bash
docker compose logs -f bot
```

Логи всех сервисов:

```bash
docker compose logs -f
```

### 5. Остановить проект

Остановить контейнеры:

```bash
docker compose down
```

Остановить контейнеры и удалить volumes PostgreSQL и Redis с данными:

```bash
docker compose down -v
```

## Локальный запуск без Docker

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
python -m app.main
```

Для Windows PowerShell активация окружения:

```powershell
.\.venv\Scripts\Activate.ps1
```

## Переменные окружения

| Переменная | Назначение |
| --- | --- |
| `BOT_TOKEN` | токен Telegram-бота |
| `WAVESPEED_API_KEY` | API-ключ WaveSpeed |
| `DATABASE_URL` | async URL PostgreSQL |
| `REDIS_URL` | URL Redis |
| `TELEGRAM_PROXY` | опциональный proxy URL для Telegram API, например `socks5://213.159.196.77:1080` |
| `POSTGRES_DB` | имя базы PostgreSQL для Docker Compose |
| `POSTGRES_USER` | пользователь PostgreSQL для Docker Compose |
| `POSTGRES_PASSWORD` | пароль PostgreSQL для Docker Compose |
| `ADMIN_IDS` | Telegram ID администраторов через запятую |
| `SUPPORT_CHAT_ID` | ID чата поддержки |
| `DEFAULT_IMAGE_SIZE` | размер изображения в формате `WIDTH*HEIGHT`, по умолчанию `2048*2048` |

## Тесты

Команда запуска тестов:

```bash
pytest
```

## Источники API

- WaveSpeed документация для `bytedance/seedream-v4`: `POST /api/v3/bytedance/seedream-v4`, `GET /api/v3/predictions/{requestId}/result`, Bearer-auth через `WAVESPEED_API_KEY`: https://wavespeed.ai/docs/docs-api/bytedance/bytedance-seedream-v4
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/20/orm/extensions/asyncio.html
- Alembic asyncio cookbook: https://alembic.sqlalchemy.org/en/latest/cookbook.html
- aiogram RedisStorage: https://docs.aiogram.dev/en/v3.15.0/dispatcher/finite_state_machine/storages.html
- pydantic-settings `BaseSettings`: https://docs.pydantic.dev/latest/api/pydantic_settings/
