import pytest
from types import SimpleNamespace


class MemoryCredentialStore:
    def __init__(self): self.values = {}
    def write(self, reference, username, password): self.values[reference] = (username, password)
    def read(self, reference): return self.values[reference]
    def delete(self, reference): self.values.pop(reference, None)


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
