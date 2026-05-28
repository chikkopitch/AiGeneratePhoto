from aiogram.fsm.state import State, StatesGroup


class PhotoSessionForm(StatesGroup):
    waiting_for_prompt = State()
    waiting_for_edit_prompt = State()
    generating = State()
