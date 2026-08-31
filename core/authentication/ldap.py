from __future__ import annotations

import os
from typing import Any

from core.logging import smart_log

try:
    from ldap3 import ALL, NTLM, SUBTREE, Connection, Server
    from ldap3.core.exceptions import LDAPException
except ImportError:  # pragma: no cover - runtime dependency
    ALL = NTLM = SUBTREE = Connection = Server = None

    class LDAPException(Exception):
        pass


class LdapAuthenticator:
    """Shared LDAP bind and identity owner used by Client and Web."""

    def __init__(self, *, host=None, domain=None, server_factory=Server,
                 connection_factory=Connection, authentication=NTLM,
                 get_info=ALL, subtree=SUBTREE, platform="client"):
        self.host = (host or os.getenv("AMLOGIC_LDAP_HOST", "ldap.amlogic.com")).strip()
        self.domain = domain or os.getenv("AMLOGIC_LDAP_DOMAIN", "AMLOGIC")
        self._server = server_factory
        self._connection = connection_factory
        self._authentication = authentication
        self._get_info = get_info
        self._subtree = subtree
        self._platform = platform

    def authenticate(self, username: str, password: str) -> dict[str, Any]:
        clean_username = (username or "").strip()
        if not clean_username or not password:
            return {"success": False, "username": "", "code": "invalid_credentials", "detail": "username_or_password_empty"}
        if not all((self._server, self._connection, self._authentication, self._get_info)):
            return {"success": False, "username": "", "code": "ldap_unavailable", "detail": "ldap3_not_installed"}
        domain_user = clean_username if "\\" in clean_username or "@" in clean_username else f"{self.domain}\\{clean_username}"
        connection = None
        try:
            server = self._server(self.host, get_info=self._get_info)
            connection = self._connection(server, user=domain_user, password=password, authentication=self._authentication)
            if not connection.bind():
                smart_log("LDAP bind failed (username=%s, server=%s)", domain_user, self.host,
                          platform=self._platform, domain="auth", source="LdapAuthenticator", level="warning")
                result = connection.result or {}
                detail = " | ".join(str(result.get(key) or "").strip() for key in ("description", "message") if str(result.get(key) or "").strip())
                return {"success": False, "username": "", "code": "invalid_credentials", "detail": detail or "ldap_bind_failed"}
            identity = self._identity(connection, clean_username)
            smart_log("LDAP bind success (username=%s, server=%s)", domain_user, self.host,
                      platform=self._platform, domain="auth", source="LdapAuthenticator")
            return {"success": True, "username": clean_username, "detail": "", **identity}
        except LDAPException as exc:
            smart_log("LDAP connection unavailable (username=%s, server=%s, error=%s)", clean_username, self.host,
                      type(exc).__name__, platform=self._platform, domain="auth", source="LdapAuthenticator", level="error")
            return {"success": False, "username": "", "code": "ldap_unavailable", "detail": type(exc).__name__}
        except Exception as exc:  # noqa: BLE001
            smart_log("LDAP connection failed (username=%s, server=%s, error=%s)", clean_username, self.host,
                      type(exc).__name__, platform=self._platform, domain="auth", source="LdapAuthenticator", level="error")
            return {"success": False, "username": "", "code": "ldap_unavailable", "detail": type(exc).__name__}
        finally:
            if connection is not None:
                try:
                    connection.unbind()
                except Exception:  # noqa: BLE001
                    pass

    def _identity(self, connection, username):
        if self._subtree is None:
            return {"display_name": "", "avatar_bytes": b""}
        contexts = list((connection.server.info.other or {}).get("defaultNamingContext") or [])
        if not contexts:
            return {"display_name": "", "avatar_bytes": b""}
        account = username.split("\\")[-1].split("@")[0].strip()
        escaped_account = _escape(account)
        escaped_username = _escape(username)
        if not connection.search(search_base=str(contexts[0]),
                                 search_filter=f"(|(sAMAccountName={escaped_account})(userPrincipalName={escaped_username})(mail={escaped_username}))",
                                 search_scope=self._subtree,
                                 attributes=["displayName", "thumbnailPhoto", "jpegPhoto"], size_limit=1) or not connection.entries:
            return {"display_name": "", "avatar_bytes": b""}
        entry = connection.entries[0]
        attrs = {name: entry[name].value if name in entry else None for name in ("displayName", "thumbnailPhoto", "jpegPhoto")}
        return ldap_identity_from_attributes(attrs)


def _escape(value):
    return str(value).replace("\\", r"\5c").replace("*", r"\2a").replace("(", r"\28").replace(")", r"\29").replace("\0", r"\00")


def ldap_identity_from_attributes(attributes):
    avatar = next((value[0] if isinstance(value, list) and value and isinstance(value[0], bytes) else value
                   for value in (attributes.get("thumbnailPhoto"), attributes.get("jpegPhoto"))
                   if isinstance(value, bytes) or (isinstance(value, list) and value and isinstance(value[0], bytes))), b"")
    return {"display_name": str(attributes.get("displayName") or "").strip(), "avatar_bytes": avatar}
