"""Functions used by the API."""

# pylint: disable=W1203

import datetime
import logging
import time
from typing import Final

logger = logging.getLogger(__name__)


MINUTES_DAY: Final[int] = 1440
MINUTES_HOUR: Final[int] = 60


def _function_name(func: str) -> str:
    """Attemptt to retrieve function name for timeit."""
    return str(func).rsplit("at", 1)[0].replace("<function", "function: ").strip()


def timeit(func):
    """Decorator to output the time taken for a function"""

    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        end = time.perf_counter()
        elapsed = end - start
        func_name = _function_name(str(func))
        logger.info(f"Time taken: {elapsed:.6f} seconds ({func_name})")
        return result

    return wrapper


@timeit
def get_minutes(date_str_1: str, date_str_2: str) -> int:
    """Return minutes from two date strings."""
    date_object_1 = datetime.datetime.strptime(date_str_1, "%Y-%m-%d")
    date_object_2 = datetime.datetime.strptime(date_str_2, "%Y-%m-%d")
    time_diff = date_object_2 - date_object_1
    return int(time_diff.total_seconds() / 60)


def update_dict(index: dict, key: str, value) -> dict:
    """Update a dictionary of lists."""
    try:
        index[key].append(value)
    except KeyError:
        index[key] = [value]
    return index


def dedupe_dicts(index: dict) -> dict:
    """De-duplicate a dictionary of lists."""
    new_index = {}
    for key, value in index.items():
        new_index[key] = list(set(value))
    return new_index
