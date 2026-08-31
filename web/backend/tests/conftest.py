import pytest
from types import SimpleNamespace


class MemoryCredentialStore:
    def __init__(self): self.values = {}
    def write(self, reference, username, password): self.values[reference] = (username, password)
    def read(self, reference): return self.values[reference]
    def delete(self, reference): self.values.pop(reference, None)


def confirmed_access(database, projects=(), pages=(), account="coco"):
    """Seed a previously confirmed account in the real SQLite boundary."""
    from smarttest_web.session import PersistentSessionStore
    sessions = PersistentSessionStore(path=database.path, credential_store=MemoryCredentialStore())
    token = sessions.create(account, "test")
    access = sessions.resource_access(token, "confluence:https://confluence.amlogic.com", database)
    grants = [("project", project_id, capability, "DOPL") for project_id in projects
              for capability in ("catalog", "roles", "evidence")]
    grants += [("page", page_id, "metadata", "P1:evidence") for page_id in pages]
    access.publish(grants, lambda: None)
    return access


@pytest.fixture(autouse=True)
def isolate_server_credentials(monkeypatch, tmp_path):
    import smarttest_web.session as session_module
    database_path = tmp_path / "isolated-smarttest-web.db"
    stores = {}
    monkeypatch.setattr(session_module, "default_web_database_path", lambda: database_path)
    monkeypatch.setattr(
        session_module, "create_credential_store",
        lambda path: stores.setdefault(str(path), MemoryCredentialStore()),
    )
    return SimpleNamespace(root=tmp_path, database_path=database_path, credential_stores=stores)
