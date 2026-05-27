import logging
from typing import Any


LOG_RECORD_DEFAULTS: dict[str, Any] = {
    "telegram_id": "-",
    "generation_id": "-",
    "request_id": "-",
    "status": "-",
    "error_type": "-",
    "error_message": "-",
    "database_path": "-",
}


class ContextDefaultsFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in LOG_RECORD_DEFAULTS.items():
            if not hasattr(record, key):
                setattr(record, key, value)
        return True


def setup_logging(level: str) -> None:
    logging.basicConfig(
        level=level.upper(),
        format=(
            "%(asctime)s %(levelname)s %(name)s %(message)s "
            "telegram_id=%(telegram_id)s generation_id=%(generation_id)s "
            "request_id=%(request_id)s status=%(status)s error_type=%(error_type)s "
            "error_message=%(error_message)s database_path=%(database_path)s"
        ),
    )
    context_filter = ContextDefaultsFilter()
    root_logger = logging.getLogger()
    for handler in root_logger.handlers:
        handler.addFilter(context_filter)
