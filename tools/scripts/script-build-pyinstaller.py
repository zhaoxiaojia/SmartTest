import shutil
import os
import subprocess

import env

if __name__ == "__main__":
    scripts_dir = os.path.dirname(os.path.abspath(__file__))
    buildDir = os.path.join('.', 'build')
    distDir = os.path.join('.', 'dist')
    try:
        shutil.rmtree(buildDir)
        shutil.rmtree(distDir)
    except FileNotFoundError:
        pass

    # Keep build deterministic and local: refresh i18n and QRC outputs, then package.
    subprocess.run([env.python(), os.path.join(scripts_dir, 'script-update-translations.py')], check=True)
    subprocess.run([env.python(), os.path.join(scripts_dir, 'script-update-resource.py')], check=True)
    subprocess.run([env.python(), os.path.join(scripts_dir, 'script-build-test-catalog.py')], check=True)

    build_env = env.environment()
    build_env["SMARTTEST_REPO_ROOT"] = os.path.abspath(".")
    subprocess.run(
        [env.pyinstaller(), "--clean", "-y", os.path.join(".", "tools", "packaging", "pyinstaller", "main.spec")],
        env=build_env,
        check=True,
    )
