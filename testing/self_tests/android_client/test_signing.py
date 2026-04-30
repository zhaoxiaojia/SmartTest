from __future__ import annotations

import os
import time

import android_client


def test_sign_privileged_apk_uses_existing_platform_apk_without_signing_files(tmp_path, monkeypatch) -> None:
    source_apk = tmp_path / "app-debug.apk"
    target_apk = tmp_path / "app-debug-platform.apk"
    source_apk.write_bytes(b"unsigned")
    target_apk.write_bytes(b"signed")
    now = time.time()
    os.utime(target_apk, (now - 10, now - 10))
    os.utime(source_apk, (now, now))
    monkeypatch.setattr(android_client, "_platform_signing_available", lambda: False)

    assert android_client.sign_privileged_apk(input_apk_path=source_apk, output_apk_path=target_apk) == target_apk
