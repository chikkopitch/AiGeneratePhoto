# Telegram-бот AI-фотосессий

MVP Telegram-бота для генерации AI-фотосессий по текстовому описанию.

## Стек

- Python 3.11+
- aiogram 3
- SQLite или PostgreSQL через SQLAlchemy 2 async
- Alembic оставлен в проекте; при запуске приложения схема создаётся через SQLAlchemy metadata
- Redis для FSM и лимитов, опционально
- httpx
- pydantic-settings
- Docker Compose
- pytest

## База данных

Проект поддерживает SQLite по умолчанию и внешний PostgreSQL через `DATABASE_URL`.

По умолчанию используется:

```env
DATABASE_URL=sqlite+aiosqlite:///./data/app.db
```

Если `DATABASE_URL` не задан или задан пустым, приложение использует этот SQLite URL. Папка `data` создаётся автоматически. При первом запуске приложение создаёт таблицы через SQLAlchemy metadata.

Для PostgreSQL укажите URL формата:

```env
DATABASE_URL=postgresql://USER:PASSWORD@HOST:PORT/DB_NAME
```

URL со схемой `postgresql://` автоматически нормализуется к async-драйверу `postgresql+asyncpg://`.

## Архитектура

Handlers в `app/bot/handlers` не вызывают WaveSpeed напрямую. Они получают `GenerationService`, а сервис уже использует `WavespeedClient`; записи пользователей и генераций сохраняются через репозитории SQLAlchemy.

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
- `DATABASE_URL`, можно оставить значением из `.env.example`
- `REDIS_URL`, если нужен внешний Redis
- `ADMIN_IDS`
- `SUPPORT_CHAT_ID`, если нужен чат поддержки

Пример для SQLite:

```env
DATABASE_URL=sqlite+aiosqlite:////app/data/app.db
REDIS_URL=
```

### 2. Запустить проект

Запустите бота:

```bash
docker compose up --build
```

Для запуска в фоне используйте:

```bash
docker compose up -d --build
```

SQLite-файл хранится в Docker volume `bot_data`, который подключён к `/app/data`. При использовании PostgreSQL данные хранятся во внешней базе из `DATABASE_URL`.

### 3. Смотреть логи

Логи бота:

```bash
docker compose logs -f bot
```

Логи всех сервисов:

```bash
docker compose logs -f
```

### 4. Остановить проект

Остановить контейнеры:

```bash
docker compose down
```

Остановить контейнеры и удалить volume с SQLite-файлом:

```bash
docker compose down -v
```

## Локальный запуск без Docker

```bash
python -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
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
| `DATABASE_URL` | опциональный URL базы данных; по умолчанию `sqlite+aiosqlite:///./data/app.db`; для PostgreSQL можно указать `postgresql://USER:PASSWORD@HOST:PORT/DB_NAME` |
| `REDIS_URL` | опциональный URL Redis; пустое значение включает in-memory режим |
| `TELEGRAM_PROXY` | опциональный proxy URL для Telegram API, например `socks5://HOST:PORT` |
| `ADMIN_IDS` | Telegram ID администраторов через запятую |
| `SUPPORT_CHAT_ID` | ID чата поддержки |
| `DEFAULT_IMAGE_SIZE` | размер изображения в формате `WIDTH*HEIGHT`, по умолчанию `2048*2048` |

## Тесты

Команда запуска тестов:

```bash
pytest
```

## Источники API и библиотек

- WaveSpeed документация для `bytedance/seedream-v4`: `POST /api/v3/bytedance/seedream-v4`, `GET /api/v3/predictions/{requestId}/result`, Bearer-auth через `WAVESPEED_API_KEY`: https://wavespeed.ai/docs/docs-api/bytedance/bytedance-seedream-v4
- SQLAlchemy asyncio: https://docs.sqlalchemy.org/20/orm/extensions/asyncio.html
- SQLAlchemy SQLite dialect: https://docs.sqlalchemy.org/20/dialects/sqlite.html
- SQLAlchemy PostgreSQL dialect: https://docs.sqlalchemy.org/20/dialects/postgresql.html
- aiosqlite: https://aiosqlite.omnilib.dev/
- asyncpg: https://magicstack.github.io/asyncpg/current/
- aiogram RedisStorage: https://docs.aiogram.dev/en/v3.15.0/dispatcher/finite_state_machine/storages.html
- pydantic-settings `BaseSettings`: https://docs.pydantic.dev/latest/api/pydantic_settings/
