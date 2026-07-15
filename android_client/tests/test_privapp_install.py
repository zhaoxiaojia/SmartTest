from pathlib import Path
from subprocess import CompletedProcess

import android_client


def test_privapp_install_restores_system_package_for_user_zero(monkeypatch, tmp_path: Path):
    apk_path = tmp_path / "SmartTestMobile.apk"
    apk_path.write_bytes(b"signed-apk")
    install_probes = iter([False, True])
    adb_calls: list[tuple[str | None, list[str]]] = []

    monkeypatch.setattr(android_client, "_install_privileged_test_apk", lambda **_kwargs: None)
    monkeypatch.setattr(android_client, "is_test_apk_installed", lambda **_kwargs: next(install_probes))
    monkeypatch.setattr(
        android_client,
        "_run_adb",
        lambda *, adb_serial, args, **_kwargs: (
            adb_calls.append((adb_serial, args))
            or CompletedProcess(args, 0, "Package com.smarttest.mobile installed for user: 0\n", "")
        ),
    )
    monkeypatch.setattr(
        android_client,
        "_package_code_path",
        lambda **_kwargs: "/system/priv-app/SmartTestMobile/SmartTestMobile.apk",
    )
    monkeypatch.setattr(android_client, "_save_install_state", lambda _state: None)

    changed = android_client._ensure_privileged_install(
        adb_executable="adb",
        resolved_apk_path=apk_path,
        adb_serial="192.168.1.154:5555",
        current_hash="current-hash",
        state_key="state-key",
        install_state={},
        installed=False,
        code_path="",
        recorded_mode="privapp",
        recorded_hash="current-hash",
    )

    assert changed is True
    assert adb_calls == [
        (
            "192.168.1.154:5555",
            ["shell", "cmd", "package", "install-existing", "--user", "0", "com.smarttest.mobile"],
        )
    ]
