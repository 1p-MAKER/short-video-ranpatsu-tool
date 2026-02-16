from __future__ import annotations

import logging
import sys

try:
    import structlog
except ImportError:  # pragma: no cover
    structlog = None


class FallbackLogger:
    def __init__(self, name: str = "short-video-ranpatsu-tool") -> None:
        self._logger = logging.getLogger(name)

    def info(self, event: str, **kwargs) -> None:
        self._logger.info(self._fmt(event, kwargs))

    def warning(self, event: str, **kwargs) -> None:
        self._logger.warning(self._fmt(event, kwargs))

    def exception(self, event: str, **kwargs) -> None:
        self._logger.exception(self._fmt(event, kwargs))

    def _fmt(self, event: str, kwargs: dict) -> str:
        if not kwargs:
            return event
        pairs = ", ".join(f"{k}={v}" for k, v in kwargs.items())
        return f"{event} | {pairs}"


def configure_logger() -> None:
    if structlog is None:
        logging.basicConfig(
            level=logging.INFO,
            stream=sys.stdout,
            format="%(asctime)s %(levelname)s %(message)s",
        )
        return

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger():
    if structlog is None:
        return FallbackLogger()
    return structlog.get_logger()
