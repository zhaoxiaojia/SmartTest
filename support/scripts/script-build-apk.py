import os
from pathlib import Path
import shutil
import subprocess

import env


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _gradle_command(gradlew: Path) -> list[str]:
    if os.name == "nt" or os.access(gradlew, os.X_OK):
        return [str(gradlew)]
    return ["sh", str(gradlew)]


def _build_env() -> dict[str, str]:
    build_env = os.environ.copy()
    if build_env.get("JAVA_HOME"):
        return build_env
    homebrew_jdk17 = Path("/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home")
    if homebrew_jdk17.exists():
        build_env["JAVA_HOME"] = str(homebrew_jdk17)
        build_env["PATH"] = f"{homebrew_jdk17 / 'bin'}{os.pathsep}{build_env.get('PATH', '')}"
    return build_env


def _build_android_client(repo_root: Path) -> Path:
    android_dir = repo_root / "android_client"
    gradlew = android_dir / ("gradlew.bat" if os.name == "nt" else "gradlew")
    subprocess.run([*_gradle_command(gradlew), ":app:assembleDebug"], cwd=android_dir, env=_build_env(), check=True)
    subprocess.run(
        [env.python(), "-c", "import android_client; android_client.sign_privileged_apk()"],
        cwd=repo_root,
        check=True,
    )
    return android_dir / "app" / "build" / "outputs" / "apk" / "debug" / "app-debug-platform.apk"


def _copy_apk(repo_root: Path, apk_path: Path) -> Path:
    output_dir = repo_root / "dist_installer"
    output_dir.mkdir(parents=True, exist_ok=True)
    if not apk_path.exists():
        raise SystemExit(f"Signed APK build output is missing: {apk_path}")
    output_path = output_dir / apk_path.name
    shutil.copy2(apk_path, output_path)
    return output_path


if __name__ == "__main__":
    root = _repo_root()
    signed_apk = _build_android_client(root)
    output = _copy_apk(root, signed_apk)
    print(f"Signed APK output: {output}")
