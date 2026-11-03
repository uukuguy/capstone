"""Run cleanup without replacing an active execution failure."""
import logging
import sys
from collections.abc import Callable

from .native_failure_origin import native_failure_origin


def run_runtime_cleanup(action: Callable[[], object], *, operation: str) -> None:
    original = sys.exception()
    try:
        action()
    except Exception as error:
        logging.getLogger(__name__).error(
            'Runtime cleanup failed; operation=%s; exception_type=%s; origin=%s',
            operation, type(error).__name__, native_failure_origin(error))
        if original is None:
            raise
