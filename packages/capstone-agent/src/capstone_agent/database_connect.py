"""Bounded connection recovery for a cold hosted PostgreSQL service."""
from __future__ import annotations

import time
import psycopg


def connect_database(dsn: str, *, sleep=time.sleep, **kwargs):
    # Only connection establishment is retried. Never replay a transaction.
    for attempt in range(5):
        try:
            return psycopg.connect(dsn, connect_timeout=3, **kwargs)
        except psycopg.OperationalError as error:
            state = error.sqlstate
            if attempt == 4 or (state is not None and not state.startswith('08') and state != '57P03'):
                raise
            sleep(0.2 * 2 ** attempt)
    raise AssertionError('unreachable')
