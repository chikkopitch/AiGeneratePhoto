import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.storage.redis import RedisStorage
from redis.asyncio import Redis

from app.bot.handlers import get_routers
from app.bot.middlewares import DatabaseSessionMiddleware, IncomingLoggingMiddleware
from app.config import Settings
from app.database import check_database_connection, create_database_engine, create_session_factory
from app.services import GenerationService, InMemoryKeyValueStore, RateLimitService, WavespeedClient
from app.utils import setup_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    settings = Settings()
    setup_logging(settings.log_level)

    engine = create_database_engine(settings)
    try:
        await check_database_connection(engine)
    except RuntimeError as exc:
        await engine.dispose()
        raise SystemExit(str(exc)) from exc

    session_factory = create_session_factory(engine)
    storage = create_storage(settings)
    redis = get_storage_redis(storage)
    if redis is None:
        logger.warning("REDIS_URL is not set, using in-memory rate limits and support mapping")
        key_value_store = InMemoryKeyValueStore()
    else:
        key_value_store = redis

    bot = await create_bot(settings)
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.middleware(IncomingLoggingMiddleware())
    dispatcher.update.middleware(DatabaseSessionMiddleware(session_factory))

    for router in get_routers():
        dispatcher.include_router(router)

    wavespeed_client = WavespeedClient(
        api_key=settings.wavespeed_api_key.get_secret_value(),
        base_url=settings.wavespeed_base_url,
        model_path=settings.wavespeed_model_path,
        timeout_seconds=settings.wavespeed_request_timeout_seconds,
    )
    generation_service = GenerationService(
        wavespeed_client=wavespeed_client,
        settings=settings,
    )
    rate_limit_service = RateLimitService(key_value_store)

    try:
        logger.info("Bot polling started")
        await dispatcher.start_polling(
            bot,
            settings=settings,
            generation_service=generation_service,
            rate_limit_service=rate_limit_service,
            redis=key_value_store,
        )
    finally:
        await wavespeed_client.close()
        if redis is not None:
            await redis.aclose()
        await bot.session.close()
        await engine.dispose()


def create_storage(settings: Settings) -> MemoryStorage | RedisStorage:
    if settings.redis_url:
        logger.info("Using RedisStorage for FSM")
        redis = Redis.from_url(settings.redis_url)
        return RedisStorage(redis=redis)

    logger.info("Using MemoryStorage for FSM")
    return MemoryStorage()


def get_storage_redis(storage: MemoryStorage | RedisStorage) -> Redis | None:
    if isinstance(storage, RedisStorage):
        return storage.redis
    return None


def build_bot(settings: Settings, proxy: str | None) -> Bot:
    session = AiohttpSession(proxy=proxy)
    return Bot(
        token=settings.bot_token.get_secret_value(),
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


async def create_bot(settings: Settings) -> Bot:
    bot = build_bot(settings, settings.telegram_proxy)
    if settings.telegram_proxy is None:
        return bot

    try:
        await bot.get_me()
        logger.info("Telegram proxy connection verified", extra={"status": "telegram_proxy_ok"})
        return bot
    except Exception as exc:
        logger.warning(
            "Telegram proxy connection failed, falling back to direct connection",
            extra={"status": "telegram_proxy_failed", "error_type": type(exc).__name__},
        )
        await bot.session.close()

    direct_bot = build_bot(settings, None)
    try:
        await direct_bot.get_me()
        logger.warning("Telegram direct connection verified", extra={"status": "telegram_direct_ok"})
    except Exception:
        await direct_bot.session.close()
        raise
    return direct_bot


if __name__ == "__main__":
    asyncio.run(main())
