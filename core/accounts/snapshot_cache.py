from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
from threading import RLock
import time

SCHEMA_VERSION = 1
DEFAULT_MAX_BYTES = 2_000_000
DEFAULT_MAX_FILES = 8
FILE_PREFIX = "account-snapshot-"


@dataclass(frozen=True)
class AccountSnapshot:
    fetched_at: datetime
    payload: dict


class AccountScopedSnapshotCache:
    """Bounded LRU cache; max_files applies per domain/source owner directory."""

    def __init__(self, root, *, max_bytes=DEFAULT_MAX_BYTES, max_files=DEFAULT_MAX_FILES):
        self.root = Path(root).resolve()
        self.max_bytes = int(max_bytes)
        self.max_files = int(max_files)
        self._lock = RLock()

    @staticmethod
    def identity(value):
        return hashlib.sha256(
            str(value).strip().casefold().encode("utf-8"),
        ).hexdigest()

    def load(self, domain, source, account):
        with self._lock:
            path = self._path(domain, source, account)
            try:
                if not path.is_file() or path.stat().st_size > self.max_bytes:
                    return None
                value = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(value, dict):
                    return None
                if (
                    value.get("schema_version") != SCHEMA_VERSION
                    or value.get("domain_hash") != self.identity(domain)
                    or value.get("source_hash") != self.identity(source)
                    or value.get("account_hash") != self.identity(account)
                    or not isinstance(value.get("payload"), dict)
                    or not isinstance(value.get("fetched_at"), str)
                ):
                    return None
                fetched = datetime.fromisoformat(value["fetched_at"])
                if fetched.tzinfo is None:
                    return None
                self._touch_newest(path)
                return AccountSnapshot(fetched, value["payload"])
            except (AttributeError, KeyError, OSError, ValueError, TypeError):
                return None

    def save(self, domain, source, account, payload, *, fetched_at=None):
        if not isinstance(payload, dict):
            raise ValueError("Snapshot payload must be an object")
        timestamp = fetched_at or datetime.now(timezone.utc)
        if not isinstance(timestamp, datetime) or timestamp.tzinfo is None:
            raise ValueError("Snapshot timestamp must be timezone-aware")
        value = {
            "schema_version": SCHEMA_VERSION,
            "domain_hash": self.identity(domain),
            "source_hash": self.identity(source),
            "account_hash": self.identity(account),
            "fetched_at": timestamp.isoformat(),
            "payload": payload,
        }
        encoded = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        if len(encoded.encode("utf-8")) > self.max_bytes:
            raise ValueError("Snapshot exceeds size limit")

        with self._lock:
            path = self._path(domain, source, account)
            path.parent.mkdir(parents=True, exist_ok=True)
            handle, temporary = tempfile.mkstemp(
                prefix=FILE_PREFIX, suffix=".tmp", dir=path.parent,
            )
            try:
                with os.fdopen(handle, "w", encoding="utf-8") as stream:
                    stream.write(encoded)
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary, path)
                self._fsync_directory(path.parent)
            finally:
                if os.path.exists(temporary):
                    os.unlink(temporary)
            self._touch_newest(path)
            self._evict(path.parent)

    @staticmethod
    def _touch_newest(path):
        existing = [
            candidate.stat().st_mtime_ns
            for candidate in path.parent.glob(f"{FILE_PREFIX}*.json")
            if candidate != path
        ]
        newest = max(existing, default=0)
        timestamp = max(time.time_ns(), newest + 2_000_000_000)
        os.utime(path, ns=(timestamp, timestamp))

    def _evict(self, directory):
        files = []
        for candidate in directory.glob(f"{FILE_PREFIX}*.json"):
            try:
                resolved = candidate.resolve()
                if resolved.parent != directory.resolve():
                    continue
                files.append((candidate.stat().st_mtime, candidate))
            except OSError:
                continue
        for _, old in sorted(files, reverse=True)[self.max_files:]:
            try:
                old.unlink()
            except OSError:
                pass

    def _path(self, domain, source, account):
        owner_hash = hashlib.sha256(
            (
                str(domain).strip().casefold()
                + "\0"
                + str(source).strip().casefold()
            ).encode("utf-8"),
        ).hexdigest()
        directory = (
            self.root
            / f"owner-{owner_hash}"
        ).resolve()
        if self.root != directory and self.root not in directory.parents:
            raise ValueError("Invalid cache path")
        return directory / f"{FILE_PREFIX}{self.identity(account)[:32]}.json"

    @staticmethod
    def _fsync_directory(directory):
        try:
            descriptor = os.open(str(directory), os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        except OSError:
            pass
        finally:
            os.close(descriptor)
