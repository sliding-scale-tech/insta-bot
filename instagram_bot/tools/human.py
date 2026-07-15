"""Human-like delays for browser tools."""

import random
import time


def wait_human(min_seconds: float = 2, max_seconds: float = 5) -> None:
    delay = random.uniform(min_seconds, max_seconds)
    print(f"  ...waiting {delay:.1f}s")
    time.sleep(delay)
