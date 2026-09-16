import pytest
from types import SimpleNamespace


class MemoryCredentialStore:
    def __init__(self): self.values = {}
    def write(self, reference, username, password): self.values[reference] = (username, password)
    def read(self, reference):
        from smarttest_web.credentials import CredentialMissingError
        if reference not in self.values:
            raise CredentialMissingError("credential not found")
        return self.values[reference]
    def delete(self, reference): self.values.pop(reference, None)


def confirmed_access(database, projects=(), pages=(), account="coco"):
    """Seed a previously confirmed account in the real SQLite boundary."""
    from smarttest_web.session import PersistentSessionStore
    sessions = PersistentSessionStore(path=database.path, credential_store=MemoryCredentialStore())
    token = sessions.create(account, "test")
    access = sessions.resource_access(token, "confluence:https://confluence.amlogic.com", database)
    from core.product_lines import PRODUCT_LINES
    grants = [("project", project_id, capability, PRODUCT_LINES[0].name) for project_id in projects
              for capability in ("catalog", "roles", "evidence")]
    grants += [("page", page_id, "metadata", "P1:evidence") for page_id in pages]
    access.publish(grants, lambda: None)
    return access


@pytest.fixture(autouse=True)
def isolate_server_credentials(monkeypatch, tmp_path):
    import smarttest_web.session as session_module
    import smarttest_web.app as app_module
    database_path = tmp_path / "isolated-smarttest-web.db"
    stores = {}
    monkeypatch.setattr(session_module, "default_web_database_path", lambda: database_path)
    monkeypatch.setattr(
        session_module, "create_credential_store",
        lambda path: stores.setdefault(str(path), MemoryCredentialStore()),
    )
    class NoopPersonnelRefresh:
        def schedule(self, account, password, owner_factory, **_context):
            return False
    monkeypatch.setattr(app_module, "default_confluence_personnel_refresh", NoopPersonnelRefresh)
    return SimpleNamespace(root=tmp_path, database_path=database_path, credential_stores=stores)
