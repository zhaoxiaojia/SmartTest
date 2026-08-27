import pytest


class MemoryCredentialStore:
    def __init__(self): self.values = {}
    def write(self, reference, username, password): self.values[reference] = (username, password)
    def read(self, reference): return self.values[reference]
    def delete(self, reference): self.values.pop(reference, None)


@pytest.fixture(autouse=True)
def isolate_server_credentials(monkeypatch):
    import smarttest_web.session as session_module
    stores = {}
    monkeypatch.setattr(
        session_module, "create_credential_store",
        lambda path: stores.setdefault(str(path), MemoryCredentialStore()),
    )
