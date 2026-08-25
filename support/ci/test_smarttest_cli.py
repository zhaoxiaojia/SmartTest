from pathlib import Path
import runpy
import subprocess
import sys

import pytest
from support import smarttest


def test_package_all_delegates_to_existing_owners_in_required_order():
    calls = []
    exit_code = smarttest.main(["package", "all"], runner=lambda command, **kwargs: calls.append(command))
    scripts = [Path(command[1]).name for command in calls]
    assert exit_code == 0
    assert scripts == ["script-build-apk.py", "script-build-installer.py", "script-build-tool-portable.py"]


@pytest.mark.parametrize("target", ["client", "tool", "mobile"])
def test_each_package_target_delegates_to_one_existing_owner(target):
    calls = []
    assert smarttest.main(["package", target], runner=lambda command, **kwargs: calls.append(command)) == 0
    assert len(calls) == 1


def test_web_is_explicitly_rejected_as_a_package_target(capsys):
    with pytest.raises(SystemExit) as error:
        smarttest.main(["package", "web"])
    assert error.value.code == 2
    assert "Web does not provide a release package" in capsys.readouterr().err


def test_web_package_cli_process_has_the_same_explicit_error():
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, str(root / "support/smarttest.py"), "package", "web"],
        cwd=root, capture_output=True, text=True,
    )
    assert result.returncode == 2
    assert "Web does not provide a release package" in result.stderr


def test_check_web_runs_backend_and_frontend_contracts():
    calls = []
    assert smarttest.main(["check", "web"], runner=lambda command, **kwargs: calls.append(command)) == 0
    flattened = [" ".join(command) for command in calls]
    assert any("pytest" in command and " tests " in f" {command} " for command in flattened)
    assert any(Path(command[0]).name.lower() in {"npm", "npm.cmd", "npm.exe"} and command[1:] == ["run", "test"] for command in calls)
    assert any(command[1:] == ["run", "lint"] for command in calls)
    assert any(command[1:] == ["run", "build"] for command in calls)


def test_backend_checks_run_from_the_independent_backend_root():
    calls = []
    smarttest.main(["check", "web"], runner=lambda command, **kwargs: calls.append((command, kwargs)))
    backend = next(item for item in calls if "pytest" in item[0])
    assert Path(backend[1]["cwd"]).as_posix().endswith("/web/backend")


def test_npm_launcher_is_windows_compatible():
    launcher = Path(smarttest._npm())
    assert launcher.name.lower() in {"npm", "npm.cmd", "npm.exe"}
    assert launcher.exists() or str(launcher) == "npm"


def test_dev_all_builds_mobile_before_starting_three_long_running_processes():
    bootstrap, processes, addresses = smarttest._dev_plan("all")
    assert Path(bootstrap[0][0][0]).name.lower() in {"gradlew", "gradlew.bat"}
    assert len(processes) == 3
    assert set(addresses) == {"Client", "Web API", "Web UI"}


def _workflow(name):
    path = Path(__file__).resolve().parents[2] / ".github" / "workflows" / name
    return path.read_text(encoding="utf-8")


def test_ci_workflow_checks_push_and_pull_request_without_packaging():
    text = _workflow("ci.yml")
    assert "  push:" in text
    assert "  pull_request:" in text
    assert "support/smarttest.py check" in text
    assert "support/smarttest.py package" not in text
    assert text.count("- '.github/**'") == 3


def test_release_workflow_is_tag_only_self_hosted_and_has_no_web_package():
    text = _workflow("release.yml")
    assert "tags: ['v*']" in text
    assert "runs-on: [self-hosted, Windows, X64, smarttest-release]" in text
    assert "support\\smarttest.py package all" in text.replace("/", "\\")
    assert "package web" not in text
    assert "actions/upload-artifact" in text
    assert text.index("SMARTTEST_SIGNAPK_DIR") < text.index("script-init-venv.py")
    assert text.index("script-init-venv.py") < text.index(".venv\\Scripts\\python.exe support\\smarttest.py package all")
    assert "dist/mobile/app-debug-platform.apk" in text
    assert "dist/client/SmartTest-Setup.exe" in text
    assert "dist/tool/SmartTestTool-*.zip" in text


def test_windows_bootstrap_creates_dot_venv_and_installs_required_packages(tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/script-init-venv.py"))
    calls = []
    module["initialize_environment"](
        tmp_path,
        runner=lambda command, **kwargs: calls.append((command, kwargs)),
    )
    commands = [command for command, _ in calls]
    assert commands[0][-2:] == ["venv", str(tmp_path / ".venv")]
    assert commands[1][:4] == [str(tmp_path / ".venv" / "Scripts/python.exe"), "-m", "pip", "install"]
    assert any(argument.startswith("pytest==") for argument in commands[1])
    assert any(argument.startswith("uiautomator2==") for argument in commands[1])
    assert any(argument.startswith("xlrd==") for argument in commands[1])
    assert commands[2][-4:] == ["-m", "playwright", "install", "chromium"]
    assert commands[3] == [
        str(tmp_path / ".venv" / "Scripts/python.exe"),
        "-m", "pip", "install", "-r", str(tmp_path / "web/backend/requirements.txt"),
        "-r", str(tmp_path / "web/backend/requirements-dev.txt"),
    ]
    assert commands[4] == ["npm.cmd", "ci"]
    assert calls[4][1]["cwd"] == tmp_path / "web/frontend"


def test_bootstrap_reuses_existing_dot_venv_without_recreating_running_python(tmp_path):
    module = runpy.run_path(str(Path(__file__).resolve().parents[1] / "scripts/script-init-venv.py"))
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    calls = []

    module["initialize_environment"](
        tmp_path,
        runner=lambda command, **kwargs: calls.append(command),
    )

    assert [sys.executable, "-m", "venv", str(tmp_path / ".venv")] not in calls
    assert calls[0][:4] == [str(python), "-m", "pip", "install"]


def test_tool_build_separates_runtime_staging_from_release_archive():
    root = Path(__file__).resolve().parents[2]
    module = runpy.run_path(str(root / "support/scripts/script-build-tool-portable.py"))

    assert module["STAGING_ROOT"] == root / "build" / "tool_runtime"
    assert module["DIST_ROOT"] == root / "dist" / "tool"
    assert module["STAGING_ROOT"] / module["APP_NAME"] != (
        module["DIST_ROOT"] / module["APP_NAME"]
    )
