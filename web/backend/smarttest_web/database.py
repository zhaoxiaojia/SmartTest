from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
import sqlite3

from mysql.connector.pooling import MySQLConnectionPool

from .config import DatabaseSettings
from .queries import ensure_readonly_sql

_TRANSACTIONS = ContextVar("web-database-transactions", default={})

class WebDatabase:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._key = str(self.path.resolve()).casefold()

    @contextmanager
    def connect(self):
        active = _TRANSACTIONS.get().get(self._key)
        if active is not None:
            yield active
            return
        connection = sqlite3.connect(self.path, timeout=5)
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("PRAGMA busy_timeout = 5000")
            yield connection
        finally:
            connection.close()

    @contextmanager
    def transaction(self):
        active = _TRANSACTIONS.get().get(self._key)
        if active is not None:
            yield active
            return
        with self.connect() as connection:
            token = _TRANSACTIONS.set({**_TRANSACTIONS.get(), self._key: connection})
            try:
                connection.execute("BEGIN IMMEDIATE")
                yield connection
            except Exception:
                connection.rollback()
                raise
            else:
                connection.commit()
            finally:
                _TRANSACTIONS.reset(token)


class ReadonlyDatabase:
    def __init__(self, settings: DatabaseSettings):
        self._pool = MySQLConnectionPool(
            pool_name="smarttest_wifi_readonly", pool_size=settings.pool_size,
            pool_reset_session=True, host=settings.host, port=settings.port,
            user=settings.user, password=settings.password, database=settings.database,
        )

    def select(self, sql: str, params=()) -> list[dict]:
        ensure_readonly_sql(sql)
        connection = self._pool.get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            try:
                cursor.execute(sql, tuple(params))
                return cursor.fetchall()
            finally:
                cursor.close()
        finally:
            connection.close()
