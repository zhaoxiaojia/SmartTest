import os
import subprocess
from pathlib import Path

import env


if __name__ == "__main__":
    scripts_dir = Path(__file__).resolve().parent
    repo_root = scripts_dir.parents[1]
    os.chdir(repo_root)

    dist_dir = repo_root / "dist"

    # Keep build deterministic and local: refresh i18n and QRC outputs, then package.
    subprocess.run([env.python(), str(scripts_dir / "script-update-translations.py")], check=True)
    subprocess.run([env.python(), str(scripts_dir / "script-update-resource.py")], check=True)
    subprocess.run([env.python(), str(scripts_dir / "script-build-test-catalog.py")], check=True)
    subprocess.run([env.python(), str(scripts_dir / "script-build-manifest.py")], check=True)

    build_env = env.environment()
    build_env["SMARTTEST_REPO_ROOT"] = str(repo_root)
    subprocess.run(
        [env.pyinstaller(), "--clean", "-y", str(repo_root / "tools" / "packaging" / "pyinstaller" / "main.spec")],
        env=build_env,
        check=True,
    )
    subprocess.run([env.python(), str(scripts_dir / "script-build-python-runtime.py")], check=True)
    print(f"PyInstaller dist folder: {dist_dir}")
