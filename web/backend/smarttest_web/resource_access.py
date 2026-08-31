from __future__ import annotations

import time

from .schema import ensure_component_schema


class ResourceAccess:
    """Last remotely confirmed resources for one account and one live Web session."""

    def __init__(self, database, account, platform, session_hash, *, now=time.time):
        self.database, self.account, self.platform = database, account, platform
        self.session_hash, self._now = session_hash, now
        ensure_component_schema(database, component="resource_access", version=1,
            drop_tables=("web_resource_access",), statements=(
                """CREATE TABLE IF NOT EXISTS web_resource_access (
                    account TEXT NOT NULL, platform TEXT NOT NULL, kind TEXT NOT NULL,
                    resource_id TEXT NOT NULL, capability TEXT NOT NULL, scope TEXT NOT NULL,
                    confirmed_at REAL NOT NULL,
                    PRIMARY KEY(account,platform,kind,resource_id,capability,scope))""",
            ))

    def require_active(self):
        with self.database.connect() as connection:
            valid = connection.execute(
                """SELECT 1 FROM web_sessions WHERE token_hash=? AND username=?
                   AND revoked_at IS NULL AND expires_at>?""",
                (self.session_hash, self.account, self._now()),
            ).fetchone()
        if not valid:
            raise PermissionError("reauthentication_required")

    def ids(self, kind, capability):
        self.require_active()
        with self.database.connect() as connection:
            return {row[0] for row in connection.execute(
                "SELECT resource_id FROM web_resource_access WHERE account=? AND platform=? AND kind=? AND capability=?",
                (self.account, self.platform, kind, capability),
            )}

    def allows(self, kind, resource_id, capability):
        return str(resource_id) in self.ids(kind, capability)

    def scopes(self, kind, resource_id, capability):
        self.require_active()
        with self.database.connect() as connection:
            return {row[0] for row in connection.execute(
                "SELECT scope FROM web_resource_access WHERE account=? AND platform=? AND kind=? AND resource_id=? AND capability=?",
                (self.account, self.platform, kind, str(resource_id), capability),
            )}

    def require(self, kind, resource_id, capability):
        if not self.allows(kind, resource_id, capability):
            raise PermissionError("permission_denied")

    def publish(self, grants, write, *, replace_scopes=()):
        grants = tuple(grants)
        with self.database.transaction() as connection:
            self.require_active()
            retained = {str(key) for kind, key, capability, _ in grants if kind == 'project' and capability == 'catalog'}
            removed = set()
            for scope in replace_scopes:
                removed.update(row[0] for row in connection.execute(
                    "SELECT resource_id FROM web_resource_access WHERE account=? AND platform=? AND kind='project' AND capability='catalog' AND scope=?",
                    (self.account, self.platform, scope)))
            for key in removed - retained:
                connection.execute(
                    "DELETE FROM web_resource_access WHERE account=? AND platform=? AND ((kind='project' AND resource_id=?) OR scope=?)",
                    (self.account, self.platform, key, f'{key}:evidence'))
            connection.executemany(
                "DELETE FROM web_resource_access WHERE account=? AND platform=? AND scope=?",
                ((self.account, self.platform, scope) for scope in replace_scopes),
            )
            result = write()
            connection.executemany(
                "INSERT OR REPLACE INTO web_resource_access VALUES(?,?,?,?,?,?,?)",
                ((self.account, self.platform, kind, str(key), capability, scope, self._now())
                 for kind, key, capability, scope in grants),
            )
            return result

    def revoke(self, kind, resource_id, capability=None):
        with self.database.transaction() as connection:
            self.require_active()
            connection.execute(
                "DELETE FROM web_resource_access WHERE account=? AND platform=? AND kind=? AND resource_id=?"
                + (" AND capability=?" if capability else ""),
                (self.account, self.platform, kind, str(resource_id)) + ((capability,) if capability else ()),
            )


def remote_status(error):
    while error is not None:
        status = getattr(getattr(error, "response", None), "status_code", None)
        if status is not None:
            return status
        error = error.__cause__
    return None
