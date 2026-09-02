from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import json
import sqlite3
import time
from uuid import uuid4

from .database import WebDatabase


class NameConflictError(ValueError):
    pass


class RevisionConflictError(ValueError):
    pass


@dataclass(frozen=True)
class TestSuiteRecord:
    id: str
    owner_username: str
    owner_display_name: str
    name: str
    description: str
    visibility: str
    ordered_nodeids: tuple[str, ...]
    revision: int
    created_at: float
    updated_at: float


class TestSuiteRepository:
    __test__ = False
    def __init__(self, database: WebDatabase, *, now=time.time):
        self.database = database
        self._now = now
        with database.transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS test_suites ("
                "id TEXT PRIMARY KEY, owner_username TEXT NOT NULL, "
                "owner_display_name TEXT NOT NULL, name TEXT NOT NULL, "
                "description TEXT NOT NULL DEFAULT '', visibility TEXT NOT NULL "
                "CHECK (visibility IN ('private','shared')), "
                "ordered_nodeids_json TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1, "
                "created_at REAL NOT NULL, updated_at REAL NOT NULL, "
                "UNIQUE(owner_username,name))"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS ix_test_suites_visibility_updated "
                "ON test_suites(visibility,updated_at DESC)"
            )

    @staticmethod
    def _record(row) -> TestSuiteRecord:
        return TestSuiteRecord(
            id=row[0], owner_username=row[1], owner_display_name=row[2], name=row[3],
            description=row[4], visibility=row[5],
            ordered_nodeids=tuple(json.loads(row[6])), revision=int(row[7]),
            created_at=float(row[8]), updated_at=float(row[9]),
        )

    @staticmethod
    def _values(name: str, description: str, visibility: str,
                ordered_nodeids: Sequence[str]) -> tuple[str, str, str, str]:
        clean_name = str(name or "").strip()
        if not clean_name or visibility not in {"private", "shared"}:
            raise ValueError("invalid_input")
        ordered: list[str] = []
        for value in ordered_nodeids:
            nodeid = str(value or "").strip()
            if nodeid and nodeid not in ordered:
                ordered.append(nodeid)
        if not ordered:
            raise ValueError("invalid_input")
        return clean_name, str(description or ""), visibility, json.dumps(ordered, ensure_ascii=False)

    def _query(self, sql: str, params=()) -> list[TestSuiteRecord]:
        with self.database.connect() as connection:
            return [self._record(row) for row in connection.execute(sql, tuple(params)).fetchall()]

    def list_mine(self, username: str) -> list[TestSuiteRecord]:
        return self._query("SELECT * FROM test_suites WHERE owner_username=? ORDER BY updated_at DESC", (username,))

    def list_shared(self, username: str) -> list[TestSuiteRecord]:
        return self._query("SELECT * FROM test_suites WHERE visibility='shared' AND owner_username<>? ORDER BY updated_at DESC", (username,))

    def get_visible(self, suite_id: str, username: str) -> TestSuiteRecord | None:
        rows = self._query("SELECT * FROM test_suites WHERE id=? AND (owner_username=? OR visibility='shared')", (suite_id, username))
        return rows[0] if rows else None

    def create(self, *, owner_username: str, owner_display_name: str, name: str,
               description: str, visibility: str, ordered_nodeids: Sequence[str]) -> TestSuiteRecord:
        clean_name, description, visibility, encoded = self._values(name, description, visibility, ordered_nodeids)
        suite_id, timestamp = str(uuid4()), float(self._now())
        try:
            with self.database.transaction() as connection:
                connection.execute("INSERT INTO test_suites VALUES(?,?,?,?,?,?,?,?,?,?)",
                                   (suite_id, owner_username, owner_display_name, clean_name, description,
                                    visibility, encoded, 1, timestamp, timestamp))
        except sqlite3.IntegrityError as error:
            raise NameConflictError(clean_name) from error
        return self.get_visible(suite_id, owner_username)  # type: ignore[return-value]

    def update(self, suite_id: str, *, owner_username: str, revision: int, name: str,
               description: str, visibility: str, ordered_nodeids: Sequence[str]) -> TestSuiteRecord | None:
        clean_name, description, visibility, encoded = self._values(name, description, visibility, ordered_nodeids)
        timestamp = float(self._now())
        try:
            with self.database.transaction() as connection:
                owner = connection.execute("SELECT revision FROM test_suites WHERE id=? AND owner_username=?", (suite_id, owner_username)).fetchone()
                if owner is None:
                    return None
                if int(owner[0]) != int(revision):
                    raise RevisionConflictError(suite_id)
                connection.execute("UPDATE test_suites SET name=?,description=?,visibility=?,ordered_nodeids_json=?,revision=revision+1,updated_at=? WHERE id=? AND owner_username=?",
                                   (clean_name, description, visibility, encoded, timestamp, suite_id, owner_username))
        except sqlite3.IntegrityError as error:
            raise NameConflictError(clean_name) from error
        return self.get_visible(suite_id, owner_username)

    def delete(self, suite_id: str, *, owner_username: str) -> bool:
        with self.database.transaction() as connection:
            cursor = connection.execute("DELETE FROM test_suites WHERE id=? AND owner_username=?", (suite_id, owner_username))
            return cursor.rowcount > 0

    def copy(self, suite_id: str, *, reader_username: str, owner_display_name: str,
             name: str, visibility: str = "private") -> TestSuiteRecord | None:
        source = self.get_visible(suite_id, reader_username)
        if source is None:
            return None
        return self.create(owner_username=reader_username, owner_display_name=owner_display_name,
                           name=name, description=source.description, visibility=visibility,
                           ordered_nodeids=source.ordered_nodeids)
