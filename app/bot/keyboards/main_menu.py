from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

CREATE_SESSION_TEXT = "Создать фотосессию"
HISTORY_TEXT = "Мои генерации"
HELP_TEXT = "Помощь"
SUPPORT_TEXT = "Поддержка"
CREATE_AGAIN_TEXT = "Создать ещё"
MAIN_MENU_TEXT = "Главное меню"
TRY_AGAIN_TEXT = "Попробовать снова"
SHOW_LAST_IMAGE_TEXT = "Показать последнюю картинку"

CREATE_SESSION_CALLBACK = "menu:create"
HISTORY_CALLBACK = "menu:history"
HELP_CALLBACK = "menu:help"
SUPPORT_CALLBACK = "menu:support"
MAIN_MENU_CALLBACK = "menu:main"
CREATE_AGAIN_CALLBACK = "generation:create_again"
TRY_AGAIN_CALLBACK = "generation:try_again"
SHOW_LAST_IMAGE_CALLBACK = "history:last_image"


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CREATE_SESSION_TEXT, callback_data=CREATE_SESSION_CALLBACK)],
            [InlineKeyboardButton(text=HISTORY_TEXT, callback_data=HISTORY_CALLBACK)],
            [InlineKeyboardButton(text=HELP_TEXT, callback_data=HELP_CALLBACK)],
            [InlineKeyboardButton(text=SUPPORT_TEXT, callback_data=SUPPORT_CALLBACK)],
        ],
    )


def after_generation_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=CREATE_AGAIN_TEXT, callback_data=CREATE_AGAIN_CALLBACK)],
            [InlineKeyboardButton(text=MAIN_MENU_TEXT, callback_data=MAIN_MENU_CALLBACK)],
            [InlineKeyboardButton(text=SUPPORT_TEXT, callback_data=SUPPORT_CALLBACK)],
        ],
    )


def retry_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=TRY_AGAIN_TEXT, callback_data=TRY_AGAIN_CALLBACK)],
            [InlineKeyboardButton(text=MAIN_MENU_TEXT, callback_data=MAIN_MENU_CALLBACK)],
        ],
    )


def history_keyboard(has_completed_generation: bool) -> InlineKeyboardMarkup:
    inline_keyboard = []
    if has_completed_generation:
        inline_keyboard.append(
            [
                InlineKeyboardButton(
                    text=SHOW_LAST_IMAGE_TEXT,
                    callback_data=SHOW_LAST_IMAGE_CALLBACK,
                )
            ]
        )
    inline_keyboard.append([InlineKeyboardButton(text=MAIN_MENU_TEXT, callback_data=MAIN_MENU_CALLBACK)])
    return InlineKeyboardMarkup(inline_keyboard=inline_keyboard)


def prompt_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=MAIN_MENU_TEXT, callback_data=MAIN_MENU_CALLBACK)],
            [InlineKeyboardButton(text=SUPPORT_TEXT, callback_data=SUPPORT_CALLBACK)],
        ],
    )
