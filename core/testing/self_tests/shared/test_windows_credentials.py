import pytest

from core.credentials.windows import (
    CredentialNotFoundError, WindowsCredentialStore, _PyWin32CredentialAdapter,
)


class NativeAdapter:
    def __init__(self):
        self.values = {}
        self.calls = []
        self.cleared = []
        self.fail_write = False
        self.read_blob = None

    def write_generic(self, target, username, password_blob):
        self.calls.append(("write", target))
        if self.fail_write:
            raise RuntimeError("native write failed")
        self.values[target] = (username, bytes(password_blob))

    def read_generic(self, target):
        self.calls.append(("read", target))
        if target not in self.values:
            raise CredentialNotFoundError(target)
        username, blob = self.values[target]
        return username, bytearray(self.read_blob if self.read_blob is not None else blob)

    def delete_generic(self, target):
        self.calls.append(("delete", target))
        if target not in self.values:
            raise CredentialNotFoundError(target)
        del self.values[target]

    def clear(self, blob):
        for index in range(len(blob)):
            blob[index] = 0
        self.cleared.append(bytes(blob))


def test_credential_store_uses_scoped_target_and_round_trips_unicode():
    native = NativeAdapter()
    store = WindowsCredentialStore(native)
    store.write("plan-a", "测试用户", "密碼-🔒")
    assert store.read("plan-a") == ("测试用户", "密碼-🔒")
    store.delete("plan-a")
    assert native.calls == [
        ("write", "SmartTest/ProjectWeeklyAudit/plan-a"),
        ("read", "SmartTest/ProjectWeeklyAudit/plan-a"),
        ("delete", "SmartTest/ProjectWeeklyAudit/plan-a"),
    ]
    assert native.cleared and set(native.cleared[-1]) <= {0}


def test_write_buffer_is_cleared_when_native_write_fails():
    native = NativeAdapter()
    native.fail_write = True
    with pytest.raises(RuntimeError, match="native write failed"):
        WindowsCredentialStore(native).write("plan-a", "user", "synthetic-secret")
    assert len(native.cleared) == 1
    assert set(native.cleared[0]) <= {0}


def test_read_buffer_is_cleared_when_password_decode_fails():
    native = NativeAdapter()
    native.values["SmartTest/ProjectWeeklyAudit/plan-a"] = ("user", b"placeholder")
    native.read_blob = b"\xff"
    with pytest.raises(UnicodeDecodeError):
        WindowsCredentialStore(native).read("plan-a")
    assert len(native.cleared) == 1
    assert native.cleared[0] == b"\x00"


def test_missing_credential_is_actionable_without_secret_material():
    store = WindowsCredentialStore(NativeAdapter())
    with pytest.raises(CredentialNotFoundError, match="missing-plan") as captured:
        store.read("missing-plan")
    assert "password" not in str(captured.value).casefold()


def test_pywin32_adapter_uses_unicode_blob_and_normalizes_read_value():
    class Api:
        CRED_TYPE_GENERIC = 1
        CRED_PERSIST_LOCAL_MACHINE = 2

        def __init__(self):
            self.value = None

        def CredWrite(self, value, flags):
            assert flags == 0
            assert isinstance(value["CredentialBlob"], str)
            self.value = value

        def CredRead(self, target, credential_type, flags):
            assert (target, credential_type, flags) == ("target", 1, 0)
            return self.value

    adapter = _PyWin32CredentialAdapter.__new__(_PyWin32CredentialAdapter)
    adapter._api = Api()
    adapter.write_generic(
        "target", "user", bytearray("密碼-🔐".encode("utf-16-le")),
    )

    username, blob = adapter.read_generic("target")

    assert username == "user"
    assert bytes(blob).decode("utf-16-le") == "密碼-🔐"
