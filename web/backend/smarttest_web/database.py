from __future__ import annotations

from mysql.connector.pooling import MySQLConnectionPool

from .config import DatabaseSettings
from .queries import ensure_readonly_sql


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
