from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


def retry(operation: Callable[[], T], retries: int, delay_sec: float = 1.0) -> T:
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(delay_sec * (attempt + 1))

    if last_error is None:
        raise RuntimeError("retry() failed without exception")
    raise last_error
