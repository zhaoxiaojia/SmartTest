import os
import subprocess
import sys
from pathlib import Path

import env


if __name__ == "__main__":
    scripts_dir = Path(__file__).resolve().parent
    repo_root = scripts_dir.parents[1]
    os.chdir(repo_root)

    dist_dir = repo_root / "build" / "client_runtime"

    # Keep build deterministic and local: refresh i18n and QRC outputs, then package.
    subprocess.run([env.python(), str(scripts_dir / "update_translations.py")], check=True)
    subprocess.run([env.python(), str(scripts_dir / "update_resource.py")], check=True)
    subprocess.run([env.python(), str(repo_root / "core/testing/scripts/build_test_catalog.py")], check=True)
    subprocess.run([env.python(), str(repo_root / "core/devtools/scripts/build_manifest.py")], check=True)

    build_env = env.environment()
    build_env["SMARTTEST_REPO_ROOT"] = str(repo_root)
    subprocess.run(
        [env.pyinstaller(), "--clean", "-y", "--distpath", str(dist_dir), str(repo_root / "client/packaging/pyinstaller/main.spec")],
        env=build_env,
        check=True,
    )
    if sys.platform.startswith("win"):
        subprocess.run([env.python(), str(scripts_dir / "build_python_runtime.py")], check=True)
    print(f"PyInstaller dist folder: {dist_dir}")
