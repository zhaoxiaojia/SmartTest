"""Repository-level SmartTest development, check, and packaging orchestrator."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "support" / "scripts"


def _python() -> str:
    candidate = ROOT / ".venv" / ("Scripts/python.exe" if sys.platform.startswith("win") else "bin/python")
    return str(candidate) if candidate.exists() else sys.executable


def _gradle() -> str:
    return str(ROOT / "mobile" / "android" / ("gradlew.bat" if sys.platform.startswith("win") else "gradlew"))


def _npm() -> str:
    return shutil.which("npm.cmd" if sys.platform.startswith("win") else "npm") or "npm"


PACKAGE_COMMANDS = {
    "mobile": lambda: [_python(), str(SCRIPTS / "script-build-apk.py")],
    "client": lambda: [_python(), str(SCRIPTS / "script-build-installer.py")],
    "tool": lambda: [_python(), str(SCRIPTS / "script-build-tool-portable.py")],
}
PACKAGE_ORDER = ("mobile", "client", "tool")


def _run(command, *, runner, cwd=ROOT, env=None):
    options = {"cwd": str(cwd), "check": True}
    if env is not None:
        options["env"] = env
    runner([str(part) for part in command], **options)


def package(target: str, runner=subprocess.run) -> None:
    targets = PACKAGE_ORDER if target == "all" else (target,)
    for item in targets:
        print(f"[package] {item}")
        _run(PACKAGE_COMMANDS[item](), runner=runner)


def check(target: str, runner=subprocess.run) -> None:
    targets = ("client", "web", "mobile") if target == "all" else (target,)
    _run([_python(), str(ROOT / "support/ci/check_product_boundaries.py")], runner=runner)
    for item in targets:
        print(f"[check] {item}")
        if item == "client":
            _run([_python(), "-m", "compileall", "-q", "client", "support"], runner=runner)
            _run([_python(), "-m", "pytest", "support/ci/test_smarttest_cli.py", "support/ci/test_check_product_boundaries.py", "-q"], runner=runner)
        elif item == "web":
            backend_env = os.environ.copy()
            existing_python_path = backend_env.get("PYTHONPATH", "").strip()
            backend_env["PYTHONPATH"] = os.pathsep.join(
                part for part in (str(ROOT), existing_python_path) if part
            )
            _run(
                [_python(), "-m", "pytest", "tests", "-q"],
                runner=runner,
                cwd=ROOT / "web/backend",
                env=backend_env,
            )
            for script in ("test", "lint", "build"):
                _run([_npm(), "run", script], runner=runner, cwd=ROOT / "web/frontend")
        else:
            _run([_gradle(), ":app:testDebugUnitTest"], runner=runner, cwd=ROOT / "mobile/android")


def _dev_plan(target: str):
    client = ([_python(), str(ROOT / "client/app/main.py")], ROOT)
    backend = ([_python(), "-m", "uvicorn", "smarttest_web.app:app", "--app-dir", "web/backend", "--reload", "--port", "8000", "--no-access-log"], ROOT)
    frontend = ([_npm(), "run", "dev"], ROOT / "web/frontend")
    mobile = ([_gradle(), ":app:assembleDebug"], ROOT / "mobile/android")
    if target == "client": return [], [client], {"Client": "desktop window"}
    if target == "web": return [], [backend, frontend], {"Web API": "http://127.0.0.1:8000", "Web UI": "Vite-reported address"}
    if target == "mobile": return [mobile], [], {"Mobile": "mobile/android/app/build/outputs/apk/debug"}
    return [mobile], [backend, frontend, client], {
        "Client": "desktop window", "Web API": "http://127.0.0.1:8000", "Web UI": "Vite-reported address"
    }


def dev(target: str) -> None:
    processes = []
    bootstrap, process_specs, addresses = _dev_plan(target)
    print(" | ".join(f"{name}: {address}" for name, address in addresses.items()))
    try:
        for command, cwd in bootstrap:
            subprocess.run(command, cwd=cwd, check=True)
        for command, cwd in process_specs:
            processes.append(subprocess.Popen(command, cwd=cwd))
        while processes:
            for process in processes:
                exit_code = process.poll()
                if exit_code is not None:
                    if exit_code:
                        raise SystemExit(exit_code)
                    return
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        for process in processes:
            if process.poll() is None:
                process.terminate()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    dev_parser = commands.add_parser("dev")
    dev_parser.add_argument("target", choices=("client", "web", "mobile", "all"))
    check_parser = commands.add_parser("check")
    check_parser.add_argument("target", choices=("client", "web", "mobile", "all"))
    package_parser = commands.add_parser("package")
    package_parser.add_argument("target", choices=("client", "tool", "mobile", "all"))
    return parser


def main(argv=None, runner=subprocess.run) -> int:
    parser = _parser()
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:2] == ["package", "web"]:
        parser.error("Web does not provide a release package; use 'check web' or 'dev web'.")
    args = parser.parse_args(arguments)
    if args.command == "dev":
        dev(args.target)
    elif args.command == "check":
        check(args.target, runner)
    else:
        package(args.target, runner)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
