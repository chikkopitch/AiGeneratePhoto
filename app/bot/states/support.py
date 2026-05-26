from aiogram.fsm.state import State, StatesGroup


class SupportForm(StatesGroup):
    waiting_for_message = State()
