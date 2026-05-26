from aiogram import Router

from app.bot.handlers.admin import router as admin_router
from app.bot.handlers.errors import router as errors_router
from app.bot.handlers.generation import router as generation_router
from app.bot.handlers.history import router as history_router
from app.bot.handlers.menu import router as menu_router
from app.bot.handlers.support import router as support_router


def get_routers() -> list[Router]:
    return [
        errors_router,
        admin_router,
        menu_router,
        history_router,
        support_router,
        generation_router,
    ]
