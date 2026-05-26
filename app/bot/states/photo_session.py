from aiogram.fsm.state import State, StatesGroup


class PhotoSessionForm(StatesGroup):
    waiting_for_prompt = State()
    generating = State()
