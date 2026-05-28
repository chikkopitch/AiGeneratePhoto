import logging

import pytest
from aiogram.fsm.storage.memory import MemoryStorage

from app.main import create_storage


def test_create_storage_uses_memory_storage(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO):
        storage = create_storage()

    assert isinstance(storage, MemoryStorage)
    assert "Using MemoryStorage for FSM" in caplog.text
