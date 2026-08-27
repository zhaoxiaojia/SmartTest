from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import secrets
import sqlite3
import sys

from core.credentials.windows import CredentialNotFoundError, WindowsCredentialError, WindowsCredentialStore

WEB_CREDENTIAL_TARGET_PREFIX = "SmartTest/WebSession/"

class CredentialStoreError(RuntimeError):
    pass


class CredentialMissingError(CredentialStoreError):
    pass


class WindowsWebCredentialStore:
    def __init__(self, native=None):
        self._owner = WindowsCredentialStore(native=native, target_prefix=WEB_CREDENTIAL_TARGET_PREFIX)

    def write(self, credential_ref, username, password):
        try:
            self._owner.write(credential_ref, username, password)
        except WindowsCredentialError as exc:
            raise CredentialStoreError("Server credential storage failed.") from exc

    def read(self, credential_ref):
        try:
            return self._owner.read(credential_ref)
        except CredentialNotFoundError as exc:
            raise CredentialMissingError("Server credential was not found.") from exc
        except WindowsCredentialError as exc:
            raise CredentialStoreError("Server credential recovery failed.") from exc

    def delete(self, credential_ref):
        try:
            self._owner.delete(credential_ref)
        except CredentialNotFoundError:
            return
        except WindowsCredentialError as exc:
            raise CredentialStoreError("Server credential deletion failed.") from exc


class LinuxEncryptedCredentialStore:
    KEY_VERSION = 1

    def __init__(self, path, *, environ=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._environ = os.environ if environ is None else environ
        with self._connect() as connection:
            connection.execute("""
                CREATE TABLE IF NOT EXISTS web_credentials (
                    credential_ref TEXT PRIMARY KEY,
                    nonce BLOB NOT NULL,
                    ciphertext BLOB NOT NULL,
                    key_version INTEGER NOT NULL
                )
            """)

    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.execute("PRAGMA busy_timeout=5000")
        return connection

    def _key(self):
        value = self._environ.get("SMARTTEST_WEB_CREDENTIAL_KEY", "")
        try:
            key = base64.b64decode(value.encode("ascii"), altchars=b"-_", validate=True)
        except (ValueError, UnicodeError) as exc:
            raise CredentialStoreError("Server credential key is invalid.") from exc
        if len(key) != 32:
            raise CredentialStoreError("Server credential key must decode to 32 bytes.")
        return key

    @staticmethod
    def _aad(credential_ref, version):
        return f"smarttest-web:{version}:{credential_ref}".encode("utf-8")

    def write(self, credential_ref, username, password):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        nonce = secrets.token_bytes(12)
        payload = json.dumps({"username": str(username), "password": str(password)},
                             ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ciphertext = AESGCM(self._key()).encrypt(nonce, payload, self._aad(credential_ref, self.KEY_VERSION))
        with self._connect() as connection:
            connection.execute("""
                INSERT INTO web_credentials(credential_ref,nonce,ciphertext,key_version) VALUES(?,?,?,?)
                ON CONFLICT(credential_ref) DO UPDATE SET nonce=excluded.nonce,
                  ciphertext=excluded.ciphertext,key_version=excluded.key_version
            """, (credential_ref, nonce, ciphertext, self.KEY_VERSION))

    def read(self, credential_ref):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        with self._connect() as connection:
            row = connection.execute(
                "SELECT nonce,ciphertext,key_version FROM web_credentials WHERE credential_ref=?",
                (credential_ref,),
            ).fetchone()
        if row is None:
            raise CredentialMissingError("Server credential was not found.")
        if row[2] != self.KEY_VERSION:
            raise CredentialStoreError("Server credential key version is unsupported.")
        try:
            payload = AESGCM(self._key()).decrypt(row[0], row[1], self._aad(credential_ref, row[2]))
            value = json.loads(payload.decode("utf-8"))
            return str(value["username"]), str(value["password"])
        except CredentialStoreError:
            raise
        except Exception as exc:
            raise CredentialStoreError("Server credential recovery failed.") from exc

    def delete(self, credential_ref):
        with self._connect() as connection:
            connection.execute("DELETE FROM web_credentials WHERE credential_ref=?", (credential_ref,))


def create_credential_store(path, *, platform_name=None, environ=None, windows_native=None):
    platform_name = platform_name or sys.platform
    if platform_name == "win32":
        return WindowsWebCredentialStore(native=windows_native)
    return LinuxEncryptedCredentialStore(path, environ=environ)
