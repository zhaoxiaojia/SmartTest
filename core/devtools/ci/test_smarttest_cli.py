from pathlib import Path
import os
import runpy
import shutil
import subprocess
import sys

import pytest

from core.devtools import smarttest


ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("action", ["check", "package"])
def test_all_reuses_each_single_product_script_in_order(action):
    calls = []
    assert smarttest.main([action, "all"], runner=lambda command, **kwargs: calls.append(command)) == 0
    product_scripts = [Path(command[1]).as_posix() for command in calls if "/scripts/" in Path(command[1]).as_posix()]
    assert product_scripts == [
        str(ROOT / product / "scripts" / f"{action}.py").replace("\\", "/")
        for product in ("client", "web", "mobile")
    ]


@pytest.mark.parametrize("action", ["check", "package"])
@pytest.mark.parametrize("product", ["client", "web", "mobile"])
def test_single_product_routes_to_one_product_owned_script(action, product):
    calls = []
    smarttest.main([action, product], runner=lambda command, **kwargs: calls.append(command))
    product_calls = [command for command in calls if "/scripts/" in Path(command[1]).as_posix()]
    assert len(product_calls) == 1
    assert Path(product_calls[0][1]) == ROOT / product / "scripts" / f"{action}.py"


def test_check_runs_shared_boundary_once_before_product_script():
    calls = []
    smarttest.main(["check", "web"], runner=lambda command, **kwargs: calls.append(command))
    assert Path(calls[0][1]) == ROOT / "core/devtools/ci/check_product_boundaries.py"
    assert Path(calls[1][1]) == ROOT / "web/scripts/check.py"


def test_dev_is_product_owned_not_a_unified_command():
    with pytest.raises(SystemExit) as error:
        smarttest.main(["dev", "all"])
    assert error.value.code == 2
    assert (ROOT / "client/scripts/dev.py").is_file()
    assert (ROOT / "web/scripts/dev.py").is_file()


def test_web_dev_exposes_frontend_to_local_network():
    module = runpy.run_path(str(ROOT / "web/scripts/dev.py"), run_name="migration_contract")
    calls = []
    python = (ROOT / "outside/python.exe").resolve()
    npm = Path(shutil.which("npm.cmd")).resolve()
    module["run"].__globals__["resolve_runtime_tools"] = lambda: (python, npm)

    class FinishedProcess:
        returncode = 1

        @staticmethod
        def poll():
            return 1

        @staticmethod
        def wait(timeout=None):
            return 1

    result = module["run"](
        popen=lambda command, **kwargs: calls.append((command, kwargs)) or FinishedProcess(),
        port_in_use=lambda: False,
        wait_for_health=lambda _processes: False,
        terminate_tree=lambda _process: None,
        wait_for_port_release=lambda: True,
    )

    assert result == 1
    assert Path(calls[0][0][0]) == python
    assert Path(calls[1][0][0]) == npm
    assert calls[1][0][-3:] == ["--", "--host", "0.0.0.0"]
    assert calls[1][1]["env"]["PATH"].split(os.pathsep)[0] == str(npm.parent)


def test_bootstrap_reuses_existing_dot_venv_without_recreating_running_python(tmp_path):
    module = runpy.run_path(str(ROOT / "core/devtools/scripts/init_venv.py"))
    python = tmp_path / ".venv" / "Scripts" / "python.exe"
    python.parent.mkdir(parents=True)
    python.touch()
    calls = []
    module["initialize_environment"](tmp_path, runner=lambda command, **kwargs: calls.append((command, kwargs)))
    commands = [command for command, _ in calls]
    assert [sys.executable, "-m", "venv", str(tmp_path / ".venv")] not in commands
    assert commands[0][:4] == [str(python), "-m", "pip", "install"]
    assert [str(python), "-m", "nodeenv", "-p", "--node=22.14.0", "--prebuilt"] in commands
    assert commands[-1][0] == str(tmp_path / ".venv/Scripts/npm.cmd")
    assert calls[-1][1]["env"]["PATH"].split(os.pathsep)[0] == str(python.parent)


def test_web_check_and_package_use_managed_npm():
    for script in ("check.py", "package.py"):
        module = runpy.run_path(str(ROOT / "web/scripts" / script), run_name="migration_contract")
        calls = []
        module["main"](runner=lambda command, **kwargs: calls.append((command, kwargs)))
        npm_calls = [(command, kwargs) for command, kwargs in calls if len(command) > 1 and command[1] == "run"]
        assert npm_calls
        assert all(Path(command[0]) == ROOT / ".venv/Scripts/npm.cmd" for command, _ in npm_calls)
        assert all(kwargs["env"]["PATH"].split(os.pathsep)[0] == str(ROOT / ".venv/Scripts") for _, kwargs in npm_calls)


def test_client_package_reuses_installer_and_portable_owners():
    module = runpy.run_path(str(ROOT / "client/scripts/package.py"))
    calls = []
    module["main"](runner=lambda command, **kwargs: calls.append(command))
    assert [Path(command[1]).name for command in calls] == [
        "build_installer.py",
        "build_tool_portable.py",
    ]


def test_product_scripts_are_importable_without_running_tools():
    for path in (
        ROOT / "client/scripts/check.py",
        ROOT / "client/scripts/package.py",
        ROOT / "web/scripts/check.py",
        ROOT / "web/scripts/package.py",
        ROOT / "mobile/scripts/check.py",
        ROOT / "mobile/scripts/package.py",
    ):
        namespace = runpy.run_path(str(path), run_name="migration_contract")
        assert callable(namespace["main"])


def test_ci_and_release_workflows_use_new_orchestrator():
    ci = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")
    release = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "core/devtools/smarttest.py check" in ci
    assert "core\\devtools\\smarttest.py package all" in release.replace("/", "\\")
    assert "support/" not in ci and "support\\" not in release
